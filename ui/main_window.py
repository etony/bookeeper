# -*- coding: utf-8 -*-
"""Bookeeper 主窗口"""

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
from PyQt6.QtGui import QIcon, QAction, QFont
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

  def __init__(self):
    super().__init__()
    self._api = DoubanService()
    self._data_mgr = DataManager()
    self._setup_ui()
    self._init_model()
    self._setup_connections()
    self._setup_auto_backup()
    self._load_last_file()

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
    layout.setContentsMargins(12, 8, 12, 8)
    layout.setSpacing(8)

    # 顶部标题栏
    layout.addWidget(self._make_header())

    # 文件操作组
    layout.addWidget(self._make_file_group())

    # 图书信息组（核心表单）
    layout.addWidget(self._make_book_group())

    # 搜索筛选组
    layout.addWidget(self._make_search_group())

    # 图书列表表格
    self._table = QTableView()
    self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self._table.setAlternatingRowColors(True)
    self._table.setSortingEnabled(True)
    self._table.verticalHeader().setVisible(True)
    hdr = self._table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
    hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
    layout.addWidget(self._table, stretch=1)

    self.setStatusBar(QStatusBar(self))

  # ── 顶部标题栏 ──────────────────────────────

  def _make_header(self):
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
    row.addWidget(self._btn_theme)
    return bar

  # ── 文件操作组 ──────────────────────────────

  def _make_file_group(self):
    g = QGroupBox('📁 文件操作')
    row = QHBoxLayout(g)
    row.setContentsMargins(8, 16, 8, 8)
    row.setSpacing(6)

    row.addWidget(QLabel('目录'))
    self._file_path = QLineEdit()
    self._file_path.setReadOnly(True)
    self._file_path.setPlaceholderText('未加载文件')
    row.addWidget(self._file_path, stretch=1)

    self._btn_load = QPushButton('📂 加载')
    self._btn_save = QPushButton('💾 保存')
    self._btn_export = QPushButton('📤 导出')
    self._btn_template = QPushButton('📋 模板')
    self._btn_stats = QPushButton('📊 统计')
    for btn in (self._btn_load, self._btn_save, self._btn_export, self._btn_template, self._btn_stats):
      row.addWidget(btn)
    return g

  # ── 图书信息组 ──────────────────────────────

  def _make_book_group(self):
    g = QGroupBox('📖 图书信息')
    grid = QGridLayout(g)
    grid.setContentsMargins(8, 16, 8, 8)
    grid.setSpacing(6)

    # ISBN 行（占整行宽度）
    grid.addWidget(QLabel('ISBN'), 0, 0)
    self._isbn_input = QLineEdit()
    self._isbn_input.setPlaceholderText('输入 13 位 ISBN 编码')
    grid.addWidget(self._isbn_input, 0, 1)
    self._btn_scan = QPushButton('📷 识别')
    self._btn_fetch = QPushButton('🌐 获取信息')
    self._btn_update = QPushButton('💾 更新记录')
    self._btn_refresh = QPushButton('🔄 批量刷新')
    grid.addWidget(self._btn_scan, 0, 2)
    grid.addWidget(self._btn_fetch, 0, 3)
    grid.addWidget(self._btn_update, 0, 4)
    grid.addWidget(self._btn_refresh, 0, 5)

    # 第一行：书名 / 作者 / 出版
    grid.addWidget(QLabel('书名'), 1, 0)
    self._title_input = QLineEdit()
    self._title_input.setPlaceholderText('图书名称')
    grid.addWidget(self._title_input, 1, 1)
    grid.addWidget(QLabel('作者'), 1, 2)
    self._author_input = QLineEdit()
    self._author_input.setPlaceholderText('作者 / 译者')
    grid.addWidget(self._author_input, 1, 3)
    grid.addWidget(QLabel('出版'), 1, 4)
    self._publisher_input = QLineEdit()
    self._publisher_input.setPlaceholderText('出版社')
    grid.addWidget(self._publisher_input, 1, 5)

    # 第二行：价格 / 状态 / 书柜
    grid.addWidget(QLabel('价格'), 2, 0)
    self._price_input = QLineEdit()
    self._price_input.setPlaceholderText('定价')
    grid.addWidget(self._price_input, 2, 1)
    grid.addWidget(QLabel('状态'), 2, 2)
    self._status_combo = QComboBox()
    self._status_combo.addItems(Config.STATUSES)
    self._status_combo.setCurrentIndex(-1)
    grid.addWidget(self._status_combo, 2, 3)
    grid.addWidget(QLabel('书柜'), 2, 4)
    self._shelf_input = QLineEdit()
    self._shelf_input.setPlaceholderText('存放位置')
    grid.addWidget(self._shelf_input, 2, 5)

    # 第三行：评分 / 购书日期 / 已读日期
    grid.addWidget(QLabel('评分'), 3, 0)
    self._rating_display = QLineEdit()
    self._rating_display.setReadOnly(True)
    self._rating_display.setPlaceholderText('豆瓣评分 / 人数')
    grid.addWidget(self._rating_display, 3, 1)
    grid.addWidget(QLabel('购书日期'), 3, 2)
    self._start_date_input = QDateEdit()
    self._start_date_input.setDisplayFormat('yyyy-MM-dd')
    self._start_date_input.setCalendarPopup(True)
    self._start_date_input.setSpecialValueText(' ')
    self._start_date_input.setDate(QDate(1900, 1, 1))
    grid.addWidget(self._start_date_input, 3, 3)
    grid.addWidget(QLabel('已读日期'), 3, 4)
    self._end_date_input = QDateEdit()
    self._end_date_input.setDisplayFormat('yyyy-MM-dd')
    self._end_date_input.setCalendarPopup(True)
    self._end_date_input.setSpecialValueText(' ')
    self._end_date_input.setDate(QDate(1900, 1, 1))
    grid.addWidget(self._end_date_input, 3, 5)
    return g

  # ── 搜索筛选组 ──────────────────────────────

  def _make_search_group(self):
    g = QGroupBox('🔍 搜索筛选')
    row = QHBoxLayout(g)
    row.setContentsMargins(8, 16, 8, 8)
    row.setSpacing(6)

    row.addStretch()
    self._btn_cancel = QPushButton('✕ 取消')
    self._btn_cancel.setVisible(False)
    self._btn_reset = QPushButton('⟲ 重置')
    self._btn_search = QPushButton('🔎 查询列表')
    self._btn_search_douban = QPushButton('🌐 豆瓣搜索')
    row.addWidget(self._btn_cancel)
    row.addWidget(self._btn_reset)
    row.addWidget(self._btn_search)
    row.addWidget(self._btn_search_douban)
    self._btn_web = QPushButton('🌐 Web 服务')
    row.addWidget(self._btn_web)
    return g

  # ══════════════════════════════════════════════
  #  数据模型
  # ══════════════════════════════════════════════

  def _init_model(self):
    df = pd.DataFrame({c: [] for c in Config.TABLE_COLUMNS}, dtype=object)
    self._model = BookTableModel(df)
    self._table.setModel(self._model)
    self._update_status()

  # ══════════════════════════════════════════════
  #  信号绑定
  # ══════════════════════════════════════════════

  def _setup_connections(self):
    self._isbn_input.returnPressed.connect(self._fetch_book_info)
    self._btn_load.clicked.connect(self._load_csv)
    self._btn_save.clicked.connect(self._save_csv)
    self._btn_export.clicked.connect(self._export_books)
    self._btn_template.clicked.connect(self._export_template)
    self._btn_stats.clicked.connect(self._show_stats)
    self._btn_scan.clicked.connect(self._scan_barcode)
    self._btn_fetch.clicked.connect(self._fetch_book_info)
    self._btn_update.clicked.connect(self._update_book)
    self._btn_refresh.clicked.connect(self._refresh_all)
    self._btn_reset.clicked.connect(self._reset_form)
    self._btn_search.clicked.connect(self._search_table)
    self._btn_search_douban.clicked.connect(self._open_search_dialog)
    self._btn_web.clicked.connect(self._toggle_web_server)
    self._btn_cancel.clicked.connect(self._cancel_operation)
    self._table.clicked.connect(self._on_row_clicked)
    self._table.doubleClicked.connect(self._on_row_double_clicked)
    self._table.customContextMenuRequested.connect(self._show_context_menu)
    self._isbn_input.editingFinished.connect(self._validate_isbn_input)
    self._btn_theme.clicked.connect(self._toggle_theme)

  # ══════════════════════════════════════════════
  #  自动备份
  # ══════════════════════════════════════════════

  def _setup_auto_backup(self):
    self._backup_timer = QTimer(self)
    self._backup_timer.timeout.connect(self._do_auto_backup)
    self._backup_timer.start(300000)

  def _do_auto_backup(self):
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

  # ══════════════════════════════════════════════
  #  文件操作
  # ══════════════════════════════════════════════

  def _load_csv(self):
    path, _ = QFileDialog.getOpenFileName(self, '加载 CSV', '.', 'CSV 文件 (*.csv);;所有文件 (*)')
    if not path:
      return
    try:
      new_df = self._data_mgr.load_csv(path)
      existing = set(self._model._original.iloc[:, 0].astype(str).tolist())
      incoming = set(new_df.iloc[:, 0].astype(str).tolist())
      duplicates = list(existing & incoming)
      choice = 'skip'
      if duplicates:
        dlg = DuplicateDialog(duplicates, self)
        dlg.exec()
        choice = dlg.choice
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
    path, _ = QFileDialog.getSaveFileName(self, '保存 CSV', '.', 'CSV 文件 (*.csv);;所有文件 (*)')
    if not path:
      return
    try:
      self._data_mgr.save_csv(path, self._model.export_all())
      QMessageBox.information(self, '提示', '保存成功')
    except PermissionError as e:
      QMessageBox.warning(self, '错误', f'文件写入失败：{e}\n请检查文件是否被其他程序占用')

  def _export_template(self):
    path, _ = QFileDialog.getSaveFileName(self, '导出模板', '模板.csv', 'CSV 文件 (*.csv)')
    if not path:
      return
    self._data_mgr.export_template(path, Config.TABLE_COLUMNS)

  def _show_stats(self):
    dlg = StatsDialog(self._model._original, self)
    dlg.exec()

  # ══════════════════════════════════════════════
  #  条形码扫描
  # ══════════════════════════════════════════════

  def _scan_barcode(self):
    path, _ = QFileDialog.getOpenFileName(self, '选择条形码图片', '.', '图片 (*.png *.jpg);;所有文件 (*)')
    if not path:
      return
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
    if text and text.strip():
      d = QDate.fromString(text.strip(), 'yyyy-MM-dd')
      if d.isValid():
        edit.setDate(d)
        return
    edit.setDate(QDate(1900, 1, 1))

  def _get_date_val(self, edit: QDateEdit) -> str:
    d = edit.date()
    if d.isValid() and d > QDate(1900, 1, 1):
      return d.toString('yyyy-MM-dd')
    return ''

  # ══════════════════════════════════════════════
  #  豆瓣 API 操作
  # ══════════════════════════════════════════════

  def _validate_isbn_input(self):
    raw = self._isbn_input.text().strip()
    isbn = clean_isbn(raw)
    if not isbn:
      self._isbn_input.setStyleSheet('')
      return
    valid = (len(isbn) == 13 and is_valid_isbn13(isbn)) or (len(isbn) == 10 and is_valid_isbn10(isbn))
    if not valid:
      if self._dark_mode:
        self._isbn_input.setStyleSheet('background-color: #3d1f1f; color: #ffcccc; border: 1px solid #cc4444')
      else:
        self._isbn_input.setStyleSheet('background-color: #fff0f0; color: #cc0000; border: 1px solid #cc0000')
    else:
      self._isbn_input.setStyleSheet('')

  def _fetch_book_info(self):
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
    self._model.update_or_insert(book.to_row())
    self._update_status()

  def _fill_form(self, book: Book):
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
    row = [
      self._isbn_input.text(),
      self._title_input.text(),
      self._author_input.text(),
      self._publisher_input.text(),
      self._price_input.text(),
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
    if hasattr(self, '_current_worker') and self._current_worker:
      self._current_worker.cancel()
      self.statusBar().showMessage('操作已取消')
      self._btn_cancel.setVisible(False)

  # ══════════════════════════════════════════════
  #  批量刷新
  # ══════════════════════════════════════════════

  def _refresh_all(self):
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
    self._model.update_or_insert(book.to_row())
    self._refresh_done += 1
    self.statusBar().showMessage(f'信息更新:{self._refresh_total}/{self._refresh_done}')

  # ══════════════════════════════════════════════
  #  导出
  # ══════════════════════════════════════════════

  def _export_books(self):
    isbn_list = self._model.get_column_unique(0)
    if not isbn_list:
      QMessageBox.warning(self, '错误', '导出信息为空')
      return
    path, _ = QFileDialog.getSaveFileName(self, '保存导出文件', '.', 'CSV 文件 (*.csv);;所有文件 (*)')
    if not path:
      return

    self._btn_export.setEnabled(False)
    self._btn_cancel.setVisible(True)
    self._export_results = []
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
    self._export_worker.result_ready.connect(self._export_results.append)
    self._export_worker.progress.connect(
      lambda c, t: self.statusBar().showMessage(f'导出中 {c}/{t}'))

    self._current_worker = self._export_worker
    self._export_thread.start()

  def _on_export_done(self):
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
    isbn_clicked = index.sibling(index.row(), 0).data()
    if not isbn_clicked:
      return
    isbn_clicked = str(isbn_clicked)
    isbn_list = self._model.get_column_unique(0)
    pos = isbn_list.index(isbn_clicked) if isbn_clicked in isbn_list else 0
    dlg = DetailDialog(self, isbn_list, pos)
    dlg.show()

  def _show_context_menu(self, pos):
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
    keyword = self._title_input.text().strip()
    self._model.search(keyword)
    self._update_status()

  def _reset_form(self):
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
    self._fill_form(book)
    self._model.update_or_insert(book.to_row())
    self._update_status()

  # ══════════════════════════════════════════════
  #  辅助
  # ══════════════════════════════════════════════

  @staticmethod
  def _settings():
    return QSettings(os.path.join(os.path.dirname(__file__), '..', 'settings.ini'),
                     QSettings.Format.IniFormat)

  def _load_last_file(self):
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
    self._update_status()

  def _toggle_theme(self):
    self._dark_mode = not self._dark_mode
    qss = DARK_QSS if self._dark_mode else LIGHT_QSS
    self.window().setStyleSheet(qss)
    self._btn_theme.setText('☀️' if self._dark_mode else '🌙')
    s = self._settings()
    s.setValue('darkMode', self._dark_mode)

  def _save_last_file(self, path: str):
    s = self._settings()
    s.setValue('lastFile', path)

  def _toggle_web_server(self):
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

  def _update_status(self):
    self.statusBar().showMessage(
      f'共 {self._model.rowCount()} 条记录  {Config.APP_VERSION}')


class _WebWorker(QObject):
  def __init__(self, file_path, port):
    super().__init__()
    self.file_path = file_path
    self.port = port
    self.server = None

  def run(self):
    from services.web_server import BookWebServer
    self.server = BookWebServer(self.file_path, self.port)
    self.server.start()

  def stop(self):
    if self.server:
      self.server.stop()
