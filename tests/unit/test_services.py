"""服务测试"""
import pytest
import requests
from unittest.mock import Mock, patch
from core.services.douban import DoubanService, _request_with_retry
from core.exceptions import DoubanAPIError, NetworkError

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

def test_douban_service_init():
    service = DoubanService()
    assert service._session is not None
    assert "User-Agent" in service._session.headers

def test_douban_service_get_book_by_isbn():
    service = DoubanService()
    
    # 测试无效 ISBN
    assert service.get_book_by_isbn("") is None
    assert service.get_book_by_isbn("123") is None  # 长度不对