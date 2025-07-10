

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