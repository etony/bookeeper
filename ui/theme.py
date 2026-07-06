"""
主题样式模块 - 提供暗色/亮色两套 Qt 样式表（QSS）。

设计要点：
  - 使用 DARK_QSS 与 LIGHT_QSS 两个字符串常量定义全局样式。
  - 在 MainWindow 中通过 setStyleSheet 切换。
  - 选色遵循低对比度、护眼原则，适合长时间使用。
"""

# 暗色主题样式表（默认），覆盖所有标准控件的外观
DARK_QSS = '''
QWidget {
  background-color: #1b1e23;
  color: #c8ccd4;
  font-size: 13px;
}
QLineEdit, QComboBox, QTextBrowser {
  background-color: #282c34;
  border: 1px solid #3a3f4b;
  border-radius: 4px;
  padding: 4px 8px;
  color: #c8ccd4;
}
QLineEdit:focus, QComboBox:focus {
  border-color: #5b9aff;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
  image: none; border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid #8899aa; margin-right: 6px;
}
QComboBox QAbstractItemView {
  background-color: #282c34; border: 1px solid #3a3f4b;
  selection-background-color: #3a3f4b;
}
QPushButton {
  background-color: #2d323e; border: 1px solid #3a3f4b;
  border-radius: 4px; padding: 5px 16px; color: #c8ccd4;
}
QPushButton:hover { background-color: #363b49; border-color: #5b9aff; }
QPushButton:pressed { background-color: #1e222b; }
QPushButton:disabled { background-color: #252830; color: #555; }
QGroupBox {
  background-color: #21252b; border: 1px solid #3a3f4b;
  border-radius: 6px; margin-top: 10px; padding-top: 14px; font-weight: bold;
}
QGroupBox::title {
  subcontrol-origin: margin; left: 12px;
  padding: 0 6px; color: #e0e4ea;
}
QTableView {
  background-color: #1b1e23; alternate-background-color: #21252b;
  border: 1px solid #3a3f4b; border-radius: 4px;
  gridline-color: #2d323e; selection-background-color: #264f78; selection-color: #fff;
}
QTableView::item:hover { background-color: #2a3d5c; }
QHeaderView::section {
  background-color: #282c34; border: none;
  border-right: 1px solid #3a3f4b; border-bottom: 1px solid #3a3f4b;
  padding: 4px 8px; color: #c8ccd4; font-weight: bold;
}
QScrollBar:vertical { background: #1b1e23; width: 10px; border: none; }
QScrollBar::handle:vertical { background: #3a3f4b; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4a4f5b; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #1b1e23; height: 10px; border: none; }
QScrollBar::handle:horizontal { background: #3a3f4b; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #4a4f5b; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QStatusBar { background: #21252b; border-top: 1px solid #3a3f4b; color: #8899aa; }
QMenu { background-color: #282c34; border: 1px solid #3a3f4b; padding: 4px; }
QMenu::item { padding: 6px 24px; border-radius: 3px; }
QMenu::item:selected { background-color: #264f78; }
QDialog { background-color: #1b1e23; }
QTextBrowser { background-color: #21252b; }
QFrame#headerFrame { background-color: #2d323e; border-radius: 6px; padding: 8px; }
QMessageBox { background-color: #1b1e23; }
QMessageBox QLabel { color: #c8ccd4; }
QMessageBox QPushButton { min-width: 70px; }
'''

# 亮色主题样式表，通过 _toggle_theme 切换
LIGHT_QSS = '''
QWidget { background-color: #f5f5f5; color: #333; font-size: 13px; }
QLineEdit, QComboBox, QTextBrowser {
  background-color: #fff; border: 1px solid #ccc;
  border-radius: 4px; padding: 4px 8px; color: #333;
}
QLineEdit:focus, QComboBox:focus { border-color: #4a90d9; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
  image: none; border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid #666; margin-right: 6px;
}
QComboBox QAbstractItemView {
  background-color: #fff; border: 1px solid #ccc;
  selection-background-color: #d0e4f5;
}
QPushButton {
  background-color: #e8e8e8; border: 1px solid #ccc;
  border-radius: 4px; padding: 5px 16px; color: #333;
}
QPushButton:hover { background-color: #ddd; border-color: #4a90d9; }
QPushButton:pressed { background-color: #ccc; }
QPushButton:disabled { background-color: #f0f0f0; color: #aaa; }
QGroupBox {
  background-color: #fff; border: 1px solid #d0d0d0;
  border-radius: 6px; margin-top: 10px; padding-top: 14px; font-weight: bold;
}
QGroupBox::title {
  subcontrol-origin: margin; left: 12px;
  padding: 0 6px; color: #555;
}
QTableView {
  background-color: #fff; alternate-background-color: #f9f9f9;
  border: 1px solid #d0d0d0; border-radius: 4px;
  gridline-color: #e0e0e0; selection-background-color: #4a90d9; selection-color: #fff;
}
QTableView::item:hover { background-color: #e8f0fe; }
QHeaderView::section {
  background-color: #e8e8e8; border: none;
  border-right: 1px solid #d0d0d0; border-bottom: 1px solid #d0d0d0;
  padding: 4px 8px; color: #333; font-weight: bold;
}
QScrollBar:vertical { background: #f0f0f0; width: 10px; border: none; }
QScrollBar::handle:vertical { background: #ccc; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #aaa; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #f0f0f0; height: 10px; border: none; }
QScrollBar::handle:horizontal { background: #ccc; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #aaa; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QStatusBar { background: #e8e8e8; border-top: 1px solid #d0d0d0; color: #666; }
QMenu { background-color: #fff; border: 1px solid #ccc; padding: 4px; }
QMenu::item { padding: 6px 24px; border-radius: 3px; }
QMenu::item:selected { background-color: #4a90d9; color: #fff; }
QDialog { background-color: #f5f5f5; }
QTextBrowser { background-color: #fff; }
QFrame#headerFrame { background-color: #e0e4ea; border-radius: 6px; padding: 8px; }
QMessageBox { background-color: #f5f5f5; }
QMessageBox QLabel { color: #333; }
QMessageBox QPushButton { min-width: 70px; }
'''
