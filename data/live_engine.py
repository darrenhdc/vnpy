# =============================================================================
# 实时行情引擎 —— Futu API + vn.py 双兼容
# =============================================================================
"""
此模块封装实时行情推送，支持两种后端：
1. **Futu API** (默认): 直接连接 OpenD，轻量稳定
2. **vn.py EventEngine**: 如果安装了 vnpy + vnpy_futu

使用方式:
    from data.live_engine import LiveDataEngine
    engine = LiveDataEngine(futu_config)
    engine.connect()
    engine.subscribe(["US.AAPL"])
    engine.register_bar_callback(my_strategy.on_bar)
    engine.run()        # 阻塞，接收实时推送
    engine.stop()
"""
import sys
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# 尝试导入 Futu API
try:
    from futu import OpenQuoteContext, SubType, KLType
    FUTU_API_AVAILABLE = True
except ImportError:
    FUTU_API_AVAILABLE = False
    logger.warning("[LiveDataEngine] futu-api 未安装")

# 尝试导入 vn.py
try:
    from vnpy.event import EventEngine, Event
    from vnpy.trader.engine import MainEngine
    from vnpy.trader.object import BarData, SubscribeRequest
    from vnpy.trader.constant import Exchange
    VNPY_AVAILABLE = True
except ImportError:
    VNPY_AVAILABLE = False


class LiveDataEngine:
    """
    实时行情引擎封装。
    优先使用 Futu API，回退到 vn.py，最后降级为 mock。
    """

    def __init__(self, futu_config: Dict[str, Any], backend: str = "auto"):
        self.futu_config = futu_config
        self.opend_host = futu_config.get("opend", {}).get("host", "127.0.0.1")
        self.opend_port = futu_config.get("opend", {}).get("port", 11111)

        self._bar_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._tick_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        self._backend: str = backend
        self._quote_ctx: Optional[Any] = None
        self._event_engine: Optional[Any] = None
        self._running = False
        self._subscribed_symbols: List[str] = []

        # 自动选择后端
        if backend == "auto":
            if FUTU_API_AVAILABLE:
                self._backend = "futu"
            elif VNPY_AVAILABLE:
                self._backend = "vnpy"
            else:
                self._backend = "mock"

        logger.info(f"[LiveDataEngine] 选择后端: {self._backend}")

    def connect(self) -> bool:
        """连接行情源。"""
        if self._backend == "futu":
            return self._connect_futu()
        elif self._backend == "vnpy":
            return self._connect_vnpy()
        else:
            logger.warning("[LiveDataEngine] mock 模式，无真实连接")
            return False

    def _connect_futu(self) -> bool:
        try:
            self._quote_ctx = OpenQuoteContext(host=self.opend_host, port=self.opend_port)
            # 注册 K 线推送回调
            self._quote_ctx.set_handler(FutuKLineHandler(self._on_futu_bar))
            logger.info(f"[LiveDataEngine] Futu API 连接成功: {self.opend_host}:{self.opend_port}")
            return True
        except Exception as e:
            logger.error(f"[LiveDataEngine] Futu API 连接失败: {e}")
            return False

    def _connect_vnpy(self) -> bool:
        """vn.py 连接（保留接口）。"""
        try:
            from vnpy_futu import FutuGateway
        except ImportError:
            logger.warning("[LiveDataEngine] vnpy_futu 未安装")
            return False

        self._event_engine = EventEngine()
        main_engine = MainEngine(self._event_engine)
        main_engine.add_gateway(FutuGateway)

        setting = {
            "address": self.opend_host,
            "port": str(self.opend_port),
            "password": self.futu_config.get("trade_password", ""),
            "env": self.futu_config.get("environment", "SIMULATE"),
        }
        try:
            main_engine.connect(setting, "FUTU")
            self._event_engine.register("EVENT_BAR", self._on_vnpy_bar)
            self._event_engine.start()
            logger.info("[LiveDataEngine] vn.py Gateway 连接成功")
            return True
        except Exception as e:
            logger.error(f"[LiveDataEngine] vn.py 连接失败: {e}")
            return False

    def subscribe(self, symbols: List[str]):
        """订阅标的行情。"""
        self._subscribed_symbols = symbols
        if self._backend == "futu" and self._quote_ctx:
            # Futu API 订阅
            ret, err = self._quote_ctx.subscribe(symbols, [SubType.K_1M], subscribe_push=True)
            if ret == 0:
                logger.info(f"[LiveDataEngine] 已订阅: {symbols}")
            else:
                logger.error(f"[LiveDataEngine] 订阅失败: {err}")
        elif self._backend == "vnpy":
            # vn.py 订阅（保留接口）
            pass

    def register_bar_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self._bar_callbacks.append(callback)

    def register_tick_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self._tick_callbacks.append(callback)

    def _on_futu_bar(self, bar_dict: Dict[str, Any]):
        """Futu API K 线推送回调。"""
        # bar_dict 格式: {"code": "US.AAPL", "time_key": "...", "open": ..., ...}
        symbol = bar_dict.get("code", "")
        normalized = {
            "symbol": symbol,
            "interval": "1m",
            "timestamp": bar_dict.get("time_key", ""),
            "open": float(bar_dict.get("open", 0)),
            "high": float(bar_dict.get("high", 0)),
            "low": float(bar_dict.get("low", 0)),
            "close": float(bar_dict.get("close", 0)),
            "volume": int(bar_dict.get("volume", 0)),
        }
        for cb in self._bar_callbacks:
            try:
                cb(normalized)
            except Exception as e:
                logger.error(f"[LiveDataEngine] bar callback 异常: {e}")

    def _on_vnpy_bar(self, event: Any):
        """vn.py bar 回调（保留）。"""
        bar: BarData = event.data
        normalized = {
            "symbol": f"{bar.exchange.value}.{bar.symbol}",
            "interval": "1m",
            "timestamp": bar.datetime.isoformat() if bar.datetime else "",
            "open": bar.open_price,
            "high": bar.high_price,
            "low": bar.low_price,
            "close": bar.close_price,
            "volume": bar.volume,
        }
        for cb in self._bar_callbacks:
            cb(normalized)

    def run(self):
        """启动主循环（阻塞）。"""
        self._running = True
        logger.info("[LiveDataEngine] 进入主循环，等待行情推送...")
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("[LiveDataEngine] 收到中断信号")
        finally:
            self.stop()

    def stop(self):
        """停止引擎。"""
        self._running = False
        if self._quote_ctx:
            self._quote_ctx.close()
            logger.info("[LiveDataEngine] Futu API 连接已关闭")
        if self._event_engine:
            self._event_engine.stop()
            logger.info("[LiveDataEngine] vn.py EventEngine 已停止")


class FutuKLineHandler:
    """Futu API K 线推送处理器。"""

    def __init__(self, callback: Callable):
        self.callback = callback

    def on_recv_rsp(self, rsp_pb):
        """Futu API 回调入口。"""
        from futu import RET_OK
        ret_code, data = rsp_pb
        if ret_code != RET_OK:
            logger.warning(f"[FutuHandler] K线推送错误: {data}")
            return
        # data 是 DataFrame，每行是一条 K 线
        for _, row in data.iterrows():
            self.callback(row.to_dict())
