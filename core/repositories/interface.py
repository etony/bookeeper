"""Repository 接口定义"""
from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic

T = TypeVar("T")

class RepositoryInterface(ABC, Generic[T]):
    """Repository 通用接口"""
    
    @abstractmethod
    def get_by_id(self, id: str) -> Optional[T]:
        """根据 ID 获取单个对象"""
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
    def count(self) -> int:
        """统计总数"""
        pass