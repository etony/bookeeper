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
        
        # 关闭所有处理器以释放文件锁
        for handler in logger.handlers:
            handler.close()
        
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
