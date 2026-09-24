"""备份服务测试"""
import os
import time
import tempfile
import shutil
import sqlite3
import pytest

from services.backup import BackupService


@pytest.fixture
def backup_env():
  """创建临时目录和测试数据库"""
  tmpdir = tempfile.mkdtemp()
  db_path = os.path.join(tmpdir, 'test.db')
  # 创建一个最小的 SQLite 数据库
  conn = sqlite3.connect(db_path)
  conn.execute('CREATE TABLE test (id INTEGER)')
  conn.execute("INSERT INTO test VALUES (1)")
  conn.commit()
  conn.close()
  yield tmpdir, db_path
  shutil.rmtree(tmpdir)


@pytest.fixture
def backup_service(backup_env):
  """创建 BackupService 实例"""
  _, db_path = backup_env
  return BackupService(db_path=db_path)


# ── 初始化 ──────────────────────────────────────────


def test_init_with_custom_path(backup_env):
  """使用自定义路径初始化"""
  _, db_path = backup_env
  svc = BackupService(db_path=db_path)
  assert svc._db_path == db_path


# ── 创建备份 ────────────────────────────────────────


def test_backup_creates_file(backup_service, backup_env):
  """备份创建文件"""
  result = backup_service.backup()
  assert result is not None
  assert os.path.exists(result)
  assert result.endswith('.db')


def test_backup_returns_path_in_backups_dir(backup_service, backup_env):
  """备份路径在 backups 目录下"""
  result = backup_service.backup()
  tmpdir, _ = backup_env
  assert result.startswith(os.path.join(tmpdir, 'backups'))


def test_backup_creates_backups_dir(backup_env):
  """备份自动创建 backups 目录"""
  _, db_path = backup_env
  svc = BackupService(db_path=db_path)
  result = svc.backup()
  assert os.path.isdir(os.path.join(os.path.dirname(db_path), 'backups'))


def test_backup_skips_when_no_change(backup_service):
  """数据库未变化时跳过备份"""
  first = backup_service.backup()
  second = backup_service.backup()
  assert first is not None
  assert second is None


def test_backup_skips_when_db_missing():
  """数据库文件不存在时返回 None"""
  svc = BackupService(db_path='/nonexistent/path/test.db')
  result = svc.backup()
  assert result is None


# ── 列出备份 ────────────────────────────────────────


def test_list_backups_empty(backup_service, backup_env):
  """无备份时返回空列表"""
  result = backup_service.list_backups()
  assert result == []


def test_list_backups_after_backup(backup_service):
  """备份后列出备份"""
  backup_service.backup()
  backups = backup_service.list_backups()
  assert len(backups) == 1
  path, name = backups[0]
  assert os.path.exists(path)
  assert name.startswith('book_backup_')
  assert name.endswith('.db')


def test_list_backups_sorted_newest_first(backup_service):
  """备份按时间倒序"""
  # 创建两个备份，中间加间隔确保时间戳不同
  backup_service.backup()
  time.sleep(1.1)
  # 修改数据库内容使 mtime 变化
  conn = sqlite3.connect(backup_service._db_path)
  conn.execute("INSERT INTO test VALUES (2)")
  conn.commit()
  conn.close()
  backup_service.backup()
  backups = backup_service.list_backups()
  assert len(backups) == 2
  # 最新的在前
  assert backups[0][1] >= backups[1][1]


# ── 清理旧备份 ──────────────────────────────────────


def test_clean_removes_old_backups(backup_service, backup_env):
  """清理保留指定数量的备份"""
  _, db_path = backup_env
  backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
  os.makedirs(backup_dir, exist_ok=True)

  # 手动创建 5 个假备份文件
  for i in range(5):
    fname = f'book_backup_20260101_00000{i}.db'
    fpath = os.path.join(backup_dir, fname)
    sqlite3.connect(fpath).close()
    # 设置不同的 mtime 以便排序
    os.utime(fpath, (i, i))

  # keep=3，应该删除最早 2 份
  backup_service._clean(backup_dir, keep=3)
  remaining = [f for f in os.listdir(backup_dir) if f.startswith('book_backup_')]
  assert len(remaining) == 3
