import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import logging
from datetime import datetime
from binance_client import BinanceClient
from indicators import add_combined_strategy
import config

logger = logging.getLogger(__name__)

class Backtester:
    def __init__(self, symbol=None, timeframe=None, start_date=None, end_date=None):
        self.symbol = symbol or config.SYMBOL
        self.timeframe = timeframe or config.TIMEFRAME
        self.start_date = start_date or "1 month ago UTC"
        self.end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        self.client = BinanceClient()
        self.results = None
        
        # Create data directory if it doesn't exist
        os.makedirs(config.DATA_DIR, exist_ok=True)
        
    def load_data(self):
        """Load historical data for backtesting"""
        logger.info(f"Loading historical data for {self.symbol} ({self.timeframe}) from {self.start_date} to {self.end_date}")
        
        # Check if we have cached data
        filename = f"{config.DATA_DIR}/{self.symbol}_{self.timeframe}_{self.start_date}_{self.end_date}.csv"
        filename = filename.replace(" ", "_").replace("/", "-")
        
        if os.path.exists(filename):
            logger.info(f"Loading data from cache: {filename}")
            return pd.read_csv(filename, index_col='timestamp', parse_dates=True)
        
        # Load data from Binance
        df = self.client.get_historical_klines(
            symbol=self.symbol, 
            interval=self.timeframe,
            start_str=self.start_date,
            limit=1000
        )
        
        if df.empty:
            logger.error(f"No data returned for {self.symbol}")
            return None
            
        # Save to cache for future use
        df.to_csv(filename)
        
        return df
    
    def run_backtest(self, strategy_params=None):
        """Run backtest with the specified strategy"""
        # Default strategy parameters
        if strategy_params is None:
            strategy_params = {
                'ema_fast': config.EMA_FAST,
                'ema_slow': config.EMA_SLOW,
                'rsi_period': config.RSI_PERIOD,
                'rsi_oversold': config.RSI_OVERSOLD,
                'rsi_overbought': config.RSI_OVERBOUGHT
            }
            
        # Load historical data
        df = self.load_data()
        if df is None or df.empty:
            logger.error("No data available for backtesting")
            return None
            
        # Apply strategy indicators
        df = add_combined_strategy(
            df,
            ema_fast=strategy_params['ema_fast'],
            ema_slow=strategy_params['ema_slow'],
            rsi_period=strategy_params['rsi_period'],
            rsi_oversold=strategy_params['rsi_oversold'],
            rsi_overbought=strategy_params['rsi_overbought']
        )
        
        # Initialize columns for backtesting
        df['position'] = 0
        df['entry_price'] = np.nan
        df['exit_price'] = np.nan
        df['trade_result'] = np.nan
        
        # Run backtest simulation
        position = 0
        entry_price = 0
        
        for i in range(1, len(df)):
            # Current signal
            signal = df.iloc[i]['signal']
            
            # Update position
            if position == 0 and signal == 1:  # Enter long position
                position = 1
                entry_price = df.iloc[i]['close']
                df.iloc[i, df.columns.get_loc('position')] = position
                df.iloc[i, df.columns.get_loc('entry_price')] = entry_price
                
            elif position == 1 and signal == -1:  # Exit long position
                exit_price = df.iloc[i]['close']
                trade_result = (exit_price - entry_price) / entry_price * 100  # Percent return
                
                df.iloc[i, df.columns.get_loc('position')] = 0
                df.iloc[i, df.columns.get_loc('exit_price')] = exit_price
                df.iloc[i, df.columns.get_loc('trade_result')] = trade_result
                
                position = 0
                entry_price = 0
            else:
                df.iloc[i, df.columns.get_loc('position')] = position
        
        # Calculate performance metrics
        trades = df[df['trade_result'].notna()]
        
        results = {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'start_date': df.index[0].strftime('%Y-%m-%d'),
            'end_date': df.index[-1].strftime('%Y-%m-%d'),
            'total_trades': len(trades),
            'winning_trades': len(trades[trades['trade_result'] > 0]),
            'losing_trades': len(trades[trades['trade_result'] < 0]),
            'win_rate': len(trades[trades['trade_result'] > 0]) / len(trades) * 100 if len(trades) > 0 else 0,
            'avg_win': trades[trades['trade_result'] > 0]['trade_result'].mean() if len(trades[trades['trade_result'] > 0]) > 0 else 0,
            'avg_loss': trades[trades['trade_result'] < 0]['trade_result'].mean() if len(trades[trades['trade_result'] < 0]) > 0 else 0,
            'profit_loss': trades['trade_result'].sum(),
            'max_drawdown': self._calculate_max_drawdown(trades['trade_result']),
            'sharpe_ratio': self._calculate_sharpe_ratio(trades['trade_result']),
            'data': df
        }
        
        self.results = results
        logger.info(f"Backtest completed: {results['total_trades']} trades, Win rate: {results['win_rate']:.2f}%, P&L: {results['profit_loss']:.2f}%")
        
        return results
    
    def _calculate_max_drawdown(self, returns):
        """Calculate maximum drawdown from a series of returns"""
        if len(returns) == 0:
            return 0
            
        # Convert returns to equity curve (cumulative returns)
        cumulative = (1 + returns / 100).cumprod()
        
        # Calculate drawdown series
        max_equity = cumulative.cummax()
        drawdown = (cumulative / max_equity - 1) * 100
        
        return drawdown.min()
    
    def _calculate_sharpe_ratio(self, returns, risk_free_rate=0.0, periods_per_year=365):
        """Calculate annualized Sharpe ratio"""
        if len(returns) < 2:
            return 0
            
        # Convert percentage returns to decimals
        returns_decimal = returns / 100
        
        excess_returns = returns_decimal - risk_free_rate / periods_per_year
        annualized_return = excess_returns.mean() * periods_per_year
        annualized_volatility = returns_decimal.std() * np.sqrt(periods_per_year)
        
        if annualized_volatility == 0:
            return 0
            
        return annualized_return / annualized_volatility
    
    def plot_results(self, save_path=None):
        """Plot backtest results"""
        if self.results is None:
            logger.error("No backtest results available to plot")
            return
            
        df = self.results['data']
        
        # Create a figure with 3 subplots
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        fig.suptitle(f'Backtest Results: {self.symbol} ({self.timeframe})', fontsize=16)
        
        # Price and EMAs
        axes[0].plot(df.index, df['close'], label='Close Price', alpha=0.7)
        axes[0].plot(df.index, df[f'ema_{config.EMA_FAST}'], label=f'EMA {config.EMA_FAST}', alpha=0.7)
        axes[0].plot(df.index, df[f'ema_{config.EMA_SLOW}'], label=f'EMA {config.EMA_SLOW}', alpha=0.7)
        
        # Plot buy/sell points
        buy_signals = df[(df['signal'] == 1) & (df['position'].shift(1) == 0)]
        sell_signals = df[(df['signal'] == -1) & (df['position'].shift(1) == 1)]
        
        axes[0].scatter(buy_signals.index, buy_signals['close'], marker='^', color='green', s=100, label='Buy Signal')
        axes[0].scatter(sell_signals.index, sell_signals['close'], marker='v', color='red', s=100, label='Sell Signal')
        
        axes[0].set_ylabel('Price')
        axes[0].legend()
        axes[0].grid(True)
        
        # RSI
        axes[1].plot(df.index, df[f'rsi_{config.RSI_PERIOD}'], label=f'RSI {config.RSI_PERIOD}', color='purple')
        axes[1].axhline(y=config.RSI_OVERSOLD, color='green', linestyle='--', alpha=0.5, label=f'Oversold ({config.RSI_OVERSOLD})')
        axes[1].axhline(y=config.RSI_OVERBOUGHT, color='red', linestyle='--', alpha=0.5, label=f'Overbought ({config.RSI_OVERBOUGHT})')
        axes[1].set_ylabel('RSI')
        axes[1].set_ylim(0, 100)
        axes[1].legend()
        axes[1].grid(True)
        
        # Equity curve
        trades = df[df['trade_result'].notna()].copy()
        
        if not trades.empty:
            trades['cumulative_return'] = trades['trade_result'].cumsum()
            axes[2].plot(trades.index, trades['cumulative_return'], label='Cumulative P&L %', color='blue')
            axes[2].set_ylabel('Cumulative P&L %')
            axes[2].set_xlabel('Date')
            axes[2].legend()
            axes[2].grid(True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()
            
        plt.close(fig)
        
    def optimize_strategy(self, param_grid):
        """
        Optimize strategy parameters using grid search
        
        :param param_grid: Dict of parameters to optimize with lists of values to try
        :return: Best parameters and results
        """
        logger.info("Starting strategy optimization...")
        
        best_profit = -float('inf')
        best_params = None
        best_results = None
        results_list = []
        
        # Generate all parameter combinations
        import itertools
        param_keys = param_grid.keys()
        param_values = param_grid.values()
        param_combinations = list(itertools.product(*param_values))
        
        total_combinations = len(param_combinations)
        logger.info(f"Testing {total_combinations} parameter combinations")
        
        for i, combination in enumerate(param_combinations):
            params = dict(zip(param_keys, combination))
            logger.info(f"Testing combination {i+1}/{total_combinations}: {params}")
            
            results = self.run_backtest(params)
            
            if results is None:
                continue
                
            profit = results['profit_loss']
            
            # Record this result
            params_with_results = params.copy()
            params_with_results.update({
                'profit_loss': results['profit_loss'],
                'win_rate': results['win_rate'],
                'total_trades': results['total_trades']
            })
            results_list.append(params_with_results)
            
            # Check if this is better than our current best
            if profit > best_profit and results['total_trades'] >= 5:  # Minimum number of trades
                best_profit = profit
                best_params = params
                best_results = results
                
        # Convert results to DataFrame for easy analysis
        results_df = pd.DataFrame(results_list)
        
        if best_params:
            logger.info(f"Best parameters found: {best_params}")
            logger.info(f"Profit/Loss: {best_profit:.2f}%, Win Rate: {best_results['win_rate']:.2f}%, Trades: {best_results['total_trades']}")
        else:
            logger.warning("No suitable parameter combination found")
            
        return best_params, best_results, results_df 