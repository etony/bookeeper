import os
import time
import logging
import shutil

from config import Config

LOG = logging.getLogger(__name__)


class BackupService:
  """数据库自动备份服务，带旧备份清理机制"""

  def __init__(self, db_path: str = None):
    self._db_path = db_path or Config.DB_PATH

  def backup(self):
    """执行备份：复制数据库到 backups/ 目录，失败时仅打日志不抛出异常"""
    if not os.path.exists(self._db_path):
      return None
    base_dir = os.path.dirname(self._db_path)
    backup_dir = os.path.join(base_dir, 'backups')
    try:
      os.makedirs(backup_dir, exist_ok=True)
      ts = time.strftime('%Y%m%d_%H%M%S')
      path = os.path.join(backup_dir, f'book_backup_{ts}.db')
      shutil.copy2(self._db_path, path)
      LOG.info('自动备份成功: %s', path)
      self._clean(backup_dir)
      return path
    except (OSError, shutil.Error) as e:
      LOG.error('备份失败: %s', e)
      return None

  def _clean(self, backup_dir: str, keep: int = None):
    """只保留最近 keep 份备份，删除更旧的"""
    keep = keep or Config.BACKUP_KEEP
    try:
      files = sorted([f for f in os.listdir(backup_dir)
                      if f.startswith('book_backup_') and f.endswith('.db')])
      for f in files[:-keep]:
        os.remove(os.path.join(backup_dir, f))
        LOG.info('删除旧备份: %s', f)
    except OSError as e:
      LOG.error('清理旧备份失败: %s', e)
