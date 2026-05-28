# =============================================================================
# 配置读取模块
# =============================================================================
import os
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"


def get_config_path(name: str) -> Path:
    """获取配置文件路径，如不存在则提示复制 example 文件。"""
    config_file = CONFIG_DIR / f"{name}.yaml"
    if not config_file.exists():
        example_file = CONFIG_DIR / f"{name}.example.yaml"
        if example_file.exists():
            print(f"[Config] 配置文件 {config_file.name} 不存在。")
            print(f"[Config] 请先复制: cp config/{example_file.name} config/{config_file.name}")
            print(f"[Config] 并根据您的环境修改配置。")
        else:
            print(f"[Config] 配置文件 {config_file.name} 及对应 example 均不存在。")
        sys.exit(1)
    return config_file


def load_yaml(path: Path) -> Dict[str, Any]:
    """读取 YAML 文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(name: str) -> Dict[str, Any]:
    """按名称加载配置。"""
    path = get_config_path(name)
    return load_yaml(path)


class AppConfig:
    """统一配置入口。"""

    def __init__(self):
        self.futu: Dict[str, Any] = load_config("futu")
        self.risk: Dict[str, Any] = load_config("risk")
        self.strategy: Dict[str, Any] = load_config("strategy")

    def is_simulate(self) -> bool:
        env = self.futu.get("environment", "SIMULATE")
        return str(env).upper() == "SIMULATE"

    def ensure_simulate(self) -> None:
        """强制检查当前环境为模拟盘，否则退出。"""
        if not self.is_simulate():
            print("[Config] 致命错误: 当前配置 environment 不是 SIMULATE。")
            print("[Config] 如需实盘，请手动修改代码并充分测试。")
            sys.exit(1)


# 单例
_app_config: Optional[AppConfig] = None


def get_app_config() -> AppConfig:
    global _app_config
    if _app_config is None:
        _app_config = AppConfig()
    return _app_config
