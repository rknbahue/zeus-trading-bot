# -*- coding: utf-8 -*-
"""
Risk Manager Module for Zeus Trading Bot

Manages position sizing, stop losses, and risk parameters.
"""

import logging
from typing import Dict, Optional, Union
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RiskParameters:
    """Risk management parameters"""
    max_position_size: float = 0.05  # 5% of portfolio
    max_daily_loss: float = 0.02  # 2% daily loss limit
    stop_loss_percentage: float = 0.02  # 2% stop loss
    take_profit_percentage: float = 0.06  # 6% take profit
    max_open_positions: int = 3
    min_risk_reward_ratio: float = 2.0


class RiskManager:
    """Advanced Risk Management System"""
    
    def __init__(self, initial_balance: float, risk_params: Optional[RiskParameters] = None):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_params = risk_params or RiskParameters()
        self.daily_pnl = 0.0
        self.open_positions = {}
        self.logger = logging.getLogger(__name__)
        
    def calculate_position_size(self, symbol: str, entry_price: float, 
                              stop_loss: float) -> float:
        """Calculate optimal position size based on risk parameters"""
        try:
            risk_per_trade = self.current_balance * self.risk_params.max_position_size
            price_risk = abs(entry_price - stop_loss) / entry_price
            
            if price_risk == 0:
                return 0.0
                
            position_value = risk_per_trade / price_risk
            max_position_value = self.current_balance * self.risk_params.max_position_size
            
            return min(position_value, max_position_value) / entry_price
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def validate_trade(self, symbol: str, side: str, quantity: float, 
                      price: float) -> bool:
        """Validate if trade meets risk management criteria"""
        # Check daily loss limit
        if self.daily_pnl <= -self.current_balance * self.risk_params.max_daily_loss:
            self.logger.warning("Daily loss limit reached")
            return False
            
        # Check max open positions
        if len(self.open_positions) >= self.risk_params.max_open_positions:
            self.logger.warning("Maximum open positions reached")
            return False
            
        # Check position size
        position_value = quantity * price
        max_position_value = self.current_balance * self.risk_params.max_position_size
        
        if position_value > max_position_value:
            self.logger.warning(f"Position size exceeds limit: {position_value} > {max_position_value}")
            return False
            
        return True
    
    def set_stop_loss_take_profit(self, symbol: str, entry_price: float, 
                                 side: str) -> Dict[str, float]:
        """Calculate stop loss and take profit levels"""
        if side.lower() == 'buy':
            stop_loss = entry_price * (1 - self.risk_params.stop_loss_percentage)
            take_profit = entry_price * (1 + self.risk_params.take_profit_percentage)
        else:  # sell
            stop_loss = entry_price * (1 + self.risk_params.stop_loss_percentage)
            take_profit = entry_price * (1 - self.risk_params.take_profit_percentage)
            
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    def update_balance(self, new_balance: float):
        """Update current balance and calculate daily P&L"""
        pnl_change = new_balance - self.current_balance
        self.daily_pnl += pnl_change
        self.current_balance = new_balance
        
        self.logger.info(f"Balance updated: {self.current_balance}, Daily P&L: {self.daily_pnl}")
    
    def add_position(self, symbol: str, side: str, quantity: float, 
                   entry_price: float):
        """Add new position to tracking"""
        self.open_positions[symbol] = {
            'side': side,
            'quantity': quantity,
            'entry_price': entry_price,
            'unrealized_pnl': 0.0
        }
    
    def remove_position(self, symbol: str):
        """Remove position from tracking"""
        if symbol in self.open_positions:
            del self.open_positions[symbol]
    
    def get_risk_metrics(self) -> Dict[str, Union[float, int]]:
        """Get current risk metrics"""
        return {
            'current_balance': self.current_balance,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_percentage': (self.daily_pnl / self.initial_balance) * 100,
            'open_positions': len(self.open_positions),
            'risk_utilization': len(self.open_positions) / self.risk_params.max_open_positions * 100
        }
    
    def reset_daily_metrics(self):
        """Reset daily metrics (call at start of new trading day)"""
        self.daily_pnl = 0.0
        self.logger.info("Daily metrics reset")
