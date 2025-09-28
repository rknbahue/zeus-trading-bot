# -*- coding: utf-8 -*-
"""
Asynchronous Exchange Interface Module for Zeus Trading Bot
Provides unified async interface for cryptocurrency exchanges using ccxt.pro (AsyncClient-like).
"""
import asyncio
import logging
from typing import Dict, List, Optional, Union, Any
from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass

try:
    import ccxt.pro as ccxt_async  # async version of ccxt
except Exception:  # fallback if ccxt.pro not available
    ccxt_async = None

@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str
    amount: float
    price: float
    filled: float
    remaining: float
    status: str
    timestamp: datetime
    fees: Dict[str, float] | None = None

class AsyncExchangeInterface(ABC):
    """Abstract base class for async exchange interfaces"""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to exchange asynchronously"""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Close exchange connection"""
        raise NotImplementedError

    @abstractmethod
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        raise NotImplementedError

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker data for symbol"""
        raise NotImplementedError

    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List[Union[int, float]]]:
        """Get OHLCV data (raw list for speed)"""
        raise NotImplementedError

    @abstractmethod
    async def place_order(self, symbol: str, side: str, amount: float,
                          price: Optional[float] = None, order_type: str = 'market') -> OrderResult:
        """Place an order asynchronously"""
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

class BinanceAsyncInterface(AsyncExchangeInterface):
    """Binance async interface using ccxt.pro"""

    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        self.exchange = None
        self.logger = logging.getLogger(__name__)
        self.connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        if ccxt_async is None:
            self.logger.error("ccxt.pro not available. Install ccxtpro for async support.")
            return False
        try:
            params = {
                'apiKey': self.api_key,
                'secret': self.secret_key,
                'enableRateLimit': True,
            }
            if self.testnet:
                params['options'] = {'defaultType': 'spot'}
                params['urls'] = {'api': {'public': 'https://testnet.binance.vision/api',
                                          'private': 'https://testnet.binance.vision/api'}}
            self.exchange = ccxt_async.binance(params)
            await self.exchange.load_markets()
            self.connected = True
            self.logger.info("Connected to Binance (async)")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance (async): {e}")
            self.connected = False
            return False

    async def close(self) -> None:
        if self.exchange is not None:
            try:
                await self.exchange.close()
            except Exception:
                pass
            finally:
                self.connected = False

    async def get_balance(self) -> Dict[str, Any]:
        async with self._lock:
            try:
                if not self.connected:
                    raise ConnectionError("Not connected to exchange")
                balance = await self.exchange.fetch_balance()
                return {
                    'total': balance.get('total', {}),
                    'free': balance.get('free', {}),
                    'used': balance.get('used', {}),
                }
            except Exception as e:
                self.logger.error(f"Error fetching balance: {e}")
                return {}

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        async with self._lock:
            try:
                if not self.connected:
                    raise ConnectionError("Not connected to exchange")
                ticker = await self.exchange.fetch_ticker(symbol)
                return {
                    'symbol': symbol,
                    'last': ticker.get('last'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'open': ticker.get('open'),
                    'high': ticker.get('high'),
                    'low': ticker.get('low'),
                    'close': ticker.get('close'),
                    'volume': ticker.get('baseVolume') or ticker.get('quoteVolume'),
                    'timestamp': datetime.fromtimestamp((ticker.get('timestamp') or 0) / 1000) if ticker.get('timestamp') else None,
                }
            except Exception as e:
                self.logger.error(f"Error fetching ticker for {symbol}: {e}")
                return {}

    async def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List[Union[int, float]]]:
        async with self._lock:
            try:
                if not self.connected:
                    raise ConnectionError("Not connected to exchange")
                ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                return ohlcv
            except Exception as e:
                self.logger.error(f"Error fetching OHLCV for {symbol}: {e}")
                return []

    async def place_order(self, symbol: str, side: str, amount: float,
                          price: Optional[float] = None, order_type: str = 'market') -> OrderResult:
        async with self._lock:
            try:
                if not self.connected:
                    raise ConnectionError("Not connected to exchange")
                if order_type.lower() == 'market':
                    order = await self.exchange.create_order(symbol, 'market', side, amount)
                elif order_type.lower() == 'limit':
                    if price is None:
                        raise ValueError("Price required for limit order")
                    order = await self.exchange.create_order(symbol, 'limit', side, amount, price)
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")

                return OrderResult(
                    order_id=order.get('id', ''),
                    symbol=order.get('symbol', symbol),
                    side=order.get('side', side),
                    amount=float(order.get('amount', amount) or 0),
                    price=float(order.get('price', price) or 0),
                    filled=float(order.get('filled', 0) or 0),
                    remaining=float(order.get('remaining', 0) or 0),
                    status=order.get('status', ''),
                    timestamp=datetime.fromtimestamp((order.get('timestamp') or 0) / 1000) if order.get('timestamp') else datetime.utcnow(),
                    fees=order.get('fees', {}) if isinstance(order.get('fees', {}), dict) else {},
                )
            except Exception as e:
                self.logger.error(f"Error placing order: {e}")
                raise

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        async with self._lock:
            try:
                if not self.connected:
                    raise ConnectionError("Not connected to exchange")
                await self.exchange.cancel_order(order_id, symbol)
                self.logger.info(f"Order {order_id} cancelled")
                return True
            except Exception as e:
                self.logger.error(f"Error cancelling order {order_id}: {e}")
                return False

    async def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        async with self._lock:
            try:
                if not self.connected:
                    raise ConnectionError("Not connected to exchange")
                order = await self.exchange.fetch_order(order_id, symbol)
                return {
                    'id': order.get('id'),
                    'status': order.get('status'),
                    'filled': order.get('filled', 0),
                    'remaining': order.get('remaining', 0),
                    'price': order.get('price', 0),
                    'average': order.get('average', 0),
                    'timestamp': datetime.fromtimestamp((order.get('timestamp') or 0) / 1000) if order.get('timestamp') else None,
                }
            except Exception as e:
                self.logger.error(f"Error fetching order status: {e}")
                return {}

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        async with self._lock:
            try:
                if not self.connected:
                    raise ConnectionError("Not connected to exchange")
                orders = await self.exchange.fetch_open_orders(symbol)
                return [{
                    'id': o.get('id'),
                    'symbol': o.get('symbol'),
                    'side': o.get('side'),
                    'amount': o.get('amount'),
                    'price': o.get('price', 0),
                    'filled': o.get('filled', 0),
                    'remaining': o.get('remaining', 0),
                    'status': o.get('status'),
                    'timestamp': datetime.fromtimestamp((o.get('timestamp') or 0) / 1000) if o.get('timestamp') else None,
                } for o in orders]
            except Exception as e:
                self.logger.error(f"Error fetching open orders: {e}")
                return []

class AsyncExchangeManager:
    """Manages multiple async exchange interfaces"""

    def __init__(self):
        self.exchanges: Dict[str, AsyncExchangeInterface] = {}
        self.active_exchange: Optional[AsyncExchangeInterface] = None
        self.logger = logging.getLogger(__name__)

    def add_exchange(self, name: str, exchange_interface: AsyncExchangeInterface):
        self.exchanges[name] = exchange_interface
        self.logger.info(f"Added exchange interface: {name}")

    def set_active_exchange(self, name: str) -> bool:
        if name in self.exchanges:
            self.active_exchange = self.exchanges[name]
            self.logger.info(f"Active exchange set to: {name}")
            return True
        self.logger.error(f"Exchange {name} not found")
        return False

    async def connect_all(self) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        for name, exchange in self.exchanges.items():
            results[name] = await exchange.connect()
        return results

    async def close_all(self) -> None:
        await asyncio.gather(*[ex.close() for ex in self.exchanges.values() if ex])

    async def get_best_price(self, symbol: str, side: str) -> Dict[str, Any]:
        best_price: Optional[float] = None
        best_exchange: Optional[str] = None

        async def fetch_from(name: str, ex: AsyncExchangeInterface):
            try:
                return name, await ex.get_ticker(symbol)
            except Exception as e:
                self.logger.error(f"Error getting price from {name}: {e}")
                return name, {}

        results = await asyncio.gather(*[fetch_from(n, e) for n, e in self.exchanges.items()])
        for name, ticker in results:
            if not ticker:
                continue
            if side.lower() == 'buy':
                price = ticker.get('ask', float('inf'))
                if best_price is None or price < best_price:
                    best_price = price
                    best_exchange = name
            else:
                price = ticker.get('bid', 0.0)
                if best_price is None or price > best_price:
                    best_price = price
                    best_exchange = name
        return {'exchange': best_exchange, 'price': best_price, 'side': side, 'symbol': symbol}

    async def execute_order(self, symbol: str, side: str, amount: float,
                            price: Optional[float] = None, order_type: str = 'market',
                            exchange_name: Optional[str] = None) -> Optional[OrderResult]:
        try:
            exchange = self.exchanges.get(exchange_name) if exchange_name else self.active_exchange
            if not exchange:
                raise ValueError("No active exchange set or exchange_name invalid")
            return await exchange.place_order(symbol, side, amount, price, order_type)
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
            return None

# Backward compatibility aliases
ExchangeInterface = AsyncExchangeInterface
BinanceInterface = BinanceAsyncInterface
ExchangeManager = AsyncExchangeManager
