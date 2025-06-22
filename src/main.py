import flet as ft
import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class Expense:
    def __init__(self, amount: float, category: str, description: str, date: str = None, expense_id: int = None):
        self.id = expense_id or int(datetime.now().timestamp() * 1000)
        self.amount = amount
        self.category = category
        self.description = description
        self.date = date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'category': self.category,
            'description': self.description,
            'date': self.date,
            'is_recurring': self.is_recurring,
            'recurring_date': self.recurring_date
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            amount=data['amount'],
            category=data['category'],
            description=data['description'],
            date=data['date'],
            expense_id=data['id']
        )


class BudgetApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Budget Planning App"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window_width = 800
        self.page.window_height = 600

        # Data storage
        self.expenses: List[Expense] = []
        self.budget_amount = 0.0
        self.budget_start_day = 1
        self.data_file = "budget_data.json"

        # Load data
        self.load_data()

        # UI Components
        self.tabs = None
        self.overview_tab = None
        self.all_expenses_tab = None

        # Overview tab components
        self.budget_input = ft.TextField(
            label="Monthly Budget",
            value=str(self.budget_amount),
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        self.start_day_dropdown = ft.Dropdown(
            label="Budget Start Day",
            value=str(self.budget_start_day),
            options=[ft.dropdown.Option(str(i)) for i in range(1, 32)],
            width=200
        )
        self.budget_display = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
        self.spent_display = ft.Text("", size=16)
        self.remaining_display = ft.Text("", size=16)

        # Expense form components
        self.expense_dialog = None
        self.amount_field = ft.TextField(label="Amount", keyboard_type=ft.KeyboardType.NUMBER, width=200)
        self.category_field = ft.TextField(label="Category", width=200)
        self.description_field = ft.TextField(label="Description", width=300, multiline=True)

        # All expenses tab components
        self.category_filter = ft.Dropdown(
            label="Filter by Category",
            options=[ft.dropdown.Option("All")],
            value="All",
            width=200
        )
        self.expenses_list = ft.Column()

        # Recent expenses display
        self.recent_expenses = ft.Column()

        self.setup_ui()
        self.update_displays()

    def load_data(self):
        """Load data from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.budget_amount = data.get('budget_amount', 0.0)
                    self.budget_start_day = data.get('budget_start_day', 1)
                    expenses_data = data.get('expenses', [])
                    self.expenses = [Expense.from_dict(exp) for exp in expenses_data]
            except Exception as e:
                print(f"Error loading data: {e}")

    def save_data(self):
        """Save data to JSON file"""
        try:
            data = {
                'budget_amount': self.budget_amount,
                'budget_start_day': self.budget_start_day,
                'expenses': [exp.to_dict() for exp in self.expenses]
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")

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
            expand=1
        )

        # Create expense dialog
        self.create_expense_dialog()

        # Add to page
        self.page.add(self.tabs)

    def create_overview_content(self):
        """Create the overview tab content"""
        return ft.Container(
            content=ft.Column([
                ft.Text("Budget Configuration", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.budget_input,
                    self.start_day_dropdown,
                    ft.ElevatedButton(
                        text="Save Budget",
                        on_click=self.save_budget_config
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
                ft.Row([
                    ft.ElevatedButton(
                        text="Add Expense",
                        on_click=self.open_expense_dialog,
                        bgcolor=ft.colors.BLUE,
                        color=ft.colors.WHITE
                    )
                ]),
                ft.Text("Recent Expenses (Last 10)", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=self.recent_expenses,
                    height=300,
                    border=ft.border.all(1, ft.colors.GREY_300),
                    padding=10
                )
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
                    ft.ElevatedButton(
                        text="Apply Filter",
                        on_click=self.filter_expenses
                    )
                ]),
                ft.Divider(),
                ft.Container(
                    content=self.expenses_list,
                    expand=True,
                    border=ft.border.all(1, ft.colors.GREY_300),
                    padding=10
                )
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
                    self.amount_field,
                    self.category_field,
                    self.description_field
                ], height=200, scroll=ft.ScrollMode.AUTO),
                width=400
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_expense_dialog),
                ft.ElevatedButton("Save", on_click=self.save_expense)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

    def save_budget_config(self, e):
        """Save budget configuration"""
        try:
            self.budget_amount = float(self.budget_input.value or 0)
            self.budget_start_day = int(self.start_day_dropdown.value)
            self.save_data()
            self.update_displays()
            self.show_snackbar("Budget configuration saved!")
        except ValueError:
            self.show_snackbar("Please enter valid numbers!")

    def open_expense_dialog(self, e):
        """Open the expense input dialog"""
        self.amount_field.value = ""
        self.category_field.value = ""
        self.description_field.value = ""
        self.page.dialog = self.expense_dialog
        self.expense_dialog.open = True
        self.page.update()

    def close_expense_dialog(self, e):
        """Close the expense input dialog"""
        self.expense_dialog.open = False
        self.page.update()

    def save_expense(self, e):
        """Save a new expense"""
        try:
            amount = float(self.amount_field.value or 0)
            category = self.category_field.value.strip()
            description = self.description_field.value.strip()

            if amount <= 0:
                self.show_snackbar("Please enter a valid amount!")
                return

            if not category:
                self.show_snackbar("Please enter a category!")
                return

            # Create new expense
            expense = Expense(amount, category, description)
            self.expenses.append(expense)

            # Save data
            self.save_data()

            # Update displays
            self.update_displays()
            self.update_category_filter()
            self.update_all_expenses_list()

            # Close dialog
            self.close_expense_dialog(e)
            self.show_snackbar("Expense added successfully!")

        except ValueError:
            self.show_snackbar("Please enter a valid amount!")

    def edit_expense(self, expense_id: int):
        """Edit an existing expense"""
        expense = next((exp for exp in self.expenses if exp.id == expense_id), None)
        if expense:
            self.amount_field.value = str(expense.amount)
            self.category_field.value = expense.category
            self.description_field.value = expense.description

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

    def delete_expense(self, expense_id: int):
        """Delete an expense"""
        self.expenses = [exp for exp in self.expenses if exp.id != expense_id]
        self.save_data()
        self.update_displays()
        self.update_all_expenses_list()
        self.show_snackbar("Expense deleted successfully!")

    def filter_expenses(self, e):
        """Filter expenses by category"""
        self.update_all_expenses_list()

    def update_displays(self):
        """Update all display components"""
        self.update_budget_summary()
        self.update_recent_expenses()

    def update_budget_summary(self):
        """Update budget summary display"""
        total_spent = sum(exp.amount for exp in self.expenses)
        remaining = self.budget_amount - total_spent

        self.budget_display.value = f"Monthly Budget: ${self.budget_amount:.2f}"
        self.spent_display.value = f"Total Spent: ${total_spent:.2f}"
        self.remaining_display.value = f"Remaining: ${remaining:.2f}"

        # Color coding for remaining amount
        if remaining < 0:
            self.remaining_display.color = ft.colors.RED
        elif remaining < self.budget_amount * 0.2:
            self.remaining_display.color = ft.colors.ORANGE
        else:
            self.remaining_display.color = ft.colors.GREEN

        self.page.update()

    def update_recent_expenses(self):
        """Update recent expenses display"""
        recent = sorted(self.expenses, key=lambda x: x.date, reverse=True)[:10]

        self.recent_expenses.controls.clear()

        if not recent:
            self.recent_expenses.controls.append(
                ft.Text("No expenses yet", italic=True, color=ft.colors.GREY_600)
            )
        else:
            for expense in recent:
                self.recent_expenses.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(f"${expense.amount:.2f}", weight=ft.FontWeight.BOLD),
                                ft.Text(expense.category, size=12, color=ft.colors.BLUE_GREY_600),
                            ], tight=True),
                            ft.Column([
                                ft.Text(expense.description, expand=True),
                                ft.Text(expense.date.split()[0], size=12, color=ft.colors.GREY_600),
                            ], expand=True, tight=True),
                        ]),
                        padding=10,
                        margin=ft.margin.only(bottom=5),
                        border=ft.border.all(1, ft.colors.GREY_300),
                        border_radius=5
                    )
                )

        self.page.update()

    def update_category_filter(self):
        """Update category filter dropdown"""
        categories = set(exp.category for exp in self.expenses)
        options = [ft.dropdown.Option("All")] + [ft.dropdown.Option(cat) for cat in sorted(categories)]
        self.category_filter.options = options
        self.page.update()

    def update_all_expenses_list(self):
        """Update all expenses list with filtering"""
        filtered_expenses = self.expenses

        if self.category_filter.value and self.category_filter.value != "All":
            filtered_expenses = [exp for exp in self.expenses if exp.category == self.category_filter.value]

        # Sort by date (newest first)
        filtered_expenses = sorted(filtered_expenses, key=lambda x: x.date, reverse=True)

        self.expenses_list.controls.clear()

        if not filtered_expenses:
            self.expenses_list.controls.append(
                ft.Text("No expenses found", italic=True, color=ft.colors.GREY_600)
            )
        else:
            for expense in filtered_expenses:
                self.expenses_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(f"${expense.amount:.2f}", weight=ft.FontWeight.BOLD, size=16),
                                ft.Text(expense.category, size=12, color=ft.colors.BLUE_GREY_600),
                                ft.Text(expense.date.split()[0], size=10, color=ft.colors.GREY_600),
                            ], tight=True, spacing=2),
                            ft.Column([
                                ft.Text(expense.description, expand=True, size=14),
                            ], expand=True, tight=True),
                            ft.Column([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    tooltip="Edit",
                                    on_click=lambda e, exp_id=expense.id: self.edit_expense(exp_id)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    tooltip="Delete",
                                    icon_color=ft.colors.RED,
                                    on_click=lambda e, exp_id=expense.id: self.delete_expense(exp_id)
                                ),
                            ], tight=True, spacing=0),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=15,
                        margin=ft.margin.only(bottom=10),
                        border=ft.border.all(1, ft.colors.GREY_300),
                        border_radius=8,
                        bgcolor=ft.colors.WHITE
                    )
                )

        self.page.update()

    def show_snackbar(self, message: str):
        """Show a snackbar message"""
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()


def main(page: ft.Page):
    app = BudgetApp(page)
    # Initial setup
    app.update_category_filter()
    app.update_all_expenses_list()


if __name__ == "__main__":
    ft.app(target=main)