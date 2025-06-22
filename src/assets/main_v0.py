import flet as ft
from datetime import datetime

class ExpenseTracker:
    def __init__(self, page: ft.Page):
        self.page = page
        self.budget = 100
        self.period = "08.06.2025 - 08.07.2025"
        self.page.adaptive = True
        self.page.expand = True
        self.page.expand_loose = True
        self.expenses =[]
        self.success_text = ft.Text("", color="green", visible=False)

# Component for Home Tab
    @property
    def home_tab(self):
        self.amount_field = ft.TextField(
            label="Amount",
            prefix_text="$",
            width=200,
            keyboard_type='number'
        )

        self.description_field = ft.TextField(
            label="Description",
            width=300,
            hint_text="What did you spend on?"
        )

        self.category_dropdown = ft.Dropdown(
            label="Category",
            width=200,
            options=[
                ft.dropdown.Option("Food"),
                ft.dropdown.Option("Transport"),
                ft.dropdown.Option("Entertainment"),
                ft.dropdown.Option("Shopping"),
                ft.dropdown.Option("Utilities"),
                ft.dropdown.Option("Services"),
                ft.dropdown.Option("Books"),
                ft.dropdown.Option("Childcare"),
                ft.dropdown.Option("Education"),
                ft.dropdown.Option("Insurance"),
                ft.dropdown.Option("Urgency Fund"),
                ft.dropdown.Option("Safety Fund"),
                ft.dropdown.Option("Personal Development"),
                ft.dropdown.Option("Eating Out"),
            ]
        )

        self.was_planned = ft.Dropdown(
            label="Planned",
            width=200,
            options=[ft.dropdown.Option("Planned"),
                ft.dropdown.Option("Not Planned")] )

        self.owner = ft.Dropdown(
            label="Owner",
            width=200,
            options=[ft.dropdown.Option("Full Amount"),
                     ft.dropdown.Option("Split with")])

        # Add button
        add_button = ft.ElevatedButton(
            "Add Expense",
            icon=ft.Icons.ADD,
            on_click=self.add_expense,
            style=ft.ButtonStyle(
                bgcolor="blue",
                color="white"
            )
        )

        # Form card
        form_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Add New Expense", size=20, weight='bold'),
                    ft.Row([self.amount_field, self.was_planned, self.description_field]),
                    ft.Row([self.category_dropdown, self.owner, add_button]),
                ], spacing=15),
                padding=20
            ),
            elevation=3
        )

        estimate_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Estimate New Expense", size=20, weight='bold'),
                    ft.Row([self.amount_field, self.description_field]),
                    ft.Row([self.category_dropdown, add_button]),
                ], spacing=15),
                padding=20
            ),
            elevation=3
        )
        return ft.Column([ft.Text(f"Your budget for {self.period} is {self.budget}."),
            ft.Text("What do you want to do today"), form_card, estimate_card], expand = True
        )
    def add_expense(self, e):
        if not all([self.amount_field.value, self.description_field.value, self.category_dropdown.value]):
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Please fill all fields")))
            return

        try:
            new_expense = {
                "id": len(self.expenses) + 1,
                "amount": float(self.amount_field.value),
                "description": self.description_field.value,
                "category": self.category_dropdown.value,
                "date": datetime.now().strftime("%Y-%m-%d")
            }

            self.expenses.append(new_expense)
            self.update_expenses_list()
            self.clear_form()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Expense added!")))

        except ValueError:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Invalid amount")))

    def update_expenses_list(self):
        self.expenses_list.controls.clear()

        for expense in reversed(self.expenses):  # Most recent first
            expense_item = ft.Card(
                content=ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(
                                self.get_category_icon(expense['category']),
                                color="white",
                                size=20
                            ),
                            width=40,
                            height=40,
                            bgcolor=self.get_category_color(expense['category']),
                            border_radius=20,
                            alignment=ft.alignment.center
                        ),
                        ft.Column([
                            ft.Text(expense['description'], weight='bold'),
                            ft.Text(f"{expense['category']} • {expense['date']}",
                                    size=12, color='grey')
                        ], expand=True, spacing=2),
                        ft.Column([
                            ft.Text(f"${expense['amount']:.2f}",
                                    weight='bold', color="red"),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                icon_size=16,
                                on_click=lambda e, exp_id=expense['id']: self.delete_expense(exp_id)
                            )
                        ], horizontal_alignment='end')
                    ]),
                    padding=15
                ),
                elevation=1
            )
            self.expenses_list.controls.append(expense_item)

        return self.expenses_list

    def delete_expense(self, expense_id):
        self.expenses = [e for e in self.expenses if e['id'] != expense_id]
        self.update_expenses_list()
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Expense deleted")))

    def clear_form(self):
        self.amount_field.value = ""
        self.description_field.value = ""
        self.category_dropdown.value = None
        self.page.update()

    def calculate_total(self):
        return sum(expense['amount'] for expense in self.expenses)

    def get_category_icon(self, category):
        icons_map = {
            "Food": ft.Icons.RESTAURANT,
            "Transport": ft.Icons.DIRECTIONS_CAR,
            "Entertainment": ft.Icons.MOVIE,
            "Shopping": ft.Icons.SHOPPING_BAG,
            "Bills": ft.Icons.RECEIPT
        }
        return icons_map.get(category, ft.Icons.MONEY)

    def get_category_color(self, category):
        colors = {
            "Food": "orange",
            "Transport": "blue",
            "Entertainment": "purple",
            "Shopping": "green",
            "Bills": "red"
        }
        return colors.get(category, 'grey')

    # Component for All Expenses page
    def all_expenses(self):
        # Expenses list
        self.expenses_list = ft.ListView(expand=True, spacing=10)
        self.update_expenses_list()
        expenses_list = self.update_expenses_list()

        # Total display
        total_card = ft.Card(
            content=ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=30),
                    ft.Column([
                        ft.Text("Total Spent", size=14, color='grey'),
                        ft.Text(f"${self.calculate_total():.2f}", size=24, weight='bold')
                    ], spacing=2)
                ], alignment='center'),
                padding=20
            ),
            elevation=3
        )


        return ft.Column([total_card, expenses_list], expand=True, spacing=20)

    # Add button handler
    def handle_add_expense(self):
        self.success_text.value = "Expense added successfully!"
        self.success_text.visible = True


    add_button = ft.ElevatedButton("Add", icon=ft.icons.CHECK, on_click=handle_add_expense)

