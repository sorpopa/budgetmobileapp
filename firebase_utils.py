import firebase_admin
import requests
from firebase_admin import credentials, firestore, auth
import json


class FirebaseAuth:
    def __init__(self, api_key, service_account_path):
        self.api_key = api_key
        self.auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts"

        # Initialize Firebase Admin SDK
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)

    def sign_up(self, email, password):
        """Create new user account"""
        url = f"{self.auth_url}:signUp?key={self.api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json()
                return {"error": error_data.get("error", {}).get("message", "Unknown error")}
        except Exception as e:
            return {"error": str(e)}

    def verify_token(self, id_token):
        """Verify ID token using Admin SDK"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            return {"error": str(e)}

    def sign_in(self, email, password):
        """Sign in existing user"""
        url = f"{self.auth_url}:signInWithPassword?key={self.api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json()
                return {"error": error_data.get("error", {}).get("message", "Unknown error")}
        except Exception as e:
            return {"error": str(e)}