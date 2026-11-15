"""
Web 服务管理组件的启停正确性：

1. 端口被占用时 uvicorn 直接 sys.exit(1)（BaseException），原 _WebWorker 的
   except Exception 接不住 → failed 信号永不发出 → UI 永卡「正在启动」。
2. 启动后立即停止的竞态：stop() 早于 server 创建时是空操作，服务会永远
   跑下去，wait() 超时后引用被丢弃 → 运行中的 QThread 被 GC 直接 abort。
"""
import os
import socket
import threading
import time

import pytest

# GUI 测试需要 offscreen 平台（必须在 QApplication 创建前设置）
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# 测试内引用保活：失败路径上若线程仍在运行，先扣住引用避免被 GC 销毁
# （运行中的 QThread 被 GC 会直接 abort 整个测试进程）
_RESCUE = []


def _wait_until(cond, timeout=8.0):
  """跑 Qt 事件循环直到条件成立（工作线程的信号要经事件循环才会投递）"""
  from PyQt6.QtWidgets import QApplication
  deadline = time.time() + timeout
  while time.time() < deadline:
    if cond():
      return True
    QApplication.processEvents()
    time.sleep(0.01)
  return bool(cond())


def _is_running(thread):
  try:
    return thread.isRunning()
  except RuntimeError:
    return False        # C++ 对象已被销毁


def _rescue(thread, worker=None):
  """线程还在跑就扣住引用，交给测试模块保活"""
  if thread is not None and _is_running(thread):
    _RESCUE.append((thread, worker))


def _occupy_port():
  """占住一个端口，返回 (socket, 端口号)（模拟其他程序已监听该端口）"""
  s = socket.socket()
  s.bind(('127.0.0.1', 0))
  s.listen(1)
  return s, s.getsockname()[1]


def _free_port():
  """拿一个当前空闲的端口号（先占后放，存在小概率竞争，测试可接受）"""
  s = socket.socket()
  s.bind(('127.0.0.1', 0))
  port = s.getsockname()[1]
  s.close()
  return port


# ══════════════════════════════════════════════════
#  A. BookWebServer.start 的失败语义（非 Qt，确定性）
# ══════════════════════════════════════════════════


class TestBookWebServerStartFailure:
  """端口冲突必须转成 RuntimeError；stop 早于 start 不得进入服务循环"""

  def test_occupied_port_raises_runtimeerror(self, monkeypatch):
    from web.server import BookWebServer
    sock, port = _occupy_port()
    monkeypatch.setattr('config.Config.WEB_PORT', port)
    result = {}

    def _run():
      try:
        BookWebServer().start()
        result['exc'] = None
      except BaseException as e:       # SystemExit 是 BaseException
        result['exc'] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=15)
    assert not t.is_alive(), 'start() 应在绑定失败后返回'
    exc = result.get('exc')
    assert exc is not None, '端口占用时 start() 必须抛异常'
    assert isinstance(exc, RuntimeError), \
      f'应转成 RuntimeError 而不是 {type(exc).__name__}（uvicorn 会 sys.exit）'
    assert '端口' in str(exc), f'错误消息应包含端口号: {exc}'
    sock.close()

  def test_stop_before_start_returns_immediately(self):
    """竞态：stop() 先到、start() 后到 → start 不得进入服务循环"""
    from web.server import BookWebServer
    srv = BookWebServer()
    srv.stop()                        # 服务尚未创建，原实现这里是空操作
    t = threading.Thread(target=srv.start, daemon=True)
    t.start()
    t.join(timeout=5)
    assert not t.is_alive(), \
      'stop 请求已先到，start() 应立即返回而不是启动服务'


# ══════════════════════════════════════════════════
#  B. WebManager 信号与状态（Qt 事件循环）
# ══════════════════════════════════════════════════


@pytest.fixture(scope='session')
def app():
  from PyQt6.QtWidgets import QApplication
  if not QApplication.instance():
    return QApplication([])
  return QApplication.instance()


