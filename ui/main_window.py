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
from PyQt6.QtCore import Qt, QThread, QSettings, QDate, QByteArray
from PyQt6.QtGui import QIcon, QAction, QFont, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
  QMainWindow, QWidget, QVBoxLayout,
  QLabel, QPushButton, QTableView,
  QFileDialog, QMessageBox, QMenu, QHeaderView, QStatusBar,
  QDialog, QListWidget, QListWidgetItem, QDialogButtonBox,
)

from config import Config
from core.models.book import Book
from services import get_repo
from services.douban import DoubanService
from services.undo import (UndoManager, AddBookCommand, DeleteBookCommand,
                           UpdateBookCommand, BatchDeleteCommand,
                           BatchUpdateCommand)
from utils import clean_isbn

from ui.theme import DARK_QSS, LIGHT_QSS
from ui.components import BookFormWidget, SearchBarWidget, ToolBarWidget
from ui.thread_utils import RETIRED as _retired_threads, retire
from ui.workers import FetchBookWorker as _FetchBookWorker
from ui.backup_controller import BackupController
from ui.web_controller import WebController

# 已退役但可能仍在运行的豆瓣查询线程 (thread, worker)。
# 必须保留引用：Python 持有的 QThread 在运行中被 GC 销毁会直接崩溃；
# 也不能 finished → deleteLater——C++ 对象销毁后包装器仍存活，
# 下次 _do_fetch_book 调 isRunning() 会抛 RuntimeError。
# 看护列表与实现见 ui/thread_utils.py。


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
    self._undo_manager = UndoManager()
    self._backup_ctl = BackupController(parent=self)
    self._backup_ctl.failed.connect(
      lambda msg: self.statusBar().showMessage(msg, 15000))
    self._dark_mode = True
    # 排序标记由 TableState 持有（_init_table 里创建），默认未排序
    self._setup_ui()
    self._init_table()
    from ui.import_export import CsvController
    self._csv = CsvController(self._repo, self)
    self._connect_signals()
    self._setup_shortcuts()
    self._setup_backup_timer()
    self._load_settings()

    # Web 服务（线程与浏览器打开都在 ui/web_controller.py 里）
    self._web = WebController(self)
    self._web.started.connect(self._on_web_started)
    self._web.stopped.connect(self._on_web_stopped)
    self._web.failed.connect(self._on_web_failed)
    self._web.data_changed.connect(self._on_web_data_changed)

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
    # 表头状态（列宽/顺序/可见性/排序）交给 TableState 管理
    from ui.table_state import TableState, title_column_width, author_column_width
    hdr = self._table.horizontalHeader()
    # 列 0（ISBN）必须始终 ResizeToContents，列 1（书名）/列 2（作者）固定宽；
    # 防存量 headerState 恢复时把这些列的模式/宽度覆盖掉
    self._table_state = TableState(
      self._table, self._model, self._settings, self,
      resize_to_contents_sections=(0,),
      fixed_width_sections={1: title_column_width, 2: author_column_width})
    # 列宽模式：默认拉伸填满，ISBN 列需完整显示 13 位 → 内容自适应，
    # 书名 30 字符 / 作者 20 字符固定宽（超出截断省略号，可手动拖宽）
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    hdr.resizeSection(1, title_column_width(hdr))
    hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
    hdr.resizeSection(2, author_column_width(hdr))
    hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    self._load_data()

  def _load_data(self):
    """
    从数据库重新加载全量数据到表格。

    每次增删改查后调用此方法刷新界面。
    """
    self._set_table_data(self._repo.get_all())
    self._update_status()

  def _set_table_data(self, books):
    """
    把一组图书灌进表格（全量刷新）。

    _load_data（全部）与 _on_search_requested（筛选结果）共用，
    避免两处各拼一份 DataFrame 逻辑。
    """
    rows = [b.to_row() for b in books]
    cols = Config.TABLE_COLUMNS
    df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame({c: [] for c in cols}, dtype=object)
    self._model.load_dataframe(df)
    self._table_state.reapply_sort()
    # 同时更新封面墙数据
    if hasattr(self, '_cover_wall'):
      self._cover_wall.set_books(books)

  def _reapply_user_sort(self):
    """重新应用用户当前的表头排序（实现见 ui/table_state.py）"""
    self._table_state.reapply_sort()

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
    self._toolbar.import_requested.connect(self._csv.import_csv)
    self._toolbar.export_requested.connect(self._csv.export_csv)
    self._csv.imported.connect(self._on_csv_imported)
    self._csv.busy_changed.connect(
      lambda busy: self._toolbar.set_load_enabled(not busy))
    self._csv.exported.connect(
      lambda path: self.statusBar().showMessage(f'已导出: {path}', 5000))
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
    """设置定时备份（默认每 5 分钟，实现见 ui/backup_controller.py）"""
    self._backup_ctl.start()

  @property
  def _dirty(self) -> bool:
    """数据是否有未备份的变更（委托给 BackupController）"""
    return self._backup_ctl.dirty

  @_dirty.setter
  def _dirty(self, value: bool):
    self._backup_ctl.dirty = value

  @property
  def _backup_svc(self):
    """备份服务（委托给 BackupController，恢复备份时直接用）"""
    return self._backup_ctl.service

  def _mark_dirty(self):
    """标记数据已变更，下次定时器触发时执行备份"""
    self._backup_ctl.mark_dirty()

  def _do_backup(self):
    """执行定时备份：数据无变更则跳过"""
    self._backup_ctl.request_backup()

  def _run_backup(self):
    """实际执行备份（失败保留 dirty 并提示，见 BackupController）"""
    return self._backup_ctl.run_backup()

  def closeEvent(self, event):
    """关闭窗口前：停止 Web 线程 + 保存窗口状态 + 备份"""
    # 查询线程若仍在运行，交给看护列表保活，避免随窗口被 GC 销毁导致 abort
    thread = getattr(self, '_fetch_thread', None)
    worker = getattr(self, '_fetch_worker', None)
    self._fetch_thread = None
    self._fetch_worker = None
    if thread is not None:
      retire(thread, worker)
    self._web.cleanup()
    s = self._settings()
    geo = self.saveGeometry().data()
    if geo:
      s.setValue('windowGeometry', base64.b64encode(geo).decode('ascii'))
    # 无条件备份：backup 内部按 mtime 去重，不会产生冗余文件；
    # 不能以 rowCount 为条件——搜索过滤为 0 行时也会有真实数据
    self._backup_ctl.backup_now()
    super().closeEvent(event)

  # ══════════════════════════════════════════════
  #  图书操作
  # ══════════════════════════════════════════════

  def _fetch_book(self):
    """从豆瓣 API 获取 ISBN 对应的图书信息并填入表单"""
    from utils import is_valid_isbn13, is_valid_isbn10
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
    # 先退役旧线程，防止快速重复调用时泄漏。
    # 注意：不能 quit/wait 旧线程（豆瓣请求阻塞中 quit 无效，wait 会卡 UI），
    # 也不能 finished → deleteLater——见 ui/thread_utils.py 注释
    old_thread = getattr(self, '_fetch_thread', None)
    old_worker = getattr(self, '_fetch_worker', None)
    self._fetch_thread = None
    self._fetch_worker = None
    if old_thread is not None:
      retire(old_thread, old_worker)

    # 创建 worker 和线程
    self._fetch_worker = _FetchBookWorker(self._api, isbn)
    self._fetch_thread = QThread()
    self._fetch_worker.moveToThread(self._fetch_thread)

    # 连接信号（线程退出后不 deleteLater，交由看护列表回收）
    self._fetch_worker.finished.connect(self._on_fetch_success)
    self._fetch_worker.failed.connect(self._on_fetch_error)

    # 启动查询
    self._fetch_thread.started.connect(self._fetch_worker.run)
    self._fetch_thread.start()

  def _on_fetch_success(self, book):
    """豆瓣查询成功回调"""
    # 恢复按钮状态
    self._book_form.set_fetch_enabled(True)
    self._book_form.set_fetch_text('🌐 获取信息')

    if not book.isbn:
      # 空 ISBN 不能入库（会被当作主键互相覆盖）：表单照填，方便手动补全后保存
      self._book_form.fill_form(book)
      self.statusBar().showMessage('豆瓣未返回 ISBN，未保存。请补全 ISBN 后点「更新记录」。')
      return
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
    isbn = clean_isbn(self._book_form.get_isbn())
    if not isbn:
      QMessageBox.warning(self, 'ISBN 不能为空',
        'ISBN 是图书的唯一标识，缺少 ISBN 的记录会互相覆盖。\n\n'
        '请填写 ISBN 后再点击更新。')
      return

    row_data = self._book_form.get_row_data()
    row_data[0] = isbn  # 以清洗后的 ISBN 为准，连字符/空格不会产生重复记录
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
      self._delete_books(isbn_list)

  def _delete_books(self, isbn_list: list):
    """
    批量删除（单事务 + 单条撤销记录）。

    逐条删除时若中途失败，会留下半套数据和半套撤销记录；
    这里整批一次执行，撤销也只算一步。
    """
    books = [b for b in (self._repo.get_by_isbn(i) for i in isbn_list) if b]
    if not books:
      return
    self._undo_manager.execute(BatchDeleteCommand(self._repo, books))
    self._mark_dirty()
    self._load_data()

  def _batch_update_status(self, isbn_list: list, new_status: str):
    """批量修改图书状态（单事务 + 单条撤销记录）"""
    import copy
    old_books, new_books = [], []
    for isbn in isbn_list:
      book = self._repo.get_by_isbn(isbn)
      if book:
        old_books.append(book)
        new_book = copy.copy(book)
        new_book.status = new_status
        new_books.append(new_book)
    if not old_books:
      return
    self._undo_manager.execute(
      BatchUpdateCommand(self._repo, old_books, new_books))
    self._mark_dirty()
    self._load_data()
    self.statusBar().showMessage(f'已将 {len(new_books)} 本图书设为"{new_status}"')

  # ══════════════════════════════════════════════
  #  搜索
  # ══════════════════════════════════════════════

  def _on_search_requested(self, keyword: str, status: str):
    """搜索栏发出搜索请求的槽函数"""
    self._set_table_data(self._repo.search(keyword, status))
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
    if not book.isbn:
      # 空 ISBN 不能入库：表单照填，方便手动补全后保存
      self._book_form.fill_form(book)
      self.statusBar().showMessage('豆瓣未返回 ISBN，未保存。请补全 ISBN 后点「更新记录」。')
      return
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
    """加载 CSV 文件并异步导入（实际逻辑见 ui/import_export.py）"""
    self._csv.import_csv()

  def _on_csv_imported(self, count):
    """导入完成：标脏、刷新表格、更新工具栏标签"""
    self._mark_dirty()
    self._load_data()
    self._toolbar.set_file_label(f'已导入 {count} 条')

  def _save_csv(self):
    """导出全部数据为 CSV 文件（实际逻辑见 ui/import_export.py）"""
    self._csv.export_csv()

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

  @property
  def _web_manager(self):
    """底层 WebManager（兼容旧引用，实际归 WebController 管理）"""
    return self._web.manager

  def _toggle_web(self):
    """启动/停止内嵌 FastAPI Web 服务"""
    if self._web.is_running:
      self._web.stop()
    else:
      self._toolbar.set_web_starting()
      self.statusBar().showMessage('正在启动 Web 服务...')
      self._web.start()

  def _on_web_started(self, url: str):
    """Web 服务启动成功：更新按钮状态（浏览器已由控制器打开）"""
    self._toolbar.set_web_running(True)
    self.statusBar().showMessage(f'Web 服务已启动: {url}')

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
    self._update_status()  # 刷新状态栏中的主题名称

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

  @property
  def _user_sorted(self) -> bool:
    """用户是否已应用表头排序（委托给 TableState）"""
    return self._table_state.user_sorted

  @_user_sorted.setter
  def _user_sorted(self, value: bool):
    self._table_state.user_sorted = value

  def _show_header_menu(self, pos):
    """表头右键菜单：显隐列（实现见 ui/table_state.py）"""
    self._table_state.show_menu(pos)

  def _toggle_column(self, col):
    """切换列的显隐"""
    self._table_state.toggle_column(col)

  def _save_header_state(self):
    """将表头状态保存到 settings.ini（500ms 防抖）"""
    self._table_state.save_soon()

  def _do_save_header_state(self):
    """实际执行表头状态保存"""
    self._table_state.save_now()

  def _restore_header_state(self):
    """从 settings.ini 恢复表头状态（列宽/列顺序/可见性，不恢复排序）"""
    self._table_state.load(self._load_data)

  def _on_sort_indicator_changed(self, *_args):
    """表头排序变化：标记已排序并保存状态"""
    self._table_state._on_sort_indicator_changed(*_args)

  def _update_status(self):
    """更新状态栏：显示记录总数、Web状态和版本"""
    total = self._repo.count()
    visible = self._model.rowCount()
    txt = f'共 {total} 条记录'
    if visible != total and total > 0:
      txt = f'已筛选 {visible}/{total} 条记录'

    # Web服务状态
    web_running = getattr(self, '_web', None) and self._web.is_running
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

