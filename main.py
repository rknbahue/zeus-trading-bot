#!/usr/bin/env python3
"""
Zeus Trading Bot - Main Entry Point
A sophisticated trading bot with risk management, analysis modules, and web dashboard.
"""
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from modules.logger import get_logger if False else None  # placeholder compatibility
from modules.risk_manager import RiskManager
from modules.exchange_interface import ExchangeManager, BinanceInterface
from modules.position_reconciler import PositionReconciler

try:
    from aiohttp import web
except Exception:
    web = None


class ZeusTradingBot:
    def __init__(self):
        self.logger = self._setup_logging()
        self.logger.info("Initializing Zeus Trading Bot...")
        self.is_running = False

        # Core components
        self.exchange_manager = ExchangeManager()
        # For demo/paper, allow empty keys; user will set .env in real run
        self.exchange_manager.add_exchange('binance', BinanceInterface('<api_key>', '<secret>', testnet=True))
        self.risk_manager = RiskManager(initial_balance=10000.0)
        self.reconciler = PositionReconciler(self.exchange_manager, self.risk_manager)

        # Health cache
        self._health: Dict[str, Any] = {}

        # Web app
        self.app = web.Application() if web else None
        self._site = None

    def _setup_logging(self):
        log_dir = Path("logs"); log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / f"zeus_bot_{datetime.now().strftime('%Y%m%d')}.log"),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger('ZeusBot')

    async def _serve(self):
        if not self.app:
            return
        self.app.router.add_get('/health', self._health_handler)
        runner = web.AppRunner(self.app)
        await runner.setup()
        self._site = web.TCPSite(runner, '0.0.0.0', 8000)
        await self._site.start()
        self.logger.info("HTTP server started on :8000")

    async def _health_handler(self, request):
        try:
            snap = self.reconciler.get_health_snapshot()
        except Exception:
            snap = {}
        # Normalize fields required by task: breaker, ws, exposición, slippage, latencia
        payload = {
            'breaker': snap.get('breaker', 'closed'),
            'ws': snap.get('ws', {}),
            'exposicion_pct': snap.get('exposure_pct', 0.0),
            'slippage_bps': snap.get('slippage_bps', 0.0),
            'latencia_ms': snap.get('latency_ms', 0.0),
            'fill_rate': snap.get('fill_rate', 0.0),
            'ultimo_error': snap.get('last_error'),
        }
        return web.json_response(payload)

    async def start(self):
        try:
            self.logger.info("Starting Zeus Trading Bot...")
            self.is_running = True

            await self.exchange_manager.connect_all()

            # Start reconciler and web server
            asyncio.create_task(self.reconciler.loop())
            await self._serve()

            await self._main_loop()
        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            raise

    async def _main_loop(self):
        self.logger.info("Starting main trading loop...")
        while self.is_running:
            try:
                # Periodically refresh health cache
                self._health = self.reconciler.get_health_snapshot()
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.logger.info("Stopping Zeus Trading Bot...")
        self.is_running = False
        await self.exchange_manager.close_all()
        await self.reconciler.stop()
        self.logger.info("Zeus Trading Bot stopped")


async def main():
    bot = ZeusTradingBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\nReceived interrupt signal...")
        await bot.stop()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        await bot.stop()
        raise

if __name__ == "__main__":
    print("Zeus Trading Bot v1.0.0")
    print("=" * 50)
    print("Starting bot...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Bot crashed: {e}")
        raise
