# Zeus Trading Bot

Asynchronous upgrade (feature/async-upgrade) introducing ccxt.pro-based async exchange layer and async risk engine.

## What changed
- exchange_interface.py migrated to AsyncExchangeInterface + BinanceAsyncInterface (ccxt.pro)
- risk_manager.py upgraded to AsyncRiskManager with volatility- and correlation-aware sizing
- Backward-compat shims preserved: ExchangeInterface/BinanceInterface/ExchangeManager and RiskManager map to async versions

## Key parameters (risk)
- max_position_size: fraction of balance per trade (default 0.05)
- max_daily_loss: stop trading after daily PnL <= -X (default 0.02)
- stop_loss_percentage / take_profit_percentage: base SL/TP (defaults 0.02 / 0.06)
- max_open_positions: cap concurrent positions (default 3)
- min_risk_reward_ratio: minimum RR (default 2.0)
- volatility_adjustment: widen SL/TP and reduce size on high vol (default True)
- emergency_stop_loss: global kill-switch drawdown (default 0.10)
- paper_trading: simulate without live orders (default False)

## New async functions
- Risk: calculate_position_size_async, validate_trade_async, set_stop_loss_take_profit_async, update_balance_async, add/remove_position_async, get_risk_metrics_async, export_risk_report
- Exchange: connect/close, get_balance, get_ticker, get_ohlcv, place_order, cancel_order, get_order_status, get_open_orders (all async)
- Manager: connect_all, close_all, get_best_price (parallel), execute_order (async)

## Usage (paper mode example)
```python
import asyncio
from modules.exchange_interface import ExchangeManager, BinanceInterface
from modules.risk_manager import RiskManager

async def main():
    ex_mgr = ExchangeManager()
    ex_mgr.add_exchange('binance', BinanceInterface('<API_KEY>', '<SECRET>', testnet=True))
    await ex_mgr.connect_all()

    rm = RiskManager(initial_balance=10000.0)
    ticker = await ex_mgr.exchanges['binance'].get_ticker('BTC/USDT')
    price = ticker['last']
    levels = await rm.set_stop_loss_take_profit_async('BTC/USDT', price, 'buy', volatility=0.02)
    size = await rm.calculate_position_size_async('BTC/USDT', price, levels['stop_loss'], volatility=0.02)
    validation = await rm.validate_trade_async('BTC/USDT', 'buy', size, price)
    if validation['valid']:
        order = await ex_mgr.execute_order('BTC/USDT', 'buy', size, order_type='market', exchange_name='binance')
        print(order)
    await ex_mgr.close_all()

asyncio.run(main())
```

## Test workflow (paper testing)
1) Create a .env with testnet API keys or run pure paper by mocking place_order.
2) Start an async test script (see sample above) targeting a test symbol (e.g., BTC/USDT).
3) Verify:
   - Risk metrics via get_risk_metrics_async
   - SL/TP and position sizing respond to volatility parameter
   - Manager.get_best_price runs in parallel without blocking
4) Run multiple trades until hitting max_open_positions or daily loss to confirm risk halts.
5) Inspect recent events with export_risk_report for audit trail.

## Notes
- Requires ccxt.pro for true async exchange I/O. If not installed, BinanceAsyncInterface returns a clear error.
- Keep event loop single-threaded; heavy CPU work should be offloaded to executors.
- This branch is for testing; open a PR when validated.
