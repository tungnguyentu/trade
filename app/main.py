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
        """Run a single trading cycle (check signals, manage positions)"""
        logger.info(f"Running trading cycle at {datetime.now()}")

        # Check if we should continue trading based on risk management
        if not self.risk_manager.should_continue_trading():
            logger.warning("Maximum drawdown reached, stopping trading")
            self.notifier.send_error(
                "⚠️ Maximum drawdown reached, trading stopped! Please restart manually."
            )
            return False

        try:
            # Process each symbol
            for symbol in self.symbols:
                # Fetch current market data
                data_dict = self.data_handler.prepare_data_for_strategy(
                    symbol, self.timeframes
                )

                # Skip if no data available
                if not data_dict:
                    logger.warning(f"No data available for {symbol}, skipping")
                    continue

                # Prepare data for strategy
                self.strategy_selectors[symbol].prepare_strategies(data_dict)

                # Check if we have an open position for this symbol
                position_exists = symbol in self.order_manager.open_positions

                if position_exists:
                    # Get the appropriate strategy for checking exit signals
                    position = self.order_manager.open_positions[symbol]
                    if position["strategy"] == "Scalping":
                        strategy = self.strategy_selectors[symbol].scalping_strategy
                    else:
                        strategy = self.strategy_selectors[symbol].swing_strategy

                    if not strategy:
                        continue

                    # Get latest data for the primary timeframe
                    primary_tf = min(
                        self.timeframes, key=lambda x: self._get_timeframe_minutes(x)
                    )
                    if primary_tf not in data_dict:
                        primary_tf = next(iter(data_dict))

                    # Check for exit signals
                    self.order_manager.check_open_positions(
                        symbol, data_dict[primary_tf], strategy
                    )
                else:
                    # Check for entry signals
                    should_enter, signal_data, strategy_name = self.strategy_selectors[
                        symbol
                    ].should_enter_trade()

                    if should_enter and signal_data:
                        # Calculate entry parameters
                        entry_price = signal_data["price"]
                        is_long = signal_data["type"] == "long"

                        # Get strategy for calculating stop loss and take profit
                        best_strategy, _ = self.strategy_selectors[
                            symbol
                        ].get_best_strategy()

                        # Calculate stop loss and take profit
                        stop_loss = best_strategy.calculate_stop_loss(
                            entry_price, is_long
                        )
                        take_profit = best_strategy.calculate_take_profit(
                            entry_price, is_long
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

            # Send periodic status update (every 4 hours)
            current_hour = datetime.now().hour
            if current_hour % 4 == 0 and datetime.now().minute < 5:
                self._send_status_update()

            return True

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            self.notifier.send_error(f"Error in trading cycle: {e}")
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
