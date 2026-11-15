"""
搜索后必须保持用户已应用的排序。

load_dataframe 会把顺序重置为 rowid DESC（最新在前）；_load_data 之后有
「按 _user_sorted 重新应用表头排序」的补偿，但 _on_search_requested 漏了
这一步——搜索后表头箭头还指着「评分」，数据却按 rowid 排。
"""
import os
import sys

import pytest

# GUI 测试需要 offscreen 平台（必须在 QApplication 创建前设置）
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


def _first_rating(window):
  from config import Config
  col = Config.TABLE_COLUMNS.index('评分')
  return window._model.data(window._model.index(0, col))


class TestSearchKeepsSort:
  def test_search_preserves_user_sort(self, window):
    from PyQt6.QtCore import Qt
    from config import Config
    _seed()
    window._load_data()
    col = Config.TABLE_COLUMNS.index('评分')
    # 模拟用户点击「评分」表头（QTableView 会调用 model.sort）
    window._table.horizontalHeader().setSortIndicator(
      col, Qt.SortOrder.DescendingOrder)
    assert window._user_sorted, '点击表头后应标记已排序'
    assert _first_rating(window) == '9'

    # 搜索（空条件＝全部）后，排序必须保持
    window._on_search_requested('', '')
    assert _first_rating(window) == '9', \
      '搜索后必须重新应用用户排序（原先 load_dataframe 重置成 rowid DESC）'

  def test_search_without_user_sort_keeps_rowid_order(self, window):
    """用户没排序时，搜索结果保持 rowid DESC（最新在前），不得多排一次"""
    _seed()
    window._load_data()
    assert not window._user_sorted
    assert _first_rating(window) == '7'
    window._on_search_requested('', '')
    assert _first_rating(window) == '7'
