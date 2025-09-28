# -*- coding: utf-8 -*-
"""
Advanced Logger Module for Zeus Trading Bot

Provides structured logging with different levels and file rotation.
"""

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
import json
from typing import Dict, Any, Optional
import sys


class TradingLogger:
    """Advanced logging system for trading operations"""
    
    def __init__(self, name: str = 'ZeusTradingBot', log_dir: str = 'logs', 
                 max_file_size: int = 10485760, backup_count: int = 5):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.max_file_size = max_file_size  # 10MB default
        self.backup_count = backup_count
        
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Setup different loggers for different purposes"""
        # Main application logger
        self.main_logger = self._create_logger(
            'main', 
            self.log_dir / 'zeus_bot.log',
            logging.INFO
        )
        
        # Trading operations logger
        self.trading_logger = self._create_logger(
            'trading',
            self.log_dir / 'trading.log',
            logging.INFO
        )
        
        # Error logger
        self.error_logger = self._create_logger(
            'errors',
            self.log_dir / 'errors.log',
            logging.ERROR
        )
        
        # Debug logger
        self.debug_logger = self._create_logger(
            'debug',
            self.log_dir / 'debug.log',
            logging.DEBUG
        )
        
        # Performance logger
        self.performance_logger = self._create_logger(
            'performance',
            self.log_dir / 'performance.log',
            logging.INFO
        )
    
    def _create_logger(self, name: str, log_file: Path, level: int) -> logging.Logger:
        """Create a logger with rotating file handler"""
        logger = logging.getLogger(f"{self.name}.{name}")
        logger.setLevel(level)
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        
        # Create console handler for errors
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Set formatters
        file_handler.setFormatter(detailed_formatter)
        console_handler.setFormatter(simple_formatter)
        
        # Add handlers
        logger.addHandler(file_handler)
        
        # Add console handler only for errors and critical
        if level >= logging.ERROR:
            logger.addHandler(console_handler)
        
        return logger
    
    def info(self, message: str, category: str = 'main', extra_data: Optional[Dict[str, Any]] = None):
        """Log info message"""
        logger = getattr(self, f'{category}_logger', self.main_logger)
        if extra_data:
            message = f"{message} | Data: {json.dumps(extra_data, default=str)}"
        logger.info(message)
    
    def warning(self, message: str, category: str = 'main', extra_data: Optional[Dict[str, Any]] = None):
        """Log warning message"""
        logger = getattr(self, f'{category}_logger', self.main_logger)
        if extra_data:
            message = f"{message} | Data: {json.dumps(extra_data, default=str)}"
        logger.warning(message)
    
    def error(self, message: str, category: str = 'errors', extra_data: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log error message"""
        logger = getattr(self, f'{category}_logger', self.error_logger)
        if extra_data:
            message = f"{message} | Data: {json.dumps(extra_data, default=str)}"
        logger.error(message, exc_info=exc_info)
    
    def debug(self, message: str, category: str = 'debug', extra_data: Optional[Dict[str, Any]] = None):
        """Log debug message"""
        logger = getattr(self, f'{category}_logger', self.debug_logger)
        if extra_data:
            message = f"{message} | Data: {json.dumps(extra_data, default=str)}"
        logger.debug(message)
    
    def critical(self, message: str, category: str = 'errors', extra_data: Optional[Dict[str, Any]] = None):
        """Log critical message"""
        logger = getattr(self, f'{category}_logger', self.error_logger)
        if extra_data:
            message = f"{message} | Data: {json.dumps(extra_data, default=str)}"
        logger.critical(message)
    
    def log_trade(self, symbol: str, side: str, quantity: float, price: float, 
                  order_id: str, status: str, timestamp: Optional[datetime] = None):
        """Log trading operations"""
        if timestamp is None:
            timestamp = datetime.now()
        
        trade_data = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'order_id': order_id,
            'status': status,
            'timestamp': timestamp.isoformat()
        }
        
        message = f"Trade Executed: {side} {quantity} {symbol} @ {price} | Order: {order_id} | Status: {status}"
        self.trading_logger.info(f"{message} | {json.dumps(trade_data)}")
    
    def log_signal(self, symbol: str, signal_type: str, strength: str, 
                   indicators: Dict[str, Any], recommendation: str):
        """Log trading signals"""
        signal_data = {
            'symbol': symbol,
            'signal_type': signal_type,
            'strength': strength,
            'indicators': indicators,
            'recommendation': recommendation,
            'timestamp': datetime.now().isoformat()
        }
        
        message = f"Signal Generated: {symbol} | {signal_type} | {strength} | Recommendation: {recommendation}"
        self.trading_logger.info(f"{message} | {json.dumps(signal_data, default=str)}")
    
    def log_performance(self, metric: str, value: float, symbol: Optional[str] = None, 
                       timeframe: Optional[str] = None):
        """Log performance metrics"""
        perf_data = {
            'metric': metric,
            'value': value,
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat()
        }
        
        message = f"Performance Metric: {metric} = {value}"
        if symbol:
            message += f" | Symbol: {symbol}"
        if timeframe:
            message += f" | Timeframe: {timeframe}"
        
        self.performance_logger.info(f"{message} | {json.dumps(perf_data)}")
    
    def log_risk_event(self, event_type: str, details: Dict[str, Any], severity: str = 'INFO'):
        """Log risk management events"""
        risk_data = {
            'event_type': event_type,
            'details': details,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }
        
        message = f"Risk Event: {event_type} | Severity: {severity}"
        
        if severity.upper() == 'ERROR':
            self.error(f"{message} | {json.dumps(risk_data, default=str)}", category='errors')
        elif severity.upper() == 'WARNING':
            self.warning(f"{message} | {json.dumps(risk_data, default=str)}", category='trading')
        else:
            self.info(f"{message} | {json.dumps(risk_data, default=str)}", category='trading')
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        stats = {}
        
        for log_file in self.log_dir.glob('*.log'):
            try:
                stats[log_file.stem] = {
                    'file_size': log_file.stat().st_size,
                    'last_modified': datetime.fromtimestamp(log_file.stat().st_mtime),
                    'line_count': sum(1 for _ in open(log_file, 'r', encoding='utf-8'))
                }
            except Exception as e:
                stats[log_file.stem] = {'error': str(e)}
        
        return stats
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old log files"""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cleaned_files = []
        
        for log_file in self.log_dir.glob('*.log.*'):  # Rotated files
            try:
                file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_date < cutoff_date:
                    log_file.unlink()
                    cleaned_files.append(str(log_file))
            except Exception as e:
                self.error(f"Error cleaning up log file {log_file}: {e}", exc_info=True)
        
        if cleaned_files:
            self.info(f"Cleaned up {len(cleaned_files)} old log files", 
                     extra_data={'cleaned_files': cleaned_files})
        
        return cleaned_files


# Global logger instance
zeus_logger = TradingLogger()

# Convenience functions
def log_info(message: str, category: str = 'main', **kwargs):
    zeus_logger.info(message, category, kwargs)

def log_error(message: str, category: str = 'errors', **kwargs):
    zeus_logger.error(message, category, kwargs, exc_info=True)

def log_trade(symbol: str, side: str, quantity: float, price: float, order_id: str, status: str):
    zeus_logger.log_trade(symbol, side, quantity, price, order_id, status)

def log_signal(symbol: str, signal_type: str, strength: str, indicators: dict, recommendation: str):
    zeus_logger.log_signal(symbol, signal_type, strength, indicators, recommendation)
