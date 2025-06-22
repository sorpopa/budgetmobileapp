from flask import Flask, request, jsonify, redirect, session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(16))

# Firebase setup
cred = credentials.Certificate('firebase-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()  #creates firestore database client for data operations

# Load environment variables with explicit path
basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')

load_dotenv()

# Get credentials
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Validate credentials
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise ValueError("Missing Google OAuth credentials in environment variables")

# The redirect URI must EXACTLY match what's in Google Cloud Console
REDIRECT_URI = 'http://localhost:5000/callback'

# Create the OAuth configuration
GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI]
    }
}

# OAuth flow
flow = Flow.from_client_config(
    GOOGLE_CLIENT_CONFIG,
    scopes=['openid', 'email', 'profile'],
    redirect_uri=os.getenv('REDIRECT_URI', 'http://localhost:5000/callback')
)


@app.route('/auth/login')
def login():
    """Start OAuth flow"""
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)


@app.route('/callback')
def callback():
    """Handle OAuth callback"""
    try:
        # Verify state parameter
        if request.args.get('state') != session.get('state'):
            return jsonify({'error': 'Invalid state parameter'}), 400

        # Exchange authorization code for tokens
        flow.fetch_token(authorization_response=request.url)

        # Get user info
        credentials = flow.credentials
        user_info = get_user_info(credentials)

        # Store user in Firebase
        user_ref = db.collection('users').document(user_info['id'])
        user_ref.set({
            'email': user_info['email'],
            'name': user_info['name'],
            'picture': user_info.get('picture', ''),
            'last_login': firestore.SERVER_TIMESTAMP
        }, merge=True)

        # Store session
        session['user_id'] = user_info['id']
        session['user_email'] = user_info['email']
        session['user_name'] = user_info['name']

        # Redirect to success page (you can customize this)
        return redirect('http://localhost:8080/auth-success')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_user_info(credentials):
    """Get user info from Google"""
    import requests

    response = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {credentials.token}'}
    )
    return response.json()


@app.route('/auth/user')
def get_current_user():
    """Get current authenticated user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    return jsonify({
        'id': session['user_id'],
        'email': session['user_email'],
        'name': session['user_name']
    })


@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


# Expense endpoints
@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    """Get user's expenses"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']

    # Get user's own expenses
    expenses_ref = db.collection('expenses').where('owner_id', '==', user_id)
    expenses = []

    for doc in expenses_ref.stream():
        expense_data = doc.to_dict()
        expense_data['id'] = doc.id
        expenses.append(expense_data)

    # Get shared expenses
    shared_ref = db.collection('expenses').where('shared_with', 'array_contains', session['user_email'])

    for doc in shared_ref.stream():
        expense_data = doc.to_dict()
        expense_data['id'] = doc.id
        expense_data['is_shared_with_me'] = True
        expenses.append(expense_data)

    return jsonify(expenses)


@app.route('/api/expenses', methods=['POST'])
def create_expense():
    """Create a new expense"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.json
    user_id = session['user_id']
    user_email = session['user_email']

    # Validate required fields
    required_fields = ['amount', 'category', 'description']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Process sharing
    shared_with = data.get('shared_with', [])
    split_amounts = data.get('split_amounts', {})

    expense_data = {
        'amount': float(data['amount']),
        'category': data['category'],
        'description': data['description'],
        'owner_id': user_id,
        'owner_email': user_email,
        'shared_with': shared_with,
        'split_amounts': split_amounts,
        'is_shared': len(shared_with) > 0,
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP
    }

    # Save to Firebase
    doc_ref = db.collection('expenses').add(expense_data)

    # Send notifications to shared users (optional)
    if shared_with:
        send_share_notifications(expense_data, shared_with)

    return jsonify({'id': doc_ref[1].id, 'message': 'Expense created successfully'})


@app.route('/api/expenses/<expense_id>', methods=['PUT'])
def update_expense(expense_id):
    """Update an expense"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    data = request.json

    # Check if user owns the expense
    expense_ref = db.collection('expenses').document(expense_id)
    expense = expense_ref.get()

    if not expense.exists:
        return jsonify({'error': 'Expense not found'}), 404

    expense_data = expense.to_dict()
    if expense_data['owner_id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Update fields
    update_data = {
        'updated_at': firestore.SERVER_TIMESTAMP
    }

    allowed_fields = ['amount', 'category', 'description', 'shared_with', 'split_amounts']
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]

    update_data['is_shared'] = len(update_data.get('shared_with', [])) > 0

    expense_ref.update(update_data)
    return jsonify({'message': 'Expense updated successfully'})


@app.route('/api/expenses/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete an expense"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']

    # Check if user owns the expense
    expense_ref = db.collection('expenses').document(expense_id)
    expense = expense_ref.get()

    if not expense.exists:
        return jsonify({'error': 'Expense not found'}), 404

    expense_data = expense.to_dict()
    if expense_data['owner_id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    expense_ref.delete()
    return jsonify({'message': 'Expense deleted successfully'})


@app.route('/api/budget', methods=['GET', 'POST'])
def budget_config():
    """Get or set budget configuration"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    budget_ref = db.collection('budgets').document(user_id)

    if request.method == 'GET':
        budget = budget_ref.get()
        if budget.exists:
            return jsonify(budget.to_dict())
        else:
            return jsonify({'budget_amount': 0.0, 'budget_start_day': 1})

    elif request.method == 'POST':
        data = request.json
        budget_data = {
            'budget_amount': float(data.get('budget_amount', 0)),
            'budget_start_day': int(data.get('budget_start_day', 1)),
            'updated_at': firestore.SERVER_TIMESTAMP
        }

        budget_ref.set(budget_data, merge=True)
        return jsonify({'message': 'Budget saved successfully'})


def send_share_notifications(expense_data, shared_emails):
    """Send notifications to users when expense is shared (optional implementation)"""
    # You can implement email notifications here using SendGrid, etc.
    pass


if __name__ == '__main__':
    app.run(debug=True, port=5000)