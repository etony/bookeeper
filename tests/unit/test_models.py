"""数据模型测试"""
import pytest
from core.models.book import Book

def test_book_creation():
    book = Book(isbn="9787544291163", title="百年孤独")
    assert book.isbn == "9787544291163"
    assert book.title == "百年孤独"
    assert book.status == "默认"

def test_book_to_dict():
    book = Book(isbn="111", title="Test Book")
    data = book.to_dict()
    assert data["isbn"] == "111"
    assert data["title"] == "Test Book"

def test_book_from_dict():
    data = {"isbn": "111", "title": "Test Book", "author": "Author"}
    book = Book.from_dict(data)
    assert book.isbn == "111"
    assert book.title == "Test Book"
    assert book.author == "Author"

def test_book_to_row():
    book = Book(isbn="111", title="Test", author="Author")
    row = book.to_row()
    assert row[0] == "111"
    assert row[1] == "Test"
    assert row[2] == "Author"

def test_book_from_douban():
    douban_data = {
        "isbn13": "9787544291163",
        "title": "百年孤独",
        "author": ["加西亚·马尔克斯"],
        "translator": ["范晔"],
        "publisher": "南海出版公司",
        "price": "CNY 39.50",
        "rating": {"average": "9.2", "numRaters": 12345},
        "images": {"large": "https://example.com/large.jpg"},
        "pubdate": "2011-06",
        "alt": "https://book.douban.com/subject/123",
        "pages": "360",
    }
    
    book = Book.from_douban(douban_data)
    assert book is not None
    assert book.isbn == "9787544291163"
    assert book.title == "百年孤独"
    assert book.author == "加西亚·马尔克斯 译者: 范晔"
    assert book.publisher == "南海出版公司"
    assert book.price == "39.50"
    assert book.rating == "9.2"
    assert book.raters == "12345"
    assert book.cover_url == "https://example.com/large.jpg"
    assert book.pubdate == "2011-06"
    assert book.douban_url == "https://book.douban.com/subject/123"
    assert book.pages == "360"

def test_book_from_douban_invalid():
    # 测试无效数据
    assert Book.from_douban({}) is None
    assert Book.from_douban({"isbn13": "123"}) is None

def test_calc_recommend():
    # 测试推荐度计算
    assert Book._calc_recommend("9.0", "10000") > 0
    assert Book._calc_recommend("2.0", "1000") == 0  # 评分太低
    assert Book._calc_recommend("9.0", "0") == 0  # 人数为0
    assert Book._calc_recommend("", "") == 0  # 空值