@pytest.fixture
def manager(app, monkeypatch):
  from ui.components.web_manager import WebManager
  m = WebManager()
  errors = []
  started = []
  stopped = []
  m.error_occurred.connect(errors.append)
  m.server_started.connect(lambda: started.append(True))
  m.server_stopped.connect(lambda: stopped.append(True))
  m._test_errors = errors       # 供断言读取
  m._test_started = started
  m._test_stopped = stopped
  yield m
  # teardown：尽力停止；若线程仍未退出，引用保活，避免运行中被 GC
  try:
    m.cleanup()
  except Exception:
    pass
  thread = getattr(m, '_thread', None)
  worker = getattr(m, '_worker', None)
  _rescue(thread, worker)


class TestPortInUse:
  """端口被占用时必须报错，而不是永远「正在启动」"""

  def test_occupied_port_emits_error(self, manager, monkeypatch):
    sock, port = _occupy_port()
    try:
      monkeypatch.setattr('config.Config.WEB_PORT', port)
      manager.start_server()
      assert _wait_until(lambda: manager._test_errors), \
        '端口占用必须触发 error_occurred（原先 SystemExit 逃逸，信号永不发出）'
      msg = manager._test_errors[0]
      assert '端口' in msg, f'错误消息应包含端口号信息: {msg}'
      # 失败后状态必须复位，允许用户改端口后重试
      assert not manager.is_running
    finally:
      sock.close()

  def test_restart_after_port_error_succeeds(self, manager, monkeypatch):
    """端口占用失败后，换空闲端口能正常启动/停止（引用已正确清理）"""
    sock, port = _occupy_port()
    try:
      monkeypatch.setattr('config.Config.WEB_PORT', port)
      manager.start_server()
      assert _wait_until(lambda: manager._test_errors)
    finally:
      sock.close()

    monkeypatch.setattr('config.Config.WEB_PORT', _free_port())
    manager.start_server()
    assert _wait_until(lambda: manager._test_started), '换端口后应能正常启动'
    manager.stop_server()
    assert _wait_until(lambda: manager._test_stopped)
    assert not manager.is_running
    assert _wait_until(lambda: not any(_is_running(t) for t in _all_threads())), \
      'stop_server 后不得留下运行中的线程'


class TestStopRace:
  """启动后立即停止：不崩溃、不泄漏运行中的线程"""

  def test_stop_immediately_after_start(self, manager, monkeypatch):
    monkeypatch.setattr('config.Config.WEB_PORT', _free_port())
    manager.start_server()
    thread = manager._thread
    try:
      manager.stop_server()          # 立刻停——此时 server 可能尚未创建
    finally:
      _rescue(thread, getattr(manager, '_worker', None))

    assert not manager.is_running
    assert manager._test_stopped, 'stop_server 必须发出 server_stopped'
    # 线程必须真正退出（引用不得在运行中被丢弃）
    assert _wait_until(lambda: not _is_running(thread), timeout=6.0), \
      'stop_server 后线程必须退出（否则运行中 QThread 被 GC 会 abort）'

  def test_cleanup_after_start(self, manager, monkeypatch):
    """cleanup（关闭窗口路径）同样不得留下运行中的线程"""
    monkeypatch.setattr('config.Config.WEB_PORT', _free_port())
    manager.start_server()
    thread = manager._thread
    try:
      manager.cleanup()
    finally:
      _rescue(thread, getattr(manager, '_worker', None))

    assert not manager.is_running
    assert manager._test_stopped
    assert _wait_until(lambda: not _is_running(thread), timeout=6.0), \
      'cleanup 后线程必须退出'


def _all_threads():
  """实现看护列表中的线程（若已存在）+ 测试保活列表"""
  from ui.components import web_manager as wm
  return [t for t, _ in _RESCUE] + [t for t, _ in getattr(wm, '_RETIRED', [])]
