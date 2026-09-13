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
DEFAULT_SCHEMA.add_field(ConfigField("web_port", int, default=8899))
DEFAULT_SCHEMA.add_field(ConfigField("web_host", str, default="127.0.0.1"))
DEFAULT_SCHEMA.add_field(ConfigField("backup_keep", int, default=30))
DEFAULT_SCHEMA.add_field(ConfigField("backup_interval_ms", int, default=300000))