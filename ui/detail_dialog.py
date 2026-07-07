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
    self.setWindowTitle('图书详情')
    self.resize(*Config.DETAIL_DIALOG_SIZE)
    layout = QHBoxLayout(self)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(16)

    self._cover = QLabel()
    self._cover.setFixedSize(200, 280)
    self._cover.setScaledContents(True)
    self._cover.setStyleSheet(
      'border: 1px solid #3a3f4b; border-radius: 4px; background-color: #1e2230;')
    layout.addWidget(self._cover)

    right = QVBoxLayout()
    right.setSpacing(10)
    self._info = QTextBrowser()
    self._info.setOpenExternalLinks(True)
    self._info.setMinimumWidth(300)
    right.addWidget(self._info)

    nav = QHBoxLayout()
    nav.setSpacing(8)
    self._prev_btn = QPushButton('◀ 上一本')
    self._prev_btn.setToolTip('查看上一本（快捷键：键盘左方向键）')
    self._next_btn = QPushButton('下一本 ▶')
    self._next_btn.setToolTip('查看下一本（快捷键：键盘右方向键）')
    self._prev_btn.clicked.connect(self._prev)
    self._next_btn.clicked.connect(self._next)
    nav.addStretch()
    nav.addWidget(self._prev_btn)
    nav.addWidget(self._next_btn)
    nav.addStretch()
    right.addLayout(nav)
    layout.addLayout(right)

  def _load_current(self):
    """加载当前索引对应的图书信息并更新界面。
    先查缓存，未命中则调用豆瓣 API；封面通过 download_image 异步获取。"""
    if not self._isbn_list:
      return
    self._prev_btn.setEnabled(len(self._isbn_list) > 1)
    self._next_btn.setEnabled(len(self._isbn_list) > 1)
    # 取模保证索引安全（循环翻页时不会越界）
    isbn = self._isbn_list[self._index % len(self._isbn_list)]
    # 缓存查询：避免重复网络请求，同一 ISBN 只调一次豆瓣 API
    if isbn not in self._cache:
      self._cache[isbn] = self._api.get_book_by_isbn(isbn)
    book = self._cache[isbn]
    if not book:
      return
    self.setWindowTitle(f'图书信息 - {book.title}')

    # 下载并显示封面
    # cover_url 是豆瓣返回的小尺寸封面 URL，通过 download_image 获取二进制数据
    if book.cover_url:
      data = self._api.download_image(book.cover_url)
      if data:
        img = QImage.fromData(data)
        self._cover.setPixmap(QPixmap.fromImage(img))

    # 图书详情以 HTML 表格形式展示，QTextBrowser 可安全渲染简单 HTML
    info_html = f'''<div style="padding: 8px;">
<div style="font-size: 18px; font-weight: bold; margin-bottom: 12px;">{book.title}</div>
<table style="line-height: 1.8;">
<tr><td style="color:#8899aa; padding-right:16px;">作者</td><td>{book.author}</td></tr>
<tr><td style="color:#8899aa;">出版</td><td>{book.publisher}</td></tr>
<tr><td style="color:#8899aa;">价格</td><td>{book.price}</td></tr>
<tr><td style="color:#8899aa;">日期</td><td>{book.pubdate}</td></tr>
<tr><td style="color:#8899aa;">ISBN</td><td>{book.isbn}</td></tr>
<tr><td style="color:#8899aa;">评分</td><td>{book.rating} 分 / {book.raters} 人</td></tr>
<tr><td style="color:#8899aa;">推荐</td><td>{book.recommend}</td></tr>
<tr><td style="color:#8899aa;">链接</td><td><a style="color:#4a8cff; text-decoration:none;" href="{book.douban_url}">豆瓣详情 →</a></td></tr>
</table></div>'''
    self._info.setHtml(info_html)

  def _prev(self):
    """翻到上一本，索引循环"""
    self._index = (self._index - 1) % len(self._isbn_list)
    self._load_current()

  def _next(self):
    """翻到下一本，索引循环"""
    self._index = (self._index + 1) % len(self._isbn_list)
    self._load_current()
