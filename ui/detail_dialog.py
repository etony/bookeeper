from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser, QPushButton

from config import Config
from services import get_repo
from models.book import Book
from services.douban import DoubanService

# 图书缓存最大数量，超过时淘汰最早访问的
_MAX_CACHE = 50


class _CoverWorker(QObject):
  """后台下载封面的工作线程"""
  cover_ready = pyqtSignal(str, bytes)

  def __init__(self, url: str, isbn: str, referer: str = None):
    super().__init__()
    self._url = url
    self._isbn = isbn
    self._referer = referer

  def run(self):
    try:
      api = DoubanService()
      data = api.download_image(self._url, referer=self._referer)
      if data:
        self.cover_ready.emit(self._isbn, data)
    except Exception:
      pass


class DetailDialog(QDialog):
  """图书详情对话框，支持翻页浏览和封面后台下载"""

  def __init__(self, isbn_list=None, index=0, parent=None):
    super().__init__(parent)
    self._repo = get_repo()
    self._api = DoubanService()
    self._isbn_list = isbn_list or []
    self._index = index
    self._cache = {}
    self._cache_order = []
    self._build_ui()
    self._load_current()

  def _build_ui(self):
    """构建界面：左侧封面 + 右侧 HTML 信息 + 上下翻页按钮"""
    self.setWindowTitle('图书详情')
    self.resize(*Config.DETAIL_DIALOG_SIZE)
    layout = QHBoxLayout(self)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(16)

    self._cover = QLabel('无封面')
    self._cover.setFixedSize(200, 280)
    self._cover.setScaledContents(True)
    self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._cover.setStyleSheet(
      'border: 1px solid #38383f; border-radius: 4px; background-color: #26262b; color: #6a6a70; font-size: 13px;')
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
    self._next_btn = QPushButton('下一本 ▶')
    self._prev_btn.clicked.connect(self._prev)
    self._next_btn.clicked.connect(self._next)
    nav.addStretch()
    nav.addWidget(self._prev_btn)
    nav.addWidget(self._next_btn)
    nav.addStretch()
    right.addLayout(nav)
    layout.addLayout(right)

  def _load_current(self):
    """加载当前索引的图书信息并显示"""
    if not self._isbn_list:
      return
    self._prev_btn.setEnabled(len(self._isbn_list) > 1)
    self._next_btn.setEnabled(len(self._isbn_list) > 1)
    isbn = self._isbn_list[self._index % len(self._isbn_list)]
    if isbn not in self._cache:
      self._evict_cache()
      book = self._repo.get_by_isbn(isbn)
      # 如果缺少封面或出版日期，尝试从豆瓣补充
      if book and (not book.cover_url or not book.pubdate):
        api_book = self._api.get_book_by_isbn(isbn)
        if api_book:
          if api_book.cover_url:
            book.cover_url = api_book.cover_url
          if api_book.pubdate:
            book.pubdate = api_book.pubdate
          if api_book.douban_url:
            book.douban_url = api_book.douban_url
          self._repo.upsert(book)
      self._cache[isbn] = book
      self._cache_order.append(isbn)
    book = self._cache[isbn]
    if not book:
      return
    book.recommend = str(Book._calc_recommend(book.rating, book.raters))
    self.setWindowTitle(f'图书信息 - {book.title}')
    self._cover.setText('无封面')
    self._cover.setPixmap(QPixmap())
    if book.cover_url:
      self._start_cover_download(book.cover_url, isbn, book.douban_url)
    info_html = f'''<div style="padding: 8px;">
<div style="font-size: 18px; font-weight: bold; margin-bottom: 12px;">{book.title}</div>
<table style="line-height: 1.8;">
<tr><td style="color:#7a7a80; padding-right:16px;">作者</td><td>{book.author}</td></tr>
<tr><td style="color:#7a7a80;">出版</td><td>{book.publisher}</td></tr>
<tr><td style="color:#7a7a80;">价格</td><td>{book.price}</td></tr>
<tr><td style="color:#7a7a80;">出版年</td><td>{book.pubdate}</td></tr>
<tr><td style="color:#7a7a80;">ISBN</td><td>{book.isbn}</td></tr>
<tr><td style="color:#7a7a80;">评分</td><td>{book.rating} 分 / {book.raters} 人</td></tr>
<tr><td style="color:#7a7a80;">推荐</td><td>{book.recommend}</td></tr>
<tr><td style="color:#7a7a80;">链接</td><td><a style="color:#e8922a; text-decoration:none;" href="{book.douban_url}">豆瓣详情 →</a></td></tr>
</table></div>'''
    self._info.setHtml(info_html)

  def _start_cover_download(self, url: str, isbn: str, referer: str = None):
    """在后台线程下载封面图片"""
    self._cover_thread = QThread()
    self._cover_worker = _CoverWorker(url, isbn, referer)
    self._cover_worker.moveToThread(self._cover_thread)
    self._cover_thread.started.connect(self._cover_worker.run)
    self._cover_worker.cover_ready.connect(self._on_cover_ready)
    self._cover_worker.cover_ready.connect(self._cover_thread.quit)
    self._cover_worker.cover_ready.connect(self._cover_worker.deleteLater)
    self._cover_thread.finished.connect(self._cover_thread.deleteLater)
    self._cover_thread.start()

  def _on_cover_ready(self, isbn: str, data: bytes):
    """封面下载完成后更新界面（仅当仍是当前图书时）"""
    if isbn != self._isbn_list[self._index % len(self._isbn_list)]:
      return
    img = QImage.fromData(data)
    self._cover.setPixmap(QPixmap.fromImage(img))

  def _evict_cache(self):
    """LRU 淘汰：缓存超过上限时删除最早访问的记录"""
    while len(self._cache) >= _MAX_CACHE:
      oldest = self._cache_order.pop(0)
      self._cache.pop(oldest, None)

  def _prev(self):
    self._index = (self._index - 1) % len(self._isbn_list)
    self._load_current()

  def _next(self):
    self._index = (self._index + 1) % len(self._isbn_list)
    self._load_current()
