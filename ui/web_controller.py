"""
Web 服务控制器（从 ui/main_window.py 拆出）。

职责：
  - 创建并持有 WebManager（后台线程跑 uvicorn）
  - 把启停、状态和错误统一成对外的信号
  - 启动成功后自动打开浏览器

主窗口只保留工具栏按钮与状态栏文案，不再关心线程细节。
"""

import webbrowser

from PyQt6.QtCore import QObject, pyqtSignal

from config import Config
from ui.components import WebManager


class WebController(QObject):
  """
  内嵌 Web 服务的界面侧封装。

  信号：
    started(str)  — 服务已开始监听，携带访问地址
    stopped()     — 服务已停止
    failed(str)   — 启动失败（端口占用等）
    data_changed()— Web 端修改了数据（已投递到主线程）
  """

  started = pyqtSignal(str)
  stopped = pyqtSignal()
  failed = pyqtSignal(str)
  data_changed = pyqtSignal()

  def __init__(self, parent=None, manager=None, open_browser=None):
    super().__init__(parent)
    self._manager = manager or WebManager(self)
    self._open_browser = open_browser or webbrowser.open
    self._manager.server_started.connect(self._on_started)
    self._manager.server_stopped.connect(self.stopped)
    self._manager.error_occurred.connect(self.failed)
    self._manager.data_changed.connect(self.data_changed)

  @property
  def manager(self):
    return self._manager

  @property
  def is_running(self) -> bool:
    """服务是否正在运行（含正在启动）"""
    return self._manager.is_running

  @property
  def url(self) -> str:
    # 只监听本机：个人图书管理工具不对外暴露
    return f'http://127.0.0.1:{Config.WEB_PORT}'

  # ── 启停 ────────────────────────────────────────

  def start(self):
    self._manager.start_server()

  def stop(self):
    self._manager.stop_server()

  def toggle(self) -> bool:
    """工具栏开关：已在运行则停止，否则启动。返回操作后是否应在运行"""
    if self._manager.is_running:
      self._manager.stop_server()
      return False
    self._manager.start_server()
    return True

  def cleanup(self):
    """关闭窗口时清理线程"""
    self._manager.cleanup()

  # ── 内部回调 ────────────────────────────────────

  def _on_started(self):
    self.started.emit(self.url)
    self._open_browser(self.url)
