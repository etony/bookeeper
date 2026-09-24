"""数据库 Repository 测试"""
import tempfile
import os
import pytest

from database import BookRepo
from core.models.book import Book


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


def test_get_all_newest_first(repo, sample_book, second_book):
  """新记录在最前（按 rowid 倒序）"""
  repo.upsert(second_book)
  repo.upsert(sample_book)
  all_books = repo.get_all()
  assert len(all_books) == 2
  # 新插入的 sample_book 应在最前
  assert all_books[0].isbn == sample_book.isbn
  assert all_books[1].isbn == second_book.isbn


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


# ── 出版社/评分统计 ────────────────────────────────────


def test_publisher_top(repo, sample_book, second_book):
  """出版社 TOP N"""
  repo.upsert(sample_book)
  repo.upsert(second_book)
  top = repo.publisher_top(10)
  assert len(top) == 2
  publishers = [p for p, _ in top]
  assert '南海出版公司' in publishers
  assert '北京十月文艺出版社' in publishers


def test_publisher_top_empty(repo):
  """空库时出版社统计为空"""
  assert repo.publisher_top() == []


def test_publisher_top_limit(repo):
  """出版社 TOP N 限制数量"""
  for i in range(5):
    book = Book(isbn=f'isbn{i}', title=f'Book{i}', publisher=f'出版社{i}')
    repo.upsert(book)
  top = repo.publisher_top(3)
  assert len(top) == 3


def test_publisher_top_skips_empty(repo):
  """空出版社不参与统计"""
  book_empty = Book(isbn='isbn0', title='No Publisher', publisher='')
  book_ok = Book(isbn='isbn1', title='Has Publisher', publisher='出版社A')
  repo.upsert(book_empty)
  repo.upsert(book_ok)
  top = repo.publisher_top()
  assert len(top) == 1
  assert top[0] == ('出版社A', 1)


def test_rating_distribution(repo):
  """评分分布统计"""
  books = [
    Book(isbn='isbn1', title='B1', rating='5.0'),
    Book(isbn='isbn2', title='B2', rating='6.5'),
    Book(isbn='isbn3', title='B3', rating='7.5'),
    Book(isbn='isbn4', title='B4', rating='8.5'),
    Book(isbn='isbn5', title='B5', rating='9.5'),
  ]
  for b in books:
    repo.upsert(b)
  dist = repo.rating_distribution()
  assert dist['0-6'] == 1
  assert dist['6-7'] == 1
  assert dist['7-8'] == 1
  assert dist['8-9'] == 1
  assert dist['9-10'] == 1


def test_rating_distribution_empty(repo):
  """空库时评分布全为 0"""
  dist = repo.rating_distribution()
  assert all(v == 0 for v in dist.values())


def test_rating_distribution_skips_zero_and_empty(repo):
  """排除空评分和 0 评分"""
  repo.upsert(Book(isbn='isbn1', title='B1', rating='0'))
  repo.upsert(Book(isbn='isbn2', title='B2', rating=''))
  repo.upsert(Book(isbn='isbn3', title='B3', rating='8.0'))
  dist = repo.rating_distribution()
  assert dist['8-9'] == 1
  assert sum(dist.values()) == 1
