"""
QThread 生命周期看护（全应用唯一实现）。

为什么需要这个模块？
  运行中的 QThread 一旦被 Python GC 回收，Qt 会直接 abort 整个进程
  （Windows 退出码 0xC0000409）。所以「请求停止但 wait() 超时」的线程
  不能丢引用，必须先放进看护列表保活，等它自然结束后再清理。

  也不能用 finished → deleteLater：C++ 对象销毁后 Python 包装器仍存活，
  下次调 isRunning() 会抛 RuntimeError。

  原先 main_window / detail_dialog / web_manager 各写了一份同样的逻辑，
  现在共用这里的 RETIRED 列表。
"""

# 已请求停止但可能仍在运行的线程：(thread, worker)。
# worker 一起保活——信号连接依赖它，丢了可能让线程回调打到已释放对象。
RETIRED = []


def is_running(thread) -> bool:
  """线程是否仍在运行（C++ 对象已销毁视为已结束）"""
  try:
    return thread.isRunning()
  except RuntimeError:
    return False


def prune_retired():
  """丢弃已经结束的线程引用"""
  RETIRED[:] = [item for item in RETIRED if is_running(item[0])]


def retire(thread, worker=None):
  """把线程引用交给看护列表保活，并顺带清理已结束的"""
  RETIRED.append((thread, worker))
  prune_retired()
