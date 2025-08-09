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

    def refresh_id_token(self, refresh_token):
        print("refre_id_token function")
        url = f"https://securetoken.googleapis.com/v1/token?key={self.api_key}"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        response = requests.post(url, data=payload)
        print(f"response for token refresh {response}")
        if response.status_code == 200:
            data = response.json()
            id_token = data['id_token']
            refresh_token = data['refresh_token']
            print(f"new tokens: {id_token, refresh_token}")
            return id_token, refresh_token

        else:
            print(f"Token refresh failed: {response.status_code}")
            print(f"Response: {response.text}")

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