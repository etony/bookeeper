# 公共 QSS 样式（所有主题共享的基础样式）
BASE = '''
QWidget { font-size: 13px; }
QLineEdit, QComboBox, QDateEdit, QTextBrowser {
  border-radius: 5px; padding: 5px 10px;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border-width: 2px; }
QPushButton {
  border-radius: 5px; padding: 6px 18px; font-weight: 500;
}
QPushButton:hover { border-width: 2px; }
QPushButton:pressed { padding-top: 7px; padding-bottom: 5px; }
QGroupBox {
  border: 1px solid; border-radius: 8px; margin-top: 6px;
  padding-top: 14px; padding-bottom: 6px; padding-left: 8px; padding-right: 8px;
  font-weight: 600;
}
QGroupBox::title {
  subcontrol-origin: margin; left: 14px; padding: 0 8px;
}
QTableView { border: 1px solid; border-radius: 6px; outline: none; }
QTableView::item { padding: 4px 8px; }
QHeaderView::section {
  border: none; padding: 6px 10px; font-weight: 600;
}
QScrollBar:vertical { width: 8px; border: none; }
QScrollBar::handle:vertical { border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 8px; border: none; }
QScrollBar::handle:horizontal { border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QStatusBar { border-top: 1px solid; }
QMenu { padding: 4px; border-radius: 6px; }
QMenu::item { padding: 6px 28px 6px 16px; border-radius: 3px; }
QMessageBox QPushButton { min-width: 70px; }
QCalendarWidget QToolButton { font-size: 12px; }
'''

# 暗色主题 QSS：深灰背景 + 橙色强调
DARK_QSS = BASE + '''
QWidget { background-color: #1c1c1f; color: #e0e0e4; }
QLineEdit, QComboBox, QDateEdit, QTextBrowser {
  background-color: #26262b; border: 1px solid #38383f; color: #eaeaea;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
  border-color: #e8922a; background-color: #202025;
}
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
  image: none; border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid #7a7a80; margin-right: 6px;
}
QComboBox QAbstractItemView {
  background-color: #26262b; border: 1px solid #38383f;
  selection-background-color: #3a3528;
}
QPushButton { background-color: #2c2c33; border: 1px solid #3a3a42; color: #e0e0e4; }
QPushButton:hover { background-color: #363640; border-color: #e8922a; }
QPushButton:pressed { background-color: #222228; }
QPushButton:disabled { background-color: #202024; color: #5a5a60; }
QGroupBox { background-color: #242428; border-color: #323238; }
QGroupBox::title { color: #eaeaea; }
QTableView {
  background-color: #1c1c1f; alternate-background-color: #212125;
  border-color: #323238; gridline-color: #28282e;
  selection-background-color: #3a3528; selection-color: #fff;
}
QTableView::item:hover { background-color: #2a2825; }
QHeaderView::section {
  background-color: #26262b;
  border-right: 1px solid #323238; border-bottom: 1px solid #323238;
  color: #9a9aa0;
}
QScrollBar::handle:vertical { background: #38383f; }
QScrollBar::handle:vertical:hover { background: #484850; }
QScrollBar::handle:horizontal { background: #38383f; }
QScrollBar::handle:horizontal:hover { background: #484850; }
QStatusBar { background: #242428; border-top-color: #323238; color: #7a7a80; }
QMenu { background-color: #26262b; border: 1px solid #38383f; }
QMenu::item:selected { background-color: #3a3528; }
QDialog { background-color: #1c1c1f; }
QTextBrowser { background-color: #242428; }
QMessageBox { background-color: #1c1c1f; }
QMessageBox QLabel { color: #e0e0e4; }
QToolTip {
  background-color: #26262b; color: #e0e0e4;
  border: 1px solid #38383f; padding: 4px 8px;
  border-radius: 4px; font-size: 12px;
}

'''

# 亮色主题 QSS：米白背景 + 橙色强调
LIGHT_QSS = BASE + '''
QWidget { background-color: #f8f6f2; color: #2c3e50; }
QLineEdit, QComboBox, QDateEdit, QTextBrowser {
  background-color: #ffffff; border: 1px solid #d8d6d0; color: #2c3e50;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
  border-color: #e8922a; background-color: #fefcf8;
}
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
  image: none; border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid #8a8a8a; margin-right: 6px;
}
QComboBox QAbstractItemView {
  background-color: #fff; border: 1px solid #d8d6d0;
  selection-background-color: #f0e8d8;
}
QPushButton { background-color: #e8e6e0; border: 1px solid #d8d6d0; color: #2c3e50; }
QPushButton:hover { background-color: #e0dcd4; border-color: #e8922a; }
QPushButton:pressed { background-color: #d0ccc4; }
QPushButton:disabled { background-color: #f0eeea; color: #9a9a9a; }
QGroupBox { background-color: #ffffff; border-color: #e0ded8; }
QGroupBox::title { color: #4a5a6a; }
QTableView {
  background-color: #ffffff; alternate-background-color: #f6f4f0;
  border-color: #e0ded8; gridline-color: #ece8e2;
  selection-background-color: #e8dcc8; selection-color: #2c3e50;
}
QTableView::item:hover { background-color: #f0ece4; }
QHeaderView::section {
  background-color: #f0eee8;
  border-right: 1px solid #e0ded8; border-bottom: 1px solid #e0ded8;
  color: #5a5a5a;
}
QScrollBar::handle:vertical { background: #d8d6d0; }
QScrollBar::handle:vertical:hover { background: #c0beb8; }
QScrollBar::handle:horizontal { background: #d8d6d0; }
QScrollBar::handle:horizontal:hover { background: #c0beb8; }
QStatusBar { background: #f0eee8; border-top-color: #e0ded8; color: #8a8a8a; }
QMenu { background-color: #ffffff; border: 1px solid #d8d6d0; }
QMenu::item:selected { background-color: #e8dcc8; color: #2c3e50; }
QDialog { background-color: #f8f6f2; }
QTextBrowser { background-color: #ffffff; }
QMessageBox { background-color: #f8f6f2; }
QMessageBox QLabel { color: #2c3e50; }
QToolTip {
  background-color: #f0eee8; color: #2c3e50;
  border: 1px solid #d8d6d0; padding: 4px 8px;
  border-radius: 4px; font-size: 12px;
}
'''
