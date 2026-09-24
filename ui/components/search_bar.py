"""搜索栏组件"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
  QGroupBox, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton,
)

from config import Config


class SearchBarWidget(QGroupBox):
  """
  搜索栏：关键词输入 + 状态下拉 + 查询/重置按钮。

  信号：
    search_requested(str, str)  — (keyword, status)，状态为空表示"全部"
    reset_requested()           — 用户点击重置
  """

  search_requested = pyqtSignal(str, str)
  reset_requested = pyqtSignal()

  def __init__(self, parent=None):
    super().__init__('🔎 搜索', parent)
    self._setup_ui()

  def _setup_ui(self):
    """构建搜索栏的所有控件"""
    row = QHBoxLayout(self)
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

    # 防抖定时器：输入变化后 300ms 自动触发搜索
    self._search_timer = QTimer(self)
    self._search_timer.setSingleShot(True)
    self._search_timer.timeout.connect(self._on_search)
    self._search_input.textChanged.connect(self._on_search_text_changed)

    # 信号绑定
    self._btn_search.clicked.connect(self._on_search)
    self._btn_reset.clicked.connect(self._on_reset)
    self._search_input.returnPressed.connect(self._on_search)

  # ══════════════════════════════════════════════
  #  公开方法
  # ══════════════════════════════════════════════

  def get_search_params(self) -> tuple:
    """返回 (keyword, status)，status 为空表示 '全部'"""
    keyword = self._search_input.text().strip()
    status = self._search_status.currentText()
    if status == '全部':
      status = ''
    return keyword, status

  def reset(self):
    """重置搜索条件"""
    self._search_input.clear()
    self._search_status.setCurrentIndex(0)

  def focus_input(self):
    """聚焦到搜索输入框"""
    self._search_input.setFocus()

  def set_keyword(self, text: str):
    """设置搜索关键词"""
    self._search_input.setText(text)

  # ══════════════════════════════════════════════
  #  内部槽
  # ══════════════════════════════════════════════

  def _on_search(self):
    """执行搜索"""
    keyword, status = self.get_search_params()
    self.search_requested.emit(keyword, status)

  def _on_reset(self):
    """重置搜索"""
    self.reset()
    self.reset_requested.emit()

  def _on_search_text_changed(self, text: str):
    """搜索文本变化时重置定时器（防抖 300ms）"""
    self._search_timer.stop()
    # 显示搜索中状态
    self._btn_search.setText('🔎 搜索中...')
    self._search_timer.start(300)

  def _on_search(self):
    """执行搜索"""
    # 恢复搜索按钮状态
    self._btn_search.setText('🔎 查询')
    keyword, status = self.get_search_params()
    self.search_requested.emit(keyword, status)
