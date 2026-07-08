# -*- coding: utf-8 -*-
"""
Bookeeper 主窗口模块 — MainWindow。

这是整个应用的唯一主窗口，承担以下职责：
  1. UI 布局：按功能区分为标题栏、文件操作、图书信息表单、搜索筛选、图书列表表格
  2. 数据模型：通过 BookTableModel (QSortFilterProxyModel) 管理表格数据，支持排序与搜索
  3. API 交互：调用 DoubanService 获取图书信息（按 ISBN / 关键词搜索）
  4. 文件操作：CSV 加载、保存、导出、模板导出
  5. 后台任务：批量刷新、导出、Web 服务均在 QThread 中执行，不阻塞 UI
  6. 状态持久化：使用 QSettings 保存上次打开的文件路径与暗色/亮色主题偏好

与各 Dialog 的数据交互方式：
  - DetailDialog  : 传入 isbn_list + index，独立通过 API 获取数据
  - SearchDialog  : 通过 book_selected 信号回传 Book 对象
  - DuplicateDialog : 通过 dlg.choice 属性读取用户选择
  - StatsDialog   : 直接传入 self._model._original (原始 DataFrame)
"""

import os
import time
import webbrowser
import logging
from typing import Optional

import cv2 as cv
import numpy as np
import pandas as pd
import pyzbar.pyzbar as pyzbar
from PyQt6.QtCore import Qt, QThread, QTimer, QSettings, QObject, QDate
from PyQt6.QtGui import QIcon, QAction, QFont, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
  QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
  QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QTableView, QDateEdit,
  QFileDialog, QMessageBox, QMenu, QHeaderView, QStatusBar, QFrame,
)

from config import Config
from models.book import Book
from models.table_model import BookTableModel
from services.douban_api import DoubanService
from services.data_manager import DataManager
from workers.workers import RefreshWorker, ExportWorker
from ui.detail_dialog import DetailDialog
from ui.search_dialog import SearchDialog
from ui.duplicate_dialog import DuplicateDialog
from ui.stats_dialog import StatsDialog
from ui.theme import DARK_QSS, LIGHT_QSS
from utils import clean_isbn, is_valid_isbn13, is_valid_isbn10

LOG = logging.getLogger(__name__)


