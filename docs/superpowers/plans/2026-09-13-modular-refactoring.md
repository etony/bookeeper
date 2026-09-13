# Bookeeper 模块化重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Bookeeper 从单体架构重构为模块化架构，提高代码可维护性和可扩展性

**Architecture:** 采用分层架构，将代码拆分为 core（核心业务逻辑）、ui（界面层）、web（Web服务）、config（配置管理）等模块，使用依赖注入和接口抽象降低耦合

**Tech Stack:** Python 3.12, PyQt6, FastAPI, SQLite, Docker, pytest

---

## 文件结构映射

### 新建文件
```
bookeeper/
├── core/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py              # 基础模型类
│   │   └── book.py              # Book 数据模型
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py              # Repository 基类
│   │   ├── book_repo.py         # Book 专用仓储
│   │   └── interface.py         # Repository 接口
│   ├── services/
│   │   ├── __init__.py
│   │   ├── douban.py            # 豆瓣API服务
│   │   ├── backup.py            # 备份服务
│   │   ├── covers.py            # 封面缓存服务
│   │   └── undo.py              # 撤销管理服务
│   ├── exceptions.py            # 自定义异常类
│   └── logging.py               # 日志配置模块
├── config/
│   ├── __init__.py              # 配置管理器
│   ├── defaults.py              # 默认配置值
│   ├── schema.py                # 配置验证模式
│   └── env.py                   # 环境变量处理
├── tests/
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_repositories.py
│   │   └── test_services.py
│   ├── integration/
│   │   ├── test_database.py
│   │   └── test_web.py
│   ├── fixtures/
│   │   ├── books.json
│   │   └── config.json
│   └── conftest.py
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── requirements-dev.txt
```

### 修改文件
```
bookeeper/
├── ui/
│   ├── main_window.py           # 简化主窗口
│   ├── components/              # 新建组件目录
│   ├── dialogs/                 # 新建对话框目录
│   └── views/                   # 新建视图目录
├── web/
│   ├── app.py                   # 新建应用工厂
│   ├── routes/                  # 新建路由目录
│   └── middleware/               # 新建中间件目录
└── utils.py                     # 保持现有工具函数
```

---

## Task 1: 基础架构 - 配置管理

**Files:**
- Create: `config/__init__.py`
- Create: `config/defaults.py`
- Create: `config/schema.py`
- Create: `config/env.py`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: 创建默认配置**

```python
# config/defaults.py
"""默认配置值"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class DoubanConfig:
    api_key: str = "0ab215a8b1977939201640fa14c66bab"
    api_key_search: str = "0ac44ae016490db2204ce0a042db2916"
    book_url: str = "https://api.douban.com/v2/book"

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
```

- [ ] **Step 2: 创建配置验证**

```python
# config/schema.py
"""配置验证模式"""
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
```

- [ ] **Step 3: 创建环境变量处理**

```python
# config/env.py
"""环境变量处理"""
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
```

- [ ] **Step 4: 创建配置管理器**

```python
# config/__init__.py
"""配置管理器"""
import json
import os
from typing import Dict, Any
from .defaults import AppConfig, DEFAULT_CONFIG
from .schema import DEFAULT_SCHEMA
from .env import EnvLoader

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
            with open(self._config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config_data.update(file_config)
        
        # 3. 加载环境变量
        env_config = EnvLoader.load()
        config_data.update(env_config)
        
        # 4. 验证配置
        validated = DEFAULT_SCHEMA.validate(config_data)
        
        # 5. 转换为 AppConfig 对象
        self._config = self._dict_to_config(validated)
    
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        return {
            "name": config.name,
            "version": config.version,
            "douban_api_key": config.douban.api_key,
            "douban_api_key_search": config.douban.api_key_search,
            "douban_book_url": config.douban.book_url,
            "database_path": config.database.path,
            "web_port": config.web.port,
            "web_host": config.web.host,
            "backup_keep": config.backup.keep,
            "backup_interval_ms": config.backup.interval_ms,
        }
    
    def _dict_to_config(self, data: Dict[str, Any]) -> AppConfig:
        from .defaults import DoubanConfig, DatabaseConfig, WebConfig, BackupConfig
        
        return AppConfig(
            name=data.get("name", "Bookeeper"),
            version=data.get("version", "3.0.0"),
            douban=DoubanConfig(
                api_key=data.get("douban_api_key", "0ab215a8b1977939201640fa14c66bab"),
                api_key_search=data.get("douban_api_key_search", "0ac44ae016490db2204ce0a042db2916"),
                book_url=data.get("douban_book_url", "https://api.douban.com/v2/book"),
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
```

- [ ] **Step 5: 编写配置测试**

