"""
后台工作线程（从 ui/main_window.py 拆出）。

这些 worker 只做「在独立线程里跑阻塞调用 + 用信号回报」，
和主窗口的界面逻辑无关，拆开后主窗口只剩协调代码。
"""
import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from core.models.book import Book

ISBN = '9787544291163'


@pytest.fixture(scope='session')
def qapp():
  from PyQt6.QtCore import QCoreApplication
  app = QCoreApplication.instance() or QCoreApplication([])
  yield app


class _FakeApi:
  def __init__(self, book=None, error=None):
    self._book = book
    self._error = error
    self.calls = []

  def get_book_by_isbn(self, isbn):
    self.calls.append(isbn)
    if self._error:
      raise self._error
    return self._book


class TestFetchBookWorker:
  def test_success_emits_book(self, qapp):
    from ui.workers import FetchBookWorker
    book = Book(isbn=ISBN, title='书')
    got = []
    worker = FetchBookWorker(_FakeApi(book), ISBN)
    worker.finished.connect(got.append)
    worker.run()
    assert got == [book]

  def test_missing_book_emits_failure(self, qapp):
    from ui.workers import FetchBookWorker
    errors = []
    worker = FetchBookWorker(_FakeApi(None), ISBN)
    worker.failed.connect(errors.append)
    worker.run()
    assert len(errors) == 1 and ISBN in errors[0]

  def test_exception_emits_failure(self, qapp):
    from ui.workers import FetchBookWorker
    errors = []
    worker = FetchBookWorker(_FakeApi(error=RuntimeError('网络断开')), ISBN)
    worker.failed.connect(errors.append)
    worker.run()
    assert errors == ['网络断开']


class _FakeRepo:
  def __init__(self, count=3, error=None):
    self._count = count
    self._error = error
    self.seen = []

  def import_df(self, df, progress_callback=None):
    if self._error:
      raise self._error
    self.seen.append(df)
    if progress_callback:
      for i in range(self._count):
        progress_callback(i + 1, self._count)
    return self._count


class TestImportWorker:
  def test_reports_progress_and_count(self, qapp):
    from ui.workers import ImportWorker
    repo = _FakeRepo(count=3)
    progress, done = [], []
    worker = ImportWorker(repo, 'df')
    worker.progress.connect(lambda cur, total: progress.append((cur, total)))
    worker.finished.connect(done.append)
    worker.run()
    assert repo.seen == ['df']
    assert progress == [(1, 3), (2, 3), (3, 3)]
    assert done == [3]

  def test_exception_emits_failure(self, qapp):
    from ui.workers import ImportWorker
    errors = []
    worker = ImportWorker(_FakeRepo(error=ValueError('CSV 列缺失')), 'df')
    worker.failed.connect(errors.append)
    worker.run()
    assert errors == ['CSV 列缺失']
