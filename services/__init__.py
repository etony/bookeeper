from database import BookRepo as _BookRepo

# 全局共享的 BookRepo 单例，避免各模块重复创建
_repo = None


def get_repo() -> _BookRepo:
  """获取全局唯一的 BookRepo 实例"""
  global _repo
  if _repo is None:
    _repo = _BookRepo()
  return _repo
