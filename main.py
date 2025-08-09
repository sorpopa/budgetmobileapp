import flet as ft
import json
from firebase_admin import firestore, auth
from google.cloud import firestore as fire
from datetime import datetime, timedelta, time
from typing import Dict
import os
from dotenv import load_dotenv
import random
import base64
from dateutil.relativedelta import relativedelta
from theme import Themecolors
from auth_manager import AuthManager
from friends_manager import FriendsUI, FriendsManager
from ai_utilities import FinancialAdviceGenerator
from claude_api import ClaudeUtilityFunctions
from firebase_utils import FirebaseAuth

load_dotenv()


class BudgetApp:
    def __init__(self, page: ft.Page):
        # Check if configuration is loaded
        self.page = page
        self.page.title = "Expense Tracker"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.is_dark_mode = True
        self.theme_color = Themecolors(page)
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.db = None

        self.budget_amount = 0
        self.start_date = datetime.now().strftime('%Y-%m-%d')
        self.end_date = datetime.now().strftime('%Y-%m-%d')
        self.expenses = []
        self.wishes = []
        self.analysis = []
        self.expense_form_dialog = None
        self.income_form_dialog = None
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
        self.refresh_token = None
        self.token_expiry = None
        self.user_id = None
        self.display_name = None
        self.currency = None
        self.available_avatars = None
        self.current_avatar = r"/assets/fancy zebra.png"

        # UI Controls
        self.email_field = ft.TextField(label="Email", expand=True)
        self.password_field = ft.TextField(label="Password", password=True, expand=True)
        self.error_text = ft.Text(color=ft.colors.RED)
        self.user_info = ft.Text()

        self.friend_list = []

        self.settings_file = "app_settings.json"
        self.default_settings = {
            "display_name": "User",
            "theme": 'DARK',
            "avatar": self.current_avatar
        }
        self.settings = self.default_settings

        # Create main container
        self.main_container = ft.Column(
            controls=[self.create_auth_view()],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20
        )

        self.auth_manager = AuthManager()
        self.advice_generator = FinancialAdviceGenerator()
        self.initialize_firebase()
        self.ai_analyst = ClaudeUtilityFunctions()

        self.check_existing_session()
        # self.setup_ui()

    def set_app_theme(self, e=None):
        self.is_dark_mode = e.control.value
        self.update_user_profile(self.user_id, "theme", self.is_dark_mode)

        if self.is_dark_mode:
            self.page.theme_mode = ft.ThemeMode.DARK

        else:
            self.page.theme_mode = ft.ThemeMode.LIGHT

        self.page.update()
        self.show_main()

    def check_existing_session(self):
        user_session = self.auth_manager.load_user_session()
        remember_user = user_session.get('remember_me')
        stored_token = user_session.get('id_token')
        self.refresh_token = user_session.get('refresh_token')
        user_id = user_session.get('user_id')
        print(f"Saved user session: {user_session}")

        if remember_user and stored_token:
            if not self.db:
                print("⚠️ Firebase not initialized, initializing database")
                self.db = firestore.client()
            try:
                try:
                    decoded_token=self.firebase_auth.verify_token(stored_token)
                    if "error" in decoded_token:
                        print(f"Refreshing token {self.refresh_token}")
                        stored_token, self.refresh_token = self.firebase_auth.refresh_id_token(self.refresh_token)
                    print(f"Decoded token is {decoded_token}")
                except Exception as e:
                    print(e)
                user = auth.get_user(user_id)
                if user:
                    self.user_id = user_id
                    self.id_token = stored_token
                    user_doc = self.db.collection('users').document(self.user_id).get()
                    user_data = user_doc.to_dict()
                    self.current_user = {}
                    self.current_user['localId'] = self.user_id
                    self.current_user['email'] = user_data.get('email')
                    self.current_user['displayName'] = user_data.get('displayName')
                    self.current_user['idToken'] = user_data.get('idToken')
                    self.show_main()
            except Exception as e:
                print(f"Token validation failed: {e}")
                self.setup_ui()
        else:
            self.setup_ui()

    def create_auth_view(self):
        """Create authentication UI"""
        self.status_text = ft.Text("")

        app_logo = ft.Container(
            content=ft.Icon(
                name=ft.icons.ACCOUNT_BALANCE_WALLET,
                size=56,
                color=self.theme_color.text_primary
            ),
            bgcolor=ft.colors.WHITE24,
            border_radius=20,
            padding=12,
            margin=ft.margin.only(bottom=15)
        )

        title_section = ft.Column([
            ft.Text(
                "Expense Tracker",
                size=32,
                weight=ft.FontWeight.BOLD,
                color=self.theme_color.text_logo,
                text_align=ft.TextAlign.CENTER
            ),
            ft.Text(
                "Track your expenses effortlessly",
                size=16,
                color=ft.colors.WHITE70,
                text_align=ft.TextAlign.CENTER
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)

        email_field = email_field = ft.TextField(
                    label="Email",
                    border=ft.InputBorder.NONE,
                    label_style=ft.TextStyle(color=ft.colors.WHITE70 , size=14),
                    text_style=ft.TextStyle(color=ft.colors.WHITE70, size=16),
                    cursor_color=ft.colors.TEAL_800,
                    selection_color=ft.colors.TEAL_200,
                    content_padding=ft.padding.symmetric(horizontal=20, vertical=16)
                )

        email_container = ft.Container(
            content=email_field,
            bgcolor=ft.colors.WHITE12,
            border_radius=16,
            width=350,
            height=60,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color=ft.colors.BLACK26,
                offset=ft.Offset(0, 4)
            ),
            margin=ft.margin.only(bottom=5)
        )

        password_field = ft.TextField(
                        label="Password",
                        password=True,
                        border=ft.InputBorder.NONE,
                        label_style=ft.TextStyle(color=ft.colors.WHITE70, size=14),
                        text_style=ft.TextStyle(color=ft.colors.WHITE70, size=16),
                        cursor_color=ft.colors.TEAL_600,
                        selection_color=ft.colors.TEAL_200,
                        content_padding=ft.padding.symmetric(horizontal=20, vertical=16)
                    )

        password_container = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=password_field,
                    expand=True
                ),
                ft.Container(
                    content=ft.IconButton(
                        icon=ft.icons.VISIBILITY_OFF,
                        icon_color=ft.colors.GREY_600,
                        icon_size=20,
                        tooltip="Show password",
                        on_click=lambda e: self.toggle_password_visibility(password_field, e),
                        style=ft.ButtonStyle(
                            overlay_color=ft.colors.TEAL_100
                        )
                    ),
                    padding=ft.padding.only(right=8)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=ft.colors.WHITE12,
            border_radius=16,
            width=350,
            height=60,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color=ft.colors.BLACK26,
                offset=ft.Offset(0, 4)
            ),
            margin=ft.margin.only(top=5)
        )

        sign_in_button = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row([
                    ft.Text("Sign In", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE24),
                    ft.Icon(ft.icons.ARROW_FORWARD, color=ft.colors.WHITE24, size=20)
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                on_click=lambda _: self.sign_in_clicked(email_field.value, password_field.value),
                style=ft.ButtonStyle(
                    bgcolor=self.theme_color.sign_in,
                    elevation=8,
                    shadow_color=ft.colors.DEEP_ORANGE_300,
                    shape=ft.RoundedRectangleBorder(radius=16),
                    padding=ft.padding.symmetric(vertical=18),
                    overlay_color={
                        ft.MaterialState.HOVERED: ft.colors.DEEP_ORANGE_700,
                        ft.MaterialState.PRESSED: ft.colors.DEEP_ORANGE_800,
                    }
                ),
                width=350
            ),
            margin=ft.margin.symmetric(vertical=15)
        )

        secondary_actions = ft.Container(
            content=ft.Row([
                ft.TextButton(
                    content=ft.Text(
                        "Forgot Password?",
                        color=ft.colors.WHITE,
                        size=15,
                        weight=ft.FontWeight.W_500
                    ),
                    on_click=self.reset_password,
                    style=ft.ButtonStyle(
                        overlay_color=ft.colors.WHITE24,
                        padding=ft.padding.symmetric(horizontal=16, vertical=8),
                        shape=ft.RoundedRectangleBorder(radius=8)
                    )
                ),
                ft.Container(
                    content=ft.Text("•", color=ft.colors.WHITE60, size=16),
                    margin=ft.margin.symmetric(horizontal=12)
                ),
                ft.TextButton(
                    content=ft.Text(
                        "Create Account",
                        color=ft.colors.WHITE,
                        size=15,
                        weight=ft.FontWeight.W_500
                    ),
                    on_click=lambda _: self.sign_up_clicked(email_field.value, password_field.value),
                    style=ft.ButtonStyle(
                        overlay_color=ft.colors.WHITE24,
                        padding=ft.padding.symmetric(horizontal=16, vertical=8),
                        shape=ft.RoundedRectangleBorder(radius=8)
                    )
                )
            ], alignment=ft.MainAxisAlignment.CENTER),
            margin=ft.margin.only(bottom=20)
        )

        biometric_section = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Divider(color=ft.colors.WHITE38, height=1),
                            expand=True
                        ),
                        ft.Container(
                            content=ft.Text("OR", color=ft.colors.WHITE70, size=12, weight=ft.FontWeight.BOLD),
                            margin=ft.margin.symmetric(horizontal=16)
                        ),
                        ft.Container(
                            content=ft.Divider(color=ft.colors.WHITE38, height=1),
                            expand=True
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    margin=ft.margin.only(bottom=15)
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.IconButton(
                                icon=ft.icons.FINGERPRINT,
                                icon_size=28,
                                icon_color=ft.colors.TEAL_600,
                                tooltip="Use biometric login",
                                on_click=self.biometric_login,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.colors.WHITE,
                                    shape=ft.CircleBorder(),
                                    padding=ft.padding.all(12),
                                    elevation=4,
                                    shadow_color=ft.colors.BLACK26,
                                    overlay_color=ft.colors.TEAL_50
                                )
                            ),
                            margin=ft.margin.only(right=12)
                        ),
                        ft.Text(
                            "Use biometric login",
                            size=14,
                            color=ft.colors.WHITE,
                            weight=ft.FontWeight.W_500
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    bgcolor=ft.colors.WHITE24,
                    border_radius=12,
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    border=ft.border.all(1, ft.colors.WHITE38)
                )
            ], spacing=0),
            margin=ft.margin.only(top=10)
        )

        # Status container with enhanced styling
        status_container = ft.Container(
            content=ft.Column([
                self.status_text,
                self.error_text
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            margin=ft.margin.only(top=15)
        )

        return ft.Container(
            content=ft.Column([
                    ft.Container(height=20),  # Top spacer
                    app_logo,
                    title_section,
                    ft.Container(height=35),  # Main spacer
                    email_container,
                    password_container,
                    sign_in_button,
                    secondary_actions,
                    biometric_section,
                    status_container,
                    self.user_info,
                    ft.Container(height=20)  # Bottom spacer
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                scroll=ft.ScrollMode.AUTO  # Add scrolling for smaller screens
                ),
                    padding=ft.padding.all(24),
                    gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=[
                        self.theme_color.auth_background_primary,
                        self.theme_color.auth_background_midle,
                        self.theme_color.auth_background_secondary
                    ],
                stops=[0.0, 0.5, 1.0]
            ),
            expand=True
        )

    def toggle_password_visibility(self, password_field, e):
        """Toggle password field visibility"""
        if password_field.password:
            password_field.password = False
            e.control.icon = ft.icons.VISIBILITY
        else:
            password_field.password = True
            e.control.icon = ft.icons.VISIBILITY_OFF
        self.page.update()

    def biometric_login(self, e):
        """Handle biometric authentication (if available)"""
        # Implementation depends on your platform capabilities
        # For now, show a message
        self.show_message("Biometric login not implemented yet", is_error=False)

    def show_message(self, message, is_error=True):
        """Display status messages to user"""
        self.status_text.value = message
        self.status_text.color = ft.colors.RED_400 if is_error else ft.colors.GREEN_400
        self.page.update()

        # Auto-clear message after 3 seconds
        import threading

        def clear_message():
            import time
            time.sleep(3)
            self.status_text.value = ""
            self.page.update()

        threading.Thread(target=clear_message, daemon=True).start()

    def create_styled_textfield(self, label, is_password=False):
        """Create a styled text field"""
        return ft.TextField(
            label=label,
            password=is_password,
            border=ft.InputBorder.NONE,
            label_style=ft.TextStyle(color=ft.colors.GREY_400),
            text_style=ft.TextStyle(color=ft.colors.WHITE),
            cursor_color=ft.colors.BLUE_400,
            selection_color=ft.colors.BLUE_200
        )

    def sign_in_clicked(self, email, password, e=None):
        """Handle sign in button click"""
        if not email or not password:
            print("no email or password")
            self.show_error("Please enter both email and password")
            return

        if not self.initialize_firebase():
            print("no connection to firebase")
            return

        try:
            result = self.firebase_auth.sign_in(email, password)

            if "error" in result:
                self.show_error(result["error"])
            else:
                self.current_user = result
                self.id_token = result["idToken"]
                self.refresh_token = result["refreshToken"]
                self.token_expiry = result["expiresIn"]
                self.user_id = result["localId"]
                self.display_name = result['displayName']
                self.remember_user = True
                self.auth_manager.save_user_session_preference(self.remember_user, id_token=self.id_token,
                                                               refresh_token= self.refresh_token,
                                                               user_id=self.user_id)

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
            self.db.collection('users').document(user_id).collection('settings').document(field).set({
                field: value
            }, merge=True)
        except Exception as e:
            print(f"Error updating {field}: {e}")

    def sign_up_clicked(self, email, password, e=None):
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
                self.refresh_token = result["refreshToken"]
                self.token_expiry = result["expiresIn"]
                self.user_id = result["localId"]

                self.create_user_profile(self.user_id, email)
                self.remember_user = True
                self.auth_manager.save_user_session_preference(self.remember_user, id_token=self.id_token,
                                                               refresh_token=self.refresh_token,
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
                self.firebase_auth = FirebaseAuth(self.API_KEY, self.SERVICE_ACCOUNT_PATH,)
                print("Firebase initialized successfully")
                return True
            except Exception as e:
                self.show_error(f"Firebase initialization error: {str(e)}")
                print(f"Firebase initialization failed: {e}")
                return False
        return True

    def setup_ui(self):
        """Set up the initial UI"""
        try:
            # Clear the page first
            self.page.clean()

            # Add the authentication view
            auth_view = self.create_auth_view()
            self.page.add(auth_view)
            self.page.update()


        except Exception as e:
            print(f"Error setting up UI: {e}")
            # Add a simple fallback UI
            self.page.add(ft.Text("Error loading app"))
            self.page.update()

    def show_main(self):
        self.page.clean()

        self.expenses_list = ft.ListView(spacing=10, padding=20, auto_scroll=False, height=500)
        self.wish_list = ft.ListView(spacing=10, padding=20, auto_scroll=False, height=300)
        self.analysis_list = ft.ListView(spacing=10, padding=20, auto_scroll=False, height=300)

        self.recurring_checkbox = ft.Checkbox(label="Recurring expenses", on_change=self.update_expenses_list)
        self.filter_category_options = [ft.dropdown.Option("All")]
        self.filter_category_options += self.show_expense_category()

        # Load initial data
        self.load_budget_data()
        self.load_expenses()
        self.load_wish_list()
        self.load_analysis_list()
        self.load_settings()
        if self.is_dark_mode:
            self.page.theme_mode = ft.ThemeMode.DARK
        else:
            self.page.theme_mode = ft.ThemeMode.LIGHT



        friends_ui = FriendsUI(self.page, self.user_id)

        # Create tabs
        self.overview_tab = self.create_overview_tab()
        self.expenses_tab = self.create_expenses_tab()
        self.charts_tab = self.create_charts_tab()
        self.wish_list_tab = self.create_wish_list_tab()

        self.tabs = ft.Tabs(
            selected_index=0,
            indicator_color=self.theme_color.teal_text_secondary,
            label_color=self.theme_color.teal_text_secondary,
            unselected_label_color=self.theme_color.text_secondary,
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
        advice_text = self.generate_themed_advice()

        advice_display = ft.Text(
            value=advice_text,
            size=14,
            color=self.theme_color.text_primary,
            text_align=ft.TextAlign.CENTER,
            weight=ft.FontWeight.W_500
        )

        # Budget summary
        self.budget_summary = ft.Container(
            content=ft.Column([
                ft.Text("Budget Summary", size=20, weight=ft.FontWeight.BOLD),
            ]),
            padding=10,
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
        self.upcoming_transactions = ft.Container(
                content=ft.Column([
                        ft.Row([
                            ft.Text("Upcoming Transactions", size=16, weight=ft.FontWeight.BOLD),
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
        self.create_upcoming_transactions_card()

        return ft.Container(
            content=ft.ListView([
                # Header with avatar and settings
                self.create_header_section(),

                # Motivational quote (moved to bottom, smaller)
                self.create_quote_section(),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ADD_CIRCLE, size=18, color=self.theme_color.text_primary),
                        ft.Text("Add Expense", size=12, weight=ft.FontWeight.W_600, color=self.theme_color.text_primary)
                    ], spacing=10),
                    padding=ft.padding.symmetric(horizontal=20, vertical=14),
                    bgcolor=self.theme_color.teal_card,
                    border_radius=12,
                    border=ft.border.all(1, ft.colors.TEAL_300),
                    on_click=self.show_add_expense_dialog,
                    ink=True,  # Adds ripple effect
                    # Add shadow for depth
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.colors.with_opacity(0.3, ft.colors.TEAL_600),
                        offset=ft.Offset(0, 3)
                    ), expand=True
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.CAMERA_ALT, size=18, color=self.theme_color.text_primary),
                        ft.Text("From Picture", size=12, weight=ft.FontWeight.W_600, color=self.theme_color.text_primary)
                    ], spacing=10),
                    padding=ft.padding.symmetric(horizontal=20, vertical=14),
                    bgcolor=self.theme_color.cyan_card,
                    border_radius=16,
                    border=ft.border.all(2, ft.colors.CYAN_600),
                    on_click=self.add_expense_from_picture_dialog,
                    ink=True,
                    # Add subtle shadow
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=6,
                        color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                        offset=ft.Offset(0, 2)
                    ),expand=True
                ),

                # Key metrics cards row
                self.budget_summary,

                # Budget progress card
                self.budget_progress_card,

                # Quick insights row (shared expenses + weekly trend)
                self.quick_insights_row,

                # Highest expenses card
                self.highest_expenses_card,
                self.upcoming_transactions,

            ], spacing=20, padding=ft.padding.all(0)),
            padding=ft.padding.all(20),
            bgcolor=self.theme_color.background,  # Light background for better contrast,

        )

    def create_header_section(self):
        return ft.Container(
            content=ft.Row([
                ft.Row([
                    self.main_avatar_container,
                    ft.Column([
                        ft.Text(f"Welcome back!", size=14, color=self.theme_color.text_primary),
                        ft.Text(f"{self.current_user['displayName']}", size=18, weight=ft.FontWeight.BOLD,
                                color=self.theme_color.text_primary),
                    ], spacing=0),
                ], spacing=12),
                ft.Row([
                    self.open_settings_menu()
                ], alignment=ft.MainAxisAlignment.END),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            margin=ft.margin.only(bottom=10)
        )

    def create_budget_progress_card(self):
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
                            color=self.theme_color.text_primary),
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
                        bgcolor=self.theme_color.progress_bar,
                        height=12,
                        border_radius=6
                    ),
                    # Add a subtle container around progress bar
                    padding=ft.padding.all(2),
                    bgcolor=self.theme_color.container_primary,
                    border_radius=8,
                ),

                ft.Container(height=12),

                ft.Row([
                    ft.Text(f"0 {self.currency}", size=12, color=self.theme_color.text_primary),
                    ft.Text(f"{budget_amount:.0f} {self.currency}", size=12, color=self.theme_color.text_primary),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Container(height=16),

                # Enhanced stats row with icons
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.icons.CALENDAR_TODAY, size=16, color=self.theme_color.text_primary),
                        ft.Text(f"Daily avg: {daily_average:.2f} {self.currency}",
                                size=13, color=self.theme_color.text_primary, weight=ft.FontWeight.W_500),
                    ], spacing=6),
                    ft.Row([
                        ft.Icon(ft.icons.SCHEDULE, size=16, color=self.theme_color.text_primary),
                        ft.Text(f"{days_remaining} days left",
                                size=13, color=self.theme_color.text_primary, weight=ft.FontWeight.W_500),
                    ], spacing=6),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=0),
            bgcolor=self.theme_color.teal_card,
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
        #owed_amount = self.get_owed_amount()
        weekly_change = self.get_weekly_spending_change()

        self.quick_insights_row.content = ft.Row([
            # Shared expenses card with improved design
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.PEOPLE_ALT, size=20, color=self.theme_color.logo_on_orange),
                        ft.Text("Shared", size=14, color=self.theme_color.text_primary,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8),
                    ft.Container(height=12),
                    self.update_shared_expenses()  # Your existing method
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                bgcolor=self.theme_color.orange_card,
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
                            color=self.theme_color.text_primary
                        ),
                        ft.Text("This Week", size=14, color=self.theme_color.text_primary,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8),
                    ft.Container(height=12),
                    ft.Text(
                        f"{'+' if weekly_change >= 0 else ''}{weekly_change:.2f} {self.currency}",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=self.theme_color.text_primary if weekly_change >= 0 else self.theme_color.text_primary
                    ),
                    ft.Text("vs last week", size=12, color=self.theme_color.text_primary),
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                bgcolor=self.theme_color.red_card if weekly_change >= 0 else self.theme_color.green_card,
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


    def create_highest_expenses_card(self):
        self.highest_expenses = self.get_highest_expenses_list()
        self.highest_expenses_card.content = ft.Container(
            content=ft.Column([
            # Better header design
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.BAR_CHART, size=24, color=self.theme_color.logo_primary),
                        bgcolor=self.theme_color.text_primary,
                        padding=8,
                        border_radius=8,
                    ),
                    ft.Text("Top Categories", size=18, weight=ft.FontWeight.BOLD,
                        color=self.theme_color.text_primary),
                ], spacing=12),

                ft.Container(height=16),

            # Your existing content method
            self.get_highest_expenses(),
            ], spacing=0),
            bgcolor=self.theme_color.purple_card,
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

    def create_upcoming_transactions_card(self):
        recurring_this_week = [expense for expense in self.recurring_expenses if
                               self.start_date < expense.get('recurring day') < self.end_date]
        amount =0
        transaction_rows = []
        for transaction in recurring_this_week:
            amount+=transaction['amount']
            transaction_rows.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(
                            self.get_category_icon(transaction['category']),
                            size=16,
                            color=ft.colors.TEAL_800
                        ),
                        ft.Text(transaction['category'], size=12, color=self.theme_color.text_primary),
                        ft.Column([
                            ft.Text(transaction['description'], size=14, weight=ft.FontWeight.BOLD),
                        ], spacing=0, expand=1),
                        ft.Text(f"-{transaction['amount']:.2f} {self.currency}", size=14, weight=ft.FontWeight.BOLD,
                                color=ft.colors.RED_600),
                    ], spacing=10),
                    bgcolor=self.theme_color.teal_card
                ))
        transaction_rows.append(ft.Container(
                    content=ft.Row([
                        ft.Row([
                        ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET,size=16,
                            color=ft.colors.TEAL_800),
                        ft.Text(f"Total: ", size=16, weight=ft.FontWeight.BOLD, color=self.theme_color.text_primary),
                        ]),
                        ft.Row([ft.Text(f"-{amount} {self.currency} ", size=16, weight=ft.FontWeight.BOLD,
                                color=ft.colors.RED_600)])
                    ],alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    bgcolor=self.theme_color.teal_card,
                ))

        self.upcoming_transactions.content = ft.Container(
            content=ft.Column([
                # Improved header with better spacing
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.RECEIPT_LONG, size=24, color=self.theme_color.logo_primary),
                        bgcolor=self.theme_color.auth_background_midle,
                        padding=8,
                        border_radius=8,
                    ),
                    ft.Text("Upcoming Transactions", size=18, weight=ft.FontWeight.BOLD,
                            color=ft.colors.TEAL_800),
                    ft.Container(
                        content=ft.ElevatedButton(
                            "View All",
                            on_click=lambda _: self.switch_to_expenses_tab(),
                            style=ft.ButtonStyle(
                                color=self.theme_color.logo_primary,
                                bgcolor=self.theme_color.auth_background_midle,
                            )
                        ),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Container(height=16),

                # Your existing transaction content
                ft.Column(transaction_rows, spacing=12) if transaction_rows else
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.RECEIPT_OUTLINED, size=48, color=self.theme_color.auth_background_primary),
                        ft.Text("No upcoming transactions", size=14, color=self.theme_color.auth_background_primary),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                    padding=ft.padding.all(24),
                    alignment=ft.alignment.center,
                ),
            ], spacing=0),
            bgcolor=self.theme_color.background,
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

    def create_quote_section(self):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.LIGHTBULB_OUTLINE, size=20, color=self.theme_color.text_primary),
                        bgcolor=self.theme_color.green_card,
                        padding=8,
                        border_radius=8,
                    ),
                    ft.Text("Daily Tip", size=16, weight=ft.FontWeight.BOLD,
                           color=self.theme_color.text_primary),
                ], spacing=12),

                ft.Container(height=12),

                ft.Text(
                    f"{self.generate_themed_advice()}",
                    size=13,
                    color=self.theme_color.text_primary,
                    text_align=ft.TextAlign.LEFT,
                    weight=ft.FontWeight.W_400
                ),
            ], spacing=0),
            bgcolor=self.theme_color.green_card,
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
        # Calculate based on total expenses and days in current period
        total_expenses = self.get_total_expenses()
        days_elapsed = self.get_days_elapsed_in_budget_period()
        return total_expenses / days_elapsed if days_elapsed > 0 else 0

    def get_days_remaining_in_budget_period(self):
        end_datetime = datetime.strptime(self.end_date, "%Y-%m-%d").date()  # Remove timezone info if present
        current_datetime = datetime.now().date()

        # Calculate the difference
        date_difference = end_datetime - current_datetime

        # Get the number of days
        days_between = date_difference.days
        # Calculate remaining days in budget period
        return days_between

    def get_days_elapsed_in_budget_period(self):
        # Calculate elapsed days in budget period
        start_datetime = datetime.strptime(self.start_date, "%Y-%m-%d").date()  # Remove timezone info if present
        current_datetime = datetime.now().date()

        # Calculate the difference
        date_difference = current_datetime - start_datetime

        # Get the number of days
        days_between = date_difference.days

        return days_between

    def get_weekly_spending_change(self):
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
            bgcolor=self.theme_color.yellow_card,
            data=0,
            on_click=self.get_ai_analysis,
        )
        self.analysis_status_text = ft.Text("", color=self.theme_color.text_secondary)

        self.category_filter = ft.Dropdown(
            label="Filter by Category",
            options=self.filter_category_options,
            value="All",
            width=200,
            bgcolor=self.theme_color.teal_card,
            border_color=ft.colors.TEAL_500,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_expenses_list
        )
        self.time_period_filter = ft.Dropdown(
            label="Filter by Period",
            options=self.filter_period_options,
            value="1M",
            width=200,
            bgcolor=self.theme_color.teal_card,
            border_color=ft.colors.TEAL_500,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_expenses_list
        )

        self.occurence_filter = ft.Dropdown(
            label="Filter by Occurrence",
            options=self.filter_ocurrence_options,
            value="All",
            width=200,
            bgcolor=self.theme_color.teal_card,
            border_color=ft.colors.TEAL_500,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_expenses_list
        )


        def create_selected_expense_tab(e):
            self.tab_content.controls.clear()

            if expense_tab_selector.selected_index == 0:
                content = create_expenses_list_tab()
            elif expense_tab_selector.selected_index == 1:
                content = create_ai_analysis_tab()
            else :
                content = self.create_charts_tab()

                # Add the new content
            self.tab_content.controls.append(content)
            self.tab_content.update()
            self.page.update()  # Change this line

        expense_tab_selector = ft.Tabs(is_secondary=True, selected_index=0,
                                on_change=create_selected_expense_tab,
                                indicator_color=self.theme_color.teal_text_secondary,
                                label_color=self.theme_color.teal_text_secondary,
                                unselected_label_color=self.theme_color.text_secondary,
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
                                ])

        self.page.overlay.append(self.recurring_date_picker)

        self.update_displays()

        def create_expenses_list_tab():
            return ft.Container(
                content=ft.Column([
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
            self.update_analysis_button_state()
            # Header section with icon and title
            header_section = ft.Container(
                content=ft.Row([
                    ft.Icon(
                        ft.icons.AUTO_AWESOME,
                        color=self.theme_color.teal_text_secondary,
                        size=32
                    ),
                    ft.Column([
                        ft.Text(
                            "AI Insights",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            color=self.theme_color.teal_text_secondary,
                            font_family='Arial'
                        ),
                        ft.Text(
                            "Smart analysis of your spending patterns",
                            size=14,
                            color=self.theme_color.teal_text_secondary,
                            font_family='Arial'
                        )
                    ], spacing=2, expand=True)
                ], alignment=ft.MainAxisAlignment.START),
                padding=ft.padding.all(20),
                bgcolor=self.theme_color.background,
                border_radius=16,
                margin=ft.margin.only(bottom=16)
            )

            info_card = ft.Container(
                content=ft.Row([
                    ft.Icon(
                        ft.icons.INFO_OUTLINE,
                        color=self.theme_color.text_primary,
                        size=20
                    ),
                    ft.Text(
                        "Analysis updates every 2 weeks based on your recent expenses to provide "
                        "meaningful insights and time for implementing suggestions.",
                        size=14,
                        color=self.theme_color.text_primary,
                        font_family='Arial',
                        expand=True
                    )
                ], spacing=12),
                padding=ft.padding.all(16),
                bgcolor=self.theme_color.teal_card,
                border_radius=12,
                border=ft.border.all(1, ft.colors.TEAL_200),
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
                self.analysis_button.bgcolor = self.theme_color.progress_bar
                self.analysis_status_text.value = f"Next analysis available in {days_remaining} days"
            else:
                self.analysis_button.disabled = False
                self.analysis_button.text = "Generate AI Analysis"
                self.analysis_button.bgcolor = self.theme_color.yellow_card
                self.analysis_status_text.value = ""
        except ValueError:
            print(f"Invalid date format: {latest_date_str}")
            self.analysis_button.disabled = False
            self.analysis_button.text = "Generate AI Analysis"
            self.analysis_status_text.value = ""

        if hasattr(self, 'page'):
            self.page.update()

    def create_wish_list_tab(self):
        period_options = ["1M", "2M", "3M", "6M", "12M", "All"]
        filter_period_options = []
        for option in period_options:
            filter_period_options.append(ft.dropdown.Option(option))

        self.wish_period_filter = ft.Dropdown(
            label="Filter by Period",
            options=filter_period_options,
            value="1M",
            width=200,
            bgcolor=self.theme_color.purple_card,
            border_color=ft.colors.PURPLE_300,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_wish_list
        )

        self.update_wish_list()

        return ft.Container(
            content=ft.Column([
                # Header section with greeting and tip
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.LIGHTBULB_OUTLINE, color=self.theme_color.text_primary, size=24),
                            ft.Text("Daily Tip", size=16, weight=ft.FontWeight.W_500, color=self.theme_color.text_secondary)
                        ]),
                        ft.Text(
                            "Adding products to a wish list instead of buying them can help you spend your money more wisely and avoid impulse purchases.",
                            size=14,
                            color=self.theme_color.text_secondary,
                            text_align=ft.TextAlign.LEFT
                        )
                    ], spacing=8),
                    bgcolor=self.theme_color.purple_card,
                    border_radius=12,
                    padding=16,
                    margin=ft.margin.only(bottom=20)
                ),

                # Action buttons section
                ft.Container(
                    content=ft.Column([
                        ft.ElevatedButton(
                            content=ft.Row([
                                ft.Icon(ft.icons.ADD, color=self.theme_color.text_secondary),
                                ft.Text("Add Item", color=self.theme_color.text_secondary, weight=ft.FontWeight.W_500)
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                            bgcolor=self.theme_color.purple_card,
                            color=self.theme_color.text_secondary,
                            height=50,
                            width=float('inf'),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=12),
                                elevation=2
                            ),
                            on_click=self.show_add_wish_dialog
                        ),
                    ], spacing=12),
                    margin=ft.margin.only(bottom=20)
                ),

                # Filter section
                ft.Container(
                    content=self.wish_period_filter,
                    margin=ft.margin.only(bottom=16)
                ),

                # Wish list items
                self.wish_list,
            ], spacing=0),
            padding=20,
            expand=True,
            bgcolor=self.theme_color.background
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

    def get_reference_date(self, period):
        reference_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if period == "1M":
            reference_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        elif period == "2M":
            reference_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
        elif period == "3M":
            reference_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
        elif period == "6M":
            reference_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
        elif period == "12M":
            reference_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            reference_date = (datetime.now() - timedelta(days=1000)).strftime("%Y-%m-%d %H:%M:%S")

        return reference_date

    def get_expenses_selected_by_date(self, period):
        expense_categories = {}
        reference_date = self.get_reference_date(period)

        for expense in self.expenses:
            if expense['date'] > reference_date:
                if expense['category'] in expense_categories:
                    expense_categories[expense['category']] += expense['amount']
                else:
                    expense_categories[expense['category']] = expense['amount']
        return expense_categories

    def get_expenses_by_date_and_category(self, period):
        """Get expenses grouped by date and category for line chart"""
        reference_date = datetime.strptime(self.get_reference_date(period), "%Y-%m-%d %H:%M:%S")

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

    def update_chart_view(self, e=None):
        chart_filter = self.charts_filter.value
        period = self.charts_period_filter.value
        if chart_filter == "Pie Chart":
            self.update_pie_chart(period)
            self.chart_container.content = self.pie_chart
        elif chart_filter == "Bar Chart":
            self.update_bar_chart(period)
            self.chart_container.content = self.bar_chart
        else:
            self.update_line_chart(period)
            self.chart_container.content = self.line_chart

        # Update the container if it's on the page
        if hasattr(self.chart_container, 'page') and self.chart_container.page:
            self.chart_container.update()

    def create_pie_sections(self, period='1M'):
        expense_categories = self.get_expenses_selected_by_date(period)
        category_colors = self.get_category_colors()

        total_amount = sum(expense_categories.values())

        pie_sections = [ft.PieChartSection(
            value=amount,
            title=f"{category}\n{(amount / total_amount) * 100:.1f}%",
            radius=100,
            color=category_colors.get(category, ft.colors.GREY_500)
        )
            for category, amount in expense_categories.items()
        ]
        return pie_sections

    def create_bars(self, period='1M'):
        expense_categories = self.get_expenses_selected_by_date(period)
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

    def create_line_chart_data(self, period='1M'):
        expenses_by_category_date, sorted_dates = self.get_expenses_by_date_and_category(period)
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

    def update_pie_chart(self, period='1M',  e=None):

        # Update pie chart sections
        self.pie_chart.sections = self.create_pie_sections(period)

        # Update the chart if it's on the page
        if hasattr(self.pie_chart, 'page') and self.pie_chart.page:
            self.pie_chart.update()

    def update_bar_chart(self, period='1M', e=None):

        # Update bar chart data
        bars = self.create_bars(period)
        self.bar_chart.bar_groups = bars

        # Update max_y based on new data
        if bars:
            max_y = max([max([rod.to_y for rod in group.bar_rods]) for group in bars]) * 1.1
            self.bar_chart.max_y = max_y

        # Update the chart if it's on the page
        if hasattr(self.bar_chart, 'page') and self.bar_chart.page:
            self.bar_chart.update()

    def update_line_chart(self, period='1M', e=None):
        # Update line chart data
        line_chart_data = self.create_line_chart_data(period)
        self.line_chart.data_series = line_chart_data

        # Update max_y based on new data
        expenses_by_category_date, sorted_dates = self.get_expenses_by_date_and_category(self.charts_period_filter.value)
        if expenses_by_category_date:
            all_amounts = []
            for category_data in expenses_by_category_date.values():
                all_amounts.extend(category_data.values())
            if all_amounts:
                max_y = max(all_amounts) * 1.1
                self.line_chart.max_y = max_y

        # Update the chart if it's on the page
        if hasattr(self.line_chart, 'page') and self.line_chart.page:
            self.line_chart.update()

    def create_charts_tab(self):

        chart_options = [ft.dropdown.Option("Pie Chart"), ft.dropdown.Option("Bar Chart"),
                         ft.dropdown.Option("Line Chart")]

        self.charts_filter = ft.Dropdown(
            label="Filter by Category",
            options=chart_options,
            value="Pie Chart",
            width=200,
            bgcolor=self.theme_color.teal_card,
            border_color=ft.colors.TEAL_300,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_chart_view
        )

        self.charts_period_filter = ft.Dropdown(
            label="Filter by Period",
            options=self.filter_period_options,
            value="1M",
            width=200,
            bgcolor=self.theme_color.teal_card,
            border_color=ft.colors.TEAL_300,
            border_radius=12,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_change=self.update_chart_view
        )

        period = self.charts_period_filter.value

        # Create initial charts
        self.pie_chart = ft.PieChart(
            sections=self.create_pie_sections(),
            sections_space=0.1,
            center_space_radius=20,
        )

        bars = self.create_bars()
        max_y_bar = max([max([rod.to_y for rod in group.bar_rods]) for group in bars], default=100) * 1.1

        self.bar_chart = ft.BarChart(
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

        line_chart_data = self.create_line_chart_data()
        expenses_by_category_date, sorted_dates = self.get_expenses_by_date_and_category(period)

        # Calculate max_y from all categories
        max_y_line = 100  # default
        if expenses_by_category_date:
            all_amounts = []
            for category_data in expenses_by_category_date.values():
                all_amounts.extend(category_data.values())
            if all_amounts:
                max_y_line = max(all_amounts) * 1.1

        self.line_chart = ft.LineChart(
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


        # Create a container to hold the current view
        self.chart_container = ft.Container(content=self.pie_chart)

        return ft.Container(
            ft.Column([
                ft.Row([
                    self.charts_filter,
                    self.charts_period_filter
                ]),
                self.chart_container
            ])
        )

    def get_highest_expenses(self):
        if not self.highest_expenses:
            return ft.Column([ft.Text("No expenses recorded yet")])

        expenses_to_show = self.highest_expenses[:3]

        expense_controls = [
            ft.Text("Highest Expenses:", weight=ft.FontWeight.BOLD, color=self.theme_color.text_primary)
        ]
        for expense in expenses_to_show:
            expense_controls.append(
                ft.Row([ft.Icon(self.get_category_icon(expense[0]), color=self.theme_color.text_primary),
                ft.Text(f" {expense[0]}: {expense[1]:.2f}"
                        f" {self.currency}", color=self.theme_color.text_primary)
                ] , spacing=5)
            )

        return ft.Column(expense_controls, spacing=5)

    def get_upcoming_transactions(self, expense_list = None):
        if not expense_list:
            return ft.Column([ft.Text("No recurring transactions scheduled for the next period.")])
        transactions_controls = [
            ft.Text("Upcoming Transactions:", weight=ft.FontWeight.BOLD, color=ft.colors.TEAL_800)
        ]

        for i, expense in enumerate(expense_list, 1):
            transactions_controls.append(
                ft.Text(f"{i}. {expense[0]}: ${expense[1]:.2f}")
            )

        return ft.Column(transactions_controls, spacing=5)


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
        for expense in self.recurring_expenses:
            try:
                if type(expense['recurring day']) is not str:
                    expense['recurring day'] = expense['recurring day'].strftime('%Y-%m-%d %H:%M:%S')
                if expense['recurring day'] <= datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
                    months = self.get_recurring_period(expense['is recurring'])
                    new_date = expense['recurring day'] + relativedelta(months=months)
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
                        doc_ref = self.db.collection('expenses').document(expense['id'])
                        doc_ref.update({'recurring day': new_date.strftime('%Y-%m-%d %H:%M:%S')})
                    else:
                        # Generate a temporary ID for local storage
                        expense_data['id'] = f"local_{len(self.expenses)}"

                    self.expenses.append(expense_data)
                    self.update_budget_summary()
                    self.page.update()
                    self.show_snackbar("Expense added successfully!")
            except Exception as e:
                print(e)

    def add_expense_from_wish_list(self, wish_id):
        "Moves entry from wish list to expense list"
        try:
            wish_to_expense = next((wish for wish in self.wishes if wish_id == wish.get('id')))
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

            if not self.db:
                db = firestore.client()
            # Save to Firebase if available
            if self.db:
                doc_ref = self.db.collection('users').document(self.user_id).collection('expenses').add(expense_data)
                expense_data['id'] = wish_to_expense['id']
                doc_ref = self.db.collection('expenses').document(wish_to_expense['id'])

                self.db.collection('wish_list').document(wish_id).delete()

                # Remove from local data
                self.wishes = [wish for wish in self.wishes if wish.get('id') != wish_id]
            else:
                # Generate a temporary ID for local storage
                expense_data['id'] = f"local_{len(self.expenses)}"

            self.expenses.append(expense_data)
            self.update_wish_list()
            self.update_expenses_list()
            self.update_budget_summary()
            self.page.update()
            self.show_snackbar("Expense added successfully!")

        except Exception as e:
            print(e)
    def create_expense_item(self, expense):
        category = expense.get('category', '')
        category_colors = self.get_category_colors()
        category_color = category_colors.get(category, ft.colors.BLUE_300)


        category_badge = ft.Container(
            content=ft.Row([
                ft.Icon(self.get_category_icon(category), color=category_color),
                ft.Text(category, size=12, weight=ft.FontWeight.W_500, color=category_color),
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                bgcolor=self.theme_color.teal_card,
                border_radius=20,
            )

        recurring_badge = None
        if expense["is recurring"] != 'No':
            recurring_badge = ft.Container(
                content=ft.Text(
                    expense["is recurring"],
                    size=11,
                    weight=ft.FontWeight.W_500,
                    color=self.theme_color.text_secondary
                ),
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                bgcolor=self.theme_color.orange_card,
                border_radius=12,
            )
        shared_badge = None
        if expense['shared'] != "No":
            shared_sum = float(expense['amount']) * float(expense['percentage']) * 0.01
            shared_badge = ft.Container(
                content=ft.Row([
                    ft.Text(
                        f"You owe {str(shared_sum)} {self.currency} to" if expense['owe status'] == "I owe the expense"
                        else f"You are owed {str(shared_sum)} {self.currency} by",
                        size=11,
                        weight=ft.FontWeight.W_500,
                        color=ft.colors.RED_400 if expense['owe status']=="I owe the expense" else ft.colors.GREEN_400
                    ),
                ft.Text(
                    expense["shared"],
                    size=11,
                    weight=ft.FontWeight.W_500,
                    color=ft.colors.RED_400 if expense['owe status']=="I owe the expense" else ft.colors.GREEN_400
                ),
                ], alignment=ft.alignment.center),
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                bgcolor=self.theme_color.pink_card if expense['owe status']=="I owe the expense" else
                self.theme_color.green_card,
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
                            color=self.theme_color.text_primary
                        ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        category_badge
                    ], spacing=4, expand=True),
                    ft.Column([
                        ft.Row([
                            ft.IconButton(
                                icon=ft.icons.EDIT,
                                icon_color=self.theme_color.teal_text_secondary,
                                on_click=lambda e, exp_id=expense.get('id'): self.show_edit_expense_dialog(exp_id)
                            ),
                            ft.IconButton(
                                icon=ft.icons.DELETE,
                                icon_color=ft.colors.RED,
                                on_click=lambda e, exp_id=expense.get('id'): self.delete_expense(exp_id)
                            )
                        ], ),
                    ft.Text(
                        f"{expense['amount']:.2f} {self.currency}",
                        size=18,
                        weight=ft.FontWeight.W_700,
                        color=self.theme_color.text_primary
                    )
                        ]),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                # Meta row
                ft.Row([
                    ft.Container(
                        content=ft.Text(
                            expense["date"],
                            size=12,
                            color=self.theme_color.text_secondary
                        ), width=200),
                    ft.Container(
                        content=shared_badge if shared_badge else ft.Container(),
                        width=300,
                        alignment=ft.alignment.center
                    ),
                    ft.Container(
                        content=recurring_badge if recurring_badge else ft.Container(),
                        width=100,
                        alignment=ft.alignment.center
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=12),
            padding=ft.padding.all(20),
            margin=ft.margin.only(bottom=16),
            bgcolor=self.theme_color.background,
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
                expense_card = self.create_expense_item(expense)
                self.expenses_list.controls.append(expense_card)

        self.page.update()

    def update_wish_list(self, e=None):
        """Update the wish list display"""
        self.wish_list.controls.clear()
        filtered_wishes = self.wishes

        if not self.wishes:
            self.expenses_list.controls.append(
                ft.Text("No Wishes recorded yet.", color=self.theme_color.text_primary)
            )
        else:
            if self.wish_period_filter.value:
                selected_period = self.wish_period_filter.value
            else:
                selected_period = "1M"
            if selected_period == "1M":
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")]
            elif selected_period == "2M":
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")]

            elif selected_period == "3M":
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")]

            elif selected_period == "6M":
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")]

            elif selected_period == "12M":
                filtered_wishes = [wish for wish in self.wishes if wish['date'] >=
                                   (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")]

            for wish in reversed(filtered_wishes):
                category = wish.get('category', '')
                category_colors = self.get_category_colors()
                category_color = category_colors.get(category, self.theme_color.logo_in_blue)

                category_badge = ft.Container(
                    content=ft.Row([
                        ft.Icon(self.get_category_icon(category), color=category_color),
                        ft.Text(category, size=12, weight=ft.FontWeight.W_500, color=category_color),
                    ], spacing=8),
                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                    bgcolor=self.theme_color.purple_card,
                    border_radius=20,
                )
                wish_card = ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                # Header row
                                ft.Row([
                                    ft.Column([
                                        ft.Row([
                                            ft.Text(
                                                wish["description"],
                                                size=16,
                                                weight=ft.FontWeight.W_600,
                                                color=self.theme_color.text_primary
                                                ),
                                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                        category_badge
                                    ], spacing=4, expand=True),
                                ft.Column([
                                    ft.Row([
							            ft.ElevatedButton(text="Acquired this",
                                                          color=self.theme_color.text_secondary,
                                                            style=ft.ButtonStyle(
                                                            shape=ft.RoundedRectangleBorder(radius=10),
                                                            ),
                                                            bgcolor=self.theme_color.purple_card,
                                                            on_click=lambda e, wish_id=wish.get(
                                                          'id'): self.add_expense_from_wish_list(wish_id)),
                            ft.IconButton(
                                icon=ft.icons.EDIT,
                                icon_color=self.theme_color.purple_text,
                                on_click=lambda e, wish_id=wish.get('id'): self.show_edit_wish_dialog(wish_id)
                            ),
                            ft.IconButton(
                                icon=ft.icons.DELETE,
                                icon_color=ft.colors.RED,
                                on_click=lambda e, wish_id=wish.get('id'): self.delete_expense(wish_id)
                            )
                        ], ),
                    ft.Text(
                        f"{wish['amount']:.2f} {self.currency}",
                        size=18,
                        weight=ft.FontWeight.W_700,
                        color=self.theme_color.text_primary
                    )
                        ]),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                # Meta row
                ft.Row([
                    ft.Container(
                        content=ft.Text(
                            wish["date"],
                            size=12,
                            color=self.theme_color.text_secondary
                        ), width=200),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=12),
                    padding=ft.padding.all(20),
                    margin=ft.margin.only(bottom=16),
                    bgcolor=self.theme_color.background,
                    border_radius=16,
                    border=ft.border.all(1, ft.colors.GREY_100),
                    shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                offset=ft.Offset(0, 2)
            ),
        ) )

                self.wish_list.controls.append(wish_card)

        self.page.update()

    def update_analysis_list(self, e=None):
        self.analysis_list.controls.clear()

        if not self.analysis:
            # Empty state card
            empty_state = ft.Container(
                content=ft.Column([
                    ft.Icon(
                        ft.icons.INSIGHTS,
                        size=64,
                        color=self.theme_color.progress_bar
                    ),
                    ft.Text(
                        "No Analysis Yet",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=self.theme_color.text_primary,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Generate your first AI analysis to get personalized insights about your spending habits.",
                        size=14,
                        color=self.theme_color.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(40),
                bgcolor=self.theme_color.background,
                border_radius=16,
                border=ft.border.all(1, ft.colors.GREY_200),
                alignment=ft.alignment.center
            )
            self.analysis_list.controls.append(empty_state)
        else:
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
                bg_color, accent_color = (self.theme_color.teal_card, ft.colors.TEAL_400)

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
                                color=self.theme_color.text_primary,
                                expand=True
                            ),
                            ft.Text(
                                date_text,
                                size=12,
                                color=self.theme_color.text_secondary
                            ) if date_text else ft.Container()
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                        ft.Divider(color=self.theme_color.progress_bar, height=1),

                        # Analysis content
                        ft.Container(
                            content=ft.Text(
                                analysis_text,
                                size=14,
                                color=self.theme_color.text_primary,
                                selectable=True,
                                font_family='Arial'
                            ),
                            padding=ft.padding.only(top=8)
                        )
                    ], spacing=12),
                    padding=ft.padding.all(20),
                    bgcolor=bg_color,
                    border_radius=16,
                    border=ft.border.all(1, ft.colors.TEAL_200),
                    margin=ft.margin.only(bottom=12)
                )
                self.analysis_list.controls.append(analysis_card)

        self.update_analysis_button_state()
        self.page.update()

    def get_ai_analysis(self, e=None):
        benchmark_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        expenses = [expense for expense in self.expenses if expense['date'] > benchmark_date]
        # Check if there are expenses to analyze
        if not expenses:
            print("No expenses found for analysis")
            return
        generated_analysis = self.ai_analyst.analyze_expenses_with_ai(expenses, self.id_token)

        def save_analysis():
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
                return True
            except Exception as e:
                print(f"❌ Error saving analysis entries: {e}")
                return False

        # Save and update display
        if save_analysis():
            self.update_analysis_list()
            self.update_displays()

    def show_configure_budget_dialog(self, e):
        """Show dialog to configure budget"""
        self.budget_input = ft.TextField(
            label="Budget Amount",
            value=str(self.budget_amount),
            width=280,
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.icons.ACCOUNT_BALANCE_WALLET,
            border_radius=12,
            filled=True,
            bgcolor=self.theme_color.blue_card,
            border_color=ft.colors.BLUE_200,
            focused_border_color=ft.colors.BLUE_600,
            label_style=ft.TextStyle(color=self.theme_color.text_primary),
            text_style=ft.TextStyle(size=16)
        )

        self.currency_input = ft.TextField(
            label="Currency",
            value=self.currency if hasattr(self, 'currency') and self.currency else '$',
            width=280,
            prefix_icon=ft.icons.ATTACH_MONEY,
            border_radius=12,
            filled=True,
            bgcolor=self.theme_color.blue_card,
            border_color=ft.colors.BLUE_200,
            focused_border_color=ft.colors.BLUE_600,
            label_style=ft.TextStyle(color=ft.colors.GREY_700),
            text_style=ft.TextStyle(size=16)
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

        self.start_date_button = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.CALENDAR_TODAY, size=20, color=self.theme_color.text_primary),
                ft.Column([
                    ft.Text("Start Date", size=12, color=self.theme_color.text_secondary),
                    ft.Text(f"{self.start_date}", size=16, weight=ft.FontWeight.W_500, color=self.theme_color.text_primary)
                ], spacing=2, alignment=ft.MainAxisAlignment.CENTER)
            ], spacing=12, alignment=ft.MainAxisAlignment.START),
            on_click=lambda _: self.start_date_picker.pick_date(),
            bgcolor=self.theme_color.background,
            border=ft.border.all(1, ft.colors.BLUE_200),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            width=280,
            ink=True
        )

        self.end_date_button = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.CALENDAR_TODAY, size=20, color=self.theme_color.text_primary),
                ft.Column([
                    ft.Text("End Date", size=12, color=self.theme_color.text_secondary),
                    ft.Text(f"{self.end_date}", size=16, weight=ft.FontWeight.W_500, color=self.theme_color.text_primary)
                ], spacing=2, alignment=ft.MainAxisAlignment.CENTER)
            ], spacing=12, alignment=ft.MainAxisAlignment.START),
            on_click=lambda _: self.end_date_picker.pick_date(),
            bgcolor=self.theme_color.background,
            border=ft.border.all(1, ft.colors.BLUE_200),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            width=280,
            ink=True
        )

        self.budget_form_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.TUNE, size=24, color=self.theme_color.text_primary),
                ft.Text("Configure Budget", size=20, weight=ft.FontWeight.W_600, color=self.theme_color.text_primary)
            ], spacing=12),
            content=ft.Container(
                content=ft.Column([
                    ft.Container(height=8),
                    self.budget_input,
                    ft.Container(height=16),
                    self.currency_input,
                    ft.Container(height=16),
                    self.start_date_button,
                    ft.Container(height=12),
                    self.end_date_button,
                    ft.Container(height=8),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                width=320,
                padding=ft.padding.symmetric(horizontal=8, vertical=4)
            ),
            actions=[
                ft.Row([
                    ft.TextButton(
                        text="Cancel",
                        on_click=lambda e: self.close_budget_dialog(),
                        style=ft.ButtonStyle(
                            color=self.theme_color.text_primary,
                        )
                    ),
                    ft.ElevatedButton(
                        text="Save Budget",
                        on_click=self.save_budget,
                        style=ft.ButtonStyle(
                            bgcolor=self.theme_color.blue_card,
                            color=self.theme_color.text_primary,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=24, vertical=12)
                        ),
                        icon=ft.icons.SAVE
                    )
                ], alignment=ft.MainAxisAlignment.END, spacing=12)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=self.theme_color.background,
            shadow_color=ft.colors.with_opacity(0.3, ft.colors.BLACK)
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
            bgcolor=self.theme_color.blue_card,
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
                bgcolor=self.theme_color.orange_card,
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
                bgcolor=self.theme_color.green_card,
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
                    bgcolor=self.theme_color.purple_card,
                    border_color=ft.colors.PURPLE_200,
                    focused_border_color=ft.colors.PURPLE_400,
                )

        friends = self.get_friend_data()
        share_with_options = [ft.dropdown.Option("No")] + [ft.dropdown.Option(friend) for friend in friends.keys()]

        share_with_input = ft.Dropdown(
                    options=share_with_options,
                    value='No',
                    border_radius=12,
                    bgcolor=self.theme_color.cyan_card,
                    border_color=ft.colors.CYAN_200,
                    focused_border_color=ft.colors.CYAN_400,
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
        )

        owner_options = [ft.dropdown.Option("I owe the expense"), ft.dropdown.Option("Owes the expense")]
        owner_input = ft.Dropdown(
                    options=owner_options,
                    value="I owe the expense",
                    label="Who owes Who",
                    border_radius=12,
                    bgcolor=self.theme_color.cyan_card,
                    border_color=ft.colors.CYAN_200,
                    focused_border_color=ft.colors.CYAN_400,
                )

        share_with = ft.Container(
            content=ft.Column([
                ft.Text("Share With", weight=ft.FontWeight.W_500, size=14),
                share_with_input,
                percentage,
                owner_input
            ], spacing=8),
            bgcolor=self.theme_color.text_logo,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
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
                bgcolor=self.theme_color.purple_card,
                color=self.theme_color.text_secondary,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.padding.all(15)
                )
            ),
            margin=ft.margin.only(bottom=20)
        )

        recurring_period = ft.Container(
            content=ft.Column([
                ft.Text("Recurring Period", weight=ft.FontWeight.W_500, size=14),
                recurring_period_input,
                self.recurring_date_button
            ], spacing=8),
            bgcolor=self.theme_color.text_logo,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
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

                    if shared != "No":
                        if owe_status == "I owe the expense":
                            friend_owe_status = "Owes expense"
                        else:
                            friend_owe_status = "I owe the expense"
                        print(type(percentage.end_value))
                        friend_expense_data = {
                            'user id': self.user_id,
                            'amount': amount,
                            'category': category,
                            'description': description,
                            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'timestamp': datetime.now(),
                            'shared': self.current_user['displayName'],
                            'owe status': friend_owe_status,
                            'percentage': str(100 - float(percentage.end_value)),
                            'is recurring': is_recurring,
                            'recurring day': recurring_day
                        }
                        friend_doc_ref = self.db.collection('users').document(friend_data[shared]).collection(
                            'expenses').document(expense_data['id'])
                        friend_doc_ref.set(friend_expense_data)

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
                self.create_upcoming_transactions_card()
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
                ft.Icon(ft.icons.ADD_CIRCLE_OUTLINE, color=self.theme_color.text_primary, size=24),
                ft.Text("Add New Expense", weight=ft.FontWeight.BOLD, size=20, color=self.theme_color.text_primary)
            ], spacing=10),
                padding=ft.padding.only(bottom=10)
            ),
            content=ft.Container(
                content=ft.Column([
                    amount_field,
                    category_field,
                    description_field,
                    share_with,
                    recurring_period,

                ], spacing=0, scroll=ft.ScrollMode.AUTO),
                height=600,
                width=400,
                padding=20,
                bgcolor=self.theme_color.background,
                border_radius=15
            ),
            actions=[
                ft.Container(
                    content=ft.Row([
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda e: self.close_expense_dialog(),
                            style=ft.ButtonStyle(
                                color=self.theme_color.text_secondary,
                                bgcolor=self.theme_color.background,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.padding.symmetric(horizontal=20, vertical=10)
                            )
                        ),
                        ft.ElevatedButton(
                            "Save Expense",
                            on_click=save_expense,
                            icon=ft.icons.SAVE,
                            bgcolor=self.theme_color.green_card,
                            color=self.theme_color.text_secondary,
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
            bgcolor=self.theme_color.background,
            shape=ft.RoundedRectangleBorder(radius=20),
            adaptive=True
        )

        self.page.overlay.append(self.recurring_date_picker)

        self.page.dialog = self.expense_form_dialog
        self.expense_form_dialog.open = True
        self.page.update()

    def create_upload_picture_button(self):
        """Create the upload picture button with mobile camera/gallery options"""
        self.file_picker = ft.FilePicker(
            on_result=self.on_file_picked
        )

        # Create components that need to be updated later
        self.upload_status_text = ft.Text("No image selected", size=12, color=self.theme_color.text_secondary)
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
                        bgcolor=self.theme_color.green_card,
                        color=self.theme_color.text_secondary,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=20, vertical=12)
                        ),
                        expand=True
                    ),
                    ft.ElevatedButton(
                        text="Gallery",
                        icon=ft.icons.PHOTO_LIBRARY,
                        on_click=self.pick_from_gallery,
                        bgcolor=self.theme_color.green_card,
                        color=self.theme_color.text_secondary,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=20, vertical=12)
                        ),
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

    def create_expense_data_from_image(self, shared, owe_status, percentage, is_recurring='No',
                                       recurring_day=None):
        """Create expense data from processed image"""
        if not self.uploaded_image:
            return None

        # Encode image to base64
        image_base64 = self.encode_image_to_base64(self.uploaded_image.path)
        if not image_base64:
            return None

        # Process image with Anthropic
        extracted_data = self.ai_analyst.process_image_with_anthropic(self.id_token, image_base64)

        # Create expense data structure
        expense_data = {
            'user id': self.user_id,
            'amount': float(extracted_data.get('amount', 0.0)),
            'category': extracted_data.get('category', 'miscellaneous'),
            'description': extracted_data.get('description', 'Expense from image'),
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
        """Show dialog to add new expense"""
        upload_picture_button, file_picker = self.create_upload_picture_button()
        # Add file picker to page overlay
        self.page.overlay.append(file_picker)
        friends = self.get_friend_data()
        share_with_options = [ft.dropdown.Option("No")] + [ft.dropdown.Option(friend) for friend in friends.keys()]

        share_with_input = ft.Dropdown(
            options=share_with_options,
            value='No',
            border_radius=12,
            bgcolor=self.theme_color.cyan_card,
            border_color=ft.colors.CYAN_200,
            focused_border_color=ft.colors.CYAN_400,
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
            bgcolor=self.theme_color.text_logo,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
        )

        owner_options = [ft.dropdown.Option("I owe the expense"), ft.dropdown.Option("Owes the expense")]
        owner_input = ft.Dropdown(
            options=owner_options,
            value="I owe the expense",
            label="Who owes Who",
            border_radius=12,
            bgcolor=self.theme_color.cyan_card,
            border_color=ft.colors.CYAN_200,
            focused_border_color=ft.colors.CYAN_400,
        )

        share_with = ft.Container(
            content=ft.Column([
                ft.Text("Share With", weight=ft.FontWeight.W_500, size=14),
                share_with_input,
                percentage,
                owner_input
            ], spacing=8),
            bgcolor=self.theme_color.text_logo,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
        )



        def save_expense_from_picture(e):
            try:
                expense_data = self.create_expense_data_from_image(share_with_input.value,
                                                                   owner_input.value, percentage.end_value)

                friend_data = self.get_friend_data()

                if not self.db:
                    self.db = firestore.client()
                # Save to Firebase if available
                if self.db:
                    # Add user ID to ensure data isolation
                    doc_ref = self.db.collection('users').document(self.user_id).collection('expenses').add(
                        expense_data)
                    expense_data['id'] = doc_ref[1].id

                    if share_with_input.value != "No":
                        doc_ref = self.db.collection('users').document(friend_data[share_with_input.value]).\
                            collection('expenses').add(
                            expense_data)
                        expense_data['id'] = doc_ref[1].id

                else:
                    # Generate a temporary ID for local storage
                    expense_data['id'] = f"local_{len(self.expenses)}"

                self.expenses.insert(0,expense_data)
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

        self.expense_from_picture_dialog =  ft.AlertDialog(
    modal=True,
    title=ft.Text("Add New Expense", color=self.theme_color.text_primary),
    content=ft.Container(
        content=ft.ListView([  # Changed back to ListView
            upload_picture_button,
            share_with,
            percentage_display,
        ], spacing=10, padding=ft.padding.only(bottom=20)),  # Added bottom padding
        height=350,  # Reduced height to leave room for actions
        width=300,
        padding=10
    ),
    actions=[
        ft.TextButton(
            "Cancel",
            on_click=lambda e: self.close_dialog(self.expense_from_picture_dialog),
            style=ft.ButtonStyle(
                color=self.theme_color.text_secondary,
                bgcolor=self.theme_color.background,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=20, vertical=10)
            )
        ),
        ft.ElevatedButton(
            "Save Expense",
            on_click=save_expense_from_picture,
            icon=ft.icons.SAVE,
            bgcolor=self.theme_color.green_card,
            color=self.theme_color.text_secondary,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=20, vertical=12)
            )
        )
    ],
    actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    bgcolor=self.theme_color.background,
    shape=ft.RoundedRectangleBorder(radius=20),
    adaptive=True
)
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
            bgcolor=self.theme_color.blue_card,
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
            bgcolor=self.theme_color.orange_card,
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
            bgcolor=self.theme_color.green_card,
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
            bgcolor=self.theme_color.purple_card,
            border_color=ft.colors.PURPLE_200,
            focused_border_color=ft.colors.PURPLE_400,
        )

        friends = self.get_friend_data()
        share_with_options = [ft.dropdown.Option("No")] + [ft.dropdown.Option(friend) for friend in friends.keys()]

        share_with_input = ft.Dropdown(
            options=share_with_options,
            value=expense.get("shared"," "),
            border_radius=12,
            bgcolor=self.theme_color.cyan_card,
            border_color=ft.colors.CYAN_200,
            focused_border_color=ft.colors.CYAN_400,
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


        owner_options = [ft.dropdown.Option("I owe the expense"), ft.dropdown.Option("Owes the expense")]
        owner_input = ft.Dropdown(
            options=owner_options,
            value="I owe the expense",
            label="Who owes Who",
            border_radius=12,
            bgcolor=self.theme_color.cyan_card,
            border_color=ft.colors.CYAN_200,
            focused_border_color=ft.colors.CYAN_400,
        )

        share_with = ft.Container(
            content=ft.Column([
                ft.Text("Share With", weight=ft.FontWeight.W_500, size=14),
                share_with_input,
                percentage,
                owner_input
            ], spacing=8),
            bgcolor=self.theme_color.text_logo,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
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

        recurring_period = ft.Container(
            content=ft.Column([
                ft.Text("Recurring Period", weight=ft.FontWeight.W_500, size=14),
                recurring_period_input,
                self.recurring_date_button
            ], spacing=8),
            bgcolor=self.theme_color.text_logo,
            border_radius=12,
            padding=15,
            margin=ft.margin.only(bottom=15),
            border=ft.border.all(1, ft.colors.GREY_200)
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
                self.create_upcoming_transactions_card()
                self.edit_expense_dialog.open = False
                self.page.update()
                self.show_snackbar("Expense updated successfully!")

            except ValueError:
                self.show_snackbar("Please enter a valid amount")
            except Exception as ex:
                print(f"Editing operation failed with error {ex}")
                self.show_snackbar(f"Error updating expense: {ex}")

        self.edit_expense_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.EDIT_SHARP, color=self.theme_color.text_primary, size=24),
                ft.Text("Edit Expense", weight=ft.FontWeight.BOLD, size=20, color=self.theme_color.text_primary)
            ], spacing=10),
                padding=ft.padding.only(bottom=10)
            ),
            content=ft.Container(
                content=ft.Column([
                    amount_field,
                    category_field,
                    description_field,
                    share_with,
                    recurring_period,
                ], spacing=0, scroll=ft.ScrollMode.AUTO),
                height=600,
                width=400,
                padding=20,
                bgcolor=self.theme_color.background,
                border_radius=15
            ),
            actions=[
                ft.Container(
                    content=ft.Row([
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda e: self.close_edit_dialog(),
                            style=ft.ButtonStyle(
                                color=self.theme_color.text_secondary,
                                bgcolor=self.theme_color.background,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.padding.symmetric(horizontal=20, vertical=10)
                            )
                        ),
                        ft.ElevatedButton(
                            "Update Expense",
                            on_click=update_expense,
                            icon=ft.icons.SAVE,
                            bgcolor=self.theme_color.green_card,
                            color=self.theme_color.text_logo,
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
            bgcolor=self.theme_color.background,
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
                self.db.collection('users').document(self.user_id).collection('expenses').document(expense_id).delete()

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
        self.create_budget_progress_card()
        self.create_quick_insights_row()
        self.create_highest_expenses_card()
        self.create_upcoming_transactions_card()
        confirm_dialog.open = True
        self.page.update()

    def show_edit_wish_dialog(self, wish_id):
        """Show dialog to edit existing wish item"""
        wish_item = next((wish for wish in self.wishes if wish.get('id') == wish_id), None)
        if not wish_item:
            return

        self.editing_wish_id = wish_id

        amount_input = ft.TextField(
            label="Amount",
            keyboard_type=ft.KeyboardType.NUMBER,
            value=wish_item['amount'],
            adaptive=True,
            border_radius=12,
            prefix_icon=ft.icons.MONEY,
            bgcolor=self.theme_color.blue_card,
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
            value=wish_item['category'],
            border_radius=12,
            bgcolor=self.theme_color.orange_card,
            border_color=ft.colors.ORANGE_200,
            focused_border_color=ft.colors.ORANGE_400,
        )
        category_field = ft.Container(
            content=category_input,
            margin=ft.margin.only(bottom=15)
        )
        description_input = ft.TextField(
            label="Description",
            value=wish_item['description'],
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=12,
            bgcolor=self.theme_color.green_card,
            border_color=ft.colors.GREEN_200,
            focused_border_color=ft.colors.GREEN_400,
        )

        description_field = ft.Container(
            content=description_input,
            margin=ft.margin.only(bottom=15)
        )

        def update_wish_item(e):
            try:
                amount = float(amount_input.value or 0)
                category = category_input.value or ""
                description = description_input.value or ""

                if amount <= 0:
                    self.show_snackbar("Please enter a valid amount")
                    return

                # Update in Firebase
                self.db.collection('users').document(self.user_id).collection('wish_list').document(wish_id).update({
                    'amount': amount,
                    'category': category,
                    'description': description,
                })

                self.update_wish_list()
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
            content=ft.Container(
                content=ft.Column([
                    amount_field,
                    category_field,
                    description_field,

                ], spacing=0, scroll=ft.ScrollMode.AUTO),
                height=600,
                width=400,
                padding=20,
                bgcolor=self.theme_color.background,
                border_radius=15
            ),
            actions=[
                ft.Container(
                    content=ft.Row([
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda e: self.close_dialog(self.edit_wish_dialog),
                            style=ft.ButtonStyle(
                                color=self.theme_color.text_secondary,
                                bgcolor=self.theme_color.button_background,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.padding.symmetric(horizontal=20, vertical=10)
                            )
                        ),
                        ft.ElevatedButton(
                            "Save Expense",
                            on_click=update_wish_item,
                            icon=ft.icons.SAVE,
                            bgcolor=self.theme_color.purple_card,
                            color=self.theme_color.text_secondary,
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
            bgcolor=self.theme_color.background,
            shape=ft.RoundedRectangleBorder(radius=20),
            adaptive=True
        )

        self.page.dialog = self.edit_wish_dialog
        self.edit_wish_dialog.open = True
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
        start_date = e.control.value
        self.start_date = (datetime.combine(start_date, time.min)).strftime('%Y-%m-%d')
        self.start_date_button.text = f"Start: {self.start_date}"
        self.save_budget_data()
        self.update_budget_summary()
        self.page.update()

    def on_end_date_change(self, e):
        end_date = e.control.value
        self.end_date = (datetime.combine(end_date, time.min)).strftime('%Y-%m-%d')
        self.end_date_button.text = f"End: {self.end_date}"
        self.save_budget_data()
        self.update_budget_summary()
        self.page.update()

    def show_add_wish_dialog(self, e):
        """Show dialog to add new item on wish list"""

        amount_input = ft.TextField(
            label="Amount",
            keyboard_type=ft.KeyboardType.NUMBER,
            adaptive=True,
            border_radius=12,
            prefix_icon=ft.icons.MONEY,
            bgcolor=self.theme_color.blue_card,
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
            bgcolor=self.theme_color.orange_card,
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
            bgcolor=self.theme_color.green_card,
            border_color=ft.colors.GREEN_200,
            focused_border_color=ft.colors.GREEN_400,
        )

        description_field = ft.Container(
            content=description_input,
            margin=ft.margin.only(bottom=15)
        )

        def save_wish(e):
            try:
                amount = float(amount_input.value or 0)
                category = category_input.value or ""
                description = description_input.value or ""

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

                else:
                    print("⚠️ Firebase not available")

                self.wishes.append(wish_item_data)
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
            title=ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.ADD_CIRCLE_OUTLINE, color=self.theme_color.text_secondary, size=24),
                ft.Text("Add New Wish", weight=ft.FontWeight.BOLD, size=20, color=self.theme_color.text_secondary)
            ], spacing=10),
                padding=ft.padding.only(bottom=10)
            ),
            content=ft.Container(
                content=ft.Column([
                    amount_field,
                    category_field,
                    description_field,

                ], spacing=0, scroll=ft.ScrollMode.AUTO),
                height=600,
                width=400,
                padding=20,
                bgcolor=self.theme_color.background,
                border_radius=15
            ),
            actions=[
                ft.Container(
                    content=ft.Row([
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda e: self.close_dialog(self.wish_list_form_dialog),
                            style=ft.ButtonStyle(
                                color=self.theme_color.text_secondary,
                                bgcolor=self.theme_color.button_background,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.padding.symmetric(horizontal=20, vertical=10)
                            )
                        ),
                        ft.ElevatedButton(
                            "Save Expense",
                            on_click=save_wish,
                            icon=ft.icons.SAVE,
                            bgcolor=self.theme_color.purple_card,
                            color=self.theme_color.text_secondary,
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
            bgcolor=self.theme_color.background,
            shape=ft.RoundedRectangleBorder(radius=20),
            adaptive=True
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

        except Exception as e:
            print(f"❌ Error saving budget data: {e}")

    def load_budget_data(self):
        """Load budget data from Firebase"""
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

            self.automaticaly_update_expense()

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

            #self.update_wish_list()


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
        friends_list = FriendsManager(self.user_id).get_friends_list()
        shared_info = {}
        for friend in friends_list:
            shared_info[friend['displayName']] = 0
            for expense in self.expenses:
                if expense['shared'] != 'No':
                    if expense['owe status'] != "I owe the expense":
                        shared_info[friend['displayName']] -= expense['amount'] * float(expense['percentage']) * 0.01
                    else:
                        shared_info[friend['displayName']] += expense['amount'] * float(expense['percentage']) * 0.01

        if not shared_info:
            return ft.Text("No shared expenses")

        expense_items = []
        for person, amount in shared_info.items():
            if amount < 0:
                item = ft.Container(
                    content=ft.Row([
                        ft.Text(f"You owe {person}: {abs(amount):.2f} {self.currency}", color=self.theme_color.text_primary),
                        ft.ElevatedButton(
                            text="Settle",
                            on_click=lambda e, amount=abs(shared_info[person]): self.settle_expense(amount, person)
                        )
                    ]),
                    padding=5
                )
            else:
                item = ft.Container(
                    content=ft.Text(f"{person} owes you: {amount:.2f} {self.currency}", color=self.theme_color.text_primary),
                    padding=5
                )

            expense_items.append(item)

        return ft.Column(expense_items, spacing=5)

    def get_total_expenses(self):
        start_date = self.start_date
        total_expenses = sum(expense.get('amount', 0) for expense in self.expenses if
                             (expense['shared'] == 'No' or expense['owe status']
                              is not True and expense['user id'] == self.user_id)
                             and (start_date <= expense['date']))
        return total_expenses

    def update_budget_summary(self):
        """Update the budget summary display"""
        total_expenses = self.get_total_expenses()
        remaining_budget = self.budget_amount - total_expenses
        start_date_obj = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        current_date = datetime.now().date()

        if end_date_obj < current_date:
            day_diff = (end_date_obj - start_date_obj).days

            if day_diff > 26:
                # Add a month to both dates
                start_date_obj += relativedelta(months=1)
                end_date_obj += relativedelta(months=1)
            else:
                # Move start date to day after end date, keep same duration
                start_date_obj = end_date_obj + timedelta(days=1)
                end_date_obj += timedelta(days=day_diff)

            # Convert back to strings
            self.start_date = start_date_obj.strftime("%Y-%m-%d")
            self.end_date = end_date_obj.strftime("%Y-%m-%d")
            total_expenses = self.get_total_expenses()
            remaining_budget = self.budget_amount - total_expenses

            if not self.db:
                print("⚠️ Firebase not initialized, initializing database")
                self.db = firestore.client()

            try:
                update_data = {
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                    'updated_at': datetime.now()
                }

                # Save or update budget document
                self.db.collection('users').document(self.user_id).collection('budget').document('current').update(
                    update_data)

            except Exception as e:
                print(f"❌ Error saving budget data: {e}")

        self.budget_summary.content = ft.Column([
            # Budget card with improved styling
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        # Left side - Budget info
                        ft.Row([
                            ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET,
                                    size=20, color=self.theme_color.text_primary),
                            ft.Text("Budget", size=13, color=self.theme_color.text_primary,
                                    weight=ft.FontWeight.W_500),
                        ], spacing=8),
                        # Right side - Edit button
                        ft.IconButton(
                            icon=ft.icons.EDIT,
                            icon_color=self.theme_color.logo_on_blue,
                            on_click=self.show_configure_budget_dialog
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=8),
                    ft.Text(f"{self.budget_amount:.2f} {self.currency}",
                            size=20, weight=ft.FontWeight.BOLD, color=self.theme_color.text_primary),
                    ft.Container(height=8),
                    ft.Text(f"{self.start_date} to {self.end_date}",
                            size=15, color=self.theme_color.text_primary),
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                bgcolor=self.theme_color.blue_card,
                border_radius=16,
                padding=20,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=8,
                    color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                    offset=ft.Offset(0, 2)
                ),
                border=ft.border.all(1, ft.colors.BLUE_200)
            ),

            ft.Container(height=15),  # Spacing between budget and other cards

            # Spent and Remaining cards in a row
            ft.Row([
                # Spent card
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.TRENDING_UP,
                                    size=20, color=self.theme_color.text_primary),
                            ft.Text("Spent", size=13, color=self.theme_color.text_primary,
                                    weight=ft.FontWeight.W_500),
                        ], spacing=8),
                        ft.Container(height=8),
                        ft.Text(f"{total_expenses:.2f} Lei",
                                size=20, weight=ft.FontWeight.BOLD, color=self.theme_color.text_primary),
                    ], spacing=0, alignment=ft.MainAxisAlignment.START),
                    bgcolor=self.theme_color.red_card,
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

                # Remaining card
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.SAVINGS,
                                    size=20, color=ft.colors.GREEN_600),
                            ft.Text("Remaining", size=13, color=self.theme_color.text_primary,
                                    weight=ft.FontWeight.W_500),
                        ], spacing=8),
                        ft.Container(height=8),
                        ft.Text(f"{remaining_budget:.2f} {self.currency}",
                                size=20, weight=ft.FontWeight.BOLD, color=self.theme_color.text_primary),
                    ], spacing=0, alignment=ft.MainAxisAlignment.START),
                    bgcolor=self.theme_color.green_card,
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
            ], spacing=15),
        ], spacing=0)


        if self.page:
            self.page.update()

    def reset_password(self, e):
        """Handle password reset request"""
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


        except Exception as e:

            # Handle specific Firebase errors, e.g., invalid email format

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

    def get_highest_expenses_list(self):
        expense_categories = {}
        reference_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        for expense in self.expenses:
            if expense['category'] in expense_categories.keys() and expense['date'] > reference_date:
                expense_categories[expense['category']] += expense['amount']
            else:
                if expense['date'] > reference_date:
                    expense_categories[expense['category']] = expense['amount']
        highest_expenses = list(sorted(expense_categories.items(), key=lambda item: item[1]))[::-1]

        return highest_expenses

    def load_settings(self) -> Dict:
        """Load settings from db or file or create default settings"""
        if not self.db:
            print("⚠️ Firebase not initialized, loading settings from file")
            if os.path.exists(self.settings_file):
                try:
                    print("loaded settings from file")
                    with open(self.settings_file, 'r') as f:
                        loaded_settings = json.load(f)
                        # Merge with defaults to ensure all keys exist
                        return {**self.default_settings, **loaded_settings}
                except (json.JSONDecodeError, IOError):
                    return self.default_settings.copy()
            return self.default_settings.copy()
        try:
            print("loading settings from db")
            #doc = self.db.collection('users').document(self.user_id).collection('settings').document('display_name').get()
            doc_name = self.db.collection('users').document(self.user_id).collection('settings').document('display_name').get()
            doc_avatar = self.db.collection('users').document(self.user_id).collection('settings').document(
                'avatar').get()
            doc_theme = self.db.collection('users').document(self.user_id).collection('settings').document(
                'theme').get()
            if doc_name:
                data = doc_name.to_dict()
                self.display_name = data.get('display_name')
                print("Loading avatar")
                data = doc_avatar.to_dict()
                self.current_avatar = data.get('avatar_path')
                print(f"avatar is {self.current_avatar}")
                print("loading theme")
                data = doc_theme.to_dict()
                self.is_dark_mode = data.get('theme')


            else:
                print("ℹ️ No existing settings data found")
        except Exception as e:
            print(f"❌ Error loading settings data: {e}")

    def save_settings_to_file(self, file, data):
        try:
            with open(file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            print("Error saving settings")

    def save_settings(self, e=None):
        """Save current settings to file"""
        if not self.db:
            print("⚠️ Firebase not initialized, saving settings to file")
            self.save_settings_to_file(self.settings_file, self.settings)
        else:
            self.display_name = self.name_input.value
            self.db.collection('users').document(self.user_id).set({"displayName":self.display_name}, merge=True)
            self.update_user_profile(self.user_id, 'display_name', self.display_name)

            self.settings.update({"avatar": self.current_avatar,
                            'display_name': self.display_name})
            self.save_settings_to_file(self.settings_file, self.settings)
        self.display_name_form_dialog.open = False
        self.page.update()
        self.show_main()

    def get_setting(self, key: str):
        """Get a specific setting value"""
        return self.settings.get(key, self.default_settings.get(key))

    def set_setting(self, key: str, value):
        """Set a specific setting value"""
        self.settings[key] = value
        self.save_settings()

    def show_add_name_dialog(self, e):
        """Show dialog to configure budget"""
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
        return ft.Container(
            content=ft.PopupMenuButton(
                items=[
                    ft.PopupMenuItem(
                        content=ft.Row([
                            ft.Icon(ft.icons.ACCOUNT_CIRCLE, size=20, color=self.theme_color.text_primary),
                            ft.Text('Avatar Image', size=14, weight=ft.FontWeight.W_500)
                        ], spacing=12),
                        on_click=self.show_avatar_selection_dialog
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row([
                            ft.Icon(ft.icons.EDIT, size=20, color=self.theme_color.text_primary),
                            ft.Text('Display Name', size=14, weight=ft.FontWeight.W_500)
                        ], spacing=12),
                        on_click=self.show_add_name_dialog
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row([
                            ft.Icon(ft.icons.PALETTE, size=20, color=self.theme_color.text_primary),
                            ft.Text('Theme', size=14, weight=ft.FontWeight.W_500),
                            ft.Switch(
                                value=self.is_dark_mode,  # You'll need to track this
                                on_change=self.set_app_theme,
                                active_color=ft.colors.TEAL,
                                inactive_thumb_color=ft.colors.GREY_400,
                                scale=0.8
                            )
                        ], spacing=12, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        on_click=None
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
                    content=ft.Icon(ft.icons.SETTINGS, size=24, color=self.theme_color.text_primary),
                    padding=12,
                    bgcolor=self.theme_color.teal_card,
                    border_radius=12,
                    border=ft.border.all(1, ft.colors.TEAL_200),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=4,
                        color=ft.colors.with_opacity(0.1, ft.colors.BLACK),
                        offset=ft.Offset(0, 2)
                    )
                ), bgcolor=self.theme_color.background
            ),
        )

    def show_avatar_selection_dialog(self, e=None):
        """Show dialog with all available avatars for selection"""
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
                border=ft.border.all(3, self.theme_color.text_primary) if avatar_path == self.current_avatar else None,
                on_click=lambda e, path=avatar_path: self.select_avatar(e, path),
                bgcolor=self.theme_color.background,
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
                                          folder_path=r"/assets"):
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
        self.settings.update({'avatar':self.current_avatar})
        self.save_settings_to_file(self.settings_file, self.settings)
        try:
            print("saving avatar")
            settings_data = {
                "avatar_path": self.current_avatar,
                }

            # Save or update budget document
            self.db.collection('users').document(self.user_id).collection('settings').document('avatar').\
                set(settings_data)
            print(f"✅ Avatar saved successfully: {settings_data}")
        except Exception as e:
            print(f'An exception occurred: {e}')

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
    try:
        app = BudgetApp(page)
        print("App created successfully")  # Debug print
    except Exception as e:
        print(f"Error creating app: {e}")
        page.add(ft.Text(f"Error: {e}"))
        page.update()


if __name__ == "__main__":
    ft.app(target=main)
