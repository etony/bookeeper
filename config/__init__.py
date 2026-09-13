# 配置管理器
import json
import logging
import os
from typing import Dict, Any
from .defaults import AppConfig, DEFAULT_CONFIG
from .schema import DEFAULT_SCHEMA
from .env import EnvLoader

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: str = None):
        self._config_path = config_path or "config.json"
        self._config: AppConfig = None
        self._load_config()
    
    def _load_config(self):
        config_data = {}
        
        # 1. 加载默认配置
        config_data.update(self._config_to_dict(DEFAULT_CONFIG))
        
        # 2. 加载配置文件
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                    config_data.update(file_config)
            except json.JSONDecodeError as e:
                logger.warning(f"配置文件格式错误: {e}，将使用默认配置")
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}，将使用默认配置")
        
        # 3. 加载环境变量
        env_config = EnvLoader.load()
        config_data.update(env_config)
        
        # 4. 验证配置
        try:
            validated = DEFAULT_SCHEMA.validate(config_data)
        except ValueError as e:
            logger.warning(f"配置验证失败: {e}，将使用默认配置")
            # 使用默认配置进行验证
            validated = DEFAULT_SCHEMA.validate(self._config_to_dict(DEFAULT_CONFIG))
        
        # 5. 转换为 AppConfig 对象
        self._config = self._dict_to_config(validated)
    
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        return {
            "name": config.name,
            "version": config.version,
            "douban_api_key": config.douban.api_key,
            "douban_api_key_search": config.douban.api_key_search,
            "douban_book_url": config.douban.book_url,
            "douban_headers": config.douban.headers,
            "database_path": config.database.path,
            "web_port": config.web.port,
            "web_host": config.web.host,
            "backup_keep": config.backup.keep,
            "backup_interval_ms": config.backup.interval_ms,
        }
    
    def _dict_to_config(self, data: Dict[str, Any]) -> AppConfig:
        from .defaults import DoubanConfig, DatabaseConfig, WebConfig, BackupConfig
        
        headers = data.get("douban_headers", {
            "Referer": "https://m.douban.com/tv/american",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
        })
        
        return AppConfig(
            name=data.get("name", "Bookeeper"),
            version=data.get("version", "3.0.0"),
            douban=DoubanConfig(
                api_key=data.get("douban_api_key", "0ab215a8b1977939201640fa14c66bab"),
                api_key_search=data.get("douban_api_key_search", "0ac44ae016490db2204ce0a042db2916"),
                book_url=data.get("douban_book_url", "https://api.douban.com/v2/book"),
                headers=headers,
            ),
            database=DatabaseConfig(
                path=data.get("database_path", "books.db"),
            ),
            web=WebConfig(
                port=data.get("web_port", 8899),
                host=data.get("web_host", "127.0.0.1"),
            ),
            backup=BackupConfig(
                keep=data.get("backup_keep", 30),
                interval_ms=data.get("backup_interval_ms", 300000),
            ),
        )
    
    @property
    def config(self) -> AppConfig:
        return self._config
    
    def reload(self):
        self._load_config()

# 全局配置实例
_config_manager: ConfigManager = None

def get_config() -> AppConfig:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.config

def init_config(config_path: str = None) -> ConfigManager:
    global _config_manager
    _config_manager = ConfigManager(config_path)
    return _config_manager