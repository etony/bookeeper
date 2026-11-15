"""
Web 服务控制器（从 ui/main_window.py 拆出）。

把 WebManager 的生命周期、状态文本和「启动后打开浏览器」收在一处，
主窗口只保留工具栏按钮和状态栏文案。
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


def _make_fake_manager():
  from PyQt6.QtCore import QObject, pyqtSignal

  class FakeManager(QObject):
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)
    data_changed = pyqtSignal()

    def __init__(self):
      super().__init__()
      self.is_running = False
      self.calls = []

    def start_server(self):
      self.calls.append('start')

    def stop_server(self):
      self.calls.append('stop')

    def cleanup(self):
      self.calls.append('cleanup')

  return FakeManager()


@pytest.fixture
def web(app):
  from ui.web_controller import WebController
  manager = _make_fake_manager()
  opened = []
  ctl = WebController(manager=manager, open_browser=opened.append)
  ctl.opened = opened
  return ctl


class TestLifecycle:
  def test_not_running_initially(self, web):
    assert web.is_running is False

  def test_start_delegates(self, web):
    web.start()
    assert web.manager.calls == ['start']

  def test_stop_delegates(self, web):
    web.stop()
    assert web.manager.calls == ['stop']

  def test_cleanup_delegates(self, web):
    web.cleanup()
    assert web.manager.calls == ['cleanup']

  def test_toggle_starts_when_stopped(self, web):
    assert web.toggle() is True
    assert web.manager.calls == ['start']

  def test_toggle_stops_when_running(self, web):
    web.manager.is_running = True
    assert web.toggle() is False
    assert web.manager.calls == ['stop']

  def test_is_running_follows_manager(self, web):
    web.manager.is_running = True
    assert web.is_running is True


class TestSignals:
  def test_started_emits_url_and_opens_browser(self, web):
    from config import Config
    urls = []
    web.started.connect(urls.append)
    web.manager.server_started.emit()
    assert urls == [f'http://127.0.0.1:{Config.WEB_PORT}']
    assert web.opened == urls, '启动成功后应自动打开浏览器'

  def test_stopped_forwarded(self, web):
    got = []
    web.stopped.connect(lambda: got.append(1))
    web.manager.server_stopped.emit()
    assert got

  def test_error_forwarded(self, web):
    errors = []
    web.failed.connect(errors.append)
    web.manager.error_occurred.emit('端口被占用')
    assert errors == ['端口被占用']

  def test_data_changed_forwarded(self, web):
    got = []
    web.data_changed.connect(lambda: got.append(1))
    web.manager.data_changed.emit()
    assert got
