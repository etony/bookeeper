"""Repository 测试"""
import os
import tempfile
import pytest
from core.models.book import Book
from core.repositories.book_repo import BookRepository

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    repo = BookRepository(db_path)
    yield repo
    
    os.unlink(db_path)

def test_create_book(temp_db):
    book = Book(isbn="9787544291163", title="百年孤独", author="加西亚·马尔克斯")
    result = temp_db.create(book)
    assert result is True
    
    retrieved = temp_db.get_by_id("9787544291163")
    assert retrieved is not None
    assert retrieved.title == "百年孤独"

def test_get_all_books(temp_db):
    book1 = Book(isbn="111", title="Book 1")
    book2 = Book(isbn="222", title="Book 2")
    
    temp_db.create(book1)
    temp_db.create(book2)
    
    books = temp_db.get_all()
    assert len(books) == 2

def test_update_book(temp_db):
    book = Book(isbn="111", title="Original Title")
    temp_db.create(book)
    
    book.title = "Updated Title"
    temp_db.update(book)
    
    retrieved = temp_db.get_by_id("111")
    assert retrieved.title == "Updated Title"

def test_delete_book(temp_db):
    book = Book(isbn="111", title="To Delete")
    temp_db.create(book)
    
    result = temp_db.delete("111")
    assert result is True
    
    retrieved = temp_db.get_by_id("111")
    assert retrieved is None

def test_upsert_book(temp_db):
    book = Book(isbn="111", title="Original")
    temp_db.create(book)
    
    book.title = "Updated"
    temp_db.upsert(book)
    
    retrieved = temp_db.get_by_id("111")
    assert retrieved.title == "Updated"

def test_search_books(temp_db):
    book1 = Book(isbn="111", title="Python Programming")
    book2 = Book(isbn="222", title="Java Programming")
    book3 = Book(isbn="333", title="Python Cookbook", status="已读")
    
    temp_db.create(book1)
    temp_db.create(book2)
    temp_db.create(book3)
    
    # 按关键词搜索
    results = temp_db.search(keyword="Python")
    assert len(results) == 2
    
    # 按状态搜索
    results = temp_db.search(status="已读")
    assert len(results) == 1
    
    # 组合搜索
    results = temp_db.search(keyword="Python", status="已读")
    assert len(results) == 1

def test_count_books(temp_db):
    assert temp_db.count() == 0
    
    book = Book(isbn="111", title="Test")
    temp_db.create(book)
    
    assert temp_db.count() == 1

def test_status_counts(temp_db):
    book1 = Book(isbn="111", title="Book 1", status="默认")
    book2 = Book(isbn="222", title="Book 2", status="已读")
    book3 = Book(isbn="333", title="Book 3", status="已读")
    
    temp_db.create(book1)
    temp_db.create(book2)
    temp_db.create(book3)
    
    counts = temp_db.status_counts()
    assert counts["默认"] == 1
    assert counts["已读"] == 2