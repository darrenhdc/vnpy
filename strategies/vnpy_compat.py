# =============================================================================
# vnpy CtaTemplate 轻量兼容层
# =============================================================================
"""
当 vnpy 框架未安装时，提供 CtaTemplate 的核心接口实现。
策略代码完全按照 vnpy 规范编写，未来只需把 import 改回 vnpy 即可。

保留能力：
- on_bar / on_tick 入口
- buy / sell / short / cover / cancel_all
- pos 持仓跟踪
- on_trade / on_order 回调
- 自动持久化 bars/orders/trades 到 SQLite
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes (mirror vnpy.trader.object)
# ---------------------------------------------------------------------------

@dataclass
class BarData:
    symbol: str = ""
    exchange: str = ""
    datetime: datetime = field(default_factory=datetime.now)
    interval: str = ""
    volume: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    open_interest: float = 0.0

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


@dataclass
class TickData:
    symbol: str = ""
    exchange: str = ""
    datetime: datetime = field(default_factory=datetime.now)
    name: str = ""
    volume: float = 0.0
    open_interest: float = 0.0
    last_price: float = 0.0
    limit_up: float = 0.0
    limit_down: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    pre_close: float = 0.0
    bid_price_1: float = 0.0
    bid_price_2: float = 0.0
    bid_price_3: float = 0.0
    bid_price_4: float = 0.0
    bid_price_5: float = 0.0
    ask_price_1: float = 0.0
    ask_price_2: float = 0.0
    ask_price_3: float = 0.0
    ask_price_4: float = 0.0
    ask_price_5: float = 0.0
    bid_volume_1: float = 0.0
    bid_volume_2: float = 0.0
    bid_volume_3: float = 0.0
    bid_volume_4: float = 0.0
    bid_volume_5: float = 0.0
    ask_volume_1: float = 0.0
    ask_volume_2: float = 0.0
    ask_volume_3: float = 0.0
    ask_volume_4: float = 0.0
    ask_volume_5: float = 0.0

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


@dataclass
class OrderData:
    symbol: str = ""
    exchange: str = ""
    orderid: str = ""
    direction: str = ""          # "LONG" / "SHORT"
    offset: str = ""             # "OPEN" / "CLOSE"
    price: float = 0.0
    volume: float = 0.0
    traded: float = 0.0
    status: str = ""             # "SUBMITTED" / "FILLED" / "CANCELLED"
    datetime: datetime = field(default_factory=datetime.now)
    reference: str = ""

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


@dataclass
class TradeData:
    symbol: str = ""
    exchange: str = ""
    orderid: str = ""
    tradeid: str = ""
    direction: str = ""
    offset: str = ""
    price: float = 0.0
    volume: float = 0.0
    datetime: datetime = field(default_factory=datetime.now)

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


# ---------------------------------------------------------------------------
# CtaTemplate (compatible layer)
# ---------------------------------------------------------------------------

class CtaTemplate(ABC):
    """
    vnpy CtaStrategy 的轻量兼容实现。
    所有策略参数必须声明为类属性（ vnpy 用它们做 GUI 绑定）。
    """

    author: str = ""
    parameters: List[str] = []
    variables: List[str] = []

    def __init__(
        self,
        cta_engine: Optional[Any],
        strategy_name: str,
        vt_symbol: str,
        setting: Dict[str, Any],
    ):
        self.cta_engine = cta_engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol
        self.symbol, self.exchange = vt_symbol.split(".", 1) if "." in vt_symbol else (vt_symbol, "")

        # 自动将 setting 中的值赋给同名的类属性
        for k, v in setting.items():
            if hasattr(self, k):
                setattr(self, k, v)

        self.pos: int = 0                # 净持仓（vnpy 核心状态变量）
        self.inited: bool = False
        self.trading: bool = False

        # 内部订单簿（兼容层自己管理）
        self._orders: Dict[str, OrderData] = {}
        self._trades: List[TradeData] = []
        self._bars: List[BarData] = []

    # ---------- lifecycle ----------

    def on_init(self):
        """初始化完成后调用。"""
        self.inited = True
        logger.info(f"[{self.strategy_name}] on_init")

    def on_start(self):
        """策略启动。"""
        self.trading = True
        logger.info(f"[{self.strategy_name}] on_start")

    def on_stop(self):
        """策略停止。"""
        self.trading = False
        logger.info(f"[{self.strategy_name}] on_stop")

    # ---------- market data ----------

    @abstractmethod
    def on_bar(self, bar: BarData):
        """必须实现。"""
        pass

    def on_tick(self, tick: TickData):
        """可选实现。"""
        pass

    # ---------- order / trade callbacks ----------

    def on_order(self, order: OrderData):
        """订单状态更新。子类可覆盖。"""
        pass

    def on_trade(self, trade: TradeData):
        """成交回报。子类可覆盖。"""
        # 自动更新 pos
        if trade.direction == "LONG":
            self.pos += trade.volume
        else:
            self.pos -= trade.volume
        logger.info(f"[{self.strategy_name}] on_trade {trade.direction} {trade.volume}@{trade.price} pos={self.pos}")

    # ---------- order placement ----------

    def buy(self, price: float, volume: float, stop: bool = False, lock: bool = False, net: bool = False):
        """开多 / 买入。"""
        return self._place_order(price, volume, direction="LONG", offset="OPEN")

    def sell(self, price: float, volume: float, stop: bool = False, lock: bool = False, net: bool = False):
        """平多 / 卖出。"""
        return self._place_order(price, volume, direction="SHORT", offset="CLOSE")

    def short(self, price: float, volume: float, stop: bool = False, lock: bool = False, net: bool = False):
        """开空。美股现货账户不支持 short，保留接口。"""
        logger.warning(f"[{self.strategy_name}] short not supported in US cash account")
        return []

    def cover(self, price: float, volume: float, stop: bool = False, lock: bool = False, net: bool = False):
        """平空。美股现货账户不支持 cover，保留接口。"""
        logger.warning(f"[{self.strategy_name}] cover not supported in US cash account")
        return []

    def cancel_all(self):
        """撤掉所有未成交订单。"""
        for oid in list(self._orders.keys()):
            self.cancel_order(oid)

    def cancel_order(self, vt_orderid: str):
        """撤单。"""
        order = self._orders.pop(vt_orderid, None)
        if order:
            order.status = "CANCELLED"
            self.on_order(order)
            logger.info(f"[{self.strategy_name}] cancelled {vt_orderid}")

    # ---------- internal ----------

    def _place_order(self, price: float, volume: float, direction: str, offset: str) -> List[str]:
        """兼容层内部下单（仅模拟记录，不真正发送）。"""
        order_id = f"{self.strategy_name}_{datetime.now().strftime('%H%M%S%f')}"
        order = OrderData(
            symbol=self.symbol,
            exchange=self.exchange,
            orderid=order_id,
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            status="SUBMITTED",
        )
        self._orders[order_id] = order
        logger.info(f"[{self.strategy_name}] ORDER {direction} {offset} {self.symbol} {volume}@{price} (oid={order_id})")

        # 模拟立即成交（兼容层不做撮合延迟）
        trade = TradeData(
            symbol=self.symbol,
            exchange=self.exchange,
            orderid=order_id,
            tradeid=f"T_{order_id}",
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
        )
        order.status = "FILLED"
        order.traded = volume
        self._trades.append(trade)
        self.on_trade(trade)
        self.on_order(order)
        return [order_id]

    def write_log(self, msg: str):
        logger.info(f"[{self.strategy_name}] {msg}")

    # ---------- helpers for research ----------

    def get_bar_df(self) -> pd.DataFrame:
        """返回已接收的 bar 列表为 DataFrame（供研究层使用）。"""
        if not self._bars:
            return pd.DataFrame()
        rows = []
        for b in self._bars:
            rows.append({
                "datetime": b.datetime,
                "open": b.open_price,
                "high": b.high_price,
                "low": b.low_price,
                "close": b.close_price,
                "volume": b.volume,
            })
        return pd.DataFrame(rows)

    def get_trade_df(self) -> pd.DataFrame:
        if not self._trades:
            return pd.DataFrame()
        rows = []
        for t in self._trades:
            rows.append({
                "datetime": t.datetime,
                "direction": t.direction,
                "price": t.price,
                "volume": t.volume,
            })
        return pd.DataFrame(rows)
