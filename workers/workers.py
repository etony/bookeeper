# -*- coding: utf-8 -*-
"""后台工作线程"""

import time

from PyQt6.QtCore import QObject, pyqtSignal

from config import Config
from services.douban_api import DoubanService


class BaseBatchWorker(QObject):
  """带取消标志的批量任务基类"""
  finished = pyqtSignal()

  def __init__(self, isbn_list: list):
    super().__init__()
    self._isbn_list = isbn_list
    self._cancel = False

  def cancel(self):
    self._cancel = True


class RefreshWorker(BaseBatchWorker):
  """批量刷新图书信息"""
  progress = pyqtSignal(object)  # Book

  def run(self):
    api = DoubanService()
    for isbn in self._isbn_list:
      if self._cancel:
        break
      book = api.get_book_by_isbn(isbn)
      if book:
        self.progress.emit(book)
      time.sleep(Config.API_REQUEST_DELAY)
    self.finished.emit()


class ExportWorker(BaseBatchWorker):
  """批量导出图书完整信息"""
  result_ready = pyqtSignal(object)  # Book
  progress = pyqtSignal(int, int)

  def run(self):
    api = DoubanService()
    total = len(self._isbn_list)
    for i, isbn in enumerate(self._isbn_list):
      if self._cancel:
        break
      book = api.get_book_by_isbn(isbn)
      if book:
        self.result_ready.emit(book)
      self.progress.emit(i + 1, total)
      time.sleep(Config.API_REQUEST_DELAY)
    self.finished.emit()
