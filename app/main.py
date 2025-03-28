import os
import argparse
import time
import schedule
from datetime import datetime

from app.config.config import TRADING_SYMBOLS, TRADING_MODE, TIMEFRAMES
from app.utils.binance_client import BinanceClient
from app.utils.data_handler import DataHandler
from app.strategies.strategy_selector import StrategySelector
from app.models.order_manager import OrderManager
from app.risk_management.risk_manager import RiskManager
from app.notification.telegram_notifier import TelegramNotifier
from app.backtesting.backtest_engine import BacktestEngine
from app.utils.logger import get_logger

logger = get_logger()


class TradingBot:
    def __init__(
        self, symbols=TRADING_SYMBOLS, timeframes=TIMEFRAMES, trading_mode=TRADING_MODE
    ):
        self.symbols = symbols
        self.timeframes = timeframes
        self.trading_mode = trading_mode

        # Initialize components
        self.binance_client = BinanceClient()
        self.data_handler = DataHandler()
        self.order_manager = OrderManager()
        self.risk_manager = RiskManager()
        self.notifier = TelegramNotifier()

        # Create strategy selectors for each symbol
        self.strategy_selectors = {}
        for symbol in symbols:
            self.strategy_selectors[symbol] = StrategySelector(symbol, timeframes)

        logger.info(f"Trading bot initialized in {trading_mode} mode for {symbols}")
        self.notifier.send_message(
            f"🔄 Trading bot started in {trading_mode} mode for {', '.join(symbols)}"
        )

    def run_trading_cycle(self):
        """Run a single trading cycle - check signals and execute trades"""
        try:
            logger.info("Starting trading cycle")
            
            # Process each symbol
            for symbol in self.symbols:
                # Check for exit signals on open positions
                if symbol in self.order_manager.open_positions:
                    position = self.order_manager.open_positions[symbol]
                    
                    # Use the strategy that opened the position
                    strategy_selector = self.strategy_selectors[symbol]
                    market_data = self.data_handler.get_latest_market_data(symbol)
                    
                    # Skip if we couldn't get market data
                    if not market_data or len(market_data) == 0:
                        logger.warning(f"No market data available for {symbol}")
                        continue
                    
                    # Check if the strategy indicates we should exit
                    try:
                        strategy_name = position.get("strategy", "Unknown")
                        strategy = strategy_selector.get_strategy_by_name(strategy_name)
                        
                        if strategy and strategy.should_exit_trade(market_data, position):
                            # Close position
                            current_price = float(market_data["close"])
                            self.order_manager.close_position(symbol, current_price)
                    except KeyError as e:
                        logger.warning(f"Missing data when checking exit signal for {symbol}: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error checking exit signal for {symbol}: {e}")
                        continue
                
                # Check for entry signals if we don't have an open position
                if symbol not in self.order_manager.open_positions:
                    strategy_selector = self.strategy_selectors[symbol]
                    market_data = self.data_handler.get_latest_market_data(symbol)
                    
                    # Skip if we couldn't get market data
                    if not market_data or len(market_data) == 0:
                        logger.warning(f"No market data available for {symbol}")
                        continue
                    
                    # Check if any strategy indicates we should enter
                    try:
                        signal = strategy_selector.should_enter_trade(market_data)
                        
                        if signal and signal["should_enter"]:
                            # Get signal data
                            strategy_name = signal.get("strategy_name", "Unknown")
                            entry_price = float(market_data["close"])
                            signal_data = signal.get("signal_data", {})
                            
                            # Ensure we have stop loss and take profit
                            stop_loss = signal_data.get("stop_loss_price")
                            take_profit = signal_data.get("take_profit_price")
                            
                            if not stop_loss or not take_profit:
                                logger.warning(f"Missing stop loss or take profit for {symbol} entry signal")
                                continue
                            
                            # Log signal
                            logger.info(
                                f"Entry signal for {symbol} at {entry_price} "
                                f"(Strategy: {strategy_name}, SL: {stop_loss}, TP: {take_profit})"
                            )

                            # Calculate position size
                            quantity = self.risk_manager.calculate_position_size(
                                symbol, entry_price, stop_loss
                            )

                            # Open position
                            self.order_manager.open_position(
                                symbol=symbol,
                                entry_price=entry_price,
                                quantity=quantity,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                strategy_type=strategy_name,
                                signal_data=signal_data,
                            )
                    except KeyError as e:
                        logger.warning(f"Missing data when checking entry signal for {symbol}: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error checking entry signal for {symbol}: {e}")
                        continue

            # Send periodic status update (every 4 hours)
            current_hour = datetime.now().hour
            if current_hour % 4 == 0 and datetime.now().minute < 5:
                self._send_status_update()

            return True

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            self.notifier.send_error(f"Error in trading cycle: {str(e)}")
            return True  # Continue trading despite error

    def _get_timeframe_minutes(self, timeframe):
        """Convert timeframe to minutes for comparison"""
        unit = timeframe[-1]
        value = int(timeframe[:-1])

        if unit == "m":
            return value
        elif unit == "h":
            return value * 60
        elif unit == "d":
            return value * 1440
        else:
            return 0

    def _send_status_update(self):
        """Send status update to Telegram"""
        # Calculate and send performance metrics
        metrics = self.risk_manager.calculate_metrics()
        self.notifier.send_system_status(metrics)

    def run_backtest(self, start_date, end_date, initial_balance=10000):
        """Run backtest for all symbols"""
        results = {}

        for symbol in self.symbols:
            logger.info(f"Starting backtest for {symbol}")
            backtest = BacktestEngine(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframes=self.timeframes,
                initial_balance=initial_balance,
            )

            # Run backtest
            result = backtest.run_backtest()
            if result:
                results[symbol] = result

                # Generate and save plot
                plots_dir = os.path.join("logs", "backtest_plots")
                os.makedirs(plots_dir, exist_ok=True)
                plot_path = os.path.join(
                    plots_dir,
                    f"{symbol}_backtest_{datetime.now().strftime('%Y%m%d')}.png",
                )
                backtest.plot_results(save_path=plot_path)

        # Calculate and log overall results
        if results:
            total_profit = sum(result["total_profit"] for result in results.values())
            avg_win_rate = sum(result["win_rate"] for result in results.values()) / len(
                results
            )
            avg_profit_factor = sum(
                result["profit_factor"] for result in results.values()
            ) / len(results)

            logger.info("===== Overall Backtest Results =====")
            logger.info(f"Total Profit: {total_profit:.2f} USDT")
            logger.info(f"Average Win Rate: {avg_win_rate:.2%}")
            logger.info(f"Average Profit Factor: {avg_profit_factor:.2f}")
            logger.info("===================================")

        return results

    def run_forever(self, interval=1):
        """Run trading bot in a continuous loop"""
        if self.trading_mode == "backtest":
            logger.error("Cannot run forever in backtest mode")
            return

        logger.info(f"Starting trading bot with {interval} minute interval")
        self.notifier.send_message(
            f"🚀 Trading bot running with {interval} minute interval"
        )

        # Run immediately
        self.run_trading_cycle()

        # Schedule regular runs
        schedule.every(interval).minutes.do(self.run_trading_cycle)

        # Send daily summaries
        schedule.every().day.at("00:00").do(self._send_status_update)

        try:
            while True:
                schedule.run_pending()
                time.sleep(10)  # Sleep 10 seconds between checks
        except KeyboardInterrupt:
            logger.info("Trading bot stopped by user")
            self.notifier.send_message("🛑 Trading bot stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.notifier.send_error(f"❌ Trading bot crashed: {e}")


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Binance Futures Trading Bot")
    parser.add_argument(
        "--mode",
        type=str,
        default=TRADING_MODE,
        choices=["live", "paper", "backtest"],
        help="Trading mode",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(TRADING_SYMBOLS),
        help="Trading symbols (comma-separated)",
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default=",".join(TIMEFRAMES),
        help="Timeframes to analyze (comma-separated)",
    )
    parser.add_argument(
        "--interval", type=int, default=1, help="Trading cycle interval in minutes"
    )
    parser.add_argument(
        "--backtest-start",
        type=str,
        default="2023-01-01",
        help="Backtest start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--backtest-end",
        type=str,
        default="2023-12-31",
        help="Backtest end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        default=10000,
        help="Initial balance for backtesting",
    )

    args = parser.parse_args()

    # Initialize trading bot
    bot = TradingBot(
        symbols=args.symbols.split(","),
        timeframes=args.timeframes.split(","),
        trading_mode=args.mode,
    )

    # Run in the appropriate mode
    if args.mode == "backtest":
        logger.info(
            f"Running backtest from {args.backtest_start} to {args.backtest_end}"
        )
        bot.run_backtest(args.backtest_start, args.backtest_end, args.initial_balance)
    else:
        # Run in live/paper mode
        logger.info(f"Running in {args.mode} mode with {args.interval} minute interval")
        bot.run_forever(args.interval)


if __name__ == "__main__":
    main()
