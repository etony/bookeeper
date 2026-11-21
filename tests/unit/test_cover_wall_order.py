"""
封面墙排列顺序必须与表格视图一致。

表格默认按 rowid DESC（最新在前）；用户点击表头排序后，模型 DataFrame
会被重排。封面墙不能再有独立排序，必须按表格当前显示顺序铺卡片。
"""
import os
import sys

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from core.models.book import Book


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


def _seed():
  """按 5 / 9 / 7 的顺序插入 → rowid DESC 顺序是 7, 9, 5"""
  from services import get_repo
  repo = get_repo()
  for isbn, title, rating in [
    ('9787544291163', '低分书', '5'),
    ('9787530217337', '高分书', '9'),
    ('9787020002207', '中分书', '7'),
  ]:
    repo.upsert(Book(isbn=isbn, title=title, rating=rating))
  return repo


def _table_isbns(window):
  return list(window._model._data['ISBN'])


def _wall_isbns(window):
  return [card._book.isbn for card in window._cover_wall._cards]


class TestCoverWallOrder:
  def test_default_matches_table_rowid_order(self, window):
    """未排序时，封面墙与表格同为 rowid DESC（最新在前）"""
    _seed()
    window._load_data()
    assert _wall_isbns(window) == _table_isbns(window)

  def test_matches_table_after_user_sort(self, window):
    """用户按评分排序后，封面墙顺序与表格一致"""
    from PyQt6.QtCore import Qt
    from config import Config
    _seed()
    window._load_data()
    col = Config.TABLE_COLUMNS.index('评分')
    window._table.horizontalHeader().setSortIndicator(
      col, Qt.SortOrder.DescendingOrder)
    window._load_data()
    assert _wall_isbns(window) == _table_isbns(window)
    assert _wall_isbns(window)[0] == '9787530217337', '评分最高应排最前'

  def test_toggle_resyncs_after_sort(self, window):
    """加载后点表头排序，再切到封面墙，顺序仍与表格一致"""
    from PyQt6.QtCore import Qt
    from config import Config
    _seed()
    window._load_data()
    col = Config.TABLE_COLUMNS.index('评分')
    window._table.horizontalHeader().setSortIndicator(
      col, Qt.SortOrder.AscendingOrder)
    window._toggle_cover_wall()  # 切到封面墙
    assert _wall_isbns(window) == _table_isbns(window)
