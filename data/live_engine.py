# =============================================================================
# vn.py EventEngine 实时行情连接器
# =============================================================================
"""
此模块封装 vn.py 的 EventEngine 和 FutuGateway，用于接收实时行情推送。

使用方式:
    from data.live_engine import LiveDataEngine
    engine = LiveDataEngine(futu_config)
    engine.connect()
    engine.subscribe(["US.AAPL", "US.SPY"])
    engine.register_bar_callback(my_strategy.on_bar)
    engine.run()

注意事项:
- 需要安装 vnpy 和 vnpy_futu
- 需要 Futu OpenD 已启动
- 不需要在代码中写死 API Key（OpenD 端处理登录）
"""
import sys
import logging
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from vnpy.event import EventEngine, Event
    from vnpy.trader.engine import MainEngine
    from vnpy.trader.object import BarData, TickData, SubscribeRequest
    from vnpy.trader.constant import Exchange
    VNPY_AVAILABLE = True
except ImportError:
    VNPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class LiveDataEngine:
    """
    实时行情引擎封装。
    如果 vn.py 未安装，自动降级为 mock 模式（仅打印日志）。
    """

    def __init__(self, futu_config: Dict[str, Any]):
        self.futu_config = futu_config
        self.opend_host = futu_config.get("opend", {}).get("host", "127.0.0.1")
        self.opend_port = futu_config.get("opend", {}).get("port", 11111)
        self.password = futu_config.get("trade_password", "")
        self.env = futu_config.get("environment", "SIMULATE")

        self._bar_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._tick_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        self.event_engine: Optional[Any] = None
        self.main_engine: Optional[Any] = None
        self.gateway: Optional[Any] = None
        self._connected = False

    def connect(self) -> bool:
        """连接 Futu Gateway。"""
        if not VNPY_AVAILABLE:
            logger.warning("[LiveDataEngine] vn.py 未安装，进入 mock 模式")
            return False

        try:
            from vnpy_futu import FutuGateway
        except ImportError:
            logger.warning("[LiveDataEngine] vnpy_futu 未安装，进入 mock 模式")
            return False

        logger.info(f"[LiveDataEngine] 连接 Futu OpenD: {self.opend_host}:{self.opend_port} env={self.env}")

        self.event_engine = EventEngine()
        self.main_engine = MainEngine(self.event_engine)
        self.main_engine.add_gateway(FutuGateway)

        setting = {
            "address": self.opend_host,
            "port": str(self.opend_port),
            "password": self.password,
            "env": self.env,
        }

        try:
            self.main_engine.connect(setting, "FUTU")
        except Exception as e:
            logger.error(f"[LiveDataEngine] Gateway 连接失败: {e}")
            return False

        # 注册事件监听
        self.event_engine.register("EVENT_BAR", self._on_bar_event)
        self.event_engine.register("EVENT_TICK", self._on_tick_event)
        self.event_engine.register("EVENT_LOG", self._on_log_event)

        self._connected = True
        logger.info("[LiveDataEngine] Gateway 连接成功，事件监听已注册")
        return True

    def subscribe(self, symbols: List[str], interval: str = "1m"):
        """
        订阅标的行情。
        symbols 格式: ["US.AAPL", "US.SPY"]
        interval: vn.py 的 K线周期格式
        """
        if not self._connected or not self.main_engine:
            logger.warning("[LiveDataEngine] 未连接，无法订阅")
            return

        for sym in symbols:
            parts = sym.split(".")
            if len(parts) != 2:
                logger.warning(f"[LiveDataEngine] 标的格式错误: {sym}")
                continue
            exchange_str, ticker = parts
            # 映射 exchange
            exchange = self._map_exchange(exchange_str)

            req = SubscribeRequest(
                symbol=ticker,
                exchange=exchange,
            )
            try:
                self.main_engine.subscribe(req, "FUTU")
                logger.info(f"[LiveDataEngine] 已订阅: {sym}")
            except Exception as e:
                logger.error(f"[LiveDataEngine] 订阅失败 {sym}: {e}")

    def register_bar_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """注册 bar 回调函数。"""
        self._bar_callbacks.append(callback)

    def register_tick_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """注册 tick 回调函数。"""
        self._tick_callbacks.append(callback)

    def _on_bar_event(self, event: Any):
        """处理 vn.py EVENT_BAR。"""
        bar: BarData = event.data
        bar_dict = {
            "symbol": f"{bar.exchange.value}.{bar.symbol}",
            "interval": bar.interval.value if hasattr(bar.interval, "value") else str(bar.interval),
            "timestamp": bar.datetime.isoformat() if bar.datetime else "",
            "open": bar.open_price,
            "high": bar.high_price,
            "low": bar.low_price,
            "close": bar.close_price,
            "volume": bar.volume,
        }
        for cb in self._bar_callbacks:
            try:
                cb(bar_dict)
            except Exception as e:
                logger.error(f"[LiveDataEngine] bar callback 异常: {e}")

    def _on_tick_event(self, event: Any):
        """处理 vn.py EVENT_TICK。"""
        tick: TickData = event.data
        tick_dict = {
            "symbol": f"{tick.exchange.value}.{tick.symbol}",
            "timestamp": tick.datetime.isoformat() if tick.datetime else "",
            "last_price": tick.last_price,
            "volume": tick.volume,
            "bid_price_1": tick.bid_price_1,
            "ask_price_1": tick.ask_price_1,
        }
        for cb in self._tick_callbacks:
            try:
                cb(tick_dict)
            except Exception as e:
                logger.error(f"[LiveDataEngine] tick callback 异常: {e}")

    def _on_log_event(self, event: Any):
        """转发 vn.py 日志。"""
        log = event.data
        logger.info(f"[vnpy] {log.msg}")

    def _map_exchange(self, exchange_str: str) -> Any:
        """映射内部市场代码到 vn.py Exchange。"""
        if not VNPY_AVAILABLE:
            return None
        mapping = {
            "US": Exchange.SMART,
            "HK": Exchange.SEHK,
            "SH": Exchange.SSE,
            "SZ": Exchange.SZSE,
        }
        return mapping.get(exchange_str.upper(), Exchange.SMART)

    def run(self):
        """启动事件引擎主循环（阻塞）。"""
        if self.event_engine:
            self.event_engine.start()
            logger.info("[LiveDataEngine] EventEngine 已启动")
        else:
            logger.warning("[LiveDataEngine] 无 EventEngine，跳过 run()")

    def stop(self):
        """停止引擎。"""
        if self.event_engine:
            self.event_engine.stop()
        if self.main_engine:
            self.main_engine.close()
        self._connected = False
        logger.info("[LiveDataEngine] 已停止")
