"""
┌──────────────────────────────────────────┐
│  主窗口                                  │
│                                          │
│  应用的中央协调者，连接：                  │
│    UI 表单 ↔ 数据库 ↔ 豆瓣 API ↔ Web     │
│    CSV 导入导出 ↔ 自动备份 ↔ 主题切换     │
└──────────────────────────────────────────┘
"""

import os
import base64
import webbrowser

import pandas as pd
from PyQt6.QtCore import Qt, QThread, QTimer, QSettings, QObject, QDate, QByteArray, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QFont, QShortcut, QKeySequence, QPalette
from PyQt6.QtWidgets import (
  QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
  QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QTableView,
  QDateEdit, QFileDialog, QMessageBox, QMenu, QHeaderView, QStatusBar, QProgressDialog,
  QAbstractSpinBox, QDialog, QListWidget, QListWidgetItem, QDialogButtonBox, QFrame,
)

from config import Config
from models.book import Book
from services import get_repo
from services.douban import DoubanService
from services.backup import BackupService

from ui.theme import DARK_QSS, LIGHT_QSS


class MainWindow(QMainWindow):
  """
  主窗口——所有功能的入口点。

  布局从上到下：
    工具栏（CSV / 统计 / 豆瓣搜索 / Web / 主题）
    图书编辑表单（ISBN 查询 / 新增 / 修改）
    搜索栏（关键词 + 状态下拉）
    图书列表表格（可排序、右键菜单）

  init 流程：
    _setup_ui()         → 构建所有界面控件
    _init_table()       → 初始化表格模型
    _connect_signals()  → 绑定信号槽
    _setup_shortcuts()  → 注册快捷键
    _setup_backup_timer() → 启动定时备份
    _load_settings()    → 恢复上次关闭时的状态
  """

  def __init__(self):
    super().__init__()
    self._repo = get_repo()
    self._api = DoubanService()
    self._backup_svc = BackupService()
    self._dirty = False
    self._dark_mode = True
    self._setup_ui()
    self._init_table()
    self._connect_signals()
    self._setup_shortcuts()
    self._setup_backup_timer()
    self._load_settings()

  # ══════════════════════════════════════════════
  #  UI 构建
  # ══════════════════════════════════════════════

  def _setup_ui(self):
    """构建主窗口的全部控件和布局"""
    self.setWindowTitle(Config.APP_NAME)
    from ui.icon import make_app_icon
    self.setWindowIcon(make_app_icon())
    self.resize(*Config.MAIN_WINDOW_SIZE)
    self.setMinimumSize(800, 500)

    central = QWidget()
    self.setCentralWidget(central)
    layout = QVBoxLayout(central)
    layout.setContentsMargins(10, 6, 10, 6)
    layout.setSpacing(4)

    layout.addWidget(self._make_toolbar())
    layout.addWidget(self._make_book_form())
    layout.addWidget(self._make_search_bar())

    # 主内容区容器，用于切换表格视图和封面墙视图
    self._content_stack = QWidget()
    self._content_stack_layout = QVBoxLayout(self._content_stack)
    self._content_stack_layout.setContentsMargins(0, 0, 0, 0)
    self._content_stack_layout.setSpacing(0)

    # 图书表格视图
    self._table = QTableView()
    self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self._table.setAlternatingRowColors(True)
    self._table.setSortingEnabled(True)
    self._table.verticalHeader().setVisible(False)
    self._table.verticalHeader().setDefaultSectionSize(30)
    hdr = self._table.horizontalHeader()
    hdr.setSectionsMovable(True)
    hdr.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    hdr.customContextMenuRequested.connect(self._show_header_menu)
    self._content_stack_layout.addWidget(self._table)

    # 封面墙视图
    from ui.cover_wall import CoverWallWidget
    self._cover_wall = CoverWallWidget()
    self._cover_wall.book_selected.connect(self._on_cover_wall_selected)
    self._cover_wall.book_opened.connect(self._on_cover_wall_opened)
    self._cover_wall.book_context_menu.connect(self._on_cover_wall_context_menu)
    self._cover_wall.hide()  # 默认隐藏
    self._content_stack_layout.addWidget(self._cover_wall)

    # 当前视图模式：True=封面墙，False=表格
    self._is_cover_wall_mode = False

    layout.addWidget(self._content_stack, stretch=1)

    sb = QStatusBar(self)
    sb.setFont(QFont('', 11))
    sb.showMessage('欢迎使用 Bookeeper')
    self.setStatusBar(sb)

  def _make_toolbar(self):
    """顶部工具栏：分组排列，用分隔线区分功能区域"""
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)

    def sep():
      """添加垂直分隔线，颜色跟随主题"""
      line = QFrame()
      line.setFrameShape(QFrame.Shape.VLine)
      line.setFrameShadow(QFrame.Shadow.Sunken)
      c = self.palette().color(QPalette.ColorRole.Mid).name()
      line.setStyleSheet(f'color: {c};')
      row.addWidget(line)

    self._btn_load = QPushButton('📂 加载 CSV')
    self._btn_load.setToolTip('从 CSV 导入图书数据')
    self._btn_save = QPushButton('💾 保存 CSV')
    self._btn_save.setToolTip('导出全部数据为 CSV')
    self._btn_stats = QPushButton('📊 统计')
    self._btn_stats.setToolTip('查看图书统计信息')
    self._btn_search_douban = QPushButton('🌐 豆瓣搜索')
    self._btn_search_douban.setToolTip('从豆瓣搜索图书并添加 (Ctrl+D)')
    self._btn_cover_wall = QPushButton('🖼️ 封面墙')
    self._btn_cover_wall.setToolTip('切换到封面墙视图 (Ctrl+W)')
    self._btn_web = QPushButton('🌐 Web 服务')
    self._btn_web.setToolTip('启动/停止内嵌 Web 服务')
    self._btn_restore = QPushButton('⏪ 恢复')
    self._btn_restore.setToolTip('从备份恢复数据库')
    from ui.icon import make_theme_icon, make_about_icon
    self._btn_theme = QPushButton(make_theme_icon(self._dark_mode), '')
    self._btn_theme.setFixedSize(38, 34)
    self._btn_theme.setToolTip('切换亮色/暗色主题')
    self._btn_about = QPushButton(make_about_icon(), '')
    self._btn_about.setFixedSize(38, 34)
    self._btn_about.setToolTip('关于 Bookeeper')

    for btn in (self._btn_load, self._btn_save, self._btn_stats, self._btn_search_douban, self._btn_cover_wall, self._btn_web, self._btn_restore):
      btn.setFixedHeight(34)
      btn.setMinimumWidth(90)
    for btn in (self._btn_theme, self._btn_about):
      btn.setFixedHeight(34)

    # 数据操作组
    row.addWidget(self._btn_load)
    row.addWidget(self._btn_save)
    sep()
    # 搜索分析组
    row.addWidget(self._btn_search_douban)
    row.addWidget(self._btn_stats)
    row.addWidget(self._btn_cover_wall)
    sep()
    # 服务组
    row.addWidget(self._btn_web)
    row.addWidget(self._btn_restore)
    sep()
    # 设置组
    row.addWidget(self._btn_theme)
    row.addWidget(self._btn_about)

    self._file_label = QLabel('')
    c = self.palette().color(QPalette.ColorRole.PlaceholderText).name()
    self._file_label.setStyleSheet(f'color: {c}; font-size: 12px;')
    row.addWidget(self._file_label, stretch=1)
    return w

  def _make_book_form(self):
    """
    图书信息编辑表单。

    包含两行：
    第一行：ISBN 输入 + 获取/更新/清空按钮
    第二行：书名/作者/出版社
    第三行：价格/评分/状态/书柜/购书日期/已读日期
    """
    g = QGroupBox('📖 图书信息')
    layout = QVBoxLayout(g)
    layout.setContentsMargins(8, 14, 8, 6)
    layout.setSpacing(4)

    # ── 第一行：ISBN + 操作按钮 ──────────────────────────
    r0 = QHBoxLayout()
    r0.setSpacing(4)
    r0.addWidget(QLabel('ISBN'))
    self._isbn_input = QLineEdit()
    self._isbn_input.setPlaceholderText('输入 ISBN（回车即查询豆瓣）')
    r0.addWidget(self._isbn_input, stretch=1)
    self._btn_fetch = QPushButton('🌐 获取信息')
    self._btn_new = QPushButton('➕ 新增')
    self._btn_new.setToolTip('清空表单，手动添加新图书')
    self._btn_update = QPushButton('💾 更新记录')
    self._btn_clear = QPushButton('✕ 清空')
    for btn in (self._btn_fetch, self._btn_new, self._btn_update, self._btn_clear):
      btn.setFixedHeight(34)
      r0.addWidget(btn)
    layout.addLayout(r0)

    # ── 第 2~4 行：改用 QGridLayout 保证列对齐 ──────────
    self._title_input = QLineEdit(placeholderText='书名')
    self._author_input = QLineEdit(placeholderText='作者/译者')
    self._publisher_input = QLineEdit(placeholderText='出版社')
    self._price_input = QLineEdit(placeholderText='定价')
    self._rating_input = QLineEdit(placeholderText='评分/人数')
    self._rating_input.setReadOnly(True)
    self._status_combo = QComboBox()
    self._status_combo.addItems(Config.STATUSES)
    self._status_combo.setCurrentIndex(-1)
    self._shelf_input = QLineEdit(placeholderText='位置')
    self._start_date = QDateEdit()
    self._end_date = QDateEdit()
    for edit in (self._start_date, self._end_date):
      edit.setDisplayFormat('yyyy/M/d')
      edit.setCalendarPopup(False)
      edit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    self._start_date.setDate(QDate(1900, 1, 1))
    self._end_date.setDate(QDate.currentDate())
    grid = QGridLayout()
    grid.setSpacing(4)
    grid.addWidget(QLabel('书名'), 0, 0); grid.addWidget(self._title_input, 0, 1)
    grid.addWidget(QLabel('作者'), 0, 2); grid.addWidget(self._author_input, 0, 3)
    grid.addWidget(QLabel('出版'), 0, 4); grid.addWidget(self._publisher_input, 0, 5)
    grid.addWidget(QLabel('价格'), 1, 0); grid.addWidget(self._price_input, 1, 1)
    grid.addWidget(QLabel('评分'), 1, 2); grid.addWidget(self._rating_input, 1, 3)
    grid.addWidget(QLabel('状态'), 1, 4); grid.addWidget(self._status_combo, 1, 5)
    grid.addWidget(QLabel('书柜'), 2, 0); grid.addWidget(self._shelf_input, 2, 1)
    grid.addWidget(QLabel('购书'), 2, 2); grid.addWidget(self._start_date, 2, 3)
    grid.addWidget(QLabel('已读'), 2, 4); grid.addWidget(self._end_date, 2, 5)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(3, 1)
    grid.setColumnStretch(5, 1)
    layout.addLayout(grid)
    return g

  def _make_search_bar(self):
    """搜索栏：关键词输入 + 状态下拉 + 查询/重置按钮"""
    g = QGroupBox('🔎 搜索')
    row = QHBoxLayout(g)
    row.setContentsMargins(8, 14, 8, 6)
    row.setSpacing(4)

    self._search_input = QLineEdit()
    self._search_input.setPlaceholderText('输入关键词搜索书名/作者/出版社/ISBN')
    self._search_input.setFixedHeight(34)
    row.addWidget(self._search_input, stretch=1)
    row.addWidget(QLabel('状态'))
    self._search_status = QComboBox()
    self._search_status.addItems(['全部'] + Config.STATUSES)
    self._search_status.setCurrentIndex(0)
    self._search_status.setFixedHeight(34)
    row.addWidget(self._search_status)
    self._btn_search = QPushButton('🔎 查询')
    self._btn_search.setFixedHeight(34)
    self._btn_reset = QPushButton('⟲ 重置')
    self._btn_reset.setFixedHeight(34)
    row.addWidget(self._btn_search)
    row.addWidget(self._btn_reset)

    self._search_timer = QTimer(self)
    self._search_timer.setSingleShot(True)
    self._search_timer.timeout.connect(self._search)
    self._search_input.textChanged.connect(self._on_search_text_changed)

    return g

  def _on_search_text_changed(self, text):
    """搜索文本变化时重置定时器（防抖 300ms）"""
    self._search_timer.stop()
    self._search_timer.start(300)

  # ══════════════════════════════════════════════
  #  数据模型
  # ══════════════════════════════════════════════

  def _init_table(self):
    """
    初始化表格模型。

    创建空的 BookTableModel，绑定到 QTableView，
    设置列宽模式，然后加载数据。
    """
    from models.table_model import BookTableModel
    df = pd.DataFrame({c: [] for c in Config.TABLE_COLUMNS}, dtype=object)
    self._model = BookTableModel(df)
    self._table.setModel(self._model)
    # 列宽模式：默认拉伸填满，前三列自动调整内容宽度
    hdr = self._table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    self._load_data()

  def _load_data(self):
    """
    从数据库重新加载全量数据到表格。

    每次增删改查后调用此方法刷新界面。
    数据通过 DataFrame 传给 BookTableModel.load_dataframe()。
    """
    books = self._repo.get_all()
    rows = [b.to_row() for b in books]
    cols = Config.TABLE_COLUMNS
    df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame({c: [] for c in cols}, dtype=object)
    self._model.load_dataframe(df)
    # 同时更新封面墙数据
    if hasattr(self, '_cover_wall'):
      self._cover_wall.set_books(books)
    self._update_status()

  def _toggle_cover_wall(self):
    """切换表格视图和封面墙视图"""
    self._is_cover_wall_mode = not self._is_cover_wall_mode
    if self._is_cover_wall_mode:
      self._table.hide()
      self._cover_wall.show()
      self._btn_cover_wall.setText('📊 表格视图')
      self._btn_cover_wall.setToolTip('切换到表格视图 (Ctrl+W)')
    else:
      self._cover_wall.hide()
      self._table.show()
      self._btn_cover_wall.setText('🖼️ 封面墙')
      self._btn_cover_wall.setToolTip('切换到封面墙视图 (Ctrl+W)')

  def _on_cover_wall_selected(self, isbn: str):
    """封面墙选中图书事件"""
    book = self._repo.get_by_isbn(isbn)
    if book:
      self._fill_form(book)

  def _on_cover_wall_opened(self, isbn: str):
    """封面墙双击打开图书详情事件"""
    self._open_detail(isbn)

  def _on_cover_wall_context_menu(self, isbn: str, pos):
    """封面墙右键菜单事件"""
    menu = QMenu(self)
    view_action = QAction(QIcon(), '📖 查看详情', self)
    edit_action = QAction(QIcon(), '✏️ 编辑', self)
    delete_action = QAction(QIcon(), '🗑 删除', self)
    menu.addAction(view_action)
    menu.addAction(edit_action)
    menu.addSeparator()
    menu.addAction(delete_action)
    action = menu.exec(pos)
    if action == view_action:
      self._open_detail(isbn)
    elif action == edit_action:
      book = self._repo.get_by_isbn(isbn)
      if book:
        self._fill_form(book)
    elif action == delete_action:
      ret = QMessageBox.question(
        self, '确认删除',
        f'确定删除图书？此操作不可撤销。',
      )
      if ret == QMessageBox.StandardButton.Yes:
        self._repo.delete(isbn)
        self._mark_dirty()
        self._load_data()

  # ══════════════════════════════════════════════
  #  信号与快捷键
  # ══════════════════════════════════════════════

  def _connect_signals(self):
    """绑定所有 UI 控件的信号-槽连接"""
    self._isbn_input.returnPressed.connect(self._fetch_book)
    self._btn_fetch.clicked.connect(self._fetch_book)
    self._btn_new.clicked.connect(self._new_book)
    self._btn_update.clicked.connect(self._update_book)
    self._btn_clear.clicked.connect(self._clear_form)
    self._btn_load.clicked.connect(self._load_csv)
    self._btn_save.clicked.connect(self._save_csv)
    self._btn_stats.clicked.connect(self._show_stats)
    self._btn_theme.clicked.connect(self._toggle_theme)
    self._btn_search.clicked.connect(self._search)
    self._btn_reset.clicked.connect(self._reset_search)
    self._btn_search_douban.clicked.connect(self._open_search_dialog)
    self._btn_cover_wall.clicked.connect(self._toggle_cover_wall)
    self._btn_web.clicked.connect(self._toggle_web)
    self._btn_restore.clicked.connect(self._restore_backup)
    self._btn_about.clicked.connect(self._show_about)
    self._table.clicked.connect(self._on_row_clicked)
    self._table.doubleClicked.connect(self._on_double_clicked)
    self._table.customContextMenuRequested.connect(self._show_context_menu)
    self._status_combo.currentTextChanged.connect(self._on_status_changed)
    self._search_input.returnPressed.connect(self._search)

  def _setup_shortcuts(self):
    """注册全局快捷键"""
    QShortcut(QKeySequence('Ctrl+S'), self, self._save_csv)
    QShortcut(QKeySequence('Ctrl+F'), self, self._search_input.setFocus)
    QShortcut(QKeySequence('Ctrl+R'), self, self._reset_search)
    QShortcut(QKeySequence('Ctrl+D'), self, self._open_search_dialog)
    QShortcut(QKeySequence('Ctrl+W'), self, self._toggle_cover_wall)

  # ══════════════════════════════════════════════
  #  自动备份
  # ══════════════════════════════════════════════

  def _setup_backup_timer(self):
    """设置定时备份（默认每 5 分钟）"""
    self._backup_timer = QTimer(self)
    self._backup_timer.timeout.connect(self._do_backup)
    self._backup_timer.start(Config.BACKUP_INTERVAL_MS)

  def _mark_dirty(self):
    """标记数据已变更，下次定时器触发时执行备份"""
    self._dirty = True

  def _do_backup(self):
    """执行定时备份：无数据或数据无变更则跳过"""
    if self._model.rowCount() == 0 or not self._dirty:
      return
    self._dirty = False
    QTimer.singleShot(0, self._backup_svc.backup)

  def closeEvent(self, event):
    """关闭窗口前：停止 Web 线程 + 保存窗口状态 + 强制备份"""
    if hasattr(self, '_web_worker') and self._web_worker:
      self._web_worker.stop()
    if hasattr(self, '_web_thread') and self._web_thread:
      self._web_thread.quit()
      self._web_thread.wait(3000)
    s = self._settings()
    geo = self.saveGeometry().data()
    if geo:
      s.setValue('windowGeometry', base64.b64encode(geo).decode('ascii'))
    if self._model.rowCount():
      self._backup_svc.backup()
    super().closeEvent(event)

  # ══════════════════════════════════════════════
  #  图书操作
  # ══════════════════════════════════════════════

  def _fetch_book(self):
    """从豆瓣 API 获取 ISBN 对应的图书信息并填入表单"""
    from utils import clean_isbn, is_valid_isbn13, is_valid_isbn10
    raw = self._isbn_input.text().strip()
    isbn = clean_isbn(raw)
    if not isbn:
      return

    if len(isbn) == 13 and not is_valid_isbn13(isbn):
      QMessageBox.warning(self, '错误', f'ISBN-13 校验位无效: {isbn}')
      return
    if len(isbn) == 10 and not is_valid_isbn10(isbn):
      QMessageBox.warning(self, '错误', f'ISBN-10 校验位无效: {isbn}')
      return

    # 禁用按钮，显示加载状态
    self._btn_fetch.setEnabled(False)
    self._btn_fetch.setText('⏳ 查询中...')
    self.statusBar().showMessage('正在查询豆瓣...')

    # 使用 QTimer.singleShot 模拟异步（实际仍是同步，但界面会更新）
    QTimer.singleShot(50, lambda: self._do_fetch_book(isbn))

  def _do_fetch_book(self, isbn: str):
    """实际执行豆瓣查询"""
    book = self._api.get_book_by_isbn(isbn)

    # 恢复按钮状态
    self._btn_fetch.setEnabled(True)
    self._btn_fetch.setText('🌐 获取信息')

    if not book:
      QMessageBox.warning(self, '错误', f'未找到图书: {isbn}')
      self.statusBar().showMessage('查询失败')
      return

    self._merge_user_fields(book)
    self._fill_form(book)
    self._repo.upsert(book)
    self._mark_dirty()
    self._load_data()
    self.statusBar().showMessage(f'已获取: {book.title}')

  def _fill_form(self, book: Book):
    """将 Book 对象填充到表单各控件"""
    self._isbn_input.setText(book.isbn)
    self._title_input.setText(book.title)
    self._author_input.setText(book.author)
    self._publisher_input.setText(book.publisher)
    self._price_input.setText(book.price)
    self._rating_input.setText(f'{book.rating} / {book.raters}')
    idx = Config.STATUSES.index(book.status) if book.status in Config.STATUSES else 0
    self._status_combo.blockSignals(True)
    self._status_combo.setCurrentIndex(idx)
    self._status_combo.blockSignals(False)
    self._shelf_input.setText(book.shelf)
    self._set_date(self._start_date, book.start_date)
    self._set_date(self._end_date, book.end_date)

  def _update_book(self):
    """
    从表单读取数据，更新到数据库（使用增量更新）。
    """
    isbn = self._isbn_input.text().strip()
    title = self._title_input.text().strip()
    if not isbn and not title:
      QMessageBox.warning(self, '提示', '请至少填写 ISBN 或书名')
      return
    
    # 获取当前选中行
    selected = self._table.currentIndex()
    row = selected.row() if selected.isValid() else -1
    
    row_data = [
      isbn,
      self._title_input.text(),
      self._author_input.text(),
      self._publisher_input.text(),
      self._price_input.text(),
      self._rating_input.text().split('/')[0].strip() if '/' in self._rating_input.text() else '0',
      self._rating_input.text().split('/')[-1].strip() if '/' in self._rating_input.text() else '0',
      self._status_combo.currentText() or Config.DEFAULT_STATUS,
      self._shelf_input.text() or Config.DEFAULT_SHELF,
      self._get_date(self._start_date),
      self._get_date(self._end_date),
    ]
    
    book = Book(
      isbn=row_data[0], title=row_data[1], author=row_data[2], publisher=row_data[3],
      price=row_data[4], rating=row_data[5], raters=row_data[6], status=row_data[7],
      shelf=row_data[8], start_date=row_data[9], end_date=row_data[10],
    )
    self._repo.upsert(book)
    self._mark_dirty()
    
    # 使用增量更新
    if row >= 0:
      self._model.update_row(row, row_data)
      # 同步封面墙和状态栏
      if hasattr(self, '_cover_wall'):
        self._cover_wall.set_books(self._repo.get_all())
      self._update_status()
    else:
      self._load_data()
    
    self.statusBar().showMessage('已更新')

  def _clear_form(self):
    """清空表单所有输入，聚焦到 ISBN 输入框"""
    self._isbn_input.clear()
    self._title_input.clear()
    self._author_input.clear()
    self._publisher_input.clear()
    self._price_input.clear()
    self._rating_input.clear()
    self._status_combo.setCurrentIndex(-1)
    self._shelf_input.clear()
    self._start_date.setDate(QDate(1900, 1, 1))
    self._end_date.setDate(QDate(1900, 1, 1))
    self._isbn_input.setFocus()

  def _new_book(self):
    """清空表单，聚焦到书名输入框，方便手动添加新图书"""
    self._clear_form()
    self._title_input.setFocus()

  def _on_row_clicked(self, index):
    """点击表格行时，将选中行数据填充到表单"""
    def val(col):
      v = index.sibling(index.row(), col).data()
      return str(v) if v is not None else ''

    self._isbn_input.setText(val(0))
    self._title_input.setText(val(1))
    self._author_input.setText(val(2))
    self._publisher_input.setText(val(3))
    self._price_input.setText(val(4))
    self._rating_input.setText(f'{val(5)} / {val(6)}')
    status = val(7)
    self._status_combo.blockSignals(True)
    self._status_combo.setCurrentIndex(
      Config.STATUSES.index(status) if status in Config.STATUSES else -1)
    self._status_combo.blockSignals(False)
    self._shelf_input.setText(val(8))
    self._set_date(self._start_date, val(9))
    self._set_date(self._end_date, val(10))

  def _on_double_clicked(self, index):
    """双击打开图书详情对话框"""
    clicked_isbn = str(index.sibling(index.row(), 0).data() or '')
    if clicked_isbn:
      self._open_detail(clicked_isbn)

  def _open_detail(self, isbn: str):
    """打开指定 ISBN 的详情对话框"""
    isbn_list = []
    clicked_idx = 0
    for r in range(self._model.rowCount()):
      row_isbn = str(self._model.index(r, 0).data() or '')
      if row_isbn:
        isbn_list.append(row_isbn)
        if row_isbn == isbn:
          clicked_idx = len(isbn_list) - 1
    from ui.detail_dialog import DetailDialog
    dlg = DetailDialog(isbn_list=isbn_list, index=clicked_idx, parent=self)
    dlg.exec()

  def _load_by_isbn(self, isbn: str):
    """根据 ISBN 从数据库加载图书到表单"""
    book = self._repo.get_by_isbn(isbn)
    if book:
      self._fill_form(book)

  def _on_status_changed(self, text: str):
    """状态设为'已读'时自动填入日期，切回非'已读'时重置"""
    if text == '已读':
      if self._end_date.date() <= QDate(1900, 1, 1):
        self._end_date.setDate(QDate.currentDate())
      if self._start_date.date() <= QDate(1900, 1, 1):
        self._start_date.setDate(QDate.currentDate())
    else:
      self._end_date.setDate(QDate(1900, 1, 1))

  def _show_context_menu(self, pos):
    """表格右键菜单：删除选中行、批量修改状态"""
    if self._model.rowCount() == 0:
      return
    indexes = self._table.selectedIndexes()
    isbn_list = []
    seen = set()
    for idx in indexes:
      if idx.column() != 0:
        continue
      v = idx.data()
      if v and v not in seen:
        seen.add(v)
        isbn_list.append(str(v))
    if not isbn_list:
      return
    menu = QMenu(self)
    view_action = QAction(QIcon(), '📖 查看详情', self)
    edit_action = QAction(QIcon(), '✏️ 编辑', self)
    delete_action = QAction(QIcon(), '🗑 删除选中', self)

    # 批量操作子菜单
    batch_menu = QMenu('批量操作', menu)
    for status in Config.STATUSES:
      action = QAction(QIcon(), f'设为"{status}"', batch_menu)
      action.setData(('status', status))
      batch_menu.addAction(action)

    menu.addAction(view_action)
    menu.addAction(edit_action)
    menu.addSeparator()
    menu.addMenu(batch_menu)
    menu.addSeparator()
    menu.addAction(delete_action)

    action = menu.exec(self._table.mapToGlobal(pos))
    if action == view_action and isbn_list:
      self._open_detail(isbn_list[0])
    elif action == edit_action and isbn_list:
      self._load_by_isbn(isbn_list[0])
    elif action and action.data() and action.data()[0] == 'status':
      new_status = action.data()[1]
      self._batch_update_status(isbn_list, new_status)
    elif action == delete_action:
      ret = QMessageBox.question(
        self, '确认删除',
        f'确定删除选中的 {len(isbn_list)} 本图书？此操作不可撤销。',
      )
      if ret != QMessageBox.StandardButton.Yes:
        return
      for isbn in isbn_list:
        self._repo.delete(isbn)
      self._mark_dirty()
      self._load_data()

  def _batch_update_status(self, isbn_list: list, new_status: str):
    """批量修改图书状态"""
    for isbn in isbn_list:
      book = self._repo.get_by_isbn(isbn)
      if book:
        book.status = new_status
        self._repo.upsert(book)
    self._mark_dirty()
    self._load_data()
    self.statusBar().showMessage(f'已将 {len(isbn_list)} 本图书设为"{new_status}"')

  # ══════════════════════════════════════════════
  #  搜索
  # ══════════════════════════════════════════════

  def _search(self):
    """按关键词和状态筛选图书"""
    keyword = self._search_input.text().strip()
    status = self._search_status.currentText()
    if status == '全部':
      status = ''
    books = self._repo.search(keyword, status)
    rows = [b.to_row() for b in books]
    cols = Config.TABLE_COLUMNS
    df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame({c: [] for c in cols}, dtype=object)
    self._model.load_dataframe(df)
    # 同时更新封面墙数据
    if hasattr(self, '_cover_wall'):
      self._cover_wall.set_books(books)
    self._update_status()

  def _reset_search(self):
    """重置搜索条件，显示全部图书"""
    self._search_input.clear()
    self._search_status.setCurrentIndex(0)
    self._load_data()

  def _open_search_dialog(self):
    """打开豆瓣搜索对话框"""
    from ui.search_dialog import SearchDialog
    dlg = SearchDialog(self)
    keyword = self._title_input.text().strip()
    if len(keyword) >= 2:
      dlg.set_keyword(keyword)
    dlg.book_selected.connect(self._on_search_result)
    dlg.exec()

  def _on_search_result(self, book: Book):
    """豆瓣搜索结果回调：填入表单并存入数据库"""
    self._merge_user_fields(book)
    # 如果是新书（ISBN不存在）且购书日期为空，设置为当前日期
    if not book.start_date:
      book.start_date = QDate.currentDate().toString('yyyy-MM-dd')
    self._fill_form(book)
    self._repo.upsert(book)
    self._mark_dirty()
    self._load_data()
    self.statusBar().showMessage(f'已从豆瓣添加: {book.title}')

  # ══════════════════════════════════════════════
  #  文件操作
  # ══════════════════════════════════════════════

  def _load_csv(self):
    """
    加载 CSV 文件并异步导入到数据库。

    CSV 读取在主线程完成（快速），
    数据库写入移至后台线程，避免大文件时 UI 冻结。
    """
    path, _ = QFileDialog.getOpenFileName(self, '加载 CSV', '.', 'CSV 文件 (*.csv)')
    if not path:
      return
    try:
      from services.data import load_csv
      df = load_csv(path)
    except Exception as e:
      QMessageBox.warning(self, '错误', f'读取 CSV 失败: {e}')
      return

    self._btn_load.setEnabled(False)
    self._import_progress = QProgressDialog('正在导入 CSV...', None, 0, len(df), self)
    self._import_progress.setWindowTitle('导入中')
    self._import_progress.setMinimumDuration(0)
    self._import_progress.show()

    self._import_thread = QThread()
    self._import_worker = _ImportWorker(self._repo, df)
    self._import_worker.moveToThread(self._import_thread)
    self._import_thread.started.connect(self._import_worker.run)
    self._import_worker.progress.connect(self._on_import_progress)
    self._import_worker.finished.connect(self._on_import_finished)
    self._import_worker.failed.connect(self._on_import_failed)
    self._import_thread.start()

  def _on_import_progress(self, current, total):
    if self._import_progress and not self._import_progress.wasCanceled():
      self._import_progress.setValue(current)

  def _on_import_finished(self, count):
    if self._import_progress:
      self._import_progress.close()
    self._import_thread.quit()
    self._import_thread.wait(3000)
    self._btn_load.setEnabled(True)
    self._mark_dirty()
    self._load_data()
    self._file_label.setText(f'已导入 {count} 条')
    QMessageBox.information(self, '提示', f'导入完成，共处理 {count} 条记录')

  def _on_import_failed(self, msg):
    if self._import_progress:
      self._import_progress.close()
    self._import_thread.quit()
    self._import_thread.wait(3000)
    self._btn_load.setEnabled(True)
    QMessageBox.warning(self, '错误', f'导入失败: {msg}')

  def _save_csv(self):
    """导出全部数据为 CSV 文件"""
    path, _ = QFileDialog.getSaveFileName(self, '保存 CSV', '.', 'CSV 文件 (*.csv)')
    if not path:
      return
    try:
      df = self._repo.export_df()
      from services.data import save_csv
      save_csv(path, df)
      QMessageBox.information(self, '提示', '保存成功')
    except Exception as e:
      QMessageBox.warning(self, '错误', f'保存失败: {e}')

  def _restore_backup(self):
    """从备份恢复数据库"""
    backups = self._backup_svc.list_backups()
    if not backups:
      QMessageBox.information(self, '提示', '暂无可用备份')
      return
    dlg = QDialog(self)
    dlg.setWindowTitle('选择备份')
    dlg.setMinimumSize(420, 360)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel('选择要恢复的备份（当前数据会自动保存一份）：'))
    listw = QListWidget()
    for path, name in backups:
      item = QListWidgetItem(name)
      item.setData(Qt.ItemDataRole.UserRole, path)
      listw.addItem(item)
    listw.setCurrentRow(0)
    layout.addWidget(listw)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    if dlg.exec() != QDialog.DialogCode.Accepted:
      return
    item = listw.currentItem()
    if not item:
      return
    backup_path = item.data(Qt.ItemDataRole.UserRole)
    ret = QMessageBox.question(
      self, '确认恢复',
      f'确定从以下备份恢复？\n\n{item.text()}\n\n当前数据会先自动备份一份。',
    )
    if ret != QMessageBox.StandardButton.Yes:
      return
    if self._backup_svc.restore(backup_path):
      self._dirty = False
      self._load_data()
      QMessageBox.information(self, '提示', '恢复成功')
    else:
      QMessageBox.warning(self, '错误', '恢复失败')

  def _show_stats(self):
    """打开统计面板"""
    from ui.stats_dialog import StatsDialog
    dlg = StatsDialog(self._repo, self, dark_mode=self._dark_mode)
    dlg.exec()

  # ══════════════════════════════════════════════
  #  Web 服务
  # ══════════════════════════════════════════════

  def _toggle_web(self):
    """
    启动/停止内嵌 FastAPI Web 服务。

    启动时创建独立线程运行 uvicorn，
    避免阻塞 Qt 事件循环。
    """
    if self._btn_web.text() == '🛑 停止服务':
      if hasattr(self, '_web_worker') and self._web_worker:
        self._web_worker.stop()
        self._web_thread.quit()
        self._web_thread.wait(3000)
      self._btn_web.setText('🌐 Web 服务')
      self.statusBar().showMessage('Web 服务已停止')
      return

    self._btn_web.setText('⏳ 启动中...')
    self.statusBar().showMessage('正在启动 Web 服务...')
    self._web_thread = QThread()
    self._web_worker = _WebWorker()
    self._web_worker.moveToThread(self._web_thread)
    self._web_thread.started.connect(self._web_worker.run)
    self._web_worker.started.connect(self._on_web_started)
    self._web_worker.failed.connect(self._on_web_failed)
    self._web_thread.start()

  def _on_web_started(self):
    """Web 服务启动成功：更新按钮状态，在浏览器中打开"""
    url = f'http://127.0.0.1:{Config.WEB_PORT}'
    self._btn_web.setText('🛑 停止服务')
    self.statusBar().showMessage(f'Web 服务已启动: {url}')
    webbrowser.open(url)

  def _on_web_failed(self, msg: str):
    """Web 服务启动失败：恢复按钮状态"""
    self._btn_web.setText('🌐 Web 服务')
    self.statusBar().showMessage(f'Web 服务启动失败: {msg}')

  # ══════════════════════════════════════════════
  #  主题与设置
  # ══════════════════════════════════════════════

  def _toggle_theme(self):
    """切换暗色/亮色主题"""
    self._dark_mode = not self._dark_mode
    qss = DARK_QSS if self._dark_mode else LIGHT_QSS
    self.setStyleSheet(qss)
    from ui.icon import make_theme_icon
    self._btn_theme.setIcon(make_theme_icon(self._dark_mode))
    s = self._settings()
    s.setValue('darkMode', self._dark_mode)

  def _show_about(self):
    """显示关于对话框"""
    QMessageBox.about(
      self, '关于 Bookeeper',
      f'<h3>📚 Bookeeper v{Config.APP_VERSION}</h3>'
      '<p>个人图书管理工具</p>'
      '<p>功能：豆瓣 API 查询、ISBN 校验、CSV 导入导出、'
      '统计面板、自动备份、局域网 Web 服务</p>'
      '<p>技术栈：PyQt6 + FastAPI + SQLite + matplotlib</p>'
    )

  def _settings(self):
    """读取 settings.ini（存储窗口状态和偏好设置）"""
    return QSettings(os.path.join(os.path.dirname(__file__), '..', 'settings.ini'),
                     QSettings.Format.IniFormat)

  def _load_settings(self):
    """恢复上次保存的主题、表头状态和窗口几何"""
    s = self._settings()
    self._dark_mode = s.value('darkMode', 'true') == 'true'
    if not self._dark_mode:
      self.setStyleSheet(LIGHT_QSS)
      from ui.icon import make_theme_icon
      self._btn_theme.setIcon(make_theme_icon(False))
    geo_b64 = s.value('windowGeometry', '')
    if geo_b64:
      try:
        self.restoreGeometry(QByteArray(base64.b64decode(geo_b64)))
      except Exception:
        pass
    self._restore_header_state()

  def _show_header_menu(self, pos):
    """表头右键菜单：显隐列"""
    hdr = self._table.horizontalHeader()
    menu = QMenu(self)
    for col in range(hdr.count()):
      name = self._model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
      action = menu.addAction(name)
      action.setCheckable(True)
      action.setChecked(not hdr.isSectionHidden(col))
      action.setData(col)
      action.triggered.connect(lambda _, c=col: self._toggle_column(c))
    menu.exec(hdr.mapToGlobal(pos))

  def _toggle_column(self, col):
    """切换列的显隐"""
    hdr = self._table.horizontalHeader()
    hdr.setSectionHidden(col, not hdr.isSectionHidden(col))
    self._save_header_state()

  def _save_header_state(self):
    """将表头状态（列顺序、宽度、可见性）保存到 settings.ini（防抖 500ms）"""
    if hasattr(self, '_header_save_timer'):
      self._header_save_timer.stop()
    self._header_save_timer = QTimer(self)
    self._header_save_timer.setSingleShot(True)
    self._header_save_timer.timeout.connect(self._do_save_header_state)
    self._header_save_timer.start(500)

  def _do_save_header_state(self):
    """实际执行表头状态保存"""
    state = self._table.horizontalHeader().saveState().data()
    s = self._settings()
    s.setValue('headerState', base64.b64encode(state).decode('ascii'))

  def _restore_header_state(self):
    """从 settings.ini 恢复表头状态"""
    hdr = self._table.horizontalHeader()
    s = self._settings()
    state_b64 = s.value('headerState', '')
    if state_b64:
      try:
        hdr.restoreState(QByteArray(base64.b64decode(state_b64)))
      except Exception:
        pass
    # 断开旧的信号连接以防重复绑定
    try:
      hdr.sectionMoved.disconnect()
    except TypeError:
      pass
    try:
      hdr.sectionResized.disconnect()
    except TypeError:
      pass
    hdr.sectionMoved.connect(self._save_header_state)
    hdr.sectionResized.connect(self._save_header_state)

  def _update_status(self):
    """更新状态栏：显示记录总数和当前筛选数"""
    total = self._repo.count()
    visible = self._model.rowCount()
    txt = f'共 {total} 条记录'
    if visible != total and total > 0:
      txt = f'已筛选 {visible}/{total} 条记录'
    self.statusBar().showMessage(f'{txt}  |  {Config.APP_NAME} v{Config.APP_VERSION}')

  # ══════════════════════════════════════════════
  #  辅助
  # ══════════════════════════════════════════════

  def _merge_user_fields(self, book: Book):
    """如果 ISBN 已存在，将用户字段（状态/书柜/日期）从旧记录继承到新 book"""
    existing = self._repo.get_by_isbn(book.isbn)
    if existing:
      book.status = existing.status
      book.shelf = existing.shelf
      book.start_date = existing.start_date
      book.end_date = existing.end_date

  @staticmethod
  def _set_date(edit: QDateEdit, text: str):
    """
    设置日期控件的值。

    如果传入的文本无效或为空，重置为 1900-01-01。
    1900-01-01 被特殊处理为"未设置"。
    """
    if text and text.strip():
      d = QDate.fromString(text.strip(), 'yyyy-MM-dd')
      if d.isValid():
        edit.setDate(d)
        return
    edit.setDate(QDate(1900, 1, 1))

  @staticmethod
  def _get_date(edit: QDateEdit) -> str:
    """
    获取日期控件的文本。

    1900-01-01 被视为"未设置"，返回空字符串。
    """
    d = edit.date()
    if d.isValid() and d > QDate(1900, 1, 1):
      return d.toString('yyyy-MM-dd')
    return ''


