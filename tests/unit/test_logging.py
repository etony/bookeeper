"""日志配置测试"""
import json
import logging
import tempfile
import os
import pytest
from core.logging import setup_logging, get_logger, StructuredFormatter


@pytest.fixture(autouse=True)
def preserve_root_logger():
    """保存/恢复根 logger 的 handlers 和 level，确保测试隔离"""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    # 恢复原始状态
    root.handlers.clear()
    root.handlers.extend(original_handlers)
    root.setLevel(original_level)


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
    root = logging.getLogger()
    before = len(root.handlers)
    logger = setup_logging(level="DEBUG")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == before + 1  # 新增 1 个控制台处理器


def test_setup_logging_with_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        log_file = f.name
    
    try:
        root = logging.getLogger()
        before = len(root.handlers)
        logger = setup_logging(level="INFO", log_file=log_file)
        assert len(logger.handlers) == before + 2  # 新增控制台 + 文件处理器
        
        test_logger = get_logger("test")
        test_logger.info("测试日志消息")
        
        # 关闭本模块添加的处理器以释放文件锁
        from core.logging import _OWN_HANDLER_ATTR
        for handler in logger.handlers:
            if getattr(handler, _OWN_HANDLER_ATTR, False):
                handler.close()
        
        # 验证日志文件内容
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            data = json.loads(content)
            assert data["message"] == "测试日志消息"
    finally:
        os.unlink(log_file)


def test_setup_logging_invalid_level():
    with pytest.raises(ValueError, match="无效的日志级别"):
        setup_logging(level="FOOBAR")


def test_setup_logging_preserves_other_handlers():
    """验证 setup_logging 不会清除其他库的 handlers"""
    root = logging.getLogger()
    # 添加一个不属于本模块的 handler
    dummy_handler = logging.StreamHandler()
    dummy_handler.set_name("external_handler")
    root.addHandler(dummy_handler)
    
    setup_logging(level="INFO")
    
    # dummy_handler 应该保留
    remaining = [h for h in root.handlers if h.get_name() == "external_handler"]
    assert len(remaining) == 1


def test_get_logger():
    logger = get_logger("test.module")
    assert logger.name == "test.module"
    assert isinstance(logger, logging.Logger)
