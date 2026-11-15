"""
QThread 生命周期看护。

同一套「运行中的 QThread 不能丢引用」逻辑原先在 ui/main_window.py、
ui/detail_dialog.py、ui/components/web_manager.py 各写了一遍。
现在统一到 ui/thread_utils.py：一个看护列表 + retire() + prune_retired()。

为什么不能丢引用：Python 持有的 QThread 在运行中被 GC 销毁会直接
abort 整个进程（Windows 退出码 0xC0000409）。
"""
import os
import threading

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@pytest.fixture
def thread_utils():
  from ui import thread_utils as tu
  tu.RETIRED[:] = []        # 每个测试从干净状态开始
  yield tu
  tu.RETIRED[:] = []


class _BlockingThread:
  """最小的 QThread 替身：isRunning() 由事件控制"""

  def __init__(self, running=True):
    self._running = running

  def isRunning(self):
    return self._running

  def finish(self):
    self._running = False


class _DestroyedThread:
  """C++ 对象已被销毁的 QThread：isRunning() 抛 RuntimeError"""

  def isRunning(self):
    raise RuntimeError('QThread has been deleted')


class TestRetire:
  def test_keeps_running_thread_alive(self, thread_utils):
    thread = _BlockingThread()
    thread_utils.retire(thread, 'worker')
    assert thread_utils.RETIRED == [(thread, 'worker')], \
      '运行中的线程必须留在看护列表里（否则被 GC 会 abort 进程）'

  def test_finished_thread_is_not_kept(self, thread_utils):
    thread = _BlockingThread(running=False)
    thread_utils.retire(thread, None)
    assert thread_utils.RETIRED == []

  def test_worker_is_optional(self, thread_utils):
    thread = _BlockingThread()
    thread_utils.retire(thread)
    assert thread_utils.RETIRED == [(thread, None)]

  def test_destroyed_thread_does_not_raise(self, thread_utils):
    thread_utils.retire(_DestroyedThread(), None)
    assert thread_utils.RETIRED == [], \
      'C++ 对象已销毁时 isRunning() 抛 RuntimeError，不得让异常逃出'


class TestPruneRetired:
  def test_drops_only_finished(self, thread_utils):
    alive = _BlockingThread()
    dead = _BlockingThread(running=False)
    thread_utils.RETIRED.extend([(alive, 'a'), (dead, 'd')])
    thread_utils.prune_retired()
    assert thread_utils.RETIRED == [(alive, 'a')]

  def test_empty_list_is_noop(self, thread_utils):
    thread_utils.prune_retired()
    assert thread_utils.RETIRED == []


class TestSingleSharedList:
  """三个模块必须共用同一个看护列表（测试也依赖这些别名）"""

  def test_detail_dialog_alias(self, thread_utils):
    from ui import detail_dialog
    assert detail_dialog._retired_threads is thread_utils.RETIRED

  def test_main_window_alias(self, thread_utils):
    from ui import main_window
    assert main_window._retired_threads is thread_utils.RETIRED

  def test_web_manager_alias(self, thread_utils):
    from ui.components import web_manager
    assert web_manager._RETIRED is thread_utils.RETIRED
