"""工具栏组件"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
  QWidget, QHBoxLayout, QPushButton, QLabel, QFrame,
)

from config import Config


class ToolBarWidget(QWidget):
  """
  顶部工具栏：分组排列按钮，用分隔线区分功能区域。

  信号：
    import_requested()     — 加载 CSV
    export_requested()     — 保存 CSV
    stats_requested()      — 统计
    douban_search_requested() — 豆瓣搜索
    cover_wall_requested() — 封面墙
    web_toggled()          — Web 服务
    backup_requested()     — 恢复备份
    theme_toggled()        — 切换主题
    about_requested()      — 关于
  """

  import_requested = pyqtSignal()
  export_requested = pyqtSignal()
  stats_requested = pyqtSignal()
  douban_search_requested = pyqtSignal()
  cover_wall_requested = pyqtSignal()
  web_toggled = pyqtSignal()
  backup_requested = pyqtSignal()
  theme_toggled = pyqtSignal()
  about_requested = pyqtSignal()

  def __init__(self, dark_mode: bool = True, parent=None):
    super().__init__(parent)
    self._dark_mode = dark_mode
    self._setup_ui()

  def _setup_ui(self):
    """构建工具栏的所有控件"""
    row = QHBoxLayout(self)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)

    def sep():
      """添加垂直分隔线，颜色跟随主题"""
      line = QFrame()
      line.setFrameShape(QFrame.Shape.VLine)
      line.setFrameShadow(QFrame.Shadow.Sunken)
      c = self.palette().color(QPalette.ColorRole.Mid).name()
      line.setStyleSheet(f'color: {c};')
      row.addWidget(line)

    from ui.icon import make_theme_icon, make_about_icon

    self._btn_load = QPushButton('📂 加载 CSV')
    self._btn_load.setToolTip('从 CSV 导入图书数据')
    self._btn_save = QPushButton('💾 保存 CSV')
    self._btn_save.setToolTip('导出全部数据为 CSV')
    self._btn_stats = QPushButton('📊 统计')
    self._btn_stats.setToolTip('查看图书统计信息')
    self._btn_search_douban = QPushButton('🌐 豆瓣搜索')
    self._btn_search_douban.setToolTip('从豆瓣搜索图书并添加 (Ctrl+D)')
    self._btn_cover_wall = QPushButton('🖼️ 封面墙')
    self._btn_cover_wall.setToolTip('切换到封面墙视图 (Ctrl+W)')
    self._btn_web = QPushButton('🌐 Web 服务')
    self._btn_web.setToolTip('启动/停止内嵌 Web 服务')
    self._btn_restore = QPushButton('⏪ 恢复')
    self._btn_restore.setToolTip('从备份恢复数据库')
    self._btn_theme = QPushButton(make_theme_icon(self._dark_mode), '')
    self._btn_theme.setFixedSize(38, 34)
    self._btn_theme.setToolTip('切换亮色/暗色主题')
    self._btn_about = QPushButton(make_about_icon(), '')
    self._btn_about.setFixedSize(38, 34)
    self._btn_about.setToolTip('关于 Bookeeper')

    for btn in (self._btn_load, self._btn_save, self._btn_stats, self._btn_search_douban, self._btn_cover_wall, self._btn_web, self._btn_restore):
      btn.setFixedHeight(34)
      btn.setMinimumWidth(90)
    for btn in (self._btn_theme, self._btn_about):
      btn.setFixedHeight(34)

    # 数据操作组
    row.addWidget(self._btn_load)
    row.addWidget(self._btn_save)
    sep()
    # 搜索分析组
    row.addWidget(self._btn_search_douban)
    row.addWidget(self._btn_stats)
    row.addWidget(self._btn_cover_wall)
    sep()
    # 服务组
    row.addWidget(self._btn_web)
    row.addWidget(self._btn_restore)
    sep()
    # 设置组
    row.addWidget(self._btn_theme)
    row.addWidget(self._btn_about)

    self._file_label = QLabel('')
    c = self.palette().color(QPalette.ColorRole.PlaceholderText).name()
    self._file_label.setStyleSheet(f'color: {c}; font-size: 12px;')
    row.addWidget(self._file_label, stretch=1)

    # 信号绑定
    self._btn_load.clicked.connect(self.import_requested.emit)
    self._btn_save.clicked.connect(self.export_requested.emit)
    self._btn_stats.clicked.connect(self.stats_requested.emit)
    self._btn_search_douban.clicked.connect(self.douban_search_requested.emit)
    self._btn_cover_wall.clicked.connect(self.cover_wall_requested.emit)
    self._btn_web.clicked.connect(self.web_toggled.emit)
    self._btn_restore.clicked.connect(self.backup_requested.emit)
    self._btn_theme.clicked.connect(self.theme_toggled.emit)
    self._btn_about.clicked.connect(self.about_requested.emit)

  # ══════════════════════════════════════════════
  #  公开方法
  # ══════════════════════════════════════════════

  def set_file_label(self, text: str):
    """设置文件路径标签"""
    self._file_label.setText(text)

  def set_dark_mode(self, dark: bool):
    """更新主题按钮图标"""
    self._dark_mode = dark
    from ui.icon import make_theme_icon
    self._btn_theme.setIcon(make_theme_icon(dark))

  def set_cover_wall_mode(self, is_cover_wall: bool):
    """切换封面墙按钮文字"""
    if is_cover_wall:
      self._btn_cover_wall.setText('📊 表格视图')
      self._btn_cover_wall.setToolTip('切换到表格视图 (Ctrl+W)')
    else:
      self._btn_cover_wall.setText('🖼️ 封面墙')
      self._btn_cover_wall.setToolTip('切换到封面墙视图 (Ctrl+W)')

  def set_web_running(self, running: bool):
    """设置 Web 服务按钮状态"""
    if running:
      self._btn_web.setText('🛑 停止服务')
    else:
      self._btn_web.setText('🌐 Web 服务')

  def set_web_starting(self):
    """设置 Web 服务按钮为启动中状态"""
    self._btn_web.setText('⏳ 启动中...')

  def set_load_enabled(self, enabled: bool):
    """设置加载按钮的启用状态"""
    self._btn_load.setEnabled(enabled)
