import flet as ft
import json
import os
from pathlib import Path
from datetime import datetime


class AuthManager:
    def __init__(self):
        self.user_data_file = self._get_user_data_path()
        self.current_user = None

    def _get_user_data_path(self):
        """Get platform-appropriate path for storing user data"""
        if hasattr(ft, 'platform') and ft.platform in ['android', 'ios']:
            # For mobile platforms, use app's data directory
            return os.path.join(os.path.expanduser('~'), '.expense_tracker', 'user_data.json')
        else:
            # For desktop, use user's home directory
            home_dir = Path.home()
            app_dir = home_dir / '.expense_tracker'
            app_dir.mkdir(exist_ok=True)
            return app_dir / 'user_data.json'

    def save_user_session_preference(self, preference, id_token, refresh_token, user_id):
        """Save user session data locally"""
        user_data = {
            'remember_me': preference,
            'id_token': id_token,
            'refresh_token': refresh_token,
            'user_id': user_id,
            'saved_at': str(datetime.now())
        }
        print(f"Saving user session {user_data}")

        try:
            os.makedirs(os.path.dirname(self.user_data_file), exist_ok=True)
            with open(self.user_data_file, 'w') as f:
                json.dump(user_data, f)
            self.current_user = user_data
            return True
        except Exception as e:
            print(f"Error saving user session: {e}")
            return False

    def load_user_session(self):
        """Load saved user session"""
        print("Trying to load user data. ")
        try:
            if os.path.exists(self.user_data_file):
                print(f"user data exists at {self.user_data_file} ")
                with open(self.user_data_file, 'r') as f:
                    user_data = json.load(f)
                    if user_data.get('remember_me', False):
                        print(f"user data is {user_data.get('remember_me', False)}")
                        self.current_user = user_data
                        print(f"user data {user_data}")
                        return user_data
            else:
                print(f"No preferences file found at: {self.user_data_file}")
                return {"remember_user": False, "user_token": None}
        except Exception as e:
            print(f"Error loading preferences: {e}")
            return {"remember_user": False, "user_token": None}

    def clear_user_session(self):
        """Clear saved user session (logout)"""
        try:
            if os.path.exists(self.user_data_file):
                os.remove(self.user_data_file)
            self.current_user = None
            return True
        except Exception as e:
            print(f"Error clearing user session: {e}")
            return False

    def is_logged_in(self):
        """Check if user is currently logged in"""
        return self.current_user is not None and self.current_user.get('is_logged_in', False)