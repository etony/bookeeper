# 默认配置值
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class DoubanConfig:
    api_key: str = "0ab215a8b1977939201640fa14c66bab"
    api_key_search: str = "0ac44ae016490db2204ce0a042db2916"
    book_url: str = "https://api.douban.com/v2/book"
    headers: Dict[str, str] = field(default_factory=lambda: {
        "Referer": "https://m.douban.com/tv/american",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
    })

@dataclass
class DatabaseConfig:
    path: str = "books.db"

@dataclass
class WebConfig:
    port: int = 8899
    host: str = "127.0.0.1"

@dataclass
class BackupConfig:
    keep: int = 30
    interval_ms: int = 300000

@dataclass
class AppConfig:
    name: str = "Bookeeper"
    version: str = "3.0.0"
    douban: DoubanConfig = None
    database: DatabaseConfig = None
    web: WebConfig = None
    backup: BackupConfig = None

    def __post_init__(self):
        if self.douban is None:
            self.douban = DoubanConfig()
        if self.database is None:
            self.database = DatabaseConfig()
        if self.web is None:
            self.web = WebConfig()
        if self.backup is None:
            self.backup = BackupConfig()

DEFAULT_CONFIG = AppConfig()