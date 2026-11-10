"""Shared EchoDiary palette and application stylesheet."""

PALETTE = {
    "charcoal": "#171923",
    "storm_teal": "#344C59",
    "dusty_violet": "#9A8BB8",
    "soft_sage": "#B4C69A",
    "warm_off_white": "#F5F3EF",
    "white": "#FFFFFF",
    "primary_text": "#252833",
    "secondary_text": "#777985",
    "border": "#E5E2DE",
    "muted_red": "#8B4E4C",
    "muted_amber": "#8F6740",
    "muted_green": "#506344",
    "light_violet": "#F0ECF4",
}

PRIORITY_STYLES = {
    "High": {"foreground": "#8B4E4C", "background": "#F5E9E7"},
    "Medium": {"foreground": "#8F6740", "background": "#F5EEE4"},
    "Low": {"foreground": "#506344", "background": "#EAF0E5"},
    "Default": {"foreground": "#777985", "background": "#F1F0ED"},
}

LIGHT_THEME_QSS = """
QMainWindow, QWidget#ContentArea {
    background-color: #F5F3EF;
    color: #252833;
    font-size: 13px;
}
QLabel { color: #252833; }
QFrame#SidebarContainer {
    background-color: #171923;
    border: none;
}
QLabel#SidebarTitle {
    color: #F5F3EF;
    font-size: 21px;
    font-weight: 700;
    padding: 22px 18px 2px;
}
QLabel#SidebarSubtitle {
    color: #B4C69A;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 1px;
    padding: 0 18px 18px;
}
QPushButton#SidebarNavButton {
    color: #D8D8DE;
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    text-align: left;
    padding: 12px 16px;
    margin: 1px 8px 1px 0;
    font-weight: 500;
}
QPushButton#SidebarNavButton:hover {
    color: #FFFFFF;
    background-color: #252833;
}
QPushButton#SidebarNavButton:checked {
    color: #FFFFFF;
    background-color: #344C59;
    border-left: 3px solid #B4C69A;
    font-weight: 700;
}
QFrame#OfflineBadge {
    background-color: #252833;
    border: 1px solid #344C59;
    border-radius: 9px;
    margin: 10px 12px;
    padding: 8px;
}
QFrame#HeaderBar {
    background-color: #FFFFFF;
    border: none;
    border-bottom: 1px solid #E5E2DE;
}
QLabel#HeaderTitle { font-size: 16px; font-weight: 700; }
QFrame#CardFrame, QFrame#StatCard, QFrame#TaskItemWidget {
    background-color: #FFFFFF;
    border: 1px solid #E5E2DE;
    border-radius: 12px;
}
QWidget#DiaryEntryListItem {
    background-color: #FFFFFF;
    border: 1px solid #E5E2DE;
    border-radius: 8px;
}
QWidget#DiaryDetailContent { background-color: #F5F3EF; }
QLineEdit, QTextEdit, QComboBox, QDateEdit {
    color: #252833;
    background-color: #FFFFFF;
    border: 1px solid #E5E2DE;
    border-radius: 7px;
    padding: 7px 10px;
    selection-background-color: #344C59;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus {
    border: 1px solid #9A8BB8;
}
QComboBox::drop-down, QDateEdit::drop-down {
    border: none;
    width: 24px;
}
QPushButton {
    color: #FFFFFF;
    background-color: #344C59;
    border: 1px solid #344C59;
    border-radius: 7px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover { background-color: #405B69; }
QPushButton:pressed { background-color: #263A44; }
QPushButton:disabled {
    color: #A8A9AE;
    background-color: #EAE8E4;
    border-color: #E5E2DE;
}
QPushButton#SecondaryButton {
    color: #344C59;
    background-color: #FFFFFF;
    border: 1px solid #D5D4D0;
}
QPushButton#SecondaryButton:hover { background-color: #F5F3EF; }
QPushButton#DangerButton {
    color: #A53E3E;
    background-color: #FFF8F6;
    border: 1px solid #E7C7C1;
}
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #C8C7C4;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #9A8BB8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #C8C7C4;
    border-radius: 4px;
    min-width: 28px;
}
QListWidget {
    color: #252833;
    background-color: #FFFFFF;
    border: 1px solid #E5E2DE;
    border-radius: 8px;
    outline: none;
}
QCheckBox { spacing: 7px; }
QCheckBox::indicator {
    width: 17px;
    height: 17px;
}
QProgressBar {
    color: #252833;
    background-color: #EAE8E4;
    border: none;
    border-radius: 5px;
    text-align: center;
    min-height: 10px;
}
QProgressBar::chunk {
    background-color: #9A8BB8;
    border-radius: 5px;
}
QTabWidget::pane {
    background-color: #FFFFFF;
    border: 1px solid #E5E2DE;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    color: #777985;
    background: #F5F3EF;
    border: 1px solid #E5E2DE;
    padding: 8px 14px;
}
QTabBar::tab:selected {
    color: #344C59;
    background: #FFFFFF;
    border-bottom-color: #FFFFFF;
    font-weight: 700;
}
QToolTip {
    color: #F5F3EF;
    background-color: #171923;
    border: 1px solid #344C59;
    padding: 5px 8px;
}
"""
