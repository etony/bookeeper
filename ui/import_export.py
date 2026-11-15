"""
CSV 导入导出控制器（从 ui/main_window.py 拆出）。

导入：文件对话框 → 主线程读 CSV（快）→ 后台线程写库 + 进度条。
导出：主线程读全量数据 → 写文件。

主窗口只负责接信号：导入成功后标脏、刷新表格、更新文件标签。
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

from ui.thread_utils import retire
from ui.workers import ImportWorker


class CsvController(QObject):
  """
  CSV 导入导出的界面协调。

  信号：
    imported(int)      — 导入完成，携带处理的条数
    exported(str)      — 导出完成，携带文件路径
    busy_changed(bool) — 导入期间禁用/恢复导入按钮
  """

  imported = pyqtSignal(int)
  exported = pyqtSignal(str)
  busy_changed = pyqtSignal(bool)

  def __init__(self, repo, parent=None):
    super().__init__(parent)
    self._repo = repo
    self._parent = parent
    self._thread = None
    self._worker = None
    self._progress = None

  # ══════════════════════════════════════════════
  #  导入
  # ══════════════════════════════════════════════

  def import_csv(self):
    """选择 CSV 文件并异步导入数据库"""
    path, _ = QFileDialog.getOpenFileName(
      self._parent, '加载 CSV', '.', 'CSV 文件 (*.csv)')
    if not path:
      return
    try:
      from services.data import load_csv
      df = load_csv(path)
    except Exception as e:
      QMessageBox.warning(
        self._parent, '导入失败',
        f'无法读取 CSV 文件：\n{e}\n\n'
        f'请确认文件格式正确（UTF-8 编码），或选择其他文件。')
      return

    self.busy_changed.emit(True)
    self._progress = QProgressDialog(
      '正在导入 CSV...', None, 0, len(df), self._parent)
    self._progress.setWindowTitle('导入中')
    self._progress.setMinimumDuration(0)
    self._progress.show()

    self._thread = QThread()
    self._worker = ImportWorker(self._repo, df)
    self._worker.moveToThread(self._thread)
    self._thread.started.connect(self._worker.run)
    self._worker.progress.connect(self._on_progress)
    self._worker.finished.connect(self._on_finished)
    self._worker.failed.connect(self._on_failed)
    self._thread.start()

  def _on_progress(self, current, total):
    if self._progress and not self._progress.wasCanceled():
      self._progress.setValue(current)

  def _on_finished(self, count):
    self._close_progress()
    self._stop_thread()
    self.busy_changed.emit(False)
    self.imported.emit(count)
    QMessageBox.information(
      self._parent, '提示', f'导入完成，共处理 {count} 条记录')

  def _on_failed(self, msg):
    self._close_progress()
    self._stop_thread()
    self.busy_changed.emit(False)
    QMessageBox.warning(self._parent, '错误', f'导入失败: {msg}')

  def _close_progress(self):
    if self._progress:
      self._progress.close()
      self._progress = None

  def _stop_thread(self):
    """退出导入线程；wait() 超时的线程交给看护列表保活"""
    thread, worker = self._thread, self._worker
    self._thread = None
    self._worker = None
    if thread is None:
      return
    thread.quit()
    if not thread.wait(3000):
      retire(thread, worker)

  # ══════════════════════════════════════════════
  #  导出
  # ══════════════════════════════════════════════

  def export_csv(self):
    """导出全部数据为 CSV 文件"""
    path, _ = QFileDialog.getSaveFileName(
      self._parent, '保存 CSV', '.', 'CSV 文件 (*.csv)')
    if not path:
      return
    try:
      df = self._repo.export_df()
      from services.data import save_csv
      save_csv(path, df)
      QMessageBox.information(self._parent, '导出成功', 'CSV 文件已保存。')
      self.exported.emit(path)
    except Exception as e:
      QMessageBox.warning(
        self._parent, '导出失败',
        f'无法保存 CSV 文件：\n{e}\n\n'
        f'请检查文件路径是否可写，或选择其他位置。')