```python
# tests/unit/test_config.py
"""配置管理测试"""
import os
import tempfile
import pytest
from config import ConfigManager, get_config, init_config
from config.defaults import AppConfig, DEFAULT_CONFIG
from config.env import EnvLoader

def test_default_config():
    config = DEFAULT_CONFIG
    assert config.name == "Bookeeper"
    assert config.version == "3.0.0"
    assert config.douban.api_key == "0ab215a8b1977939201640fa14c66bab"
    assert config.web.port == 8899

def test_config_manager_with_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"name": "TestApp", "web_port": 9000}')
        config_path = f.name
    
    try:
        manager = ConfigManager(config_path)
        config = manager.config
        assert config.name == "TestApp"
        assert config.web.port == 9000
    finally:
        os.unlink(config_path)

def test_env_loader():
    os.environ["BOOKEEPER_TEST_KEY"] = "test_value"
    os.environ["BOOKEEPER_TEST_PORT"] = "8080"
    os.environ["BOOKEEPER_TEST_BOOL"] = "true"
    
    env_config = EnvLoader.load()
    assert env_config["test_key"] == "test_value"
    assert env_config["test_port"] == 8080
    assert env_config["test_bool"] is True
    
    del os.environ["BOOKEEPER_TEST_KEY"]
    del os.environ["BOOKEEPER_TEST_PORT"]
    del os.environ["BOOKEEPER_TEST_BOOL"]

def test_config_priority():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"name": "FileApp"}')
        config_path = f.name
    
    try:
        os.environ["BOOKEEPER_NAME"] = "EnvApp"
        manager = ConfigManager(config_path)
        config = manager.config
        assert config.name == "EnvApp"  # 环境变量优先
    finally:
        os.unlink(config_path)
        del os.environ["BOOKEEPER_NAME"]
```

- [ ] **Step 6: 运行测试验证**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS

- [ ] **Step 7: 提交代码**

```bash
git add config/ tests/unit/test_config.py
git commit -m "feat: add config management with layered configuration"
```

---

## Task 2: 基础架构 - 异常定义

**Files:**
- Create: `core/__init__.py`
- Create: `core/exceptions.py`
- Test: `tests/unit/test_exceptions.py`

- [ ] **Step 1: 创建异常类**

```python
# core/exceptions.py
"""自定义异常类"""
from typing import Optional, Any

class BookeeperError(Exception):
    """基础异常"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details

class DatabaseError(BookeeperError):
    """数据库相关错误"""
    pass

class ConnectionError(DatabaseError):
    """数据库连接错误"""
    pass

class QueryError(DatabaseError):
    """数据库查询错误"""
    pass

class ServiceError(BookeeperError):
    """服务相关错误"""
    pass

class DoubanAPIError(ServiceError):
    """豆瓣API错误"""
    pass

class NetworkError(ServiceError):
    """网络错误"""
    pass

class CoverDownloadError(ServiceError):
    """封面下载错误"""
    pass

class ValidationError(BookeeperError):
    """数据验证错误"""
    pass
```

- [ ] **Step 2: 创建核心模块初始化**

```python
# core/__init__.py
"""核心业务逻辑模块"""
from .exceptions import (
    BookeeperError,
    DatabaseError,
    ConnectionError,
    QueryError,
    ServiceError,
    DoubanAPIError,
    NetworkError,
    CoverDownloadError,
    ValidationError,
)

__all__ = [
    "BookeeperError",
    "DatabaseError",
    "ConnectionError",
    "QueryError",
    "ServiceError",
    "DoubanAPIError",
    "NetworkError",
    "CoverDownloadError",
    "ValidationError",
]
```

- [ ] **Step 3: 编写异常测试**

```python
# tests/unit/test_exceptions.py
"""异常类测试"""
import pytest
from core.exceptions import (
    BookeeperError,
    DatabaseError,
    ConnectionError,
    QueryError,
    ServiceError,
    DoubanAPIError,
    NetworkError,
    CoverDownloadError,
    ValidationError,
)

def test_base_exception():
    exc = BookeeperError("测试错误", details={"key": "value"})
    assert str(exc) == "测试错误"
    assert exc.message == "测试错误"
    assert exc.details == {"key": "value"}

def test_database_error():
    exc = DatabaseError("数据库错误")
    assert isinstance(exc, BookeeperError)
    assert str(exc) == "数据库错误"

def test_connection_error():
    exc = ConnectionError("连接失败")
    assert isinstance(exc, DatabaseError)
    assert isinstance(exc, BookeeperError)

def test_query_error():
    exc = QueryError("查询失败")
    assert isinstance(exc, DatabaseError)

def test_service_error():
    exc = ServiceError("服务错误")
    assert isinstance(exc, BookeeperError)

def test_douban_api_error():
    exc = DoubanAPIError("API调用失败")
    assert isinstance(exc, ServiceError)

def test_network_error():
    exc = NetworkError("网络连接失败")
    assert isinstance(exc, ServiceError)

def test_cover_download_error():
    exc = CoverDownloadError("封面下载失败")
    assert isinstance(exc, ServiceError)

def test_validation_error():
    exc = ValidationError("数据验证失败")
    assert isinstance(exc, BookeeperError)

def test_exception_hierarchy():
    # 测试异常继承关系
    assert issubclass(ConnectionError, DatabaseError)
    assert issubclass(QueryError, DatabaseError)
    assert issubclass(DoubanAPIError, ServiceError)
    assert issubclass(NetworkError, ServiceError)
    assert issubclass(CoverDownloadError, ServiceError)
    
    assert issubclass(DatabaseError, BookeeperError)
    assert issubclass(ServiceError, BookeeperError)
    assert issubclass(ValidationError, BookeeperError)
```

