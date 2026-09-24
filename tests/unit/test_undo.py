"""撤销服务测试"""
import tempfile
import os
import pytest

from database import BookRepo
from core.models.book import Book
from services.undo import (
  UndoManager,
  AddBookCommand,
  DeleteBookCommand,
  UpdateBookCommand,
)


@pytest.fixture
def repo():
  """创建使用临时文件的 BookRepo"""
  with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db_path = f.name
  r = BookRepo(db_path)
  yield r
  os.unlink(db_path)


@pytest.fixture
def manager():
  """创建 UndoManager"""
  return UndoManager()


@pytest.fixture
def book():
  """示例图书"""
  return Book(isbn='9787544291163', title='百年孤独', author='马尔克斯')


@pytest.fixture
def book2():
  """第二个示例图书"""
  return Book(isbn='9787530217337', title='活着', author='余华')


# ── 初始化 ──────────────────────────────────────────


def test_manager_init(manager):
  """UndoManager 初始化"""
  assert manager.can_undo() is False
  assert manager.can_redo() is False


def test_manager_init_custom_max_history():
  """自定义最大历史记录数"""
  m = UndoManager(max_history=5)
  assert m._max_history == 5


# ── 添加图书命令 ────────────────────────────────────


def test_add_book_command(manager, repo, book):
  """添加图书命令"""
  cmd = AddBookCommand(repo, book)
  manager.execute(cmd)
  assert repo.count() == 1
  assert repo.get_by_isbn(book.isbn) is not None
  assert manager.can_undo() is True


def test_add_book_undo(manager, repo, book):
  """撤销添加图书"""
  cmd = AddBookCommand(repo, book)
  manager.execute(cmd)
  assert repo.count() == 1
  manager.undo()
  assert repo.count() == 0
  assert repo.get_by_isbn(book.isbn) is None
  assert manager.can_redo() is True


def test_add_book_redo(manager, repo, book):
  """重做添加图书"""
  cmd = AddBookCommand(repo, book)
  manager.execute(cmd)
  manager.undo()
  assert repo.count() == 0
  manager.redo()
  assert repo.count() == 1
  assert repo.get_by_isbn(book.isbn) is not None


# ── 删除图书命令 ────────────────────────────────────


def test_delete_book_command(manager, repo, book):
  """删除图书命令"""
  repo.upsert(book)
  cmd = DeleteBookCommand(repo, book)
  manager.execute(cmd)
  assert repo.count() == 0
  assert repo.get_by_isbn(book.isbn) is None


def test_delete_book_undo(manager, repo, book):
  """撤销删除图书"""
  repo.upsert(book)
  cmd = DeleteBookCommand(repo, book)
  manager.execute(cmd)
  assert repo.count() == 0
  manager.undo()
  assert repo.count() == 1
  restored = repo.get_by_isbn(book.isbn)
  assert restored is not None
  assert restored.title == '百年孤独'


# ── 更新图书命令 ────────────────────────────────────


def test_update_book_command(manager, repo, book):
  """更新图书命令"""
  repo.upsert(book)
  updated = Book(isbn=book.isbn, title='百年孤独（修订版）', author='新作者')
  cmd = UpdateBookCommand(repo, book, updated)
  manager.execute(cmd)
  result = repo.get_by_isbn(book.isbn)
  assert result.title == '百年孤独（修订版）'


def test_update_book_undo(manager, repo, book):
  """撤销更新图书"""
  repo.upsert(book)
  updated = Book(isbn=book.isbn, title='百年孤独（修订版）')
  cmd = UpdateBookCommand(repo, book, updated)
  manager.execute(cmd)
  manager.undo()
  result = repo.get_by_isbn(book.isbn)
  assert result.title == '百年孤独'
  assert result.author == '马尔克斯'


# ── 撤销 / 重做边界 ────────────────────────────────


def test_undo_empty_stack(manager):
  """空撤销栈返回 False"""
  assert manager.undo() is False


def test_redo_empty_stack(manager):
  """空重做栈返回 False"""
  assert manager.redo() is False


def test_new_command_clears_redo(manager, repo, book, book2):
  """执行新命令清空重做栈"""
  cmd1 = AddBookCommand(repo, book)
  manager.execute(cmd1)
  manager.undo()
  assert manager.can_redo() is True
  cmd2 = AddBookCommand(repo, book2)
  manager.execute(cmd2)
  assert manager.can_redo() is False


# ── 清空历史 ────────────────────────────────────────


def test_clear(manager, repo, book, book2):
  """清空撤销和重做栈"""
  cmd1 = AddBookCommand(repo, book)
  cmd2 = AddBookCommand(repo, book2)
  manager.execute(cmd1)
  manager.execute(cmd2)
  # 此时 undo_stack: [cmd1, cmd2], redo_stack: []
  manager.undo()
  # undo_stack: [cmd1], redo_stack: [cmd2]
  assert manager.can_undo() is True
  assert manager.can_redo() is True
  manager.clear()
  assert manager.can_undo() is False
  assert manager.can_redo() is False


# ── 最大历史限制 ────────────────────────────────────


def test_max_history_limit():
  """超过最大历史记录数时丢弃最早的"""
  m = UndoManager(max_history=3)
  books = [Book(isbn=f'isbn{i}', title=f'Book{i}') for i in range(5)]

  # 模拟执行 5 次（不真正操作数据库，直接操作栈）
  for b in books:
    cmd = AddBookCommand(None, b)
    cmd.execute = lambda: None  # 跳过实际执行
    cmd.undo = lambda: None
    m.execute(cmd)

  # 只保留最近 3 条
  assert len(m._undo_stack) == 3
  # 最早的 2 条被丢弃
  assert m._undo_stack[0]._book.isbn == 'isbn2'


# ── 命令描述 ────────────────────────────────────────


def test_command_descriptions(manager, repo, book, book2):
  """命令描述包含书名"""
  add_cmd = AddBookCommand(repo, book)
  assert '百年孤独' in add_cmd.description

  repo.upsert(book)
  del_cmd = DeleteBookCommand(repo, book)
  assert '百年孤独' in del_cmd.description

  repo.upsert(book2)
  upd_cmd = UpdateBookCommand(repo, book, book2)
  assert '活着' in upd_cmd.description
