# =============================================================================
# 策略基类 — 支持 dry_run / paper trading / 真实 Futu 下单 / PnL 追踪
# =============================================================================
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from data.database import Database
from risk.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    def __init__(self, name: str, config: Dict[str, Any], risk_engine: RiskEngine, db: Database):
        self.name = name
        self.config = config
        self.risk = risk_engine
        self.db = db

        self.symbols: List[str] = config.get("symbols", [])
        self.interval: str = config.get("interval", "1m")
        self.order_amount_usd: float = config.get("order_amount_usd", 3000.0)
        self.limit_price_offset: float = config.get("limit_price_offset", 0.01)
        self.check_risk: bool = config.get("check_risk_before_order", True)
        self.dry_run: bool = config.get("dry_run", True)
        self.max_daily_loss_pct: float = config.get("max_daily_loss_pct", 5.0)  # circuit breaker

        self._bars: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._positions: Dict[str, Optional[str]] = {s: None for s in self.symbols}
        self._bar_count: Dict[str, int] = defaultdict(int)
        self._filled_orders: list = []
        self._daily_pnl: float = 0.0
        self._daily_pnl_date: str = ""
        self._start_equity: float = self.order_amount_usd * 10
        self._circuit_broken: bool = False

        # Paper trading state
        self._data_dir = Path("data") / self.name
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._paper_state_path = self._data_dir / "paper_state.json"
        self._paper_trades_path = self._data_dir / "paper_trades.jsonl"
        self._runtime_state_path = self._data_dir / "runtime_state.json"
        self._paper_session_id: Optional[str] = None
        self._paper_equity = self.order_amount_usd * 10  # 10x order amount as starting capital
        self._paper_cash = self._paper_equity
        self._paper_shares: Dict[str, float] = defaultdict(float)
        self._paper_trade_count = 0
        self._init_paper_state()

    # ========================================================== Paper trading
    def _init_paper_state(self):
        if not self.dry_run:
            return
        if self._paper_state_path.exists():
            try:
                state = json.loads(self._paper_state_path.read_text(encoding="utf-8"))
                self._paper_session_id = state.get("paper_session_id")
                self._paper_equity = float(state.get("paper_equity", self._paper_equity))
                self._paper_cash = float(state.get("paper_cash", self._paper_cash))
                self._paper_trade_count = int(state.get("paper_trade_count", 0))
                return
            except Exception:
                pass
        self._paper_session_id = f"{self.name}-{int(time.time())}"
        self._persist_paper_state()

    def _persist_paper_state(self):
        if not self.dry_run:
            return
        state = {
            "paper_session_id": self._paper_session_id,
            "updated_at": int(time.time()),
            "strategy": self.name,
            "paper_equity": round(self._paper_equity, 2),
            "paper_cash": round(self._paper_cash, 2),
            "paper_trade_count": self._paper_trade_count,
            "dry_run": True,
        }
        self._write_json(self._paper_state_path, state)

    def _record_paper_trade(self, symbol: str, direction: str, price: float, quantity: int, notional: float):
        if not self.dry_run:
            return
        self._paper_trade_count += 1
        trade = {
            "ts": int(time.time()),
            "paper_session_id": self._paper_session_id,
            "symbol": symbol,
            "side": direction,
            "price": round(price, 2),
            "quantity": quantity,
            "notional": round(notional, 2),
        }
        self._write_jsonl(self._paper_trades_path, trade)
        self._persist_paper_state()

    def _persist_runtime_state(self):
        state = {
            "ts": int(time.time()),
            "updated_at": int(time.time()),
            "strategy": self.name,
            "dry_run": self.dry_run,
            "symbols": self.symbols,
            "paper_equity": round(self._paper_equity, 2),
            "paper_cash": round(self._paper_cash, 2),
            "paper_trade_count": self._paper_trade_count,
            "filled_orders": len(self._filled_orders),
        }
        self._write_json(self._runtime_state_path, state)

    @staticmethod
    def _write_json(path: Path, data: dict):
        try: path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception: pass

    @staticmethod
    def _write_jsonl(path: Path, record: dict):
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception: pass

    # ========================================================== Bar entry
    def on_bar(self, bar: Dict[str, Any]):
        symbol = bar.get("symbol")
        if symbol not in self.symbols:
            return

        self._bar_count[symbol] += 1
        self._bars[symbol].append(bar)
        max_len = max(self.config.get("long_window", 20), 100)
        if len(self._bars[symbol]) > max_len:
            self._bars[symbol] = self._bars[symbol][-max_len:]

        self.db.insert_bar(bar)
        close_price = bar.get("close", 0)
        if close_price > 0:
            self.risk.update_market_price(symbol, close_price)

        bar_time = bar.get("timestamp")
        signal = self.on_bar_logic(symbol, bar)
        if signal:
            self._handle_signal(symbol, signal, close_price, bar_time)

        # Periodic runtime state
        if self._bar_count[symbol] % 60 == 0:
            self._persist_runtime_state()

    @abstractmethod
    def on_bar_logic(self, symbol: str, bar: Dict[str, Any]) -> Optional[str]:
        pass

    # ========================================================== Signal → Order
    def _handle_signal(self, symbol: str, signal_type: str, close_price: float, bar_time: Optional[str] = None):
        if self._circuit_broken:
            return
        direction = "BUY" if signal_type == "BUY" else "SELL"
        quantity = self._calculate_quantity(close_price)
        if quantity <= 0:
            return

        self.db.insert_signal({
            "strategy_name": self.name,
            "symbol": symbol,
            "signal_type": signal_type,
            "price": close_price,
            "quantity": quantity,
            "reason": self._signal_reason(symbol),
        })

        current_pos = self._positions.get(symbol)
        if signal_type == "BUY" and current_pos == "LONG":
            return
        if signal_type == "SELL" and current_pos == "SHORT":
            return

        if self.check_risk:
            limit_price = self._limit_price(close_price, direction)
            result = self.risk.check_order(
                symbol=symbol, direction=direction, order_type="LIMIT",
                price=limit_price, quantity=quantity, strategy_name=self.name, bar_time=bar_time,
            )
            if not result.approved:
                logger.warning(f"[{self.name}] Signal {signal_type} rejected by risk: {result.reason}")
                return
            self.risk.record_signal(symbol, bar_time)

        self._send_order(symbol, direction, close_price, quantity)

    def _calculate_quantity(self, price: float) -> int:
        if price <= 0: return 0
        return max(int(self.order_amount_usd / price), 1)

    def _limit_price(self, close_price: float, direction: str) -> float:
        if direction == "BUY": return close_price + self.limit_price_offset
        return close_price - self.limit_price_offset

    # ========================================================== Safety: circuit breaker + position sync
    def _check_circuit_breaker(self, current_pnl: float) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        if self._daily_pnl_date != today:
            self._daily_pnl = 0.0
            self._daily_pnl_date = today
            self._circuit_broken = False
        self._daily_pnl += current_pnl
        if self._start_equity > 0 and abs(self._daily_pnl) / self._start_equity > self.max_daily_loss_pct / 100:
            self._circuit_broken = True
            logger.error(f"[{self.name}] CIRCUIT BREAKER: daily loss {self._daily_pnl:.2f} > {self.max_daily_loss_pct}%")
            return True
        return False

    def sync_positions_from_futu(self):
        """Pull current positions from Futu on startup (dry_run skips)."""
        if self.dry_run:
            return
        try:
            from futu import OpenSecTradeContext, TrdEnv
            host = os.getenv("FUTU_HOST", "127.0.0.1")
            port = int(os.getenv("FUTU_PORT", "11111"))
            ctx = OpenSecTradeContext(host=host, port=port)
            ret, data = ctx.position_list_query(trd_env=TrdEnv.SIMULATE)
            if ret == 0 and len(data) > 0:
                for _, row in data.iterrows():
                    sym = row["code"]
                    if sym in self.symbols:
                        qty = int(row["qty"])
                        if qty > 0:
                            self._positions[sym] = "LONG"
                        elif qty < 0:
                            self._positions[sym] = "SHORT"
                        logger.info(f"[{self.name}] Synced position: {sym} qty={qty} side={self._positions[sym]}")
            ctx.close()
        except Exception as e:
            logger.warning(f"[{self.name}] Position sync failed: {e}")

    # ========================================================== Order execution
    def _send_order(self, symbol: str, direction: str, close_price: float, quantity: int):
        limit_price = self._limit_price(close_price, direction)
        order_id = f"{symbol.replace('.', '_')}_{datetime.now().strftime('%H%M%S%f')}"
        notional = quantity * limit_price

        # Paper mode: simulate fill
        if self.dry_run:
            self._paper_trade_count += 1
            if direction == "BUY":
                self._paper_cash -= notional
                self._paper_shares[symbol] += quantity
            else:
                self._paper_cash += notional
                self._paper_shares[symbol] -= quantity
            self._positions[symbol] = "LONG" if direction == "BUY" else "SHORT"
            self._record_paper_trade(symbol, direction, limit_price, quantity, notional)
            logger.info(f"[{self.name}] [DRY_RUN] {direction} {symbol} {quantity}@{limit_price:.2f} (oid={order_id})")
            return

        # Live mode: attempt real Futu order
        try:
            from futu import OpenSecTradeContext, TrdEnv, TrdSide, OrderType
            host = os.getenv("FUTU_HOST", "127.0.0.1")
            port = int(os.getenv("FUTU_PORT", "11111"))
            trd_ctx = OpenSecTradeContext(host=host, port=port)
            ret, data = trd_ctx.place_order(
                price=limit_price,
                qty=quantity,
                code=symbol,
                trd_side=TrdSide.BUY if direction == "BUY" else TrdSide.SELL,
                order_type=OrderType.NORMAL,
                trd_env=TrdEnv.SIMULATE,
            )
            if ret != 0:
                logger.error(f"[{self.name}] Futu order failed: {data}")
                trd_ctx.close()
                return
            logger.info(f"[{self.name}] Futu order placed: {direction} {symbol} {quantity}@{limit_price:.2f}")
            # Check fill after short delay
            time.sleep(2)
            try:
                ret2, fills = trd_ctx.order_list_query()
                if ret2 == 0 and len(fills) > 0:
                    last = fills.iloc[-1]
                    status = last.get("order_status", "")
                    logger.info(f"[{self.name}] Order status: {status}")
            except Exception:
                pass
            trd_ctx.close()
        except ImportError:
            logger.warning(f"[{self.name}] futu-api not installed, falling back to dry_run")
            self.dry_run = True
            self._send_order(symbol, direction, close_price, quantity)
            return
        except Exception as e:
            logger.error(f"[{self.name}] Futu order error: {e}")
            return
            return

        # Record to DB regardless
        self.db.insert_order({
            "order_id": order_id, "symbol": symbol, "direction": direction,
            "order_type": "LIMIT", "price": round(limit_price, 2),
            "quantity": quantity, "status": "SUBMITTED",
            "exchange": "FUTU", "account_id": "SIMULATE",
        })
        self._positions[symbol] = "LONG" if direction == "BUY" else "SHORT"

    @abstractmethod
    def _signal_reason(self, symbol: str) -> str:
        pass

    def get_bar_count(self, symbol: str) -> int:
        return len(self._bars.get(symbol, []))
