# -*- coding: utf-8 -*-
"""
Technical Analysis Module for Zeus Trading Bot

Provides technical indicators and market analysis tools.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from enum import Enum


class TrendDirection(Enum):
    """Trend direction enumeration"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"


class SignalStrength(Enum):
    """Signal strength enumeration"""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class TechnicalAnalyzer:
    """Advanced Technical Analysis Engine"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.indicators_cache = {}
    
    def calculate_sma(self, data: pd.Series, window: int) -> pd.Series:
        """Calculate Simple Moving Average"""
        return data.rolling(window=window).mean()
    
    def calculate_ema(self, data: pd.Series, window: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return data.ewm(span=window).mean()
    
    def calculate_rsi(self, data: pd.Series, window: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, data: pd.Series, fast: int = 12, 
                      slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        ema_fast = self.calculate_ema(data, fast)
        ema_slow = self.calculate_ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def calculate_bollinger_bands(self, data: pd.Series, window: int = 20, 
                                 std_dev: float = 2) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands"""
        sma = self.calculate_sma(data, window)
        std = data.rolling(window=window).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }
    
    def calculate_stochastic(self, high: pd.Series, low: pd.Series, 
                           close: pd.Series, k_window: int = 14, 
                           d_window: int = 3) -> Dict[str, pd.Series]:
        """Calculate Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_window).mean()
        
        return {
            'k': k_percent,
            'd': d_percent
        }
    
    def detect_support_resistance(self, data: pd.Series, 
                                window: int = 20) -> Dict[str, List[float]]:
        """Detect support and resistance levels"""
        # Find local minima and maxima
        local_min = data.rolling(window=window, center=True).min() == data
        local_max = data.rolling(window=window, center=True).max() == data
        
        support_levels = data[local_min].tolist()
        resistance_levels = data[local_max].tolist()
        
        return {
            'support': sorted(set(support_levels)),
            'resistance': sorted(set(resistance_levels), reverse=True)
        }
    
    def analyze_trend(self, data: pd.Series, short_window: int = 20, 
                     long_window: int = 50) -> Dict[str, any]:
        """Analyze market trend direction and strength"""
        sma_short = self.calculate_sma(data, short_window)
        sma_long = self.calculate_sma(data, long_window)
        
        current_short = sma_short.iloc[-1]
        current_long = sma_long.iloc[-1]
        current_price = data.iloc[-1]
        
        # Determine trend direction
        if current_short > current_long and current_price > current_short:
            direction = TrendDirection.BULLISH
        elif current_short < current_long and current_price < current_short:
            direction = TrendDirection.BEARISH
        else:
            direction = TrendDirection.SIDEWAYS
        
        # Calculate trend strength
        price_change = (data.iloc[-1] - data.iloc[-short_window]) / data.iloc[-short_window]
        
        if abs(price_change) > 0.05:
            strength = SignalStrength.STRONG
        elif abs(price_change) > 0.02:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK
        
        return {
            'direction': direction,
            'strength': strength,
            'price_change_pct': price_change * 100,
            'sma_short': current_short,
            'sma_long': current_long
        }
    
    def generate_trading_signals(self, ohlc_data: pd.DataFrame) -> Dict[str, any]:
        """Generate comprehensive trading signals"""
        try:
            signals = {
                'timestamp': pd.Timestamp.now(),
                'symbol': ohlc_data.get('symbol', 'Unknown'),
                'current_price': ohlc_data['close'].iloc[-1],
                'signals': [],
                'overall_score': 0
            }
            
            close = ohlc_data['close']
            high = ohlc_data['high']
            low = ohlc_data['low']
            
            # RSI Signal
            rsi = self.calculate_rsi(close)
            current_rsi = rsi.iloc[-1]
            
            if current_rsi < 30:
                signals['signals'].append({
                    'indicator': 'RSI',
                    'signal': 'BUY',
                    'strength': SignalStrength.STRONG,
                    'value': current_rsi
                })
                signals['overall_score'] += 2
            elif current_rsi > 70:
                signals['signals'].append({
                    'indicator': 'RSI',
                    'signal': 'SELL',
                    'strength': SignalStrength.STRONG,
                    'value': current_rsi
                })
                signals['overall_score'] -= 2
            
            # MACD Signal
            macd_data = self.calculate_macd(close)
            macd_line = macd_data['macd'].iloc[-1]
            signal_line = macd_data['signal'].iloc[-1]
            
            if macd_line > signal_line and macd_data['macd'].iloc[-2] <= macd_data['signal'].iloc[-2]:
                signals['signals'].append({
                    'indicator': 'MACD',
                    'signal': 'BUY',
                    'strength': SignalStrength.MODERATE,
                    'value': macd_line - signal_line
                })
                signals['overall_score'] += 1
            elif macd_line < signal_line and macd_data['macd'].iloc[-2] >= macd_data['signal'].iloc[-2]:
                signals['signals'].append({
                    'indicator': 'MACD',
                    'signal': 'SELL',
                    'strength': SignalStrength.MODERATE,
                    'value': macd_line - signal_line
                })
                signals['overall_score'] -= 1
            
            # Bollinger Bands Signal
            bb_data = self.calculate_bollinger_bands(close)
            current_price = close.iloc[-1]
            
            if current_price <= bb_data['lower'].iloc[-1]:
                signals['signals'].append({
                    'indicator': 'Bollinger Bands',
                    'signal': 'BUY',
                    'strength': SignalStrength.MODERATE,
                    'value': (current_price - bb_data['lower'].iloc[-1]) / bb_data['lower'].iloc[-1]
                })
                signals['overall_score'] += 1
            elif current_price >= bb_data['upper'].iloc[-1]:
                signals['signals'].append({
                    'indicator': 'Bollinger Bands',
                    'signal': 'SELL',
                    'strength': SignalStrength.MODERATE,
                    'value': (current_price - bb_data['upper'].iloc[-1]) / bb_data['upper'].iloc[-1]
                })
                signals['overall_score'] -= 1
            
            # Trend Analysis
            trend_analysis = self.analyze_trend(close)
            signals['trend'] = trend_analysis
            
            if trend_analysis['direction'] == TrendDirection.BULLISH:
                signals['overall_score'] += 0.5
            elif trend_analysis['direction'] == TrendDirection.BEARISH:
                signals['overall_score'] -= 0.5
            
            # Final recommendation
            if signals['overall_score'] >= 2:
                signals['recommendation'] = 'STRONG_BUY'
            elif signals['overall_score'] >= 1:
                signals['recommendation'] = 'BUY'
            elif signals['overall_score'] <= -2:
                signals['recommendation'] = 'STRONG_SELL'
            elif signals['overall_score'] <= -1:
                signals['recommendation'] = 'SELL'
            else:
                signals['recommendation'] = 'HOLD'
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Error generating trading signals: {e}")
            return {
                'timestamp': pd.Timestamp.now(),
                'error': str(e),
                'recommendation': 'HOLD'
            }
    
    def calculate_volatility(self, data: pd.Series, window: int = 20) -> float:
        """Calculate price volatility"""
        returns = data.pct_change().dropna()
        volatility = returns.rolling(window=window).std().iloc[-1]
        return volatility * np.sqrt(252)  # Annualized volatility
    
    def identify_chart_patterns(self, ohlc_data: pd.DataFrame) -> List[Dict[str, any]]:
        """Identify basic chart patterns"""
        patterns = []
        close = ohlc_data['close']
        high = ohlc_data['high']
        low = ohlc_data['low']
        
        try:
            # Simple pattern detection (can be expanded)
            # Double Top/Bottom detection (simplified)
            recent_highs = high.rolling(window=10).max()
            recent_lows = low.rolling(window=10).min()
            
            current_high = high.iloc[-1]
            current_low = low.iloc[-1]
            prev_high = recent_highs.iloc[-5]
            prev_low = recent_lows.iloc[-5]
            
            # Double top pattern (simplified)
            if abs(current_high - prev_high) / prev_high < 0.02:
                patterns.append({
                    'pattern': 'Double Top',
                    'signal': 'BEARISH',
                    'confidence': 'MODERATE'
                })
            
            # Double bottom pattern (simplified)
            if abs(current_low - prev_low) / prev_low < 0.02:
                patterns.append({
                    'pattern': 'Double Bottom',
                    'signal': 'BULLISH',
                    'confidence': 'MODERATE'
                })
            
        except Exception as e:
            self.logger.error(f"Error identifying chart patterns: {e}")
        
        return patterns
