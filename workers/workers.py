# -*- coding: utf-8 -*-
"""
workers — 后台工作线程模块

本模块实现所有在后台线程中执行的任务类，基于 PyQt6 的 QObject + moveToThread
设计模式。核心思路是将耗时操作（如网络 API 调用）放入独立线程，避免阻塞 GUI。

模块结构：
  - BaseBatchWorker: 抽象基类，封装「取消标志」和通用信号 finished
  - RefreshWorker:   批量刷新图书基本信息，每完成一本发射 progress(Book)
  - ExportWorker:    批量导出图书完整信息，同时发射进度和结果

设计模式说明（QObject + moveToThread）：
  QObject 本身不是线程，但它可以通过 moveToThread() 被迁移到某个 QThread
  实例中运行。将 Worker 对象 moveToThread(thread) 后，Worker 上的槽函数
  就会在该线程中执行。这种方式比继承 QThread 更灵活，且能安全使用信号/槽。
"""

import time

from PyQt6.QtCore import QObject, pyqtSignal

from config import Config
from services.douban_api import DoubanService


class BaseBatchWorker(QObject):
  """
  带取消标志的批量任务基类

  继承 QObject 使其支持信号/槽机制，配合 moveToThread() 可将实例
  迁移到独立线程中执行 run()。子类需实现 run() 方法并在其中定期检查
  self._cancel 以支持安全中断。

  设计意图：
    - 将「可取消性」抽象到基类，所有批量 Worker 复用同一套取消逻辑
    - finished 信号作为通用完成通知，子类可叠加自定义信号
    - 取消操作是幂等的，多次调用 cancel() 无害

  注意事项：
    - cancel() 只是设置标志位，不会立刻终止正在执行的 API 请求
    - 子类 run() 中每次循环都应检查 cancel 标志，否则取消不生效
    - 不要直接调用 run()，应通过 thread.started.connect(worker.run) 触发
  """
  finished = pyqtSignal()  # 任务完成信号（正常完成或被取消后都会发射）

  def __init__(self, isbn_list: list):
    """
    初始化批量任务

    参数:
      isbn_list: list[str] — 待处理的 ISBN 编号列表，调用方需保证列表不为空
    """
    super().__init__()
    self._isbn_list = isbn_list  # 待处理的 ISBN 列表
    self._cancel = False         # 取消标志，初始为 False；设置 True 后下次循环退出

  def cancel(self):
    """
    请求取消当前任务

    这是一个线程安全的方法，仅设置一个布尔标志。不会等待正在执行的 API
    调用完成，也不会中断正在休眠的 time.sleep()。子类 run() 在每次循环
    开始处检查该标志，发现为 True 则跳出循环并发射 finished 信号。

    使用方式（在主线程调用）：
      worker.cancel()        # 设置取消标志
      thread.quit()          # 通知事件循环退出
      thread.wait()          # 等待线程真正结束
    """
    self._cancel = True


class RefreshWorker(BaseBatchWorker):
  """
  批量刷新图书基本信息

  工作流程：
    1. 遍历 ISBN 列表，逐个调用豆瓣 API 获取图书基本信息
    2. 每成功获取一本，通过 progress 信号将 Book 对象发送到主线程
    3. 每次请求后休眠 Config.API_REQUEST_DELAY 秒，遵守 API 频率限制
    4. 全部处理完成或被取消后发射 finished 信号

  信号传递方式：
    - progress(Book): 每本成功获取的图书会立即发射，主线程收到后更新界面
    - finished():     全部完成或取消后发射，主线程收到后恢复 UI 状态

  与 ExportWorker 的区别：
    RefreshWorker 只获取基本信息（一次 API 调用/本），适合快速刷新列表；
    ExportWorker 会调用更详细的 API 接口获取完整内容。
  """
  progress = pyqtSignal(object)  # Book，每完成一本图书的刷新时发射

  def run(self):
    """
    执行批量刷新（此方法通过 thread.started.connect 在子线程中调用）

    注意：
      - 每次 API 调用后主动休眠，防止触发豆瓣 API 限流
      - 如果某 ISBN 在豆瓣中不存在，get_book_by_isbn 返回 None，
        不会发射 progress 信号（静默跳过）
      - 中途取消时仍会执行一次 time.sleep，因为 break 在 sleep 之后
    """
    api = DoubanService()                          # 每个线程创建独立的 API 客户端实例
    for isbn in self._isbn_list:                   # 遍历待处理的 ISBN 列表
      if self._cancel:                             # 检查取消标志，支持外部中断
        break                                      # 用户取消则立即终止循环
      book = api.get_book_by_isbn(isbn)            # 调用豆瓣 API 获取图书基本信息
      if book:                                     # 仅在 API 返回有效数据时
        self.progress.emit(book)                   # 通过信号将 Book 对象发往主线程
      time.sleep(Config.API_REQUEST_DELAY)         # 请求间隔，避免触发 API 限流
    self.finished.emit()                           # 通知主线程任务已结束


class ExportWorker(BaseBatchWorker):
  """
  批量导出图书完整信息（用于生成报告/文件）

  工作流程：
    1. 遍历 ISBN 列表，逐个调用豆瓣 API 获取完整图书信息
    2. 每成功获取一本，通过 result_ready 信号发送 Book 对象供写入文件
    3. 每次请求后更新进度 progress(i+1, total)，主线程借此显示进度条
    4. 全部处理完成或被取消后发射 finished 信号

  信号传递方式：
    - result_ready(Book):  每本有效图书的数据，主线程收到后追加到导出内容中
    - progress(current, total): 当前进度（从 1 开始），主线程更新进度条
    - finished():          全部完成或取消后发射

  与 RefreshWorker 的区别：
    ExportWorker 额外发射进度信号 (int, int)，因为导出操作通常需要
    向用户展示进度百分比。RefreshWorker 只发射 Book，由接收方自行计数。
  """
  result_ready = pyqtSignal(object)  # Book，每本有效图书的完整数据，供写入导出文件
  progress = pyqtSignal(int, int)    # (当前处理序号, 总数)，用于更新进度条

  def run(self):
    """
    执行批量导出（此方法通过 thread.started.connect 在子线程中调用）

    注意：
      - result_ready 先发射，然后才发射 progress，保证数据在进度更新前送达
      - progress 的当前值从 1 开始，与人类直观的「第 1 本 / 共 N 本」一致
      - 即使某 ISBN 返回 None（豆瓣无记录），进度仍然会推进，不会卡住
      - 取消时同样会执行一次 time.sleep，这是正常的容忍行为
    """
    api = DoubanService()                          # 每个线程创建独立的 API 客户端实例
    total = len(self._isbn_list)                   # 总任务量，用于进度计算
    for i, isbn in enumerate(self._isbn_list):     # i 从 0 开始，i+1 用于展示
      if self._cancel:                             # 检查取消标志
        break                                      # 用户取消则终止循环
      book = api.get_book_by_isbn(isbn)            # 调用豆瓣 API 获取图书完整信息
      if book:                                     # 仅在 API 返回有效数据时
        self.result_ready.emit(book)               # 发射图书数据供主线程写入导出文件
      self.progress.emit(i + 1, total)             # 更新进度 (第几本, 共几本)
      time.sleep(Config.API_REQUEST_DELAY)         # 请求间隔，避免触发 API 限流
    self.finished.emit()                           # 通知主线程任务已结束