- [ ] **Step 4: 运行测试验证**

Run: `pytest tests/unit/test_exceptions.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add core/ tests/unit/test_exceptions.py
git commit -m "feat: add custom exception hierarchy"
```

---

## Task 3: 基础架构 - 日志配置

**Files:**
- Create: `core/logging.py`
- Test: `tests/unit/test_logging.py`

- [ ] **Step 1: 创建日志配置**

```python
# core/logging.py
"""日志配置模块"""
import logging
import json
from datetime import datetime
from typing import Dict, Any

class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        return json.dumps(log_data, ensure_ascii=False)

def setup_logging(level: str = "INFO", log_file: str = None):
    """设置日志配置"""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)
    
    # 文件处理器（可选）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器"""
    return logging.getLogger(name)
```

- [ ] **Step 2: 编写日志测试**

```python
# tests/unit/test_logging.py
"""日志配置测试"""
import json
import logging
import tempfile
import os
from core.logging import setup_logging, get_logger, StructuredFormatter

def test_structured_formatter():
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="测试消息",
        args=(),
        exc_info=None,
    )
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["level"] == "INFO"
    assert data["logger"] == "test"
    assert data["message"] == "测试消息"
    assert "timestamp" in data

def test_setup_logging():
    logger = setup_logging(level="DEBUG")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1  # 控制台处理器

def test_setup_logging_with_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        log_file = f.name
    
    try:
        logger = setup_logging(level="INFO", log_file=log_file)
        assert len(logger.handlers) == 2  # 控制台 + 文件处理器
        
        test_logger = get_logger("test")
        test_logger.info("测试日志消息")
        
        # 验证日志文件内容
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            data = json.loads(content)
            assert data["message"] == "测试日志消息"
    finally:
        os.unlink(log_file)

def test_get_logger():
    logger = get_logger("test.module")
    assert logger.name == "test.module"
    assert isinstance(logger, logging.Logger)
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/unit/test_logging.py -v`
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add core/logging.py tests/unit/test_logging.py
git commit -m "feat: add structured logging configuration"
```

---

## Task 4: 数据层 - Repository 模式

**Files:**
- Create: `core/repositories/__init__.py`
- Create: `core/repositories/interface.py`
- Create: `core/repositories/base.py`
- Create: `core/repositories/book_repo.py`
- Test: `tests/unit/test_repositories.py`

- [ ] **Step 1: 创建 Repository 接口**

```python
# core/repositories/interface.py
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
```

- [ ] **Step 2: 创建 Repository 基类**

```python
# core/repositories/base.py
"""Repository 基类"""
import sqlite3
from contextlib import contextmanager
from typing import List, Optional, TypeVar, Generic
from config import get_config
from core.exceptions import ConnectionError, QueryError

T = TypeVar("T")

