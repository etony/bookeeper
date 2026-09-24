"""图书信息编辑表单组件"""

from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtWidgets import (
  QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout,
  QLabel, QLineEdit, QComboBox, QPushButton, QDateEdit, QWidget,
  QAbstractSpinBox,
)

from config import Config
from core.models.book import Book


class BookFormWidget(QGroupBox):
  """
  图书信息编辑表单。

  包含三行：
  第一行：ISBN 输入 + 获取/更新/清空按钮
  第二行：书名/作者/出版社
  第三行：价格/评分/状态/书柜/购书日期/已读日期

  信号：
    fetch_requested(str)  — 用户点击"获取信息"或按回车，携带 ISBN
    update_requested()    — 用户点击"更新记录"按钮
  """

  fetch_requested = pyqtSignal(str)
  update_requested = pyqtSignal()

  def __init__(self, parent=None):
    super().__init__('📖 图书信息', parent)
    self._setup_ui()

  def _setup_ui(self):
    """构建表单的所有控件"""
    layout = QVBoxLayout(self)
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

    # ── 第 2~3 行：改用 QGridLayout 保证列对齐 ──────────
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

    # ── 信号绑定 ───────────────────────────────────────
    self._isbn_input.returnPressed.connect(self._on_fetch_clicked)
    self._btn_fetch.clicked.connect(self._on_fetch_clicked)
    self._btn_new.clicked.connect(self._on_new_clicked)
    self._btn_update.clicked.connect(self.update_requested.emit)
    self._btn_clear.clicked.connect(self.clear_form)
    self._status_combo.currentTextChanged.connect(self._on_status_changed)

  # ══════════════════════════════════════════════
  #  公开方法
  # ══════════════════════════════════════════════

  def get_isbn(self) -> str:
    """获取当前 ISBN 输入"""
    return self._isbn_input.text().strip()

  def set_fetch_enabled(self, enabled: bool):
    """设置获取按钮的启用状态"""
    self._btn_fetch.setEnabled(enabled)

  def set_fetch_text(self, text: str):
    """设置获取按钮的文字"""
    self._btn_fetch.setText(text)

  def get_form_data(self) -> dict:
    """从表单读取数据，返回字典"""
    rating_text = self._rating_input.text()
    rating_parts = rating_text.split('/') if '/' in rating_text else ['0', '0']
    return {
      'isbn': self._isbn_input.text(),
      'title': self._title_input.text(),
      'author': self._author_input.text(),
      'publisher': self._publisher_input.text(),
      'price': self._price_input.text(),
      'rating': rating_parts[0].strip(),
      'raters': rating_parts[-1].strip(),
      'status': self._status_combo.currentText() or Config.DEFAULT_STATUS,
      'shelf': self._shelf_input.text() or Config.DEFAULT_SHELF,
      'start_date': self._get_date(self._start_date),
      'end_date': self._get_date(self._end_date),
    }

  def set_form_data(self, row_data: list):
    """用行列表数据填充表单（与 TABLE_COLUMNS 对应）"""
    self.fill_from_row(row_data)

  def get_row_data(self) -> list:
    """从表单读取数据，返回行列表（与 TABLE_COLUMNS 对应）"""
    d = self.get_form_data()
    return [
      d['isbn'], d['title'], d['author'], d['publisher'],
      d['price'], d['rating'], d['raters'], d['status'],
      d['shelf'], d['start_date'], d['end_date'],
    ]

  def fill_form(self, book: Book):
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

  def fill_from_row(self, row_data: list):
    """用行列表数据填充表单（与 TABLE_COLUMNS 对应）"""
    def val(idx):
      return str(row_data[idx]) if idx < len(row_data) and row_data[idx] is not None else ''

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

  def clear_form(self):
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

  def focus_title(self):
    """聚焦到书名输入框"""
    self._title_input.setFocus()

  # ══════════════════════════════════════════════
  #  内部槽
  # ══════════════════════════════════════════════

  def _on_fetch_clicked(self):
    """获取信息按钮被点击"""
    isbn = self._isbn_input.text().strip()
    if isbn:
      self.fetch_requested.emit(isbn)

  def _on_new_clicked(self):
    """新增按钮被点击：清空表单并聚焦书名"""
    self.clear_form()
    self._title_input.setFocus()

  def _on_status_changed(self, text: str):
    """状态设为'已读'时自动填入日期，切回非'已读'时重置"""
    if text == '已读':
      if self._end_date.date() <= QDate(1900, 1, 1):
        self._end_date.setDate(QDate.currentDate())
      if self._start_date.date() <= QDate(1900, 1, 1):
        self._start_date.setDate(QDate.currentDate())
    else:
      self._end_date.setDate(QDate(1900, 1, 1))

  # ══════════════════════════════════════════════
  #  静态辅助
  # ══════════════════════════════════════════════

  @staticmethod
  def _set_date(edit: QDateEdit, text: str):
    """设置日期控件的值"""
    if text and text.strip():
      d = QDate.fromString(text.strip(), 'yyyy-MM-dd')
      if d.isValid():
        edit.setDate(d)
        return
    edit.setDate(QDate(1900, 1, 1))

  @staticmethod
  def _get_date(edit: QDateEdit) -> str:
    """获取日期控件的文本"""
    d = edit.date()
    if d.isValid() and d > QDate(1900, 1, 1):
      return d.toString('yyyy-MM-dd')
    return ''
