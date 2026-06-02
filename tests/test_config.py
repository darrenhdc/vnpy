# =============================================================================
# 测试: 配置读取
# =============================================================================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import load_config, get_app_config, AppConfig


class TestConfig:
    def test_load_example_configs(self):
        """确认所有 example 配置文件可正常读取。"""
        futu = load_config("futu")
        assert futu is not None
        assert futu.get("environment") == "SIMULATE"

        risk = load_config("risk")
        assert risk is not None
        assert "single_order" in risk

        strategy = load_config("strategy")
        assert strategy is not None

    def test_app_config_singleton(self):
        cfg1 = get_app_config()
        cfg2 = get_app_config()
        assert cfg1 is cfg2
        assert cfg1.is_simulate() is True

    def test_ensure_simulate_raises_on_real(self, monkeypatch):
        """模拟 REAL 环境时 ensure_simulate 应退出。"""
        cfg = get_app_config()
        original_env = cfg.futu.get("environment")
        cfg.futu["environment"] = "REAL"

        import pytest
        with pytest.raises(SystemExit) as exc_info:
            cfg.ensure_simulate()
        assert exc_info.value.code == 1

        cfg.futu["environment"] = original_env
