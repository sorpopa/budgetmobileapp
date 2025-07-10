import flet as ft
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
import time


class SettingsManager:
    def __init__(self, settings_file: str = "app_settings.json"):
        self.settings_file = settings_file
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

    def load_settings(self) -> Dict:
        """Load settings from file or create default settings"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return {**self.default_settings, **loaded_settings}
            except (json.JSONDecodeError, IOError):
                return self.default_settings.copy()
        return self.default_settings.copy()

    def save_settings(self):
        """Save current settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except IOError:
            print("Error saving settings")

    def get_setting(self, key: str):
        """Get a specific setting value"""
        return self.settings.get(key, self.default_settings.get(key))

    def set_setting(self, key: str, value):
        """Set a specific setting value"""
        self.settings[key] = value
        self.save_settings()


class NotificationManager:
    def __init__(self, settings_manager: SettingsManager):
        self.settings_manager = settings_manager
        self.notification_thread = None
        self.running = False

    def start_notification_service(self):
        """Start the background notification service"""
        if not self.running:
            self.running = True
            self.notification_thread = threading.Thread(target=self._notification_loop, daemon=True)
            self.notification_thread.start()

    def stop_notification_service(self):
        """Stop the background notification service"""
        self.running = False

    def _notification_loop(self):
        """Background loop for checking notifications"""
        while self.running:
            try:
                self._check_notifications()
                time.sleep(3600)  # Check every hour
            except Exception as e:
                print(f"Notification error: {e}")
                time.sleep(3600)

    def _check_notifications(self):
        """Check if any notifications need to be sent"""
        current_time = datetime.now()

        # Check for bill reminders (example logic)
        if self.settings_manager.get_setting("bill_reminders"):
            self._check_bill_reminders(current_time)

        # Check for weekly summaries (every Monday)
        if (self.settings_manager.get_setting("weekly_summaries") and
                current_time.weekday() == 0):  # Monday
            self._send_weekly_summary()

        # Check for monthly summaries (first day of month)
        if (self.settings_manager.get_setting("monthly_summaries") and
                current_time.day == 1):
            self._send_monthly_summary()

    def _check_bill_reminders(self, current_time: datetime):
        """Check for upcoming bill due dates"""
        # This would integrate with your bill data
        print(f"Checking bill reminders for {current_time}")

    def _send_weekly_summary(self):
        """Send weekly spending summary"""
        print("Sending weekly summary notification")

    def _send_monthly_summary(self):
        """Send monthly spending summary"""
        print("Sending monthly summary notification")

    def check_budget_alerts(self, current_spending: float, budget_limit: float):
        """Check if spending alerts should be triggered"""
        if budget_limit <= 0:
            return

        spending_percentage = (current_spending / budget_limit) * 100

        # Check spending alert threshold
        alert_threshold = self.settings_manager.get_setting("spending_alert_threshold")
        if spending_percentage >= alert_threshold:
            self._send_spending_alert(spending_percentage, current_spending, budget_limit)

        # Check budget limit warning
        warning_threshold = self.settings_manager.get_setting("budget_limit_warning")
        if spending_percentage >= warning_threshold:
            self._send_budget_warning(spending_percentage, current_spending, budget_limit)

    def _send_spending_alert(self, percentage: float, spending: float, budget: float):
        """Send spending alert notification"""
        currency = self.settings_manager.get_setting("currency")
        message = f"Spending Alert: You've spent {percentage:.1f}% of your budget ({currency}{spending:.2f}/{currency}{budget:.2f})"
        print(message)
        # Here you would integrate with your app's notification system

    def _send_budget_warning(self, percentage: float, spending: float, budget: float):
        """Send budget limit warning"""
        currency = self.settings_manager.get_setting("currency")
        message = f"Budget Warning: You've reached {percentage:.1f}% of your budget limit ({currency}{spending:.2f}/{currency}{budget:.2f})"
        print(message)
        # Here you would integrate with your app's notification system

    def notify_goal_achievement(self, goal_name: str, goal_amount: float):
        """Send goal achievement notification"""
        if self.settings_manager.get_setting("goal_notifications"):
            currency = self.settings_manager.get_setting("currency")
            message = f"🎉 Congratulations! You've achieved your goal: {goal_name} ({currency}{goal_amount:.2f})"
            print(message)
            # Here you would integrate with your app's notification system


