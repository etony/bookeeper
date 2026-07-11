"""
┌──────────────────────────────────────────┐
│  服务模块                                │
│                                          │
│  提供全局共享的 BookRepo 单例，           │
│  避免数据库连接在各模块间重复创建。        │
└──────────────────────────────────────────┘
"""

from database import BookRepo as _BookRepo

# 全局唯一的 BookRepo 实例（惰性初始化，首次调用 get_repo() 时才创建）
_repo = None


def get_repo() -> _BookRepo:
  """
  获取全局共享的 BookRepo 实例。

  为什么用单例？
    多个界面组件（主窗口、详情对话框等）
    需要访问同一个数据库，各自创建连接会导致数据不一致。
  此函数保证整个应用生命周期内只有一份 BookRepo。
  """
  global _repo
  if _repo is None:
    _repo = _BookRepo()
  return _repo
