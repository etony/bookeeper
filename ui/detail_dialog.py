# -*- coding: utf-8 -*-
"""图书详情对话框"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser, QPushButton

from config import Config
from services.douban_api import DoubanService


class DetailDialog(QDialog):
  """展示图书详情封面、评分等信息，支持上下翻页"""

  def __init__(self, parent=None, isbn_list=None, index=0):
    super().__init__(parent)
    self._isbn_list = isbn_list or []
    self._index = index
    self._api = DoubanService()
    self._cache = {}
    self._build_ui()
    self._load_current()

  def _build_ui(self):
    self.setWindowTitle('图书信息')
    self.resize(*Config.DETAIL_DIALOG_SIZE)
    layout = QHBoxLayout(self)

    self._cover = QLabel()
    self._cover.setFixedSize(200, 280)
    self._cover.setScaledContents(True)
    layout.addWidget(self._cover)

    right = QVBoxLayout()
    self._info = QTextBrowser()
    self._info.setOpenExternalLinks(True)
    right.addWidget(self._info)

    nav = QHBoxLayout()
    self._prev_btn = QPushButton('<< 上一本')
    self._next_btn = QPushButton('下一本 >>')
    self._prev_btn.clicked.connect(self._prev)
    self._next_btn.clicked.connect(self._next)
    nav.addWidget(self._prev_btn)
    nav.addWidget(self._next_btn)
    right.addLayout(nav)
    layout.addLayout(right)

  def _load_current(self):
    if not self._isbn_list:
      return
    self._prev_btn.setEnabled(len(self._isbn_list) > 1)
    self._next_btn.setEnabled(len(self._isbn_list) > 1)
    isbn = self._isbn_list[self._index % len(self._isbn_list)]
    if isbn not in self._cache:
      self._cache[isbn] = self._api.get_book_by_isbn(isbn)
    book = self._cache[isbn]
    if not book:
      return
    self.setWindowTitle(f'图书信息 - {book.title}')

    if book.cover_url:
      data = self._api.download_image(book.cover_url)
      if data:
        img = QImage.fromData(data)
        self._cover.setPixmap(QPixmap.fromImage(img))

    info = f'''<b><font size="5">{book.title}</font></b><br><br>
<b>作者:</b> {book.author}<br>
<b>出版:</b> {book.publisher}<br>
<b>价格:</b> {book.price}<br>
<b>日期:</b> {book.pubdate}<br>
<b>ISBN:</b> {book.isbn}<br>
<b>评分:</b> {book.rating} 分 / {book.raters} 人<br>
<b>推荐:</b> {book.recommend}<br>
<b>链接:</b> <a style="color:#5b9aff;" href="{book.douban_url}">豆瓣详情</a>'''
    self._info.setHtml(info)

  def _prev(self):
    self._index = (self._index - 1) % len(self._isbn_list)
    self._load_current()

  def _next(self):
    self._index = (self._index + 1) % len(self._isbn_list)
    self._load_current()
