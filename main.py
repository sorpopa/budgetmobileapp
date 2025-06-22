from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.card import MDCard
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.list import OneLineListItem, TwoLineListItem, ThreeLineListItem
from kivymd.uix.list import MDList
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.selectioncontrol import MDSelectionControl
from kivymd.uix.menu import MDDropdownMenu
from datetime import datetime


class ExpenseItem(MDCard):
    def __init__(self, expense, delete_callback, **kwargs):
        super().__init__(**kwargs)
        self.elevation = 2
        self.padding = "8dp"
        self.size_hint_y = None
        self.height = "80dp"
        self.expense = expense
        self.delete_callback = delete_callback

        # Main layout
        main_layout = MDBoxLayout(
            orientation="horizontal",
            adaptive_width=True,
            spacing="10dp"
        )

        # Category icon (simplified as colored box)
        icon_box = MDCard(
            size_hint=(None, None),
            size=("40dp", "40dp"),
            md_bg_color=self.get_category_color(expense['category']),
            elevation=0
        )

        # Expense details
        details_layout = MDBoxLayout(
            orientation="vertical",
            size_hint_x=0.6
        )

        description_label = MDLabel(
            text=expense['description'],
            theme_text_color="Primary",
            font_style="Subtitle1",
            size_hint_y=None,
            height="20dp"
        )

        category_date_label = MDLabel(
            text=f"{expense['category']} • {expense['date']}",
            theme_text_color="Secondary",
            font_style="Caption",
            size_hint_y=None,
            height="15dp"
        )

        details_layout.add_widget(description_label)
        details_layout.add_widget(category_date_label)

        # Amount and delete button
        right_layout = MDBoxLayout(
            orientation="vertical",
            size_hint_x=0.3,
            spacing="5dp"
        )

        amount_label = MDLabel(
            text=f"${expense['amount']:.2f}",
            theme_text_color="Error",
            font_style="Subtitle1",
            halign="right",
            size_hint_y=None,
            height="20dp"
        )

        delete_button = MDIconButton(
            icon="delete",
            theme_icon_color="Error",
            on_release=lambda x: self.delete_callback(expense['id'])
        )

        right_layout.add_widget(amount_label)
        right_layout.add_widget(delete_button)

        # Add all to main layout
        main_layout.add_widget(icon_box)
        main_layout.add_widget(details_layout)
        main_layout.add_widget(right_layout)

        self.add_widget(main_layout)

    def get_category_color(self, category):
        colors = {
            "Food": [1, 0.6, 0, 1],  # Orange
            "Transport": [0, 0.5, 1, 1],  # Blue
            "Entertainment": [0.6, 0, 1, 1],  # Purple
            "Shopping": [0, 0.8, 0, 1],  # Green
            "Bills": [1, 0, 0, 1]  # Red
        }
        return colors.get(category, [0.5, 0.5, 0.5, 1])  # Grey default


