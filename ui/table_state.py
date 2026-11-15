"""
表头状态控制器（从 ui/main_window.py 拆出）。

负责：
  - 列宽/列顺序/可见性的保存（500ms 防抖）与恢复
  - 用户排序标记 user_sorted，以及 load_dataframe 之后重新应用排序
  - 表头右键菜单（列显隐）

关键约定（AGENTS.md）：
  - load_dataframe 总是重置为 rowid DESC，用户已排序时必须重新排一次，
    否则表头箭头与数据顺序不一致
  - 启动固定按 rowid DESC：restoreState 会按存储的指示器排序一次，
    这里清除指示器并重新装载数据抵消
  - 排序信号必须在 restoreState 之后连接，否则启动就被标记成已排序
"""

import base64

from PyQt6.QtCore import QByteArray, QObject, Qt, QTimer
from PyQt6.QtWidgets import QHeaderView, QMenu

# 书名 / 作者列固定 30 字符宽（超出截断显示省略号）。用像素而非字符数：
# 列宽以像素为单位，字符数需按表头字体换算。
_TITLE_COLUMN_CHARS = 30


def title_column_width(header) -> int:
  """按表头字体把 30 个字符换算成像素宽度"""
  font = header.font()
  fm = header.fontMetrics()
  return fm.horizontalAdvance('中' * _TITLE_COLUMN_CHARS)


class TableState(QObject):
  """QTableView 表头状态的持久化与排序重应用

  resize_to_contents_sections：恢复表头状态后必须保持 ResizeToContents 的列号。
  存量 headerState 可能保存了 Interactive + 被压缩的窄宽度（旧版 Stretch 列），
  restoreState 会用窄宽度覆盖代码里设的模式——这些列要强制重设，否则长内容
  （如 13 位 ISBN）会按窄宽截断成省略号。
  """

  def __init__(self, table, model, settings_factory, parent=None,
               resize_to_contents_sections=(),
               fixed_width_sections=()):
    super().__init__(parent)
    self._table = table
    self._model = model
    self._settings = settings_factory
    self._resize_to_contents_sections = frozenset(resize_to_contents_sections)
    # section → 返回像素宽度的可调用对象（恢复表头状态后强制重设，防旧状态覆盖）
    self._fixed_width_sections = dict(fixed_width_sections)
    self._user_sorted = False
    self._save_timer = None

  # ── 排序标记 ────────────────────────────────────

  @property
  def user_sorted(self) -> bool:
    return self._user_sorted

  @user_sorted.setter
  def user_sorted(self, value: bool):
    self._user_sorted = bool(value)

  def reapply_sort(self):
    """
    重新应用用户当前的表头排序。

    load_dataframe 总是把顺序重置为 rowid DESC，若用户已排序，
    必须再排一次，否则表头箭头与数据顺序会不一致。
    """
    if not self._user_sorted:
      return
    hdr = self._table.horizontalHeader()
    section = hdr.sortIndicatorSection()
    if 0 <= section < self._model.columnCount():
      self._model.sort(section, hdr.sortIndicatorOrder())

  # ── 保存（防抖） ────────────────────────────────

  def save_soon(self):
    """安排一次延迟保存（列宽拖动会连续触发 sectionResized）"""
    if self._save_timer is None:
      self._save_timer = QTimer(self)
      self._save_timer.setSingleShot(True)
      self._save_timer.timeout.connect(self.save_now)
    self._save_timer.start(500)

  def save_now(self):
    """实际执行表头状态保存"""
    state = self._table.horizontalHeader().saveState().data()
    self._settings().setValue(
      'headerState', base64.b64encode(state).decode('ascii'))

  # ── 恢复 ────────────────────────────────────────

  def load(self, reload_callback=None):
    """
    从 settings 恢复表头状态（列宽/顺序/可见性，不恢复排序）。

    reload_callback：恢复后重新装载数据的回调（用于抵消 restoreState
    内部触发的排序，让启动固定为 rowid DESC）。
    """
    hdr = self._table.horizontalHeader()
    state_b64 = self._settings().value('headerState', '')
    if state_b64:
      try:
        hdr.restoreState(QByteArray(base64.b64decode(state_b64)))
      except Exception:
        pass
      # 存量 headerState 会把每列 resize mode 一并恢复，可能把 ResizeToContents
      # 盖成旧 Interactive + 窄宽度（长内容如 13 位 ISBN 被截断）。强制重设回来。
      for section in self._resize_to_contents_sections:
        hdr.setSectionResizeMode(section, QHeaderView.ResizeMode.ResizeToContents)
      # 固定宽列（书名等）同理：恢复后强制按指定宽度重设，防旧状态覆盖
      for section, width_fn in self._fixed_width_sections.items():
        hdr.setSectionResizeMode(section, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(section, width_fn(hdr))
      hdr.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
      self._user_sorted = False
      if reload_callback:
        reload_callback()
    # 排序信号在恢复完成后才连接——启动恢复过程不标记 user_sorted；
    # 之后用户点击表头才会标记并保存
    try:
      hdr.sortIndicatorChanged.disconnect(self._on_sort_indicator_changed)
    except TypeError:
      pass
    hdr.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
    # 断开旧的信号连接以防重复绑定
    try:
      hdr.sectionMoved.disconnect()
    except TypeError:
      pass
    try:
      hdr.sectionResized.disconnect()
    except TypeError:
      pass
    hdr.sectionMoved.connect(self.save_soon)
    hdr.sectionResized.connect(self.save_soon)

  def _on_sort_indicator_changed(self, *_args):
    """表头排序变化（用户点击）：标记已排序并保存状态"""
    self._user_sorted = True
    self.save_soon()

  # ── 列显隐 ──────────────────────────────────────

  def show_menu(self, pos):
    """表头右键菜单：显隐列"""
    hdr = self._table.horizontalHeader()
    menu = QMenu(self._table)
    for col in range(hdr.count()):
      name = self._model.headerData(
        col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
      action = menu.addAction(name)
      action.setCheckable(True)
      action.setChecked(not hdr.isSectionHidden(col))
      action.triggered.connect(lambda _, c=col: self.toggle_column(c))
    menu.exec(hdr.mapToGlobal(pos))

  def toggle_column(self, col: int):
    """切换列的显隐"""
    hdr = self._table.horizontalHeader()
    hdr.setSectionHidden(col, not hdr.isSectionHidden(col))
    self.save_soon()
