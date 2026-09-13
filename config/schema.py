# 配置验证模式
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class ConfigField:
    name: str
    type: type
    required: bool = False
    default: Any = None
    description: str = ""
    min_value: Any = None  # 用于数值类型
    max_value: Any = None  # 用于数值类型
    min_length: int = None  # 用于字符串或列表类型
    max_length: int = None  # 用于字符串或列表类型

class ConfigSchema:
    def __init__(self):
        self.fields: Dict[str, ConfigField] = {}
    
    def add_field(self, field: ConfigField):
        self.fields[field.name] = field
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        validated = {}
        for name, field in self.fields.items():
            if name in data:
                value = data[name]
                if not isinstance(value, field.type):
                    raise ValueError(f"配置项 {name} 类型错误: 期望 {field.type}, 实际 {type(value)}")
                
                # 数值范围验证
                if field.type == int or field.type == float:
                    if field.min_value is not None and value < field.min_value:
                        raise ValueError(f"配置项 {name} 值过小: 最小值为 {field.min_value}, 实际值为 {value}")
                    if field.max_value is not None and value > field.max_value:
                        raise ValueError(f"配置项 {name} 值过大: 最大值为 {field.max_value}, 实际值为 {value}")
                
                # 字符串/列表长度验证
                if field.type == str or (hasattr(field.type, '__origin__') and field.type.__origin__ == list):
                    if field.min_length is not None and len(value) < field.min_length:
                        raise ValueError(f"配置项 {name} 长度过短: 最小长度为 {field.min_length}, 实际长度为 {len(value)}")
                    if field.max_length is not None and len(value) > field.max_length:
                        raise ValueError(f"配置项 {name} 长度过长: 最大长度为 {field.max_length}, 实际长度为 {len(value)}")
                
                validated[name] = value
            elif field.required:
                raise ValueError(f"配置项 {name} 是必需的")
            else:
                validated[name] = field.default
        return validated

# 创建默认配置模式
DEFAULT_SCHEMA = ConfigSchema()
DEFAULT_SCHEMA.add_field(ConfigField("name", str, default="Bookeeper"))
DEFAULT_SCHEMA.add_field(ConfigField("version", str, default="3.0.0"))
DEFAULT_SCHEMA.add_field(ConfigField("douban_api_key", str, default="0ab215a8b1977939201640fa14c66bab"))
DEFAULT_SCHEMA.add_field(ConfigField("douban_api_key_search", str, default="0ac44ae016490db2204ce0a042db2916"))
DEFAULT_SCHEMA.add_field(ConfigField("database_path", str, default="books.db"))
DEFAULT_SCHEMA.add_field(ConfigField("web_port", int, default=8899, min_value=1024, max_value=65535))
DEFAULT_SCHEMA.add_field(ConfigField("web_host", str, default="127.0.0.1"))
DEFAULT_SCHEMA.add_field(ConfigField("backup_keep", int, default=30, min_value=1, max_value=365))
DEFAULT_SCHEMA.add_field(ConfigField("backup_interval_ms", int, default=300000, min_value=60000, max_value=86400000))
DEFAULT_SCHEMA.add_field(ConfigField("douban_book_url", str, default="https://api.douban.com/v2/book"))