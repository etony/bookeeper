"""
备份可靠性与批量操作原子性：

1. 备份失败只打日志，用户完全看不到；_do_backup 还在执行前就清掉 dirty 标记
   → 失败后下一轮定时器直接跳过，数据可能永远没有备份。
2. 批量删除/批量改状态逐条执行命令：中途失败会留下半套数据，
   撤销也要按 Ctrl+Z 几十次。
"""
import os
import sqlite3
import sys

import pytest

# GUI 测试需要 offscreen 平台（必须在 QApplication 创建前设置）
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from core.models.book import Book
from services.backup import BackupService

ISBNS = ['9787544291163', '9787530217337', '9787020002207']


class _NoopCoverPool:
  """测试期间禁止真实封面下载"""

  def submit(self, *args, **kwargs):
    return None


def _seed(isbns=ISBNS, status='默认'):
  from services import get_repo
  repo = get_repo()
  for i, isbn in enumerate(isbns):
    repo.upsert(Book(isbn=isbn, title=f'书{i}', status=status, shelf='A-1'))
  return repo


# ══════════════════════════════════════════════════
#  A. 备份失败必须可被调用方感知
# ══════════════════════════════════════════════════


@pytest.fixture
def db_file(tmp_path):
  """一个正常的 SQLite 库文件"""
  path = tmp_path / 'test.db'
  conn = sqlite3.connect(str(path))
  conn.execute('CREATE TABLE t (id INTEGER)')
  conn.commit()
  conn.close()
  return path


class TestBackupFailureVisible:
  def test_failure_sets_last_error(self, tmp_path):
    """数据库文件损坏：backup 返回 None 且记录失败原因"""
    bad = tmp_path / 'bad.db'
    bad.write_bytes(b'this is definitely not a sqlite database' * 50)
    svc = BackupService(db_path=str(bad))
    assert svc.backup() is None
    assert svc.last_error, '备份失败必须把原因记在 last_error'

  def test_success_resets_last_error(self, db_file):
    svc = BackupService(db_path=str(db_file))
    svc.last_error = '上次的旧错误'
    assert svc.backup() is not None
    assert svc.last_error is None

  def test_undeduped_skip_is_not_an_error(self, db_file):
    """mtime 去重跳过不算失败"""
    svc = BackupService(db_path=str(db_file))
    assert svc.backup() is not None
    assert svc.backup() is None
    assert svc.last_error is None

  def test_makedirs_failure_does_not_raise(self, db_file):
    """backups 路径被同名文件占用：不得抛异常（closeEvent 里会直接崩）"""
    backup_dir = db_file.parent / 'backups'
    backup_dir.write_text('not a directory')
    svc = BackupService(db_path=str(db_file))
    assert svc.backup() is None
    assert svc.last_error

  def test_missing_db_is_not_an_error(self, tmp_path):
    svc = BackupService(db_path=str(tmp_path / 'nope.db'))
    assert svc.backup() is None
    assert svc.last_error is None


# ══════════════════════════════════════════════════
#  B. dirty 标记时序（GUI）
# ══════════════════════════════════════════════════


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

  # settings.ini 隔离（AGENTS.md 规范）：写到临时副本，不污染真实文件
  settings_file = tmp_path / 'settings.ini'
  settings_file.write_text('[General]\n', encoding='utf-8')
  monkeypatch.setattr(
    MainWindow, '_settings',
    lambda self: QSettings(str(settings_file), QSettings.Format.IniFormat))
  monkeypatch.setattr('ui.cover_wall._cover_pool', _NoopCoverPool())
  win = MainWindow()
  yield win
  win.close()


def _process_events(times=8):
  from PyQt6.QtWidgets import QApplication
  for _ in range(times):
    QApplication.processEvents()


class TestDirtyTiming:
  def test_failure_keeps_dirty_and_shows_message(self, window, monkeypatch):
    calls = []

    def fake_backup():
      calls.append(1)
      window._backup_svc.last_error = '磁盘已满'
      return None

    monkeypatch.setattr(window._backup_svc, 'backup', fake_backup)
    window._dirty = True
    window._do_backup()
    _process_events()

    assert calls, '应执行备份'
    assert window._dirty is True, '备份失败必须保留 dirty，下一轮定时器重试'
    assert '备份失败' in window.statusBar().currentMessage(), \
      '备份失败必须提示用户，不能只写日志'

  def test_success_clears_dirty(self, window, monkeypatch):
    def fake_backup():
      window._backup_svc.last_error = None
      return 'C:/fake/book_backup.db'

    monkeypatch.setattr(window._backup_svc, 'backup', fake_backup)
    window._dirty = True
    window._do_backup()
    _process_events()
    assert window._dirty is False

  def test_clean_window_skips_backup(self, window, monkeypatch):
    calls = []
    monkeypatch.setattr(window._backup_svc, 'backup',
                        lambda: calls.append(1))
    window._dirty = False
    window._do_backup()
    _process_events()
    assert not calls


# ══════════════════════════════════════════════════
#  C. 批量操作原子化（单事务 + 单条撤销记录）
# ══════════════════════════════════════════════════


class TestRepoBatch:
  def test_delete_many(self, repo):
    from core.models.book import Book as B
    for isbn in ISBNS:
      repo.upsert(B(isbn=isbn, title='x'))
    assert repo.delete_many(ISBNS) == 3
    assert repo.count() == 0
    assert repo.delete_many([]) == 0

  def test_upsert_many(self, repo):
    from core.models.book import Book as B
    assert repo.upsert_many([B(isbn=i, title=f'书{k}')
                             for k, i in enumerate(ISBNS)]) == 3
    assert repo.count() == 3


class TestBatchUndo:
  def test_batch_delete_one_undo_restores_all(self, window):
    repo = _seed()
    window._delete_books(ISBNS)
    assert repo.count() == 0

    assert window._undo_manager.undo() is True
    assert repo.count() == 3, '一次撤销必须恢复整批删除'
    assert not window._undo_manager.can_undo(), '批量删除只应产生一条撤销记录'

  def test_batch_status_one_undo_restores_all(self, window):
    repo = _seed(status='默认')
    window._batch_update_status(ISBNS, '已读')
    assert {repo.get_by_isbn(i).status for i in ISBNS} == {'已读'}

    assert window._undo_manager.undo() is True
    assert {repo.get_by_isbn(i).status for i in ISBNS} == {'默认'}, \
      '一次撤销必须恢复整批状态（原先每本一条命令，要撤销 3 次）'
    assert not window._undo_manager.can_undo()
