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

import pandas as pd
from PyQt6.QtCore import Qt, QThread, QTimer, QSettings, QObject, QDate, QByteArray, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QFont, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
  QMainWindow, QWidget, QVBoxLayout,
  QLabel, QPushButton, QTableView,
  QFileDialog, QMessageBox, QMenu, QHeaderView, QStatusBar, QProgressDialog,
  QDialog, QListWidget, QListWidgetItem, QDialogButtonBox,
)

from config import Config
from core.models.book import Book
from services import get_repo
from services.douban import DoubanService
from services.backup import BackupService
from services.undo import UndoManager, AddBookCommand, DeleteBookCommand, UpdateBookCommand

from ui.theme import DARK_QSS, LIGHT_QSS
from ui.components import BookFormWidget, SearchBarWidget, ToolBarWidget, WebManager


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
    self._undo_manager = UndoManager()
    self._dirty = False
    self._dark_mode = True
    self._setup_ui()
    self._init_table()
    self._connect_signals()
    self._setup_shortcuts()
    self._setup_backup_timer()
    self._load_settings()

    # 初始化 Web 管理器
    self._web_manager = WebManager(self)
    self._web_manager.server_started.connect(self._on_web_started)
    self._web_manager.server_stopped.connect(self._on_web_stopped)
    self._web_manager.error_occurred.connect(self._on_web_failed)
    self._web_manager.data_changed.connect(self._on_web_data_changed)  # 安全跨线程投递

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

    self._toolbar = ToolBarWidget(self._dark_mode)
    layout.addWidget(self._toolbar)

    # 表单折叠按钮
    from PyQt6.QtWidgets import QToolButton
    self._form_toggle = QToolButton()
    self._form_toggle.setText('📖 图书信息 ▾')
    self._form_toggle.setCheckable(True)
    self._form_toggle.setChecked(True)
    self._form_toggle.setStyleSheet('QToolButton { border: none; font-weight: bold; padding: 4px; }')
    self._form_toggle.toggled.connect(self._toggle_form)
    layout.addWidget(self._form_toggle)

    self._book_form = BookFormWidget()
    layout.addWidget(self._book_form)
    self._search_bar = SearchBarWidget()
    layout.addWidget(self._search_bar)

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
    self._table.verticalHeader().setDefaultSectionSize(34)
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

  def _toggle_form(self, checked: bool):
    """切换表单显示/隐藏"""
    self._book_form.setVisible(checked)
    self._form_toggle.setText('📖 图书信息 ▾' if checked else '📖 图书信息 ▸')

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
    else:
      self._cover_wall.hide()
      self._table.show()
    self._toolbar.set_cover_wall_mode(self._is_cover_wall_mode)

  def _on_cover_wall_selected(self, isbn: str):
    """封面墙选中图书事件"""
    book = self._repo.get_by_isbn(isbn)
    if book:
      self._book_form.fill_form(book)

  def _on_cover_wall_opened(self, isbn: str):
    """封面墙双击打开图书详情事件"""
    self._open_detail(isbn)

  def _make_book_menu(self, isbn_list: list, pos, has_batch: bool = False):
    """
    创建图书右键菜单（表格/封面墙共用工厂）。

    返回选中的 action，由调用方处理执行逻辑。
    """
    menu = QMenu(self)
    view_action = QAction('查看详情', self)
    edit_action = QAction('编辑', self)
    delete_action = QAction(f'删除{"选中" if len(isbn_list) > 1 else ""}', self)

    batch_menu = QMenu('批量操作', menu)
    for status in Config.STATUSES:
      action = QAction(f'设为"{status}"', batch_menu)
      action.setData(('status', status))
      batch_menu.addAction(action)

    menu.addAction(view_action)
    menu.addAction(edit_action)
    if has_batch:
      menu.addSeparator()
      menu.addMenu(batch_menu)
    menu.addSeparator()
    menu.addAction(delete_action)

    action = menu.exec(pos)
    return action, view_action, edit_action, delete_action

  def _on_cover_wall_context_menu(self, isbn: str, pos):
    """封面墙右键菜单事件"""
    action, view_action, edit_action, delete_action = self._make_book_menu(
      [isbn], pos, has_batch=False)
    if action == view_action:
      self._open_detail(isbn)
    elif action == edit_action:
      book = self._repo.get_by_isbn(isbn)
      if book:
        self._book_form.fill_form(book)
    elif action == delete_action:
      ret = QMessageBox.question(
        self, '确认删除',
        '确定删除这本图书？可通过 Ctrl+Z 撤销。',
      )
      if ret == QMessageBox.StandardButton.Yes:
        book = self._repo.get_by_isbn(isbn)
        if book:
          self._undo_manager.execute(DeleteBookCommand(self._repo, book))
        self._mark_dirty()
        self._load_data()

  # ══════════════════════════════════════════════
  #  信号与快捷键
  # ══════════════════════════════════════════════

  def _connect_signals(self):
    """绑定所有 UI 控件的信号-槽连接"""
    # 书表单组件信号
    self._book_form.fetch_requested.connect(self._fetch_book)
    self._book_form.update_requested.connect(self._update_book)
    # 工具栏组件信号
    self._toolbar.import_requested.connect(self._load_csv)
    self._toolbar.export_requested.connect(self._save_csv)
    self._toolbar.stats_requested.connect(self._show_stats)
    self._toolbar.theme_toggled.connect(self._toggle_theme)
    self._toolbar.douban_search_requested.connect(self._open_search_dialog)
    self._toolbar.cover_wall_requested.connect(self._toggle_cover_wall)
    self._toolbar.web_toggled.connect(self._toggle_web)
    self._toolbar.backup_requested.connect(self._restore_backup)
    self._toolbar.about_requested.connect(self._show_about)
    # 搜索栏组件信号
    self._search_bar.search_requested.connect(self._on_search_requested)
    self._search_bar.reset_requested.connect(self._reset_search)
    # 表格信号
    self._table.clicked.connect(self._on_row_clicked)
    self._table.doubleClicked.connect(self._on_double_clicked)
    self._table.customContextMenuRequested.connect(self._show_context_menu)

  def _setup_shortcuts(self):
    """注册全局快捷键"""
    QShortcut(QKeySequence('Ctrl+S'), self, self._save_csv)
    QShortcut(QKeySequence('Ctrl+F'), self, self._search_bar.focus_input)
    QShortcut(QKeySequence('Ctrl+R'), self, self._reset_search)
    QShortcut(QKeySequence('Ctrl+D'), self, self._open_search_dialog)
    QShortcut(QKeySequence('Ctrl+W'), self, self._toggle_cover_wall)
    QShortcut(QKeySequence('Ctrl+Z'), self, self._undo)
    QShortcut(QKeySequence('Ctrl+Y'), self, self._redo)
    QShortcut(QKeySequence('Ctrl+Shift+Z'), self, self._redo)

  def _undo(self):
    """撤销上一个操作"""
    if self._undo_manager.undo():
      self._load_data()
      self.statusBar().showMessage('已撤销')
    else:
      self.statusBar().showMessage('没有可撤销的操作')

  def _redo(self):
    """重做上一个撤销的操作"""
    if self._undo_manager.redo():
      self._load_data()
      self.statusBar().showMessage('已重做')
    else:
      self.statusBar().showMessage('没有可重做的操作')

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
    self._web_manager.cleanup()
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
    isbn = self._book_form.get_isbn()
    if not isbn:
      return

    raw_isbn = clean_isbn(isbn)
    if not raw_isbn:
      return

    if len(raw_isbn) == 13 and not is_valid_isbn13(raw_isbn):
      QMessageBox.warning(self, 'ISBN 格式错误',
        f'ISBN-13 校验位无效：{raw_isbn}\n\n请检查数字是否输入正确（13位数字）。')
      return
    if len(raw_isbn) == 10 and not is_valid_isbn10(raw_isbn):
      QMessageBox.warning(self, 'ISBN 格式错误',
        f'ISBN-10 校验位无效：{raw_isbn}\n\n请检查数字或末位校验码（X/x 表示 10）。')
      return

    # 禁用按钮，显示加载状态
    self._book_form.set_fetch_enabled(False)
    self._book_form.set_fetch_text('查询中...')
    self.statusBar().showMessage('正在查询豆瓣...')

    # 异步执行查询
    self._do_fetch_book(raw_isbn)

  def _do_fetch_book(self, isbn: str):
    """实际执行豆瓣查询（异步）"""
    # 先停止旧线程，防止快速重复调用时泄漏
    if hasattr(self, '_fetch_thread') and self._fetch_thread and self._fetch_thread.isRunning():
      self._fetch_thread.quit()
      self._fetch_thread.wait(1000)

    # 创建 worker 和线程
    self._fetch_worker = _FetchBookWorker(self._api, isbn)
    self._fetch_thread = QThread()
    self._fetch_worker.moveToThread(self._fetch_thread)

    # 连接信号
    self._fetch_worker.finished.connect(self._on_fetch_success)
    self._fetch_worker.failed.connect(self._on_fetch_error)
    self._fetch_thread.finished.connect(self._fetch_thread.deleteLater)

    # 启动查询
    self._fetch_thread.started.connect(self._fetch_worker.run)
    self._fetch_thread.start()

  def _on_fetch_success(self, book):
    """豆瓣查询成功回调"""
    # 恢复按钮状态
    self._book_form.set_fetch_enabled(True)
    self._book_form.set_fetch_text('🌐 获取信息')

    self._merge_user_fields(book)
    self._book_form.fill_form(book)
    # 已存在的书走 Update，否则撤销会误删整条记录
    old_book = self._repo.get_by_isbn(book.isbn)
    if old_book:
      self._undo_manager.execute(UpdateBookCommand(self._repo, old_book, book))
    else:
      self._undo_manager.execute(AddBookCommand(self._repo, book))
    self._mark_dirty()
    self._load_data()
    self.statusBar().showMessage(f'已获取: {book.title}')

  def _on_fetch_error(self, error_msg: str):
    """豆瓣查询失败回调"""
    # 恢复按钮状态
    self._book_form.set_fetch_enabled(True)
    self._book_form.set_fetch_text('获取信息')
    QMessageBox.warning(self, '查询失败',
      f'无法从豆瓣获取图书信息：\n{error_msg}\n\n请检查网络连接后重试。')
    self.statusBar().showMessage('查询失败')

  def _update_book(self):
    """
    从表单读取数据，更新到数据库（使用增量更新）。
    """
    isbn = self._book_form.get_isbn()
    title = self._book_form.get_form_data()['title']
    if not isbn and not title:
      QMessageBox.warning(self, '信息不完整', '请至少填写 ISBN 或书名，然后再点击更新。')
      return
    
    row_data = self._book_form.get_row_data()
    
    book = Book(
      isbn=row_data[0], title=row_data[1], author=row_data[2], publisher=row_data[3],
      price=row_data[4], rating=row_data[5], raters=row_data[6], status=row_data[7],
      shelf=row_data[8], start_date=row_data[9], end_date=row_data[10],
    )
    old_book = self._repo.get_by_isbn(isbn)
    if old_book:
      self._undo_manager.execute(UpdateBookCommand(self._repo, old_book, book))
    else:
      self._undo_manager.execute(AddBookCommand(self._repo, book))
    self._mark_dirty()
    
    # 全量刷新数据（排序后视觉行号可能已错位，不能用增量更新）
    self._load_data()
    
    self.statusBar().showMessage('已更新')

  def _on_row_clicked(self, index):
    """点击表格行时，选中整行并将数据填充到表单"""
    # 选中整行，保持视觉选中与表单数据同步
    self._table.selectRow(index.row())

    def val(col):
      v = index.sibling(index.row(), col).data()
      return str(v) if v is not None else ''

    row_data = [val(i) for i in range(11)]
    self._book_form.fill_from_row(row_data)

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
      self._book_form.fill_form(book)

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
    action, view_action, edit_action, delete_action = self._make_book_menu(
      isbn_list, self._table.mapToGlobal(pos), has_batch=True)
    if action == view_action:
      self._open_detail(isbn_list[0])
    elif action == edit_action:
      self._load_by_isbn(isbn_list[0])
    elif action and action.data() and action.data()[0] == 'status':
      new_status = action.data()[1]
      self._batch_update_status(isbn_list, new_status)
    elif action == delete_action:
      ret = QMessageBox.question(
        self, '确认删除',
        f'确定删除选中的 {len(isbn_list)} 本图书？可通过 Ctrl+Z 撤销。',
      )
      if ret != QMessageBox.StandardButton.Yes:
        return
      for isbn in isbn_list:
        book = self._repo.get_by_isbn(isbn)
        if book:
          self._undo_manager.execute(DeleteBookCommand(self._repo, book))
      self._mark_dirty()
      self._load_data()

  def _batch_update_status(self, isbn_list: list, new_status: str):
    """批量修改图书状态"""
    import copy
    for isbn in isbn_list:
      book = self._repo.get_by_isbn(isbn)
      if book:
        new_book = copy.copy(book)
        new_book.status = new_status
        self._undo_manager.execute(UpdateBookCommand(self._repo, book, new_book))
    self._mark_dirty()
    self._load_data()
    self.statusBar().showMessage(f'已将 {len(isbn_list)} 本图书设为"{new_status}"')

  # ══════════════════════════════════════════════
  #  搜索
  # ══════════════════════════════════════════════

  def _on_search_requested(self, keyword: str, status: str):
    """搜索栏发出搜索请求的槽函数"""
    books = self._repo.search(keyword, status)
    rows = [b.to_row() for b in books]
    cols = Config.TABLE_COLUMNS
    df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame({c: [] for c in cols}, dtype=object)
    self._model.load_dataframe(df)
    # 同时更新封面墙数据
    if hasattr(self, '_cover_wall'):
      self._cover_wall.set_books(books)
    self._update_status()
    # 重置搜索按钮文字
    self._search_bar.reset_search_button()

  def _reset_search(self):
    """重置搜索条件，显示全部图书"""
    self._search_bar.reset()
    self._load_data()

  def _open_search_dialog(self):
    """打开豆瓣搜索对话框"""
    from ui.search_dialog import SearchDialog
    dlg = SearchDialog(self)
    keyword = self._book_form.get_form_data()['title']
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
    self._book_form.fill_form(book)
    # 已存在的书走 Update，否则撤销会误删整条记录
    old_book = self._repo.get_by_isbn(book.isbn)
    if old_book:
      self._undo_manager.execute(UpdateBookCommand(self._repo, old_book, book))
    else:
      self._undo_manager.execute(AddBookCommand(self._repo, book))
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
      QMessageBox.warning(self, '导入失败',
        f'无法读取 CSV 文件：\n{e}\n\n请确认文件格式正确（UTF-8 编码），或选择其他文件。')
      return

    self._toolbar.set_load_enabled(False)
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
    self._toolbar.set_load_enabled(True)
    self._mark_dirty()
    self._load_data()
    self._toolbar.set_file_label(f'已导入 {count} 条')
    QMessageBox.information(self, '提示', f'导入完成，共处理 {count} 条记录')

  def _on_import_failed(self, msg):
    if self._import_progress:
      self._import_progress.close()
    self._import_thread.quit()
    self._import_thread.wait(3000)
    self._toolbar.set_load_enabled(True)
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
      QMessageBox.information(self, '导出成功', 'CSV 文件已保存。')
    except Exception as e:
      QMessageBox.warning(self, '导出失败',
        f'无法保存 CSV 文件：\n{e}\n\n请检查文件路径是否可写，或选择其他位置。')

  def _restore_backup(self):
    """从备份恢复数据库"""
    backups = self._backup_svc.list_backups()
    if not backups:
      QMessageBox.information(self, '提示', '暂无可用备份')
      return
    dlg = QDialog(self)
    dlg.setWindowTitle('选择备份')
    dlg.setMinimumSize(480, 360)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel('选择要恢复的备份（当前数据会自动保存一份）：'))
    listw = QListWidget()
    listw.setAccessibleName('备份文件列表')
    listw.setAccessibleDescription('选择要恢复的备份文件，双击或点击确定恢复')
    for path, name in backups:
      # 解析文件大小和修改时间
      try:
        file_size = os.path.getsize(path)
        mod_time = os.path.getmtime(path)
        from datetime import datetime
        time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
        if file_size > 1024 * 1024:
          size_str = f'{file_size / 1024 / 1024:.1f} MB'
        else:
          size_str = f'{file_size / 1024:.0f} KB'
        display = f'{name}  ({size_str}, {time_str})'
      except OSError:
        display = name
      item = QListWidgetItem(display)
      item.setData(Qt.ItemDataRole.UserRole, path)
      listw.addItem(item)
    listw.setCurrentRow(0)
    layout.addWidget(listw)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    # Esc 关闭对话框
    from PyQt6.QtGui import QShortcut, QKeySequence
    QShortcut(QKeySequence('Esc'), dlg, dlg.reject)
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
      self._undo_manager.clear()  # 清空撤销栈，避免回退到恢复前的状态
      self._load_data()
      QMessageBox.information(self, '恢复成功', '数据库已从备份恢复。')
    else:
      QMessageBox.warning(self, '恢复失败',
        '无法从备份恢复数据库。\n\n可能原因：备份文件损坏或磁盘空间不足。\n请检查备份文件后重试。')

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
    """
    if self._web_manager.is_running:
      self._web_manager.stop_server()
      self._toolbar.set_web_running(False)
      self.statusBar().showMessage('Web 服务已停止')
    else:
      self._toolbar.set_web_starting()
      self.statusBar().showMessage('正在启动 Web 服务...')
      self._web_manager.start_server()

  def _on_web_started(self):
    """Web 服务启动成功：更新按钮状态，状态栏显示地址"""
    url = f'http://127.0.0.1:{Config.WEB_PORT}'
    self._toolbar.set_web_running(True)
    self.statusBar().showMessage(f'Web 服务已启动: {url}（在浏览器打开请访问此地址）')
    # 不再强制打开浏览器——用户可能只想后台运行服务

  def _on_web_stopped(self):
    """Web 服务已停止"""
    self._toolbar.set_web_running(False)
    self.statusBar().showMessage('Web 服务已停止')

  def _on_web_failed(self, msg: str):
    """Web 服务启动失败：恢复按钮状态"""
    self._toolbar.set_web_running(False)
    self.statusBar().showMessage(f'Web 服务启动失败: {msg}')

  def _on_web_data_changed(self):
    """Web端修改数据后通知GUI刷新"""
    self._mark_dirty()
    self._undo_manager.clear()  # Web端修改后清空撤销栈，避免回滚到不一致的状态
    self._load_data()

  # ══════════════════════════════════════════════
  #  主题与设置
  # ══════════════════════════════════════════════

  def _toggle_theme(self):
    """切换暗色/亮色主题"""
    self._dark_mode = not self._dark_mode
    qss = DARK_QSS if self._dark_mode else LIGHT_QSS
    self.setStyleSheet(qss)
    self._toolbar.set_dark_mode(self._dark_mode)
    # 刷新封面墙卡片样式（卡片颜色硬编码在创建时，需重建）
    if self._is_cover_wall_mode:
      self._cover_wall.set_books(self._repo.get_all())
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
      self._toolbar.set_dark_mode(False)
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
    """更新状态栏：显示记录总数、Web状态和版本"""
    total = self._repo.count()
    visible = self._model.rowCount()
    txt = f'共 {total} 条记录'
    if visible != total and total > 0:
      txt = f'已筛选 {visible}/{total} 条记录'

    # Web服务状态
    web_running = getattr(self, '_web_manager', None) and self._web_manager.is_running
    web_status = '● Web 运行中' if web_running else '○ Web 已停止'

    # 主题模式
    theme_mode = '暗色' if self._dark_mode else '亮色'

    self.statusBar().showMessage(f'{txt}  |  {web_status}  |  {theme_mode}  |  {Config.APP_NAME} v{Config.APP_VERSION}')

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


class _FetchBookWorker(QObject):
  """
  后台查询豆瓣图书的工作线程。

  在独立线程中执行 ISBN 查询，避免 UI 卡死。
  """

  finished = pyqtSignal(object)   # 查询成功，传回 Book 对象
  failed = pyqtSignal(str)        # 查询失败，传回错误消息

  def __init__(self, api, isbn):
    super().__init__()
    self._api = api
    self._isbn = isbn

  def run(self):
    try:
      book = self._api.get_book_by_isbn(self._isbn)
      if book:
        self.finished.emit(book)
      else:
        self.failed.emit(f'未找到图书: {self._isbn}')
    except Exception as e:
      self.failed.emit(str(e))
    finally:
      # 退出线程事件循环，确保线程正常结束
      QThread.currentThread().quit()


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
