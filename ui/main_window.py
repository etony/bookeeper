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
from PyQt6.QtCore import Qt, QThread, QTimer, QSettings, QObject, QDate, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QFont, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
  QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
  QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QTableView,
  QDateEdit, QFileDialog, QMessageBox, QMenu, QHeaderView, QStatusBar, QProgressDialog,
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
    self.setWindowIcon(QIcon())
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

    # 图书表格——主内容区，占据剩余空间
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
    layout.addWidget(self._table, stretch=1)

    sb = QStatusBar(self)
    sb.setFont(QFont('', 11))
    sb.showMessage('欢迎使用 Bookeeper')
    self.setStatusBar(sb)

  def _make_toolbar(self):
    """顶部工具栏：CSV 导入/导出、统计、豆瓣搜索、Web 服务、主题切换"""
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)

    self._btn_load = QPushButton('📂 加载 CSV')
    self._btn_load.setToolTip('从 CSV 导入图书数据')
    self._btn_save = QPushButton('💾 保存 CSV')
    self._btn_save.setToolTip('导出全部数据为 CSV')
    self._btn_stats = QPushButton('📊 统计')
    self._btn_search_douban = QPushButton('🌐 豆瓣搜索')
    self._btn_search_douban.setToolTip('从豆瓣搜索图书并添加 (Ctrl+D)')
    self._btn_web = QPushButton('🌐 Web 服务')
    self._btn_web.setToolTip('启动/停止内嵌 Web 服务')
    self._btn_theme = QPushButton('☀️')
    self._btn_theme.setFixedSize(34, 32)
    self._btn_theme.setToolTip('切换亮色/暗色主题')

    for btn in (self._btn_load, self._btn_save, self._btn_stats, self._btn_search_douban, self._btn_web, self._btn_theme):
      btn.setFixedHeight(32)
      row.addWidget(btn)

    self._file_label = QLabel('')
    self._file_label.setStyleSheet('color: #7a7a80; font-size: 12px;')
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
    self._btn_update = QPushButton('💾 更新记录')
    self._btn_clear = QPushButton('✕ 清空')
    for btn in (self._btn_fetch, self._btn_update, self._btn_clear):
      btn.setFixedHeight(30)
      r0.addWidget(btn)
    layout.addLayout(r0)

    # ── 第二行：书名 / 作者 / 出版社 ─────────────────────
    self._title_input = QLineEdit(placeholderText='书名')
    self._author_input = QLineEdit(placeholderText='作者/译者')
    self._publisher_input = QLineEdit(placeholderText='出版社')
    r1 = QHBoxLayout()
    r1.setSpacing(4)
    for label, w in [(QLabel('书名'), self._title_input),
                     (QLabel('作者'), self._author_input),
                     (QLabel('出版'), self._publisher_input)]:
      r1.addWidget(label)
      r1.addWidget(w, stretch=1)
    layout.addLayout(r1)

    # ── 第三行：价格 / 评分 / 状态 / 书柜 / 日期 ────────
    self._price_input = QLineEdit(placeholderText='定价')
    self._price_input.setFixedWidth(80)
    self._rating_input = QLineEdit(placeholderText='评分/人数')
    self._rating_input.setReadOnly(True)
    self._rating_input.setFixedWidth(110)
    self._status_combo = QComboBox()
    self._status_combo.addItems(Config.STATUSES)
    self._status_combo.setCurrentIndex(-1)
    self._status_combo.setFixedWidth(85)
    self._shelf_input = QLineEdit(placeholderText='位置')
    self._shelf_input.setFixedWidth(85)
    self._start_date = QDateEdit()
    self._end_date = QDateEdit()
    for edit in (self._start_date, self._end_date):
      edit.setDisplayFormat('yyyy-MM-dd')
      edit.setCalendarPopup(True)
      edit.setSpecialValueText(' ')
      edit.setDate(QDate(1900, 1, 1))
      edit.setFixedWidth(120)
    r2 = QHBoxLayout()
    r2.setSpacing(4)
    for label, w in [(QLabel('价格'), self._price_input),
                     (QLabel('评分'), self._rating_input),
                     (QLabel('状态'), self._status_combo),
                     (QLabel('书柜'), self._shelf_input),
                     (QLabel('购书'), self._start_date),
                     (QLabel('已读'), self._end_date)]:
      r2.addWidget(label)
      r2.addWidget(w)
    r2.addStretch()
    layout.addLayout(r2)
    return g

  def _make_search_bar(self):
    """搜索栏：关键词输入 + 状态下拉 + 查询/重置按钮"""
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)

    row.addWidget(QLabel('搜索'))
    self._search_input = QLineEdit()
    self._search_input.setPlaceholderText('输入关键词搜索书名/作者/出版社/ISBN')
    self._search_input.setFixedHeight(30)
    row.addWidget(self._search_input, stretch=1)
    row.addWidget(QLabel('状态'))
    self._search_status = QComboBox()
    self._search_status.addItems(['全部'] + Config.STATUSES)
    self._search_status.setCurrentIndex(0)
    self._search_status.setFixedHeight(30)
    row.addWidget(self._search_status)
    self._btn_search = QPushButton('🔎 查询')
    self._btn_search.setFixedHeight(30)
    self._btn_reset = QPushButton('⟲ 重置')
    self._btn_reset.setFixedHeight(30)
    row.addWidget(self._btn_search)
    row.addWidget(self._btn_reset)
    return w

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
    # 列宽模式：默认拉伸填满，前三列可交互调整
    hdr = self._table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
    hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
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
    self._update_status()

  # ══════════════════════════════════════════════
  #  信号与快捷键
  # ══════════════════════════════════════════════

  def _connect_signals(self):
    """绑定所有 UI 控件的信号-槽连接"""
    self._isbn_input.returnPressed.connect(self._fetch_book)
    self._btn_fetch.clicked.connect(self._fetch_book)
    self._btn_update.clicked.connect(self._update_book)
    self._btn_clear.clicked.connect(self._clear_form)
    self._btn_load.clicked.connect(self._load_csv)
    self._btn_save.clicked.connect(self._save_csv)
    self._btn_stats.clicked.connect(self._show_stats)
    self._btn_theme.clicked.connect(self._toggle_theme)
    self._btn_search.clicked.connect(self._search)
    self._btn_reset.clicked.connect(self._reset_search)
    self._btn_search_douban.clicked.connect(self._open_search_dialog)
    self._btn_web.clicked.connect(self._toggle_web)
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
    """关闭窗口前强制备份一次"""
    if self._model.rowCount():
      self._backup_svc.backup()
    super().closeEvent(event)

  # ══════════════════════════════════════════════
  #  图书操作
  # ══════════════════════════════════════════════

  def _fetch_book(self):
    """
    从豆瓣 API 获取 ISBN 对应的图书信息并填入表单。

    流程：
      1. 清洗 ISBN（去除非数字字符）
      2. 校验 ISBN-13 或 ISBN-10 的校验位
      3. 调用豆瓣 API 查询
      4. 填入表单 + 自动存入数据库
      5. 刷新表格
    """
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

    self.statusBar().showMessage('正在查询豆瓣...')
    book = self._api.get_book_by_isbn(isbn)
    if not book:
      QMessageBox.warning(self, '错误', f'未找到图书: {isbn}')
      self.statusBar().showMessage('查询失败')
      return

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
    self._status_combo.setCurrentIndex(idx)
    self._shelf_input.setText(book.shelf)
    self._set_date(self._start_date, book.start_date)
    self._set_date(self._end_date, book.end_date)

  def _update_book(self):
    """
    从表单读取数据，更新到数据库。

    ISBN 从第 0 列取（表单中不可修改的隐含主键）。
    评分字段格式是 "评分/人数"，需要拆开。
    """
    row = [
      self._isbn_input.text(),
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
      isbn=row[0], title=row[1], author=row[2], publisher=row[3],
      price=row[4], rating=row[5], raters=row[6], status=row[7],
      shelf=row[8], start_date=row[9], end_date=row[10],
    )
    self._repo.upsert(book)
    self._mark_dirty()
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
    self._status_combo.setCurrentIndex(
      Config.STATUSES.index(status) if status in Config.STATUSES else -1)
    self._shelf_input.setText(val(8))
    self._set_date(self._start_date, val(9))
    self._set_date(self._end_date, val(10))

  def _on_double_clicked(self, index):
    """双击打开图书详情对话框"""
    clicked_isbn = str(index.sibling(index.row(), 0).data() or '')
    if not clicked_isbn:
      return
    isbn_list = []
    clicked_idx = 0
    for r in range(self._model.rowCount()):
      isbn = str(self._model.index(r, 0).data() or '')
      if isbn:
        isbn_list.append(isbn)
        if isbn == clicked_isbn:
          clicked_idx = len(isbn_list) - 1
    from ui.detail_dialog import DetailDialog
    dlg = DetailDialog(isbn_list=isbn_list, index=clicked_idx, parent=self)
    dlg.exec()

  def _on_status_changed(self, text: str):
    """状态设为'已读'时，自动填入当天日期"""
    if text == '已读' and self._end_date.date() <= QDate(1900, 1, 1):
      self._end_date.setDate(QDate.currentDate())

  def _show_context_menu(self, pos):
    """表格右键菜单：删除选中行"""
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
    delete_action = QAction(QIcon(), '🗑 删除选中', self)
    menu.addAction(delete_action)
    action = menu.exec(self._table.mapToGlobal(pos))
    if action == delete_action:
      for isbn in isbn_list:
        self._repo.delete(isbn)
      self._mark_dirty()
      self._load_data()

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
    self._update_status()

  def _reset_search(self):
    """重置搜索条件，显示全部图书"""
    self._search_input.clear()
    self._search_status.setCurrentIndex(0)
    self._clear_form()
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
    加载 CSV 文件并导入到数据库。

    用 QProgressDialog 显示进度，
    避免大文件导入时用户以为程序卡死了。
    """
    path, _ = QFileDialog.getOpenFileName(self, '加载 CSV', '.', 'CSV 文件 (*.csv)')
    if not path:
      return
    progress = QProgressDialog('正在导入 CSV...', '取消', 0, 0, self)
    progress.setWindowTitle('导入中')
    progress.setMinimumDuration(0)
    progress.show()
    try:
      from services.data import load_csv
      df = load_csv(path)
      count = self._repo.import_df(df)
      progress.close()
      self._mark_dirty()
      self._load_data()
      self._file_label.setText(os.path.basename(path))
      QMessageBox.information(self, '提示', f'导入完成，共处理 {count} 条记录')
    except Exception as e:
      progress.close()
      QMessageBox.warning(self, '错误', f'导入失败: {e}')

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

  def _show_stats(self):
    """打开统计面板"""
    from ui.stats_dialog import StatsDialog
    dlg = StatsDialog(self._repo, self)
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
    self._btn_theme.setText('☀️' if self._dark_mode else '🌙')
    s = self._settings()
    s.setValue('darkMode', self._dark_mode)

  def _settings(self):
    """读取 settings.ini（存储窗口状态和偏好设置）"""
    return QSettings(os.path.join(os.path.dirname(__file__), '..', 'settings.ini'),
                     QSettings.Format.IniFormat)

  def _load_settings(self):
    """恢复上次保存的主题和表头状态"""
    s = self._settings()
    self._dark_mode = s.value('darkMode', 'true') == 'true'
    if not self._dark_mode:
      self.setStyleSheet(LIGHT_QSS)
      self._btn_theme.setText('🌙')
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
    """将表头状态（列顺序、宽度、可见性）保存到 settings.ini"""
    state = self._table.horizontalHeader().saveState().data()
    s = self._settings()
    s.setValue('headerState', base64.b64encode(state).decode('ascii'))

  def _restore_header_state(self):
    """从 settings.ini 恢复表头状态"""
    hdr = self._table.horizontalHeader()
    s = self._settings()
    state_b64 = s.value('headerState', '')
    if state_b64:
      from PyQt6.QtCore import QByteArray
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
