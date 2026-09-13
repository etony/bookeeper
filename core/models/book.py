"""图书模型"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class Book:
    """图书领域模型"""
    
    isbn: str = ''
    title: str = ''
    author: str = ''
    publisher: str = ''
    price: str = ''
    rating: str = '0'
    raters: str = '0'
    status: str = '默认'
    shelf: str = '未设置'
    start_date: str = ''
    end_date: str = ''
    cover_url: str = ''
    pubdate: str = ''
    douban_url: str = ''
    recommend: str = '0'
    pages: str = ''
    rating_detail: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Book':
        """从字典恢复 Book 对象"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})