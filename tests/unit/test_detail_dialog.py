"""
详情对话框的后台化：豆瓣补充请求不得阻塞 GUI 线程。

原先 _load_current 在 GUI 线程同步调豆瓣 API（3 次重试 × 10s 超时 + 退避，
最坏 ~32s），双击打开缺封面/出版年的书会让整个应用"未响应"。
封面下载早已是线程化的，这里补齐同一模式。
"""
import os
import sys
import threading
import time

import pytest

# GUI 测试需要 offscreen 平台（必须在 QApplication 创建前设置）
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from core.models.book import Book

A_ISBN = '9787544291163'   # 缺封面/出版年 → 触发后台补充
B_ISBN = '9787530217337'   # 字段完整 → 不触发


def _wait_until(cond, timeout=5.0):
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


class _FakeDouban:
  """替身豆瓣服务：记录每次调用所在线程，可选延迟后返回补齐字段的 Book"""

  instances = []

  def __init__(self, delay=0.0):
    self.calls = []
    self._delay = delay
    _FakeDouban.instances.append(self)

  def get_book_by_isbn(self, isbn):
    self.calls.append((isbn, threading.current_thread()))
    if self._delay:
      time.sleep(self._delay)
    return Book(isbn=isbn, title='豆瓣补全', pubdate='2008-1',
                cover_url='https://img.example/large.jpg',
                douban_url='https://book.douban.com/subject/1/', pages='302')


@pytest.fixture(scope='session')
def app():
  from PyQt6.QtWidgets import QApplication
  if not QApplication.instance():
    return QApplication(sys.argv)
  return QApplication.instance()


@pytest.fixture
def no_network(app, monkeypatch):
  """禁止测试发起真实封面下载"""
  monkeypatch.setattr('services.covers.get_cover', lambda *a, **k: (None, None))


def _finish(dialog, enrich_thread):
  """关闭对话框并等后台线程退出，避免运行中的 QThread 被 GC 销毁导致 abort"""
  dialog.close()
  if enrich_thread is not None:
    _wait_until(lambda: not _is_running(enrich_thread))
  from ui import detail_dialog as dd
  _wait_until(lambda: all(not _is_running(t) for t, _ in dd._retired_threads))


class TestEnrichRunsInBackground:
  """豆瓣字段补充走独立线程，GUI 线程只做本地读写"""

  def test_douban_call_off_main_thread(self, no_network, monkeypatch):
    _FakeDouban.instances.clear()
    monkeypatch.setattr('ui.detail_dialog.DoubanService', lambda: _FakeDouban())
    from services import get_repo
    get_repo().upsert(Book(isbn=A_ISBN, title='缺字段的书'))

    from ui.detail_dialog import DetailDialog
    dlg = DetailDialog(isbn_list=[A_ISBN], index=0)
    enrich_thread = getattr(dlg, '_enrich_thread', None)
    try:
      # 不等豆瓣：页面立刻渲染数据库里的内容
      assert '缺字段的书' in dlg._info.toHtml()
      dlg.show()
      api = _FakeDouban.instances[0]
      assert _wait_until(lambda: api.calls), '应触发豆瓣补充请求'
      caller = api.calls[0][1]
      assert caller is not threading.main_thread(), \
        '豆瓣请求不得在 GUI 线程执行（原先的假死根因）'
      # 补充结果写回数据库
      assert _wait_until(lambda: get_repo().get_by_isbn(A_ISBN).pubdate == '2008-1')
      assert get_repo().get_by_isbn(A_ISBN).cover_url == 'https://img.example/large.jpg'
      # 对话框可见时，补充完成后自动刷新显示
      assert _wait_until(lambda: '2008-1' in dlg._info.toHtml())
    finally:
      _finish(dlg, enrich_thread)

  def test_late_result_does_not_clobber_current_page(self, no_network, monkeypatch):
    """慢返回的补充结果只更新缓存，不覆盖用户已翻到的其他页"""
    _FakeDouban.instances.clear()
    monkeypatch.setattr('ui.detail_dialog.DoubanService',
                        lambda: _FakeDouban(delay=0.3))
    from services import get_repo
    repo = get_repo()
    repo.upsert(Book(isbn=A_ISBN, title='A书-缺字段'))
    repo.upsert(Book(isbn=B_ISBN, title='B书-完整', pubdate='2010-1',
                     cover_url='https://img.example/b.jpg'))

    from ui.detail_dialog import DetailDialog
    dlg = DetailDialog(isbn_list=[A_ISBN, B_ISBN], index=0)
    enrich_thread = getattr(dlg, '_enrich_thread', None)
    try:
      dlg.show()
      dlg._goto(1)          # A 的补充还在路上，先翻到 B
      assert 'B书-完整' in dlg._info.toHtml()
      # A 的结果晚到：进缓存、写库
      assert _wait_until(lambda: dlg._cache[A_ISBN].pubdate == '2008-1')
      assert repo.get_by_isbn(A_ISBN).pubdate == '2008-1'
      # 但当前显示的仍是用户翻到的 B
      assert 'B书-完整' in dlg._info.toHtml()
      # 全程不允许任何一次豆瓣调用发生在主线程
      api = _FakeDouban.instances[0]
      assert api.calls, '应触发豆瓣补充请求'
      assert all(t is not threading.main_thread() for _, t in api.calls), \
        '豆瓣请求不得在 GUI 线程执行'
    finally:
      _finish(dlg, enrich_thread)
