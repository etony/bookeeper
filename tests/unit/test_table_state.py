"""
表头状态（列宽/顺序/可见性/排序）的保存与恢复（从 ui/main_window.py 拆出）。

关键约定（AGENTS.md）：
  - load_dataframe 总是重置为 rowid DESC；用户已排序时必须重新应用排序
  - 启动固定按 rowid DESC，不恢复 headerState 里的排序指示器
  - 排序信号必须在 restoreState 之后连接，否则启动就被标记成已排序
"""
import base64
import os
import sys

import pandas as pd
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from config import Config


@pytest.fixture(scope='session')
def app():
  from PyQt6.QtWidgets import QApplication
  if not QApplication.instance():
    return QApplication(sys.argv)
  return QApplication.instance()


@pytest.fixture
def view(app):
  from PyQt6.QtWidgets import QTableView
  from models.table_model import BookTableModel
  v = QTableView()
  model = BookTableModel(
    pd.DataFrame({c: [] for c in Config.TABLE_COLUMNS}, dtype=object))
  v.setModel(model)
  v.setSortingEnabled(True)
  return v


@pytest.fixture
def settings_file(tmp_path):
  from PyQt6.QtCore import QSettings
  path = tmp_path / 'settings.ini'
  path.write_text('[General]\n', encoding='utf-8')
  return QSettings(str(path), QSettings.Format.IniFormat)


@pytest.fixture
def state(view, settings_file):
  from ui.table_state import TableState
  return TableState(view, view.model(), lambda: settings_file)


def _fill(view, rows):
  df = pd.DataFrame(rows, columns=Config.TABLE_COLUMNS)
  view.model().load_dataframe(df)


def _first(view, col_name):
  col = Config.TABLE_COLUMNS.index(col_name)
  return view.model().data(view.model().index(0, col))


class TestSortTracking:
  def test_starts_unsorted(self, state):
    assert state.user_sorted is False

  def test_user_sort_marks_sorted(self, state):
    from PyQt6.QtCore import Qt
    state.load(lambda: None)
    state._table.horizontalHeader().setSortIndicator(
      1, Qt.SortOrder.DescendingOrder)
    assert state.user_sorted is True

  def test_user_sort_schedules_save(self, state):
    from PyQt6.QtCore import Qt
    state.load(lambda: None)
    state._table.horizontalHeader().setSortIndicator(
      1, Qt.SortOrder.DescendingOrder)
    assert state._save_timer is not None and state._save_timer.isActive()


class TestReapplySort:
  def test_noop_when_unsorted(self, state, view):
    _fill(view, [{'ISBN': '1', '评分': '5'}, {'ISBN': '2', '评分': '9'}])
    state.reapply_sort()
    assert _first(view, '评分') == '5'

  def test_reapplies_numeric_sort(self, state, view):
    from PyQt6.QtCore import Qt
    state.load(lambda: None)
    hdr = view.horizontalHeader()
    hdr.setSortIndicator(Config.TABLE_COLUMNS.index('评分'),
                         Qt.SortOrder.DescendingOrder)
    _fill(view, [{'ISBN': '1', '评分': '5'}, {'ISBN': '2', '评分': '9'},
                 {'ISBN': '3', '评分': '7'}])
    state.reapply_sort()
    assert _first(view, '评分') == '9'


class TestLoad:
  def test_saved_state_is_restored_and_sort_reset(self, state, view,
                                                  settings_file):
    from PyQt6.QtCore import Qt
    hdr = view.horizontalHeader()
    hdr.setSortIndicator(1, Qt.SortOrder.DescendingOrder)
    settings_file.setValue(
      'headerState',
      base64.b64encode(hdr.saveState().data()).decode('ascii'))

    reloads = []
    state.load(lambda: reloads.append(1))
    assert reloads == [1], '恢复状态后必须重新装载数据（抵消 restoreState 的排序）'
    assert hdr.sortIndicatorSection() == -1, '启动不恢复排序指示器'
    assert state.user_sorted is False

  def test_no_saved_state_still_connects_sort_signal(self, state, view):
    from PyQt6.QtCore import Qt
    state.load(lambda: None)
    view.horizontalHeader().setSortIndicator(2, Qt.SortOrder.AscendingOrder)
    assert state.user_sorted is True

  def test_restore_does_not_mark_user_sorted(self, state, view,
                                             settings_file):
    from PyQt6.QtCore import Qt
    hdr = view.horizontalHeader()
    hdr.setSortIndicator(1, Qt.SortOrder.DescendingOrder)
    settings_file.setValue(
      'headerState',
      base64.b64encode(hdr.saveState().data()).decode('ascii'))
    state.load(lambda: None)
    assert state.user_sorted is False, \
      'restoreState 内部触发的排序不得被当成用户排序'


class TestColumns:
  def test_toggle_column_hides_and_saves(self, state, view):
    hdr = view.horizontalHeader()
    state.toggle_column(2)
    assert hdr.isSectionHidden(2) is True
    state.toggle_column(2)
    assert hdr.isSectionHidden(2) is False
    assert state._save_timer is not None and state._save_timer.isActive()

  def test_save_now_writes_state(self, state, settings_file):
    state.save_now()
    assert settings_file.value('headerState', ''), \
      'save_now 必须把表头状态写进 settings'
