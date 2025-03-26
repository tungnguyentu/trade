import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

from app.utils.data_handler import DataHandler
from app.strategies.strategy_selector import StrategySelector
from app.indicators.technical_indicators import TechnicalIndicators
from app.risk_management.risk_manager import RiskManager
from app.utils.logger import get_logger
from app.config.config import BACKTEST_START_DATE, BACKTEST_END_DATE, TRADING_SYMBOLS, TIMEFRAMES

logger = get_logger()

class BacktestEngine:
    def __init__(self, symbol, start_date=BACKTEST_START_DATE, end_date=BACKTEST_END_DATE, 
                 timeframes=TIMEFRAMES, initial_balance=10000):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.timeframes = timeframes
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        
        self.data_handler = DataHandler()
        self.strategy_selector = StrategySelector(symbol, timeframes)
        self.risk_manager = RiskManager()
        
        # Trading state
        self.open_position = None
        self.trades = []
        self.trade_history = []
        self.equity_curve = []
        
        logger.info(f"Initialized backtesting for {symbol} from {start_date} to {end_date}")
        
    def load_data(self):
        """Load historical data for backtesting"""
        data_dict = {}
        for timeframe in self.timeframes:
            df = self.data_handler.fetch_ohlcv_data(
                symbol=self.symbol,
                interval=timeframe,
                start_time=self.start_date,
                end_time=self.end_date,
                limit=5000  # Adjust as needed
            )
            
            if not df.empty:
                data_dict[timeframe] = df
                
        return data_dict
    
    def run_backtest(self):
        """Run backtesting simulation"""
        logger.info(f"Starting backtest for {self.symbol}")
        
        # Load data for all timeframes
        data_dict = self.load_data()
        if not data_dict:
            logger.error(f"Failed to load data for backtesting {self.symbol}")
            return None
        
        # Primary timeframe for iteration (use the smallest for more precision)
        primary_tf = min(self.timeframes, key=lambda x: self._get_timeframe_minutes(x))
        if primary_tf not in data_dict:
            primary_tf = next(iter(data_dict))
            
        df_primary = data_dict[primary_tf]
        logger.info(f"Using {primary_tf} as primary timeframe with {len(df_primary)} candles")
        
        # Prepare data with indicators for all timeframes
        prepared_data = self.strategy_selector.prepare_strategies(data_dict)
        
        # Initialize simulation variables
        self.current_balance = self.initial_balance
        self.equity_curve = [{"timestamp": df_primary.index[0], "balance": self.initial_balance}]
        
        # Iterate through each candle in the primary timeframe
        for i in range(100, len(df_primary)):
            try:
                # Current timestamp
                current_time = df_primary.index[i]
                
                # Create current data views for all timeframes
                current_data = self._get_current_data(data_dict, current_time, i)
                
                # Check if we have an open position
                if self.open_position:
                    # Check for exit signals
                    self._check_exit_signals(current_data, current_time)
                else:
                    # Check for entry signals
                    self._check_entry_signals(current_data, current_time)
                
                # Record equity curve
                self.equity_curve.append({
                    "timestamp": current_time,
                    "balance": self.current_balance + self._calculate_unrealized_pnl(current_data, current_time)
                })
                
            except Exception as e:
                logger.error(f"Error at timestamp {current_time}: {e}")
                continue
                
        # Close any remaining open position at the end of the backtest
        if self.open_position:
            self._close_position(df_primary.iloc[-1]['close'], "End of backtest", df_primary.index[-1])
            
        # Calculate and log backtest results
        results = self._calculate_results()
        self._log_results(results)
        
        return results
    
    def _get_timeframe_minutes(self, timeframe):
        """Convert timeframe to minutes for comparison"""
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        
        if unit == 'm':
            return value
        elif unit == 'h':
            return value * 60
        elif unit == 'd':
            return value * 1440
        else:
            return 0
            
    def _get_current_data(self, data_dict, current_time, current_index):
        """Get current data view for each timeframe"""
        current_data = {}
        
        for timeframe, df in data_dict.items():
            # Find the most recent candle for each timeframe at current_time
            df_current = df[df.index <= current_time]
            if not df_current.empty:
                current_data[timeframe] = df_current
                
        return current_data
    
    def _check_entry_signals(self, current_data, current_time):
        """Check for entry signals across strategies"""
        # Update strategy data with current view
        self.strategy_selector.prepare_strategies(current_data)
        
        # Check if we should enter a trade
        should_enter, signal_data, strategy_name = self.strategy_selector.should_enter_trade()
        
        if should_enter and signal_data:
            # Calculate entry parameters
            entry_price = signal_data['price']
            is_long = signal_data['type'] == 'long'
            
            # Get strategy for proper stop loss and take profit calculation
            best_strategy, _ = self.strategy_selector.get_best_strategy()
            
            # Calculate stop loss and take profit prices
            stop_loss = best_strategy.calculate_stop_loss(entry_price, is_long)
            take_profit = best_strategy.calculate_take_profit(entry_price, is_long)
            
            # Calculate position size based on risk management
            risk_per_trade = 0.01  # 1% risk per trade
            risk_amount = self.current_balance * risk_per_trade
            price_diff_pct = abs(entry_price - stop_loss) / entry_price
            
            if price_diff_pct == 0:
                # Avoid division by zero
                position_size_quote = 100  # Default size
            else:
                position_size_quote = risk_amount / price_diff_pct
                
            # Limit to available balance
            position_size_quote = min(position_size_quote, self.current_balance * 0.95)
            
            # Convert to base currency quantity
            quantity = position_size_quote / entry_price
            
            # Open the position
            self._open_position(
                entry_price=entry_price,
                quantity=quantity,
                is_long=is_long,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy=strategy_name,
                timestamp=current_time,
                signal_data=signal_data
            )
    
    def _check_exit_signals(self, current_data, current_time):
        """Check for exit signals on current position"""
        if not self.open_position:
            return
            
        # Get current price from primary timeframe
        primary_tf = min(self.timeframes, key=lambda x: self._get_timeframe_minutes(x))
        if primary_tf not in current_data:
            return
            
        current_price = current_data[primary_tf].iloc[-1]['close']
        
        # Update strategy data with current view
        self.strategy_selector.prepare_strategies(current_data)
        
        # Get the appropriate strategy for exit signals
        if self.open_position['strategy'] == 'Scalping':
            strategy = self.strategy_selector.scalping_strategy
        else:
            strategy = self.strategy_selector.swing_strategy
            
        if not strategy:
            return
            
        # Check for exit signals from the strategy
        should_exit, exit_reason = strategy.should_exit_trade(
            self.open_position['entry_price'], 
            self.open_position
        )
        
        if should_exit:
            self._close_position(current_price, exit_reason, current_time)
            return
            
        # Check for stop loss / take profit
        is_long = self.open_position['type'] == 'long'
        
        # Check stop loss
        if (is_long and current_price <= self.open_position['stop_loss']) or \
           (not is_long and current_price >= self.open_position['stop_loss']):
            self._close_position(current_price, "Stop loss triggered", current_time)
            return
            
        # Check take profit
        if (is_long and current_price >= self.open_position['take_profit']) or \
           (not is_long and current_price <= self.open_position['take_profit']):
            self._close_position(current_price, "Take profit reached", current_time)
            return
    
    def _open_position(self, entry_price, quantity, is_long, stop_loss, take_profit, strategy, timestamp, signal_data):
        """Open a new position"""
        position_type = 'long' if is_long else 'short'
        
        # Create position record
        self.open_position = {
            'symbol': self.symbol,
            'type': position_type,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'strategy': strategy,
            'entry_time': timestamp,
            'exit_time': None,
            'exit_price': None,
            'exit_reason': None,
            'pnl': 0.0,
            'pnl_percent': 0.0
        }
        
        logger.info(f"Opened {position_type} position for {self.symbol} at {entry_price} | SL: {stop_loss} | TP: {take_profit}")
    
    def _close_position(self, exit_price, exit_reason, timestamp):
        """Close the current position"""
        if not self.open_position:
            return
            
        # Update position data
        self.open_position['exit_price'] = exit_price
        self.open_position['exit_time'] = timestamp
        self.open_position['exit_reason'] = exit_reason
        
        # Calculate P&L
        entry_price = self.open_position['entry_price']
        quantity = self.open_position['quantity']
        is_long = self.open_position['type'] == 'long'
        
        if is_long:
            pnl_usdt = (exit_price - entry_price) * quantity
            pnl_pct = (exit_price - entry_price) / entry_price
        else:
            pnl_usdt = (entry_price - exit_price) * quantity
            pnl_pct = (entry_price - exit_price) / entry_price
            
        self.open_position['pnl'] = pnl_usdt
        self.open_position['pnl_percent'] = pnl_pct
        
        # Calculate trade duration
        if isinstance(timestamp, datetime) and isinstance(self.open_position['entry_time'], datetime):
            duration_seconds = (timestamp - self.open_position['entry_time']).total_seconds()
            hours, remainder = divmod(duration_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            self.open_position['duration'] = duration_str
        
        # Update balance
        self.current_balance += pnl_usdt
        if self.current_balance <= 0:
            logger.warning("Account blown! Backtest stopped.")
            return
            
        # Add to trade history
        self.trade_history.append(self.open_position.copy())
        
        logger.info(f"Closed position for {self.symbol} at {exit_price} | PnL: {pnl_usdt:.2f} USDT ({pnl_pct:.2%}) | Reason: {exit_reason}")
        
        # Reset open position
        self.open_position = None
    
    def _calculate_unrealized_pnl(self, current_data, current_time):
        """Calculate unrealized PnL for open position"""
        if not self.open_position:
            return 0.0
            
        # Get current price from primary timeframe
        primary_tf = min(self.timeframes, key=lambda x: self._get_timeframe_minutes(x))
        if primary_tf not in current_data:
            return 0.0
            
        current_price = current_data[primary_tf].iloc[-1]['close']
        
        # Calculate unrealized PnL
        entry_price = self.open_position['entry_price']
        quantity = self.open_position['quantity']
        is_long = self.open_position['type'] == 'long'
        
        if is_long:
            unrealized_pnl = (current_price - entry_price) * quantity
        else:
            unrealized_pnl = (entry_price - current_price) * quantity
            
        return unrealized_pnl
    
    def _calculate_results(self):
        """Calculate backtest results"""
        if not self.trade_history:
            return {
                'symbol': self.symbol,
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_profit': 0,
                'total_profit_pct': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'equity_curve': self.equity_curve
            }
            
        # Extract trade data
        profits = [trade['pnl'] for trade in self.trade_history if trade['pnl'] > 0]
        losses = [trade['pnl'] for trade in self.trade_history if trade['pnl'] < 0]
        
        # Calculate metrics
        total_trades = len(self.trade_history)
        win_count = len(profits)
        loss_count = len(losses)
        
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        total_profit = sum(profits) if profits else 0
        total_loss = abs(sum(losses)) if losses else 0
        
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Calculate drawdown
        balance_history = [point['balance'] for point in self.equity_curve]
        max_drawdown = self._calculate_max_drawdown(balance_history)
        
        # Calculate Sharpe ratio (simplified)
        returns = [(t['pnl'] / (t['entry_price'] * t['quantity'])) for t in self.trade_history]
        sharpe_ratio = np.mean(returns) / np.std(returns) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        return {
            'symbol': self.symbol,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_balance': self.initial_balance,
            'final_balance': self.current_balance,
            'total_profit': self.current_balance - self.initial_balance,
            'total_profit_pct': (self.current_balance / self.initial_balance - 1) * 100,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'trades': self.trade_history,
            'equity_curve': self.equity_curve
        }
    
    def _calculate_max_drawdown(self, balance_history):
        """Calculate maximum drawdown from equity curve"""
        if not balance_history:
            return 0
            
        max_dd = 0
        peak = balance_history[0]
        
        for balance in balance_history:
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
            
        return max_dd
    
    def _log_results(self, results):
        """Log backtest results"""
        logger.info(f"===== Backtest Results for {self.symbol} =====")
        logger.info(f"Period: {self.start_date} to {self.end_date}")
        logger.info(f"Initial Balance: {self.initial_balance:.2f} USDT")
        logger.info(f"Final Balance: {self.current_balance:.2f} USDT")
        logger.info(f"Total Profit: {results['total_profit']:.2f} USDT ({results['total_profit_pct']:.2f}%)")
        logger.info(f"Total Trades: {results['total_trades']}")
        logger.info(f"Win Rate: {results['win_rate']:.2%}")
        logger.info(f"Profit Factor: {results['profit_factor']:.2f}")
        logger.info(f"Maximum Drawdown: {results['max_drawdown']:.2%}")
        logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        logger.info("========================================")
    
    def plot_results(self, save_path=None):
        """Plot backtest results"""
        if not self.equity_curve:
            logger.warning("No equity curve data to plot")
            return
            
        # Create figure and subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot equity curve
        timestamps = [point['timestamp'] for point in self.equity_curve]
        balances = [point['balance'] for point in self.equity_curve]
        
        ax1.plot(timestamps, balances, label='Equity Curve')
        ax1.set_title(f'Backtest Results for {self.symbol}')
        ax1.set_ylabel('Balance (USDT)')
        ax1.grid(True)
        ax1.legend()
        
        # Plot trade markers
        for trade in self.trade_history:
            if trade['pnl'] > 0:
                marker = '^'
                color = 'green'
            else:
                marker = 'v'
                color = 'red'
                
            ax1.scatter(trade['exit_time'], trade['exit_price'], marker=marker, color=color, s=50)
            
        # Plot drawdown
        max_equity = np.maximum.accumulate(balances)
        drawdowns = [1 - balance/max_equity[i] for i, balance in enumerate(balances)]
        
        ax2.fill_between(timestamps, drawdowns, 0, color='red', alpha=0.3)
        ax2.set_title('Drawdown')
        ax2.set_ylabel('Drawdown (%)')
        ax2.set_xlabel('Date')
        ax2.grid(True)
        
        plt.tight_layout()
        
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            plt.savefig(save_path)
            logger.info(f"Saved backtest plot to {save_path}")
        else:
            plt.show()
            
        plt.close() 