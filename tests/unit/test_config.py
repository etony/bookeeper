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