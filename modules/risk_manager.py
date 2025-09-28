# -*- coding: utf-8 -*-
"""
Asynchronous Risk Manager Module for Zeus Trading Bot
Manages position sizing, stop losses, and risk parameters with async support.
"""
import asyncio
import logging
from typing import Dict, Optional, Union, List
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
import json

@dataclass
class RiskParameters:
    """Advanced Risk management parameters with async capabilities"""
    max_position_size: float = 0.05  # 5% of portfolio
    max_daily_loss: float = 0.02  # 2% daily loss limit
    stop_loss_percentage: float = 0.02  # 2% stop loss
    take_profit_percentage: float = 0.06  # 6% take profit
    max_open_positions: int = 3
    min_risk_reward_ratio: float = 2.0
    max_correlation_exposure: float = 0.3  # Maximum exposure to correlated assets
    volatility_adjustment: bool = True  # Adjust position size based on volatility
    paper_trading: bool = False  # Paper trading mode
    emergency_stop_loss: float = 0.10  # Emergency stop at 10% loss
    
class AsyncRiskManager:
    """Advanced Asynchronous Risk Management System with enhanced features"""
    
    def __init__(self, initial_balance: float, risk_params: Optional[RiskParameters] = None):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_params = risk_params or RiskParameters()
        self.daily_pnl = 0.0
        self.open_positions = {}
        self.position_history = []
        self.volatility_cache = {}
        self.correlation_matrix = {}
        self.risk_events = []
        self.logger = logging.getLogger(__name__)
        self.last_balance_update = datetime.now()
        self._lock = asyncio.Lock()
        
    async def calculate_position_size_async(self, symbol: str, entry_price: float, 
                                          stop_loss: float, volatility: Optional[float] = None) -> float:
        """Calculate optimal position size based on risk parameters with async support"""
        async with self._lock:
            try:
                base_risk = self.current_balance * self.risk_params.max_position_size
                price_risk = abs(entry_price - stop_loss) / entry_price
                
                if price_risk == 0:
                    return 0.0
                    
                # Volatility adjustment
                if self.risk_params.volatility_adjustment and volatility:
                    # Reduce position size for high volatility assets
                    volatility_factor = max(0.5, 1.0 - (volatility * 2))
                    base_risk *= volatility_factor
                
                # Check correlation exposure
                correlation_adjustment = await self._check_correlation_exposure(symbol)
                base_risk *= correlation_adjustment
                
                position_value = base_risk / price_risk
                max_position_value = self.current_balance * self.risk_params.max_position_size
                
                position_size = min(position_value, max_position_value) / entry_price
                
                await self._log_risk_event({
                    'type': 'position_sizing',
                    'symbol': symbol,
                    'calculated_size': position_size,
                    'volatility_factor': volatility_factor if volatility else 1.0,
                    'correlation_adjustment': correlation_adjustment
                })
                
                return position_size
                
            except Exception as e:
                self.logger.error(f"Error calculating position size: {e}")
                return 0.0
    
    async def validate_trade_async(self, symbol: str, side: str, quantity: float, 
                                 price: float, market_conditions: Optional[Dict] = None) -> Dict[str, Union[bool, str]]:
        """Enhanced trade validation with async support and detailed feedback"""
        validation_result = {'valid': True, 'reasons': []}
        
        async with self._lock:
            # Check daily loss limit
            if self.daily_pnl <= -self.current_balance * self.risk_params.max_daily_loss:
                validation_result['valid'] = False
                validation_result['reasons'].append('Daily loss limit reached')
                
            # Check emergency stop loss
            total_loss = (self.initial_balance - self.current_balance) / self.initial_balance
            if total_loss >= self.risk_params.emergency_stop_loss:
                validation_result['valid'] = False
                validation_result['reasons'].append('Emergency stop loss triggered')
                
            # Check max open positions
            if len(self.open_positions) >= self.risk_params.max_open_positions:
                validation_result['valid'] = False
                validation_result['reasons'].append('Maximum open positions reached')
                
            # Check position size
            position_value = quantity * price
            max_position_value = self.current_balance * self.risk_params.max_position_size
            
            if position_value > max_position_value:
                validation_result['valid'] = False
                validation_result['reasons'].append(f'Position size exceeds limit: {position_value:.2f} > {max_position_value:.2f}')
            
            # Market conditions check
            if market_conditions:
                if market_conditions.get('high_volatility', False):
                    validation_result['reasons'].append('High volatility detected - proceed with caution')
                if market_conditions.get('low_liquidity', False):
                    validation_result['reasons'].append('Low liquidity detected')
            
            # Log validation
            await self._log_risk_event({
                'type': 'trade_validation',
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'result': validation_result
            })
            
            return validation_result
    
    async def set_stop_loss_take_profit_async(self, symbol: str, entry_price: float, 
                                            side: str, volatility: Optional[float] = None) -> Dict[str, float]:
        """Calculate dynamic stop loss and take profit levels with volatility adjustment"""
        base_stop = self.risk_params.stop_loss_percentage
        base_profit = self.risk_params.take_profit_percentage
        
        # Adjust for volatility
        if volatility and self.risk_params.volatility_adjustment:
            # Wider stops for volatile assets
            volatility_multiplier = 1 + (volatility * 0.5)
            base_stop *= volatility_multiplier
            base_profit *= volatility_multiplier
        
        if side.lower() == 'buy':
            stop_loss = entry_price * (1 - base_stop)
            take_profit = entry_price * (1 + base_profit)
        else:  # sell
            stop_loss = entry_price * (1 + base_stop)
            take_profit = entry_price * (1 - base_profit)
            
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_reward_ratio': base_profit / base_stop
        }
    
    async def update_balance_async(self, new_balance: float):
        """Update balance with async support and enhanced tracking"""
        async with self._lock:
            pnl_change = new_balance - self.current_balance
            self.daily_pnl += pnl_change
            old_balance = self.current_balance
            self.current_balance = new_balance
            self.last_balance_update = datetime.now()
            
            # Log significant balance changes
            if abs(pnl_change) > self.current_balance * 0.001:  # > 0.1% change
                await self._log_risk_event({
                    'type': 'balance_update',
                    'old_balance': old_balance,
                    'new_balance': new_balance,
                    'pnl_change': pnl_change,
                    'daily_pnl': self.daily_pnl
                })
            
            self.logger.info(f"Balance updated: {self.current_balance:.2f}, Daily P&L: {self.daily_pnl:.2f}")
    
    async def add_position_async(self, symbol: str, side: str, quantity: float, 
                               entry_price: float, metadata: Optional[Dict] = None):
        """Add new position with enhanced tracking"""
        async with self._lock:
            position_data = {
                'side': side,
                'quantity': quantity,
                'entry_price': entry_price,
                'entry_time': datetime.now(),
                'unrealized_pnl': 0.0,
                'metadata': metadata or {}
            }
            
            self.open_positions[symbol] = position_data
            self.position_history.append({
                **position_data,
                'symbol': symbol,
                'action': 'open'
            })
    
    async def remove_position_async(self, symbol: str, exit_price: Optional[float] = None):
        """Remove position with profit/loss calculation"""
        async with self._lock:
            if symbol in self.open_positions:
                position = self.open_positions[symbol]
                
                if exit_price:
                    # Calculate realized P&L
                    if position['side'].lower() == 'buy':
                        pnl = (exit_price - position['entry_price']) * position['quantity']
                    else:
                        pnl = (position['entry_price'] - exit_price) * position['quantity']
                    
                    # Add to history
                    self.position_history.append({
                        **position,
                        'symbol': symbol,
                        'action': 'close',
                        'exit_price': exit_price,
                        'exit_time': datetime.now(),
                        'realized_pnl': pnl
                    })
                
                del self.open_positions[symbol]
    
    async def get_risk_metrics_async(self) -> Dict[str, Union[float, int, Dict]]:
        """Get comprehensive risk metrics"""
        async with self._lock:
            total_exposure = sum([pos['quantity'] * pos['entry_price'] for pos in self.open_positions.values()])
            
            metrics = {
                'current_balance': self.current_balance,
                'daily_pnl': self.daily_pnl,
                'daily_pnl_percentage': (self.daily_pnl / self.initial_balance) * 100,
                'total_pnl_percentage': ((self.current_balance - self.initial_balance) / self.initial_balance) * 100,
                'open_positions': len(self.open_positions),
                'risk_utilization': len(self.open_positions) / self.risk_params.max_open_positions * 100,
                'total_exposure': total_exposure,
                'exposure_ratio': total_exposure / self.current_balance if self.current_balance > 0 else 0,
                'paper_trading_mode': self.risk_params.paper_trading,
                'last_update': self.last_balance_update.isoformat()
            }
            
            return metrics
    
    async def _check_correlation_exposure(self, symbol: str) -> float:
        """Check correlation exposure and return adjustment factor"""
        # Simplified correlation check - in practice, this would use real correlation data
        # For now, return 1.0 (no adjustment)
        return 1.0
    
    async def _log_risk_event(self, event: Dict):
        """Log risk management events for analysis"""
        event['timestamp'] = datetime.now().isoformat()
        self.risk_events.append(event)
        
        # Keep only last 1000 events
        if len(self.risk_events) > 1000:
            self.risk_events = self.risk_events[-1000:]
    
    async def export_risk_report(self) -> Dict:
        """Export comprehensive risk report"""
        async with self._lock:
            return {
                'risk_parameters': self.risk_params.__dict__,
                'current_metrics': await self.get_risk_metrics_async(),
                'position_history': self.position_history[-50:],  # Last 50 positions
                'recent_events': self.risk_events[-100:],  # Last 100 events
                'generated_at': datetime.now().isoformat()
            }
    
    async def reset_daily_metrics_async(self):
        """Reset daily metrics with async support"""
        async with self._lock:
            self.daily_pnl = 0.0
            await self._log_risk_event({
                'type': 'daily_reset',
                'previous_daily_pnl': self.daily_pnl
            })
            self.logger.info("Daily metrics reset")

# Backward compatibility
RiskManager = AsyncRiskManager
