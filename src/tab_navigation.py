import flet as ft

# Component for Home Tab
def home_tab(user_name_field: ft.TextField):
    return ft.Column([
        ft.Text("Main Page", size=30, weight="bold"),
        user_name_field,
        ft.Text("Enter your name and switch tabs to see it reflected."),
    ])

# Component for Page One
def page_one_tab(name: str):
    return ft.Text(f"Hello {name or 'Guest'}, welcome to Page One!", size=24)

# Component for Page Two
def page_two_tab(name: str):
    return ft.Text(f"This is Page Two, {name or 'Guest'}!", size=24)

# Main app
def main(page: ft.Page):
    page.title = "Flet Tabs with Components"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 400
    page.window_height = 600

    user_name = ft.TextField(label="Enter your name")
    content_column = ft.Column(expand=True)

    def update_content(index):
        content_column.controls.clear()
        if index == 0:
            content_column.controls.append(home_tab(user_name))
        elif index == 1:
            content_column.controls.append(page_one_tab(user_name.value))
        elif index == 2:
            content_column.controls.append(page_two_tab(user_name.value))
        page.update()

    tabs = ft.Tabs(
        selected_index=0,
        on_change=lambda e: update_content(e.control.selected_index),
        tabs=[
            ft.Tab(text="Home", icon=ft.Icons.HOME),
            ft.Tab(text="Page 1", icon=ft.Icons.PERSON),
            ft.Tab(text="Page 2", icon=ft.Icons.BOOK),
        ],
        expand=True
    )

    update_content(0)

    page.add(
        ft.AppBar(title=ft.Text("Flet Tabs App"), center_title=True, bgcolor="#BBDEFB"),
        tabs,
        content_column
    )

ft.app(target=main)
