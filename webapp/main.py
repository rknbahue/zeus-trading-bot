# -*- coding: utf-8 -*-
"""
FastAPI Web Dashboard for Zeus Trading Bot

Provides web interface for monitoring and controlling the trading bot.
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
import os
import sys

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.risk_manager import RiskManager, RiskParameters
from modules.technical_analyzer import TechnicalAnalyzer
from modules.exchange_interface import ExchangeManager, BinanceInterface
from modules.logger import zeus_logger


# Global bot state
bot_state = {
    "is_running": False,
    "start_time": None,
    "total_trades": 0,
    "daily_pnl": 0.0,
    "current_positions": {},
    "last_signals": [],
    "exchange_status": "disconnected"
}

# Initialize components
risk_manager = RiskManager(initial_balance=10000.0)  # $10k demo balance
technical_analyzer = TechnicalAnalyzer()
exchange_manager = ExchangeManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    zeus_logger.info("Starting Zeus Trading Bot Web Dashboard", category='main')
    # Initialize demo data
    bot_state["start_time"] = datetime.now()
    
    yield
    
    # Shutdown
    zeus_logger.info("Shutting down Zeus Trading Bot Web Dashboard", category='main')


app = FastAPI(
    title="Zeus Trading Bot Dashboard",
    description="Advanced cryptocurrency trading bot with risk management",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files and templates
templates = Jinja2Templates(directory="webapp/templates")
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "bot_state": bot_state,
        "risk_metrics": risk_manager.get_risk_metrics()
    })


@app.get("/api/status")
async def get_bot_status() -> Dict[str, Any]:
    """Get current bot status"""
    uptime = None
    if bot_state["start_time"]:
        uptime = str(datetime.now() - bot_state["start_time"])
    
    return {
        "status": "running" if bot_state["is_running"] else "stopped",
        "uptime": uptime,
        "total_trades": bot_state["total_trades"],
        "daily_pnl": bot_state["daily_pnl"],
        "positions_count": len(bot_state["current_positions"]),
        "exchange_status": bot_state["exchange_status"],
        "last_update": datetime.now().isoformat()
    }


@app.post("/api/bot/start")
async def start_bot():
    """Start the trading bot"""
    if bot_state["is_running"]:
        raise HTTPException(status_code=400, detail="Bot is already running")
    
    bot_state["is_running"] = True
    bot_state["start_time"] = datetime.now()
    
    zeus_logger.info("Trading bot started via web interface", category='trading')
    
    return {"message": "Trading bot started successfully", "status": "running"}


@app.post("/api/bot/stop")
async def stop_bot():
    """Stop the trading bot"""
    if not bot_state["is_running"]:
        raise HTTPException(status_code=400, detail="Bot is not running")
    
    bot_state["is_running"] = False
    
    zeus_logger.info("Trading bot stopped via web interface", category='trading')
    
    return {"message": "Trading bot stopped successfully", "status": "stopped"}


@app.get("/api/risk-metrics")
async def get_risk_metrics() -> Dict[str, Any]:
    """Get current risk management metrics"""
    return risk_manager.get_risk_metrics()


@app.get("/api/positions")
async def get_positions() -> Dict[str, Any]:
    """Get current trading positions"""
    return {
        "positions": bot_state["current_positions"],
        "count": len(bot_state["current_positions"]),
        "total_value": sum(
            pos.get("quantity", 0) * pos.get("current_price", 0) 
            for pos in bot_state["current_positions"].values()
        )
    }


@app.get("/api/signals")
async def get_recent_signals() -> List[Dict[str, Any]]:
    """Get recent trading signals"""
    return bot_state["last_signals"][-10:]  # Last 10 signals


@app.post("/api/manual-trade")
async def place_manual_trade(
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    price: Optional[float] = None
):
    """Place a manual trade"""
    try:
        # Validate trade with risk manager
        current_price = price or 50000.0  # Demo price
        
        if not risk_manager.validate_trade(symbol, side, quantity, current_price):
            raise HTTPException(status_code=400, detail="Trade rejected by risk management")
        
        # Simulate trade execution
        trade_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Add to positions
        bot_state["current_positions"][symbol] = {
            "side": side,
            "quantity": quantity,
            "entry_price": current_price,
            "current_price": current_price,
            "pnl": 0.0,
            "timestamp": datetime.now().isoformat()
        }
        
        bot_state["total_trades"] += 1
        
        zeus_logger.log_trade(symbol, side, quantity, current_price, trade_id, "filled")
        
        return {
            "message": "Manual trade executed successfully",
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": current_price
        }
        
    except Exception as e:
        zeus_logger.error(f"Manual trade failed: {e}", category='trading')
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/performance")
async def get_performance_metrics() -> Dict[str, Any]:
    """Get performance metrics"""
    # Demo performance data
    return {
        "daily_return": 2.5,
        "total_return": 15.7,
        "win_rate": 68.4,
        "sharpe_ratio": 1.85,
        "max_drawdown": -5.2,
        "total_trades": bot_state["total_trades"],
        "profitable_trades": int(bot_state["total_trades"] * 0.684),
        "avg_trade_duration": "4.2 hours",
        "best_trade": 8.5,
        "worst_trade": -2.1
    }


@app.get("/api/market-data/{symbol}")
async def get_market_data(symbol: str) -> Dict[str, Any]:
    """Get market data for a symbol"""
    # Demo market data
    import random
    base_price = 50000.0
    
    return {
        "symbol": symbol,
        "price": base_price + random.uniform(-1000, 1000),
        "change_24h": random.uniform(-5, 5),
        "volume_24h": random.uniform(1000000, 5000000),
        "high_24h": base_price + random.uniform(0, 2000),
        "low_24h": base_price - random.uniform(0, 2000),
        "timestamp": datetime.now().isoformat()
    }


@app.websocket("/ws/live-data")
async def websocket_endpoint(websocket):
    """WebSocket endpoint for live data updates"""
    await websocket.accept()
    
    try:
        while True:
            # Send live updates every 5 seconds
            data = {
                "type": "status_update",
                "data": await get_bot_status(),
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send_json(data)
            await asyncio.sleep(5)
            
    except Exception as e:
        zeus_logger.error(f"WebSocket error: {e}", category='main')
    finally:
        await websocket.close()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
