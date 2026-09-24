"""Repository 接口定义"""
from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic

T = TypeVar("T")

class RepositoryInterface(ABC, Generic[T]):
    """Repository 通用接口"""
    
    @abstractmethod
    def get_by_isbn(self, isbn: str) -> Optional[T]:
        """根据 ISBN 获取单个对象"""
        pass
    
    @abstractmethod
    def get_all(self) -> List[T]:
        """获取所有对象"""
        pass
    
    @abstractmethod
    def create(self, entity: T) -> bool:
        """创建新对象"""
        pass
    
    @abstractmethod
    def update(self, entity: T) -> bool:
        """更新对象"""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """删除对象"""
        pass
    
    @abstractmethod
    def count(self, keyword: str = '', status: str = '') -> int:
        """统计总数（支持按关键词和状态筛选）"""
        pass