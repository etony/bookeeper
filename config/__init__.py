# 配置管理器
import json
import logging
import os
from typing import Dict, Any
from .defaults import AppConfig, DEFAULT_CONFIG
from .schema import DEFAULT_SCHEMA
from .env import EnvLoader

logger = logging.getLogger(__name__)


class Config:
    """
    兼容旧版 Config 类的静态配置接口（已废弃）。
    
    请使用 ConfigManager 或 get_config() 代替。
    用法：Config.DB_PATH、Config.WEB_PORT……
    所有配置集中在此，方便统一修改和维护。
    """
    
    # ── 应用基本信息 ──────────────────────────────────────────
    APP_NAME = 'Bookeeper'
    APP_VERSION = '3.0.0'
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'books.db')
    
    # ── 豆瓣 API ──────────────────────────────────────────────
    DOUBAN_API_KEY = '0ab215a8b1977939201640fa14c66bab'
    DOUBAN_API_KEY_SEARCH = '0ac44ae016490db2204ce0a042db2916'
    DOUBAN_ISBN_URL = 'https://api.douban.com/v2/book/isbn'
    DOUBAN_SEARCH_URL = 'https://api.douban.com/v2/book/search'
    HEADERS = {
        'Referer': 'https://m.douban.com/tv/american',
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) '
                      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1',
    }
    
    # ── 界面尺寸与列定义 ──────────────────────────────────────
    TABLE_COLUMNS = ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']
    MAIN_WINDOW_SIZE = (1000, 800)
    SEARCH_DIALOG_SIZE = (700, 420)
    DETAIL_DIALOG_SIZE = (580, 500)

    # ── 图书状态与书柜 ────────────────────────────────────────
    STATUSES = ['默认', '计划', '已读']
    DEFAULT_STATUS = '默认'
    DEFAULT_SHELF = '未设置'
    
    # ── 网络与备份 ────────────────────────────────────────────
    WEB_PORT = 8899
    BACKUP_KEEP = 30
    BACKUP_INTERVAL_MS = 300000

class ConfigManager:
    def __init__(self, config_path: str = None):
        # 默认固定为项目根的 config.json（相对 CWD 会随启动目录漂移）
        self._config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config.json")
        self._config: AppConfig = None
        self._load_config()
    
    def _load_config(self):
        config_data = {}
        
        # 1. 加载默认配置
        config_data.update(self._config_to_dict(DEFAULT_CONFIG))
        
        # 2. 加载配置文件（首次运行生成默认配置，方便用户修改豆瓣 key 等）
        if not os.path.exists(self._config_path):
            try:
                with open(self._config_path, "w", encoding="utf-8") as f:
                    json.dump(self._config_to_dict(DEFAULT_CONFIG), f,
                              ensure_ascii=False, indent=2)
            except OSError as e:
                logger.warning(f"生成默认配置文件失败: {e}")
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                    # 兼容旧版键名（旧 config.json 用 DOUBAN_API_KEY 大写格式）
                    for old_key, new_key in (
                        ("DOUBAN_API_KEY", "douban_api_key"),
                        ("DOUBAN_API_KEY_SEARCH", "douban_api_key_search"),
                    ):
                        if old_key in file_config and new_key not in file_config:
                            file_config[new_key] = file_config.pop(old_key)
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
        """从字典构建 AppConfig，未提供的字段使用 DEFAULT_CONFIG 的值"""
        from .defaults import DoubanConfig, DatabaseConfig, WebConfig, BackupConfig
        d = DEFAULT_CONFIG

        headers = data.get("douban_headers", d.douban.headers)

        return AppConfig(
            name=data.get("name", d.name),
            version=data.get("version", d.version),
            douban=DoubanConfig(
                api_key=data.get("douban_api_key", d.douban.api_key),
                api_key_search=data.get("douban_api_key_search", d.douban.api_key_search),
                book_url=data.get("douban_book_url", d.douban.book_url),
                headers=headers,
            ),
            database=DatabaseConfig(
                path=data.get("database_path", d.database.path),
            ),
            web=WebConfig(
                port=data.get("web_port", d.web.port),
                host=data.get("web_host", d.web.host),
            ),
            backup=BackupConfig(
                keep=data.get("backup_keep", d.backup.keep),
                interval_ms=data.get("backup_interval_ms", d.backup.interval_ms),
            ),
        )
    
    @property
    def config(self) -> AppConfig:
        return self._config
    
    def reload(self):
        self._load_config()

# 全局配置实例
_config_manager: ConfigManager = None

def _apply_to_legacy_config(cfg: AppConfig):
    """
    把 ConfigManager 的值回写到旧版 Config 静态类。

    业务代码全部读 Config 静态类（douban.py/database.py 等 12 处），
    不回写的话 config.json 和 BOOKEEPER_ 环境变量完全不生效。
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    path = cfg.database.path
    if not os.path.isabs(path):
        path = os.path.join(base_dir, path)
    Config.DB_PATH = path
    Config.WEB_PORT = cfg.web.port
    Config.BACKUP_KEEP = cfg.backup.keep
    Config.BACKUP_INTERVAL_MS = cfg.backup.interval_ms
    Config.DOUBAN_API_KEY = cfg.douban.api_key
    Config.DOUBAN_API_KEY_SEARCH = cfg.douban.api_key_search
    Config.HEADERS = dict(cfg.douban.headers)

def get_config() -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
        _apply_to_legacy_config(_config_manager.config)
    return _config_manager

def init_config(config_path: str = None) -> ConfigManager:
    global _config_manager
    _config_manager = ConfigManager(config_path)
    _apply_to_legacy_config(_config_manager.config)
    return _config_manager