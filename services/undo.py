"""
┌──────────────────────────────────────────┐
│  撤销/重做服务                            │
│                                          │
│  基于命令模式的撤销/重做功能，             │
│  支持图书的增删改操作。                    │
└──────────────────────────────────────────┘
"""

from typing import List, Callable
from models.book import Book


class UndoCommand:
  """撤销/重做命令基类"""
  
  def __init__(self, description: str):
    self.description = description
  
  def execute(self):
    raise NotImplementedError
  
  def undo(self):
    raise NotImplementedError


class AddBookCommand(UndoCommand):
  """添加图书命令"""
  
  def __init__(self, repo, book: Book):
    super().__init__(f'添加《{book.title}》')
    self._repo = repo
    self._book = book
  
  def execute(self):
    self._repo.upsert(self._book)
  
  def undo(self):
    self._repo.delete(self._book.isbn)


class DeleteBookCommand(UndoCommand):
  """删除图书命令"""
  
  def __init__(self, repo, book: Book):
    super().__init__(f'删除《{book.title}》')
    self._repo = repo
    self._book = book
  
  def execute(self):
    self._repo.delete(self._book.isbn)
  
  def undo(self):
    self._repo.upsert(self._book)


class UpdateBookCommand(UndoCommand):
  """更新图书命令"""
  
  def __init__(self, repo, old_book: Book, new_book: Book):
    super().__init__(f'更新《{new_book.title}》')
    self._repo = repo
    self._old_book = old_book
    self._new_book = new_book
  
  def execute(self):
    self._repo.upsert(self._new_book)
  
  def undo(self):
    self._repo.upsert(self._old_book)


class UndoManager:
  """撤销/重做管理器"""
  
  def __init__(self, max_history: int = 50):
    self._undo_stack: List[UndoCommand] = []
    self._redo_stack: List[UndoCommand] = []
    self._max_history = max_history
  
  def execute(self, command: UndoCommand):
    """执行命令并加入撤销栈"""
    command.execute()
    self._undo_stack.append(command)
    self._redo_stack.clear()
    
    # 限制历史记录数量
    if len(self._undo_stack) > self._max_history:
      self._undo_stack.pop(0)
  
  def undo(self) -> bool:
    """撤销上一个命令"""
    if not self._undo_stack:
      return False
    
    command = self._undo_stack.pop()
    command.undo()
    self._redo_stack.append(command)
    return True
  
  def redo(self) -> bool:
    """重做上一个撤销的命令"""
    if not self._redo_stack:
      return False
    
    command = self._redo_stack.pop()
    command.execute()
    self._undo_stack.append(command)
    return True
  
  def can_undo(self) -> bool:
    """是否可以撤销"""
    return len(self._undo_stack) > 0
  
  def can_redo(self) -> bool:
    """是否可以重做"""
    return len(self._redo_stack) > 0
  
  def clear(self):
    """清空历史记录"""
    self._undo_stack.clear()
    self._redo_stack.clear()