class SettingsPage:
    def __init__(self, page: ft.Page, settings_manager: SettingsManager, notification_manager: NotificationManager):
        self.page = page
        self.settings_manager = settings_manager
        self.notification_manager = notification_manager

        # Currency options
        self.currencies = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR"]

        # Create UI components
        self.display_name_field = ft.TextField(
            label="Display Name",
            value=self.settings_manager.get_setting("display_name"),
            on_change=self._on_display_name_change
        )

        self.currency_dropdown = ft.Dropdown(
            label="Currency",
            value=self.settings_manager.get_setting("currency"),
            options=[ft.dropdown.Option(curr) for curr in self.currencies],
            on_change=self._on_currency_change
        )

        self.spending_alert_slider = ft.Slider(
            min=50,
            max=100,
            value=self.settings_manager.get_setting("spending_alert_threshold"),
            label="Spending Alert Threshold: {value}%",
            on_change=self._on_spending_alert_change
        )

        self.budget_warning_slider = ft.Slider(
            min=70,
            max=100,
            value=self.settings_manager.get_setting("budget_limit_warning"),
            label="Budget Warning Threshold: {value}%",
            on_change=self._on_budget_warning_change
        )

        self.bill_reminders_switch = ft.Switch(
            label="Bill Due Date Reminders",
            value=self.settings_manager.get_setting("bill_reminders"),
            on_change=self._on_bill_reminders_change
        )

        self.weekly_summaries_switch = ft.Switch(
            label="Weekly Spending Summaries",
            value=self.settings_manager.get_setting("weekly_summaries"),
            on_change=self._on_weekly_summaries_change
        )

        self.monthly_summaries_switch = ft.Switch(
            label="Monthly Spending Summaries",
            value=self.settings_manager.get_setting("monthly_summaries"),
            on_change=self._on_monthly_summaries_change
        )

        self.goal_notifications_switch = ft.Switch(
            label="Goal Achievement Notifications",
            value=self.settings_manager.get_setting("goal_notifications"),
            on_change=self._on_goal_notifications_change
        )

        self.notification_time_field = ft.TextField(
            label="Notification Time (HH:MM)",
            value=self.settings_manager.get_setting("notification_time"),
            on_change=self._on_notification_time_change
        )

    def _on_display_name_change(self, e):
        """Handle display name change"""
        self.settings_manager.set_setting("display_name", e.control.value)

    def _on_currency_change(self, e):
        """Handle currency change"""
        self.settings_manager.set_setting("currency", e.control.value)

    def _on_spending_alert_change(self, e):
        """Handle spending alert threshold change"""
        self.settings_manager.set_setting("spending_alert_threshold", int(e.control.value))

    def _on_budget_warning_change(self, e):
        """Handle budget warning threshold change"""
        self.settings_manager.set_setting("budget_limit_warning", int(e.control.value))

    def _on_bill_reminders_change(self, e):
        """Handle bill reminders toggle"""
        self.settings_manager.set_setting("bill_reminders", e.control.value)

    def _on_weekly_summaries_change(self, e):
        """Handle weekly summaries toggle"""
        self.settings_manager.set_setting("weekly_summaries", e.control.value)

    def _on_monthly_summaries_change(self, e):
        """Handle monthly summaries toggle"""
        self.settings_manager.set_setting("monthly_summaries", e.control.value)

    def _on_goal_notifications_change(self, e):
        """Handle goal notifications toggle"""
        self.settings_manager.set_setting("goal_notifications", e.control.value)

    def _on_notification_time_change(self, e):
        """Handle notification time change"""
        self.settings_manager.set_setting("notification_time", e.control.value)

    def build(self) -> ft.Column:
        """Build the settings page UI"""
        return ft.Column([
            ft.Text("Settings", size=24, weight=ft.FontWeight.BOLD),

            ft.Divider(),

            # Profile Settings
            ft.Text("Profile", size=18, weight=ft.FontWeight.W_500),
            self.display_name_field,
            self.currency_dropdown,

            ft.Divider(),

            # Alert Settings
            ft.Text("Spending Alerts", size=18, weight=ft.FontWeight.W_500),
            ft.Text("Get notified when you reach these spending thresholds:"),
            self.spending_alert_slider,
            self.budget_warning_slider,

            ft.Divider(),

            # Notification Settings
            ft.Text("Notifications", size=18, weight=ft.FontWeight.W_500),
            self.bill_reminders_switch,
            self.weekly_summaries_switch,
            self.monthly_summaries_switch,
            self.goal_notifications_switch,
            self.notification_time_field,

            ft.Divider(),

            # Test notification button
            ft.ElevatedButton(
                "Test Notification",
                on_click=self._test_notification
            )
        ], scroll=ft.ScrollMode.AUTO)

    def _test_notification(self, e):
        """Test notification functionality"""
        self.notification_manager.check_budget_alerts(800, 1000)  # Test with sample data
        self.notification_manager.notify_goal_achievement("Emergency Fund", 5000)

        # Show confirmation
        self.page.show_snack_bar(
            ft.SnackBar(content=ft.Text("Test notifications sent! Check console output."))
        )

