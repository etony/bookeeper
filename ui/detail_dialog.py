"""
┌──────────────────────────────────────────┐
│  图书详情对话框                           │
│                                          │
│  双击表格行打开，展示封面和全部信息，       │
│  支持上下翻页和后台封面下载。              │
└──────────────────────────────────────────┘
"""

import copy
import logging

from PyQt6.QtCore import Qt, QThread, QObject, QSize, pyqtSignal
from PyQt6.QtGui import QImage, QPalette, QShortcut, QKeySequence
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser, QPushButton

from config import Config
from ui.components.cover_label import CoverLabel
from ui.theme import ACCENT, DIALOG_MARGINS, DIALOG_SPACING

LOG = logging.getLogger(__name__)
from services import get_repo
from core.models.book import Book
from services.douban import DoubanService

# 图书缓存最大数量——超过时淘汰最早访问的（LRU 策略）
# 避免频繁翻页时反复从数据库加载
_MAX_CACHE = 50

# 已退役但可能仍在运行的封面下载线程 (thread, worker)。
# 必须保留引用：Python 持有的 QThread 在运行中被 GC 销毁会直接崩溃。
# 线程自然结束后由下一次 _prune_retired_threads() 释放。
_retired_threads = []


def _retire_cover_thread(thread, worker):
  """退役一个封面下载线程：引用交给看护列表，并顺带清理已结束的"""
  _retired_threads.append((thread, worker))
  _prune_retired_threads()


def _prune_retired_threads():
  alive = []
  for thread, worker in _retired_threads:
    try:
      running = thread.isRunning()
    except RuntimeError:
      running = False          # C++ 对象已被销毁
    if running:
      alive.append((thread, worker))
  _retired_threads[:] = alive


class _CoverWorker(QObject):
  """
  后台下载封面的工作线程。

  为什么用独立线程？
    下载图片涉及网络请求，如果在主线程执行，
    界面会卡住直到下载完成。
  下载完成后通过信号把图片数据传回主线程。
  """

  cover_ready = pyqtSignal(str, bytes)   # (isbn, image_data)
  done = pyqtSignal()                    # 下载结束（成功/失败/异常都会发）

  def __init__(self, url: str, isbn: str, referer: str = None):
    super().__init__()
    self._url = url
    self._isbn = isbn
    self._referer = referer

  def run(self):
    """在工作线程中执行下载"""
    try:
      from services.covers import get_cover
      data, _ = get_cover(self._isbn, self._url, referer=self._referer)
      if data:
        self.cover_ready.emit(self._isbn, data)
    except Exception as e:
      LOG.warning('封面下载失败: %s', e)
    finally:
      self.done.emit()


