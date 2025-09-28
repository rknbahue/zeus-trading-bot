# -*- coding: utf-8 -*-
"""
Exchange Interface Module for Zeus Trading Bot

Provides unified interface for different cryptocurrency exchanges.
"""

import ccxt
import pandas as pd
from typing import Dict, List, Optional, Union, Any
import logging
from abc import ABC, abstractmethod
from datetime import datetime
import asyncio
from dataclasses import dataclass


@dataclass
class OrderResult:
    """Order execution result"""
    order_id: str
    symbol: str
    side: str
    amount: float
    price: float
    filled: float
    remaining: float
    status: str
    timestamp: datetime
    fees: Dict[str, float] = None


class ExchangeInterface(ABC):
    """Abstract base class for exchange interfaces"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to exchange"""
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get ticker data for symbol"""
        pass
    
    @abstractmethod
    def place_order(self, symbol: str, side: str, amount: float, 
                   price: Optional[float] = None, order_type: str = 'market') -> OrderResult:
        """Place an order"""
        pass


class BinanceInterface(ExchangeInterface):
    """Binance exchange interface"""
    
    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        self.exchange = None
        self.logger = logging.getLogger(__name__)
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to Binance"""
        try:
            if self.testnet:
                self.exchange = ccxt.binance({
                    'apiKey': self.api_key,
                    'secret': self.secret_key,
                    'sandbox': True,
                    'enableRateLimit': True,
                })
            else:
                self.exchange = ccxt.binance({
                    'apiKey': self.api_key,
                    'secret': self.secret_key,
                    'enableRateLimit': True,
                })
            
            # Test connection
            self.exchange.load_markets()
            self.connected = True
            self.logger.info("Successfully connected to Binance")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {e}")
            self.connected = False
            return False
    
    def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        try:
            if not self.connected:
                raise ConnectionError("Not connected to exchange")
            
            balance = self.exchange.fetch_balance()
            return {
                'total': balance['total'],
                'free': balance['free'],
                'used': balance['used']
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            return {}
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get ticker data"""
        try:
            if not self.connected:
                raise ConnectionError("Not connected to exchange")
            
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'open': ticker['open'],
                'high': ticker['high'],
                'low': ticker['low'],
                'close': ticker['close'],
                'volume': ticker['baseVolume'],
                'timestamp': datetime.fromtimestamp(ticker['timestamp'] / 1000)
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching ticker for {symbol}: {e}")
            return {}
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', 
                  limit: int = 100) -> pd.DataFrame:
        """Get OHLCV data"""
        try:
            if not self.connected:
                raise ConnectionError("Not connected to exchange")
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return pd.DataFrame()
    
    def place_order(self, symbol: str, side: str, amount: float, 
                   price: Optional[float] = None, order_type: str = 'market') -> OrderResult:
        """Place an order"""
        try:
            if not self.connected:
                raise ConnectionError("Not connected to exchange")
            
            if order_type.lower() == 'market':
                order = self.exchange.create_market_order(symbol, side, amount)
            elif order_type.lower() == 'limit':
                if price is None:
                    raise ValueError("Price required for limit order")
                order = self.exchange.create_limit_order(symbol, side, amount, price)
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            return OrderResult(
                order_id=order['id'],
                symbol=order['symbol'],
                side=order['side'],
                amount=order['amount'],
                price=order.get('price', 0),
                filled=order.get('filled', 0),
                remaining=order.get('remaining', amount),
                status=order['status'],
                timestamp=datetime.fromtimestamp(order['timestamp'] / 1000),
                fees=order.get('fees', {})
            )
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        try:
            if not self.connected:
                raise ConnectionError("Not connected to exchange")
            
            self.exchange.cancel_order(order_id, symbol)
            self.logger.info(f"Order {order_id} cancelled successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Get order status"""
        try:
            if not self.connected:
                raise ConnectionError("Not connected to exchange")
            
            order = self.exchange.fetch_order(order_id, symbol)
            return {
                'id': order['id'],
                'status': order['status'],
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'price': order.get('price', 0),
                'average': order.get('average', 0),
                'timestamp': datetime.fromtimestamp(order['timestamp'] / 1000)
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching order status: {e}")
            return {}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders"""
        try:
            if not self.connected:
                raise ConnectionError("Not connected to exchange")
            
            orders = self.exchange.fetch_open_orders(symbol)
            return [{
                'id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'amount': order['amount'],
                'price': order.get('price', 0),
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'status': order['status'],
                'timestamp': datetime.fromtimestamp(order['timestamp'] / 1000)
            } for order in orders]
            
        except Exception as e:
            self.logger.error(f"Error fetching open orders: {e}")
            return []


class ExchangeManager:
    """Manages multiple exchange interfaces"""
    
    def __init__(self):
        self.exchanges = {}
        self.active_exchange = None
        self.logger = logging.getLogger(__name__)
    
    def add_exchange(self, name: str, exchange_interface: ExchangeInterface):
        """Add an exchange interface"""
        self.exchanges[name] = exchange_interface
        self.logger.info(f"Added exchange interface: {name}")
    
    def set_active_exchange(self, name: str) -> bool:
        """Set active exchange"""
        if name in self.exchanges:
            self.active_exchange = self.exchanges[name]
            self.logger.info(f"Active exchange set to: {name}")
            return True
        else:
            self.logger.error(f"Exchange {name} not found")
            return False
    
    def connect_all(self) -> Dict[str, bool]:
        """Connect to all exchanges"""
        results = {}
        for name, exchange in self.exchanges.items():
            results[name] = exchange.connect()
        return results
    
    def get_best_price(self, symbol: str, side: str) -> Dict[str, Any]:
        """Get best price across all connected exchanges"""
        best_price = None
        best_exchange = None
        
        for name, exchange in self.exchanges.items():
            try:
                if hasattr(exchange, 'connected') and exchange.connected:
                    ticker = exchange.get_ticker(symbol)
                    
                    if side.lower() == 'buy':
                        price = ticker.get('ask', float('inf'))
                        if best_price is None or price < best_price:
                            best_price = price
                            best_exchange = name
                    else:  # sell
                        price = ticker.get('bid', 0)
                        if best_price is None or price > best_price:
                            best_price = price
                            best_exchange = name
                            
            except Exception as e:
                self.logger.error(f"Error getting price from {name}: {e}")
        
        return {
            'exchange': best_exchange,
            'price': best_price,
            'side': side,
            'symbol': symbol
        }
    
    def execute_order(self, symbol: str, side: str, amount: float, 
                     price: Optional[float] = None, order_type: str = 'market',
                     exchange_name: Optional[str] = None) -> Optional[OrderResult]:
        """Execute order on specified or active exchange"""
        try:
            if exchange_name:
                exchange = self.exchanges.get(exchange_name)
                if not exchange:
                    raise ValueError(f"Exchange {exchange_name} not found")
            else:
                exchange = self.active_exchange
                if not exchange:
                    raise ValueError("No active exchange set")
            
            return exchange.place_order(symbol, side, amount, price, order_type)
            
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
            return None