class _WebWorker(QObject):
  """
  在后台线程中运行 FastAPI Web 服务。

  为什么需要这个类？
    uvicorn.run() 是阻塞调用，如果在主线程执行，
    Qt 界面会卡死。通过 moveToThread + 信号驱动，
    让 Web 服务在独立线程中运行。
  """

  started = pyqtSignal()      # 服务启动成功
  failed = pyqtSignal(str)    # 服务启动失败，附带错误消息

  def __init__(self):
    super().__init__()
    self._server = None

  def run(self):
    try:
      from web.server import BookWebServer
      self._server = BookWebServer()
      self.started.emit()
      self._server.start()
    except Exception as e:
      self.failed.emit(str(e))

  def stop(self):
    if self._server:
      self._server.stop()


class _ImportWorker(QObject):
  """
  后台导入 CSV 的工作线程。

  在独立线程中执行 import_df，通过信号汇报进度和结果，
  避免大文件导入时 UI 卡死。
  """

  progress = pyqtSignal(int, int)    # (current, total)
  finished = pyqtSignal(int)         # 导入成功的条数
  failed = pyqtSignal(str)           # 错误消息

  def __init__(self, repo, df):
    super().__init__()
    self._repo = repo
    self._df = df

  def run(self):
    try:
      count = self._repo.import_df(self._df, progress_callback=self._on_progress)
      self.finished.emit(count)
    except Exception as e:
      self.failed.emit(str(e))

  def _on_progress(self, current, total):
    self.progress.emit(current, total)
