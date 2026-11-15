"""Web 服务管理组件"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal

# 已请求停止但 wait() 未能确认退出的线程 (thread, worker)。
# 必须保留引用：运行中的 QThread 被 GC 销毁会直接 abort 整个进程。
# 线程自然结束后由下一次 _retire() 清理。
_RETIRED = []


def _retire(thread, worker):
  """把线程引用交给看护列表保活，并顺带清理已结束的"""
  _RETIRED.append((thread, worker))
  for item in list(_RETIRED):
    t = item[0]
    try:
      finished = not t.isRunning()
    except RuntimeError:
      finished = True       # C++ 对象已销毁
    if finished:
      _RETIRED.remove(item)


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
  data_changed = pyqtSignal()  # Web端数据变更信号（从Web线程安全投递到主线程）

  def __init__(self):
    super().__init__()
    self._server = None
    self._stop_requested = False

  def run(self):
    try:
      if self._stop_requested:
        return
      from web.server import BookWebServer
      self._server = BookWebServer(on_started=self.started.emit,
                                   on_data_changed=self.data_changed.emit)
      # stop() 可能在上一步之间到达：server 已创建但还没启动，直接不启动
      if self._stop_requested:
        return
      self._server.start()
    except Exception as e:
      self.failed.emit(str(e))

  def stop(self):
    # 先置标志：即使服务尚未创建（run 还没走到 start），
    # 之后的 start() 也会立即返回而不是进入服务循环
    self._stop_requested = True
    if self._server:
      self._server.stop()


class WebManager(QObject):
  """
  管理 Web 服务的启动和停止。

  信号：
    server_started()    — 服务启动成功
    server_stopped()    — 服务已停止
    error_occurred(str) — 启动失败，携带错误消息
    data_changed()      — Web端数据变更（安全投递到主线程）
  """

  server_started = pyqtSignal()
  server_stopped = pyqtSignal()
  error_occurred = pyqtSignal(str)
  data_changed = pyqtSignal()  # 从Web线程安全投递到主线程

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
    self._worker.data_changed.connect(self.data_changed)  # 安全跨线程投递
    self._thread.start()

  def stop_server(self):
    """停止 Web 服务"""
    if not self.is_running:
      return

    worker, thread = self._worker, self._thread
    worker.stop()
    thread.quit()
    if not thread.wait(3000):
      # 没能在超时内退出：不能丢弃运行中线程的引用（GC 会 abort 整个进程），
      # 交给看护列表，等它自己结束
      _retire(thread, worker)
    self._worker = None
    self._thread = None
    self.server_stopped.emit()

  def cleanup(self):
    """清理资源（关闭窗口时调用）"""
    if not self.is_running:
      return
    worker, thread = self._worker, self._thread
    worker.stop()
    thread.quit()
    if not thread.wait(5000):
      # 同上：不 terminate()（强杀线程会破坏解释器状态），改为保活等待自然退出
      _retire(thread, worker)
    self._worker = None
    self._thread = None
    self.server_stopped.emit()

  def _on_server_started(self):
    """服务启动成功回调"""
    self.server_started.emit()

  def _on_error(self, msg: str):
    """服务启动失败回调"""
    worker, thread = self._worker, self._thread
    if thread is not None:
      thread.quit()
      if not thread.wait(3000):
        _retire(thread, worker)
    self._worker = None
    self._thread = None
    self.error_occurred.emit(msg)
