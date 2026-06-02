# =============================================================================
# 策略注册表 —— 插件化架构入口
# =============================================================================
"""
所有策略通过 @register(name) 装饰器自动注册。
运行时通过 StrategyRegistry.create(name, config, risk, db) 实例化。

使用示例:
    from strategies.registry import StrategyRegistry
    strategy = StrategyRegistry.create("ma_cross", cfg, risk, db)
    # 或批量创建:
    strategies = StrategyRegistry.create_all(["ma_cross", "rsi"], cfg, risk, db)
"""
import logging
from typing import Any, Dict, List, Type

from strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """全局策略注册表。"""

    _registry: Dict[str, Type[BaseStrategy]] = {}

    @classmethod
    def register(cls, name: str):
        """装饰器：将策略类注册到全局表。"""
        def decorator(strategy_cls: Type[BaseStrategy]):
            if not issubclass(strategy_cls, BaseStrategy):
                raise TypeError(f"{strategy_cls.__name__} must inherit BaseStrategy")
            cls._registry[name] = strategy_cls
            logger.info(f"[Registry] 策略已注册: {name} -> {strategy_cls.__name__}")
            return strategy_cls
        return decorator

    @classmethod
    def create(cls, name: str, config: Dict[str, Any], risk_engine: Any, db: Any) -> BaseStrategy:
        """按名称实例化策略。"""
        if name not in cls._registry:
            available = ", ".join(cls.list_strategies())
            raise KeyError(f"未知策略 '{name}'。可用策略: {available}")
        strategy_cls = cls._registry[name]
        return strategy_cls(config, risk_engine, db)

    @classmethod
    def create_all(cls, names: List[str], config: Dict[str, Any], risk_engine: Any, db: Any) -> Dict[str, BaseStrategy]:
        """批量实例化多个策略。"""
        return {n: cls.create(n, config, risk_engine, db) for n in names}

    @classmethod
    def list_strategies(cls) -> List[str]:
        """返回所有已注册策略名称。"""
        return sorted(cls._registry.keys())

    @classmethod
    def describe(cls, name: str) -> Dict[str, Any]:
        """返回策略元信息。"""
        if name not in cls._registry:
            raise KeyError(f"未知策略: {name}")
        strategy_cls = cls._registry[name]
        return {
            "name": name,
            "class": strategy_cls.__name__,
            "module": strategy_cls.__module__,
            "doc": (strategy_cls.__doc__ or "").strip().split("\n")[0],
        }

    @classmethod
    def describe_all(cls) -> Dict[str, Dict[str, Any]]:
        """返回所有策略的元信息。"""
        return {name: cls.describe(name) for name in cls.list_strategies()}