# Component for Page Two
    def planned_expenses(self):
        return ft.Text(f"You can add plannned expenses here", size=24)

    def wish_list(self):
        return ft.Text(f"You can add what you would like to buy here.", size=24)


# Main app
def main(page: ft.Page):
    page.title = "Flet Tabs with Components"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.adaptive
    page.expand = True
    page.auto_scroll = True

    expenses = ExpenseTracker(page)
    user_name = ft.TextField(label="Enter your name")
    content_column = ft.Column(expand=True)

    def update_content(index):
        content_column.controls.clear()
        if index == 0:
            content_column.controls.append(expenses.home_tab)
        elif index == 1:
            content_column.controls.append(expenses.all_expenses())
        elif index == 2:
            content_column.controls.append(expenses.planned_expenses)
        elif index == 3:
            content_column.controls.append(expenses.wish_list)
        page.update()

    tabs = ft.Tabs(
        selected_index=0,
        on_change=lambda e: update_content(e.control.selected_index),
        tabs=[
            ft.Tab(text="Home"),
            ft.Tab(text="All Expenses"),
            ft.Tab(text="Upcoming Expenses"),
            ft.Tab(text="Wish List"),
        ],
        expand=True,
        adaptive=True
    )

    update_content(0)

    page.add(tabs,content_column)

ft.app(target=main)
