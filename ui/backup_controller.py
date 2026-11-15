"""
自动备份控制器（从 ui/main_window.py 拆出）。

职责：
  - 定时器（默认每 5 分钟）触发备份
  - dirty 标记：数据变更后置位，备份成功才清除
  - 失败可感知：把原因通过 failed 信号交给界面显示

为什么要拆：主窗口原先混了 9 类职责；备份的「失败必须保留 dirty 并提示」
是独立且容易写错的一段逻辑，单独放一处便于测试。
"""

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import Config
from services.backup import BackupService


class BackupController(QObject):
  """
  定时自动备份。

  信号：
    failed(str) — 备份失败的原因（界面用状态栏提示）
  """

  failed = pyqtSignal(str)

  def __init__(self, service=None, parent=None, interval_ms=None):
    super().__init__(parent)
    self.service = service or BackupService()
    self._dirty = False
    self._interval_ms = interval_ms or Config.BACKUP_INTERVAL_MS
    self._timer = QTimer(self)
    self._timer.timeout.connect(self.request_backup)

  # ── dirty 标记 ──────────────────────────────────

  @property
  def dirty(self) -> bool:
    return self._dirty

  @dirty.setter
  def dirty(self, value: bool):
    self._dirty = bool(value)

  def mark_dirty(self):
    """标记数据已变更，下次定时器触发时执行备份"""
    self._dirty = True

  # ── 定时器 ──────────────────────────────────────

  def start(self):
    self._timer.start(self._interval_ms)

  def stop(self):
    self._timer.stop()

  # ── 备份执行 ────────────────────────────────────

  def request_backup(self):
    """定时器入口：数据无变更则跳过（backup 内部还有 mtime 去重）"""
    if not self._dirty:
      return
    # 推迟到下一轮事件循环执行，避免在定时器回调里做 IO
    QTimer.singleShot(0, self.run_backup)

  def run_backup(self) -> bool:
    """
    实际执行备份。

    只有成功才清 dirty 标记：失败时保留标记，下一轮定时器会重试，
    同时通过 failed 信号提示用户——不能只写日志，否则数据可能永远没有备份。
    """
    self.service.backup()
    if self.service.last_error:
      self.failed.emit(
        f'自动备份失败：{self.service.last_error}（数据未备份，稍后自动重试）')
      return False
    self._dirty = False
    return True

  def backup_now(self) -> bool:
    """关闭窗口时无条件备份（backup 内部按 mtime 去重，不会产生冗余文件）"""
    self.service.backup()
    if self.service.last_error:
      self.failed.emit(f'备份失败：{self.service.last_error}')
      return False
    return True
