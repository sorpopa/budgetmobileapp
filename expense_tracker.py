import flet as ft
import firebase_admin
import requests
import json
from firebase_admin import credentials, firestore, auth
from google.cloud import firestore as fire
from datetime import datetime, timedelta
from typing import Dict
import os
from dotenv import load_dotenv
import random
import base64
from dateutil.relativedelta import relativedelta


import ai_utilities
from auth_manager import AuthManager
from friends_manager import FriendsUI, FriendsManager
from ai_utilities import FinancialAdviceGenerator
from claude_api import ClaudeUtilityFunctions

load_dotenv()


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


class BudgetApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Expense Tracker"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.db = None

        self.budget_amount = 0
        self.start_date = datetime.now().replace(day=1)
        self.end_date = datetime.now()
        self.expenses = []
        self.wishes = []
        self.analysis = []
        self.expense_form_dialog = None
        self.wish_list_form_dialog = None
        self.edit_expense_dialog = None
        self.editing_expense_id = None
        self.recurring_expenses = []
        self.recurring_expense_timestamps = []
        self.uploaded_image = None
        self.processed_expense_data = None
        self.file_picker = None
        self.recurring_only = False

        # Firebase configuration
        self.API_KEY = os.getenv('FIREBASE_API_KEY')
        self.SERVICE_ACCOUNT_PATH = os.getenv('SERVICE_ACCOUNT_PATH')
        self.firebase_auth = None
        self.current_user = None
        self.id_token = None
        self.user_id = None
        self.display_name = None
        self.currency = None
        self.available_avatars = None
        self.current_avatar = r"C:\Users\SPopa\PycharmProjects\ExpenseTracker\src\assets\fancy zebra.png"

        # UI Controls
        self.email_field = ft.TextField(label="Email", width=300)
        self.password_field = ft.TextField(label="Password", password=True, width=300)
        self.error_text = ft.Text(color=ft.colors.RED)
        self.user_info = ft.Text()
        self.remember_user = ft.Checkbox(label='Remember me', value=False)

        self.friend_list = []

        self.settings_file = "app_settings.json"
        self.default_settings = {
            "display_name": "User",
            "currency": "USD",
            "spending_alert_threshold": 80,  # Percentage of budget
            "budget_limit_warning": 90,  # Percentage of budget
            "bill_reminders": True,
            "weekly_summaries": True,
            "monthly_summaries": True,
            "goal_notifications": True,
            "notification_time": "09:00"  # Time for daily notifications
        }
        self.settings = self.load_settings()

        # Create main container
        self.main_container = ft.Column(
            controls=[self.create_auth_view()],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20
        )

        self.auth_manager = AuthManager()
        self.advice_generator = FinancialAdviceGenerator()
        #self.advice_generator = claude_api.FinancialAdviceGenerator()
        self.ai_analyst = ClaudeUtilityFunctions()
        self.initialize_firebase()

        self.check_existing_session()
        # self.setup_ui()

    def check_existing_session(self):
        print('Verify user session exists')
        user_session = self.auth_manager.load_user_session()
        remember_user = user_session.get('remember_me')
        stored_token = user_session.get('id_token')
        user_id = user_session.get('user_id')
        print(f"Saved user session: {user_session}")

        if remember_user and stored_token:
            if not self.db:
                print("⚠️ Firebase not initialized, initializing database")
                self.db = firestore.client()
            try:
                '''
                # Verify the ID token
                decoded_token = auth.verify_id_token(stored_token)
                self.user_id = decoded_token['uid']
                '''
                user = auth.get_user(user_id)
                print(f"user is {user}")
                if user:
                    self.user_id = user_id
                    user_doc = self.db.collection('users').document(self.user_id).get()
                    user_data = user_doc.to_dict()
                    print(f"User data is {user_data}")
                    self.current_user = {}
                    self.current_user['localId'] = self.user_id
                    self.current_user['email'] = user_data.get('email')
                    self.current_user['displayName'] = user_data.get('displayName')
                    self.current_user['idToken'] = user_data.get('idToken')
                    print("User exists, retrieved data, showing main page.")
                    self.show_main()
            except Exception as e:
                print(f"Token validation failed: {e}")
                self.setup_ui()
        else:
            self.setup_ui()

    def create_auth_view(self):
        """Create authentication UI"""
        self.status_text = ft.Text("")

        return ft.Container(
            content=ft.Column([
                ft.Text("Expense Tracker Login", size=24, weight=ft.FontWeight.BOLD),
                self.email_field,
                self.password_field,
                ft.Row([
                    ft.ElevatedButton("Sign In", on_click=self.sign_in_clicked),
                    ft.ElevatedButton("Sign Up", on_click=self.sign_up_clicked),
                    self.remember_user
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.TextButton("Reset Password", on_click=self.reset_password),
                self.error_text,
                self.user_info
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20
        )

    def sign_in_clicked(self, e):
        """Handle sign in button click"""
        email = self.email_field.value
        password = self.password_field.value

        if not email or not password:
            self.show_error("Please enter both email and password")
            return

        if not self.initialize_firebase():
            return

        try:
            result = self.firebase_auth.sign_in(email, password)

            if "error" in result:
                self.show_error(result["error"])
            else:
                self.current_user = result
                print(f"self.current user is {self.current_user}")
                self.id_token = result["idToken"]
                self.user_id = result["localId"]
                self.display_name = result['displayName']

                if self.remember_user.value:
                    self.auth_manager.save_user_session_preference(self.remember_user.value,
                                                                   id_token=self.id_token, user_id=self.user_id)

                self.show_main()
        except Exception as e:
            self.show_error(f"Sign in error: {str(e)}")

    def create_user_profile(self, user_id, email, display_name=None):
        try:
            user_data = {
                'email': email,
                'displayName': display_name or email.split('@')[0],
                'createdAt': fire.SERVER_TIMESTAMP
            }
            db = firestore.client()
            db.collection('users').document(user_id).set(user_data)

            return {"success": True, "message": "User profile created"}

        except Exception as e:
            return {"error": str(e)}

    def update_user_profile(self, user_id, field, value):
        try:
            self.db.collection('users').document(user_id).update({
                field: value
            })
            print(f"{field} updated successfully with value {value}")
        except Exception as e:
            print(f"Error updating {field}: {e}")

    def sign_up_clicked(self, e):
        """Handle sign up button click"""
        email = self.email_field.value
        password = self.password_field.value

        if not email or not password:
            self.show_error("Please enter both email and password")
            return

        if len(password) < 6:
            self.show_error("Password must be at least 6 characters")
            return

        # Initialize Firebase only when needed
        if not self.initialize_firebase():
            return

        try:
            result = self.firebase_auth.sign_up(email, password)

            if "error" in result:
                self.show_error(result["error"])
            else:
                self.current_user = result
                self.id_token = result["idToken"]
                self.user_id = result["localId"]

                self.create_user_profile(self.user_id, email)

                if self.remember_user:
                    self.auth_manager.save_user_session_preference(self.remember_user.value, id_token=self.id_token,
                                                                   user_id=self.user_id)

                self.show_main()


        except Exception as e:
            self.show_error(f"Sign up error: {str(e)}")

    def logout_clicked(self, e):
        """Handle logout"""
        self.current_user = None
        self.id_token = None
        self.email_field.value = ""
        self.password_field.value = ""
        self.error_text.value = ""

        self.auth_manager.clear_user_session()

        # Reset to auth view
        self.page.clean()
        auth_view = self.create_auth_view()
        self.page.add(auth_view)
        self.page.update()

    def show_error(self, message):
        """Display error message"""
        self.error_text.value = message
        self.page.update()

    def initialize_firebase(self):
        """Initialize Firebase only when needed"""
        if self.firebase_auth is None:
            try:
                self.firebase_auth = FirebaseAuth(self.API_KEY, self.SERVICE_ACCOUNT_PATH)
                print("Firebase initialized successfully")
                return True
            except Exception as e:
                self.show_error(f"Firebase initialization error: {str(e)}")
                print(f"Firebase initialization failed: {e}")
                return False
        return True

    def setup_ui(self):
        """Setup the initial UI"""
        try:
            # Clear the page first
            self.page.clean()

            # Add the authentication view
            auth_view = self.create_auth_view()
            self.page.add(auth_view)
            self.page.update()

            print("UI setup complete")  # Debug print

        except Exception as e:
            print(f"Error setting up UI: {e}")
            # Add a simple fallback UI
            self.page.add(ft.Text("Error loading app"))
            self.page.update()

    def show_main(self):
        # Clear the page first
        print("Calling show_main function")
        print(f"User id is {self.user_id}")
        self.page.clean()

        self.expenses_list = ft.ListView(spacing=10, padding=20, auto_scroll=False, height=500)
        self.wish_list = ft.ListView(spacing=10, padding=20, auto_scroll=False, height=300)
        self.analysis_list = ft.ListView(spacing=10, padding=20, auto_scroll=False, height=300)

        self.recurring_checkbox = ft.Checkbox(label="Recurring expenses", on_change=self.update_expenses_list)
        self.filter_category_options = [ft.dropdown.Option("All")]
        self.filter_category_options += self.show_expense_category()


        self.period_filter = ft.Tabs(is_secondary=True, selected_index=0,
                                     on_change=self.update_expenses_list,
                                     tabs=[
                                         ft.Tab(text="1M"),
                                         ft.Tab(text="2M"),
                                         ft.Tab(text="3M"),
                                         ft.Tab(text="6M"),
                                         ft.Tab(text="12M"),
                                         ft.Tab(text="All"),
                                     ])
        self.pie_filter = ft.Tabs(is_secondary=True, selected_index=0,
                                  on_change=self.create_pie_sections,
                                  tabs=[
                                      ft.Tab(text="1M"),
                                      ft.Tab(text="2M"),
                                      ft.Tab(text="3M"),
                                      ft.Tab(text="6M"),
                                      ft.Tab(text="12M"),
                                      ft.Tab(text="All"),
                                  ])

        self.wish_list_filter = ft.Tabs(is_secondary=True, selected_index=0,
                                        on_change=self.update_wish_list,
                                        tabs=[
                                            ft.Tab(text="1M"),
                                            ft.Tab(text="2M"),
                                            ft.Tab(text="3M"),
                                            ft.Tab(text="6M"),
                                            ft.Tab(text="12M"),
                                            ft.Tab(text="All"),
                                        ])
        print("Loading budget")

        # Load initial data
        self.load_budget_data()
        self.load_expenses()
        self.load_wish_list()
        self.load_analysis_list()
        self.load_settings()
        self.load_avatar()

        friends_ui = FriendsUI(self.page, self.user_id)

        print("Creating tabs")

        # Create tabs
        self.overview_tab = self.create_overview_tab()
        self.expenses_tab = self.create_expenses_tab()
        self.charts_tab = self.create_charts_tab()
        self.wish_list_tab = self.create_wish_list_tab()

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Overview",
                    content=self.overview_tab,
                ),
                ft.Tab(
                    text="Expenses",
                    content=self.expenses_tab
                ),
                ft.Tab(
                    text="My Wish List",
                    content=self.wish_list_tab
                ),
                ft.Tab(text="Friends", content=friends_ui.create_friends_view())
            ],
            expand=True
        )

        self.page.add(self.tabs)

    def test_firebase_connection(self):
        """Test Firebase connection and display current data"""
        if not self.db:
            print("⚠️ Firebase not initialized, skipping connection test")
            return False

        try:
            print("🔍 Testing Firebase connection...")

            # Test budget data
            budget_doc = self.db.collection('budget').document('current').get()
            if budget_doc.exists:
                print(f"💰 Budget data found: {budget_doc.to_dict()}")
            else:
                print("📋 No budget data found")

            # Test expenses data
            expenses_ref = self.db.collection('expenses').limit(5)
            expenses = list(expenses_ref.stream())
            print(f"🧾 Found {len(expenses)} expenses (showing up to 5):")

            for i, expense in enumerate(expenses, 1):
                data = expense.to_dict()
                print(f"  {i}. ID: {expense.id}")
                print(f"     Amount: ${data.get('amount', 0)}")
                print(f"     Category: {data.get('category', 'N/A')}")
                print(f"     Date: {data.get('date', 'N/A')}")
                print()

            return True

        except Exception as e:
            print(f"❌ Firebase connection test failed: {e}")
            return False

    def create_overview_tab(self):
        """Create the overview tab with budget configuration and summary"""
        print('Creating overview tab')

        advice_text = self.generate_themed_advice()

        advice_display = ft.Text(
            value=advice_text,
            size=14,
            color=ft.colors.GREEN_700,
            text_align=ft.TextAlign.CENTER,
            weight=ft.FontWeight.W_500
        )

        # Budget summary
        self.budget_summary = ft.Container(
            content=ft.Column([
                ft.Text("Budget Summary", size=20, weight=ft.FontWeight.BOLD),
                #ft.Divider(),
            ]),
            padding=10,
            #border=ft.border.all(1, ft.colors.GREY_400),
            #border_radius=10,
           # margin=ft.margin.only(top=20)
        )

        self.budget_progress_card = ft.Container(
                content=ft.Column([
                        ft.Row([
                            ft.Text("Budget Progress", size=16, weight=ft.FontWeight.BOLD),
                            ])])
                        )
        self.quick_insights_row = ft.Container(
                content=ft.Column([
                        ft.Row([
                            ft.Text("Insights card", size=16, weight=ft.FontWeight.BOLD),
                            ])])
                        )
        self.highest_expenses_card = ft.Container(
                content=ft.Column([
                        ft.Row([
                            ft.Text("Expense card", size=16, weight=ft.FontWeight.BOLD),
                            ])])
                        )
        self.recent_transactions_card = ft.Container(
                content=ft.Column([
                        ft.Row([
                            ft.Text("Recent Transactions", size=16, weight=ft.FontWeight.BOLD),
                            ])])
                        )

        self.nugget = ft.Container(
            content=ft.Column([
                ft.Text("Advice of the day", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                advice_display
            ]),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            margin=ft.margin.only(top=20)
        )
        self.pie_chart = ft.PieChart(
            sections=self.create_pie_sections(),
            sections_space=0.1,
            center_space_radius=20,
        )

        self.main_avatar_container = ft.Container(
            content=ft.Image(
                src=self.current_avatar,
                fit=ft.ImageFit.COVER,
            ),
            width=100,
            height=100,
            border_radius=50,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.border.all(3, ft.colors.BLUE_400),  # Add border
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=3,
                color=ft.colors.GREY_400, )
        )

        self.update_budget_summary()
        self.create_budget_progress_card()
        self.create_quick_insights_row()
        self.create_highest_expenses_card()
        self.create_recent_transactions_card()

        return ft.Container(
            content=ft.ListView([
                # Header with avatar and settings
                self.create_header_section(),

                # Motivational quote (moved to bottom, smaller)
                self.create_quote_section(),

                # Key metrics cards row
                self.budget_summary,

                # Budget progress card
                self.budget_progress_card,

                # Quick insights row (shared expenses + weekly trend)
                self.quick_insights_row,

                # Highest expenses card
                self.highest_expenses_card,

                # Recent transactions preview
                self.recent_transactions_card,

            ], spacing=20, padding=ft.padding.all(0)),
            padding=ft.padding.all(20),
            bgcolor=ft.colors.GREY_50,  # Light background for better contrast,

        )

    def create_header_section(self):
        print("Creating header section")
        return ft.Container(
            content=ft.Row([
                ft.Row([
                    self.main_avatar_container,
                    ft.Column([
                        ft.Text(f"Welcome back!", size=14, color=ft.colors.GREY_600),
                        ft.Text(f"{self.current_user['displayName']}", size=18, weight=ft.FontWeight.BOLD),
                    ], spacing=0),
                ], spacing=12),
                ft.Row([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.ADD_CIRCLE, size=18, color=ft.colors.WHITE),
                            ft.Text("Add Expense", size=12, weight=ft.FontWeight.W_600, color=ft.colors.WHITE)
                        ], spacing=10),
                        padding=ft.padding.symmetric(horizontal=20, vertical=14),
                        bgcolor=ft.colors.GREEN_600,
                        border_radius=12,
                        border=ft.border.all(1, ft.colors.GREEN_200),
                        on_click=self.show_add_expense_dialog,
                        ink=True,  # Adds ripple effect
                        # Add shadow for depth
                        shadow=ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=8,
                            color=ft.colors.with_opacity(0.3, ft.colors.GREEN_600),
                            offset=ft.Offset(0, 3)
                        ),
                    ),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.CAMERA_ALT, size=18, color=ft.colors.BLUE_700),
                            ft.Text("From Picture", size=12, weight=ft.FontWeight.W_600, color=ft.colors.BLUE_700)
                        ], spacing=10),
                        padding=ft.padding.symmetric(horizontal=20, vertical=14),
                        bgcolor=ft.colors.WHITE,
                        border_radius=16,
                        border=ft.border.all(2, ft.colors.BLUE_600),
                        on_click=self.add_expense_from_picture_dialog,
                        ink=True,
                        # Add subtle shadow
                        shadow=ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=6,
                            color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                            offset=ft.Offset(0, 2)
                        )
                    ),
                    self.open_settings_menu()
                ], alignment=ft.MainAxisAlignment.END),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            margin=ft.margin.only(bottom=10)
        )

    def create_budget_progress_card(self):
        print("Creating budget progress card from create_budget_progress_card")
        budget_amount = self.budget_amount
        total_expenses = self.get_total_expenses()
        budget_used_percent = (total_expenses / budget_amount) * 100 if budget_amount > 0 else 0

        # Choose color based on usage
        if budget_used_percent < 50:
            progress_color = ft.colors.GREEN_400
            bg_color = ft.colors.GREEN_50
        elif budget_used_percent < 80:
            progress_color = ft.colors.ORANGE_400
            bg_color = ft.colors.ORANGE_50
        else:
            progress_color = ft.colors.RED_400
            bg_color = ft.colors.RED_50

        # Calculate daily average and days remaining
        daily_average = self.get_daily_average_spending()
        days_remaining = self.get_days_remaining_in_budget_period()

        self.budget_progress_card.content = ft.Container(
            content=ft.Column([
                # Header with better typography
                ft.Row([
                    ft.Text("Budget Progress", size=18, weight=ft.FontWeight.BOLD,
                            color=ft.colors.GREY_800),
                    ft.Container(
                        content=ft.Text(f"{budget_used_percent:.1f}%",
                                        size=16, weight=ft.FontWeight.BOLD,
                                        color=ft.colors.WHITE),
                        bgcolor=progress_color,
                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        border_radius=20,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Container(height=16),

                # Enhanced progress bar with better visual treatment
                ft.Container(
                    content=ft.ProgressBar(
                        value=budget_used_percent / 100,
                        color=progress_color,
                        bgcolor=ft.colors.GREY_100,
                        height=12,
                        border_radius=6
                    ),
                    # Add a subtle container around progress bar
                    padding=ft.padding.all(2),
                    bgcolor=ft.colors.GREY_50,
                    border_radius=8,
                ),

                ft.Container(height=12),

                # Better aligned range indicators
                ft.Row([
                    ft.Text(f"0 {self.currency}", size=12, color=ft.colors.GREY_500),
                    ft.Text(f"{budget_amount:.0f} {self.currency}", size=12, color=ft.colors.GREY_500),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Container(height=16),

                # Enhanced stats row with icons
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.icons.CALENDAR_TODAY, size=16, color=ft.colors.GREY_600),
                        ft.Text(f"Daily avg: {daily_average:.2f} {self.currency}",
                                size=13, color=ft.colors.GREY_600, weight=ft.FontWeight.W_500),
                    ], spacing=6),
                    ft.Row([
                        ft.Icon(ft.icons.SCHEDULE, size=16, color=ft.colors.GREY_600),
                        ft.Text(f"{days_remaining} days left",
                                size=13, color=ft.colors.GREY_600, weight=ft.FontWeight.W_500),
                    ], spacing=6),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=0),
            bgcolor=ft.colors.TEAL_50,
            border_radius=16,
            padding=24,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                offset=ft.Offset(0, 2)
            ),
            border=ft.border.all(1, ft.colors.TEAL_300)
        )

        if self.page:
            self.page.update()

    def create_quick_insights_row(self):
        print("Creating create_quick_insights_row")
        #owed_amount = self.get_owed_amount()
        weekly_change = self.get_weekly_spending_change()

        self.quick_insights_row.content = ft.Row([
            # Shared expenses card with improved design
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.PEOPLE_ALT, size=20, color=ft.colors.ORANGE_700),
                        ft.Text("Shared", size=14, color=ft.colors.GREY_700,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8),
                    ft.Container(height=12),
                    self.update_shared_expenses()  # Your existing method
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                bgcolor=ft.colors.ORANGE_50,
                border_radius=16,
                padding=20,
                expand=1,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=6,
                    color=ft.colors.with_opacity(0.08, ft.colors.BLACK),
                    offset=ft.Offset(0, 2)
                ),
                border=ft.border.all(1, ft.colors.ORANGE_300)
            ),

            # Weekly trend card with better visual hierarchy
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(
                            ft.icons.TRENDING_UP if weekly_change >= 0 else ft.icons.TRENDING_DOWN,
                            size=20,
                            color=ft.colors.RED_700 if weekly_change >= 0 else ft.colors.GREEN_700
                        ),
                        ft.Text("This Week", size=14, color=ft.colors.GREY_700,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8),
                    ft.Container(height=12),
                    ft.Text(
                        f"{'+' if weekly_change >= 0 else ''}{weekly_change:.2f} {self.currency}",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.colors.RED_700 if weekly_change >= 0 else ft.colors.GREEN_700
                    ),
                    ft.Text("vs last week", size=12, color=ft.colors.GREY_500),
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                bgcolor=ft.colors.RED_50 if weekly_change >= 0 else ft.colors.GREEN_50,
                border_radius=16,
                padding=20,
                expand=1,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=6,
                    color=ft.colors.with_opacity(0.08, ft.colors.BLACK),
                    offset=ft.Offset(0, 2)
                ),
                border=ft.border.all(1, ft.colors.RED_300 if weekly_change >= 0 else ft.colors.GREEN_300)
            ),
        ], spacing=15)

        if self.page:
            self.page.update()

    def create_recent_transactions_card(self):
        print("creating recent transactions card")
        recent_transactions = self.get_recent_transactions(limit=4)  # Get last 4 transactions
        transaction_rows = []
        for transaction in recent_transactions:
            transaction_rows.append(
                ft.Container(
                content=ft.Row([
                    ft.Icon(
                        self.get_category_icon(transaction['category']),
                        size=16,
                        color=ft.colors.TEAL_800
                    ),
                    ft.Text(transaction['category'], size=12, color=ft.colors.GREY_600),
                    ft.Column([
                        ft.Text(transaction['description'], size=14, weight=ft.FontWeight.BOLD),
                    ], spacing=0, expand=1),
                    ft.Text(f"-{transaction['amount']:.2f} Lei", size=14, weight=ft.FontWeight.BOLD,
                            color=ft.colors.RED_600),
                ], spacing=10),
             bgcolor=ft.colors.TEAL_100
            ))

        self.recent_transactions_card.content = ft.Container(
            content=ft.Column([
                # Improved header with better spacing
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.RECEIPT_LONG, size=24, color=ft.colors.WHITE),
                        bgcolor=ft.colors.TEAL_600,
                        padding=8,
                        border_radius=8,
                    ),
                    ft.Text("Recent Transactions", size=18, weight=ft.FontWeight.BOLD,
                            color=ft.colors.GREY_800),
                    ft.Container(
                        content=ft.ElevatedButton(
                                    "View All",
                                    on_click=lambda _: self.switch_to_expenses_tab(),
                                    style=ft.ButtonStyle(
                                    color=ft.colors.WHITE,
                                    bgcolor=ft.colors.TEAL_600,
                                )
                            ),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Container(height=16),

                # Your existing transaction content
                ft.Column(transaction_rows, spacing=12) if transaction_rows else
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.RECEIPT_OUTLINED, size=48, color=ft.colors.GREY_300),
                        ft.Text("No recent transactions", size=14, color=ft.colors.GREY_500),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                    padding=ft.padding.all(24),
                    alignment=ft.alignment.center,
                ),
            ], spacing=0),
            bgcolor=ft.colors.WHITE,
            border_radius=16,
            padding=24,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                offset=ft.Offset(0, 2)
            )
        )
        if self.page:
            self.page.update()

    def create_highest_expenses_card(self):

        self.highest_expenses_card.content = ft.Container(
            content=ft.Column([
            # Better header design
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.BAR_CHART, size=24, color=ft.colors.WHITE),
                        bgcolor=ft.colors.BLUE_600,
                        padding=8,
                        border_radius=8,
                    ),
                    ft.Text("Top Categories", size=18, weight=ft.FontWeight.BOLD,
                        color=ft.colors.GREY_800),
                ], spacing=12),

                ft.Container(height=16),

            # Your existing content method
            self.get_highest_expenses(),
            ], spacing=0),
            bgcolor=ft.colors.PURPLE_50,
            border_radius=16,
            padding=24,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                offset=ft.Offset(0, 2)
                ),
            border=ft.border.all(1, ft.colors.PURPLE_300)
            )
        if self.page:
            self.page.update()

    def create_quote_section(self):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.LIGHTBULB_OUTLINE, size=20, color=ft.colors.WHITE),
                        bgcolor=ft.colors.GREEN_600,
                        padding=8,
                        border_radius=8,
                    ),
                    ft.Text("Daily Tip", size=16, weight=ft.FontWeight.BOLD,
                           color=ft.colors.GREY_800),
                ], spacing=12),

                ft.Container(height=12),

                ft.Text(
                    f"{self.generate_themed_advice()}",
                    size=13,
                    color=ft.colors.GREY_600,
                    text_align=ft.TextAlign.LEFT,
                    weight=ft.FontWeight.W_400
                ),
            ], spacing=0),
            bgcolor=ft.colors.GREEN_50,
            border_radius=16,
            padding=20,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=6,
                color=ft.colors.with_opacity(0.08, ft.colors.BLACK),
                offset=ft.Offset(0, 2)
            ),
            border=ft.border.all(1, ft.colors.GREEN_200)
        )

    def get_daily_average_spending(self):
        print("calculating average spending with function get_daily_average_spending")
        # Calculate based on total expenses and days in current period
        total_expenses = self.get_total_expenses()
        days_elapsed = self.get_days_elapsed_in_budget_period()
        return total_expenses / days_elapsed if days_elapsed > 0 else 0

    def get_days_remaining_in_budget_period(self):
        print("calculating days remaining with get_days_remaining_in_budget_period")
        print(f"type of end date is {type(self.end_date)}")
        end_datetime = self.end_date.replace(tzinfo=None)  # Remove timezone info if present
        current_datetime = datetime.now()

        # Calculate the difference
        date_difference = end_datetime - current_datetime

        # Get the number of days
        days_between = date_difference.days
        # Calculate remaining days in budget period
        return days_between

    def get_days_elapsed_in_budget_period(self):
        print("calculating days elapsed with get_days_elapsed_in_budget_period")
        # Calculate elapsed days in budget period
        start_datetime = self.start_date.replace(tzinfo=None)  # Remove timezone info if present
        current_datetime = datetime.now()

        # Calculate the difference
        date_difference = current_datetime - start_datetime

        # Get the number of days
        days_between = date_difference.days

        return days_between

    def get_weekly_spending_change(self):
        print("Entering get_weekly_spending_change")
        # Compare this week vs last week spending
        # Get current date and calculate week boundaries
        today = datetime.now()

        # Get start of current week (Monday)
        days_since_monday = today.weekday()
        this_week_start = today - timedelta(days=days_since_monday)
        this_week_start = this_week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get start of last week
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start

        this_week_total = 0
        last_week_total = 0

        for expense in self.expenses:
            # Convert date to datetime if it's a string
            if isinstance(expense['date'], str):
                expense_date = datetime.strptime(expense['date'], '%Y-%m-%d %H:%M:%S')
            else:
                expense_date = expense['date']

            # Remove time component for comparison
            expense_date = expense_date.replace(hour=0, minute=0, second=0, microsecond=0)

            # Check if expense is in current week
            if this_week_start <= expense_date <= today:
                this_week_total += expense['amount']

            # Check if expense is in previous week
            elif last_week_start <= expense_date < last_week_end:
                last_week_total += expense['amount']

        # Calculate difference and percentage change
        difference = this_week_total - last_week_total

        if last_week_total == 0:
            percentage_change = 100 if this_week_total > 0 else 0
        else:
            percentage_change = (difference / last_week_total) * 100


        return difference

    def get_recent_transactions(self, limit=4):
        return self.expenses[:limit]

    def switch_to_expenses_tab(self):
        """Navigate to Expenses tab when View All is clicked"""
        if self.tabs:
            self.tabs.selected_index = 1  # Index 1 = Expenses tab
            self.page.update()


    def create_expenses_tab(self):
        """Create the expenses tab with list of all expenses"""
        print("Creating expense tab")

        self.recurring_period = ft.Dropdown(
            label="Occurrence",
            options=[ft.dropdown.Option("No"),
                     ft.dropdown.Option("Monthly"),
                     ft.dropdown.Option("Yearly"),
                     ft.dropdown.Option("2 Months"),
                     ft.dropdown.Option("3 Months"),
                     ft.dropdown.Option("4 Months"),
                     ft.dropdown.Option("5 Months"),
                     ft.dropdown.Option("6 Months"),
                     ft.dropdown.Option("7 Months"),
                     ft.dropdown.Option("8 Months"),
                     ft.dropdown.Option("9 Months"),
                     ft.dropdown.Option("10 Months"),
                     ft.dropdown.Option("11 Months")],
            value="No",
            width=200,
        )
        occurence_options = ["All", "Periodic", "Not Periodic"]
        self.filter_ocurrence_options = []
        for option in occurence_options:
            self.filter_ocurrence_options.append(ft.dropdown.Option(option))

        filter_period_options = ["1M", "2M", "3M", "6M", "12M", "All"]
        self.filter_period_options = []
        for option in filter_period_options:
            self.filter_period_options.append(ft.dropdown.Option(option))


        self.recurring_day = datetime.now()
        self.recurring_date_picker = ft.DatePicker(
            on_change=self.on_recurring_date_change,
            first_date=datetime(2025, 1, 1),
            last_date=datetime(2030, 12, 31),
            current_date=datetime.now()
        )

        self.recurring_date_button = ft.TextButton(
            text=f"Recurring Date: {self.recurring_day.strftime('%Y-%m-%d')}",
            icon=ft.icons.CALENDAR_MONTH,
            on_click=self.open_recurring_date_picker,
            width=200
        )

        # Create a container to hold the tab content
        self.tab_content = ft.Column([], expand=True)

        self.analysis_button = ft.FloatingActionButton(
            icon=ft.icons.ADD,
            text="Generate AI Analysis",
            bgcolor=ft.colors.LIME_300,
            data=0,
            on_click=self.get_ai_analysis,
        )
        self.analysis_status_text = ft.Text("", color=ft.colors.GREY_600)

        self.category_filter = ft.Dropdown(
            label="Filter by Category",
            options=self.filter_category_options,
            value="All",
            width=200,
            bgcolor=ft.colors.GREEN_50,
            border_color=ft.colors.GREEN_300,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_expenses_list
        )
        self.time_period_filter = ft.Dropdown(
            label="Filter by Period",
            options=self.filter_period_options,
            value="1M",
            width=200,
            bgcolor=ft.colors.GREEN_50,
            border_color=ft.colors.GREEN_300,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_expenses_list
        )

        self.occurence_filter = ft.Dropdown(
            label="Filter by Occurrence",
            options=self.filter_ocurrence_options,
            value="All",
            width=200,
            bgcolor=ft.colors.GREEN_50,
            border_color=ft.colors.GREEN_300,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_expenses_list
        )


        def create_selected_expense_tab(e):
            self.tab_content.controls.clear()
            print(f"selected index is {expense_tab_selector.selected_index}")

            if expense_tab_selector.selected_index == 0:
                print("Creating expenses list tab")
                content = create_expenses_list_tab()
            elif expense_tab_selector.selected_index == 1:
                print("Creating AI analysis tab")
                content = create_ai_analysis_tab()
            elif expense_tab_selector.selected_index == 2:
                print("Creating charts tab")
                content = self.create_charts_tab()
            else:
                print("Creating expense review tab")
                content = create_expense_review_tab()
                # Add the new content
            self.tab_content.controls.append(content)
            print(f"Added content: {type(content)}")
            self.tab_content.update()
            self.page.update()  # Change this line

        expense_tab_selector = ft.Tabs(is_secondary=True, selected_index=0,
                                on_change=create_selected_expense_tab,
                                indicator_color=ft.colors.BLUE_600,
                                label_color=ft.colors.BLUE_600,
                                unselected_label_color=ft.colors.GREY_600,
                                tabs=[
                                    ft.Tab(
                                        text="Expenses",
                                        icon=ft.icons.RECEIPT_LONG
                                    ),
                                    ft.Tab(
                                        text="AI Insights",
                                        icon=ft.icons.AUTO_AWESOME
                                    ),
                                    ft.Tab(
                                        text="Charts",
                                        icon=ft.icons.BAR_CHART
                                    ),
                                    ft.Tab(
                                        text="Review",
                                        icon=ft.icons.RATE_REVIEW
                                    ),
                                ])

        self.page.overlay.append(self.recurring_date_picker)

        self.update_displays()

        def create_expenses_list_tab():
            print("entered create_expenses_list_tab function")
            return ft.Container(
                content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.ADD_CIRCLE, size=18, color=ft.colors.WHITE),
                                    ft.Text("Add Expense", size=12, weight=ft.FontWeight.W_600, color=ft.colors.WHITE)
                                ], spacing=10),
                                padding=ft.padding.symmetric(horizontal=20, vertical=14),
                                bgcolor=ft.colors.GREEN_600,
                                border_radius=12,
                                border=ft.border.all(1, ft.colors.GREEN_200),
                                on_click=self.show_add_expense_dialog,
                                ink=True,  # Adds ripple effect
                                # Add shadow for depth
                                shadow=ft.BoxShadow(
                                    spread_radius=0,
                                    blur_radius=8,
                                    color=ft.colors.with_opacity(0.3, ft.colors.GREEN_600),
                                    offset=ft.Offset(0, 3)
                                ),
                            ),
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.CAMERA_ALT, size=18, color=ft.colors.BLUE_700),
                                    ft.Text("From Picture", size=12, weight=ft.FontWeight.W_600,
                                            color=ft.colors.BLUE_700)
                                ], spacing=10),
                                padding=ft.padding.symmetric(horizontal=20, vertical=14),
                                bgcolor=ft.colors.WHITE,
                                border_radius=16,
                                border=ft.border.all(2, ft.colors.BLUE_600),
                                on_click=self.add_expense_from_picture_dialog,
                                ink=True,
                                # Add subtle shadow
                                shadow=ft.BoxShadow(
                                    spread_radius=0,
                                    blur_radius=6,
                                    color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                                    offset=ft.Offset(0, 2)
                                )
                            ),
                        ], alignment=ft.MainAxisAlignment.END),
                    ft.Row([
                        ft.Container(content=self.category_filter),
                        ft.Container(content=self.time_period_filter),
                        ft.Container(content=self.occurence_filter),
                    ]
                    ),
                    self.expenses_list,

                ])
            )

        def create_ai_analysis_tab():
            print("entered create_ai_analysis_tab function")
            self.update_analysis_button_state()
            # Header section with icon and title
            header_section = ft.Container(
                content=ft.Row([
                    ft.Icon(
                        ft.icons.AUTO_AWESOME,
                        color=ft.colors.PURPLE_400,
                        size=32
                    ),
                    ft.Column([
                        ft.Text(
                            "AI Insights",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            color=ft.colors.GREY_800,
                            font_family='Arial'
                        ),
                        ft.Text(
                            "Smart analysis of your spending patterns",
                            size=14,
                            color=ft.colors.GREY_600,
                            font_family='Arial'
                        )
                    ], spacing=2, expand=True)
                ], alignment=ft.MainAxisAlignment.START),
                padding=ft.padding.all(20),
                bgcolor=ft.colors.WHITE,
                border_radius=16,
                margin=ft.margin.only(bottom=16)
            )

            info_card = ft.Container(
                content=ft.Row([
                    ft.Icon(
                        ft.icons.INFO_OUTLINE,
                        color=ft.colors.BLUE_400,
                        size=20
                    ),
                    ft.Text(
                        "Analysis updates every 2 weeks based on your recent expenses to provide "
                        "meaningful insights and time for implementing suggestions.",
                        size=14,
                        color=ft.colors.BLUE_700,
                        font_family='Arial',
                        expand=True
                    )
                ], spacing=12),
                padding=ft.padding.all(16),
                bgcolor=ft.colors.BLUE_50,
                border_radius=12,
                border=ft.border.all(1, ft.colors.BLUE_200),
                margin=ft.margin.only(bottom=20)
            )

            # Analysis content area
            analysis_content = ft.Container(
                content=ft.Column([
                    self.analysis_list,
                    self.analysis_status_text
                ], spacing=16),
                expand=True
            )

            return ft.Container(
                content=ft.Column([
                header_section,
                info_card,
                ft.Row([
                    self.analysis_status_text,
                    self.analysis_button
                ], alignment=ft.MainAxisAlignment.END),
                self.analysis_list,
                ]),
                expand=True,
                adaptive=True
            )

        def create_expense_review_tab():
            print("create_expense_review_tab")
            return ft.Column([
                ft.Text("Expense Review", size=24, weight=ft.FontWeight.BOLD),
                ])

        # Initialize with the first tab
        self.tab_content.controls.append(create_expenses_list_tab())

        return ft.Container(
            content=ft.Column([
                expense_tab_selector,
                ft.Container(
                    content=self.tab_content,
                    expand=True,
                    padding=ft.padding.all(0)
                )
            ]), expand=True)



    def update_analysis_button_state(self):
        """Update button state based on cooldown period"""
        if not self.analysis:
            self.analysis_button.disabled = False
            self.analysis_button.text = "Generate AI Analysis"
            self.analysis_status_text.value = ""
            return
        latest_analysis = max(self.analysis, key=lambda x: x.get('date', ''))
        latest_date_str = latest_analysis.get('date', '')

        if not latest_date_str:
            self.analysis_button.disabled = False
            self.analysis_button.text = "Generate AI Analysis"
            self.analysis_status_text.value = ""
            return

        try:
            latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
            days_since_last = (datetime.now() - latest_date).days

            if days_since_last < 14:
                days_remaining = 14 - days_since_last
                self.analysis_button.disabled = True
                self.analysis_button.text = "AI Analysis"
                self.analysis_button.bgcolor = ft.colors.GREY_400
                self.analysis_status_text.value = f"Next analysis available in {days_remaining} days"
            else:
                self.analysis_button.disabled = False
                self.analysis_button.text = "Generate AI Analysis"
                self.analysis_button.bgcolor = ft.colors.LIME_300
                self.analysis_status_text.value = ""
        except ValueError:
            print(f"Invalid date format: {latest_date_str}")
            self.analysis_button.disabled = False
            self.analysis_button.text = "Generate AI Analysis"
            self.analysis_status_text.value = ""

        if hasattr(self, 'page'):
            self.page.update()

    def create_wish_list_tab(self):
        return ft.Container(
            content=ft.Column(
                [ft.Column([
                    ft.Text("Add here products that you wish to buy but still thinking about it."),
                    ft.Text(
                        "Adding products to a wish list instead of buying them can help you spend your money more wisely.")
                ]),
                    ft.Text("Wish list", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    self.wish_list_filter,
                    ft.Column(
                        [self.wish_list],
                        scroll=ft.ScrollMode.AUTO
                    ),
                    ft.Row([
                        ft.FloatingActionButton(icon=ft.icons.ADD,
                                                bgcolor=ft.colors.LIME_300,
                                                data=0,
                                                on_click=self.show_add_wish_dialog,
                                                ),
                    ], alignment=ft.MainAxisAlignment.END)

                ]),
            padding=20,
            expand=True,
        )

    def get_category_colors(self):
        category_colors = {
            # Essential Living - Warm, earthy tones (importance)
            "Groceries": ft.colors.GREEN_400,
            "Housing": ft.colors.BLUE_400,
            "Utilities": ft.colors.ORANGE_600,
            "Transportation": ft.colors.TEAL_600,
            "Insurance": ft.colors.BLUE_GREY_600,
            "Healthcare": ft.colors.LIGHT_GREEN_800,
            # Personal Care - Soft, nurturing colors
            "Personal Care": ft.colors.PINK_300,
            "Clothing": ft.colors.PURPLE_300,
            "Fitness": ft.colors.DEEP_PURPLE_400,
            # Food & Dining - Warm, appetizing colors
            "Dining Out": ft.colors.ORANGE_300,
            "Coffee": ft.colors.BROWN_300,
            "Snacks": ft.colors.YELLOW_600,

            # Entertainment & Leisure - Vibrant, fun colors
            "Entertainment": ft.colors.DEEP_ORANGE_ACCENT_400,
            "Hobbies": ft.colors.INDIGO_300,
            "Books": ft.colors.BLUE_GREY_400,
            "Gaming": ft.colors.DEEP_PURPLE_400,
            # Technology - Cool, modern colors
            "Digital Services": ft.colors.BLUE_500,
            "Electronics": ft.colors.CYAN_500,
            "Software": ft.colors.LIGHT_BLUE_500,

            # Family & Social - Warm, caring colors
            "Childcare": ft.colors.YELLOW_400,
            "Education": ft.colors.LIGHT_GREEN_500,
            "Gifts": ft.colors.PINK_400,
            "Pet Care": ft.colors.BROWN_200,

            # Special Occasions - Bright, celebratory colors
            "Travel": ft.colors.TEAL_400,
            "Events": ft.colors.DEEP_ORANGE_300,
            "Charity": ft.colors.LIGHT_GREEN_400,

            # Financial - Professional, trustworthy colors
            "Savings": ft.colors.GREEN_500,
            "Investments": ft.colors.GREEN_700,
            "Debt Payment": ft.colors.RED_500,

            # Miscellaneous - Neutral colors
            "Emergency": ft.colors.RED_600,
            "Other": ft.colors.GREY_500,
        }
        return category_colors

    def create_charts_tab(self):
        # Initialize filter indices
        pie_chart_filter_index = 0
        bar_chart_filter_index = 0
        line_chart_filter_index = 0

        def get_selected_expenses(filter_index):
            expense_categories = {}
            if filter_index == 0:
                reference_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            elif filter_index == 1:
                reference_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
            elif filter_index == 2:
                reference_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
            elif filter_index == 3:
                reference_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
            elif filter_index == 4:
                reference_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                reference_date = (datetime.now() - timedelta(days=1000)).strftime("%Y-%m-%d %H:%M:%S")

            for expense in self.expenses:
                if expense['date'] > reference_date:
                    if expense['category'] in expense_categories:
                        expense_categories[expense['category']] += expense['amount']
                    else:
                        expense_categories[expense['category']] = expense['amount']
            return expense_categories

        def get_expenses_by_date_and_category(filter_index):
            """Get expenses grouped by date and category for line chart"""
            if filter_index == 0:
                reference_date = datetime.now() - timedelta(days=30)
            elif filter_index == 1:
                reference_date = datetime.now() - timedelta(days=60)
            elif filter_index == 2:
                reference_date = datetime.now() - timedelta(days=90)
            elif filter_index == 3:
                reference_date = datetime.now() - timedelta(days=180)
            elif filter_index == 4:
                reference_date = datetime.now() - timedelta(days=365)
            else:
                reference_date = datetime.now() - timedelta(days=1000)

            # Dictionary to store expenses by category and date
            expenses_by_category_date = {}
            all_dates = set()

            for expense in self.expenses:
                expense_date = datetime.strptime(expense['date'], "%Y-%m-%d %H:%M:%S")
                if expense_date > reference_date:
                    date_key = expense_date.strftime("%Y-%m-%d")
                    category = expense['category']
                    amount = expense['amount']

                    all_dates.add(date_key)

                    if category not in expenses_by_category_date:
                        expenses_by_category_date[category] = {}

                    if date_key in expenses_by_category_date[category]:
                        expenses_by_category_date[category][date_key] += amount
                    else:
                        expenses_by_category_date[category][date_key] = amount

            # Sort dates
            sorted_dates = sorted(list(all_dates))

            # Fill missing dates with 0 for each category
            for category in expenses_by_category_date:
                for date in sorted_dates:
                    if date not in expenses_by_category_date[category]:
                        expenses_by_category_date[category][date] = 0

            return expenses_by_category_date, sorted_dates


        def create_pie_sections():
            expense_categories = get_selected_expenses(pie_chart_filter_index)
            category_colors = self.get_category_colors()

            total_amount = sum(expense_categories.values())

            pie_sections = [ft.PieChartSection(
                value=amount,
                title=f"{category}\n{(amount/total_amount)*100:.1f}%",
                radius=100,
                color=category_colors.get(category, ft.colors.GREY_500)
            )
                for category, amount in expense_categories.items()
            ]
            return pie_sections

        def create_bars():
            expense_categories = get_selected_expenses(bar_chart_filter_index)
            category_colors = self.get_category_colors()

            if not expense_categories:
                return []

            bars = []
            for i, (category, amount) in enumerate(expense_categories.items()):
                bars.append(ft.BarChartGroup(
                    x=i,
                    bar_rods=[
                        ft.BarChartRod(
                            from_y=0,
                            to_y=amount,
                            width=40,
                            color=category_colors.get(category, ft.colors.GREY_500),
                            tooltip=f"{category}: ${amount:.2f}",
                            border_radius=0,
                        )
                    ],
                ))
            return bars

        def create_line_chart_data():
            expenses_by_category_date, sorted_dates = get_expenses_by_date_and_category(line_chart_filter_index)
            category_colors = self.get_category_colors()

            if not expenses_by_category_date or not sorted_dates:
                return []

            line_chart_series = []

            for category, expenses_by_date in expenses_by_category_date.items():
                data_points = []
                for i, date in enumerate(sorted_dates):
                    amount = expenses_by_date.get(date, 0)
                    data_points.append(ft.LineChartDataPoint(x=i, y=amount))

                line_chart_series.append(ft.LineChartData(
                    data_points=data_points,
                    stroke_width=3,
                    color=category_colors.get(category, ft.colors.GREY_500),
                    curved=True,
                    stroke_cap_round=True,
                    prevent_curve_over_shooting=True,
                ))

            return line_chart_series

        # Create initial charts
        pie_chart = ft.PieChart(
            sections=create_pie_sections(),
            sections_space=0.1,
            center_space_radius=20,
        )

        bars = create_bars()
        max_y_bar = max([max([rod.to_y for rod in group.bar_rods]) for group in bars], default=100) * 1.1

        bar_chart = ft.BarChart(
            bar_groups=bars,
            left_axis=ft.ChartAxis(
                labels_size=40,
                title=ft.Text("Amount"),
                title_size=40,
            ),
            bottom_axis=ft.ChartAxis(
                labels_size=40,
                title=ft.Text("Categories"),
                title_size=40,
            ),
            max_y=max_y_bar,
            interactive=True,
            width=700,
            height=500,
        )

        line_chart_data = create_line_chart_data()
        expenses_by_category_date, sorted_dates = get_expenses_by_date_and_category(line_chart_filter_index)

        # Calculate max_y from all categories
        max_y_line = 100  # default
        if expenses_by_category_date:
            all_amounts = []
            for category_data in expenses_by_category_date.values():
                all_amounts.extend(category_data.values())
            if all_amounts:
                max_y_line = max(all_amounts) * 1.1

        line_chart = ft.LineChart(
            data_series=line_chart_data,
            left_axis=ft.ChartAxis(
                labels_size=40,
                title=ft.Text("Amount"),
                title_size=40,
            ),
            bottom_axis=ft.ChartAxis(
                labels_size=40,
                title=ft.Text("Date"),
                title_size=40,
            ),
            max_y=max_y_line,
            interactive=True,
            width=700,
            height=500,
        )

        def update_pie_chart(e=None):
            nonlocal pie_chart_filter_index
            if e:
                pie_chart_filter_index = e.control.selected_index

            # Update pie chart sections
            pie_chart.sections = create_pie_sections()

            # Update the chart if it's on the page
            if hasattr(pie_chart, 'page') and pie_chart.page:
                pie_chart.update()

        def update_bar_chart(e=None):
            nonlocal bar_chart_filter_index
            if e:
                bar_chart_filter_index = e.control.selected_index

            # Update bar chart data
            bars = create_bars()
            bar_chart.bar_groups = bars

            # Update max_y based on new data
            if bars:
                max_y = max([max([rod.to_y for rod in group.bar_rods]) for group in bars]) * 1.1
                bar_chart.max_y = max_y

            # Update the chart if it's on the page
            if hasattr(bar_chart, 'page') and bar_chart.page:
                bar_chart.update()

        def update_line_chart(e=None):
            nonlocal line_chart_filter_index
            if e:
                line_chart_filter_index = e.control.selected_index

            # Update line chart data
            line_chart_data = create_line_chart_data()
            line_chart.data_series = line_chart_data

            # Update max_y based on new data
            expenses_by_category_date, sorted_dates = get_expenses_by_date_and_category(line_chart_filter_index)
            if expenses_by_category_date:
                all_amounts = []
                for category_data in expenses_by_category_date.values():
                    all_amounts.extend(category_data.values())
                if all_amounts:
                    max_y = max(all_amounts) * 1.1
                    line_chart.max_y = max_y

            # Update the chart if it's on the page
            if hasattr(line_chart, 'page') and line_chart.page:
                line_chart.update()

        # Create filter tabs
        pie_chart_filter = ft.Tabs(
            is_secondary=True,
            selected_index=pie_chart_filter_index,
            on_change=update_pie_chart,
            tabs=[
                ft.Tab(text="1M"),
                ft.Tab(text="2M"),
                ft.Tab(text="3M"),
                ft.Tab(text="6M"),
                ft.Tab(text="12M"),
                ft.Tab(text="All"),
            ]
        )

        bar_chart_filter = ft.Tabs(
            is_secondary=True,
            selected_index=bar_chart_filter_index,
            on_change=update_bar_chart,
            tabs=[
                ft.Tab(text="1M"),
                ft.Tab(text="2M"),
                ft.Tab(text="3M"),
                ft.Tab(text="6M"),
                ft.Tab(text="12M"),
                ft.Tab(text="All"),
            ]
        )

        line_chart_filter = ft.Tabs(
            is_secondary=True,
            selected_index=line_chart_filter_index,
            on_change=update_line_chart,
            tabs=[
                ft.Tab(text="1M"),
                ft.Tab(text="2M"),
                ft.Tab(text="3M"),
                ft.Tab(text="6M"),
                ft.Tab(text="12M"),
                ft.Tab(text="All"),
            ]
        )

        # Create views for each chart type
        pie_view = ft.Column([pie_chart_filter, pie_chart])
        bar_view = ft.Column([bar_chart_filter, bar_chart])
        line_view = ft.Column([line_chart_filter, line_chart])

        # Create a container to hold the current view
        chart_container = ft.Container(content=pie_view)

        def update_chart_view(e=None):
            print(f"selected index is: {charts_tab.selected_index}")
            if charts_tab.selected_index == 0:
                chart_container.content = pie_view
            elif charts_tab.selected_index == 1:
                chart_container.content = bar_view
            else:
                chart_container.content = line_view

            # Update the container if it's on the page
            if hasattr(chart_container, 'page') and chart_container.page:
                chart_container.update()

        charts_tab = ft.Tabs(
            is_secondary=True,
            selected_index=0,
            on_change=update_chart_view,
            tabs=[
                ft.Tab(text="Pie Chart"),
                ft.Tab(text="Bar Chart"),
                ft.Tab(text="Line Chart"),
            ]
        )

        return ft.Container(
            ft.Column([
                charts_tab,
                chart_container
            ])
        )

    def get_highest_expenses(self):
        if not self.highest_expenses:
            return ft.Column([ft.Text("No expenses recorded yet")])

        expenses_to_show = self.highest_expenses[:3]

        expense_controls = [
            ft.Text("Highest Expenses:", weight=ft.FontWeight.BOLD)
        ]

        for i, expense in enumerate(expenses_to_show, 1):
            expense_controls.append(
                ft.Text(f"{i}. {expense[0]}: ${expense[1]:.2f}")
            )

        return ft.Column(expense_controls, spacing=5)

    def on_recurring_date_change(self, e):
        if e.control.value:
            selected_date = e.control.value
            self.recurring_day = selected_date
            self.recurring_date_button.text = f"Recurring Date: {selected_date.strftime('%Y-%m-%d')}"
            self.page.update()
            try:
                self.show_snackbar("Recurring day saved!")

            except ValueError:
                self.show_snackbar("Please enter valid numbers!")

    def open_date_picker(self, e):
        self.start_date_picker.pick_date()

    def open_recurring_date_picker(self, e):
        self.recurring_date_picker.pick_date()

    def update_displays(self):
        """Update all display components"""
        self.update_budget_summary()
        self.update_expenses_list()
        self.update_analysis_list()

    def get_recurring_period(self, period):
        months = 0
        if period == 'Monthly':
            months = 1
        elif period == "Yearly":
            months = 12
        else:
            months = int(period.split()[0])
        return months


    def automaticaly_update_expense(self):
        print("Checking for recurring expenses")
        print(f'Recurring expenses list is : {self.recurring_expenses}')
        for expense in self.recurring_expenses:
            try:
                print(f"checking reccuring expenses date")
                if type(expense['recurring day']) is not str:
                    expense['recurring day'] = expense['recurring day'].strftime('%Y-%m-%d %H:%M:%S')
                if expense['recurring day'] <= datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
                    print("Automatically updating expense")
                    months = self.get_recurring_period(expense['is recurring'])
                    new_date = expense['recurring day'] + relativedelta(months=months)
                    print(f"Old date is {expense['recurring day']} and New date is {new_date}")
                    expense_data = {
                        'user id': self.user_id,
                        'amount': expense['amount'],
                        'category': expense['category'],
                        'description': expense['description'],
                        'impulse index': expense.get('impulse index', None),
                        'date': expense['date'],
                        'timestamp': expense['timestamp'],
                        'shared': expense['shared'],
                        'owe status': expense['owe status'],
                        'percentage': expense['percentage'],
                        'is recurring': expense['is recurring'],
                        'recurring day': new_date
                    }

                    if not self.db:
                        db = firestore.client()
                    # Save to Firebase if available
                    if self.db:
                        doc_ref = self.db.collection('users').document(self.user_id).collection('expenses').add(
                            expense_data)
                        expense_data['id'] = expense['id']
                        print(f"✅ Expense saved successfully with ID: {expense_data['id']}")
                        print(f"📊 Expense data: {expense_data}")
                        doc_ref = self.db.collection('expenses').document(expense['id'])
                        doc_ref.update({'recurring day': new_date.strftime('%Y-%m-%d %H:%M:%S')})
                    else:
                        # Generate a temporary ID for local storage
                        expense_data['id'] = f"local_{len(self.expenses)}"
                        print("⚠️ Firebase not available, expense saved locally only")

                    self.expenses.append(expense_data)
                    self.update_budget_summary()
                    self.page.update()
                    self.show_snackbar("Expense added successfully!")
            except Exception as e:
                print(e)

    def add_expense_from_wish_list(self, wish_id):
        "Moves entry from wish list to expense list"
        print(f"wish list is: {self.wishes}")
        try:
            wish_to_expense = next((wish for wish in self.wishes if wish_id == wish.get('id')))
            print(f"Found wish: {wish_to_expense}")
            expense_data = {
                'user id': self.user_id,
                'amount': wish_to_expense['amount'],
                'category': wish_to_expense['category'],
                'description': wish_to_expense['description'],
                'date': wish_to_expense['date'],
                'timestamp': wish_to_expense['timestamp'],
                'shared': "No",
                'owe status': False,
                'percentage': "0",
                'is recurring': "No",
                'recurring day': None
            }

            # Remove from local data
            self.wishes = [wish for wish in self.wishes if wish.get('id') != wish_id]
            print(f'Updated wish list is {self.wishes}')

            if not self.db:
                db = firestore.client()
            # Save to Firebase if available
            if self.db:
                print("saving to db")
                doc_ref = self.db.collection('users').document(self.user_id).collection('expenses').add(expense_data)
                expense_data['id'] = wish_to_expense['id']
                print(f"✅ Expense saved successfully with ID: {expense_data['id']}")
                print(f"📊 Expense data: {expense_data}")
                doc_ref = self.db.collection('expenses').document(wish_to_expense['id'])

                self.db.collection('wish_list').document(wish_id).delete()

                # Remove from local data
                self.wishes = [wish for wish in self.wishes if wish.get('id') != wish_id]
            else:
                # Generate a temporary ID for local storage
                expense_data['id'] = f"local_{len(self.expenses)}"
                print("⚠️ Firebase not available, expense saved locally only")

            self.expenses.append(expense_data)
            self.update_wish_list()
            self.update_expenses_list()
            self.update_budget_summary()
            self.page.update()
            self.show_snackbar("Expense added successfully!")

        except Exception as e:
            print(e)
    def create_expense_item(self, expense):
        print("entering function create_expense_item")
        category = expense.get('category', '')
        category_colors = self.get_category_colors()
        category_color = category_colors.get(category, ft.colors.BLUE_300)

        category_badge = ft.Container(
            content=ft.Row([
                ft.Icon(self.get_category_icon(category)),
                ft.Text(category, size=12, weight=ft.FontWeight.W_500)
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                bgcolor=category_color,
                border_radius=20,
            )
        recurring_badge = None
        if expense["is recurring"] != 'No':
            recurring_badge = ft.Container(
                content=ft.Text(
                    expense["is recurring"],
                    size=11,
                    weight=ft.FontWeight.W_500,
                    color=ft.colors.WHITE
                ),
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                bgcolor=ft.colors.ORANGE_600,
                border_radius=12,
            )
        shared_badge = None
        if expense['shared'] != "No":
            shared_sum = float(expense['amount']) * float(expense['percentage']) * 0.01
            shared_badge = ft.Container(
                content=ft.Row([
                    ft.Text(
                        f"You owe {str(shared_sum)} {self.currency} to" if expense['owe status']==True else
                        f"You are owed {str(shared_sum)} {self.currency} by",
                        size=11,
                        weight=ft.FontWeight.W_500,
                        color=ft.colors.RED_400 if expense['owe status']==True else ft.colors.GREEN_400
                    ),
                ft.Text(
                    expense["shared"],
                    size=11,
                    weight=ft.FontWeight.W_500,
                    color=ft.colors.RED_400 if expense['owe status']==True else ft.colors.GREEN_400
                ),
                ]),
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                bgcolor=ft.colors.PINK_100 if expense['owe status']==True else ft.colors.GREEN_100,
                border_radius=12,
            )
        expense_item = ft.Card(
            content=ft.Container(
            content=ft.Column([
                # Header row
                ft.Row([
                    ft.Column([
                        ft.Row([
                        ft.Text(
                            expense["description"],
                            size=16,
                            weight=ft.FontWeight.W_600,
                            color=ft.colors.GREY_900
                        ),
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_color=ft.colors.BLUE,
                                    on_click=lambda e, exp_id=expense.get('id'): self.show_edit_expense_dialog(exp_id)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_color=ft.colors.RED,
                                    on_click=lambda e, exp_id=expense.get('id'): self.delete_expense(exp_id)
                                )
                            ], )
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        category_badge
                    ], spacing=4, expand=True),
                    ft.Text(
                        f"{expense['amount']:.2f} {self.currency}",
                        size=18,
                        weight=ft.FontWeight.W_700,
                        color=ft.colors.GREY_900
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                # Meta row
                ft.Row([
                    ft.Text(
                        expense["date"],
                        size=12,
                        color=ft.colors.GREY_600
                    ),
                    shared_badge if shared_badge else ft.Container(),
                    recurring_badge if recurring_badge else ft.Container()
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=12),
            padding=ft.padding.all(20),
            margin=ft.margin.only(bottom=16),
            bgcolor=ft.colors.WHITE,
            border_radius=16,
            border=ft.border.all(1, ft.colors.GREY_100),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                offset=ft.Offset(0, 2)
            ),
        ) )
        return expense_item

    def update_expenses_list(self, e=None):
        """Update the expenses list display"""
        print("Entered update expense list function")
        self.expenses_list.controls.clear()
        filtered_expenses = self.expenses


        if not self.expenses:
            self.expenses_list.controls.append(
                ft.Text("No expenses recorded yet.", color=ft.colors.GREY_600)
            )
        else:
            recurring_filter = self.occurence_filter.value
            selected_period = self.time_period_filter.value
            if self.category_filter.value and self.category_filter.value != 'All':
                filtered_expenses = [exp for exp in self.expenses if exp['category'] == self.category_filter.value]

            if recurring_filter == "Periodic":
                filtered_expenses = [exp for exp in filtered_expenses if exp['is recurring'] != "No"]

            elif recurring_filter == "Not Periodic":
                filtered_expenses = [exp for exp in filtered_expenses if exp['is recurring'] == "No"]

            if selected_period == "1M":
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")]
            elif selected_period == "2M":
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")]

            elif selected_period == "3M":
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")]

            elif selected_period == "6M" == 3:
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")]

            elif selected_period == "12M":
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")]

            for expense in (filtered_expenses):
                '''
                expense_card = ft.Card(
                    content=ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(f"{expense.get('amount', 0):.2f}",
                                        size=18, weight=ft.FontWeight.BOLD),
                                ft.Row([
                                    ft.Icon(self.get_category_icon(expense['category'])),
                                    ft.Text(expense.get('category', ''), color=ft.colors.BLUE),
                                ]),
                                ft.Text(expense.get('description', ''), color=ft.colors.GREY_600),
                                ft.Text(expense.get('date', ''), size=12, color=ft.colors.GREY_500),
                            ], expand=True, spacing=1),
                            ft.Column([
                                ft.Row([
                                    ft.Text("Shared with: "),
                                    ft.Text(expense.get('shared', ''), size=12, color=ft.colors.GREY_500),
                                ]),
                            ], expand=True, spacing=1),
                            ft.Column([
                                ft.Row([
                                    ft.Text("Occurrence: "),
                                    ft.Text(expense.get('is recurring', ''), size=12, color=ft.colors.GREY_500),
                                ]),
                                ft.Row([
                                    ft.Text("Next Occurrence day: "),
                                    ft.Text(expense.get('recurring day', ''), size=12, color=ft.colors.GREY_500)
                                ]),

                            ], expand=True, spacing=1),
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_color=ft.colors.BLUE,
                                    on_click=lambda e, exp_id=expense.get('id'): self.show_edit_expense_dialog(exp_id)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_color=ft.colors.RED,
                                    on_click=lambda e, exp_id=expense.get('id'): self.delete_expense(exp_id)
                                )
                            ])
                        ]),
                        padding=15
                    )
                )
                '''
                expense_card = self.create_expense_item(expense)
                self.expenses_list.controls.append(expense_card)

        self.page.update()

    def update_wish_list(self, e=None):
        """Update the wish list display"""
        print("Entered update wish list function")
        self.wish_list.controls.clear()
        filtered_wishes = []

        if not self.wishes:
            self.expenses_list.controls.append(
                ft.Text("No expenses recorded yet.", color=ft.colors.GREY_600)
            )
        else:

            if self.wish_list_filter.selected_index == 0:
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")]
            elif self.wish_list_filter.selected_index == 1:
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")]

            elif self.wish_list_filter.selected_index == 2:
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")]

            elif self.wish_list_filter.selected_index == 3:
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")]

            elif self.wish_list_filter.selected_index == 4:
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")]

            for wish in reversed(filtered_wishes):
                wish_card = ft.Card(
                    content=ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Row([
                                    ft.Text(f"{wish.get('amount', 0):.2f}",
                                            size=18, weight=ft.FontWeight.BOLD),
                                    ft.ElevatedButton(text="Acquired this",
                                                      style=ft.ButtonStyle(
                                                          shape=ft.RoundedRectangleBorder(radius=10)),
                                                      on_click=lambda e, wish_id=wish.get(
                                                          'id'): self.add_expense_from_wish_list(wish_id))
                                ]),

                                ft.Row([
                                    ft.Icon(self.get_category_icon(wish['category'])),
                                    ft.Text(wish.get('category', ''), color=ft.colors.BLUE),
                                ]),
                                ft.Text(wish.get('description', ''), color=ft.colors.GREY_600),
                                ft.Text(wish.get('date', ''), size=12, color=ft.colors.GREY_500),
                            ], expand=True, spacing=1),
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_color=ft.colors.BLUE,
                                    on_click=lambda e, wish_id=wish.get('id'): self.show_edit_wish_dialog(wish_id)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_color=ft.colors.RED,
                                    on_click=lambda e, wish_id=wish.get('id'): self.delete_wish_list_item(wish_id)
                                )
                            ])
                        ]),
                        padding=15
                    )
                )
                self.wish_list.controls.append(wish_card)

        self.page.update()

    def update_analysis_list(self, e=None):
        print('Updating AI analysis list')
        self.analysis_list.controls.clear()

        if not self.analysis:
            print("No entries in analysis list")
            # Empty state card
            empty_state = ft.Container(
                content=ft.Column([
                    ft.Icon(
                        ft.icons.INSIGHTS,
                        size=64,
                        color=ft.colors.GREY_300
                    ),
                    ft.Text(
                        "No Analysis Yet",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.colors.GREY_500,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Generate your first AI analysis to get personalized insights about your spending habits.",
                        size=14,
                        color=ft.colors.GREY_400,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(40),
                bgcolor=ft.colors.GREY_50,
                border_radius=16,
                border=ft.border.all(1, ft.colors.GREY_200),
                alignment=ft.alignment.center
            )
            self.analysis_list.controls.append(empty_state)
        else:
            print(f"AI analysis list is {self.analysis}")
            for i, entry in enumerate(self.analysis):
                print(f"Entry is {entry}")

                # Create gradient colors for different analysis cards
                card_colors = [
                    (ft.colors.PURPLE_50, ft.colors.PURPLE_400),
                    (ft.colors.BLUE_50, ft.colors.BLUE_400),
                    (ft.colors.GREEN_50, ft.colors.GREEN_400),
                    (ft.colors.ORANGE_50, ft.colors.ORANGE_400),
                    (ft.colors.PINK_50, ft.colors.PINK_400)
                ]
                bg_color, accent_color = (ft.colors.GREEN_50, ft.colors.GREEN_400)

                # Parse analysis content for better formatting
                analysis_text = entry.get('analysis', '')
                date_text = entry.get('date', '')

                analysis_card = ft.Container(
                    content=ft.Column([
                        # Card header
                        ft.Row([
                            ft.Icon(
                                ft.icons.AUTO_AWESOME,
                                color=accent_color,
                                size=20
                            ),
                            ft.Text(
                                f"Analysis Report",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.GREY_800,
                                expand=True
                            ),
                            ft.Text(
                                date_text,
                                size=12,
                                color=ft.colors.GREY_500
                            ) if date_text else ft.Container()
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                        ft.Divider(color=ft.colors.GREY_200, height=1),

                        # Analysis content
                        ft.Container(
                            content=ft.Text(
                                analysis_text,
                                size=14,
                                color=ft.colors.GREY_700,
                                selectable=True,
                                font_family='Arial'
                            ),
                            padding=ft.padding.only(top=8)
                        )
                    ], spacing=12),
                    padding=ft.padding.all(20),
                    bgcolor=bg_color,
                    border_radius=16,
                    border=ft.border.all(1, ft.colors.GREY_200),
                    margin=ft.margin.only(bottom=12)
                )
                self.analysis_list.controls.append(analysis_card)

        self.update_analysis_button_state()
        self.page.update()

    def get_ai_analysis(self, e=None):
        print("generating AI analysis")
        benchmark_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        print(benchmark_date)
        expenses = [expense for expense in self.expenses if expense['date'] > benchmark_date]
        # Check if there are expenses to analyze
        if not expenses:
            print("No expenses found for analysis")
            return
        generated_analysis = self.ai_analyst.analyze_expenses_with_ai(expenses)

        def save_analysis():
            print("Saving AI Analysis")
            analysis_data = {
                'analysis': generated_analysis,
                # Make sure this matches what you're looking for in update_analysis_list
                'date': datetime.now().strftime("%Y-%m-%d"),
                'timestamp': firestore.SERVER_TIMESTAMP
            }

            try:
                # Correct Firestore add method
                doc_ref = self.db.collection('users').document(self.user_id).collection('analysis_list').add(
                    analysis_data)
                analysis_data['id'] = doc_ref[1].id

                # Add to local list
                self.analysis.append(analysis_data)

                print("✅ Analysis saved successfully.")
                print(f"📊 Analysis data: {analysis_data}")
                return True
            except Exception as e:
                print(f"❌ Error saving analysis entries: {e}")
                return False

        # Save and update display
        if save_analysis():
            self.update_analysis_list()
            self.update_displays()

    def show_add_budget_dialog(self, e):
        """Show dialog to configure budget"""
        self.budget_input = ft.TextField(
            label="Budget Amount",
            value=str(self.budget_amount),
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.currency_input = ft.TextField(
            label="Currency",
            value='$',
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.start_date_picker = ft.DatePicker(
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31),
            on_change=self.on_start_date_change
        )

        self.end_date_picker = ft.DatePicker(
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31),
            on_change=self.on_end_date_change
        )

        self.page.overlay.extend([self.start_date_picker, self.end_date_picker])

        self.start_date_button = ft.ElevatedButton(
            text=f"Start: {self.start_date.strftime('%Y-%m-%d')}",
            on_click=lambda _: self.start_date_picker.pick_date()
        )

        self.end_date_button = ft.ElevatedButton(
            text=f"End: {self.end_date.strftime('%Y-%m-%d')}",
            on_click=lambda _: self.end_date_picker.pick_date()
        )

        self.budget_form_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Configure Budget"),
            content=ft.Column([
                self.budget_input,
                self.currency_input,
                self.start_date_button,
                self.end_date_button,
            ], height=200),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_budget_dialog()),
                ft.ElevatedButton("Save", on_click=self.save_budget)
            ]
        )

        self.page.dialog = self.budget_form_dialog
        self.budget_form_dialog.open = True
        self.page.update()

    def show_expense_category(self):
        category_groups = {
            "Essential Living": ["Groceries", "Housing", "Utilities", "Transportation", "Insurance", "Healthcare"],
            "Personal Care": ["Personal Care", "Clothing", "Fitness"],
            "Food & Dining": ["Dining Out", "Coffee", "Snacks"],
            "Entertainment & Leisure": ["Entertainment", "Hobbies", "Books", "Gaming"],
            "Technology": ["Digital Services", "Electronics", "Software"],
            "Family & Social": ["Childcare", "Education", "Gifts", "Pet Care"],
            "Special Occasions": ["Travel", "Events", "Charity"],
            "Financial": ["Savings", "Investments", "Debt Payment"],
            "Miscellaneous": ["Emergency", "Other"]
        }

        dropdown_options = []

        for group_name, categories in category_groups.items():
            # Add group header
            dropdown_options.append(ft.dropdown.Option(
                text=f"--- {group_name} ---",
                disabled=True
            ))

            # Add categories in this group
            for category in categories:
                dropdown_options.append(ft.dropdown.Option(
                    text=category,
                    key=category
                ))
        return dropdown_options

    def get_friend_data(self):
        friends_list = FriendsManager(self.user_id).get_friends_list()
        friend_data = {}
        for friend in friends_list:
            friend_data[friend['email']] = friend['userId']
        return friend_data

    def show_add_expense_dialog(self, e):
        """Show dialog to add new expense"""

        amount_input = ft.TextField(
            label="Amount",
            keyboard_type=ft.KeyboardType.NUMBER,
            adaptive=True,
            border_radius=12,
            prefix_icon=ft.icons.MONEY,
            bgcolor=ft.colors.BLUE_50,
            border_color=ft.colors.BLUE_200,
            focused_border_color=ft.colors.BLUE_400,
            suffix_text=self.currency,
        )

        amount_field = ft.Container(
            content=amount_input,
            margin=ft.margin.only(bottom=15)
        )

        category_input = ft.Dropdown(
                label="Category",
                options=self.show_expense_category(),
                border_radius=12,
                bgcolor=ft.colors.ORANGE_50,
                border_color=ft.colors.ORANGE_200,
                focused_border_color=ft.colors.ORANGE_400,
            )
        category_field = ft.Container(
            content=category_input,
            margin=ft.margin.only(bottom=15)
        )

        description_input = ft.TextField(
                label="Description",
                multiline=True,
                min_lines=2,
                max_lines=3,
                border_radius=12,
                bgcolor=ft.colors.GREEN_50,
                border_color=ft.colors.GREEN_200,
                focused_border_color=ft.colors.GREEN_400,
            )

        description_field = ft.Container(
            content=description_input,
            margin=ft.margin.only(bottom=15)
        )

        recurring_period_input = ft.Dropdown(
                    options=[ft.dropdown.Option("No"),
                             ft.dropdown.Option("Monthly"),
                             ft.dropdown.Option("Yearly"),
                             ft.dropdown.Option("2 Months"),
                             ft.dropdown.Option("3 Months"),
                             ft.dropdown.Option("4 Months"),
                             ft.dropdown.Option("5 Months"),
                             ft.dropdown.Option("6 Months"),
                             ft.dropdown.Option("7 Months"),
                             ft.dropdown.Option("8 Months"),
                             ft.dropdown.Option("9 Months"),
                             ft.dropdown.Option("10 Months"),
                             ft.dropdown.Option("11 Months")],
                    value="No",
                    border_radius=12,
                    bgcolor=ft.colors.PURPLE_50,
                    border_color=ft.colors.PURPLE_200,
                    focused_border_color=ft.colors.PURPLE_400,
                )

        recurring_period = ft.Container(
            content=ft.Column([
                ft.Text("Recurring Period", weight=ft.FontWeight.W_500, size=14),
                recurring_period_input
            ], spacing=8),
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
        )
        print(f"getting friends list with id_token")
        friends = self.get_friend_data()
        share_with_options = [ft.dropdown.Option("No")] + [ft.dropdown.Option(friend) for friend in friends.keys()]

        share_with_input = ft.Dropdown(
                    options=share_with_options,
                    value='No',
                    border_radius=12,
                    bgcolor=ft.colors.CYAN_50,
                    border_color=ft.colors.CYAN_200,
                    focused_border_color=ft.colors.CYAN_400,
                )

        share_with = ft.Container(
            content=ft.Column([
                ft.Text("Share With", weight=ft.FontWeight.W_500, size=14),
                share_with_input
            ], spacing=8),
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
        )

        percentage = ft.RangeSlider(
            min=0,
            max=100,
            start_value=0,
            end_value=50,
            divisions=10,
            label="{value}%",
            active_color=ft.colors.BLUE_400,
            inactive_color=ft.colors.BLUE_100,
            #thumb_color=ft.colors.BLUE_600,
        )

        percentage_display = ft.Container(
            content=ft.Column([
                ft.Text("Configure % of owed expense", weight=ft.FontWeight.W_500, size=14),
                percentage
            ], spacing=10),
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
        )

        review_item_input = ft.Checkbox(
                label="Review this expense later",
                value=False,
                check_color=ft.colors.WHITE,
                active_color=ft.colors.GREEN_400,
            )
        review_item = ft.Container(
            content=review_item_input,
            bgcolor=ft.colors.GREEN_50,
            border_radius=8,
            padding=10,
            margin=ft.margin.only(bottom=10)
        )

        owner_input = ft.Checkbox(
                label="I owe the expense",
                value=False,
                check_color=ft.colors.WHITE,
                active_color=ft.colors.ORANGE_400,
            )

        owner = ft.Container(
            content=owner_input,
            bgcolor=ft.colors.ORANGE_50,
            border_radius=8,
            padding=10,
            margin=ft.margin.only(bottom=15)
        )

        self.recurring_day = datetime.now().strftime('%Y-%m-%d')
        self.recurring_date_picker = ft.DatePicker(
            on_change=self.on_recurring_date_change,
            first_date=datetime(2025, 1, 1),
            last_date=datetime(2030, 12, 31),
            current_date=datetime.now()
        )

        self.recurring_date_button = ft.Container(
            content=ft.ElevatedButton(
                text=f"New Occurrence: {self.recurring_day}",
                icon=ft.icons.CALENDAR_MONTH,
                on_click=self.open_recurring_date_picker,
                bgcolor=ft.colors.INDIGO_400,
                color=ft.colors.WHITE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.padding.all(15)
                )
            ),
            margin=ft.margin.only(bottom=20)
        )

        def save_expense(e):
            try:
                amount = float(amount_input.value or 0)
                category = category_input.value or ""
                description = description_input.value or ""
                shared = share_with_input.value
                owe_status = owner_input.value
                is_recurring = recurring_period_input.value
                if is_recurring not in ['No', 'All']:
                    recurring_day = self.recurring_day
                else:
                    recurring_day = None

                friend_data = self.get_friend_data()

                if amount <= 0:
                    self.show_snackbar("Please enter a valid amount")
                    return

                expense_data = {
                    'user id': self.user_id,
                    'amount': amount,
                    'category': category,
                    'description': description,
                    'review': review_item_input.value,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': datetime.now(),
                    'shared': shared,
                    'owe status': owe_status,
                    'percentage': percentage.end_value,
                    'is recurring': is_recurring,
                    'recurring day': recurring_day
                }
                if not self.db:
                    self.db = firestore.client()
                # Save to Firebase if available
                if self.db:
                    # Add user ID to ensure data isolation
                    doc_ref = self.db.collection('users').document(self.user_id).collection('expenses').add(
                        expense_data)
                    expense_data['id'] = doc_ref[1].id
                    print(f"✅ Expense saved successfully for user : {expense_data['user id']}")
                    print(f"📊 Expense data: {expense_data}")

                    if shared != "No":
                        print(type(percentage.end_value))
                        friend_expense_data = {
                            'user id': self.user_id,
                            'amount': amount,
                            'category': category,
                            'description': description,
                            'review item': False,
                            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'timestamp': datetime.now(),
                            'shared': self.display_name,
                            'owe status': not owe_status,
                            'percentage': str(100 - float(percentage.end_value)),
                            'is recurring': is_recurring,
                            'recurring day': recurring_day
                        }
                        doc_ref = self.db.collection('users').document(friend_data[shared]).collection('expenses').add(
                            friend_expense_data)
                        expense_data['id'] = doc_ref[1].id

                else:
                    # Generate a temporary ID for local storage
                    expense_data['id'] = f"local_{len(self.expenses)}"
                    print("⚠️ Firebase not available, expense saved locally only")

                self.expenses.insert(0,expense_data)
                self.update_expenses_list()
                self.update_budget_summary()
                self.create_budget_progress_card()
                self.create_quick_insights_row()
                self.create_highest_expenses_card()
                self.create_recent_transactions_card()
                self.pie_chart.sections = self.create_pie_sections()
                self.expense_form_dialog.open = False
                self.page.update()
                self.show_snackbar("Expense added successfully!")

            except ValueError:
                self.show_snackbar("Please enter a valid amount")
            except Exception as ex:
                self.show_snackbar(f"Error saving expense: {ex}")
                print(f"❌ Detailed error: {ex}")

        self.expense_form_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.ADD_CIRCLE_OUTLINE, color=ft.colors.BLUE_600, size=24),
                ft.Text("Add New Expense", weight=ft.FontWeight.BOLD, size=20, color=ft.colors.BLUE_900)
            ], spacing=10),
                padding=ft.padding.only(bottom=10)
            ),
            content=ft.Container(
                content=ft.Column([
                    amount_field,
                    category_field,
                    description_field,
                    recurring_period,
                    share_with,
                    percentage_display,
                    review_item,
                    owner,
                    self.recurring_date_button
                ], spacing=0, scroll=ft.ScrollMode.AUTO),
                height=600,
                width=400,
                padding=20,
                bgcolor=ft.colors.GREY_50,
                border_radius=15
            ),
            actions=[
                ft.Container(
                    content=ft.Row([
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda e: self.close_expense_dialog(),
                            style=ft.ButtonStyle(
                                color=ft.colors.GREY_600,
                                bgcolor=ft.colors.GREY_100,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.padding.symmetric(horizontal=20, vertical=10)
                            )
                        ),
                        ft.ElevatedButton(
                            "Save Expense",
                            on_click=save_expense,
                            icon=ft.icons.SAVE,
                            bgcolor=ft.colors.GREEN_500,
                            color=ft.colors.WHITE,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.padding.symmetric(horizontal=20, vertical=12)
                            )
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.only(top=10)
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=ft.colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=20),
            adaptive=True
        )

        self.page.overlay.append(self.recurring_date_picker)

        self.page.dialog = self.expense_form_dialog
        self.expense_form_dialog.open = True
        self.page.update()

    def create_upload_picture_button(self):
        """Create the upload picture button with mobile camera/gallery options"""
        print("Creating upload picture button")
        self.file_picker = ft.FilePicker(
            on_result=self.on_file_picked
        )

        # Create components that need to be updated later
        self.upload_status_text = ft.Text("No image selected", size=12, color=ft.colors.GREY_600)
        self.image_preview = ft.Image(
            src="",
            width=200,
            height=150,
            fit=ft.ImageFit.CONTAIN,
            visible=False
        )

        upload_picture_button = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.ElevatedButton(
                        text="Camera",
                        icon=ft.icons.CAMERA_ALT,
                        on_click=self.take_photo,
                        expand=True
                    ),
                    ft.ElevatedButton(
                        text="Gallery",
                        icon=ft.icons.PHOTO_LIBRARY,
                        on_click=self.pick_from_gallery,
                        expand=True
                    )
                ], spacing=10),
                ft.Container(
                    content=self.upload_status_text
                ),
                ft.Container(
                    content=self.image_preview
                )
            ]),
            padding=10
        )

        return upload_picture_button, self.file_picker

    def take_photo(self, e):
        """Open camera to take a photo"""
        self.file_picker.pick_files(
            allow_multiple=True,
            allowed_extensions=['jpg', 'jpeg', 'png', 'webp'],
            dialog_title="Take Photo",
            # This will open camera on mobile devices
            file_type=ft.FilePickerFileType.IMAGE
        )

    def pick_from_gallery(self, e):
        """Pick image from gallery"""
        self.file_picker.pick_files(
            allow_multiple=True,
            allowed_extensions=['jpg', 'jpeg', 'png', 'webp'],
            dialog_title="Select from Gallery",
            file_type=ft.FilePickerFileType.IMAGE
        )

    def on_file_picked(self, e: ft.FilePickerResultEvent):
        """Handle file selection with image preview"""
        if e.files:
            file = e.files[0]
            self.uploaded_image = file

            # Update status text
            self.upload_status_text.value = f"Selected: {file.name}"

            # Show image preview if possible
            try:
                # For file picker results, we can show the file path
                if hasattr(file, 'path') and file.path:
                    self.image_preview.src = file.path
                    self.image_preview.visible = True
                else:
                    self.image_preview.visible = False
            except Exception as ex:
                print(f"Error showing preview: {ex}")
                self.image_preview.visible = False

            # Update the page to reflect changes
            if self.page:
                self.page.update()

    def encode_image_to_base64(self, file_path):
        """Convert image file to base64 string"""
        try:
            with open(file_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encoding image: {e}")
            return None

    def create_expense_data_from_image(self, impulse_index, shared, owe_status, percentage, is_recurring='No',
                                       recurring_day=None):
        """Create expense data from processed image"""
        if not self.uploaded_image:
            return None

        # Encode image to base64
        image_base64 = self.encode_image_to_base64(self.uploaded_image.path)
        if not image_base64:
            return None

        # Process image with Anthropic
        extracted_data = self.ai_analyst.process_image_with_anthropic(image_base64)

        # Create expense data structure
        expense_data = {
            'user id': self.user_id,
            'amount': float(extracted_data.get('amount', 0.0)),
            'category': extracted_data.get('category', 'miscellaneous'),
            'description': extracted_data.get('description', 'Expense from image'),
            'impulse index': impulse_index,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': datetime.now(),
            'shared': shared,
            'owe status': owe_status,
            'percentage': percentage,
            'is recurring': is_recurring,
            'recurring day': recurring_day
        }

        self.processed_expense_data = expense_data
        return expense_data

    def add_expense_from_picture_dialog(self, e):
        print("Clicked button to add expense from picture")
        """Show dialog to add new expense"""
        upload_picture_button, file_picker = self.create_upload_picture_button()
        # Add file picker to page overlay
        self.page.overlay.append(file_picker)
        #print(f"getting friends list with id_token")
        friends = self.get_friend_data()
        share_with_options = [ft.dropdown.Option(friend) for friend in friends.keys()]

        share_with = ft.Dropdown(
            label="Shared",
            options=share_with_options,
            value='No'
        )
        percentage = ft.RangeSlider(
                min=0,
                max=100,
                start_value=0,
                end_value=50,
                divisions=10,  # Creates tick marks
                label="{value}%",
            # These properties help with visibility
            )
        percentage_display = ft.Column([
            ft.Text("Configure % of owed expense"),
            percentage
        ])

        impulse_index = ft.RangeSlider(
            min=0,
            max=100,
            start_value=0,
            end_value=0,
            divisions=10,  # Creates tick marks
            label="{value}%",
            # These properties help with visibility
        )
        impulse_index_display = ft.Column([
            ft.Text("Configure Impuls Index: 0 - Low, 100 - High"),
            impulse_index
        ])

        owner = ft.Checkbox(label="I owe the expense", value=False)


        def save_expense_from_picture(e):
            print("Entering save_expense_from_picture")
            try:
                expense_data = self.create_expense_data_from_image(impulse_index.end_value, share_with.value,
                                                                   owner.value, percentage.end_value)
                print(f"Data from ai : {expense_data}")

                friend_data = self.get_friend_data()

                if not self.db:
                    self.db = firestore.client()
                # Save to Firebase if available
                if self.db:
                    # Add user ID to ensure data isolation
                    doc_ref = self.db.collection('users').document(self.user_id).collection('expenses').add(
                        expense_data)
                    expense_data['id'] = doc_ref[1].id
                    print(f"✅ Expense saved successfully for user : {expense_data['user id']}")
                    print(f"📊 Expense data: {expense_data}")

                    if share_with.value != "No":
                        doc_ref = self.db.collection('users').document(friend_data[share_with.value]).\
                            collection('expenses').add(
                            expense_data)
                        expense_data['id'] = doc_ref[1].id

                else:
                    # Generate a temporary ID for local storage
                    expense_data['id'] = f"local_{len(self.expenses)}"
                    print("⚠️ Firebase not available, expense saved locally only")

                self.expenses.append(expense_data)
                self.update_expenses_list()
                self.update_budget_summary()
                self.expense_from_picture_dialog.open = False
                self.page.update()
                self.show_snackbar("Expense added successfully!")

            except ValueError:
                self.show_snackbar("Please enter a valid amount")
            except Exception as ex:
                self.show_snackbar(f"Error saving expense: {ex}")
                print(f"❌ Detailed error: {ex}")

        print("Creating self.expense_from_picture_dialog")
        self.expense_from_picture_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add New Expense"),
            content=ft.Container(
                content=ft.Column([  # Changed from ListView to Column
                    upload_picture_button,
                    impulse_index_display,
                    share_with,
                    percentage_display,
                    owner,
                ], spacing=10),
                height=400,
                width=300,
                padding=10
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_dialog(self.expense_from_picture_dialog)),
                ft.ElevatedButton("Save", on_click=save_expense_from_picture)
            ],
            adaptive=True
        )
        print("Created add expense dialog, adding to page")
        self.page.dialog = self.expense_from_picture_dialog
        self.expense_from_picture_dialog.open = True
        self.page.update()

    def show_edit_expense_dialog(self, expense_id):
        """Show dialog to edit existing expense"""
        expense = next((exp for exp in self.expenses if exp.get('id') == expense_id), None)
        if not expense:
            return

        self.editing_expense_id = expense_id

        amount_input = ft.TextField(
            label="Amount",
            value=str(expense.get('amount', 0)),
            keyboard_type=ft.KeyboardType.NUMBER,
            adaptive=True,
            border_radius=12,
            prefix_icon=ft.icons.MONEY,
            bgcolor=ft.colors.BLUE_50,
            border_color=ft.colors.BLUE_200,
            focused_border_color=ft.colors.BLUE_400,
            suffix_text=self.currency,
        )

        amount_field = ft.Container(
            content=amount_input,
            margin=ft.margin.only(bottom=15)
        )

        category_input = ft.Dropdown(
            label="Category",
            value=expense.get('category', ''),
            options=self.show_expense_category(),
            border_radius=12,
            bgcolor=ft.colors.ORANGE_50,
            border_color=ft.colors.ORANGE_200,
            focused_border_color=ft.colors.ORANGE_400,
        )

        category_field = ft.Container(
            content=category_input,
            margin=ft.margin.only(bottom=15)
        )

        description_input = ft.TextField(
            label="Description",
            value=expense.get('description', ''),
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=12,
            bgcolor=ft.colors.GREEN_50,
            border_color=ft.colors.GREEN_200,
            focused_border_color=ft.colors.GREEN_400,
        )
        description_field = ft.Container(
            content=description_input,
            margin=ft.margin.only(bottom=15)
        )

        recurring_period_input = ft.Dropdown(
            options=[ft.dropdown.Option("No"),
                     ft.dropdown.Option("Monthly"),
                     ft.dropdown.Option("Yearly"),
                     ft.dropdown.Option("2 Months"),
                     ft.dropdown.Option("3 Months"),
                     ft.dropdown.Option("4 Months"),
                     ft.dropdown.Option("5 Months"),
                     ft.dropdown.Option("6 Months"),
                     ft.dropdown.Option("7 Months"),
                     ft.dropdown.Option("8 Months"),
                     ft.dropdown.Option("9 Months"),
                     ft.dropdown.Option("10 Months"),
                     ft.dropdown.Option("11 Months")],
            value=expense.get('is recurring', ''),
            border_radius=12,
            bgcolor=ft.colors.PURPLE_50,
            border_color=ft.colors.PURPLE_200,
            focused_border_color=ft.colors.PURPLE_400,
        )

        recurring_period = ft.Container(
            content=ft.Column([
                ft.Text("Recurring Period", weight=ft.FontWeight.W_500, size=14),
                recurring_period_input
            ], spacing=8),
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
        )
        friends = self.get_friend_data()
        share_with_options = [ft.dropdown.Option("No")] + [ft.dropdown.Option(friend) for friend in friends.keys()]

        share_with_input = ft.Dropdown(
            options=share_with_options,
            value=expense.get("shared"," "),
            border_radius=12,
            bgcolor=ft.colors.CYAN_50,
            border_color=ft.colors.CYAN_200,
            focused_border_color=ft.colors.CYAN_400,
        )

        share_with = ft.Container(
            content=ft.Column([
                ft.Text("Share With", weight=ft.FontWeight.W_500, size=14),
                share_with_input
            ], spacing=8),
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
        )

        percentage = ft.RangeSlider(
            min=0,
            max=100,
            start_value=0,
            end_value=50,
            divisions=10,
            label="{value}%",
            active_color=ft.colors.BLUE_400,
            inactive_color=ft.colors.BLUE_100,
            # thumb_color=ft.colors.BLUE_600,
        )

        percentage_display = ft.Container(
            content=ft.Column([
                ft.Text("Configure % of owed expense", weight=ft.FontWeight.W_500, size=14),
                percentage
            ], spacing=10),
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
        )

        review_item_input = ft.Checkbox(
            label="Review this expense later",
            value=expense.get('review', " "),
            check_color=ft.colors.WHITE,
            active_color=ft.colors.GREEN_400,
        )
        review_item = ft.Container(
            content=review_item_input,
            bgcolor=ft.colors.GREEN_50,
            border_radius=8,
            padding=10,
            margin=ft.margin.only(bottom=10)
        )

        owner_input = ft.Checkbox(
            label="I owe the expense",
            value=expense.get("owe status", " "),
            check_color=ft.colors.WHITE,
            active_color=ft.colors.ORANGE_400,
        )

        owner = ft.Container(
            content=owner_input,
            bgcolor=ft.colors.ORANGE_50,
            border_radius=8,
            padding=10,
            margin=ft.margin.only(bottom=15)
        )

        self.recurring_day = expense.get('recurring day', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.recurring_date_picker = ft.DatePicker(
            on_change=self.on_recurring_date_change,
            first_date=datetime(2025, 1, 1),
            last_date=datetime(2030, 12, 31),
            current_date=datetime.now()
        )

        self.recurring_date_button = ft.Container(
            content=ft.ElevatedButton(
                text=f"New Occurrence: {self.recurring_day}",
                icon=ft.icons.CALENDAR_MONTH,
                on_click=self.open_recurring_date_picker,
                bgcolor=ft.colors.INDIGO_400,
                color=ft.colors.WHITE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.padding.all(15)
                )
            ),
            margin=ft.margin.only(bottom=20)
        )

        def update_expense(e):
            try:
                amount = float(amount_input.value or 0)
                category = category_input.value or ""
                description = description_input.value or ""
                shared = share_with_input.value
                owe_status = owner_input.value
                is_recurring = recurring_period_input.value
                if is_recurring not in ['No', 'All']:
                    recurring_day = self.recurring_day
                else:
                    recurring_day = None

                friend_data = self.get_friend_data()

                if amount <= 0:
                    self.show_snackbar("Please enter a valid amount")
                    return

                expense_data = {
                    'user id': self.user_id,
                    'amount': amount,
                    'category': category,
                    'description': description,
                    'review': review_item_input.value,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': datetime.now(),
                    'shared': shared,
                    'owe status': owe_status,
                    'percentage': percentage.end_value,
                    'is recurring': is_recurring,
                    'recurring day': recurring_day
                }

                if amount <= 0:
                    self.show_snackbar("Please enter a valid amount")
                    return

                # Update in Firebase
                if not self.db:
                    self.db = firestore.client()

                self.db.collection('users').document(self.user_id).collection('expenses').document(expense_id)\
                    .update(expense_data)

                if shared != "No":
                    friend_expense_data = {
                        'user id': self.user_id,
                        'amount': amount,
                        'category': category,
                        'description': description,
                        'review item': False,
                        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'timestamp': datetime.now(),
                        'shared': self.display_name,
                        'owe status': not owe_status,
                        'percentage': str(100 - float(percentage.end_value)),
                        'is recurring': is_recurring,
                        'recurring day': recurring_day
                    }
                    self.db.collection('users').document(friend_data[shared]).collection('expenses').document(expense_id)\
                        .update(friend_expense_data)

                # Update local data
                for i, exp in enumerate(self.expenses):
                    if exp.get('id') == expense_id:
                        self.expenses[i].update(expense_data)
                        break

                self.update_expenses_list()
                self.update_budget_summary()
                self.create_budget_progress_card()
                self.create_quick_insights_row()
                self.create_highest_expenses_card()
                self.create_recent_transactions_card()
                self.edit_expense_dialog.open = False
                self.page.update()
                self.show_snackbar("Expense updated successfully!")

            except ValueError:
                self.show_snackbar("Please enter a valid amount")
            except Exception as ex:
                self.show_snackbar(f"Error updating expense: {ex}")

        self.edit_expense_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.EDIT_SHARP, color=ft.colors.BLUE_600, size=24),
                ft.Text("Edit Expense", weight=ft.FontWeight.BOLD, size=20, color=ft.colors.BLUE_900)
            ], spacing=10),
                padding=ft.padding.only(bottom=10)
            ),
            content=ft.Container(
                content=ft.Column([
                    amount_field,
                    category_field,
                    description_field,
                    recurring_period,
                    share_with,
                    percentage_display,
                    review_item,
                    owner,
                    self.recurring_date_button
                ], spacing=0, scroll=ft.ScrollMode.AUTO),
                height=600,
                width=400,
                padding=20,
                bgcolor=ft.colors.GREY_50,
                border_radius=15
            ),
            actions=[
                ft.Container(
                    content=ft.Row([
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda e: self.close_edit_dialog(),
                            style=ft.ButtonStyle(
                                color=ft.colors.GREY_600,
                                bgcolor=ft.colors.GREY_100,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.padding.symmetric(horizontal=20, vertical=10)
                            )
                        ),
                        ft.ElevatedButton(
                            "Update Expense",
                            on_click=update_expense,
                            icon=ft.icons.SAVE,
                            bgcolor=ft.colors.GREEN_500,
                            color=ft.colors.WHITE,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.padding.symmetric(horizontal=20, vertical=12)
                            )
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.only(top=10)
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=ft.colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=20),
            adaptive=True
        )
        self.page.overlay.append(self.recurring_date_picker)

        self.page.dialog = self.edit_expense_dialog
        self.edit_expense_dialog.open = True
        self.page.update()

    def delete_expense(self, expense_id):
        """Delete an expense"""

        def confirm_delete(e):
            try:
                # Delete from Firebase
                self.db.collection('expenses').document(expense_id).delete()

                # Remove from local data
                self.expenses = [exp for exp in self.expenses if exp.get('id') != expense_id]
                self.recurring_expenses = [exp for exp in self.recurring_expenses if exp.get('id') != expense_id]

                self.update_expenses_list()
                self.update_budget_summary()
                confirm_dialog.open = False
                self.page.update()
                self.show_snackbar("Expense deleted successfully!")

            except Exception as ex:
                self.show_snackbar(f"Error deleting expense: {ex}")

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm Delete"),
            content=ft.Text("Are you sure you want to delete this expense?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_confirm_dialog()),
                ft.ElevatedButton("Delete", on_click=confirm_delete,
                                  color=ft.colors.WHITE, bgcolor=ft.colors.RED)
            ]
        )

        self.page.dialog = confirm_dialog
        confirm_dialog.open = True
        self.page.update()

    def show_edit_wish_dialog(self, wish_id):
        """Show dialog to edit existing wish item"""
        wish_item = next((wish for wish in self.wishes if wish.get('id') == wish_id), None)
        if not wish_item:
            return

        self.editing_wish_id = wish_id

        amount_field = ft.TextField(label="Amount", value=str(wish_item.get('amount', 0)),
                                    keyboard_type=ft.KeyboardType.NUMBER, width=200)
        category_field = ft.TextField(label="Category", value=wish_item.get('category', ''), width=200)
        description_field = ft.TextField(label="Description", value=wish_item.get('description', ''),
                                         multiline=True, width=300)

        def update_wish_item(e):
            try:
                amount = float(amount_field.value or 0)
                category = category_field.value or ""
                description = description_field.value or ""

                if amount <= 0:
                    self.show_snackbar("Please enter a valid amount")
                    return

                # Update in Firebase
                self.db.collection('wish_list').document(wish_id).update({
                    'amount': amount,
                    'category': category,
                    'description': description,
                })

                self.update_wish_list()
                self.update_budget_summary()
                self.edit_wish_dialog.open = False
                self.page.update()
                self.show_snackbar("Wish List Item updated successfully!")

            except ValueError:
                self.show_snackbar("Please enter a valid amount")
            except Exception as ex:
                self.show_snackbar(f"Error updating wish list item: {ex}")

        self.edit_wish_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Wish List Item"),
            content=ft.Column([
                amount_field,
                category_field,
                description_field
            ], height=200),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_edit_dialog()),
                ft.ElevatedButton("Update", on_click=update_wish_item)
            ]
        )

        self.page.dialog = self.edit_expense_dialog
        self.edit_expense_dialog.open = True
        self.page.update()

    def delete_wish_list_item(self, wish_id):
        """Delete a wish list item"""

        def confirm_delete(e):
            try:
                # Delete from Firebase
                self.db.collection('wish_list').document(wish_id).delete()

                # Remove from local data
                self.wishes = [wish for wish in self.wishes if wish.get('id') != wish_id]

                self.update_wish_list()
                self.update_budget_summary()
                confirm_dialog.open = False
                self.page.update()
                self.show_snackbar("Expense deleted successfully!")

            except Exception as ex:
                self.show_snackbar(f"Error deleting Wish List Item: {ex}")

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm Delete"),
            content=ft.Text("Are you sure you want to delete this entry?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_confirm_dialog()),
                ft.ElevatedButton("Delete", on_click=confirm_delete,
                                  color=ft.colors.WHITE, bgcolor=ft.colors.RED)
            ]
        )

        self.page.dialog = confirm_dialog
        confirm_dialog.open = True
        self.page.update()

    def close_budget_dialog(self):
        self.budget_form_dialog.open = False
        self.page.update()

    def close_dialog(self, dialog):
        """Close dialog"""
        dialog.open = False
        self.page.update()

    def close_expense_dialog(self):
        self.expense_form_dialog.open = False
        self.page.update()

    def close_edit_dialog(self):
        self.edit_expense_dialog.open = False
        self.page.update()

    def close_confirm_dialog(self):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def on_start_date_change(self, e):
        self.start_date = e.control.value
        self.start_date_button.text = f"Start: {self.start_date.strftime('%Y-%m-%d')}"
        self.save_budget_data()
        self.update_budget_summary()
        self.page.update()

    def on_end_date_change(self, e):
        self.end_date = e.control.value
        self.end_date_button.text = f"End: {self.end_date.strftime('%Y-%m-%d')}"
        self.save_budget_data()
        self.update_budget_summary()
        self.page.update()

    def show_add_wish_dialog(self, e):
        """Show dialog to add new item on wish list"""

        amount_field = ft.TextField(label="Amount", keyboard_type=ft.KeyboardType.NUMBER, width=200)
        category_field = ft.Dropdown(
            label="Category",
            width=200,
            options=self.show_expense_category()
        )
        description_field = ft.TextField(label="Description", multiline=True, width=300)

        def save_wish(e):
            try:
                amount = float(amount_field.value or 0)
                category = category_field.value or ""
                description = description_field.value or ""

                if amount <= 0:
                    self.show_snackbar("Please enter a valid amount")
                    return

                wish_item_data = {
                    'user id': self.user_id,
                    'amount': amount,
                    'category': category,
                    'description': description,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': datetime.now(),

                }
                if not self.db:
                    self.db = firestore.client()
                # Save to Firebase if available
                if self.db:
                    # Add user ID to ensure data isolation
                    doc_ref = self.db.collection('users').document(self.user_id).collection('wish_list').add(
                        wish_item_data)
                    wish_item_data['id'] = doc_ref[1].id
                    print(f"✅ Wish added successfully for user : {wish_item_data['user id']}")

                else:
                    print("⚠️ Firebase not available")

                self.wishes.append(wish_item_data)
                print("Updating wish list")
                self.update_wish_list()
                self.update_budget_summary()
                self.wish_list_form_dialog.open = False
                self.page.update()
                self.show_snackbar("Wish added successfully!")

            except ValueError:
                self.show_snackbar("Please enter a valid amount")
            except Exception as ex:
                self.show_snackbar(f"Error saving item: {ex}")
                print(f"❌ Detailed error: {ex}")

        self.wish_list_form_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add New Item to your Wish List"),
            content=ft.Column([
                amount_field,
                category_field,
                description_field,
            ],
                tight=True,  # Makes column only as tall as needed
                spacing=10  # Add some spacing between elements
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_dialog(self.wish_list_form_dialog)),
                ft.ElevatedButton("Save", on_click=save_wish)
            ]
        )

        self.page.dialog = self.wish_list_form_dialog
        self.wish_list_form_dialog.open = True
        self.page.update()

    def save_budget(self, e):
        """Save budget configuration"""
        try:
            self.budget_amount = float(self.budget_input.value or 0)
            self.currency = self.currency_input.value
            self.save_budget_data()
            self.update_budget_summary()
            self.show_snackbar("Budget saved successfully!")

            self.budget_form_dialog.open = False
            self.page.update()

        except ValueError:
            self.show_snackbar("Please enter a valid budget amount")

    def save_budget_data(self):
        """Save budget data to Firebase"""
        if not self.db:
            print("⚠️ Firebase not initialized, initializing database")
            self.db = firestore.client()

        try:
            budget_data = {
                'amount': self.budget_amount,
                'currency': self.currency,
                'start_date': self.start_date,
                'end_date': self.end_date,
                'updated_at': datetime.now()
            }

            # Save or update budget document
            self.db.collection('users').document(self.user_id).collection('budget').document('current').set(budget_data)
            print(f"✅ Budget data saved successfully: {budget_data}")

        except Exception as e:
            print(f"❌ Error saving budget data: {e}")

    def load_budget_data(self):
        """Load budget data from Firebase"""
        print("entered loading budget function")
        if not self.db:
            print("⚠️ Firebase not initialized, initializing database")
            self.db = firestore.client()

        try:
            doc = self.db.collection('users').document(self.user_id).collection('budget').document('current').get()
            if doc.exists:
                data = doc.to_dict()
                self.budget_amount = data.get('amount', 0)
                self.currency = data.get('currency')
                self.start_date = data.get('start_date', self.start_date)
                self.end_date = data.get('end_date', self.end_date)
                print(f"✅ Budget data loaded successfully: {data}")
            else:
                print("ℹ️ No existing budget data found")
        except Exception as e:
            print(f"❌ Error loading budget data: {e}")

    def load_expenses(self):
        """Load expenses from Firebase"""
        if not self.db:
            print("⚠️ Firebase not initialized, skipping expenses load")
            self.db = firestore.client()

        try:
            expenses_ref = self.db.collection('users').document(self.user_id).collection('expenses').order_by(
                'timestamp', direction=firestore.Query.DESCENDING)
            docs = expenses_ref.stream()

            self.expenses = []
            for doc in docs:
                expense_data = doc.to_dict()
                expense_data['id'] = doc.id
                self.expenses.append(expense_data)
                if expense_data['is recurring'] != 'No' and expense_data[
                    'date'] not in self.recurring_expense_timestamps:
                    self.recurring_expenses.append(expense_data)
                    self.recurring_expense_timestamps.append(expense_data['date'])
            print(f"✅ Loaded {len(self.expenses)} expenses from Firebase")

            self.automaticaly_update_expense()
            self.update_expenses_list()

            print(self.recurring_expenses)
            print(self.recurring_expense_timestamps)

        except Exception as e:
            print(f"❌ Error loading expenses: {e}")

    def load_wish_list(self):
        """Load wish list from Firebase"""
        if not self.db:
            print("⚠️ Firebase not initialized, skipping expenses load")
            self.db = firestore.client()

        try:
            wish_list_ref = self.db.collection('users').document(self.user_id).collection('wish_list').order_by(
                'timestamp', direction=firestore.Query.DESCENDING)
            docs = wish_list_ref.stream()

            self.wishes = []
            for doc in docs:
                wish_data = doc.to_dict()
                wish_data['id'] = doc.id
                self.wishes.append(wish_data)
            print(f"✅ Loaded {len(self.wishes)} wishes from Firebase")

            self.update_wish_list()


        except Exception as e:
            print(f"❌ Error loading wishes: {e}")

    def load_analysis_list(self):
        """Load wish list from Firebase"""
        if not self.db:
            print("⚠️ Firebase not initialized, skipping expenses load")
            self.db = firestore.client()

        try:
            analysis_list_ref = self.db.collection('users').document(self.user_id).collection('analysis_list').order_by(
                'timestamp', direction=firestore.Query.DESCENDING)
            docs = analysis_list_ref.stream()

            self.analysis = []
            for doc in docs:
                analysis_data = doc.to_dict()
                analysis_data['id'] = doc.id
                self.analysis.append(analysis_data)
            print(f"✅ Loaded {len(self.analysis)} entries from Firebase")

            self.update_analysis_list()


        except Exception as e:
            print(f"❌ Error loading analysis entries: {e}")

    def settle_expense(self, amount, friend):
        friends = self.get_friend_data()
        expense_data = {
            'user id': self.user_id,
            'amount': amount,
            'category': "Debt Payment",
            'description': "Settling payment",
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': datetime.now(),
            'shared': 'No',
            'owe status': False,
            'percentage': 0,
            'is recurring': 'No',
            'recurring day': None
        }
        if not self.db:
            db = firestore.client()
            # Save to Firebase if available
        if self.db:
            doc_ref = self.db.collection('users').document(self.user_id).collection('expenses').add(expense_data)
            print(f"✅ Expense saved successfully with ID: {expense_data['id']}")
            print(f"📊 Expense data: {expense_data}")
        else:
            # Generate a temporary ID for local storage
            expense_data['id'] = f"local_{len(self.expenses)}"
            print("⚠️ Firebase not available, expense saved locally only")

        self.expenses.append(expense_data)
        self.update_expenses_list()
        self.update_budget_summary()
        self.page.update()

    def update_shared_expenses(self):
        "Update the shared expenses display"
        print("Updating shared expenses: ")
        #friends_list = self.get_friend_data()
        friends_list = FriendsManager(self.user_id).get_friends_list()
        print(f"friend list is {friends_list}")
        shared_info = {}
        for friend in friends_list:
            print("going throuh expenses to calculate shared expenses")
            shared_info[friend['displayName']] = 0
            for expense in self.expenses:
                if expense['shared'] != 'No':
                    if expense['owe status']:
                        shared_info[friend['displayName']] -= expense['amount'] * float(expense['percentage']) * 0.01
                    else:
                        shared_info[friend['displayName']] += expense['amount'] * float(expense['percentage']) * 0.01

        if not shared_info:
            return ft.Text("No shared expenses")
        print(f"shared info {shared_info}")

        expense_items = []
        for person, amount in shared_info.items():
            if amount < 0:
                item = ft.Container(
                    content=ft.Row([
                        ft.Text(f"You owe {person}: {abs(amount):.2f} {self.currency}", color=ft.colors.RED),
                        ft.ElevatedButton(
                            text="Settle",
                            on_click=lambda e, amount=abs(shared_info[person]): self.settle_expense(amount, person)
                        )
                    ]),
                    padding=5
                )
            else:
                item = ft.Container(
                    content=ft.Text(f"{person} owes you: {amount:.2f} {self.currency}", color=ft.colors.GREEN_500),
                    padding=5
                )

            expense_items.append(item)

        return ft.Column(expense_items, spacing=5)

    def get_total_expenses(self):
        print("calculating total expenses for budget progress card")
        if self.end_date.strftime("%Y-%m-%d") < datetime.now().strftime("%Y-%m-%d"):
            self.start_date = self.end_date
            self.end_date = datetime.now()
        start_date = self.start_date.strftime("%Y-%m-%d")
        total_expenses = sum(expense.get('amount', 0) for expense in self.expenses if
                             (expense['shared'] == 'No' or expense['owe status']
                              is not True and expense['user id'] == self.user_id)
                             and (start_date <= expense['date']))
        return total_expenses

    def update_budget_summary(self):
        """Update the budget summary display"""
        print("Creating budget summary for overview")
        if self.end_date.strftime("%Y-%m-%d") < datetime.now().strftime("%Y-%m-%d"):
            self.start_date = self.end_date
            self.end_date = datetime.now()
        print("Budget summary - setting dates")
        start_date = self.start_date.strftime("%Y-%m-%d")
        end_date = self.end_date.strftime("%Y-%m-%d")
        print(f"Print expenses: {self.expenses[0]}")
        total_expenses = self.get_total_expenses()
        remaining_budget = self.budget_amount - total_expenses
        percentage_used = (total_expenses / self.budget_amount * 100) if self.budget_amount > 0 else 0

        print(f"Budget date: {self.end_date}, type : {type(self.end_date)}")

        self.budget_summary.content = ft.Row([
            # Budget card with improved styling
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET,
                                size=20, color=ft.colors.BLUE_600),
                        ft.Text("Budget", size=13, color=ft.colors.GREY_700,
                                weight=ft.FontWeight.W_500),
                    ], spacing=8),
                    ft.Container(height=8),
                    ft.Text(f"{self.budget_amount:.2f} {self.currency}",
                            size=20, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700),
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                bgcolor=ft.colors.BLUE_50,
                border_radius=16,
                padding=20,
                expand=1,
                # Add subtle shadow for depth
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=8,
                    color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                    offset=ft.Offset(0, 2)
                ),
                border=ft.border.all(1, ft.colors.BLUE_200)
            ),

            # Spent card with improved visual treatment
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.TRENDING_UP,
                                size=20, color=ft.colors.RED_600),
                        ft.Text("Spent", size=13, color=ft.colors.GREY_700,
                                weight=ft.FontWeight.W_500),
                    ], spacing=8),
                    ft.Container(height=8),
                    ft.Text(f"{total_expenses:.2f} Lei",
                            size=20, weight=ft.FontWeight.BOLD, color=ft.colors.RED_700),
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                bgcolor=ft.colors.RED_50,
                border_radius=16,
                padding=20,
                expand=1,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=8,
                    color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                    offset=ft.Offset(0, 2)
                ),
                border=ft.border.all(1, ft.colors.RED_200)
            ),

            # Remaining card with enhanced styling
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.SAVINGS,
                                size=20, color=ft.colors.GREEN_600),
                        ft.Text("Remaining", size=13, color=ft.colors.GREY_700,
                                weight=ft.FontWeight.W_500),
                    ], spacing=8),
                    ft.Container(height=8),
                    ft.Text(f"{remaining_budget:.2f} {self.currency}",
                            size=20, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_700),
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                bgcolor=ft.colors.GREEN_50,
                border_radius=16,
                padding=20,
                expand=1,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=8,
                    color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                    offset=ft.Offset(0, 2)
                ),
                border=ft.border.all(1, ft.colors.GREEN_200)
            ),
        ], spacing=15)


        if self.page:
            self.page.update()

    def reset_password(self, e):
        """Handle password reset request"""
        print("reseting password")
        email = self.email_field.value

        if not email:
            self.show_password_reset_dialog()
            return

        self.send_password_reset_email(email)

    def show_password_reset_dialog(self):
        """Show dialog to enter email for password reset"""
        self.reset_email_field = ft.TextField(
            label="Enter your email address",
            width=300,
            autofocus=True
        )

        def send_reset_email(e):
            email = self.reset_email_field.value
            if email:
                self.close_dialog(reset_dialog)
                self.send_password_reset_email(email)
            else:
                # Show error in dialog
                error_text.value = "Please enter your email address"
                error_text.color = ft.colors.RED
                self.page.update()

        error_text = ft.Text("")

        reset_dialog = ft.AlertDialog(
            title=ft.Text("Reset Password"),
            content=ft.Column([
                ft.Text("Enter your email address to receive password reset instructions."),
                self.reset_email_field,
                error_text
            ], height=150, spacing=10),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self.close_dialog(reset_dialog)),
                ft.ElevatedButton("Send Reset Email", on_click=send_reset_email)
            ]
        )

        self.page.dialog = reset_dialog
        reset_dialog.open = True
        self.page.update()

    def send_password_reset_email(self, email):
        """Send password reset email using Firebase Auth with actual email sending"""

        try:
            # Validate email format
            if not self.is_valid_email(email):
                self.status_text.value = "Please enter a valid email address"
                self.status_text.color = ft.colors.RED
                self.page.update()
                return

            auth.generate_password_reset_link(email)
            print(f"Successfully sent password reset email to {email}")



        except Exception as e:

            # Handle specific Firebase errors, e.g., invalid email format

            print(f"Error sending password reset email: {e}")

            if "invalid-email" in str(e):

                print("The provided email address is not a valid format.")

            elif "user-not-found" in str(e):

                # While the API generally tries to mask this, sometimes

                # a more specific error can surface depending on context/SDK version.

                print("No user found with the given email address.")

            else:

                print("An unexpected Firebase error occurred.")

    def show_reset_success_dialog(self, email):
        """Show success dialog after password reset request"""
        success_dialog = ft.AlertDialog(
            title=ft.Text("Password Reset Sent"),
            content=ft.Column([
                ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN, size=48),
                ft.Text(f"Password reset instructions have been sent to {email}"),
                ft.Text("Please check your email and follow the instructions to reset your password."),
                ft.Text("If you don't see the email, check your spam folder.")
            ], height=200, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[
                ft.ElevatedButton("OK", on_click=lambda _: self.close_dialog(success_dialog))
            ]
        )

        self.page.dialog = success_dialog
        success_dialog.open = True
        self.page.update()

        # Clear status text and reset form
        self.status_text.value = ""
        self.email_field.value = ""
        self.password_field.value = ""
        self.page.update()

    def is_valid_email(self, email):
        """Basic email validation"""
        print("mail validating function")
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        return re.match(pattern, email) is not None

    def show_snackbar(self, message):
        """Show a snackbar with a message"""
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()

    def show_error_dialog(self, message):
        """Show error dialog"""
        dialog = ft.AlertDialog(
            title=ft.Text("Error"),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=lambda _: self.close_dialog(dialog))]
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def get_category_icon(self, category):
        icons_map = {
            # Essential Living
            "Groceries": ft.icons.SHOPPING_CART,
            "Housing": ft.icons.HOME,
            "Utilities": ft.icons.BOLT,
            "Transportation": ft.icons.DIRECTIONS_CAR,
            "Insurance": ft.icons.SECURITY,
            "Healthcare": ft.icons.LOCAL_HOSPITAL,
            # Personal Care
            "Personal Care": ft.icons.FACE,
            "Clothing": ft.icons.CHECKROOM,
            "Fitness": ft.icons.FITNESS_CENTER,
            # Food & Dining
            "Dining Out": ft.icons.RESTAURANT,
            "Coffee": ft.icons.COFFEE,
            "Snacks": ft.icons.FASTFOOD,
            # Entertainment & Leisure
            "Entertainment": ft.icons.MOVIE,
            "Hobbies": ft.icons.PALETTE,
            "Books": ft.icons.BOOK,
            "Gaming": ft.icons.SPORTS_ESPORTS,
            # Technology
            "Digital Services": ft.icons.CLOUD,
            "Electronics": ft.icons.DEVICES,
            "Software": ft.icons.COMPUTER,
            # Family & Social
            "Childcare": ft.icons.CHILD_CARE,
            "Education": ft.icons.SCHOOL,
            "Gifts": ft.icons.CARD_GIFTCARD,
            "Pet Care": ft.icons.PETS,
            # Special Occasions
            "Travel": ft.icons.FLIGHT,
            "Events": ft.icons.CELEBRATION,
            "Charity": ft.icons.VOLUNTEER_ACTIVISM,
            # Financial
            "Savings": ft.icons.SAVINGS,
            "Investments": ft.icons.TRENDING_UP,
            "Debt Payment": ft.icons.PAYMENT,
            # Miscellaneous
            "Emergency": ft.icons.WARNING,
            "Other": ft.icons.MORE_HORIZ
        }
        return icons_map.get(category, ft.icons.MONEY)

    def create_pie_sections(self, e=None):
        expense_categories = {}
        period = self.pie_filter.selected_index
        print("Creating pie sections")
        print(f"selected index = {period}")
        if self.pie_filter.selected_index == 0:
            reference_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        elif self.pie_filter.selected_index == 1:
            reference_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
        elif self.pie_filter.selected_index == 2:
            reference_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
        elif self.pie_filter.selected_index == 3:
            reference_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
        elif self.pie_filter.selected_index == 4:
            reference_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            reference_date = (datetime.now() - timedelta(days=1000)).strftime("%Y-%m-%d %H:%M:%S")

        for expense in self.expenses:
            if expense['category'] in expense_categories.keys() and expense['date'] > reference_date:
                expense_categories[expense['category']] += expense['amount']
            else:
                if expense['date'] > reference_date:
                    expense_categories[expense['category']] = expense['amount']
        category_colors = {
            "Food": ft.colors.RED_400,
            "Transport": ft.colors.LIGHT_BLUE_400,
            "Entertainment": ft.colors.PURPLE_200,
            "Cloths": ft.colors.LIME_900,
            "Bills": ft.colors.RED_ACCENT_200,
            "Childcare": ft.colors.YELLOW_300,
            "Health": ft.colors.GREEN_600,
            "Digital services": ft.colors.BLUE_500,
            "Dining Out": ft.colors.ORANGE_200,
            "Toys": ft.colors.PURPLE_400,
            "Presents": ft.colors.PURPLE_800,
            "Other": ft.colors.TEAL_500,
            "Vacation": ft.colors.GREEN_ACCENT_400,
            "Books": ft.colors.BLUE_500,
            "Self Improvement": ft.colors.LIME_200,
        }

        pie_sections = [ft.PieChartSection(
            value=amount,
            title=category,
            radius=200,
            color=category_colors.get(category, ft.colors.GREY_500)
        )
            for category, amount in expense_categories.items()
        ]
        self.highest_expenses = list(sorted(expense_categories.items(), key=lambda item: item[1]))[::-1]
        return pie_sections

    def load_settings(self) -> Dict:
        """Load settings from db or file or create default settings"""
        if not self.db:
            print("⚠️ Firebase not initialized, loading settings from file")
            if os.path.exists(self.settings_file):
                try:
                    with open(self.settings_file, 'r') as f:
                        loaded_settings = json.load(f)
                        # Merge with defaults to ensure all keys exist
                        return {**self.default_settings, **loaded_settings}
                except (json.JSONDecodeError, IOError):
                    return self.default_settings.copy()
            return self.default_settings.copy()
        try:
            doc = self.db.collection('users').document(self.user_id).collection('settings').document(
                'display_name').get()
            if doc.exists:
                data = doc.to_dict()
                self.display_name = data.get('display_name')
                print(f"✅ Settings data loaded successfully: {data}, {self.display_name}")
            else:
                print("ℹ️ No existing settings data found")
        except Exception as e:
            print(f"❌ Error loading settings data: {e}")

    def load_avatar(self) -> Dict:
        """Load settings from db or file or create default settings"""
        if not self.db:
            print("⚠️ Firebase not initialized, loading settings from file")
            if os.path.exists(self.settings_file):
                try:
                    with open(self.settings_file, 'r') as f:
                        loaded_settings = json.load(f)
                        # Merge with defaults to ensure all keys exist
                        return {**self.default_settings, **loaded_settings}
                except (json.JSONDecodeError, IOError):
                    return self.default_settings.copy()
            return self.default_settings.copy()
        try:
            doc = self.db.collection('users').document(self.user_id).collection('settings').document('avatar').get()
            if doc.exists:
                data = doc.to_dict()
                self.current_avatar = data.get('avatar_path')
                print(f"✅ Settings data loaded successfully: {data}, {self.display_name}")
            else:
                print("ℹ️ No existing settings data found")
        except Exception as e:
            print(f"❌ Error loading settings data: {e}")

    def save_settings(self, e=None):
        """Save current settings to file"""
        if not self.db:
            print("⚠️ Firebase not initialized, saving settings to file")
            try:
                with open(self.settings_file, 'w') as f:
                    json.dump(self.settings, f, indent=2)
            except IOError:
                print("Error saving settings")
        else:
            print("saving settings")
            self.display_name = self.name_input.value

            # Save or update budget document
            self.update_user_profile(self.user_id, 'displayName', self.display_name)
        self.display_name_form_dialog.open = False
        self.page.update()

    def get_setting(self, key: str):
        """Get a specific setting value"""
        return self.settings.get(key, self.default_settings.get(key))

    def set_setting(self, key: str, value):
        """Set a specific setting value"""
        self.settings[key] = value
        self.save_settings()

    def show_add_name_dialog(self, e):
        """Show dialog to configure budget"""
        print("creating display_name")
        self.name_input = ft.TextField(
            label="Display Name",
            value=str(''),
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.display_name_form_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Configure Your Display Name"),
            content=ft.Column([
                self.name_input,
            ], height=200),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_dialog(self.display_name_form_dialog)),
                ft.ElevatedButton("Save", on_click=self.save_settings)
            ]
        )

        self.page.dialog = self.display_name_form_dialog
        self.display_name_form_dialog.open = True
        self.page.update()

    def open_settings_menu(self, e=None):
        print("Creating settings menu")
        return ft.Container(
            content=ft.PopupMenuButton(
                items=[
                    ft.PopupMenuItem(
                        content=ft.Row([
                            ft.Icon(ft.icons.ACCOUNT_CIRCLE, size=20, color=ft.colors.GREY_600),
                            ft.Text('Avatar Image', size=14, weight=ft.FontWeight.W_500)
                        ], spacing=12),
                        on_click=self.show_avatar_selection_dialog
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row([
                            ft.Icon(ft.icons.EDIT, size=20, color=ft.colors.GREY_600),
                            ft.Text('Display Name', size=14, weight=ft.FontWeight.W_500)
                        ], spacing=12),
                        on_click=self.show_add_name_dialog
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row([
                            ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=20, color=ft.colors.GREY_600),
                            ft.Text('Configure Budget', size=14, weight=ft.FontWeight.W_500)
                        ], spacing=12),
                        on_click=self.show_add_budget_dialog
                    ),
                    ft.PopupMenuItem(),  # Divider
                    ft.PopupMenuItem(
                        content=ft.Row([
                            ft.Icon(ft.icons.LOGOUT, size=20, color=ft.colors.RED_600),
                            ft.Text('Logout', size=14, weight=ft.FontWeight.W_500, color=ft.colors.RED_600)
                        ], spacing=12),
                        on_click=self.logout_clicked
                    ),

                ],
                content=ft.Container(
                    content=ft.Icon(ft.icons.SETTINGS, size=24, color=ft.colors.GREY_600),
                    padding=12,
                    bgcolor=ft.colors.WHITE,
                    border_radius=12,
                    border=ft.border.all(1, ft.colors.GREY_200),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=4,
                        color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                        offset=ft.Offset(0, 2)
                    )
                ), bgcolor=ft.colors.LIGHT_GREEN_50
            ),
        )

    def show_avatar_selection_dialog(self, e=None):
        """Show dialog with all available avatars for selection"""
        print("Showing avatar selection dialog")
        self.available_avatars = self.get_available_avatars_from_folder()
        # Create a grid of avatar options
        avatar_grid = []
        for i, avatar_path in enumerate(self.available_avatars):
            avatar_container = ft.Container(
                content=ft.Image(
                    src=avatar_path,
                    fit=ft.ImageFit.COVER,
                    error_content=ft.Text("Error"),
                ),
                width=80,
                height=80,
                border_radius=40,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                border=ft.border.all(3, ft.colors.BLUE_400) if avatar_path == self.current_avatar else None,
                on_click=lambda e, path=avatar_path: self.select_avatar(e, path),
                bgcolor=ft.colors.GREY_200,
            )
            avatar_grid.append(avatar_container)

        # Create dialog content
        dialog_content = ft.Column([
            ft.Text("Choose your avatar:", size=20, weight=ft.FontWeight.BOLD),
            ft.Container(height=10),  # Spacing
            ft.GridView(
                controls=avatar_grid,
                runs_count=3,  # 3 avatars per row
                max_extent=100,
                child_aspect_ratio=1.0,
                spacing=10,
                run_spacing=10,
                height=300,  # Fixed height for scrolling
            )
        ])

        # Create the dialog
        self.avatar_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Select Avatar"),
            content=dialog_content,
            actions=[
                ft.TextButton("Cancel", on_click=self.close_avatar_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # Show the dialog
        e.page.dialog = self.avatar_dialog
        self.avatar_dialog.open = True
        e.page.update()

    def select_avatar(self, e, avatar_path):
        """Handle avatar selection"""
        print(f"Selected avatar: {avatar_path}")

        # Update current avatar
        self.current_avatar = avatar_path
        self.save_avatar()

        # Close dialog
        self.close_avatar_dialog(e)

        # Update the UI with new avatar
        self.update_avatar_display()
        self.page.update()

        # Show confirmation
        self.show_snack_bar(e.page, "Avatar updated successfully!")

    def close_avatar_dialog(self, e):
        """Close the avatar selection dialog"""
        if self.avatar_dialog:
            self.avatar_dialog.open = False
            e.page.update()

    def get_available_avatars_from_folder(self,
                                          folder_path=r"C:\Users\SPopa\PycharmProjects\ExpenseTracker\src\assets"):
        """Automatically get all image files from assets folder"""
        avatars = []
        if os.path.exists(folder_path):
            for file in os.listdir(folder_path):
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    avatars.append(f"{folder_path}/{file}")
        return avatars

    def update_avatar_display(self):
        """Update the avatar display in your main UI"""
        # You'll need to update your main avatar container here
        # This depends on how your main UI is structured
        # For example, if you have a reference to your avatar container:
        self.main_avatar_container.content.src = self.current_avatar
        self.page.update()
        self.update_displays()
        print(f"Avatar display updated to: {self.current_avatar}")

    def show_snack_bar(self, page, message):
        """Show a confirmation message"""
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.colors.GREEN_400,
        )
        page.snack_bar.open = True
        page.update()

    def save_avatar(self, e=None):
        """Save avatar path to file"""
        if not self.db:
            print("⚠️ Firebase not initialized, saving settings to file")
            try:
                with open(self.settings_file, 'w') as f:
                    json.dump(self.settings, f, indent=2)
            except IOError:
                print("Error saving settings")
        else:
            try:
                print("saving avatar")
                self.avatar_patsh = self.current_avatar
                settings_data = {
                    "avatar_path": self.current_avatar,
                }

                # Save or update budget document
                self.db.collection('users').document(self.user_id).collection('settings').document('avatar').set(
                    settings_data)
                print(f"✅ Budget data saved successfully: {settings_data}")
            except Exception as e:
                print(f'An exception occured: {e}')

    def generate_themed_advice(self):
        fallback_messages = [
            "Great job tracking your expenses! Every dollar you monitor is a step toward financial freedom.",
            "Small consistent savings today lead to big financial wins tomorrow. Keep up the excellent work!",
            "You're building healthy money habits that will serve you for life. Stay focused on your goals!",
            "Remember: budgeting isn't about restricting yourself, it's about giving yourself permission to "
            "spend on what truly matters.",
            "Your financial journey is a marathon, not a sprint. Every budget decision is progress forward.",
            "Celebrating small wins keeps you motivated! Each day you stick to your budget is a victory "
            "worth acknowledging.",
            "You have the power to shape your financial future. Every conscious spending choice brings "
            "you closer to your dreams.",
            "Building wealth isn't about making more money—it's about making smart decisions with what you have.",
            "Learn as you go. Personal finance is a journey, not a race. Take time to understand your choices and "
            "enjoy the growth along the way.",
            "Invest in yourself too. Spending money on learning, growth, or health can be just as valuable as "
            "saving—balance is key.",
            "Stay inspired. Read stories of others who’ve succeeded, listen to uplifting podcasts, or join a community"
            " working toward financial wellness. You’re not alone on this path!",
            "Practice mindful spending. Before buying, pause and ask: Does this align with my goals? This tiny habit "
            "can make a huge difference.",
            "Avoid comparing your journey to others. Your financial story is uniquely yours. Focus on your progress, "
            "not someone else's finish line.",
            "Be patient with yourself. Financial habits take time to build. Every good choice is a brick in the foundation."
            "of your future security.",
            "Cut expenses with creativity, not deprivation. Challenge yourself to find fun, low-cost alternatives that still bring joy.",
            "Learn as you go. Personal finance is a journey, not a race. Take time to understand your choices and enjoy the "
            "growth along the way.",
            "Review your progress regularly. A quick monthly check-in helps you stay on course and adjust as needed. "
            "Think of it like steering your ship towards your goals."
        ]
        return random.choice(fallback_messages)


def main(page: ft.Page):
    print("Main function called")  # Debug print
    try:
        app = BudgetApp(page)
        print("App created successfully")  # Debug print
    except Exception as e:
        print(f"Error creating app: {e}")
        page.add(ft.Text(f"Error: {e}"))
        page.update()


if __name__ == "__main__":
    print("Starting app...")  # Debug print
    ft.app(target=main)