class BaseRepository(RepositoryInterface, Generic[T]):
    """Repository 基类，提供通用数据库操作"""
    
    def __init__(self, db_path: str = None):
        config = get_config()
        self._path = db_path or config.database.path
        self._init_db()
    
    @contextmanager
    def _conn(self):
        """数据库连接上下文管理器"""
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise QueryError(f"数据库操作失败: {e}")
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库（子类实现）"""
        pass
    
    def count(self) -> int:
        """统计总数"""
        with self._conn() as conn:
            table_name = self._get_table_name()
            result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            return result[0]
    
    def _get_table_name(self) -> str:
        """获取表名（子类实现）"""
        raise NotImplementedError
```

- [ ] **Step 3: 创建 Book Repository**

```python
# core/repositories/book_repo.py
"""Book Repository 实现"""
from typing import List, Optional
from core.models.book import Book
from core.repositories.base import BaseRepository
from core.exceptions import QueryError

class BookRepository(BaseRepository[Book]):
    """Book 专用仓储"""
    
    def _get_table_name(self) -> str:
        return "books"
    
    def _init_db(self):
        """初始化 books 表"""
        with self._conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS books (
                    isbn TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    author TEXT DEFAULT '',
                    publisher TEXT DEFAULT '',
                    price TEXT DEFAULT '',
                    rating TEXT DEFAULT '0',
                    raters TEXT DEFAULT '0',
                    status TEXT DEFAULT '默认',
                    shelf TEXT DEFAULT '未设置',
                    start_date TEXT DEFAULT '',
                    end_date TEXT DEFAULT '',
                    cover_url TEXT DEFAULT '',
                    pubdate TEXT DEFAULT '',
                    douban_url TEXT DEFAULT '',
                    recommend TEXT DEFAULT '0',
                    pages TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_books_status ON books(status)')
    
    def get_by_id(self, isbn: str) -> Optional[Book]:
        """根据 ISBN 获取图书"""
        with self._conn() as conn:
            row = conn.execute('SELECT * FROM books WHERE isbn = ?', (isbn,)).fetchone()
            return Book.from_dict(dict(row)) if row else None
    
    def get_all(self) -> List[Book]:
        """获取所有图书"""
        with self._conn() as conn:
            rows = conn.execute('SELECT * FROM books ORDER BY title').fetchall()
            return [Book.from_dict(dict(r)) for r in rows]
    
    def create(self, book: Book) -> bool:
        """创建新图书"""
        data = {k: v for k, v in book.to_dict().items() if k != 'rating_detail'}
        cols = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        sql = f'INSERT INTO books ({cols}) VALUES ({placeholders})'
        
        with self._conn() as conn:
            conn.execute(sql, list(data.values()))
        return True
    
    def update(self, book: Book) -> bool:
        """更新图书"""
        data = {k: v for k, v in book.to_dict().items() if k != 'rating_detail'}
        updates = ', '.join(f'{k}=?' for k in data)
        sql = f'UPDATE books SET {updates}, updated_at=CURRENT_TIMESTAMP WHERE isbn=?'
        
        with self._conn() as conn:
            conn.execute(sql, list(data.values()) + [book.isbn])
        return True
    
    def upsert(self, book: Book) -> bool:
        """插入或更新图书"""
        data = {k: v for k, v in book.to_dict().items() if k != 'rating_detail'}
        cols = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        updates = ', '.join(f'{k}=excluded.{k}' for k in data)
        sql = f'''
            INSERT INTO books ({cols}) VALUES ({placeholders})
            ON CONFLICT(isbn) DO UPDATE SET {updates}, updated_at=CURRENT_TIMESTAMP
        '''
        
        with self._conn() as conn:
            conn.execute(sql, list(data.values()))
        return True
    
    def delete(self, isbn: str) -> bool:
        """删除图书"""
        with self._conn() as conn:
            cur = conn.execute('DELETE FROM books WHERE isbn = ?', (isbn,))
            return cur.rowcount > 0
    
    def search(self, keyword: str = '', status: str = '') -> List[Book]:
        """搜索图书"""
        clauses = []
        params = []
        
        if keyword:
            clauses.append('(title LIKE ? OR author LIKE ? OR publisher LIKE ? OR isbn LIKE ?)')
            kw = f'%{keyword}%'
            params.extend([kw, kw, kw, kw])
        
        if status:
            clauses.append('status = ?')
            params.append(status)
        
        where = ' AND '.join(clauses)
        if where:
            where = 'WHERE ' + where
        
        sql = f'SELECT * FROM books {where} ORDER BY title'
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [Book.from_dict(dict(r)) for r in rows]
    
    def status_counts(self) -> dict:
        """统计各状态数量"""
        with self._conn() as conn:
            rows = conn.execute('SELECT status, COUNT(*) as cnt FROM books GROUP BY status').fetchall()
            return {r['status']: r['cnt'] for r in rows}
    
    def publisher_top(self, n: int = 10) -> list:
        """出版社 TOP N"""
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT publisher, COUNT(*) as cnt FROM books WHERE publisher != "" GROUP BY publisher ORDER BY cnt DESC LIMIT ?',
                (n,)
            ).fetchall()
            return [(r['publisher'], r['cnt']) for r in rows]
    
    def rating_distribution(self) -> dict:
        """评分分布"""
        with self._conn() as conn:
            rows = conn.execute('SELECT rating FROM books WHERE rating != "" AND rating != "0"').fetchall()
        
        bins = {'0-6': 0, '6-7': 0, '7-8': 0, '8-9': 0, '9-10': 0}
        for r in rows:
            try:
                val = float(r['rating'])
            except ValueError:
                continue
            if val < 6: bins['0-6'] += 1
            elif val < 7: bins['6-7'] += 1
            elif val < 8: bins['7-8'] += 1
            elif val < 9: bins['8-9'] += 1
            else: bins['9-10'] += 1
        return bins
```

- [ ] **Step 4: 创建 Repository 初始化**

```python
# core/repositories/__init__.py
"""Repository 模块"""
from .interface import RepositoryInterface
from .base import BaseRepository
from .book_repo import BookRepository

__all__ = [
    "RepositoryInterface",
    "BaseRepository",
    "BookRepository",
]
```

- [ ] **Step 5: 编写 Repository 测试**

```python
# tests/unit/test_repositories.py
"""Repository 测试"""
import os
import tempfile
import pytest
from core.models.book import Book
from core.repositories.book_repo import BookRepository

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    repo = BookRepository(db_path)
    yield repo
    
    os.unlink(db_path)

def test_create_book(temp_db):
    book = Book(isbn="9787544291163", title="百年孤独", author="加西亚·马尔克斯")
    result = temp_db.create(book)
    assert result is True
    
    retrieved = temp_db.get_by_id("9787544291163")
    assert retrieved is not None
    assert retrieved.title == "百年孤独"

def test_get_all_books(temp_db):
    book1 = Book(isbn="111", title="Book 1")
    book2 = Book(isbn="222", title="Book 2")
    
    temp_db.create(book1)
    temp_db.create(book2)
    
    books = temp_db.get_all()
    assert len(books) == 2

def test_update_book(temp_db):
    book = Book(isbn="111", title="Original Title")
    temp_db.create(book)
    
    book.title = "Updated Title"
    temp_db.update(book)
    
    retrieved = temp_db.get_by_id("111")
    assert retrieved.title == "Updated Title"

def test_delete_book(temp_db):
    book = Book(isbn="111", title="To Delete")
    temp_db.create(book)
    
    result = temp_db.delete("111")
    assert result is True
    
    retrieved = temp_db.get_by_id("111")
    assert retrieved is None

def test_upsert_book(temp_db):
    book = Book(isbn="111", title="Original")
    temp_db.create(book)
    
    book.title = "Updated"
    temp_db.upsert(book)
    
    retrieved = temp_db.get_by_id("111")
    assert retrieved.title == "Updated"

def test_search_books(temp_db):
    book1 = Book(isbn="111", title="Python Programming")
    book2 = Book(isbn="222", title="Java Programming")
    book3 = Book(isbn="333", title="Python Cookbook", status="已读")
    
    temp_db.create(book1)
    temp_db.create(book2)
    temp_db.create(book3)
    
    # 按关键词搜索
    results = temp_db.search(keyword="Python")
    assert len(results) == 2
    
    # 按状态搜索
    results = temp_db.search(status="已读")
    assert len(results) == 1
    
    # 组合搜索
    results = temp_db.search(keyword="Python", status="已读")
    assert len(results) == 1

def test_count_books(temp_db):
    assert temp_db.count() == 0
    
    book = Book(isbn="111", title="Test")
    temp_db.create(book)
    
    assert temp_db.count() == 1

def test_status_counts(temp_db):
    book1 = Book(isbn="111", title="Book 1", status="默认")
    book2 = Book(isbn="222", title="Book 2", status="已读")
    book3 = Book(isbn="333", title="Book 3", status="已读")
    
    temp_db.create(book1)
    temp_db.create(book2)
    temp_db.create(book3)
    
    counts = temp_db.status_counts()
    assert counts["默认"] == 1
    assert counts["已读"] == 2
```

- [ ] **Step 6: 运行测试验证**

Run: `pytest tests/unit/test_repositories.py -v`
Expected: PASS

- [ ] **Step 7: 提交代码**

```bash
git add core/repositories/ tests/unit/test_repositories.py
git commit -m "feat: add Repository pattern with BookRepository"
```

---

## Task 5: 数据层 - 数据模型

**Files:**
- Create: `core/models/__init__.py`
- Create: `core/models/base.py`
- Create: `core/models/book.py`
- Test: `tests/unit/test_models.py`

- [ ] **Step 1: 创建基础模型**

```python
# core/models/base.py
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
```

- [ ] **Step 2: 创建 Book 模型**

```python
# core/models/book.py
"""Book 数据模型"""
import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from .base import BaseModel

@dataclass
class Book(BaseModel):
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
    
    def to_row(self) -> List[str]:
        """转为一行的字符串列表"""
        return [
            self.isbn, self.title, self.author, self.publisher,
            self.price, self.rating, self.raters, self.status, self.shelf,
            self.start_date, self.end_date,
        ]
    
    @classmethod
    def from_douban(cls, data: Dict[str, Any]) -> Optional['Book']:
        """从豆瓣 API 的 JSON 响应创建 Book 对象"""
        if not isinstance(data, dict) or len(data) <= 5:
            return None
        
        book = cls()
        book.isbn = str(data.get('isbn13', ''))
        book.title = str(data.get('title', ''))
        
        authors = data.get('author', []) or []
        translators = data.get('translator', []) or []
        author_str = '/'.join(authors)
        if translators:
            author_str += ' 译者: ' + '/'.join(translators)
        book.author = author_str
        
        book.publisher = str(data.get('publisher', ''))
        price = str(data.get('price', ''))
        book.price = price.replace('CNY', '').replace('元', '').strip()
        
        rating = data.get('rating', {}) or {}
        book.rating = str(rating.get('average', '0'))
        book.raters = str(rating.get('numRaters', '0'))
        book.rating_detail = rating
        
        images = data.get('images', {}) or {}
        book.cover_url = str(images.get('large', '') or images.get('medium', '') or images.get('small', ''))
        
        book.pubdate = str(data.get('pubdate', ''))
        book.douban_url = str(data.get('alt', ''))
        book.pages = str(data.get('pages', ''))
        book.recommend = str(cls._calc_recommend(book.rating, book.raters))
        return book
    
    @staticmethod
    def _calc_recommend(rating: str, raters: str) -> int:
        """计算推荐度"""
        try:
            avg = float(rating) if rating else 0.0
            num = float(raters) if raters else 0.0
            if avg < 2.5 or num <= 0:
                return 0
            return round((avg - 2.5) * math.log(num + 1))
        except (ValueError, OverflowError):
            return 0
```

- [ ] **Step 3: 创建模型初始化**

```python
# core/models/__init__.py
"""数据模型模块"""
from .base import BaseModel
from .book import Book

__all__ = ["BaseModel", "Book"]
```

- [ ] **Step 4: 编写模型测试**

```python
# tests/unit/test_models.py
"""数据模型测试"""
import pytest
from core.models.book import Book

def test_book_creation():
    book = Book(isbn="9787544291163", title="百年孤独")
    assert book.isbn == "9787544291163"
    assert book.title == "百年孤独"
    assert book.status == "默认"

def test_book_to_dict():
    book = Book(isbn="111", title="Test Book")
    data = book.to_dict()
    assert data["isbn"] == "111"
    assert data["title"] == "Test Book"

def test_book_from_dict():
    data = {"isbn": "111", "title": "Test Book", "author": "Author"}
    book = Book.from_dict(data)
    assert book.isbn == "111"
    assert book.title == "Test Book"
    assert book.author == "Author"

def test_book_to_row():
    book = Book(isbn="111", title="Test", author="Author")
    row = book.to_row()
    assert row[0] == "111"
    assert row[1] == "Test"
    assert row[2] == "Author"

def test_book_from_douban():
    douban_data = {
        "isbn13": "9787544291163",
        "title": "百年孤独",
        "author": ["加西亚·马尔克斯"],
        "translator": ["范晔"],
        "publisher": "南海出版公司",
        "price": "CNY 39.50",
        "rating": {"average": "9.2", "numRaters": 12345},
        "images": {"large": "https://example.com/large.jpg"},
        "pubdate": "2011-06",
        "alt": "https://book.douban.com/subject/123",
        "pages": "360",
    }
    
    book = Book.from_douban(douban_data)
    assert book is not None
    assert book.isbn == "9787544291163"
    assert book.title == "百年孤独"
    assert book.author == "加西亚·马尔克斯 译者: 范晔"
    assert book.publisher == "南海出版公司"
    assert book.price == "39.50"
    assert book.rating == "9.2"
    assert book.raters == "12345"
    assert book.cover_url == "https://example.com/large.jpg"
    assert book.pubdate == "2011-06"
    assert book.douban_url == "https://book.douban.com/subject/123"
    assert book.pages == "360"

def test_book_from_douban_invalid():
    # 测试无效数据
    assert Book.from_douban({}) is None
    assert Book.from_douban({"isbn13": "123"}) is None

def test_calc_recommend():
    # 测试推荐度计算
    assert Book._calc_recommend("9.0", "10000") > 0
    assert Book._calc_recommend("2.0", "1000") == 0  # 评分太低
    assert Book._calc_recommend("9.0", "0") == 0  # 人数为0
    assert Book._calc_recommend("", "") == 0  # 空值
```

- [ ] **Step 5: 运行测试验证**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS

- [ ] **Step 6: 提交代码**

```bash
git add core/models/ tests/unit/test_models.py
git commit -m "feat: add data models with Book model"
```

---

## Task 6: 业务逻辑 - 豆瓣 API 服务

**Files:**
- Create: `core/services/__init__.py`
- Create: `core/services/douban.py`
- Test: `tests/unit/test_services.py`

- [ ] **Step 1: 创建豆瓣 API 服务**

```python
# core/services/douban.py
"""豆瓣 API 服务"""
import json
import logging
import time
from typing import List, Optional
import requests
from config import get_config
from core.models.book import Book
from core.exceptions import DoubanAPIError, NetworkError

LOG = logging.getLogger(__name__)

# 重试参数
MAX_RETRIES = 3
RETRY_DELAY = 1.0

def _request_with_retry(method: str, url: str, session: requests.Session, **kwargs) -> Optional[requests.Response]:
    """带指数退避重试的 HTTP 请求"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.request(method, url, timeout=10, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            LOG.warning(f"请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt))
    return None

