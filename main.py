#!/usr/bin/env python3
"""
SNIPER V12 QUAD-CHANNEL
Bot de trading automatizado para IQ Option
4 canais paralelos: OTC M1, OTC M5, REAL M1, REAL M5
"""

import sys
import os
import signal
import logging
import time
import threading
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from integrations.iq_option import IQOptionClient
from integrations.forex_factory import ForexFactoryCalendar
from integrations.twelve_data import TwelveDataClient
from integrations.finnhub_api import FinnhubClient
from protections.manager import ProtectionManager
from channels.otc_m1 import OtcM1Channel
from channels.otc_m5 import OtcM5Channel
from channels.real_m1 import RealM1Channel
from channels.real_m5 import RealM5Channel
from dashboard.server import create_dashboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('sniper_v12.log', mode='a')
    ]
)
logger = logging.getLogger("SNIPER_V12")


class SniperV12:
    """Main bot controller."""

    def __init__(self):
        self.running = False
        self.mode = "UNKNOWN"
        self.channels = []
        self.iq_client = None
        self.protections = None
        self.forex_factory = None
        self.twelve_data = None
        self.finnhub = None
        self.bot_state = {}

    def detect_mode(self) -> str:
        """Detect trading mode based on current time (BRT = UTC-3).
        
        Mon-Fri 00h→18h BRT → HYBRID (all 4 channels)
        Fri after 18h BRT → OTC PURE
        Saturday → OTC PURE
        Sunday until 18h BRT → OTC PURE
        """
        # Get current time in BRT (UTC-3)
        from datetime import timezone, timedelta
        brt = timezone(timedelta(hours=-3))
        now = datetime.now(brt)

        weekday = now.weekday()  # 0=Monday, 6=Sunday
        hour = now.hour

        if weekday == 5:  # Saturday
            return "OTC_PURE"
        elif weekday == 6:  # Sunday
            if hour < 18:
                return "OTC_PURE"
            else:
                return "HYBRID"
        elif weekday == 4:  # Friday
            if hour >= 18:
                return "OTC_PURE"
            else:
                return "HYBRID"
        elif 0 <= weekday <= 3:  # Mon-Thu
            return "HYBRID"

        return "HYBRID"

    def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("=" * 60)
        logger.info("   SNIPER V12 QUAD-CHANNEL - INITIALIZING")
        logger.info("=" * 60)

        # 1. Connect to IQ Option
        logger.info("Connecting to IQ Option...")
        self.iq_client = IQOptionClient(
            email=config.IQ_EMAIL,
            password=config.IQ_PASSWORD,
            mode=config.IQ_MODE
        )

        if not self.iq_client.connect():
            logger.critical("Failed to connect to IQ Option. Exiting.")
            return False

        balance = self.iq_client.get_balance()
        logger.info(f"Connected! Mode: {config.IQ_MODE} | Balance: ${balance:.2f}")

        # 2. Initialize protections
        self.protections = ProtectionManager(
            daily_stop_limit=config.DAILY_STOP,
            sequential_stop_limit=config.SEQ_STOP,
            seq_pause_minutes=config.SEQ_PAUSE,
            cooldown_seconds=config.COOLDOWN
        )
        logger.info("Protection manager initialized")

        # 3. Initialize integrations
        self.forex_factory = ForexFactoryCalendar()
        self.forex_factory.start_background_update()
        logger.info("ForexFactory calendar monitor started")

        self.twelve_data = TwelveDataClient(api_key=config.TWELVE_DATA_KEY)
        self.twelve_data.start_background_update(interval_seconds=300)
        logger.info("Twelve Data DXY monitor started")

        self.finnhub = FinnhubClient(api_key=config.FINNHUB_KEY)
        self.finnhub.start_background_monitor(interval_seconds=120)
        logger.info("Finnhub news monitor started")

        # 4. Detect mode
        self.mode = self.detect_mode()
        logger.info(f"Trading mode: {self.mode}")

        # 5. Create channels
        self._create_channels()

        # 6. Setup bot state for dashboard
        self.bot_state = {
            "iq_client": self.iq_client,
            "protections": self.protections,
            "channels": self.channels,
            "mode": self.mode,
            "forex_factory": self.forex_factory,
            "twelve_data": self.twelve_data,
            "finnhub": self.finnhub
        }

        # 7. Start dashboard
        create_dashboard(config.PORT, self.bot_state)
        logger.info(f"Dashboard running on port {config.PORT}")

        return True

    def _create_channels(self):
        """Create channel instances based on current mode."""
        common_kwargs = {
            "iq_client": self.iq_client,
            "protections": self.protections,
            "forex_factory": self.forex_factory,
            "twelve_data": self.twelve_data,
            "finnhub": self.finnhub
        }

        # Always create OTC channels
        otc_m1 = OtcM1Channel(pairs=config.OTC_PAIRS, **common_kwargs)
        otc_m5 = OtcM5Channel(pairs=config.OTC_PAIRS, m1_channel=otc_m1, **common_kwargs)

        self.channels = [otc_m1, otc_m5]

        if self.mode == "HYBRID":
            real_m1 = RealM1Channel(pairs=config.REAL_PAIRS, **common_kwargs)
            real_m5 = RealM5Channel(pairs=config.REAL_PAIRS, m1_channel=real_m1, **common_kwargs)
            self.channels.extend([real_m1, real_m5])

        logger.info(f"Channels created: {[ch.name for ch in self.channels]}")

    def start(self):
        """Start all channels."""
        self.running = True
        logger.info("Starting all channels...")

        for channel in self.channels:
            channel.start()
            time.sleep(2)  # Stagger starts

        logger.info("=" * 60)
        logger.info("   SNIPER V12 IS LIVE!")
        logger.info(f"   Mode: {self.mode}")
        logger.info(f"   Channels: {len(self.channels)}")
        logger.info(f"   Balance: ${self.iq_client.get_balance():.2f}")
        logger.info(f"   Entry: {config.ENTRY_PERCENT * 100}% of balance")
        logger.info(f"   Dashboard: http://0.0.0.0:{config.PORT}")
        logger.info("=" * 60)

        # Mode detection loop (check every 5 minutes)
        self._mode_monitor()

    def _mode_monitor(self):
        """Monitor and switch modes when needed."""
        while self.running:
            try:
                new_mode = self.detect_mode()
                if new_mode != self.mode:
                    logger.info(f"MODE CHANGE: {self.mode} → {new_mode}")
                    self.mode = new_mode
                    self.bot_state["mode"] = new_mode

                    # Stop current channels
                    for ch in self.channels:
                        ch.stop()

                    # Recreate channels for new mode
                    self._create_channels()
                    self.bot_state["channels"] = self.channels

                    # Start new channels
                    for ch in self.channels:
                        ch.start()
                        time.sleep(2)

                time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Mode monitor error: {e}")
                time.sleep(60)

    def stop(self):
        """Gracefully stop the bot."""
        logger.info("Stopping Sniper V12...")
        self.running = False
        for channel in self.channels:
            channel.stop()
        logger.info("All channels stopped. Goodbye!")


def main():
    """Entry point."""
    bot = SniperV12()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize and start
    if not bot.initialize():
        logger.critical("Initialization failed. Exiting.")
        sys.exit(1)

    bot.start()


if __name__ == "__main__":
    main()
