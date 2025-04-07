import logging
import sys
import argparse
from src.trading_bot import TradingBot
from config.config import TESTNET

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/trading.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("main")

def parse_arguments():
    parser = argparse.ArgumentParser(description='Binance Futures Trading Bot')
    parser.add_argument('--interval', type=str, default='1h', 
                        help='Trading interval (e.g., 1m, 5m, 15m, 1h, 4h, 1d)')
    parser.add_argument('--check-interval', type=int, default=3600,
                        help='Time in seconds between strategy checks')
    parser.add_argument('--testnet', action='store_true', default=TESTNET,
                        help='Use Binance testnet (default: based on config)')
    parser.add_argument('--paper-trading', action='store_true', default=False,
                        help='Run in paper trading mode (no real orders)')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Enable debug mode with more verbose logging')
    parser.add_argument('--force-check', action='store_true', default=False,
                        help='Force immediate strategy check without waiting')
    return parser.parse_args()

def main():
    args = parse_arguments()

    # Set logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    mode = "Testnet" if args.testnet else "Production"
    if args.paper_trading:
        mode = "Paper Trading"

    logger.info(f"Starting Binance Futures Trading Bot in {mode} mode")

    try:
        bot = TradingBot(testnet=args.testnet, paper_trading=args.paper_trading, debug=args.debug)
        bot.run(interval=args.interval, check_interval=args.check_interval, force_check=args.force_check)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
