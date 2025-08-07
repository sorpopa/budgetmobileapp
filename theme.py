import flet as ft

class Themecolors:
    def __init__(self, page):
        self.page = page

    @property
    def is_dark(self):
        return self.page.theme_mode == ft.ThemeMode.DARK

    @property
    def text_primary(self):
        return ft.colors.WHITE70 if self.is_dark else ft.colors.GREY_800

    @property
    def text_logo(self):
        return ft.colors.WHITE24 if self.is_dark else ft.colors.WHITE

    @property
    def text_secondary(self):
        return ft.colors.GREY_300 if self.is_dark else ft.colors.GREY_600

    @property
    def blue_text(self):
        return ft.colors.BLUE_300 if self.is_dark else ft.colors.BLUE_600

    @property
    def purple_text(self):
        return ft.colors.PURPLE_200 if self.is_dark else ft.colors.PURPLE_400

    @property
    def background(self):
        return ft.colors.GREY_900 if self.is_dark else ft.colors.GREY_50

    @property
    def button_background(self):
        return ft.colors.GREY_700 if self.is_dark else ft.colors.GREY_100

    @property
    def auth_background_primary(self):
        return ft.colors.TEAL_800 if self.is_dark else ft.colors.TEAL_400

    @property
    def auth_background_secondary(self):
        return ft.colors.GREY_800 if self.is_dark else ft.colors.TEAL_800

    @property
    def auth_background_midle(self):
        return ft.colors.TEAL_900 if self.is_dark else ft.colors.TEAL_600

    @property
    def logo_primary(self):
        return ft.colors.GREY_400 if self.is_dark else ft.colors.WHITE

    @property
    def logo_on_orange(self):
        return ft.colors.ORANGE_100 if self.is_dark else ft.colors.ORANGE_700

    @property
    def logo_on_blue(self):
        return ft.colors.BLUE_50 if self.is_dark else ft.colors.BLUE

    @property
    def logo_in_blue(self):
        return ft.colors.BLUE_100 if self.is_dark else ft.colors.BLUE_700

    @property
    def sign_in(self):
        return ft.colors.DEEP_ORANGE_800 if self.is_dark else ft.colors.DEEP_ORANGE_300

    @property
    def teal_card(self):
        return ft.colors.TEAL_800 if self.is_dark else ft.colors.TEAL_50

    @property
    def teal_text(self):
        return ft.colors.TEAL_ACCENT_700 if self.is_dark else ft.colors.TEAL_ACCENT_400

    @property
    def teal_text_secondary(self):
        return ft.colors.TEAL_300 if self.is_dark else ft.colors.TEAL_600

    @property
    def orange_card(self):
        return ft.colors.DEEP_ORANGE_800 if self.is_dark else ft.colors.ORANGE_50

    @property
    def green_card(self):
        return ft.colors.GREEN_900 if self.is_dark else ft.colors.GREEN_50

    @property
    def red_card(self):
        return ft.colors.RED_800 if self.is_dark else ft.colors.RED_50

    @property
    def purple_card(self):
        return ft.colors.PURPLE_800 if self.is_dark else ft.colors.PURPLE_50

    @property
    def blue_card(self):
        return ft.colors.BLUE_800 if self.is_dark else ft.colors.BLUE_50

    @property
    def cyan_card(self):
        return ft.colors.CYAN_800 if self.is_dark else ft.colors.CYAN_50

    @property
    def yellow_card(self):
        return ft.colors.YELLOW_900 if self.is_dark else ft.colors.YELLOW_100

    @property
    def pink_card(self):
        return ft.colors.PINK_900 if self.is_dark else ft.colors.PINK_100

    @property
    def progress_bar(self):
        return ft.colors.GREY_400 if self.is_dark else ft.colors.GREY_100

    @property
    def container_primary(self):
        return ft.colors.GREY_200 if self.is_dark else ft.colors.GREY_50

    @property
    def surface(self):
        return ft.colors.GREY_800 if self.is_dark else ft.colors.WHITE