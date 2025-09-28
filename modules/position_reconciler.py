"""
PositionReconciler module

Continuously reconciles internal positions with actual exchange state, detects fills/partials,
updates realized/unrealized PnL, and records last errors. Designed to work with the async
ExchangeManager and AsyncRiskManager layers.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

from .logger import get_logger
# Expected interfaces (backward-compat names in README):
# - ExchangeManager: manages named exchanges and offers execute_order, get_best_price, etc.
# - RiskManager: tracks balance, positions, metrics, and offers async helpers.


@dataclass
class Position:
    symbol: str
    side: str  # 'buy' or 'sell'
    size: float
    avg_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    exchange: str = ""
    updated_ts: float = field(default_factory=lambda: time.time())


class PositionReconciler:
    def __init__(
        self,
        exchange_manager,
        risk_manager,
        *,
        poll_interval: float = 2.0,
        latency_window: int = 50,
    ):
        self.log = get_logger(__name__)
        self.ex_mgr = exchange_manager
        self.risk = risk_manager
        self.poll_interval = poll_interval
        self.running = False

        # Health and diagnostics
        self.breaker_open: bool = False
        self.ws_status: Dict[str, Dict[str, Any]] = {}  # {ex:{status:str, ping_ms:float}}
        self.avg_slippage_bp: float = 0.0
        self.fill_events: int = 0
        self.order_events: int = 0
        self.last_error: Optional[str] = None
        self._latencies: List[float] = []
        self._latency_window = max(1, latency_window)

        # Internal cache of positions by key (exchange|symbol)
        self._positions: Dict[str, Position] = {}

    def _pos_key(self, exchange: str, symbol: str) -> str:
        return f"{exchange}|{symbol}"

    def get_health_snapshot(self) -> Dict[str, Any]:
        # exposure% computed from risk manager
        try:
            metrics = asyncio.run(self.risk.get_risk_metrics_async()) if asyncio.get_event_loop().is_closed() else None
        except Exception:
            metrics = None
        exposure_pct = 0.0
        if metrics and isinstance(metrics, dict):
            exposure_pct = float(metrics.get("exposure_pct", 0.0))

        avg_latency = sum(self._latencies[-self._latency_window:]) / max(1, min(len(self._latencies), self._latency_window))
        fill_rate = (self.fill_events / max(1, self.order_events)) if self.order_events else 0.0
        return {
            "breaker": "open" if self.breaker_open else "closed",
            "ws": self.ws_status,
            "exposure_pct": exposure_pct,
            "slippage_bps": self.avg_slippage_bp,
            "latency_ms": avg_latency,
            "fill_rate": fill_rate,
            "last_error": self.last_error,
        }

    async def _calc_unrealized(self, symbol: str, side: str, size: float, avg_price: float, last_price: float) -> float:
        # Long: (last - avg) * size; Short: (avg - last) * size
        direction = 1.0 if side == 'buy' else -1.0
        return (last_price - avg_price) * size * direction

    async def _fetch_remote_positions(self) -> Dict[str, Dict[str, Any]]:
        # Query each connected exchange for open positions and open orders
        # Expected normalized structure per exchange adapter
        remote: Dict[str, Dict[str, Any]] = {}
        for name, ex in self.ex_mgr.exchanges.items():
            try:
                t0 = time.time()
                # Prefer unified method if provided; otherwise gather from open orders + balances
                if hasattr(ex, 'get_open_positions'):
                    positions = await ex.get_open_positions()
                else:
                    positions = []
                orders = await ex.get_open_orders() if hasattr(ex, 'get_open_orders') else []
                ws_info = {}
                if hasattr(ex, 'ping_ws'):
                    try:
                        ping = await ex.ping_ws()
                        ws_info = {"status": "up", "ping_ms": float(ping)}
                    except Exception as e:
                        ws_info = {"status": "down", "ping_ms": None}
                        self.log.warning(f"WS ping failed for {name}: {e}")
                self.ws_status[name] = ws_info
                self._latencies.append((time.time() - t0) * 1000.0)
                remote[name] = {"positions": positions, "orders": orders}
            except Exception as e:
                self.last_error = str(e)
                self.log.exception(f"Failed fetching state from {name}")
        return remote

    async def _update_slippage_stats(self, fills: List[Dict[str, Any]]):
        # fills items expected: {symbol, side, size, price, ref_price}
        if not fills:
            return
        bps_list = []
        for f in fills:
            ref = f.get('ref_price')
            px = f.get('price')
            if ref and px:
                bps = (px - ref) / ref * 10000.0
                bps_list.append(abs(bps))
        if bps_list:
            # simple moving average over last window
            recent = bps_list
            if self.avg_slippage_bp == 0.0:
                self.avg_slippage_bp = sum(recent) / len(recent)
            else:
                # EMA-ish update
                alpha = 0.2
                self.avg_slippage_bp = (1 - alpha) * self.avg_slippage_bp + alpha * (sum(recent) / len(recent))

    async def _reconcile(self, remote: Dict[str, Dict[str, Any]]):
        # Compare remote positions with internal risk manager positions
        # Internal API assumed on RiskManager: add/remove_position_async, get_risk_metrics_async, update_balance_async
        detected_fills: List[Dict[str, Any]] = []
        for ex_name, data in remote.items():
            positions = data.get('positions') or []
            orders = data.get('orders') or []

            # Map positions by symbol
            remote_map: Dict[str, Tuple[str, float, float]] = {}
            for p in positions:
                # normalized fields expected: symbol, side, size, avg_price, unrealizedPnl(optional), lastPrice(optional)
                sym = p.get('symbol')
                side = p.get('side')
                size = float(p.get('size', 0.0))
                avg = float(p.get('avg_price', p.get('entryPrice', 0.0)))
                if not sym or size == 0.0:
                    continue
                remote_map[sym] = (side, size, avg)

            # Detect fills/partials from orders list if fields provided
            for o in orders:
                status = (o.get('status') or '').lower()
                filled = float(o.get('filled', 0.0))
                amount = float(o.get('amount', 0.0))
                symbol = o.get('symbol')
                side = o.get('side')
                avg_fill_price = o.get('average') or o.get('price')
                ref_price = o.get('ref_price') or o.get('price')
                if symbol and amount > 0:
                    self.order_events += 1
                if status in ('filled', 'closed') or (filled > 0 and filled >= amount * 0.99):
                    if symbol and filled > 0:
                        self.fill_events += 1
                        detected_fills.append({
                            'exchange': ex_name,
                            'symbol': symbol,
                            'side': side,
                            'size': filled,
                            'price': avg_fill_price,
                            'ref_price': ref_price,
                        })

            # Reconcile each remote position to internal cache and risk manager
            for symbol, (side, size, avg) in remote_map.items():
                key = self._pos_key(ex_name, symbol)
                last_price = avg
                try:
                    # try to fetch ticker for mark price
                    if ex_name in self.ex_mgr.exchanges:
                        tkr = await self.ex_mgr.exchanges[ex_name].get_ticker(symbol)
                        if tkr and 'last' in tkr:
                            last_price = float(tkr['last'])
                except Exception:
                    pass

                unreal = await self._calc_unrealized(symbol, side, size, avg, last_price)
                pos = self._positions.get(key)
                if not pos:
                    pos = Position(symbol=symbol, side=side, size=size, avg_price=avg, exchange=ex_name, unrealized_pnl=unreal)
                    self._positions[key] = pos
                    # inform risk manager
                    try:
                        await self.risk.add_position_async(symbol, side, size, avg)
                    except Exception as e:
                        self.last_error = str(e)
                        self.log.warning(f"Risk add_position failed {symbol}: {e}")
                else:
                    # update
                    pos.side = side
                    pos.size = size
                    pos.avg_price = avg
                    pos.unrealized_pnl = unreal
                    pos.updated_ts = time.time()

            # Detect closed positions locally if not present remotely
            keys_for_ex = [k for k in list(self._positions.keys()) if k.startswith(f"{ex_name}|")]
            for key in keys_for_ex:
                sym = key.split('|', 1)[1]
                if sym not in remote_map:
                    # closed externally
                    pos = self._positions.pop(key, None)
                    if pos:
                        try:
                            await self.risk.remove_position_async(sym)
                        except Exception as e:
                            self.last_error = str(e)
                            self.log.warning(f"Risk remove_position failed {sym}: {e}")

        await self._update_slippage_stats(detected_fills)

    async def loop(self, *, breaker: Optional[asyncio.Event] = None):
        self.running = True
        self.log.info("PositionReconciler loop started")
        try:
            while self.running:
                if breaker and breaker.is_set():
                    self.breaker_open = True
                    await asyncio.sleep(self.poll_interval)
                    continue
                self.breaker_open = False

                try:
                    remote = await self._fetch_remote_positions()
                    await self._reconcile(remote)
                except Exception as e:
                    self.last_error = str(e)
                    self.log.exception("Reconciliation cycle failed")

                await asyncio.sleep(self.poll_interval)
        finally:
            self.running = False
            self.log.info("PositionReconciler loop stopped")

    async def stop(self):
        self.running = False