class DoubanService:
    """豆瓣图书 API 服务"""
    
    def __init__(self):
        config = get_config()
        self._session = requests.Session()
        self._session.headers.update({
            "Referer": "https://m.douban.com/tv/american",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
        })
        self._api_key = config.douban.api_key
        self._api_key_search = config.douban.api_key_search
        self._isbn_url = f"{config.douban.book_url}/isbn"
        self._search_url = f"{config.douban.book_url}/search"
    
    def get_book_by_isbn(self, isbn: str) -> Optional[Book]:
        """根据 ISBN 获取图书信息"""
        if not isbn or len(isbn) not in (13, 17):
            return None
        
        url = f"{self._isbn_url}/{isbn}"
        resp = _request_with_retry("POST", url, session=self._session,
                                   data={"apikey": self._api_key})
        if resp is None:
            return None
        
        try:
            book = Book.from_douban(resp.json())
            if book:
                book.isbn = isbn
            return book
        except (json.JSONDecodeError, ValueError) as e:
            LOG.error(f"ISBN {isbn} 解析失败: {e}")
        return None
    
    def search_books(self, keyword: str) -> List[Book]:
        """搜索图书"""
        if not keyword:
            return []
        
        resp = _request_with_retry(
            "GET", self._search_url, session=self._session,
            params={"q": keyword, "apikey": self._api_key_search},
        )
        if resp is None:
            return []
        
        try:
            books = []
            for item in resp.json().get("books", []):
                book = Book.from_douban(item)
                if book:
                    books.append(book)
            return books
        except (json.JSONDecodeError, ValueError) as e:
            LOG.error(f"搜索 '{keyword}' 解析失败: {e}")
        return []
    
    def download_image(self, url: str, referer: str = None) -> Optional[bytes]:
        """下载图片"""
        if not url:
            return None
        
        headers = {}
        if referer:
            headers["Referer"] = referer
        
        resp = _request_with_retry("GET", url, session=self._session, headers=headers)
        if resp is None:
            return None
        return resp.content
