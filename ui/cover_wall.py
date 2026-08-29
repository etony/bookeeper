"""
┌──────────────────────────────────────────┐
│  封面墙视图                              │
│                                          │
│  以封面图片网格展示图书，                │
│  类似豆瓣书架的展示方式。                 │
└──────────────────────────────────────────┘
"""

import os
import threading
from queue import Queue
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QColor, QPainter, QPen, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea, QFrame, QMenu, QComboBox, QSizePolicy,
)

from config import Config
from models.book import Book
from ui.theme import ACCENT


class CoverDownloadPool:
    """封面下载线程池，限制并发数量"""

    def __init__(self, max_workers=3):
        self._queue = Queue()
        self._workers = []
        self._lock = threading.Lock()

        for _ in range(max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self._workers.append(worker)

    def _worker_loop(self):
        while True:
            isbn, cover_url, callback = self._queue.get()
            try:
                from services.covers import get_cover
                data, _ = get_cover(isbn, cover_url)
                if callback:
                    callback(isbn, data)
            except Exception:
                if callback:
                    callback(isbn, None)
            finally:
                self._queue.task_done()

    def submit(self, isbn: str, cover_url: str, callback=None):
        """提交下载任务"""
        self._queue.put((isbn, cover_url, callback))


# 全局线程池实例
_cover_pool = CoverDownloadPool()


class CoverCard(QFrame):
    """
    单个封面卡片组件。

    显示封面图片、书名、评分和状态标签。
    """

    clicked = pyqtSignal(str)      # 点击信号，传递 ISBN
    double_clicked = pyqtSignal(str)  # 双击信号
    context_menu = pyqtSignal(str, object)  # 右键菜单信号 (isbn, pos)

    def __init__(self, book: Book, parent=None):
        super().__init__(parent)
        self._book = book
        self._cover_label = None
        self._setup_ui()

    def _setup_ui(self):
        """构建卡片界面"""
        self.setFixedSize(150, 230)
        self.setFrameShape(QFrame.Shape.Box)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # 状态标签（左上角）
        self._status_label = QLabel(self._book.status)
        self._status_label.setFixedSize(40, 16)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setFont(QFont('', 9))
        self._status_label.move(4, 4)
        self._status_label.setStyleSheet(self._get_status_style())

        # 评分标签（右上角）
        rating_text = self._book.rating if self._book.rating and self._book.rating != '0' else ''
        self._rating_label = QLabel(rating_text)
        self._rating_label.setFixedSize(35, 16)
        self._rating_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rating_label.setFont(QFont('', 9, QFont.Weight.Bold))
        self._rating_label.move(111, 4)
        if rating_text:
            self._rating_label.setStyleSheet('background-color: rgba(0,0,0,150); color: white; border-radius: 3px;')
        else:
            self._rating_label.hide()

        # 封面图片
        self._cover_label = QLabel('加载中...')
        self._cover_label.setFixedSize(140, 180)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet('border: 1px solid #3a3a40; border-radius: 4px; background-color: #2c2c31;')
        layout.addWidget(self._cover_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 书名
        self._title_label = QLabel()
        self._title_label.setFixedHeight(28)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        self._title_label.setFont(QFont('', 10))
        title = self._book.title or '未知书名'
        if len(title) > 12:
            title = title[:11] + '...'
        self._title_label.setText(title)
        layout.addWidget(self._title_label)

        # 加载封面
        self._load_cover()

    def _get_status_style(self) -> str:
        """根据状态返回对应样式"""
        styles = {
            '已读': 'background-color: #4a9; color: white;',
            '计划': 'background-color: #58a; color: white;',
            '默认': 'background-color: #666; color: white;',
        }
        return styles.get(self._book.status, styles['默认'])

    def _update_style(self, hovered: bool):
        """更新卡片边框样式"""
        if hovered:
            self.setStyleSheet('QFrame { border: 2px solid #e8922a; border-radius: 6px; background-color: #2a2a2e; }')
        else:
            self.setStyleSheet('QFrame { border: 1px solid #3a3a40; border-radius: 6px; background-color: #2a2a2e; }')

    def _load_cover(self):
        """加载封面图片"""
        if not self._book.cover_url:
            self._cover_label.setText('无封面')
            return

        # 检查本地缓存
        from services.covers import _COVERS_DIR
        cache_path = os.path.join(_COVERS_DIR, f'{self._book.isbn}.img')
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    data = f.read()
                self._set_cover_from_data(data)
                return
            except Exception:
                pass

        # 后台下载
        self._start_cover_download()

    def _start_cover_download(self):
        """使用线程池下载封面"""
        _cover_pool.submit(
            self._book.isbn,
            self._book.cover_url,
            self._on_cover_ready
        )

    def _apply_cover(self, isbn: str, data: bytes):
        """在主线程中应用封面"""
        if isbn != self._book.isbn:
            return
        if data:
            self._set_cover_from_data(data)
        else:
            self._cover_label.setText('加载失败')

    def _on_cover_ready(self, isbn: str, data: bytes):
        """封面下载完成回调"""
        if isbn != self._book.isbn:
            return
        self._set_cover_from_data(data)

    def _on_cover_error(self, isbn: str):
        """封面下载失败回调"""
        if isbn != self._book.isbn:
            return
        self._cover_label.setText('加载失败')

    def _set_cover_from_data(self, data: bytes):
        """从图片数据设置封面"""
        img = QImage.fromData(data)
        if img.isNull():
            self._cover_label.setText('加载失败')
            return
        pixmap = QPixmap.fromImage(img)
        scaled = pixmap.scaled(138, 178, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        self._cover_label.setPixmap(scaled)

    def enterEvent(self, event):
        """鼠标进入事件"""
        self._update_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self._update_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._book.isbn)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._book.isbn)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单事件"""
        self.context_menu.emit(self._book.isbn, event.globalPos())

    def get_book(self) -> Book:
        """获取卡片对应的图书对象"""
        return self._book


class CoverWallWidget(QWidget):
    """
    封面墙主控件。

    以网格布局展示图书封面，支持排序和筛选。
    """

    book_selected = pyqtSignal(str)     # 选中图书信号
    book_opened = pyqtSignal(str)       # 打开图书详情信号
    book_context_menu = pyqtSignal(str, object)  # 右键菜单信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._books: List[Book] = []
        self._cards: List[CoverCard] = []
        self._columns = 5  # 每行显示的图书数量
        self._setup_ui()

    def _setup_ui(self):
        """构建封面墙界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel('排序:'))
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(['书名', '评分', '添加时间', '购书日期'])
        self._sort_combo.setFixedHeight(28)
        self._sort_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self._sort_combo)

        toolbar.addWidget(QLabel('每行:'))
        self._columns_combo = QComboBox()
        self._columns_combo.addItems(['3', '4', '5', '6', '7', '8'])
        self._columns_combo.setCurrentText('5')
        self._columns_combo.setFixedHeight(28)
        self._columns_combo.currentTextChanged.connect(self._on_columns_changed)
        toolbar.addWidget(self._columns_combo)

        toolbar.addStretch()
        self._count_label = QLabel('')
        self._count_label.setStyleSheet('color: #9a9aa0; font-size: 12px;')
        toolbar.addWidget(self._count_label)

        layout.addLayout(toolbar)

        # 封面网格区域
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(8, 8, 8, 8)
        self._grid_layout.setSpacing(10)
        self._scroll_area.setWidget(self._grid_widget)

        layout.addWidget(self._scroll_area, stretch=1)

    def set_books(self, books: List[Book]):
        """设置要显示的图书列表"""
        self._books = books
        self._refresh_grid()

    def get_selected_isbn(self) -> Optional[str]:
        """获取当前选中的图书 ISBN"""
        focused = self._grid_widget.focusWidget()
        if isinstance(focused, CoverCard):
            return focused._book.isbn
        return None

    def _refresh_grid(self):
        """刷新封面网格"""
        # 清空现有卡片
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        # 排序
        sorted_books = self._sort_books(self._books)

        # 创建新卡片
        for i, book in enumerate(sorted_books):
            card = CoverCard(book)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.context_menu.connect(self._on_card_context_menu)
            self._cards.append(card)

            row = i // self._columns
            col = i % self._columns
            self._grid_layout.addWidget(card, row, col)

        # 更新计数
        self._count_label.setText(f'共 {len(self._books)} 本')

        # 添加弹性空间
        for col in range(self._columns):
            self._grid_layout.setColumnStretch(col, 1)

    def _sort_books(self, books: List[Book]) -> List[Book]:
        """根据当前排序选项排序图书"""
        sort_key = self._sort_combo.currentText()

        def get_sort_value(book: Book):
            if sort_key == '书名':
                return book.title.lower()
            elif sort_key == '评分':
                try:
                    return -float(book.rating)
                except (ValueError, TypeError):
                    return 0
            elif sort_key == '购书日期':
                return book.start_date or '9999'
            else:  # 添加时间
                return book.isbn  # ISBN 作为添加顺序的近似

        return sorted(books, key=get_sort_value)

    def _on_sort_changed(self, text: str):
        """排序选项改变"""
        self._refresh_grid()

    def _on_columns_changed(self, text: str):
        """每行数量改变"""
        try:
            self._columns = int(text)
            self._refresh_grid()
        except ValueError:
            pass

    def _on_card_clicked(self, isbn: str):
        """卡片点击事件"""
        self.book_selected.emit(isbn)

    def _on_card_double_clicked(self, isbn: str):
        """卡片双击事件"""
        self.book_opened.emit(isbn)

    def _on_card_context_menu(self, isbn: str, pos):
        """卡片右键菜单事件"""
        self.book_context_menu.emit(isbn, pos)
