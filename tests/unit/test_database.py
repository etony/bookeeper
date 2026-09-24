"""数据库 Repository 测试"""
import tempfile
import os
import pytest

from database import BookRepo
from core.models.book import Book


@pytest.fixture
def repo():
  """创建使用临时文件的 BookRepo 实例"""
  with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db_path = f.name
  r = BookRepo(db_path)
  yield r
  os.unlink(db_path)


@pytest.fixture
def sample_book():
  """示例图书"""
  return Book(
    isbn='9787544291163',
    title='百年孤独',
    author='加西亚·马尔克斯',
    publisher='南海出版公司',
    price='39.50',
    rating='9.2',
    status='默认',
  )


@pytest.fixture
def second_book():
  """第二个示例图书"""
  return Book(
    isbn='9787530217337',
    title='活着',
    author='余华',
    publisher='北京十月文艺出版社',
    price='29.00',
    rating='9.4',
    status='已读',
  )


# ── 创建 / 插入 ──────────────────────────────────────


def test_upsert_inserts_new_book(repo, sample_book):
  """新书插入"""
  assert repo.count() == 0
  repo.upsert(sample_book)
  assert repo.count() == 1
  result = repo.get_by_isbn(sample_book.isbn)
  assert result is not None
  assert result.title == '百年孤独'
  assert result.author == '加西亚·马尔克斯'


def test_upsert_updates_existing_book(repo, sample_book):
  """已存在的书更新"""
  repo.upsert(sample_book)
  # 修改后再次 upsert
  updated = Book(isbn=sample_book.isbn, title='百年孤独（修订版）', author='新作者')
  repo.upsert(updated)
  assert repo.count() == 1
  result = repo.get_by_isbn(sample_book.isbn)
  assert result.title == '百年孤独（修订版）'
  assert result.author == '新作者'


# ── 读取 ──────────────────────────────────────────────


def test_get_all_empty(repo):
  """空库返回空列表"""
  assert repo.get_all() == []


def test_get_all_sorted_by_title(repo, sample_book, second_book):
  """按书名排序"""
  repo.upsert(second_book)
  repo.upsert(sample_book)
  all_books = repo.get_all()
  assert len(all_books) == 2
  # 按 title 排序，两个书名不同即可验证已排序
  titles = [b.title for b in all_books]
  assert titles == sorted(titles)


def test_get_by_isbn_found(repo, sample_book):
  """按 ISBN 查询——存在"""
  repo.upsert(sample_book)
  result = repo.get_by_isbn(sample_book.isbn)
  assert result is not None
  assert result.isbn == sample_book.isbn


def test_get_by_isbn_not_found(repo):
  """按 ISBN 查询——不存在"""
  result = repo.get_by_isbn('0000000000000')
  assert result is None


# ── 删除 ──────────────────────────────────────────────


def test_delete_existing(repo, sample_book):
  """删除已存在的书"""
  repo.upsert(sample_book)
  assert repo.delete(sample_book.isbn) is True
  assert repo.count() == 0
  assert repo.get_by_isbn(sample_book.isbn) is None


def test_delete_nonexistent(repo):
  """删除不存在的 ISBN"""
  assert repo.delete('0000000000000') is False


# ── 搜索 ──────────────────────────────────────────────


def test_search_by_title(repo, sample_book):
  """按书名搜索"""
  repo.upsert(sample_book)
  results = repo.search(keyword='百年')
  assert len(results) == 1
  assert results[0].isbn == sample_book.isbn


def test_search_by_author(repo, sample_book):
  """按作者搜索"""
  repo.upsert(sample_book)
  results = repo.search(keyword='马尔克斯')
  assert len(results) == 1


def test_search_by_status(repo, sample_book, second_book):
  """按状态搜索"""
  repo.upsert(sample_book)
  repo.upsert(second_book)
  results = repo.search(status='已读')
  assert len(results) == 1
  assert results[0].isbn == second_book.isbn


def test_search_combined(repo, sample_book, second_book):
  """组合搜索"""
  repo.upsert(sample_book)
  repo.upsert(second_book)
  results = repo.search(keyword='余华', status='已读')
  assert len(results) == 1
  assert results[0].isbn == second_book.isbn


def test_search_no_match(repo, sample_book):
  """搜索无匹配"""
  repo.upsert(sample_book)
  results = repo.search(keyword='不存在的书名')
  assert len(results) == 0


# ── 统计 ──────────────────────────────────────────────


def test_count_empty(repo):
  """空库计数"""
  assert repo.count() == 0


def test_count_with_books(repo, sample_book, second_book):
  """有书时计数"""
  repo.upsert(sample_book)
  repo.upsert(second_book)
  assert repo.count() == 2


def test_count_with_filter(repo, sample_book, second_book):
  """带条件计数"""
  repo.upsert(sample_book)
  repo.upsert(second_book)
  assert repo.count(status='已读') == 1
  assert repo.count(status='默认') == 1


def test_status_counts(repo, sample_book, second_book):
  """各状态数量统计"""
  repo.upsert(sample_book)
  repo.upsert(second_book)
  counts = repo.status_counts()
  assert counts == {'默认': 1, '已读': 1}
