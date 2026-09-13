"""基础模型类"""
from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class BaseModel:
    """基础模型类，提供通用方法"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """从字典创建对象"""
        # 过滤掉不属于当前类的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)