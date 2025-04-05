import logging
import sys
import argparse
import pandas as pd
import os
from datetime import datetime
from src.backtester import Backtester
from src.binance_client import BinanceFuturesClient
from strategies.ma_crossover import MACrossoverStrategy
from strategies.rsi_strategy import RSIStrategy
from config.config import SYMBOL, SHORT_WINDOW, LONG_WINDOW, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/backtest.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("backtest")

def parse_arguments():
    parser = argparse.ArgumentParser(description='Binance Futures Trading Bot Backtester')
    parser.add_argument('--strategy', type=str, default='ma_crossover', 
                        choices=['ma_crossover', 'rsi'],
                        help='Trading strategy to backtest')
    parser.add_argument('--interval', type=str, default='1h', 
                        help='Trading interval (e.g., 1m, 5m, 15m, 1h, 4h, 1d)')
    parser.add_argument('--days', type=int, default=30,
                        help='Number of days of historical data to use')
    parser.add_argument('--initial-balance', type=float, default=1000.0,
                        help='Initial account balance in USDT')
    parser.add_argument('--commission', type=float, default=0.0004,
                        help='Commission rate per trade (default: 0.04%)')
    parser.add_argument('--file', type=str, default=None,
                        help='CSV file with historical data (optional)')
    parser.add_argument('--output-dir', type=str, default='backtest_results',
                        help='Directory to save backtest results')
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    logger.info(f"Starting backtest with {args.strategy} strategy on {SYMBOL} {args.interval} data")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize strategy
    if args.strategy == 'ma_crossover':
        strategy = MACrossoverStrategy(short_window=SHORT_WINDOW, long_window=LONG_WINDOW)
    elif args.strategy == 'rsi':
        strategy = RSIStrategy(period=RSI_PERIOD, overbought=RSI_OVERBOUGHT, oversold=RSI_OVERSOLD)
    else:
        logger.error(f"Unknown strategy: {args.strategy}")
        return 1
    
    # Initialize backtester
    backtester = Backtester(
        strategy=strategy,
        initial_balance=args.initial_balance,
        commission=args.commission
    )
    
    # Load historical data
    if args.file:
        # Load from CSV file
        df = backtester.load_historical_data(file_path=args.file)
    else:
        # Fetch from Binance API
        client = BinanceFuturesClient()
        limit = args.days * 24  # Assuming 1h candles, adjust for other intervals
        klines = client.get_historical_klines(SYMBOL, args.interval, limit)
        if not klines:
            logger.error("Failed to fetch historical data")
            return 1
        df = backtester.load_historical_data(klines=klines, interval=args.interval)
    
    if df is None or df.empty:
        logger.error("No data available for backtest")
        return 1
    
    # Run backtest
    results_df = backtester.run(df)
    
    # Get performance metrics
    metrics = backtester.get_performance_metrics()
    
    # Print results
    logger.info("Backtest Results:")
    logger.info(f"Total Trades: {metrics['total_trades']}")
    logger.info(f"Win Rate: {metrics['win_rate']:.2f}%")
    logger.info(f"Profit Factor: {metrics['profit_factor']:.2f}")
    logger.info(f"Total Return: {metrics['total_return']:.2f}%")
    logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
    logger.info(f"Average Profit per Trade: {metrics['avg_profit']:.2f} USDT")
    logger.info(f"Expectancy: {metrics['expectancy']:.2f} USDT")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"{args.output_dir}/{SYMBOL}_{args.strategy}_{args.interval}_{timestamp}.csv"
    results_df.to_csv(results_file)
    logger.info(f"Saved backtest data to {results_file}")
    
    # Save trades list
    trades_df = pd.DataFrame(backtester.trades)
    if not trades_df.empty:
        trades_file = f"{args.output_dir}/{SYMBOL}_{args.strategy}_{args.interval}_{timestamp}_trades.csv"
        trades_df.to_csv(trades_file)
        logger.info(f"Saved trades data to {trades_file}")
    
    # Create and save plots
    plot_file = f"{args.output_dir}/{SYMBOL}_{args.strategy}_{args.interval}_{timestamp}.png"
    backtester.plot_results(results_df, save_path=plot_file)
    
    # Create interactive chart
    interactive_file = f"{args.output_dir}/{SYMBOL}_{args.strategy}_{args.interval}_{timestamp}.html"
    backtester.create_interactive_chart(results_df, save_path=interactive_file)
    
    logger.info("Backtest completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())