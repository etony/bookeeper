"""
┌──────────────────────────────────────────┐
│  豆瓣图书搜索对话框                       │
│                                          │
│  输入关键词，后台搜索豆瓣 API，            │
│  双击结果即可将图书添加到本地数据库。       │
└──────────────────────────────────────────┘
"""

from PyQt6.QtCore import pyqtSignal, QModelIndex, QThread, QObject
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
  QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
  QTableView, QMessageBox, QHeaderView, QLabel,
)

from config import Config
from services.douban import DoubanService


class _SearchWorker(QObject):
  """
  后台搜索工作线程。

  搜索豆瓣 API 需要网络请求，可能耗时 1-3 秒。
  放在后台线程执行，UI 不会卡住。
  """

  finished = pyqtSignal(object)   # 搜索完成，传回 Book 列表
  error = pyqtSignal(str)         # 搜索失败，传回错误消息

  def __init__(self, keyword: str):
    super().__init__()
    self._keyword = keyword

  def run(self):
    try:
      api = DoubanService()
      books = api.search_books(self._keyword)
      self.finished.emit(books)
    except Exception as e:
      self.error.emit(str(e))


class SearchDialog(QDialog):
  """
  豆瓣图书搜索对话框。

  用法：
    dlg = SearchDialog(parent)
    dlg.set_keyword('百年孤独')     # 预填关键词
    dlg.book_selected.connect(callback)  # 双击选书回调
    dlg.exec()

  用户双击某本书时，通过 book_selected 信号
  把 Book 对象传回主窗口。
  """

  book_selected = pyqtSignal(object)   # 传出选中的 Book 对象

  def __init__(self, parent=None):
    super().__init__(parent)
    self._books = []       # 搜索结果列表
    self._thread = None
    self._worker = None
    self._build_ui()

  def _build_ui(self):
    """
    构建界面：输入框 + 搜索按钮 + 结果表格。

    表格含 9 列（ISBN ~ 书柜），
    双击任意行触发选择回调。
    """
    self.setWindowTitle('豆瓣图书搜索')
    self.resize(*Config.SEARCH_DIALOG_SIZE)
    layout = QVBoxLayout(self)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    # ── 顶部搜索栏 ──────────────────────────────────────
    top = QHBoxLayout()
    top.setSpacing(6)
    self._input = QLineEdit()
    self._input.setPlaceholderText('输入书名关键词，回车搜索...')
    self._input.returnPressed.connect(self._search)
    top.addWidget(self._input, stretch=1)
    self._search_btn = QPushButton('🔎 搜索')
    self._search_btn.setFixedWidth(100)
    self._search_btn.clicked.connect(self._search)
    top.addWidget(self._search_btn)
    self._loading = QLabel('')
    self._loading.setStyleSheet('color: #e8922a; font-size: 13px;')
    top.addWidget(self._loading)
    layout.addLayout(top)

    # ── 结果表格 ────────────────────────────────────────
    self._table = QTableView()
    self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    self._table.setAlternatingRowColors(True)
    self._table.setSortingEnabled(True)
    self._table.verticalHeader().setVisible(False)
    hdr = self._table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    hdr.setStretchLastSection(True)
    hdr.resizeSection(0, 150)
    hdr.resizeSection(1, 200)
    hdr.resizeSection(2, 120)
    self._table.doubleClicked.connect(self._on_double_click)
    layout.addWidget(self._table)

  def set_keyword(self, keyword: str):
    """预填搜索关键词（主窗口传入当前选中的书名）"""
    self._input.setText(keyword)

  def _search(self):
    """
    开始搜索。

    在后台线程中调用豆瓣 API，
    搜索期间禁用输入和按钮，防止重复提交。
    """
    keyword = self._input.text().strip()
    if not keyword:
      QMessageBox.warning(self, '提示', '请输入搜索关键词')
      return

    self._set_loading(True)
    self._thread = QThread()
    self._worker = _SearchWorker(keyword)
    self._worker.moveToThread(self._thread)
    self._thread.started.connect(self._worker.run)
    self._worker.finished.connect(self._on_results)
    self._worker.error.connect(self._on_error)
    self._worker.finished.connect(self._thread.quit)
    self._worker.finished.connect(self._worker.deleteLater)
    self._thread.finished.connect(self._thread.deleteLater)
    self._thread.start()

  def _on_results(self, books):
    """
    搜索结果回调：将结果填入表格。

    搜索完成后自动填入 QStandardItemModel，
    表格会显示 ISBN、书名、作者、价格等字段。
    """
    self._set_loading(False)
    self._books = books
    if not books:
      QMessageBox.information(self, '搜索结果', '未找到匹配的图书')
    model = QStandardItemModel(len(books), 9)
    model.setHorizontalHeaderLabels(['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜'])
    for r, book in enumerate(books):
      for c, val in enumerate(book.to_row()):
        model.setItem(r, c, QStandardItem(str(val)))
    self._table.setModel(model)

  def _on_error(self, msg):
    """搜索失败回调"""
    self._set_loading(False)
    QMessageBox.warning(self, '错误', f'搜索失败: {msg}')

  def _set_loading(self, loading: bool):
    """切换加载状态"""
    self._loading.setText('正在搜索...' if loading else '')
    self._search_btn.setEnabled(not loading)
    self._input.setEnabled(not loading)

  def _on_double_click(self, index: QModelIndex):
    """
    双击选中结果，通过信号传回主窗口。

    触发后自动关闭对话框。
    """
    if 0 <= index.row() < len(self._books):
      self.book_selected.emit(self._books[index.row()])
      self.close()
