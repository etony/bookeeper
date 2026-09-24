"""服务测试"""
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from core.services.douban import DoubanService, _request_with_retry


def test_request_with_retry_success():
    mock_session = Mock()
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_session.request.return_value = mock_response
    
    result = _request_with_retry("GET", "http://test.com", mock_session)
    assert result == mock_response
    assert mock_session.request.call_count == 1

def test_request_with_retry_failure():
    mock_session = Mock()
    mock_session.request.side_effect = requests.RequestException("网络错误")
    
    result = _request_with_retry("GET", "http://test.com", mock_session)
    assert result is None
    assert mock_session.request.call_count == 3

@patch('core.services.douban.get_config')
def test_douban_service_init(mock_get_config):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    service = DoubanService()
    assert service._session is not None
    assert "User-Agent" in service._session.headers
    assert service._api_key == "test_api_key"
    assert service._api_key_search == "test_search_key"

@patch('core.services.douban.get_config')
def test_douban_service_get_book_by_isbn_invalid(mock_get_config):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    service = DoubanService()
    
    assert service.get_book_by_isbn("") is None
    assert service.get_book_by_isbn("123") is None  # 长度不对

@patch('core.services.douban._request_with_retry')
@patch('core.services.douban.get_config')
def test_douban_service_get_book_by_isbn_success(mock_get_config, mock_request):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "isbn13": "9787111636663",
        "title": "深入理解计算机系统",
        "author": ["Randal E. Bryant"],
        "translator": [],
        "publisher": "机械工业出版社",
        "price": "139",
        "rating": {"average": "9.7", "numRaters": 12345},
        "images": {"large": "https://img.example.com/large.jpg"},
        "pubdate": "2016-11-01",
        "alt": "https://book.douban.com/subject/26402407/",
        "pages": "737"
    }
    mock_request.return_value = mock_response
    
    service = DoubanService()
    book = service.get_book_by_isbn("9787111636663")
    
    assert book is not None
    assert book.isbn == "9787111636663"
    assert book.title == "深入理解计算机系统"
    assert book.author == "Randal E. Bryant"

@patch('core.services.douban._request_with_retry')
@patch('core.services.douban.get_config')
def test_douban_service_get_book_by_isbn_empty_response(mock_get_config, mock_request):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    mock_request.return_value = None
    
    service = DoubanService()
    book = service.get_book_by_isbn("9787111636663")
    
    assert book is None

@patch('core.services.douban.get_config')
def test_douban_service_search_books_empty_keyword(mock_get_config):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    service = DoubanService()
    assert service.search_books("") == []
    assert service.search_books(None) == []

@patch('core.services.douban._request_with_retry')
@patch('core.services.douban.get_config')
def test_douban_service_search_books_success(mock_get_config, mock_request):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "books": [
            {
                "isbn13": "9787111636663",
                "title": "深入理解计算机系统",
                "author": ["Randal E. Bryant"],
                "publisher": "机械工业出版社",
                "price": "139",
                "rating": {"average": "9.7", "numRaters": 12345},
                "images": {},
                "pubdate": "2016-11-01",
                "alt": "https://book.douban.com/subject/26402407/",
                "pages": "737"
            },
            {
                "isbn13": "9787115546081",
                "title": "Python编程：从入门到实践",
                "author": ["Eric Matthes"],
                "publisher": "人民邮电出版社",
                "price": "89",
                "rating": {"average": "9.2", "numRaters": 8765},
                "images": {},
                "pubdate": "2020-07-01",
                "alt": "https://book.douban.com/subject/35444622/",
                "pages": "456"
            }
        ],
        "total": 2
    }
    mock_request.return_value = mock_response
    
    service = DoubanService()
    books = service.search_books("计算机")
    
    assert len(books) == 2
    assert books[0].title == "深入理解计算机系统"
    assert books[1].title == "Python编程：从入门到实践"

@patch('core.services.douban._request_with_retry')
@patch('core.services.douban.get_config')
def test_douban_service_search_books_empty_response(mock_get_config, mock_request):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    mock_request.return_value = None
    
    service = DoubanService()
    books = service.search_books("计算机")
    
    assert books == []

@patch('core.services.douban.get_config')
def test_douban_service_download_image_empty_url(mock_get_config):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    service = DoubanService()
    assert service.download_image("") is None
    assert service.download_image(None) is None

@patch('core.services.douban._request_with_retry')
@patch('core.services.douban.get_config')
def test_douban_service_download_image_success(mock_get_config, mock_request):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    mock_response = Mock()
    mock_response.content = b'\x89PNG\r\n\x1a\n'
    mock_request.return_value = mock_response
    
    service = DoubanService()
    image_data = service.download_image("https://img.example.com/cover.jpg")
    
    assert image_data == b'\x89PNG\r\n\x1a\n'
    mock_request.assert_called_once()

@patch('core.services.douban._request_with_retry')
@patch('core.services.douban.get_config')
def test_douban_service_download_image_with_referer(mock_get_config, mock_request):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    mock_response = Mock()
    mock_response.content = b'\x89PNG\r\n\x1a\n'
    mock_request.return_value = mock_response
    
    service = DoubanService()
    image_data = service.download_image(
        "https://img.example.com/cover.jpg",
        referer="https://book.douban.com/subject/123/"
    )
    
    assert image_data == b'\x89PNG\r\n\x1a\n'
    mock_request.assert_called_once()

@patch('core.services.douban._request_with_retry')
@patch('core.services.douban.get_config')
def test_douban_service_download_image_empty_response(mock_get_config, mock_request):
    mock_config = MagicMock()
    mock_config.douban.api_key = "test_api_key"
    mock_config.douban.api_key_search = "test_search_key"
    mock_config.douban.book_url = "https://api.douban.com/v2/book"
    mock_get_config.return_value = mock_config
    
    mock_request.return_value = None
    
    service = DoubanService()
    image_data = service.download_image("https://img.example.com/cover.jpg")
    
    assert image_data is None
