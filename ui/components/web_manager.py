"""Web 服务管理组件"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class _WebWorker(QObject):
  """
  在后台线程中运行 FastAPI Web 服务。

  为什么需要这个类？
    uvicorn.run() 是阻塞调用，如果在主线程执行，
    Qt 界面会卡死。通过 moveToThread + 信号驱动，
    让 Web 服务在独立线程中运行。
  """

  started = pyqtSignal()
  failed = pyqtSignal(str)

  def __init__(self):
    super().__init__()
    self._server = None

  def run(self):
    try:
      from web.server import BookWebServer
      self._server = BookWebServer(on_started=self.started.emit)
      self._server.start()
    except Exception as e:
      self.failed.emit(str(e))

  def stop(self):
    if self._server:
      self._server.stop()


class WebManager(QObject):
  """
  管理 Web 服务的启动和停止。

  信号：
    server_started()    — 服务启动成功
    server_stopped()    — 服务已停止
    error_occurred(str) — 启动失败，携带错误消息
  """

  server_started = pyqtSignal()
  server_stopped = pyqtSignal()
  error_occurred = pyqtSignal(str)

  def __init__(self, parent=None):
    super().__init__(parent)
    self._worker = None
    self._thread = None

  @property
  def is_running(self) -> bool:
    """服务是否正在运行"""
    return self._worker is not None and self._thread is not None

  def start_server(self):
    """启动 Web 服务"""
    if self.is_running:
      return

    self._thread = QThread()
    self._worker = _WebWorker()
    self._worker.moveToThread(self._thread)
    self._thread.started.connect(self._worker.run)
    self._worker.started.connect(self._on_server_started)
    self._worker.failed.connect(self._on_error)
    self._thread.start()

  def stop_server(self):
    """停止 Web 服务"""
    if not self.is_running:
      return

    self._worker.stop()
    self._thread.quit()
    self._thread.wait(3000)
    self._worker = None
    self._thread = None
    self.server_stopped.emit()

  def cleanup(self):
    """清理资源（关闭窗口时调用）"""
    self.stop_server()

  def _on_server_started(self):
    """服务启动成功回调"""
    self.server_started.emit()

  def _on_error(self, msg: str):
    """服务启动失败回调"""
    self._thread.quit()
    self._thread.wait(3000)
    self._worker = None
    self._thread = None
    self.error_occurred.emit(msg)
