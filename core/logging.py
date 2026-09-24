"""日志配置模块"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

# 用于标识本模块添加的 handler 的属性名
_OWN_HANDLER_ATTR = "_bookeeper_handler"

# 有效的日志级别
_VALID_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

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


class ContextLoggerAdapter(logging.LoggerAdapter):
    """带上下文的日志适配器
    
    用法：
        logger = ContextLoggerAdapter(get_logger("mylogger"), {"user_id": "123"})
        logger.info("操作完成")  # 日志中自动包含 user_id 上下文
    """
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        extra = kwargs.get("extra", {})
        if self.extra:
            extra.setdefault("context", {}).update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """设置日志配置
    
    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
        log_file: 可选的日志文件路径
    
    Returns:
        配置好的根 logger
    
    Raises:
        ValueError: 当传入无效的日志级别时
    """
    # 校验日志级别
    normalized_level = level.upper()
    if normalized_level not in _VALID_LEVELS:
        raise ValueError(
            f"无效的日志级别: '{level}'。有效值: {', '.join(_VALID_LEVELS)}"
        )
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, normalized_level))
    
    # 移除本模块之前添加的 handlers，保留其他库的 handlers
    for handler in root_logger.handlers[:]:
        if getattr(handler, _OWN_HANDLER_ATTR, False):
            root_logger.removeHandler(handler)
            handler.close()
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter())
    setattr(console_handler, _OWN_HANDLER_ATTR, True)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（可选）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(StructuredFormatter())
        setattr(file_handler, _OWN_HANDLER_ATTR, True)
        root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器"""
    return logging.getLogger(name)
