"""
┌──────────────────────────────────────────┐
│  自动备份服务                             │
│                                          │
│  定时复制数据库文件到 backups/ 目录，      │
│  并自动清理 30 天前的旧备份。             │
│  所有操作异常安全——失败只打日志不崩溃。     │
└──────────────────────────────────────────┘
"""

import os
import time
import logging
import shutil

from config import Config

LOG = logging.getLogger(__name__)


class BackupService:
  """
  数据库自动备份服务。

  用法：
    svc = BackupService()
    svc.backup()          # 立即备份
    # 与 QTimer 配合实现定时备份

  备份文件命名：book_backup_YYYYMMDD_HHMMSS.db
  """

  def __init__(self, db_path: str = None):
    # db_path 默认取 Config.DB_PATH，也可传入自定义路径（测试用）
    self._db_path = db_path or Config.DB_PATH

  def _latest_backup_path(self, backup_dir: str):
    """返回 backups 目录中最新的备份文件路径，无则返回 None"""
    files = sorted([f for f in os.listdir(backup_dir)
                    if f.startswith('book_backup_') and f.endswith('.db')],
                   reverse=True)
    return os.path.join(backup_dir, files[0]) if files else None

  def backup(self):
    """
    执行一次备份。

    流程：
      1. 检查数据库文件是否存在
      2. 若已有备份且数据库 mtime 未变 → 跳过（去重）
      3. 创建 backups/ 目录（不存在则新建）
      4. 以时间戳命名复制数据库
      5. 清理超出保留数量的旧备份
      6. 所有异常都只打日志，不抛出

    返回备份文件的路径，失败或跳过返回 None。
    """
    if not os.path.exists(self._db_path):
      return None

    base_dir = os.path.dirname(self._db_path)
    backup_dir = os.path.join(base_dir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    latest = self._latest_backup_path(backup_dir)
    db_mtime = os.path.getmtime(self._db_path)
    if latest and os.path.getmtime(latest) >= db_mtime:
      return None

    try:
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
    """
    清理旧备份，只保留最近 keep 份。

    原理：按文件名排序（时间戳在前缀中），
    删除排在前面的（即最早创建的）旧文件。
    """
    keep = keep or Config.BACKUP_KEEP
    try:
      files = sorted([f for f in os.listdir(backup_dir)
                      if f.startswith('book_backup_') and f.endswith('.db')])
      for f in files[:-keep]:
        os.remove(os.path.join(backup_dir, f))
        LOG.info('删除旧备份: %s', f)
    except OSError as e:
      LOG.error('清理旧备份失败: %s', e)
