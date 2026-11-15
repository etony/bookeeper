"""
表格列宽配置。

ISBN 列必须是 ResizeToContents：13 位 ISBN 较长，用默认的 Stretch 拉伸
会被压缩到截断（显示省略号）。列 0 的配置在 MainWindow._init_table。
"""
import os
import sys

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from core.models.book import Book

LONG_ISBN = '9787544291163'


class _NoopCoverPool:
  def submit(self, *args, **kwargs):
    return None


@pytest.fixture(scope='session')
def app():
  from PyQt6.QtWidgets import QApplication
  if not QApplication.instance():
    return QApplication(sys.argv)
  return QApplication.instance()


@pytest.fixture
def window(app, monkeypatch, tmp_path):
  from PyQt6.QtCore import QSettings
  from ui.main_window import MainWindow

  settings_file = tmp_path / 'settings.ini'
  settings_file.write_text('[General]\n', encoding='utf-8')
  monkeypatch.setattr(
    MainWindow, '_settings',
    lambda self: QSettings(str(settings_file), QSettings.Format.IniFormat))
  monkeypatch.setattr('ui.cover_wall._cover_pool', _NoopCoverPool())
  win = MainWindow()
  yield win
  win.close()


class TestIsbnColumnWidth:
  def test_isbn_column_is_resize_to_contents(self, window):
    """13 位 ISBN 必须能完整显示，不能是 Stretch 截断"""
    from PyQt6.QtWidgets import QHeaderView
    hdr = window._table.horizontalHeader()
    assert hdr.sectionResizeMode(0) == QHeaderView.ResizeMode.ResizeToContents, \
      'ISBN 列用 Stretch 会压缩截断（显示省略号），应改为 ResizeToContents'

  def test_wide_isbn_fits_column(self, window):
    """最长 13 位 ISBN 时列宽必须容纳完整内容"""
    from PyQt6.QtWidgets import QApplication
    from services import get_repo
    get_repo().upsert(Book(isbn=LONG_ISBN, title='测试书'))
    window._load_data()
    window.show()
    QApplication.processEvents()
    hdr = window._table.horizontalHeader()
    assert hdr.sectionSize(0) >= hdr.sectionSizeHint(0), \
      'ISBN 列宽度必须 >= 内容提示宽度，否则会截断显示'