```

- [ ] **Step 2: 创建服务初始化**

```python
# core/services/__init__.py
"""服务模块"""
from .douban import DoubanService

__all__ = ["DoubanService"]
```

- [ ] **Step 3: 编写服务测试**

```python
# tests/unit/test_services.py
"""服务测试"""
import pytest
from unittest.mock import Mock, patch
from core.services.douban import DoubanService, _request_with_retry
from core.exceptions import DoubanAPIError, NetworkError

def test_request_with_retry_success():
    mock_session = Mock()
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_session.request.return_value = mock_response
    
    result = _request_with_retry("GET", "http://test.com", mock_session)
    assert result == mock_response
    assert mock_session.request.call_count == 1

def test_request_with_retry_failure():
    mock_session = Mock()
    mock_session.request.side_effect = Exception("网络错误")
    
    result = _request_with_retry("GET", "http://test.com", mock_session)
    assert result is None
    assert mock_session.request.call_count == 3

def test_douban_service_init():
    service = DoubanService()
    assert service._session is not None
    assert "User-Agent" in service._session.headers

def test_douban_service_get_book_by_isbn():
    service = DoubanService()
    
    # 测试无效 ISBN
    assert service.get_book_by_isbn("") is None
    assert service.get_book_by_isbn("123") is None  # 长度不对
