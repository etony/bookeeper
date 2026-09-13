# 环境变量处理
import os
from typing import Dict, Any

class EnvLoader:
    PREFIX = "BOOKEEPER_"
    
    @classmethod
    def load(cls) -> Dict[str, Any]:
        env_config = {}
        for key, value in os.environ.items():
            if key.startswith(cls.PREFIX):
                config_key = key[len(cls.PREFIX):].lower()
                env_config[config_key] = cls._convert_value(value)
        return env_config
    
    @classmethod
    def _convert_value(cls, value: str) -> Any:
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value