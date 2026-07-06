# -*- coding: utf-8 -*-
"""豆瓣图书搜索对话框"""

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

  book_selected = pyqtSignal(object)  # Book

  def __init__(self, parent=None):
    super().__init__(parent)
    self._api = DoubanService()
    self._books = []
    self._build_ui()

  def _build_ui(self):
    self.setWindowTitle('豆瓣图书搜索')
    self.resize(*Config.SEARCH_DIALOG_SIZE)
    layout = QVBoxLayout(self)

    top = QHBoxLayout()
    self._input = QLineEdit()
    self._input.setPlaceholderText('输入书名关键词...')
    self._input.returnPressed.connect(self._search)
    top.addWidget(self._input)
    btn = QPushButton('搜索')
    btn.clicked.connect(self._search)
    top.addWidget(btn)
    layout.addLayout(top)

    self._table = QTableView()
    self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    hdr = self._table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    hdr.setStretchLastSection(True)
    hdr.resizeSection(0, 150)
    hdr.resizeSection(1, 200)
    hdr.resizeSection(2, 120)
    self._table.doubleClicked.connect(self._on_double_click)
    layout.addWidget(self._table)

  def set_keyword(self, keyword: str):
    self._input.setText(keyword)

  def _search(self):
    keyword = self._input.text().strip()
    if not keyword:
      QMessageBox.warning(self, '提示', '请输入搜索关键词')
      return
    self._books = self._api.search_books(keyword)
    if not self._books:
      QMessageBox.information(self, '搜索结果', '未找到匹配的图书，请尝试其他关键词')
    model = QStandardItemModel(len(self._books), 9)
    model.setHorizontalHeaderLabels(['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '分类', '书柜'])
    for r, book in enumerate(self._books):
      for c, val in enumerate(book.to_row()):
        model.setItem(r, c, QStandardItem(str(val)))
    self._table.setModel(model)

  def _on_double_click(self, index: QModelIndex):
    if 0 <= index.row() < len(self._books):
      self.book_selected.emit(self._books[index.row()])
      self.close()
