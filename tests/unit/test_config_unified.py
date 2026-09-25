"""配置系统统一测试"""
import os
import tempfile
import pytest
from config import ConfigManager, get_config, init_config, Config
from config.defaults import AppConfig, DEFAULT_CONFIG


class TestConfigSingleton:
    """测试配置单例模式"""

    def test_get_config_returns_same_instance(self):
        """get_config 多次调用返回同一个 ConfigManager"""
        mgr1 = init_config()
        mgr2 = get_config()
        assert mgr1 is mgr2

    def test_init_config_resets_instance(self):
        """init_config 重新初始化后返回新实例"""
        mgr1 = init_config()
        mgr2 = init_config()
        assert mgr1 is not mgr2


class TestConfigManagerInit:
    """测试 ConfigManager 初始化"""

    def test_default_init(self):
        """默认初始化使用默认配置"""
        mgr = ConfigManager()
        cfg = mgr.config
        assert cfg.name == "Bookeeper"
        assert cfg.version == "3.0.0"
        assert cfg.web.port == 8899

    def test_init_with_file(self):
        """从配置文件加载"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"name": "TestApp", "web_port": 9000}')
            path = f.name
        try:
            mgr = ConfigManager(path)
            cfg = mgr.config
            assert cfg.name == "TestApp"
            assert cfg.web.port == 9000
        finally:
            os.unlink(path)

    def test_reload(self):
        """reload 重新加载配置"""
        mgr = ConfigManager()
        assert mgr.config.name == "Bookeeper"
        mgr.reload()
        assert mgr.config.name == "Bookeeper"


class TestEnvOverride:
    """测试环境变量覆盖配置"""

    def test_env_overrides_file(self):
        """环境变量优先于配置文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"name": "FileApp"}')
            path = f.name
        try:
            os.environ["BOOKEEPER_NAME"] = "EnvApp"
            mgr = ConfigManager(path)
            assert mgr.config.name == "EnvApp"
        finally:
            os.unlink(path)
            os.environ.pop("BOOKEEPER_NAME", None)

    def test_env_overrides_default(self):
        """环境变量优先于默认值"""
        os.environ["BOOKEEPER_WEB_PORT"] = "7777"
        try:
            mgr = ConfigManager()
            assert mgr.config.web.port == 7777
        finally:
            os.environ.pop("BOOKEEPER_WEB_PORT", None)

    def test_env_type_conversion(self):
        """环境变量正确转换类型"""
        os.environ["BOOKEEPER_WEB_PORT"] = "8080"
        os.environ["BOOKEEPER_TEST_BOOL"] = "true"
        try:
            from config.env import EnvLoader
            env = EnvLoader.load()
            assert env["web_port"] == 8080
            assert env["test_bool"] is True
        finally:
            os.environ.pop("BOOKEEPER_WEB_PORT", None)
            os.environ.pop("BOOKEEPER_TEST_BOOL", None)


class TestConfigValidation:
    """测试配置验证"""

    def test_port_range_validation(self):
        """端口范围验证"""
        from config.schema import ConfigSchema, ConfigField
        schema = ConfigSchema()
        schema.add_field(ConfigField("port", int, min_value=1024, max_value=65535, default=8080))

        assert schema.validate({"port": 8080})["port"] == 8080
        assert schema.validate({"port": 1024})["port"] == 1024
        assert schema.validate({"port": 65535})["port"] == 65535

        with pytest.raises(ValueError, match="值过小"):
            schema.validate({"port": 1023})
        with pytest.raises(ValueError, match="值过大"):
            schema.validate({"port": 65536})

    def test_corrupted_file_fallback(self):
        """损坏的配置文件回退到默认值"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"name": "TestApp", "invalid": json}')
            path = f.name
        try:
            mgr = ConfigManager(path)
            assert mgr.config.name == "Bookeeper"
        finally:
            os.unlink(path)

    def test_validation_failure_fallback(self):
        """验证失败时回退到默认值"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"web_port": 99999}')
            path = f.name
        try:
            mgr = ConfigManager(path)
            assert mgr.config.web.port == 8899
        finally:
            os.unlink(path)


class TestDeprecatedConfig:
    """测试旧 Config 类的兼容性"""

    def test_config_has_required_attributes(self):
        """旧 Config 类保留所有必要属性"""
        assert hasattr(Config, 'APP_NAME')
        assert hasattr(Config, 'APP_VERSION')
        assert hasattr(Config, 'DB_PATH')
        assert hasattr(Config, 'WEB_PORT')
        assert hasattr(Config, 'DOUBAN_API_KEY')
        assert hasattr(Config, 'DOUBAN_API_KEY_SEARCH')
        assert hasattr(Config, 'HEADERS')
        assert hasattr(Config, 'TABLE_COLUMNS')
        assert hasattr(Config, 'STATUSES')
        assert hasattr(Config, 'BACKUP_KEEP')
        assert hasattr(Config, 'BACKUP_INTERVAL_MS')

    def test_config_load_from_config_manager(self):
        """Config 可以从 ConfigManager 加载配置（已移除，改为直接使用 ConfigManager）"""
        mgr = ConfigManager()
        assert mgr.config.name == "Bookeeper"
        assert mgr.config.version == "3.0.0"
        assert mgr.config.database.path == "books.db"
        assert mgr.config.web.port == 8899
        assert mgr.config.douban.api_key == "0ab215a8b1977939201640fa14c66bab"
        assert mgr.config.douban.api_key_search == "0ac44ae016490db2204ce0a042db2916"
        assert mgr.config.backup.keep == 30
        assert mgr.config.backup.interval_ms == 300000

    def test_legacy_key_names_compat(self):
        """旧版 config.json 大写键名（DOUBAN_API_KEY）仍能被读取"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"DOUBAN_API_KEY": "legacy_key_123"}')
            path = f.name
        try:
            mgr = ConfigManager(path)
            assert mgr.config.douban.api_key == "legacy_key_123"
        finally:
            os.unlink(path)

    def test_init_config_applies_to_legacy_config(self):
        """init_config 把配置回写到旧 Config 静态类（config.json/环境变量真正生效）"""
        import json
        # database_path 也写入：回写的 DB_PATH 必须仍是 conftest 钳制的临时库
        isolated_db = Config.DB_PATH
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"web_port": 9100, "douban_api_key": "test_key_xyz",
                       "backup_keep": 7, "database_path": isolated_db}, f)
            path = f.name
        try:
            init_config(path)
            assert Config.WEB_PORT == 9100
            assert Config.DOUBAN_API_KEY == "test_key_xyz"
            assert Config.BACKUP_KEEP == 7
            assert Config.DB_PATH == isolated_db
        finally:
            os.unlink(path)
        # conftest 的 _isolate_config 会在测试后还原 Config 静态类
