import flet as ft
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import webbrowser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import tempfile
import os

import requests
import webbrowser
import time
from threading import Thread


class Expense:
    #reads data and puts data into storage
    def __init__(self, amount: float, category: str, description: str, owner_id: str, shared_with: List[str] = None,
                 split_amounts: Dict[str, float] = None, date: datetime = None,
                is_recurring = False, recurring_day: datetime = None, expense_id: int = None):
        self.id = expense_id or int(datetime.now().timestamp() * 1000)
        self.amount = amount
        self.category = category
        self.description = description
        self.date = date or datetime.now().strftime("%m-%d-%Y %H:%M:%S")
        self.is_recurring = is_recurring
        self.recurring_day = recurring_day

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'category': self.category,
            'description': self.description,
            'date': self.date,
            "is recurring": self.is_recurring,
            'recurring day': self.recurring_day
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            amount=data['amount'],
            category=data['category'],
            description=data['description'],
            date=data['date'],
            expense_id=data['id'],
            is_recurring=data['is recurring'],
            recurring_day=data['recurring day']
        )

class SharedExpense(Expense):
    def __init__(self, amount: float, category: str, description: str, owner_id: str, shared_with: List[str] = None,
                 split_amounts: Dict[str, float] = None, date: datetime = None,
                 is_recurring=False, recurring_day: datetime = None, expense_id: int = None):
        super().__init__(amount, category, description, date, expense_id, is_recurring, recurring_day)
        self.owner_id = owner_id
        self.shared_with = shared_with
        self.split_amounts = split_amounts
        self.is_shared = len(self.shared_with) > 0

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'owner_id': self.owner_id,
            'shared_with': self.shared_with,
            'split_amounts': self.split_amounts,
            'is_shared': self.is_shared
        })

    @classmethod
    def from_dict(cls, data):
        return cls(
            amount=data['amount'],
            category=data['category'],
            description=data['description'],
            owner_id=data.get('owner_id', ''),
            shared_with=data.get('shared_with', []),
            split_amounts=data.get('split_amounts', {}),
            date=data['date'],
            expense_id=data['id'],
            is_recurring = data['is recurring'],
            recurring_day = data['recurring day']
        )


class BudgetApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Budget Planning App"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window_width = 800
        self.page.window_height = 600
        self.page.adaptive


        # Data storage
        self.expenses: List[Expense] = []
        self.filtered_expenses: List[Expense] = []
        self.recurring_expenses: list[Expense] = []

        self.budget_amount = 0.0
        self.budget_start_day = datetime.now()
        self.budget_end_day = datetime.now()
        self.data_file = "budget_data.json"

        # Load data
        self.load_data()

        # UI Components
        self.tabs = None
        self.overview_tab = None
        self.all_expenses_tab = None

        # Overview tab components
        #Budget components
        self.budget_dialog = None
        self.budget_input = ft.TextField(
            label="Monthly Budget",
            value=str(self.budget_amount),
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER)

        self.start_date_picker = ft.DatePicker(
            on_change=self.on_start_date_change,
            first_date=datetime(2025, 1, 1),
            last_date=datetime(2030, 12, 31),
            current_date=datetime.now()
        )

        self.start_date_button = ft.TextButton(
            text=f"Start Date: {self.budget_start_day.strftime('%Y-%m-%d')}",
            icon=ft.icons.CALENDAR_MONTH,
            on_click=self.open_date_picker,
            width=200
        )
        self.end_date_picker = ft.DatePicker(
            on_change=self.on_end_date_change,
            first_date=datetime(2025, 1, 1),
            last_date=datetime(2030, 12, 31),
            current_date=datetime.now()
        )

        self.end_date_button = ft.TextButton(
            text=f"End Date: {self.budget_end_day.strftime('%Y-%m-%d')}",
            icon=ft.icons.CALENDAR_MONTH,
            on_click=self.open_end_date_picker,
            width=200
        )

        self.page.overlay.append(self.start_date_picker)
        self.page.overlay.append(self.end_date_picker)

        self.budget_display = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
        self.spent_display = ft.Text("", size=16)
        self.remaining_display = ft.Text("", size=16)

        # Expense form components
        self.expense_dialog = None
        self.amount_field = ft.TextField(label="Amount", keyboard_type=ft.KeyboardType.NUMBER, width=200)
        self.drop_down_options = [
                ft.dropdown.Option("Food"),
                ft.dropdown.Option("Transport"),
                ft.dropdown.Option("Entertainment"),
                ft.dropdown.Option("Cloths"),
                ft.dropdown.Option("Bills"),
                ft.dropdown.Option("Childcare"),
                ft.dropdown.Option("Health"),
                ft.dropdown.Option("Digital services"),
                ft.dropdown.Option("Dining Out"),
                ft.dropdown.Option("Toys"),
                ft.dropdown.Option("Presents"),
                ft.dropdown.Option("Other"),
                ft.dropdown.Option("Vacation"),
                ft.dropdown.Option("Books"),
                ft.dropdown.Option("Self Improvement"),
            ]
        self.category_field = ft.Dropdown(
            label="Category",
            width=200,
            options=self.drop_down_options
        )
        self.description_field = ft.TextField(label="Description", width=300, multiline=True)

        # All expenses tab components
        self.filter_category_options = [ft.dropdown.Option("All")]
        self.filter_category_options += self.drop_down_options
        self.category_filter = ft.Dropdown(
            label="Filter by Category",
            options=self.filter_category_options,
            value="All",
            width=200,
            #Flet automatically passes an event parameter to the method, that is why it was needed to add e=None as a parameter
            #to update_all_expenses_list()
            on_change=self.update_all_expenses_list
        )
        self.recurring_period = ft.Dropdown(
            label="Is Recurring",
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
            value="All",
            width=200,
        )

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

        self.recurring_checkbox = ft.Checkbox(label="Recurring expenses", on_change=self.update_all_expenses_list)
        self.filter_by_period_dropdown = ft.Dropdown(width=200,
                                                     label="Filter by Time Period",
                                                     value="Beginning of Time",
                options=[
                    ft.dropdown.Option("Beginning of Time"),
                    ft.dropdown.Option("1 Month"),
                    ft.dropdown.Option("2 Months"),
                    ft.dropdown.Option("3 Months"),
                    ft.dropdown.Option("4 Months"),
                    ft.dropdown.Option("5 Months"),
                    ft.dropdown.Option("6 Months"),
                ],
                on_change=self.update_all_expenses_list
            )


        self.page.overlay.append(self.recurring_date_picker)

        self.expenses_list = ft.ListView(expand=True, spacing=10)

        self.automaticaly_update_expense()
        self.setup_ui()
        self.update_displays()


    # Add this method to handle date selection:
    def on_start_date_change(self, e):
        if e.control.value:
            selected_date = e.control.value
            self.budget_start_day = selected_date
            self.start_date_button.text = f"Start Date: {selected_date.strftime('%Y-%m-%d')}"
            self.page.update()
            try:
                self.show_snackbar("Start of the month day saved!")

            except ValueError:
                self.show_snackbar("Please enter valid numbers!")


    def on_end_date_change(self, e):
        if e.control.value:
            selected_date = e.control.value
            self.budget_end_day = selected_date
            self.end_date_button.text = f"End Date: {selected_date.strftime('%Y-%m-%d')}"
            self.page.update()
            try:
                self.show_snackbar("End of the month day saved!")

            except ValueError:
                self.show_snackbar("Please enter valid numbers!")

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

    def open_end_date_picker(self, e):
        self.end_date_picker.pick_date()
        self.update_displays()

    def load_data(self):
        """Load user data from API"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.budget_amount = data.get('budget_amount', 0.0)
                    self.budget_start_day = datetime(*tuple(map(int, (data.get.get('budget_start_day').split("T"))[0].split("-")[:3])))
                    self.budget_end_day = datetime(*tuple(map(int, (data.get('budget_end_day').split("T"))[0].split("-")[:3])))
                    expenses_data = data.get('expenses', [])
                    self.expenses = [SharedExpense.from_dict(exp) for exp in expenses_data]

                self.recurring_expenses = [exp for exp in self.expenses if exp.is_recurring != "No"]

            except Exception as e:
                print(f"Error loading data: {e}")

    def save_data(self):
        """Save data to JSON file"""

        try:

            data = {
                'budget_amount': self.budget_amount,
                'budget_start_day': self.budget_start_day.isoformat(),
                'budget_end_day': self.budget_end_day.isoformat(),
                'expenses': [exp.to_dict() for exp in self.expenses]
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")


    def get_category_icon(self, category):
        icons_map = {
            "Food": ft.icons.RESTAURANT,
            "Transport": ft.icons.BUS_ALERT,
            "Entertainment": ft.icons.MOVIE,
            "Shopping": ft.icons.SHOPPING_BAG,
            "Bills": ft.icons.RECEIPT,
            "Coffe": ft.icons.BLENDER,
            "Cloths": ft.icons.GIRL_OUTLINED,
            "Childcare": ft.icons.BABY_CHANGING_STATION,
            "Health": ft.icons.MEDICATION,
            "Digital services": ft.icons.WIDGETS,
            "Dining Out": ft.icons.RESTAURANT,
            "Toys": ft.icons.CHILD_CARE,
            "Presents": ft.icons.WALLET_GIFTCARD,
            "Other": ft.icons.WALLET,
            "Vacation": ft.icons.BEACH_ACCESS,
            "Books": ft.icons.BOOK,
            "Self Improvement": ft.icons.BOOK_ROUNDED,
            "Self care": ft.icons.BEACH_ACCESS_ROUNDED,
            "Sweets": ft.icons.CAKE
        }
        return icons_map.get(category, ft.icons.MONEY)

    def get_category_color(self, category):
        colors = {
            "Food": ft.colors.ORANGE,
            "Transport": ft.colors.BLUE,
            "Entertainment": ft.colors.PURPLE,
            "Shopping": ft.colors.GREEN,
            "Bills": ft.colors.RED
        }
        return colors.get(category, 'grey')

    def set_recurring_day(self, recurring_period):
        if recurring_period == "Monthly":
            period =30
        elif recurring_period == "Yearly":
            period = 12*30
        else:
            period = int(recurring_period.split()[0])*30
        return period

    def setup_ui(self):
        """Setup the main UI components"""
        # Create tabs
        self.overview_tab = ft.Tab(
            text="Overview",
            content=self.create_overview_content()
        )

        self.all_expenses_tab = ft.Tab(
            text="All Expenses",
            content=self.create_all_expenses_content()
        )

        self.tabs = ft.Tabs(
            selected_index=0,
            tabs=[self.overview_tab, self.all_expenses_tab],
            expand=1,
            on_change=self.on_tab_change  # Add this
        )

        # Create expense dialog
        self.create_expense_dialog()
        self.create_budget_dialog()

        # Add to page
        self.page.add(self.tabs)

    def on_tab_change(self, e):
        if e.control.selected_index == 1:  # All Expenses tab
            self.update_all_expenses_list()

    def setup_google_auth(self):
        """Setup Google OAuth flow"""
        # You need to create credentials in Google Cloud Console
        CLIENT_CONFIG = {
            "web": {
                "client_id": "YOUR_GOOGLE_CLIENT_ID",
                "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080/callback"]
            }
        }

        self.auth_flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=['openid', 'email', 'profile'],
            redirect_uri='http://localhost:8080/callback'
        )

    def start_google_auth(self, e):
        """Start Google authentication process"""
        try:
            self.setup_google_auth()
            auth_url, _ = self.auth_flow.authorization_url(prompt='consent')
            webbrowser.open(auth_url)
            self.show_snackbar("Please complete authentication in your browser")

            # In a real app, you'd handle the callback properly
            # For demo purposes, we'll simulate successful login
            self.login()
        except Exception as ex:
            self.show_snackbar(f"Authentication error: {str(ex)}")


    def create_overview_content(self):
        """Create the overview tab content"""

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.ElevatedButton(
                        text="Configure Budget",
                        on_click=self.open_budget_dialog,
                        bgcolor=ft.colors.BLUE_300,
                        color=ft.colors.WHITE
                    ),
                    ft.ElevatedButton(
                        text="Add Expense",
                        on_click=self.open_expense_dialog,
                        bgcolor=ft.colors.BLUE_300,
                        color=ft.colors.WHITE
                    )
                ]),
                ft.Divider(),
                ft.Text("Budget Summary", size=18, weight=ft.FontWeight.BOLD),
                ft.Column([
                    self.budget_display,
                    self.spent_display,
                    self.remaining_display
                ]),
                ft.Divider(),
            ], scroll=ft.ScrollMode.AUTO),
            padding=20
        )

    def create_all_expenses_content(self):
        """Create the all expenses tab content"""
        return ft.Container(
            content=ft.Column([
                ft.Text("All Expenses", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.category_filter,
                    self.filter_by_period_dropdown,
                    self.recurring_checkbox,
                ]),
                ft.FloatingActionButton(icon=ft.icons.ADD,
                                        bgcolor=ft.colors.LIME_300,
                                        data=0,
                                        on_click=self.open_expense_dialog
                                        ),
                ft.Container(
                    content=self.expenses_list,
                    expand=True,
                    border=ft.border.all(1, ft.colors.GREY_300),
                    padding=10
                ),
            ], expand=True),
            padding=20
        )

    def create_expense_dialog(self):
        """Create the expense input dialog"""
        self.expense_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add New Expense"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([self.amount_field,
                    self.category_field]),
                    self.description_field,
                    ft.Row([self.recurring_period, self.recurring_date_button]),
                ], height=600, scroll=ft.ScrollMode.AUTO),
                width=400
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_expense_dialog),
                ft.ElevatedButton("Save", on_click=self.save_expense)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
    def create_budget_dialog(self):
        """Create the expense input dialog"""
        self.budget_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Configure Budget"),
            content=ft.Container(
                content=ft.Column([
                    self.budget_input,
                    self.start_date_button,
                    self.end_date_button
                ], height=200, scroll=ft.ScrollMode.AUTO),
                width=400
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_budget_dialog),
                ft.ElevatedButton("Save", on_click=self.save_budget_config)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

    def save_budget_config(self, e):
        """Save budget configuration"""
        try:
            self.budget_amount = float(self.budget_input.value or 0)

            if self.budget_amount <= 0:
                self.show_snackbar("Please enter a valid amount!")
                return

            self.save_data()
            self.update_displays()

            # Close dialog
            self.close_budget_dialog(e)
            self.show_snackbar("Budget configured successfully!")

        except ValueError:
            self.show_snackbar("Please enter valid numbers!")


    def open_expense_dialog(self, e):
        """Open the expense input dialog"""
        self.amount_field.value = ""
        self.category_field.value = ""
        self.description_field.value = ""
        self.recurring_period.value = "No"
        self.page.dialog = self.expense_dialog
        self.expense_dialog.open = True
        self.page.update()

    def close_expense_dialog(self, e):
        """Close the expense input dialog"""
        self.expense_dialog.open = False
        self.page.update()

    def save_expense(self, e):
        """Save expense via API"""

        try:
            amount = float(self.amount_field.value or 0)
            category = self.category_field.value.strip()
            description = self.description_field.value.strip()
            if self.recurring_period != "No":
                is_recurring = self.recurring_period.value
                recurring_day = self.recurring_day.strftime("%m-%d-%Y")
            else:
                recurring_day = " "

            if amount <= 0:
                self.show_snackbar("Please enter a valid amount!")
                return

            if not category:
                self.show_snackbar("Please enter a category!")
                return


            # Create new expense
            expense_data = {
                'amount': amount,
                'category': category,
                'description': description,
                'is_recurring': is_recurring,
                'recurring_day': recurring_day
            }

            self.load_data()  # Refresh data
            self.update_displays()
            self.close_expense_dialog(e)
            self.show_snackbar("Expense saved successfully!")


        except ValueError:
            self.show_snackbar("Please enter a valid amount!")

    def save_budget_config(self, e):
        """Save budget configuration via API"""

        try:
            self.budget_amount = float(self.budget_input.value)
            self.budget_start_day = self.budget_start_day
            self.budget_end_day = self.budget_end_day
            self.save_data()
            self.update_displays()
            self.show_snackbar("Budget configuration saved!")

        except ValueError:
            self.show_snackbar("Please enter valid numbers!")

    def edit_expense(self, expense_id: int):
        """Edit an existing expense"""
        expense = next((exp for exp in self.expenses if exp.id == expense_id), None)
        if expense:
            self.amount_field.value = str(expense.amount)
            self.category_field.value = expense.category
            self.description_field.value = expense.description
            self.recurring_period.value = expense.is_recurring
            if self.recurring_period != "No":
                is_recurring = self.recurring_period.value
                recurring_day = self.recurring_day.strftime("%m-%d-%Y")
            else:
                recurring_day = " "

            # Modify dialog for editing
            self.expense_dialog.title = ft.Text("Edit Expense")
            self.expense_dialog.actions = [
                ft.TextButton("Cancel", on_click=self.close_expense_dialog),
                ft.ElevatedButton("Update", on_click=lambda e: self.update_expense(expense_id))
            ]

            self.page.dialog = self.expense_dialog
            self.expense_dialog.open = True
            self.page.update()

    def update_expense(self, expense_id: int):
        """Update an existing expense"""
        try:
            amount = float(self.amount_field.value or 0)
            category = self.category_field.value.strip()
            description = self.description_field.value.strip()
            is_recuring = self.recurring_period.value
            recurring_day = self.recurring_day.strftime("%m-%d-%Y")
            if amount <= 0:
                self.show_snackbar("Please enter a valid amount!")
                return

            if not category:
                self.show_snackbar("Please enter a category!")
                return

            # Find and update expense
            expense = next((exp for exp in self.expenses if exp.id == expense_id), None)
            if expense:
                expense.amount = amount
                expense.category = category
                expense.description = description
                expense.is_recurring = is_recuring
                expense.recurring_day = recurring_day

                # Save data
                self.save_data()

                # Update displays
                self.update_displays()
                self.update_all_expenses_list()

                # Reset dialog
                self.expense_dialog.title = ft.Text("Add New Expense")
                self.expense_dialog.actions = [
                    ft.TextButton("Cancel", on_click=self.close_expense_dialog),
                    ft.ElevatedButton("Save", on_click=self.save_expense)
                ]

                # Close dialog
                self.close_expense_dialog(None)
                self.show_snackbar("Expense updated successfully!")

        except ValueError:
            self.show_snackbar("Please enter a valid amount!")

    def automaticaly_update_expense(self):
        for expense in self.recurring_expenses:
            if expense.recurring_day <= datetime.now().strftime('%m-%d-%Y').split()[0]:
                new_day = (datetime.now() + timedelta(
                    days=self.set_recurring_day(expense.is_recurring))).strftime("%m-%d-%Y %H:%M:%S")
                new_expense = Expense(expense.amount, expense.category, expense.description,
                                       is_recurring=expense.is_recurring,
                                      recurring_day=new_day)
                expense.recurring_day = new_day
                self.expenses.append(new_expense)

        self.save_data()

        # Update displays
        self.update_displays()
        # self.update_category_filter()
        self.update_all_expenses_list()


        # Force page update
        self.page.update()

    def delete_expense(self, expense_id: int):
        """Delete an expense"""
        self.expenses = [exp for exp in self.expenses if exp.id != expense_id]
        self.save_data()
        self.update_displays()
        self.update_all_expenses_list()
        self.show_snackbar("Expense deleted successfully!")

    def open_budget_dialog(self, e):
        """Open the budget input dialog"""
        self.budget_input.value = self.budget_amount
        self.page.dialog = self.budget_dialog
        self.start_date_button = self.start_date_button
        self.end_date_button = self.end_date_button
        self.budget_dialog.open = True
        self.page.update()

    def close_budget_dialog(self, e):
        """Close the budget configuration dialog"""
        self.budget_dialog.open = False
        self.page.update()


    def update_displays(self):
        """Update all display components"""
        self.update_budget_summary()
        self.update_all_expenses_list()

    def update_budget_summary(self):
        """Update budget summary display"""
        total_spent = sum(exp.amount for exp in self.expenses)
        remaining = self.budget_amount - total_spent

        self.budget_display.value = f"Budget is: {self.budget_amount:.2f} " \
                                    f"for period: {self.budget_start_day.strftime('%m/%d/%Y')} " \
                                    f"- {self.budget_end_day.strftime('%m/%d/%Y')}"
        self.spent_display.value = f"Total Spent: {total_spent:.2f}"
        self.remaining_display.value = f"Remaining: {remaining:.2f}"

        # Color coding for remaining amount
        if remaining < 0:
            self.remaining_display.color = ft.colors.RED
        elif remaining < self.budget_amount * 0.2:
            self.remaining_display.color = ft.colors.ORANGE
        else:
            self.remaining_display.color = ft.colors.GREEN

        self.page.update()


    def update_category_filter(self):
        """Update category filter dropdown"""
        category_filter = self.category_filter.value
        filtered_expenses = [Expense]
        if category_filter == "All":
            filtered_expenses = self.expenses
        else:
            return [exp for exp in self.expenses if exp.category == category_filter]
        return filtered_expenses

    def update_all_expenses_list(self, e=None):
        """Update all expenses list with filtering"""
        self.expenses_list.controls.clear()
        filtered_expenses: list[Expense] = []
        filtered_expenses = self.expenses
        recurring_filter = self.recurring_checkbox.value

        if self.category_filter.value and self.category_filter.value !="All":
            filtered_expenses = [exp for exp in self.expenses if exp.category == self.category_filter.value]

        if recurring_filter:
            filtered_expenses = [exp for exp in filtered_expenses if exp.is_recurring != "No"]

        if self.filter_by_period_dropdown.value != "Beginning of Time":
            reference_date = (datetime.now() - timedelta(
                    days=int(self.filter_by_period_dropdown.value.split()[0]))).strftime("%m-%d-%Y %H:%M:%S")
            print(reference_date)
            filtered_expenses = [exp for exp in filtered_expenses if exp.date > reference_date]

        for expense in reversed(filtered_expenses):  # Most recent first
            expense_item = ft.Card(
                content=ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(
                                self.get_category_icon(expense.category),
                                color=ft.colors.WHITE,
                                size=20
                            ),
                            width=40,
                            height=40,
                            bgcolor=self.get_category_color(expense.category),
                            border_radius=20,
                            alignment=ft.alignment.center
                        ),
                        ft.Column([
                            ft.Text(expense.description, weight='bold'),
                            ft.Text(f"{expense.category} • {expense.date}",
                                    size=12, color='grey')
                        ], expand=True, spacing=0.5),
                        ft.Column([ft.Text("Periodic expense", size=12, color='grey'),
                            ft.Text(f"{expense.is_recurring} • {expense.recurring_day}",
                                    size=12, color='grey')],expand=True, spacing=0.5),
                        ft.Row([
                            ft.Text(f"{expense.amount:.2f}",
                                    weight='bold', color=ft.colors.RED_400),
                            ft.IconButton(
                                icon=ft.icons.EDIT,
                                tooltip="Edit",
                                on_click=lambda e, exp_id=expense.id: self.edit_expense(exp_id)
                            ),
                            ft.IconButton(
                                icon=ft.icons.DELETE,
                                icon_size=16,
                                on_click=lambda e, exp_id=expense.id: self.delete_expense(exp_id)
                            )
                        ])
                    ]),
                    padding=15
                ),
                elevation=1
            )
            self.expenses_list.controls.append(expense_item)

        self.page.update()

    def show_snackbar(self, message: str):
        """Show a snackbar message"""
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()


def main(page: ft.Page):
    BudgetApp(page)
    # Initial setup
    #app.update_category_filter()
    #app.update_all_expenses_list()


if __name__ == "__main__":
    ft.app(target=main)