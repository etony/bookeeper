"""异常类测试"""
import pytest
from core.exceptions import (
    BookeeperError,
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ServiceError,
    DoubanAPIError,
    NetworkError,
    CoverDownloadError,
    ValidationError,
)

def test_base_exception():
    exc = BookeeperError("测试错误", details={"key": "value"})
    assert str(exc) == "测试错误"
    assert exc.message == "测试错误"
    assert exc.details == {"key": "value"}

def test_database_error():
    exc = DatabaseError("数据库错误")
    assert isinstance(exc, BookeeperError)
    assert str(exc) == "数据库错误"

def test_connection_error():
    exc = DatabaseConnectionError("连接失败")
    assert isinstance(exc, DatabaseError)
    assert isinstance(exc, BookeeperError)

def test_query_error():
    exc = QueryError("查询失败")
    assert isinstance(exc, DatabaseError)

def test_service_error():
    exc = ServiceError("服务错误")
    assert isinstance(exc, BookeeperError)

def test_douban_api_error():
    exc = DoubanAPIError("API调用失败")
    assert isinstance(exc, ServiceError)

def test_network_error():
    exc = NetworkError("网络连接失败")
    assert isinstance(exc, ServiceError)

def test_cover_download_error():
    exc = CoverDownloadError("封面下载失败")
    assert isinstance(exc, ServiceError)

def test_validation_error():
    exc = ValidationError("数据验证失败")
    assert isinstance(exc, BookeeperError)

def test_exception_hierarchy():
    # 测试异常继承关系
    assert issubclass(DatabaseConnectionError, DatabaseError)
    assert issubclass(QueryError, DatabaseError)
    assert issubclass(DoubanAPIError, ServiceError)
    assert issubclass(NetworkError, ServiceError)
    assert issubclass(CoverDownloadError, ServiceError)

    assert issubclass(DatabaseError, BookeeperError)
    assert issubclass(ServiceError, BookeeperError)
    assert issubclass(ValidationError, BookeeperError)