class DetailDialog(QDialog):
  """
  图书详情对话框。

  功能：
    - 展示封面（后台下载，不卡界面）
    - 展示完整图书信息（含豆瓣链接）
    - 上下翻页浏览列表中的图书
    - LRU 缓存避免重复加载

  触发方式：主窗口表格双击任意行。
  """

  def __init__(self, isbn_list=None, index=0, parent=None):
    super().__init__(parent)
    self._repo = get_repo()
    self._api = DoubanService()
    self._isbn_list = isbn_list or []    # 当前列表的全部 ISBN
    self._index = index                   # 当前显示的是第几本
    self._cache = {}                      # isbn → Book 对象的缓存字典
    self._cache_order = []                # 维护缓存访问顺序（用于 LRU 淘汰）
    self._build_ui()
    # accept()/reject() 不经过 closeEvent，也要退役下载线程
    self.finished.connect(self._retire_cover_download)
    self._load_current()

  def _build_ui(self):
    """
    构建界面布局。

    顶：翻页按钮 + 页码指示器
    左：封面图（200×280）
    右：图书信息（QTextBrowser 支持 HTML 渲染）
    """
    self.setWindowTitle('图书详情')
    self.resize(*Config.DETAIL_DIALOG_SIZE)
    self.setMinimumSize(500, 400)
    layout = QVBoxLayout(self)
    layout.setContentsMargins(*DIALOG_MARGINS)
    layout.setSpacing(DIALOG_SPACING)

    # ── 顶部：翻页按钮 + 页码 ───────────────────────────
    nav = QHBoxLayout()
    nav.setSpacing(DIALOG_SPACING)
    self._prev_btn = QPushButton('上一本')
    self._next_btn = QPushButton('下一本')
    self._page_label = QLabel('')
    self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._prev_btn.setToolTip('查看上一本图书 (← 或 ↑)')
    self._next_btn.setToolTip('查看下一本图书 (→ 或 ↓)')
    self._prev_btn.setAccessibleName('上一本图书')
    self._next_btn.setAccessibleName('下一本图书')
    self._prev_btn.clicked.connect(self._prev)
    self._next_btn.clicked.connect(self._next)
    nav.addWidget(self._prev_btn)
    nav.addWidget(self._page_label, stretch=1)
    nav.addWidget(self._next_btn)
    layout.addLayout(nav)

    # 键盘快捷键翻页 + 关闭
    QShortcut(QKeySequence('Left'), self, self._prev)
    QShortcut(QKeySequence('Right'), self, self._next)
    QShortcut(QKeySequence('Up'), self, self._prev)
    QShortcut(QKeySequence('Down'), self, self._next)
    QShortcut(QKeySequence('Home'), self, lambda: self._goto(0))
    QShortcut(QKeySequence('End'), self, lambda: self._goto(len(self._isbn_list) - 1))
    QShortcut(QKeySequence('Esc'), self, self.close)

    # ── 内容区：封面 + 信息 ──────────────────────────────
    content = QHBoxLayout()
    content.setSpacing(DIALOG_SPACING)

    # 左侧：封面（最小尺寸 + 可缩放；CoverLabel 等比缩放不变形）
    self._cover = CoverLabel('无封面', size_hint=QSize(200, 280))
    self._cover.setMinimumSize(160, 224)
    self._cover.setMaximumSize(280, 392)
    self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._cover.setStyleSheet(
      'border: 1px solid; border-radius: 4px; font-size: 13px;')
    self._cover.setAccessibleName('图书封面')
    self._cover.setToolTip('图书封面图片')
    content.addWidget(self._cover)

    # 右侧：信息
    self._info = QTextBrowser()
    self._info.setOpenExternalLinks(True)    # 点击链接自动在浏览器打开
    self._info.setMinimumWidth(300)
    self._info.setAccessibleName('图书详细信息')
    content.addWidget(self._info)

    layout.addLayout(content, stretch=1)

  def _load_current(self):
    """
    加载并显示当前索引的图书。

    流程：
      1. 检查缓存中是否有，没有则从数据库加载
      2. 如果缺少封面或出版日期，尝试从豆瓣 API 补充
      3. 计算推荐度
      4. 生成 HTML 信息展示
      5. 后台下载封面

    用缓存避免频繁翻页时重复查询数据库。
    """
    if not self._isbn_list:
      return

    self._prev_btn.setEnabled(len(self._isbn_list) > 1)
    self._next_btn.setEnabled(len(self._isbn_list) > 1)
    self._page_label.setText(f'{self._index + 1} / {len(self._isbn_list)}')

    isbn = self._isbn_list[self._index % len(self._isbn_list)]

    if isbn not in self._cache:
      self._evict_cache()
      book = self._repo.get_by_isbn(isbn)

      # 如果数据不完整，尝试从豆瓣补充
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

    # 使用副本显示，避免污染缓存/数据库
    display_book = copy.copy(book)
    # 更新推荐度（评分或人数可能有变化）
    display_book.recommend = str(Book._calc_recommend(display_book.rating, display_book.raters))

    self.setWindowTitle(f'图书信息 - {display_book.title}')

    # 重置封面显示
    self._cover.clear_image()
    if display_book.cover_url:
      self._cover.setText('加载中...')
      self._start_cover_download(display_book.cover_url, isbn, display_book.douban_url)
    else:
      self._cover.setText('无封面')

    # 用 HTML 渲染图书信息（颜色跟随主题 palette）
    pal = self.palette()
    muted = pal.color(QPalette.ColorRole.PlaceholderText).name()
    info_html = f'''<div style="padding: 8px;">
<div style="font-size: 18px; font-weight: bold; margin-bottom: 12px;">{display_book.title}</div>
<table style="line-height: 1.8;">
<tr><td style="color:{muted}; padding-right:16px;">作者</td><td>{display_book.author}</td></tr>
<tr><td style="color:{muted};">出版</td><td>{display_book.publisher}</td></tr>
<tr><td style="color:{muted};">价格</td><td>{display_book.price}</td></tr>
<tr><td style="color:{muted};">出版年</td><td>{display_book.pubdate}</td></tr>
<tr><td style="color:{muted};">ISBN</td><td>{display_book.isbn}</td></tr>
<tr><td style="color:{muted};">评分</td><td>{display_book.rating} 分 / {display_book.raters} 人</td></tr>
<tr><td style="color:{muted};">推荐</td><td>{display_book.recommend}</td></tr>
<tr><td style="color:{muted};">链接</td><td><a style="color:{ACCENT}; text-decoration:none;" href="{display_book.douban_url}">豆瓣详情 →</a></td></tr>
</table></div>'''
    self._info.setHtml(info_html)

  def _start_cover_download(self, url: str, isbn: str, referer: str = None):
    """
    在后台线程下载封面图片。

    使用 QThread + 工作对象模式，
    避免线程操作界面控件。

    旧线程不做同步 wait（快速翻页时会卡 UI），直接退役：
    引用交给模块级看护列表，下载完（done → quit）后自然结束。
    注意不能用 finished → deleteLater 销毁线程对象——Python 还持有
    引用，下次翻页访问 isRunning() 会抛 RuntimeError 导致崩溃。
    """
    self._retire_cover_download()

    thread = QThread()
    worker = _CoverWorker(url, isbn, referer)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.cover_ready.connect(self._on_cover_ready)
    worker.done.connect(thread.quit)      # 失败/空结果也要退出线程
    self._cover_thread = thread
    self._cover_worker = worker
    thread.start()

  def _retire_cover_download(self):
    """把当前封面下载线程退役（交给看护列表或直接丢弃已结束的）"""
    thread = getattr(self, '_cover_thread', None)
    worker = getattr(self, '_cover_worker', None)
    self._cover_thread = None
    self._cover_worker = None
    if thread is not None:
      _retire_cover_thread(thread, worker)

  def closeEvent(self, a0):
    """关闭前退役下载线程，避免线程对象随对话框一起被 GC 销毁"""
    self._retire_cover_download()
    super().closeEvent(a0)

  def _on_cover_ready(self, isbn: str, data: bytes):
    """
    封面下载完成后的回调。

    检查当前显示的仍然是当初请求的那本书，
    避免翻页后旧封面覆盖新封面。
    """
    if isbn != self._isbn_list[self._index % len(self._isbn_list)]:
      return
    img = QImage.fromData(data)
    self._cover.set_image(img if not img.isNull() else None)

  def _evict_cache(self):
    """
    LRU 淘汰策略。

    当缓存数量超过限制时，删除最早访问的记录。
    这样翻页浏览大量图书时，内存不会无限增长。
    """
    while len(self._cache) >= _MAX_CACHE:
      oldest = self._cache_order.pop(0)
      self._cache.pop(oldest, None)

  def _prev(self):
    """上一本"""
    if not self._isbn_list:
      return
    self._index = (self._index - 1) % len(self._isbn_list)
    self._load_current()

  def _next(self):
    """下一本"""
    if not self._isbn_list:
      return
    self._index = (self._index + 1) % len(self._isbn_list)
    self._load_current()

  def _goto(self, index: int):
    """跳转到指定索引"""
    if not self._isbn_list:
      return
    self._index = index % len(self._isbn_list)
    self._load_current()