class MainWindow(QMainWindow):
  """应用主窗口，聚合所有 UI 组件与业务逻辑。"""

  def __init__(self):
    super().__init__()
    self._api = DoubanService()      # 豆瓣 API 服务（单例）
    self._data_mgr = DataManager()   # CSV 文件读写管理
    self._setup_ui()                  # 1. 构建所有 UI 控件
    self._init_model()                # 2. 初始化表格数据模型
    self._setup_connections()         # 3. 绑定信号与槽
    self._setup_auto_backup()         # 4. 启动自动备份定时器（5 分钟）
    self._load_last_file()            # 5. 恢复上次会话（文件路径 + 主题）

  # ══════════════════════════════════════════════
  #  UI 构建
  # ══════════════════════════════════════════════

  def _setup_ui(self):
    self.setWindowTitle(Config.APP_NAME)
    icon_path = Config.APP_ICON
    self.setWindowIcon(QIcon(icon_path) if os.path.exists(icon_path) else QIcon())
    self.resize(*Config.MAIN_WINDOW_SIZE)
    self.setMinimumSize(800, 600)

    central = QWidget()
    self.setCentralWidget(central)
    layout = QVBoxLayout(central)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(10)

    layout.addWidget(self._make_header())
    layout.addWidget(self._make_file_group())
    layout.addWidget(self._make_book_group())
    layout.addWidget(self._make_search_group())

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

    self._setup_shortcuts()

  # ── 顶部标题栏 ──────────────────────────────

  def _make_header(self):
    """构建顶部标题栏 QFrame，包含应用名、版本号、主题切换按钮。
    使用 objectName='headerFrame' 方便主题 QSS 单独定制。"""
    bar = QFrame()
    bar.setObjectName('headerFrame')
    row = QHBoxLayout(bar)
    row.setContentsMargins(12, 6, 12, 6)

    title = QLabel('📚 Bookeeper')
    title_font = QFont()
    title_font.setPointSize(15)
    title_font.setBold(True)
    title.setFont(title_font)
    row.addWidget(title)

    row.addStretch()

    ver = QLabel(f'v{Config.APP_VERSION}')
    ver.setStyleSheet('color: #8899aa; font-size: 12px;')
    row.addWidget(ver)
    self._btn_theme = QPushButton('☀️')
    self._btn_theme.setFixedWidth(36)
    self._btn_theme.setToolTip('切换亮色/暗色主题')
    self._btn_theme.setStyleSheet('font-size: 16px;')
    row.addWidget(self._btn_theme)
    return bar

  # ── 文件操作组 ──────────────────────────────

  def _make_file_group(self):
    g = QGroupBox('📁 文件操作')
    row = QHBoxLayout(g)
    row.setContentsMargins(8, 18, 8, 8)
    row.setSpacing(6)

    row.addWidget(QLabel('目录'))
    self._file_path = QLineEdit()
    self._file_path.setReadOnly(True)
    self._file_path.setPlaceholderText('点击「加载」按钮或 Ctrl+O 打开 CSV 文件')
    row.addWidget(self._file_path, stretch=1)

    self._btn_load = QPushButton('📂 加载')
    self._btn_load.setToolTip('从 CSV 文件加载图书数据 (Ctrl+O)')
    self._btn_save = QPushButton('💾 保存')
    self._btn_save.setToolTip('将当前数据保存到 CSV 文件 (Ctrl+S)')
    self._btn_export = QPushButton('📤 导出')
    self._btn_export.setToolTip('导出扩展字段（封面、页码等）到 CSV')
    self._btn_template = QPushButton('📋 模板')
    self._btn_template.setToolTip('导出一个空模板供填写')
    self._btn_stats = QPushButton('📊 统计')
    self._btn_stats.setToolTip('查看阅读状态、出版社、评分分布统计')
    for btn in (self._btn_load, self._btn_save, self._btn_export, self._btn_template, self._btn_stats):
      row.addWidget(btn)
    return g

  # ── 图书信息组 ──────────────────────────────

  def _make_book_group(self):
    g = QGroupBox('📖 图书信息')
    grid = QGridLayout(g)
    grid.setContentsMargins(8, 18, 8, 8)
    grid.setSpacing(6)

    grid.addWidget(QLabel('ISBN'), 0, 0)
    self._isbn_input = QLineEdit()
    self._isbn_input.setPlaceholderText('输入 ISBN（回车即查询）')
    self._isbn_input.setToolTip('输入 13 位或 10 位 ISBN，回车自动从豆瓣获取信息')
    grid.addWidget(self._isbn_input, 0, 1)
    self._btn_scan = QPushButton('📷 识别')
    self._btn_scan.setToolTip('从图片中扫描条形码识别 ISBN')
    self._btn_fetch = QPushButton('🌐 获取信息')
    self._btn_fetch.setToolTip('从豆瓣获取当前 ISBN 的图书信息')
    self._btn_update = QPushButton('💾 更新记录')
    self._btn_update.setToolTip('将表单内容保存到当前表格')
    self._btn_refresh = QPushButton('🔄 批量刷新')
    self._btn_refresh.setToolTip('遍历所有图书，从豆瓣更新评分等信息')
    grid.addWidget(self._btn_scan, 0, 2)
    grid.addWidget(self._btn_fetch, 0, 3)
    grid.addWidget(self._btn_update, 0, 4)
    grid.addWidget(self._btn_refresh, 0, 5)

    grid.addWidget(QLabel('书名'), 1, 0)
    self._title_input = QLineEdit()
    self._title_input.setPlaceholderText('图书名称（用作搜索关键词）')
    self._title_input.setToolTip('输入书名，点击「查询列表」可按此过滤表格')
    grid.addWidget(self._title_input, 1, 1)
    grid.addWidget(QLabel('作者'), 1, 2)
    self._author_input = QLineEdit()
    self._author_input.setPlaceholderText('作者 / 译者')
    grid.addWidget(self._author_input, 1, 3)
    grid.addWidget(QLabel('出版'), 1, 4)
    self._publisher_input = QLineEdit()
    self._publisher_input.setPlaceholderText('出版社')
    grid.addWidget(self._publisher_input, 1, 5)

    grid.addWidget(QLabel('价格'), 2, 0)
    self._price_input = QLineEdit()
    self._price_input.setPlaceholderText('定价')
    grid.addWidget(self._price_input, 2, 1)
    grid.addWidget(QLabel('状态'), 2, 2)
    self._status_combo = QComboBox()
    self._status_combo.addItems(Config.STATUSES)
    self._status_combo.setCurrentIndex(-1)
    self._status_combo.setToolTip('阅读状态：默认 / 计划 / 已读')
    grid.addWidget(self._status_combo, 2, 3)
    grid.addWidget(QLabel('书柜'), 2, 4)
    self._shelf_input = QLineEdit()
    self._shelf_input.setPlaceholderText('存放位置')
    grid.addWidget(self._shelf_input, 2, 5)

    grid.addWidget(QLabel('评分'), 3, 0)
    self._rating_display = QLineEdit()
    self._rating_display.setReadOnly(True)
    self._rating_display.setPlaceholderText('豆瓣评分 / 人数')
    self._rating_display.setToolTip('豆瓣评分，由获取信息自动填充')
    grid.addWidget(self._rating_display, 3, 1)
    grid.addWidget(QLabel('购书日期'), 3, 2)
    self._start_date_input = QDateEdit()
    self._start_date_input.setDisplayFormat('yyyy-MM-dd')
    self._start_date_input.setCalendarPopup(True)
    self._start_date_input.setSpecialValueText(' ')
    self._start_date_input.setDate(QDate(1900, 1, 1))
    self._start_date_input.setToolTip('购书日期，留空表示未记录')
    grid.addWidget(self._start_date_input, 3, 3)
    grid.addWidget(QLabel('已读日期'), 3, 4)
    self._end_date_input = QDateEdit()
    self._end_date_input.setDisplayFormat('yyyy-MM-dd')
    self._end_date_input.setCalendarPopup(True)
    self._end_date_input.setSpecialValueText(' ')
    self._end_date_input.setDate(QDate(1900, 1, 1))
    self._end_date_input.setToolTip('读完日期，状态设为"已读"时自动填入')
    grid.addWidget(self._end_date_input, 3, 5)
    return g

  # ── 搜索筛选组 ──────────────────────────────

  def _make_search_group(self):
    g = QGroupBox('🔍 搜索筛选')
    row = QHBoxLayout(g)
    row.setContentsMargins(8, 18, 8, 8)
    row.setSpacing(6)

    row.addWidget(QLabel('按书名过滤'))
    self._search_input = QLineEdit()
    self._search_input.setPlaceholderText('输入关键词，回车即搜索')
    self._search_input.setToolTip('输入关键词后回车，按书名过滤表格 (Ctrl+F)')
    self._search_input.returnPressed.connect(self._search_table)
    row.addWidget(self._search_input)
    row.addWidget(QLabel('状态'))
    self._search_status = QComboBox()
    self._search_status.addItems(['全部'] + Config.STATUSES)
    self._search_status.setCurrentIndex(0)
    self._search_status.setToolTip('按阅读状态筛选')
    row.addWidget(self._search_status)
    row.addStretch()
    self._btn_cancel = QPushButton('✕ 取消')
    self._btn_cancel.setVisible(False)
    self._btn_cancel.setToolTip('取消正在进行的后台操作 (Esc)')
    self._btn_reset = QPushButton('⟲ 重置')
    self._btn_reset.setToolTip('清空表单并重置列表显示 (Ctrl+R)')
    self._btn_search = QPushButton('🔎 查询')
    self._btn_search.setToolTip('按书名过滤表格 (Ctrl+F)')
    self._btn_search_douban = QPushButton('🌐 豆瓣搜索')
    self._btn_search_douban.setToolTip('从豆瓣搜索图书并添加到列表 (Ctrl+D)')
    row.addWidget(self._btn_cancel)
    row.addWidget(self._btn_reset)
    row.addWidget(self._btn_search)
    row.addWidget(self._btn_search_douban)
    self._btn_web = QPushButton('🌐 Web 服务')
    self._btn_web.setToolTip('启动/停止内嵌 Web 服务（手机/浏览器可访问）')
    row.addWidget(self._btn_web)
    return g

  # ══════════════════════════════════════════════
  #  数据模型
  # ══════════════════════════════════════════════

  def _init_model(self):
    """初始化空的 BookTableModel（QSortFilterProxyModel 子类）并绑定到表格。
    BookTableModel 内部维护 _original（原始 DataFrame）与 _proxy（排序后 DataFrame），
    通过 mapToSource / mapFromSource 实现排序后行号映射。
    初始时所有列均为空列表。"""
    df = pd.DataFrame({c: [] for c in Config.TABLE_COLUMNS}, dtype=object)
    self._model = BookTableModel(df)
    self._table.setModel(self._model)

    hdr = self._table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
    hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)

    self._update_status()

  # ══════════════════════════════════════════════
  #  信号绑定
  # ══════════════════════════════════════════════

  def _setup_shortcuts(self):
    QShortcut(QKeySequence('Ctrl+O'), self, self._load_csv)
    QShortcut(QKeySequence('Ctrl+S'), self, self._save_csv)
    QShortcut(QKeySequence('Ctrl+F'), self, self._search_table)
    QShortcut(QKeySequence('Ctrl+D'), self, self._open_search_dialog)
    QShortcut(QKeySequence('Ctrl+R'), self, self._reset_form)
    QShortcut(QKeySequence('Escape'), self, lambda: (
      self._cancel_operation() if self._btn_cancel.isVisible() else None))

  def _setup_connections(self):
    """绑定所有信号与槽，分以下几类：
      - 输入事件   : ISBN 回车/校验、主题切换
      - 按钮点击   : 文件操作、图书扫码/获取/更新、搜索/重置
      - 表格交互   : 单击（填充表单）/ 双击（打开详情）/ 右键菜单
      - 后台任务   : 批量刷新、导出、Web 服务（通过 _btn_cancel 取消）
    """
    # ISBN 回车即触发获取
    self._isbn_input.returnPressed.connect(self._fetch_book_info)
    # 文件操作按钮
    self._btn_load.clicked.connect(self._load_csv)
    self._btn_save.clicked.connect(self._save_csv)
    self._btn_export.clicked.connect(self._export_books)
    self._btn_template.clicked.connect(self._export_template)
    self._btn_stats.clicked.connect(self._show_stats)
    # 图书信息操作按钮
    self._btn_scan.clicked.connect(self._scan_barcode)
    self._btn_fetch.clicked.connect(self._fetch_book_info)
    self._btn_update.clicked.connect(self._update_book)
    self._btn_refresh.clicked.connect(self._refresh_all)
    # 搜索/重置按钮
    self._btn_reset.clicked.connect(self._reset_form)
    self._btn_search.clicked.connect(self._search_table)
    self._btn_search_douban.clicked.connect(self._open_search_dialog)
    # Web 服务 / 取消操作
    self._btn_web.clicked.connect(self._toggle_web_server)
    self._btn_cancel.clicked.connect(self._cancel_operation)
    # 表格交互：单击填充下方表单，双击打开详情，右键弹出删除菜单
    self._table.clicked.connect(self._on_row_clicked)
    self._table.doubleClicked.connect(self._on_row_double_clicked)
    self._table.customContextMenuRequested.connect(self._show_context_menu)
    # ISBN 输入框失去焦点/回车后校验格式
    self._isbn_input.editingFinished.connect(self._validate_isbn_input)
    # 状态变更时，若设为"已读"则自动填入当前日期
    self._status_combo.currentTextChanged.connect(self._on_status_changed)
    # 主题切换
    self._btn_theme.clicked.connect(self._toggle_theme)

  # ══════════════════════════════════════════════
  #  自动备份
  # ══════════════════════════════════════════════

  def _setup_auto_backup(self):
    """启动自动备份定时器，每 5 分钟（300000ms）备份一次数据到 backups/ 目录。"""
    self._backup_timer = QTimer(self)
    self._backup_timer.timeout.connect(self._do_auto_backup)
    self._backup_timer.start(300000)

  def _do_auto_backup(self):
    """执行自动备份：导出全量数据到 CSV，文件名带时间戳（如 book_backup_20260706_143000.csv）。
    备份目录位于当前文件所在目录的 backups/ 文件夹下。"""
    if self._model.rowCount() == 0:
      return
    src = self._file_path.text()
    base_dir = os.path.dirname(src) if src else '.'
    backup_dir = os.path.join(base_dir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = os.path.join(backup_dir, f'book_backup_{ts}.csv')
    self._model.export_all().to_csv(path, index=False, encoding='utf-8-sig')
    LOG.info('自动备份成功：%s', path)
    self._clean_old_backups(backup_dir, keep=30)

  @staticmethod
  def _clean_old_backups(backup_dir: str, keep: int = 30):
    files = sorted([f for f in os.listdir(backup_dir) if f.startswith('book_backup_') and f.endswith('.csv')])
    for f in files[:-keep]:
      os.remove(os.path.join(backup_dir, f))
      LOG.info('删除旧备份：%s', f)

  # ══════════════════════════════════════════════
  #  文件操作
  # ══════════════════════════════════════════════

  def _load_csv(self):
    """加载 CSV 文件并与现有数据合并。
    重复处理流程：
      1. 计算已存在 ISBN 与导入 ISBN 的交集
      2. 若有重复 → 弹出 DuplicateDialog 让用户选择 skip / overwrite / merge
      3. 根据选择过滤/删除/更新数据
      4. 使用 pd.concat 合并新旧 DataFrame，重新加载到模型
    注意：所有比较基于第 0 列（ISBN）的字符串值。"""
    path, _ = QFileDialog.getOpenFileName(self, '加载 CSV', '.', 'CSV 文件 (*.csv);;所有文件 (*)')
    if not path:
      return
    try:
      new_df = self._data_mgr.load_csv(path)
      # 获取已有数据的 ISBN 集合（第 0 列）
      existing = set(self._model._original.iloc[:, 0].astype(str).tolist())
      incoming = set(new_df.iloc[:, 0].astype(str).tolist())
      duplicates = list(existing & incoming)
      choice = 'skip'
      if duplicates:
        dlg = DuplicateDialog(duplicates, self)
        dlg.exec()
        choice = dlg.choice  # 通过 Dialog 的属性读取选择结果
      if choice == 'skip':
        new_df = new_df[~new_df.iloc[:, 0].astype(str).isin(duplicates)]
      elif choice == 'overwrite':
        self._model.delete_by_isbn_batch(duplicates)
      elif choice == 'merge':
        for isbn in duplicates:
          dup_row = new_df[new_df.iloc[:, 0].astype(str) == isbn].iloc[0]
          self._model.update_or_insert(dup_row.tolist())
        new_df = new_df[~new_df.iloc[:, 0].astype(str).isin(duplicates)]
      df = pd.concat([self._model._original, new_df], ignore_index=True)
      self._model.load_dataframe(df)
      self._file_path.setText(path)
      self._save_last_file(path)
      self._update_status()
    except Exception as e:
      QMessageBox.warning(self, '错误', f'加载失败：{e}')

  def _save_csv(self):
    """将当前数据保存为 CSV 文件。捕获 PermissionError 并给出明确提示。"""
    path, _ = QFileDialog.getSaveFileName(self, '保存 CSV', '.', 'CSV 文件 (*.csv);;所有文件 (*)')
    if not path:
      return
    try:
      self._data_mgr.save_csv(path, self._model.export_all())
      QMessageBox.information(self, '提示', '保存成功')
    except PermissionError as e:
      QMessageBox.warning(self, '错误', f'文件写入失败：{e}\n请检查文件是否被其他程序占用')

  def _export_template(self):
    """导出一个仅含表头（无数据）的 CSV 模板，供用户填写。"""
    path, _ = QFileDialog.getSaveFileName(self, '导出模板', '模板.csv', 'CSV 文件 (*.csv)')
    if not path:
      return
    self._data_mgr.export_template(path, Config.TABLE_COLUMNS)

  def _show_stats(self):
    """打开统计面板 Dialog，传入原始 DataFrame（未过滤/排序的数据）。"""
    dlg = StatsDialog(self._model._original, self)
    dlg.exec()

  # ══════════════════════════════════════════════
  #  条形码扫描
  # ══════════════════════════════════════════════

  def _scan_barcode(self):
    """
    从图片中识别 ISBN 条形码。
    流程：cv.imdecode 读取 → 灰度化 → Otsu 二值化 → pyzbar 解码。
    使用 np.fromfile 支持中文路径（cv.imread 不支持）。
    识别成功后自动填入 ISBN 输入框并触发 _fetch_book_info。"""
    path, _ = QFileDialog.getOpenFileName(self, '选择条形码图片', '.', '图片 (*.png *.jpg);;所有文件 (*)')
    if not path:
      return
    # imdecode + np.fromfile 支持中文路径
    img = cv.imdecode(np.fromfile(path, dtype=np.uint8), cv.IMREAD_COLOR)
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    _, binary = cv.threshold(gray, 0, 255, cv.THRESH_OTSU + cv.THRESH_BINARY)
    barcodes = pyzbar.decode(binary)
    if barcodes:
      self._isbn_input.setText(barcodes[0].data.decode('utf-8'))
      self._fetch_book_info()
    else:
      QMessageBox.warning(self, '提示', '未识别到条形码')

  # ── 日期工具 ──────────────────────────────────

  def _set_date_val(self, edit: QDateEdit, text: str):
    """将字符串日期（yyyy-MM-dd）设置到 QDateEdit。
    约定：空值/无效日期统一设到 QDate(1900, 1, 1)，
    配合 setSpecialValueText(' ') 显示为空白。"""
    if text and text.strip():
      d = QDate.fromString(text.strip(), 'yyyy-MM-dd')
      if d.isValid():
        edit.setDate(d)
        return
    edit.setDate(QDate(1900, 1, 1))

  def _get_date_val(self, edit: QDateEdit) -> str:
    """从 QDateEdit 读取日期字符串。
    若为 1900-01-01（空值标记）则返回空字符串。"""
    d = edit.date()
    if d.isValid() and d > QDate(1900, 1, 1):
      return d.toString('yyyy-MM-dd')
    return ''

  # ══════════════════════════════════════════════
  #  豆瓣 API 操作
  # ══════════════════════════════════════════════

  def _validate_isbn_input(self):
    """ISBN 输入框失去焦点/回车时校验格式。
    校验失败时通过 setStyleSheet 显示红色边框/背景提示。
    注意：仅校验格式，不调用 API。"""
    raw = self._isbn_input.text().strip()
    isbn = clean_isbn(raw)
    if not isbn:
      self._isbn_input.setStyleSheet('')
      return
    valid = (len(isbn) == 13 and is_valid_isbn13(isbn)) or (len(isbn) == 10 and is_valid_isbn10(isbn))
    if not valid:
      # 暗色/亮色主题使用不同色系的错误提示
      if self._dark_mode:
        self._isbn_input.setStyleSheet('background-color: #3d1f1f; color: #ffcccc; border: 1px solid #cc4444')
      else:
        self._isbn_input.setStyleSheet('background-color: #fff0f0; color: #cc0000; border: 1px solid #cc0000')
    else:
      self._isbn_input.setStyleSheet('')

  def _fetch_book_info(self):
    """校验 ISBN 并调用豆瓣 API 获取图书信息。
    流程：clean_isbn → 校验位验证 → API 调用 → 填充表单 + 插入/更新模型。
    若 ISBN 无效或网络异常，弹出警告并不做任何修改。"""
    raw = self._isbn_input.text().strip()
    isbn = clean_isbn(raw)
    if not isbn:
      return
    if len(isbn) == 13 and not is_valid_isbn13(isbn):
      QMessageBox.warning(self, '错误', f'ISBN-13 校验位无效：{isbn}')
      return
    if len(isbn) == 10 and not is_valid_isbn10(isbn):
      QMessageBox.warning(self, '错误', f'ISBN-10 校验位无效：{isbn}')
      return
    book = self._api.get_book_by_isbn(isbn)
    if not book:
      QMessageBox.warning(self, '错误', f'ISBN 无效或网络异常：{isbn}')
      return
    self._fill_form(book)
    # 自动将获取到的记录插入/更新到表格
    self._model.update_or_insert(book.to_row())
    self._update_status()

  def _fill_form(self, book: Book):
    """将 Book 对象的数据填充到图书表单各输入控件中。
    QComboBox 通过状态名称查找索引；QDateEdit 通过 _set_date_val 处理空值。"""
    self._title_input.setText(book.title)
    self._author_input.setText(book.author)
    self._publisher_input.setText(book.publisher)
    self._price_input.setText(book.price)
    self._rating_display.setText(f'{book.rating} / {book.raters}')
    idx = Config.STATUSES.index(book.status) if book.status in Config.STATUSES else 0
    self._status_combo.setCurrentIndex(idx)
    self._shelf_input.setText(book.shelf)
    self._set_date_val(self._start_date_input, book.start_date)
    self._set_date_val(self._end_date_input, book.end_date)

  # ══════════════════════════════════════════════
  #  插入 / 更新
  # ══════════════════════════════════════════════

  def _update_book(self):
    """读取表单各输入控件值，组装为行数据并更新表格模型。
    评分/评分人数从 'x / y' 格式拆分；状态/书柜为空时使用 Config 默认值。"""
    row = [
      self._isbn_input.text(),
      self._title_input.text(),
      self._author_input.text(),
      self._publisher_input.text(),
      self._price_input.text(),
      # 从 '8.5 / 1234' 中拆分评分和人数
      self._rating_display.text().split('/')[0].strip() if '/' in self._rating_display.text() else '0',
      self._rating_display.text().split('/')[-1].strip() if '/' in self._rating_display.text() else '0',
      self._status_combo.currentText() or Config.DEFAULT_STATUS,
      self._shelf_input.text() or Config.DEFAULT_SHELF,
      self._get_date_val(self._start_date_input),
      self._get_date_val(self._end_date_input),
    ]
    self._model.update_or_insert(row)
    self._update_status()

  # ══════════════════════════════════════════════
  #  取消操作
  # ══════════════════════════════════════════════

  def _cancel_operation(self):
    """取消当前正在运行的后台任务（批量刷新或导出）。
    通过 _current_worker.cancel() 设置标志位，worker 在下一个循环检测并退出。"""
    if hasattr(self, '_current_worker') and self._current_worker:
      self._current_worker.cancel()
      self.statusBar().showMessage('操作已取消')
      self._btn_cancel.setVisible(False)

  # ══════════════════════════════════════════════
  #  批量刷新
  # ══════════════════════════════════════════════

  def _refresh_all(self):
    """
    批量刷新所有图书的豆瓣信息，使用 QThread + RefreshWorker。
    设计要点：
      - 通过 moveToThread 将 worker 移至子线程，避免 UI 阻塞
      - worker 处理完一本即通过 progress 信号回传 Book 对象
      - finished 信号连接清理代码（deleteLater + 恢复按钮状态）
      - _btn_cancel 可见时用户可随时中断操作
    注意：QThread 本身不能跨线程直接操作 UI，只能通过信号传递数据。"""
    isbn_list = self._model.get_column_unique(0)
    if not isbn_list:
      return
    self._btn_refresh.setEnabled(False)
    self._btn_cancel.setVisible(True)
    self._refresh_total = len(isbn_list)
    self._refresh_done = 0
    self.statusBar().showMessage(f'信息更新:0/{self._refresh_total}')

    self._refresh_thread = QThread()
    self._refresh_worker = RefreshWorker(isbn_list)
    self._refresh_worker.moveToThread(self._refresh_thread)

    self._refresh_thread.started.connect(self._refresh_worker.run)
    self._refresh_worker.finished.connect(self._refresh_thread.quit)
    self._refresh_worker.finished.connect(self._refresh_worker.deleteLater)
    self._refresh_thread.finished.connect(self._refresh_thread.deleteLater)
    self._refresh_thread.finished.connect(lambda: self._btn_refresh.setEnabled(True))
    self._refresh_thread.finished.connect(self._update_status)
    self._refresh_thread.finished.connect(lambda: self._btn_cancel.setVisible(False))
    self._refresh_worker.progress.connect(self._on_refresh_progress)

    self._current_worker = self._refresh_worker
    self._refresh_thread.start()

  def _on_refresh_progress(self, book: Book):
    """接收到 RefreshWorker 的 progress 信号后，更新模型和状态栏。"""
    self._model.update_or_insert(book.to_row())
    self._refresh_done += 1
    self.statusBar().showMessage(f'信息更新:{self._refresh_total}/{self._refresh_done}')

  # ══════════════════════════════════════════════
  #  导出
  # ══════════════════════════════════════════════

  def _export_books(self):
    """
    导出所有图书的详细信息到 CSV（含封面链接、豆瓣页等扩展字段）。
    使用 ExportWorker 在后台获取每本书的详细信息，结果通过 result_ready 信号收集。
    最终合并到 DataFrame 后写入 CSV。
    设计意图：与 _refresh_all 相同的 QThread 模式，可被 _cancel_operation 中断。"""
    isbn_list = self._model.get_column_unique(0)
    if not isbn_list:
      QMessageBox.warning(self, '错误', '导出信息为空')
      return
    path, _ = QFileDialog.getSaveFileName(self, '保存导出文件', '.', 'CSV 文件 (*.csv);;所有文件 (*)')
    if not path:
      return

    self._btn_export.setEnabled(False)
    self._btn_cancel.setVisible(True)
    self._export_results = []  # 收集所有 ExportWorker 发回的 Book 对象
    self._export_path = path

    self._export_thread = QThread()
    self._export_worker = ExportWorker(isbn_list)
    self._export_worker.moveToThread(self._export_thread)

    self._export_thread.started.connect(self._export_worker.run)
    self._export_worker.finished.connect(self._export_thread.quit)
    self._export_worker.finished.connect(self._export_worker.deleteLater)
    self._export_thread.finished.connect(self._export_thread.deleteLater)
    self._export_thread.finished.connect(self._on_export_done)
    self._export_thread.finished.connect(lambda: self._btn_export.setEnabled(True))
    self._export_thread.finished.connect(lambda: self._btn_cancel.setVisible(False))
    # result_ready 每获取一本书即追加到列表
    self._export_worker.result_ready.connect(self._export_results.append)
    self._export_worker.progress.connect(
      lambda c, t: self.statusBar().showMessage(f'导出中 {c}/{t}'))

    self._current_worker = self._export_worker
    self._export_thread.start()

  def _on_export_done(self):
    """导出线程结束后，将收集的 Book 列表拼装为 DataFrame 写入 CSV。
    扩展字段（封面链接、出版日期、豆瓣页等）追加在 TABLE_COLUMNS 之后。"""
    if not self._export_results:
      return
    rows = [b.to_row() + [b.cover_url, b.pubdate, b.douban_url, b.recommend, b.pages]
            for b in self._export_results]
    cols = Config.TABLE_COLUMNS + ['封面', '出版日期', '详情页', '推荐度', '页数']
    df = pd.DataFrame(rows, columns=cols)
    self._data_mgr.save_csv(self._export_path, df)
    QMessageBox.information(self, '提示', '导出成功')
    self._update_status()

  # ══════════════════════════════════════════════
  #  表格交互
  # ══════════════════════════════════════════════

  def _on_row_clicked(self, index):
    """单击表格行：将选中行的数据填充到下方的图书表单。
    index 是代理模型（QSortFilterProxyModel）索引，
    需要先通过 mapToSource 映射到原始模型行号（由 BookTableModel 内部处理）。
    使用 index.sibling() 读取同一行不同列的数据。"""
    def val(col):
      v = index.sibling(index.row(), col).data()
      return str(v) if v is not None else ''
    self._isbn_input.setText(val(0))
    self._title_input.setText(val(1))
    self._author_input.setText(val(2))
    self._publisher_input.setText(val(3))
    self._price_input.setText(val(4))
    self._rating_display.setText(f'{val(5)} / {val(6)}')
    status = val(7)
    self._status_combo.setCurrentIndex(
      Config.STATUSES.index(status) if status in Config.STATUSES else -1)
    self._shelf_input.setText(val(8))
    self._set_date_val(self._start_date_input, val(9))
    self._set_date_val(self._end_date_input, val(10))

  def _on_row_double_clicked(self, index):
    """双击表格行：打开 DetailDialog 显示图书详情。
    从当前行的第 0 列读取 ISBN，在完整 ISBN 列表中查找位置，
    传递给 DetailDialog 用于翻页。"""
    isbn_clicked = index.sibling(index.row(), 0).data()
    if not isbn_clicked:
      return
    isbn_clicked = str(isbn_clicked)
    # 从原始模型获取完整的 ISBN 列表（非排序后视图）
    isbn_list = self._model.get_column_unique(0)
    pos = isbn_list.index(isbn_clicked) if isbn_clicked in isbn_list else 0
    dlg = DetailDialog(self, isbn_list, pos)
    dlg.show()

  def _show_context_menu(self, pos):
    """右键表格弹出上下文菜单（目前只有「删除选中」）。
    选中多行时收集所有不重复的 ISBN（只取第 0 列），
    用户确认后逐条删除。"""
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
        self._model.delete_by_isbn(isbn)
      self._update_status()

  # ══════════════════════════════════════════════
  #  搜索 / 重置
  # ══════════════════════════════════════════════

  def _search_table(self):
    """关键词 + 状态组合筛选，更新表格显示"""
    keyword = self._search_input.text().strip()
    status = self._search_status.currentText()
    self._model.apply_filters(keyword, status if status != '全部' else '')
    self._update_status()

  def _on_status_changed(self, text: str):
    if text == '已读' and self._end_date_input.date() <= QDate(1900, 1, 1):
      self._end_date_input.setDate(QDate.currentDate())

  def _reset_form(self):
    self._search_input.clear()
    self._search_status.setCurrentIndex(0)
    self._title_input.clear()
    self._author_input.clear()
    self._publisher_input.clear()
    self._price_input.clear()
    self._rating_display.clear()
    self._shelf_input.clear()
    self._status_combo.setCurrentIndex(-1)
    self._start_date_input.setDate(QDate(1900, 1, 1))
    self._end_date_input.setDate(QDate(1900, 1, 1))
    self._model.reset_search()
    self._update_status()

  def _open_search_dialog(self):
    dlg = SearchDialog(self)
    keyword = self._title_input.text().strip()
    if len(keyword) >= 2:
      dlg.set_keyword(keyword)
    dlg.book_selected.connect(self._on_search_result)
    dlg.exec()

  def _on_search_result(self, book: Book):
    """接收 SearchDialog 的 book_selected 信号，填充表单并更新表格。"""
    self._fill_form(book)
    self._model.update_or_insert(book.to_row())
    self._update_status()

  # ══════════════════════════════════════════════
  #  辅助
  # ══════════════════════════════════════════════

  @staticmethod
  def _settings():
    """返回 QSettings 实例，配置文件位于项目根目录下的 settings.ini。
    使用 IniFormat 便于手动编辑。"""
    return QSettings(os.path.join(os.path.dirname(__file__), '..', 'settings.ini'),
                     QSettings.Format.IniFormat)

  def _load_last_file(self):
    """启动时从 QSettings 恢复上次会话：
      - 若之前保存了文件路径且文件存在 → 自动加载
      - 恢复暗色/亮色主题偏好"""
    s = self._settings()
    path = s.value('lastFile', '')
    self._dark_mode = s.value('darkMode', 'true') == 'true'
    if not self._dark_mode:
      self.window().setStyleSheet(LIGHT_QSS)
      self._btn_theme.setText('🌙')
    if path and os.path.exists(path):
      try:
        df = self._data_mgr.load_csv(path)
        self._model.load_dataframe(df)
        self._file_path.setText(path)
      except Exception:
        pass
    self._restore_column_state()
    self._update_status()

  def _toggle_theme(self):
    """切换暗色/亮色主题，更新按钮图标并保存偏好到 QSettings。"""
    self._dark_mode = not self._dark_mode
    qss = DARK_QSS if self._dark_mode else LIGHT_QSS
    self.window().setStyleSheet(qss)
    self._btn_theme.setText('☀️' if self._dark_mode else '🌙')
    s = self._settings()
    s.setValue('darkMode', self._dark_mode)

  def _save_last_file(self, path: str):
    """将最近打开的文件路径写入 QSettings。"""
    s = self._settings()
    s.setValue('lastFile', path)

  def _toggle_web_server(self):
    """启动/停止内嵌 Web 服务（FastAPI + uvicorn）。
    启动条件：必须先加载数据文件。
    使用 QThread + _WebWorker 运行 Web 服务器，不阻塞主线程。
    按钮文字根据服务状态切换。"""
    if self._btn_web.text() == '🛑 停止服务':
      if hasattr(self, '_web_worker') and self._web_worker:
        self._web_worker.stop()
        self._web_server.quit()
        self._web_server.wait(3000)
      self._btn_web.setText('🌐 Web 服务')
      self.statusBar().showMessage('Web 服务已停止')
      return
    file_path = self._file_path.text()
    if not file_path or not os.path.exists(file_path):
      QMessageBox.warning(self, '错误', '请先加载数据文件')
      return
    self._btn_web.setText('⏳ 启动中...')
    self._web_server = QThread()
    self._web_worker = _WebWorker(file_path, Config.WEB_PORT)
    self._web_worker.moveToThread(self._web_server)
    self._web_server.started.connect(self._web_worker.run)
    self._web_server.start()
    url = f'http://127.0.0.1:{Config.WEB_PORT}'
    self.statusBar().showMessage(f'Web 服务已启动：{url}  API 文档：{url}/docs')
    self._btn_web.setText('🛑 停止服务')
    webbrowser.open(url)

  # ══════════════════════════════════════════════
  #  列隐藏/重排
  # ══════════════════════════════════════════════

  def _show_header_menu(self, pos):
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
    hdr = self._table.horizontalHeader()
    hdr.setSectionHidden(col, not hdr.isSectionHidden(col))
    self._save_column_state()

  def _save_column_state(self):
    hdr = self._table.horizontalHeader()
    state_bytes = hdr.saveState().data()
    import base64
    state_b64 = base64.b64encode(state_bytes).decode('ascii')
    s = self._settings()
    s.setValue('headerState', state_b64)

  def _restore_column_state(self):
    hdr = self._table.horizontalHeader()
    s = self._settings()
    state_b64 = s.value('headerState', '')
    if state_b64:
      from PyQt6.QtCore import QByteArray
      try:
        import base64
        state_bytes = base64.b64decode(state_b64)
        hdr.restoreState(QByteArray(state_bytes))
      except Exception:
        pass
    # 恢复完成后连接信号，避免初始化时 signal 覆盖已保存状态
    try:
      hdr.sectionMoved.disconnect()
    except TypeError:
      pass
    try:
      hdr.sectionResized.disconnect()
    except TypeError:
      pass
    hdr.sectionMoved.connect(self._save_column_state)
    hdr.sectionResized.connect(self._save_column_state)

  def _update_status(self):
    total = self._model._original.shape[0]
    visible = self._model.rowCount()
    txt = f'共 {total} 条记录'
    if visible != total and total > 0:
      txt = f'已筛选 {visible}/{total} 条记录'
    self.statusBar().showMessage(f'{txt}  |  {Config.APP_NAME} v{Config.APP_VERSION}')


class _WebWorker(QObject):
  """在子线程中运行内嵌 Web 服务器的 Worker。
  通过 QThread + moveToThread 实现非阻塞运行。
  run() 创建 BookWebServer 实例并启动，start() 会阻塞当前线程。
  stop() 从主线程调用以终止服务器。"""

  def __init__(self, file_path, port):
    super().__init__()
    self.file_path = file_path
    self.port = port
    self.server = None

  def run(self):
    """启动 Web 服务器（阻塞调用，运行在子线程中）。"""
    from services.web_server import BookWebServer
    self.server = BookWebServer(self.file_path, self.port)
    self.server.start()

  def stop(self):
    """请求停止 Web 服务器。"""
    if self.server:
      self.server.stop()
