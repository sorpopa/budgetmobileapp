import flet as ft
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, date, timedelta
import json
import os


class BudgetApp:
    def __init__(self):
        self.db = None
        self.page = None
        self.budget_amount = 0
        self.start_date = datetime.now().replace(day=1)
        self.end_date = datetime.now()
        self.expenses = []
        self.expense_form_dialog = None
        self.edit_expense_dialog = None
        self.editing_expense_id = None
        self.recurring_expenses = []
        self.recurring_expense_timestamps = []

    def initialize_firebase(self):
        """Initialize Firebase connection"""
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                print("🔧 Initializing Firebase...")

                # Method 1: Using service account key file (RECOMMENDED)
                service_key_path = "serviceAccountKey.json"  # Update this path
                if os.path.exists(service_key_path):
                    print(f"📁 Found service account key at: {service_key_path}")
                    cred = credentials.Certificate(service_key_path)
                    firebase_admin.initialize_app(cred)
                    print("✅ Firebase initialized with service account key")

            # Test the connection
            self.db = firestore.client()

            # Simple test to verify connection works
            test_ref = self.db.collection('_test').document('connection')
            test_ref.set({'test': True, 'timestamp': datetime.now()})
            test_ref.delete()  # Clean up test document

            print("✅ Firebase connection successful!")
            return True

        except Exception as e:
            print(f"❌ Firebase initialization error: {e}")
            print("This usually means:")
            print("1. Service account key file is missing or invalid")
            print("2. Firebase project doesn't exist")
            print("3. Firestore is not enabled for your project")
            print("4. Network connectivity issues")
            self.db = None
            return False

    def main(self, page: ft.Page):
        self.page = page
        page.title = "Budget Planner"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 20

        # Initialize Firebase
        if not self.initialize_firebase():
            page.add(ft.Text("Failed to connect to Firebase. Please check your configuration.", color="red"))
            return

        # Test Firebase connection and display data
        self.test_firebase_connection()

        self.expenses_list = ft.ListView(spacing=10, padding=20, auto_scroll=True, height=300)
        self.recurring_checkbox = ft.Checkbox(label="Recurring expenses", on_change=self.update_expenses_list)
        self.filter_category_options = [ft.dropdown.Option("All")]
        self.filter_category_options += self.show_expense_category()
        self.category_filter = ft.Dropdown(
            label="Filter by Category",
            options=self.filter_category_options,
            value="All",
            width=200,
            # Flet automatically passes an event parameter to the method, that is why it was needed to add e=None as a parameter
            # to update_all_expenses_list()
            on_change=self.update_expenses_list
        )

        self.period_filter = ft.Tabs(is_secondary=True, selected_index=0,
                                     on_change=self.update_expenses_list,
                                     tabs=[
                                         ft.Tab(text="All"),
                                         ft.Tab(text="1M"),
                                         ft.Tab(text="2M"),
                                         ft.Tab(text="3M"),
                                         ft.Tab(text="6M"),
                                         ft.Tab(text="12M"),
                                     ])

        # Load initial data
        self.load_budget_data()
        self.load_expenses()

        # Create tabs
        self.overview_tab = self.create_overview_tab()
        self.expenses_tab = self.create_expenses_tab()

        tabs = ft.Tabs(
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
            ],
        )

        page.add(tabs)


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
        # Budget summary
        self.budget_summary = ft.Container(
            content=ft.Column([
                ft.Text("Budget Summary", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(),
            ]),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            margin=ft.margin.only(top=20)
        )
        self.pie_chart=ft.PieChart(
                    sections=self.create_pie_sections(),
                    sections_space=0.1,
                    center_space_radius=20,
                )

        self.update_budget_summary()

        return ft.Container(
            content=ft.ListView([
                ft.Text("Budget Configuration", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.ElevatedButton(
                        text="Configure Budget",
                        icon=ft.icons.ADD,
                        style=ft.ButtonStyle(
                            color=ft.colors.WHITE,
                            bgcolor=ft.colors.LIME_200,
                            shape=ft.RoundedRectangleBorder(radius=7)
                        ),
                        on_click=self.show_add_budget_dialog
                    ),
                ]),
                self.budget_summary,
                self.pie_chart
            ],
            auto_scroll=True),
            expand=True
        )

    def create_expenses_tab(self):
        """Create the expenses tab with list of all expenses"""

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

        self.page.overlay.append(self.recurring_date_picker)

        self.update_displays()

        return ft.Container(
            content=ft.Column(
                [ft.Row([
                self.category_filter,
                self.recurring_checkbox
            ]),
                ft.Text("Expenses", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                self.period_filter,
                ft.Column(
                    [self.expenses_list],
                    scroll=ft.ScrollMode.AUTO
                ),
                ft.Row([
                    ft.FloatingActionButton(icon=ft.icons.ADD,
                                            bgcolor=ft.colors.LIME_300,
                                            data=0,
                                            on_click=self.show_add_expense_dialog,
                                            ),
                ], alignment=ft.MainAxisAlignment.END)

            ]),
            padding=20,
            expand=True,
        )


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

    def get_recurring_period(self, period):
        nr_of_days = 0
        if period == 'Monthly':
            nr_of_days = 30
        elif period == "Yearly":
            nr_of_days == 30*12
        else:
            nr_of_days == int(period.split()[0])*30
        return nr_of_days

    def automaticaly_update_expense(self):
        print(self.recurring_expenses)
        for expense in self.recurring_expenses:
            try:
                if expense['recurring day'] <= datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
                    print("Automatically updating expense")
                    new_date = datetime.fromisoformat(expense['recurring day'].replace('Z', '')) + timedelta(
                        self.get_recurring_period(expense['is recurring']))
                    print(f"Old date is {expense['recurring day']} and New date is {new_date}")
                    expense_data = {
                        'amount': expense['amount'],
                        'category': expense['category'],
                        'description': expense['description'],
                        'date': expense['date'],
                        'timestamp': expense['timestamp'],
                        'is recurring': expense['is recurring'],
                        'recurring day': new_date.strftime('%Y-%m-%d %H:%M:%S')
                        }


                    # Save to Firebase if available
                    if self.db:
                        doc_ref = self.db.collection('expenses').add(expense_data)
                        expense_data['id'] = expense['id']
                        print(f"✅ Expense saved successfully with ID: {expense_data['id']}")
                        print(f"📊 Expense data: {expense_data}")
                        doc_ref = self.db.collection('expenses').document(expense['id'])
                        doc_ref.update({'recurring day':new_date.strftime('%Y-%m-%d %H:%M:%S')})
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


    def update_expenses_list(self, e=None):
        """Update the expenses list display"""
        self.expenses_list.controls.clear()
        filtered_expenses = self.expenses

        if not self.expenses:
            self.expenses_list.controls.append(
                ft.Text("No expenses recorded yet.", color=ft.colors.GREY_600)
            )
        else:
            recurring_filter = self.recurring_checkbox.value
            if self.category_filter.value and self.category_filter.value != 'All':
                filtered_expenses = [exp for exp in self.expenses if exp['category'] == self.category_filter.value]

            if recurring_filter:
                filtered_expenses = [exp for exp in filtered_expenses if exp['is recurring'] != "No"]

            if self.period_filter.selected_index == 1:
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")]
            elif self.period_filter.selected_index == 2:
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")]

            elif self.period_filter.selected_index == 3:
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")]

            elif self.period_filter.selected_index == 4:
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")]

            elif self.period_filter.selected_index == 5:
                filtered_expenses = [exp for exp in filtered_expenses if exp['date'] >=
                                     (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")]

            for expense in reversed(filtered_expenses):
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
                                    ft.Text("Is Recurring: "),
                                    ft.Text(expense.get('is recurring', ''), size=12, color=ft.colors.GREY_500),
                                ]),
                                ft.Row([
                                    ft.Text("Recurring day: "),
                                    ft.Text(expense.get('recurring day', ''), size=12, color=ft.colors.GREY_500)
                                ]),
                            ],expand=True, spacing=1),
                            ft.Column([
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
                self.expenses_list.controls.append(expense_card)

        self.page.update()

    def show_add_budget_dialog(self, e):
        """Show dialog to configure budget"""
        self.budget_input = ft.TextField(
            label="Budget Amount",
            value=str(self.budget_amount),
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
                self.start_date_button,
                self.end_date_button
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
        drop_down_options = [
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
        return drop_down_options


    def show_add_expense_dialog(self, e):
        """Show dialog to add new expense"""

        amount_field = ft.TextField(label="Amount", keyboard_type=ft.KeyboardType.NUMBER, width=200)
        category_field = ft.Dropdown(
            label="Category",
            width=200,
            options=self.show_expense_category()
        )
        description_field = ft.TextField(label="Description", multiline=True, width=300)

        recurring_period = ft.Dropdown(
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

        self.recurring_day = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.recurring_date_picker = ft.DatePicker(
            on_change=self.on_recurring_date_change,
            first_date=datetime(2025, 1, 1),
            last_date=datetime(2030, 12, 31),
            current_date=datetime.now()
        )

        self.recurring_date_button = ft.TextButton(
            text=f"Recurring Date: {self.recurring_day}",
            icon=ft.icons.CALENDAR_MONTH,
            on_click=self.open_recurring_date_picker,
            width=200
        )

        def save_expense(e):
            try:
                amount = float(amount_field.value or 0)
                category = category_field.value or ""
                description = description_field.value or ""
                is_recurring = recurring_period.value
                if is_recurring not in ['No', 'All']:
                    recurring_day = self.recurring_day.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    recurring_day = None


                if amount <= 0:
                    self.show_snackbar("Please enter a valid amount")
                    return

                expense_data = {
                    'amount': amount,
                    'category': category,
                    'description': description,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': datetime.now(),
                    'is recurring': is_recurring,
                    'recurring day': recurring_day
                }
                print(f"Expense data is saved as {expense_data}")

                # Save to Firebase if available
                if self.db:
                    doc_ref = self.db.collection('expenses').add(expense_data)
                    expense_data['id'] = doc_ref[1].id
                    print(f"✅ Expense saved successfully with ID: {expense_data['id']}")
                    print(f"📊 Expense data: {expense_data}")
                else:
                    # Generate a temporary ID for local storage
                    expense_data['id'] = f"local_{len(self.expenses)}"
                    print("⚠️ Firebase not available, expense saved locally only")

                self.expenses.append(expense_data)
                self.update_expenses_list()
                self.update_budget_summary()
                self.pie_chart.sections=self.create_pie_sections()
                self.pie_chart.update()
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
            title=ft.Text("Add New Expense"),
            content=ft.Column([
                amount_field,
                category_field,
                description_field,
                recurring_period,
                self.recurring_date_button
            ], height=300),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_dialog()),
                ft.ElevatedButton("Save", on_click=save_expense)
            ]
        )

        self.page.overlay.append(self.recurring_date_picker)

        self.page.dialog = self.expense_form_dialog
        self.expense_form_dialog.open = True
        self.page.update()

    def show_edit_expense_dialog(self, expense_id):
        """Show dialog to edit existing expense"""
        expense = next((exp for exp in self.expenses if exp.get('id') == expense_id), None)
        if not expense:
            return

        self.editing_expense_id = expense_id

        amount_field = ft.TextField(label="Amount", value=str(expense.get('amount', 0)),
                                    keyboard_type=ft.KeyboardType.NUMBER, width=200)
        category_field = ft.TextField(label="Category", value=expense.get('category', ''), width=200)
        description_field = ft.TextField(label="Description", value=expense.get('description', ''),
                                         multiline=True, width=300)

        def update_expense(e):
            try:
                amount = float(amount_field.value or 0)
                category = category_field.value or ""
                description = description_field.value or ""

                if amount <= 0:
                    self.show_snackbar("Please enter a valid amount")
                    return

                # Update in Firebase
                self.db.collection('expenses').document(expense_id).update({
                    'amount': amount,
                    'category': category,
                    'description': description,
                })

                # Update local data
                for i, exp in enumerate(self.expenses):
                    if exp.get('id') == expense_id:
                        self.expenses[i].update({
                            'amount': amount,
                            'category': category,
                            'description': description
                        })
                        break

                self.update_expenses_list()
                self.update_budget_summary()
                self.edit_expense_dialog.open = False
                self.page.update()
                self.show_snackbar("Expense updated successfully!")

            except ValueError:
                self.show_snackbar("Please enter a valid amount")
            except Exception as ex:
                self.show_snackbar(f"Error updating expense: {ex}")

        self.edit_expense_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Expense"),
            content=ft.Column([
                amount_field,
                category_field,
                description_field
            ], height=200),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_edit_dialog()),
                ft.ElevatedButton("Update", on_click=update_expense)
            ]
        )

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

    def close_budget_dialog(self):
        self.budget_form_dialog.open = False
        self.page.update()

    def close_dialog(self):
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

    def save_budget(self, e):
        """Save budget configuration"""
        try:
            self.budget_amount = float(self.budget_input.value or 0)
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
            print("⚠️ Firebase not initialized, cannot save budget data")
            return

        try:
            budget_data = {
                'amount': self.budget_amount,
                'start_date': self.start_date,
                'end_date': self.end_date,
                'updated_at': datetime.now()
            }

            # Save or update budget document
            self.db.collection('budget').document('current').set(budget_data)
            print(f"✅ Budget data saved successfully: {budget_data}")

        except Exception as e:
            print(f"❌ Error saving budget data: {e}")

    def load_budget_data(self):
        """Load budget data from Firebase"""
        if not self.db:
            print("⚠️ Firebase not initialized, skipping budget data load")
            return

        try:
            doc = self.db.collection('budget').document('current').get()
            if doc.exists:
                data = doc.to_dict()
                self.budget_amount = data.get('amount', 0)
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
            return

        try:
            expenses_ref = self.db.collection('expenses').order_by('timestamp', direction=firestore.Query.DESCENDING)
            docs = expenses_ref.stream()

            self.expenses = []
            for doc in docs:
                expense_data = doc.to_dict()
                expense_data['id'] = doc.id
                self.expenses.append(expense_data)
                if expense_data['is recurring'] != 'No' and expense_data['date'] not in self.recurring_expense_timestamps:
                    self.recurring_expenses.append(expense_data)
                    self.recurring_expense_timestamps.append(expense_data['date'])
            print(f"✅ Loaded {len(self.expenses)} expenses from Firebase")

            self.automaticaly_update_expense()
            self.update_expenses_list()

            print(self.recurring_expenses)
            print(self.recurring_expense_timestamps)

        except Exception as e:
            print(f"❌ Error loading expenses: {e}")

    def update_budget_summary(self):
        """Update the budget summary display"""
        total_expenses = sum(expense.get('amount', 0) for expense in self.expenses)
        remaining_budget = self.budget_amount - total_expenses
        percentage_used = (total_expenses / self.budget_amount * 100) if self.budget_amount > 0 else 0

        # Determine color based on budget usage
        if percentage_used >= 90:
            remaining_color = ft.colors.RED
        elif percentage_used >= 70:
            remaining_color = ft.colors.ORANGE
        else:
            remaining_color = ft.colors.GREEN

        self.budget_summary.content = ft.Column([
            ft.Text("Budget Summary", size=20, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Row([
                ft.Text("Budget Amount:", weight=ft.FontWeight.BOLD),
                ft.Text(f"${self.budget_amount:.2f}")
            ]),
            ft.Row([
                ft.Text("Total Expenses:", weight=ft.FontWeight.BOLD),
                ft.Text(f"${total_expenses:.2f}")
            ]),
            ft.Row([
                ft.Text("Remaining:", weight=ft.FontWeight.BOLD),
                ft.Text(f"${remaining_budget:.2f}", color=remaining_color)
            ]),
            ft.Row([
                ft.Text("Budget Used:", weight=ft.FontWeight.BOLD),
                ft.Text(f"{percentage_used:.1f}%", color=remaining_color)
            ]),
            ft.ProgressBar(value=percentage_used / 100, color=remaining_color, height=10),
        ])

        if self.page:
            self.page.update()

    def show_snackbar(self, message):
        """Show a snackbar with a message"""
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()

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

    def create_pie_sections(self):
        expense_categories = {}
        for expense in self.expenses:
            if expense['category'] in expense_categories.keys():
                expense_categories[expense['category']] +=expense['amount']
            else:
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

        pie_sections =[ft.PieChartSection(
            value=amount,
            title=category,
            radius=100,
            color=category_colors.get(category, ft.colors.GREY_500)
        )
            for category, amount in expense_categories.items()
        ]

        return pie_sections






def main(page: ft.Page):
    app = BudgetApp()
    app.main(page)


if __name__ == "__main__":
    ft.app(target=main)