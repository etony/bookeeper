"""
自动备份控制器（从 ui/main_window.py 拆出）。

要点：只有备份成功才清 dirty 标记；失败必须保留标记（下一轮定时器重试）
并把原因交给界面显示，不能只写日志。
"""
import os
import sys

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@pytest.fixture(scope='session')
def app():
  from PyQt6.QtWidgets import QApplication
  if not QApplication.instance():
    return QApplication(sys.argv)
  return QApplication.instance()


class _FakeService:
  def __init__(self, error=None, result='C:/fake/backup.db'):
    self.last_error = error
    self._result = result
    self.calls = 0

  def backup(self):
    self.calls += 1
    return self._result


@pytest.fixture
def controller(app):
  from ui.backup_controller import BackupController
  ctl = BackupController(service=_FakeService(), interval_ms=60000)
  yield ctl
  ctl.stop()


def _process_events(times=8):
  from PyQt6.QtWidgets import QApplication
  for _ in range(times):
    QApplication.processEvents()


class TestDirtyFlag:
  def test_starts_clean(self, controller):
    assert controller.dirty is False

  def test_mark_dirty(self, controller):
    controller.mark_dirty()
    assert controller.dirty is True

  def test_dirty_is_settable(self, controller):
    controller.dirty = True
    assert controller.dirty is True
    controller.dirty = False
    assert controller.dirty is False


class TestBackupRun:
  def test_clean_skips_backup(self, controller):
    controller.request_backup()
    _process_events()
    assert controller.service.calls == 0

  def test_success_clears_dirty(self, controller):
    controller.dirty = True
    controller.request_backup()
    _process_events()
    assert controller.service.calls == 1
    assert controller.dirty is False

  def test_failure_keeps_dirty_and_emits(self, controller):
    controller.service.last_error = '磁盘已满'
    controller.dirty = True
    messages = []
    controller.failed.connect(messages.append)
    controller.request_backup()
    _process_events()
    assert controller.dirty is True, '失败必须保留 dirty，下一轮定时器重试'
    assert messages and '备份失败' in messages[0]
    assert '磁盘已满' in messages[0]

  def test_backup_now_ignores_dirty(self, controller):
    """关闭窗口时无条件备份（backup 内部按 mtime 去重）"""
    controller.dirty = False
    assert controller.backup_now() is True
    assert controller.service.calls == 1

  def test_backup_now_reports_failure(self, controller):
    controller.service.last_error = '磁盘已满'
    messages = []
    controller.failed.connect(messages.append)
    assert controller.backup_now() is False
    assert messages


class TestTimer:
  def test_start_activates_timer(self, controller):
    assert not controller._timer.isActive()
    controller.start()
    assert controller._timer.isActive()

  def test_stop_deactivates_timer(self, controller):
    controller.start()
    controller.stop()
    assert not controller._timer.isActive()
