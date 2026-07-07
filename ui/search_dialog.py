# -*- coding: utf-8 -*-
"""
豆瓣图书搜索对话框模块 — SearchDialog。

功能：输入书名关键词，调用豆瓣 API 搜索，结果以表格展示。
      用户双击某行后通过 book_selected 信号将 Book 对象传回主窗口。
      这是 Dialog 与 MainWindow 之间「信号回传数据」的典型模式。
"""

from PyQt6.QtCore import pyqtSignal, QModelIndex
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
  QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
  QTableView, QMessageBox, QHeaderView,
)

from config import Config
from services.douban_api import DoubanService


class SearchDialog(QDialog):
  """搜索豆瓣图书，双击选中后通过信号回传"""

  book_selected = pyqtSignal(object)  # 传出 Book 对象，由 MainWindow._on_search_result 接收

  def __init__(self, parent=None):
    super().__init__(parent)
    self._api = DoubanService()
    self._books = []  # 保存搜索结果列表，供双击时按索引取出
    self._build_ui()

  def _build_ui(self):
    self.setWindowTitle('豆瓣图书搜索')
    self.resize(*Config.SEARCH_DIALOG_SIZE)
    layout = QVBoxLayout(self)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    top = QHBoxLayout()
    top.setSpacing(6)
    self._input = QLineEdit()
    self._input.setPlaceholderText('输入书名关键词，回车搜索...')
    self._input.setToolTip('输入书名关键词，回车即从豆瓣搜索')
    self._input.returnPressed.connect(self._search)
    top.addWidget(self._input, stretch=1)
    btn = QPushButton('🔎 搜索')
    btn.setToolTip('从豆瓣搜索图书')
    btn.setFixedWidth(100)
    btn.clicked.connect(self._search)
    top.addWidget(btn)
    layout.addLayout(top)

    self._table = QTableView()
    self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    self._table.setAlternatingRowColors(True)
    self._table.setSortingEnabled(True)
    self._table.verticalHeader().setVisible(False)
    self._table.setToolTip('双击行将图书添加到列表')
    hdr = self._table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    hdr.setStretchLastSection(True)
    hdr.resizeSection(0, 150)
    hdr.resizeSection(1, 200)
    hdr.resizeSection(2, 120)
    self._table.doubleClicked.connect(self._on_double_click)
    layout.addWidget(self._table)

  def set_keyword(self, keyword: str):
    """供 MainWindow 调用，预填搜索关键词（取自图书表单的书名输入框）"""
    self._input.setText(keyword)

  def _search(self):
    """调用豆瓣 API 搜索，结果填充到 QStandardItemModel 表格"""
    keyword = self._input.text().strip()
    if not keyword:
      QMessageBox.warning(self, '提示', '请输入搜索关键词')
      return
    self._books = self._api.search_books(keyword)
    if not self._books:
      QMessageBox.information(self, '搜索结果', '未找到匹配的图书，请尝试其他关键词')
    # 创建 9 列模型，与 Book.to_row() 的列顺序一致
    model = QStandardItemModel(len(self._books), 9)
    model.setHorizontalHeaderLabels(['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '分类', '书柜'])
    for r, book in enumerate(self._books):
      for c, val in enumerate(book.to_row()):
        model.setItem(r, c, QStandardItem(str(val)))
    self._table.setModel(model)

  def _on_double_click(self, index: QModelIndex):
    """双击行 -> 发送 book_selected 信号 -> 关闭对话框。
    注意：根据 _books 列表索引取 Book 对象，而不是从表格 model 读取。"""
    if 0 <= index.row() < len(self._books):
      self.book_selected.emit(self._books[index.row()])
      self.close()
