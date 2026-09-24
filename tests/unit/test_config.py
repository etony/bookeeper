# 配置管理测试
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

def test_config_validation_range():
    """测试配置验证的范围检查"""
    from config.schema import ConfigSchema, ConfigField
    
    schema = ConfigSchema()
    schema.add_field(ConfigField("port", int, min_value=1024, max_value=65535, default=8080))
    
    # 测试有效值
    validated = schema.validate({"port": 8080})
    assert validated["port"] == 8080
    
    # 测试最小值边界
    validated = schema.validate({"port": 1024})
    assert validated["port"] == 1024
    
    # 测试最大值边界
    validated = schema.validate({"port": 65535})
    assert validated["port"] == 65535
    
    # 测试超出范围
    with pytest.raises(ValueError, match="值过小"):
        schema.validate({"port": 1023})
    
    with pytest.raises(ValueError, match="值过大"):
        schema.validate({"port": 65536})

def test_config_validation_string_length():
    """测试配置验证的字符串长度检查"""
    from config.schema import ConfigSchema, ConfigField
    
    schema = ConfigSchema()
    schema.add_field(ConfigField("name", str, min_length=2, max_length=10, default="default"))
    
    # 测试有效长度
    validated = schema.validate({"name": "test"})
    assert validated["name"] == "test"
    
    # 测试最小长度边界
    validated = schema.validate({"name": "ab"})
    assert validated["name"] == "ab"
    
    # 测试最大长度边界
    validated = schema.validate({"name": "1234567890"})
    assert validated["name"] == "1234567890"
    
    # 测试超出范围
    with pytest.raises(ValueError, match="长度过短"):
        schema.validate({"name": "a"})
    
    with pytest.raises(ValueError, match="长度过长"):
        schema.validate({"name": "12345678901"})

def test_config_file_corrupted():
    """测试配置文件损坏时的错误处理"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"name": "TestApp", "invalid": json}')
        config_path = f.name
    
    try:
        # 应该能够处理损坏的文件，使用默认配置
        manager = ConfigManager(config_path)
        config = manager.config
        # 应该使用默认配置
        assert config.name == "Bookeeper"
    finally:
        os.unlink(config_path)

def test_config_validation_failure_fallback():
    """测试配置验证失败时的回退"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        # 写入无效的端口号（超出范围）
        f.write('{"web_port": 99999}')
        config_path = f.name
    
    try:
        # 应该能够处理验证失败，使用默认配置
        manager = ConfigManager(config_path)
        config = manager.config
        # 应该使用默认端口
        assert config.web.port == 8899
    finally:
        os.unlink(config_path)