```

- [ ] **Step 4: 运行测试验证**

Run: `pytest tests/unit/test_services.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add core/services/ tests/unit/test_services.py
git commit -m "feat: add DoubanService with retry mechanism"
```

---

## Task 7: 测试基础设施

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/books.json`
- Create: `tests/fixtures/config.json`
- Create: `requirements-dev.txt`

- [ ] **Step 1: 创建测试目录结构**

```bash
mkdir -p tests/unit tests/integration tests/fixtures
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/fixtures/__init__.py
```

- [ ] **Step 2: 创建 pytest 配置**

```python
# tests/conftest.py
"""pytest 配置"""
import os
import tempfile
import pytest
from config import init_config
from core.repositories.book_repo import BookRepository

@pytest.fixture(scope="session")
def test_config():
    """测试配置"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"database_path": ":memory:"}')
        config_path = f.name
    
    init_config(config_path)
    yield
    
    os.unlink(config_path)

@pytest.fixture
def temp_db():
    """临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    repo = BookRepository(db_path)
    yield repo
    
    os.unlink(db_path)

@pytest.fixture
def sample_books():
    """示例图书数据"""
    return [
        {"isbn": "9787544291163", "title": "百年孤独", "author": "加西亚·马尔克斯"},
        {"isbn": "9787530217337", "title": "活着", "author": "余华"},
        {"isbn": "9787544270878", "title": "1984", "author": "乔治·奥威尔"},
    ]
```

