"""
后台工作线程。

这些 worker 只负责「在独立线程里跑阻塞调用 + 用信号回报」：
  FetchBookWorker — 豆瓣 ISBN 查询
  ImportWorker    — CSV 批量导入

主窗口负责创建线程、连接信号和界面反馈；线程看护见 ui/thread_utils.py。
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class FetchBookWorker(QObject):
  """
  后台查询豆瓣图书的工作线程。

  在独立线程中执行 ISBN 查询，避免 UI 卡死。
  """

  finished = pyqtSignal(object)   # 查询成功，传回 Book 对象
  failed = pyqtSignal(str)        # 查询失败，传回错误消息

  def __init__(self, api, isbn):
    super().__init__()
    self._api = api
    self._isbn = isbn

  def run(self):
    try:
      book = self._api.get_book_by_isbn(self._isbn)
      if book:
        self.finished.emit(book)
      else:
        self.failed.emit(f'未找到图书: {self._isbn}')
    except Exception as e:
      self.failed.emit(str(e))
    finally:
      # 退出线程事件循环，确保线程正常结束
      QThread.currentThread().quit()


class ImportWorker(QObject):
  """
  后台导入 CSV 的工作线程。

  在独立线程中执行 import_df，通过信号汇报进度和结果，
  避免大文件导入时 UI 卡死。
  """

  progress = pyqtSignal(int, int)    # (current, total)
  finished = pyqtSignal(int)         # 导入成功的条数
  failed = pyqtSignal(str)           # 错误消息

  def __init__(self, repo, df):
    super().__init__()
    self._repo = repo
    self._df = df

  def run(self):
    try:
      count = self._repo.import_df(self._df, progress_callback=self._on_progress)
      self.finished.emit(count)
    except Exception as e:
      self.failed.emit(str(e))

  def _on_progress(self, current, total):
    self.progress.emit(current, total)
