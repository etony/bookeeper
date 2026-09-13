"""自定义异常类"""
from typing import Optional, Any


class BookeeperError(Exception):
    """基础异常"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details


class DatabaseError(BookeeperError):
    """数据库相关错误"""
    pass


class ConnectionError(DatabaseError):
    """数据库连接错误"""
    pass


class QueryError(DatabaseError):
    """数据库查询错误"""
    pass


class ServiceError(BookeeperError):
    """服务相关错误"""
    pass


class DoubanAPIError(ServiceError):
    """豆瓣API错误"""
    pass


class NetworkError(ServiceError):
    """网络错误"""
    pass


class CoverDownloadError(ServiceError):
    """封面下载错误"""
    pass


class ValidationError(BookeeperError):
    """数据验证错误"""
    pass
