import argparse
import logging
import os
from datetime import datetime
import config
from trader import BinanceFuturesTrader
from backtest import Backtester
from telegram_bot import TelegramNotifier

# Set up logging
os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(config.LOG_DIR, f"main_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def run_trading_bot(interval_seconds=60):
    """Run the trading bot"""
    trader = BinanceFuturesTrader()
    trader.run(interval_seconds=interval_seconds)

def run_backtest(symbol=None, timeframe=None, start_date=None, end_date=None, plot=True):
    """Run backtesting on historical data"""
    backtester = Backtester(
        symbol=symbol or config.SYMBOL,
        timeframe=timeframe or config.TIMEFRAME,
        start_date=start_date or "1 month ago UTC",
        end_date=end_date
    )
    
    results = backtester.run_backtest()
    
    if results and plot:
        # Create plots directory if it doesn't exist
        plots_dir = os.path.join(config.DATA_DIR, 'plots')
        os.makedirs(plots_dir, exist_ok=True)
        
        # Plot and save results
        plot_filename = os.path.join(plots_dir, f"backtest_{config.SYMBOL}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        backtester.plot_results(save_path=plot_filename)
    
    # Send backtest results to Telegram if configured
    if results:
        notifier = TelegramNotifier()
        notifier.send_backtest_results(
            results['symbol'],
            results['timeframe'],
            results['start_date'],
            results['end_date'],
            results['total_trades'],
            results['win_rate'],
            results['profit_loss']
        )
    
    return results

def optimize_strategy(symbol=None, timeframe=None, start_date=None, end_date=None):
    """Optimize trading strategy parameters"""
    backtester = Backtester(
        symbol=symbol or config.SYMBOL,
        timeframe=timeframe or config.TIMEFRAME,
        start_date=start_date or "3 months ago UTC",
        end_date=end_date
    )
    
    # Define parameter grid for optimization
    param_grid = {
        'ema_fast': [8, 12, 16],
        'ema_slow': [21, 26, 34],
        'rsi_period': [7, 14, 21],
        'rsi_oversold': [20, 30, 40],
        'rsi_overbought': [60, 70, 80]
    }
    
    # Run optimization
    best_params, best_results, results_df = backtester.optimize_strategy(param_grid)
    
    if best_results:
        # Plot results with best parameters
        plots_dir = os.path.join(config.DATA_DIR, 'plots')
        os.makedirs(plots_dir, exist_ok=True)
        
        # Save optimization results
        results_path = os.path.join(config.DATA_DIR, f"optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        results_df.to_csv(results_path)
        logger.info(f"Optimization results saved to {results_path}")
        
        # Plot the best backtest
        plot_filename = os.path.join(plots_dir, f"optimized_{config.SYMBOL}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        backtester.plot_results(save_path=plot_filename)
        
        # Send results to Telegram
        notifier = TelegramNotifier()
        
        message = f"📊 *Strategy Optimization Results*\n"
        message += f"*Symbol:* {best_results['symbol']}\n"
        message += f"*Timeframe:* {best_results['timeframe']}\n\n"
        message += f"*Best Parameters:*\n"
        for param, value in best_params.items():
            message += f"- {param}: {value}\n"
        message += f"\n*Performance:*\n"
        message += f"- Total Trades: {best_results['total_trades']}\n"
        message += f"- Win Rate: {best_results['win_rate']:.2f}%\n"
        message += f"- P&L: {best_results['profit_loss']:.2f}%\n"
        message += f"- Max Drawdown: {best_results['max_drawdown']:.2f}%\n"
        message += f"- Sharpe Ratio: {best_results['sharpe_ratio']:.2f}"
        
        notifier.send_message(message)
    
    return best_params, best_results

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Binance Futures Trading Bot')
    parser.add_argument('--mode', type=str, choices=['trade', 'backtest', 'optimize'], default='trade',
                        help='Bot operation mode: trade, backtest, or optimize')
    parser.add_argument('--interval', type=int, default=60,
                        help='Trading interval in seconds (for trade mode)')
    parser.add_argument('--symbol', type=str, default=None,
                        help='Trading symbol (e.g., BTCUSDT)')
    parser.add_argument('--timeframe', type=str, default=None,
                        help='Trading timeframe (e.g., 1h, 15m, 4h)')
    parser.add_argument('--start-date', type=str, default=None,
                        help='Start date for backtesting (e.g., "1 month ago UTC")')
    parser.add_argument('--end-date', type=str, default=None,
                        help='End date for backtesting')
    parser.add_argument('--no-plot', action='store_true',
                        help='Disable plotting for backtest mode')
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'trade':
            logger.info("Starting in trading mode")
            run_trading_bot(interval_seconds=args.interval)
        
        elif args.mode == 'backtest':
            logger.info("Starting in backtest mode")
            run_backtest(
                symbol=args.symbol,
                timeframe=args.timeframe,
                start_date=args.start_date,
                end_date=args.end_date,
                plot=not args.no_plot
            )
        
        elif args.mode == 'optimize':
            logger.info("Starting in optimization mode")
            optimize_strategy(
                symbol=args.symbol,
                timeframe=args.timeframe,
                start_date=args.start_date,
                end_date=args.end_date
            )
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        notifier = TelegramNotifier()
        notifier.send_error_notification(f"Fatal error: {e}")

if __name__ == "__main__":
    main() 