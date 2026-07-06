# -*- coding: utf-8 -*-
"""
图书详情对话框模块 — DetailDialog。

功能：双击表格行时弹出，展示单本图书的封面、豆瓣信息、评分等。
      支持「上一本/下一本」翻页浏览整个 ISBN 列表。
      封面图像通过豆瓣 API 下载后缓存。
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser, QPushButton

from config import Config
from services.douban_api import DoubanService


class DetailDialog(QDialog):
  """展示图书详情封面、评分等信息，支持上下翻页"""

  def __init__(self, parent=None, isbn_list=None, index=0):
    """
    参数:
      parent: 父窗口（MainWindow）
      isbn_list: 所有 ISBN 列表，用于翻页
      index: 初始显示的图书位置
    _cache: dict[str, Book]，按 ISBN 缓存已获取的图书信息，避免重复网络请求
    """
    super().__init__(parent)
    self._isbn_list = isbn_list or []
    self._index = index
    self._api = DoubanService()
    self._cache = {}
    self._build_ui()
    self._load_current()

  def _build_ui(self):
    """构建布局：左侧 200x280 封面，右侧 QTextBrowser 显示详细信息 + 翻页按钮"""
    self.setWindowTitle('图书信息')
    self.resize(*Config.DETAIL_DIALOG_SIZE)
    layout = QHBoxLayout(self)

    # 左侧封面图片
    self._cover = QLabel()
    self._cover.setFixedSize(200, 280)
    self._cover.setScaledContents(True)  # 图片自适应缩放
    layout.addWidget(self._cover)

    # 右侧信息区域
    right = QVBoxLayout()
    self._info = QTextBrowser()
    self._info.setOpenExternalLinks(True)  # HTML 链接可点击跳转
    right.addWidget(self._info)

    # 底部翻页按钮
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
    """加载当前索引对应的图书信息并更新界面。
    先查缓存，未命中则调用豆瓣 API；封面通过 download_image 异步获取。"""
    if not self._isbn_list:
      return
    self._prev_btn.setEnabled(len(self._isbn_list) > 1)
    self._next_btn.setEnabled(len(self._isbn_list) > 1)
    # 取模保证索引安全
    isbn = self._isbn_list[self._index % len(self._isbn_list)]
    if isbn not in self._cache:
      self._cache[isbn] = self._api.get_book_by_isbn(isbn)
    book = self._cache[isbn]
    if not book:
      return
    self.setWindowTitle(f'图书信息 - {book.title}')

    # 下载并显示封面
    if book.cover_url:
      data = self._api.download_image(book.cover_url)
      if data:
        img = QImage.fromData(data)
        self._cover.setPixmap(QPixmap.fromImage(img))

    # 使用 HTML 渲染详细信息，豆瓣链接可点击
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
    """翻到上一本，索引循环"""
    self._index = (self._index - 1) % len(self._isbn_list)
    self._load_current()

  def _next(self):
    """翻到下一本，索引循环"""
    self._index = (self._index + 1) % len(self._isbn_list)
    self._load_current()
