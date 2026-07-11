from PyQt6.QtCore import pyqtSignal, QModelIndex, QThread, QObject
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
  QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
  QTableView, QMessageBox, QHeaderView, QLabel,
)

from config import Config
from services.douban import DoubanService


class _SearchWorker(QObject):
  """后台搜索工作线程，避免 UI 冻结"""
  finished = pyqtSignal(object)
  error = pyqtSignal(str)

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
  """豆瓣图书搜索对话框，后台搜索 + 双击选书"""
  book_selected = pyqtSignal(object)

  def __init__(self, parent=None):
    super().__init__(parent)
    self._books = []
    self._thread = None
    self._worker = None
    self._build_ui()

  def _build_ui(self):
    self.setWindowTitle('豆瓣图书搜索')
    self.resize(*Config.SEARCH_DIALOG_SIZE)
    layout = QVBoxLayout(self)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

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
    self._input.setText(keyword)

  def _search(self):
    """在后台线程中执行豆瓣搜索"""
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
    self._set_loading(False)
    QMessageBox.warning(self, '错误', f'搜索失败: {msg}')

  def _set_loading(self, loading: bool):
    """切换加载状态：显示/隐藏"正在搜索..."文字"""
    self._loading.setText('正在搜索...' if loading else '')
    self._search_btn.setEnabled(not loading)
    self._input.setEnabled(not loading)

  def _on_double_click(self, index: QModelIndex):
    """双击选中结果，通过信号传回主窗口"""
    if 0 <= index.row() < len(self._books):
      self.book_selected.emit(self._books[index.row()])
      self.close()