class ExpenseTrackerKivy(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expenses = [
            {"id": 1, "amount": 25.50, "description": "Lunch", "category": "Food", "date": "2024-06-04"},
            {"id": 2, "amount": 60.00, "description": "Gas", "category": "Transport", "date": "2024-06-03"},
        ]
        self.categories = ["Food", "Transport", "Entertainment", "Shopping", "Bills"]

    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"

        # Main container
        main_layout = MDBoxLayout(
            orientation="vertical",
            padding="20dp",
            spacing="20dp"
        )

        # Total card
        total_card = self.create_total_card()

        # Add expense form
        form_card = self.create_form_card()

        # Expenses list
        expenses_card = self.create_expenses_card()

        main_layout.add_widget(total_card)
        main_layout.add_widget(form_card)
        main_layout.add_widget(expenses_card)

        return main_layout

    def create_total_card(self):
        card = MDCard(
            size_hint_y=None,
            height="80dp",
            elevation=3,
            padding="20dp"
        )

        layout = MDBoxLayout(
            orientation="horizontal",
            adaptive_height=True
        )

        total_label = MDLabel(
            text=f"Total Spent: ${self.calculate_total():.2f}",
            theme_text_color="Primary",
            font_style="H6",
            halign="center"
        )

        layout.add_widget(total_label)
        card.add_widget(layout)
        return card

    def create_form_card(self):
        card = MDCard(
            size_hint_y=None,
            height="180dp",
            elevation=3,
            padding="20dp"
        )

        layout = MDBoxLayout(
            orientation="vertical",
            spacing="10dp"
        )

        # Title
        title = MDLabel(
            text="Add New Expense",
            theme_text_color="Primary",
            font_style="H6",
            size_hint_y=None,
            height="30dp"
        )

        # Input fields row
        inputs_layout = MDBoxLayout(
            orientation="horizontal",
            spacing="10dp",
            size_hint_y=None,
            height="40dp"
        )

        self.amount_field = MDTextField(
            hint_text="Amount",
            helper_text="Enter amount in dollars",
            input_filter="float",
            size_hint_x=0.3
        )

        self.description_field = MDTextField(
            hint_text="Description",
            helper_text="What did you spend on?",
            size_hint_x=0.5
        )

        # Category spinner (dropdown)
        self.category_spinner = Spinner(
            text="Select Category",
            values=self.categories,
            size_hint_x=0.3
        )

        inputs_layout.add_widget(self.amount_field)
        inputs_layout.add_widget(self.description_field)
        inputs_layout.add_widget(self.category_spinner)

        # Add button
        add_button = MDRaisedButton(
            text="Add Expense",
            size_hint_y=None,
            height="40dp",
            on_release=self.add_expense
        )

        layout.add_widget(title)
        layout.add_widget(inputs_layout)
        layout.add_widget(add_button)

        card.add_widget(layout)
        return card

    def create_expenses_card(self):
        card = MDCard(
            elevation=3,
            padding="20dp"
        )

        layout = MDBoxLayout(
            orientation="vertical",
            spacing="10dp"
        )

        # Title
        title = MDLabel(
            text="Recent Expenses",
            theme_text_color="Primary",
            font_style="H6",
            size_hint_y=None,
            height="30dp"
        )

        # Scrollable list
        scroll = MDScrollView()
        self.expenses_list = MDBoxLayout(
            orientation="vertical",
            spacing="5dp",
            adaptive_height=True
        )

        scroll.add_widget(self.expenses_list)
        self.update_expenses_list()

        layout.add_widget(title)
        layout.add_widget(scroll)

        card.add_widget(layout)
        return card

    def add_expense(self, instance):
        if not all([self.amount_field.text, self.description_field.text,
                    self.category_spinner.text != "Select Category"]):
            # In a real app, you'd show a proper dialog
            print("Please fill all fields")
            return

        try:
            new_expense = {
                "id": len(self.expenses) + 1,
                "amount": float(self.amount_field.text),
                "description": self.description_field.text,
                "category": self.category_spinner.text,
                "date": datetime.now().strftime("%Y-%m-%d")
            }

            self.expenses.append(new_expense)
            self.update_expenses_list()
            self.clear_form()
            print("Expense added!")

        except ValueError:
            print("Invalid amount")

    def update_expenses_list(self):
        self.expenses_list.clear_widgets()

        for expense in reversed(self.expenses):
            expense_item = ExpenseItem(expense, self.delete_expense)
            self.expenses_list.add_widget(expense_item)

    def delete_expense(self, expense_id):
        self.expenses = [e for e in self.expenses if e['id'] != expense_id]
        self.update_expenses_list()
        print("Expense deleted")

    def clear_form(self):
        self.amount_field.text = ""
        self.description_field.text = ""
        self.category_spinner.text = "Select Category"

    def calculate_total(self):
        return sum(expense['amount'] for expense in self.expenses)


if __name__ == "__main__":
    ExpenseTrackerKivy().run()