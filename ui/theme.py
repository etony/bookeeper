"""
主题样式模块 - 提供暗色/亮色两套 Qt 样式表（QSS）。

设计要点：
  - DARK_QSS / LIGHT_QSS 两个字符串常量定义全局样式
  - 通过 MainWindow.setStyleSheet 切换
  - 选色遵循低对比度、护眼原则
  - 圆角、阴影、悬停高亮增强操作感
"""

BASE = '''
QWidget {
  font-size: 13px;
}
QLineEdit, QComboBox, QDateEdit, QTextBrowser {
  border-radius: 5px;
  padding: 5px 10px;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
  border-width: 2px;
}
QPushButton {
  border-radius: 5px;
  padding: 6px 18px;
  font-weight: 500;
}
QPushButton:hover {
  border-width: 2px;
}
QPushButton:pressed {
  padding-top: 7px;
  padding-bottom: 5px;
}
QPushButton:disabled {
  opacity: 0.5;
}
QGroupBox {
  border-radius: 8px;
  margin-top: 12px;
  padding-top: 18px;
  padding-bottom: 8px;
  padding-left: 8px;
  padding-right: 8px;
  font-weight: 600;
}
QGroupBox::title {
  subcontrol-origin: margin;
  left: 14px;
  padding: 0 8px;
}
QTableView {
  border-radius: 6px;
  outline: none;
}
QTableView::item {
  padding: 4px 8px;
}
QTableView::item:hover {
}
QHeaderView::section {
  border: none;
  padding: 6px 10px;
  font-weight: 600;
}
QScrollBar:vertical {
  width: 8px;
  border: none;
}
QScrollBar::handle:vertical {
  border-radius: 4px;
  min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
  height: 0;
}
QScrollBar:horizontal {
  height: 8px;
  border: none;
}
QScrollBar::handle:horizontal {
  border-radius: 4px;
  min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
  width: 0;
}
QStatusBar {
  border-top: 1px solid;
}
QMenu {
  padding: 4px;
  border-radius: 6px;
}
QMenu::item {
  padding: 6px 28px 6px 16px;
  border-radius: 3px;
}
QMessageBox QPushButton {
  min-width: 70px;
}
'''

DARK_QSS = BASE + '''
QWidget {
  background-color: #161920;
  color: #c8ccd4;
}
QLineEdit, QComboBox, QDateEdit, QTextBrowser {
  background-color: #1e2230;
  border: 1px solid #2d3548;
  color: #e0e4ea;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
  border-color: #4a8cff;
  background-color: #1a1f30;
}
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
  image: none; border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid #6a7a8a; margin-right: 6px;
}
QComboBox QAbstractItemView {
  background-color: #1e2230; border: 1px solid #2d3548;
  selection-background-color: #2d3a5a;
}
QPushButton {
  background-color: #222738; border: 1px solid #2d3548;
  color: #c8ccd4;
}
QPushButton:hover { background-color: #2a3045; border-color: #4a8cff; }
QPushButton:pressed { background-color: #181c2a; }
QPushButton:disabled { background-color: #1a1d28; color: #4a5060; }
QGroupBox {
  background-color: #1a1e2a; border: 1px solid #2a3142;
}
QGroupBox::title { color: #e0e4ea; }
QTableView {
  background-color: #161920; alternate-background-color: #1a1e2a;
  border: 1px solid #2a3142;
  gridline-color: #222838; selection-background-color: #264f78; selection-color: #fff;
}
QTableView::item:hover { background-color: #1f2a40; }
QHeaderView::section {
  background-color: #1e2230;
  border-right: 1px solid #2a3142; border-bottom: 1px solid #2a3142;
  color: #a0a8b4;
}
QScrollBar::handle:vertical { background: #2d3548; }
QScrollBar::handle:vertical:hover { background: #3d4560; }
QScrollBar::handle:horizontal { background: #2d3548; }
QScrollBar::handle:horizontal:hover { background: #3d4560; }
QStatusBar { background: #1a1e2a; border-top-color: #2a3142; color: #6a7a8a; }
QMenu { background-color: #1e2230; border: 1px solid #2d3548; }
QMenu::item:selected { background-color: #264f78; }
QDialog { background-color: #161920; }
QTextBrowser { background-color: #1a1e2a; }
QFrame#headerFrame { background-color: #1e2230; border-radius: 8px; padding: 10px; }
QMessageBox { background-color: #161920; }
QMessageBox QLabel { color: #c8ccd4; }
'''

LIGHT_QSS = BASE + '''
QWidget {
  background-color: #f5f6f8;
  color: #2c3e50;
}
QLineEdit, QComboBox, QDateEdit, QTextBrowser {
  background-color: #ffffff;
  border: 1px solid #d0d5dd;
  color: #2c3e50;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
  border-color: #3b82f6;
  background-color: #fafcff;
}
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
  image: none; border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid #8a94a6; margin-right: 6px;
}
QComboBox QAbstractItemView {
  background-color: #fff; border: 1px solid #d0d5dd;
  selection-background-color: #dbeafe;
}
QPushButton {
  background-color: #e8ecf0; border: 1px solid #d0d5dd;
  color: #2c3e50;
}
QPushButton:hover { background-color: #dce0e6; border-color: #3b82f6; }
QPushButton:pressed { background-color: #c8cdd4; }
QPushButton:disabled { background-color: #f0f2f4; color: #9aa2ae; }
QGroupBox {
  background-color: #ffffff; border: 1px solid #e0e4ea;
}
QGroupBox::title { color: #4a5a6a; }
QTableView {
  background-color: #ffffff; alternate-background-color: #f8f9fb;
  border: 1px solid #e0e4ea;
  gridline-color: #eaecf0; selection-background-color: #3b82f6; selection-color: #fff;
}
QTableView::item:hover { background-color: #eef2ff; }
QHeaderView::section {
  background-color: #f0f2f5;
  border-right: 1px solid #e0e4ea; border-bottom: 1px solid #e0e4ea;
  color: #4a5a6a;
}
QScrollBar::handle:vertical { background: #d0d5dd; }
QScrollBar::handle:vertical:hover { background: #b0b8c4; }
QScrollBar::handle:horizontal { background: #d0d5dd; }
QScrollBar::handle:horizontal:hover { background: #b0b8c4; }
QStatusBar { background: #eef0f3; border-top-color: #e0e4ea; color: #8a94a6; }
QMenu { background-color: #ffffff; border: 1px solid #d0d5dd; }
QMenu::item:selected { background-color: #3b82f6; color: #fff; }
QDialog { background-color: #f5f6f8; }
QTextBrowser { background-color: #ffffff; }
QFrame#headerFrame { background-color: #eef0f3; border-radius: 8px; padding: 10px; }
QMessageBox { background-color: #f5f6f8; }
QMessageBox QLabel { color: #2c3e50; }
'''