- [ ] **Step 3: 创建测试数据**

```json
// tests/fixtures/books.json
[
  {
    "isbn": "9787544291163",
    "title": "百年孤独",
    "author": "加西亚·马尔克斯",
    "publisher": "南海出版公司",
    "price": "39.50",
    "rating": "9.2",
    "raters": "12345",
    "status": "默认"
  },
  {
    "isbn": "9787530217337",
    "title": "活着",
    "author": "余华",
    "publisher": "作家出版社",
    "price": "28.00",
    "rating": "9.4",
    "raters": "23456",
    "status": "已读"
  }
]
```

```json
// tests/fixtures/config.json
{
  "name": "TestApp",
  "database_path": ":memory:",
  "web_port": 9000
}
```

- [ ] **Step 4: 创建开发依赖**

```text
# requirements-dev.txt
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
black>=23.0.0
flake8>=6.0.0
mypy>=1.0.0
```

- [ ] **Step 5: 提交代码**

```bash
git add tests/ requirements-dev.txt
git commit -m "feat: add test infrastructure and fixtures"
```

---

## Task 8: 容器化部署

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Create: `deploy/nginx.conf`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
# Dockerfile
# 多阶段构建

# 构建阶段
FROM python:3.12-slim as builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 运行阶段
FROM python:3.12-slim

WORKDIR /app

# 创建非 root 用户
RUN groupadd -r bookeeper && useradd -r -g bookeeper bookeeper

# 从构建阶段复制依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/data /app/backups /app/covers && \
    chown -R bookeeper:bookeeper /app

# 切换到非 root 用户
USER bookeeper

# 暴露端口
EXPOSE 8899

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8899/')" || exit 1

# 启动命令
CMD ["python", "main.py"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
# docker-compose.yml
version: '3.8'

services:
  bookeeper:
    build: .
    container_name: bookeeper
    ports:
      - "8899:8899"
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
      - ./covers:/app/covers
      - ./config.json:/app/config.json
    environment:
      - BOOKEEPER_DATABASE_PATH=/app/data/books.db
      - BOOKEEPER_WEB_HOST=0.0.0.0
    restart: unless-stopped
    networks:
      - bookeeper-network

  nginx:
    image: nginx:alpine
    container_name: bookeeper-nginx
    ports:
      - "80:80"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - bookeeper
    restart: unless-stopped
    networks:
      - bookeeper-network
    profiles:
      - with-nginx

networks:
  bookeeper-network:
    driver: bridge
```

- [ ] **Step 3: 创建 .dockerignore**

```text
# .dockerignore
.git
.gitignore
__pycache__
*.pyc
*.pyo
*.db
*.ini
*.log
backups/
covers/
data/
.superpowers/
.vscode/
.idea/
*.md
!requirements.txt
```

- [ ] **Step 4: 创建 Nginx 配置**

```nginx
# deploy/nginx.conf
server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://bookeeper:8899;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /cover/ {
        proxy_pass http://bookeeper:8899;
        proxy_set_header Host $host;
        proxy_set_header Referer https://book.douban.com/;
    }
}
```

- [ ] **Step 5: 提交代码**

```bash
git add Dockerfile docker-compose.yml .dockerignore deploy/
git commit -m "feat: add Docker containerization"
```

---

## 自我审查

### 1. 规范覆盖检查
- [x] 配置管理 (Task 1)
- [x] 异常定义 (Task 2)
- [x] 日志配置 (Task 3)
- [x] Repository 模式 (Task 4)
- [x] 数据模型 (Task 5)
- [x] 豆瓣 API 服务 (Task 6)
- [x] 测试基础设施 (Task 7)
- [x] 容器化部署 (Task 8)

### 2. 占位符扫描
- [x] 所有步骤都包含完整代码
- [x] 没有 TBD、TODO 等占位符
- [x] 测试代码完整

### 3. 类型一致性
- [x] 函数签名一致
- [x] 类名一致
- [x] 模块导入路径一致

计划已完成，可以开始实施。