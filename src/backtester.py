import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from datetime import datetime
from config.config import SYMBOL, QUANTITY, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT
from src.data_processor import DataProcessor

logger = logging.getLogger("backtester")

class Backtester:
    def __init__(self, strategy, initial_balance=1000.0, commission=0.0004):
        """
        Initialize the backtester
        
        Args:
            strategy: Trading strategy to backtest
            initial_balance: Initial account balance in USDT
            commission: Commission rate per trade (0.04% for Binance futures)
        """
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission = commission
        self.positions = []
        self.trades = []
        self.equity_curve = []
        self.data_processor = DataProcessor()
        
        logger.info(f"Backtester initialized with {strategy.__class__.__name__} strategy")
        logger.info(f"Initial balance: {initial_balance} USDT, Commission: {commission*100}%")
        
    def load_historical_data(self, file_path=None, klines=None, interval='1h'):
        """
        Load historical data from file or klines
        
        Args:
            file_path: Path to CSV file with historical data
            klines: Klines data from Binance API
            interval: Timeframe interval
        
        Returns:
            DataFrame with processed data
        """
        if file_path:
            logger.info(f"Loading historical data from {file_path}")
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        elif klines:
            logger.info(f"Processing {len(klines)} klines for {SYMBOL} at {interval} interval")
            df = self.data_processor.klines_to_dataframe(klines)
        else:
            logger.error("No data source provided")
            return None
            
        # Add indicators
        df = self.data_processor.add_indicators(df)
        return df
        
    def run(self, df):
        """
        Run backtest on historical data
        
        Args:
            df: DataFrame with historical data and indicators
            
        Returns:
            DataFrame with backtest results
        """
        if df is None or df.empty:
            logger.error("Empty dataframe provided for backtest")
            return None
            
        logger.info(f"Running backtest on {len(df)} candles from {df.index[0]} to {df.index[-1]}")
        
        # Reset backtest state
        self.balance = self.initial_balance
        self.positions = []
        self.trades = []
        self.equity_curve = []
        
        # Add columns for signals and positions
        df['signal'] = 0
        df['position'] = 0
        df['entry_price'] = np.nan
        df['exit_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        df['pnl'] = 0.0
        df['balance'] = self.initial_balance
        
        # Generate signals for each candle
        for i in range(1, len(df)):
            # Get data up to current candle
            current_data = df.iloc[:i+1]
            
            # Generate signal
            signal = self.strategy.generate_signal(current_data)
            df.loc[df.index[i], 'signal'] = signal
            
            # Process signal
            self._process_signal(df, i, signal)
            
            # Update equity curve
            self.equity_curve.append({
                'timestamp': df.index[i],
                'balance': self.balance,
                'open_position': len(self.positions) > 0
            })
            
            # Update balance in dataframe
            df.loc[df.index[i], 'balance'] = self.balance
            
        logger.info(f"Backtest completed. Final balance: {self.balance} USDT")
        return df
    
    def _process_signal(self, df, i, signal):
        """Process trading signal and update positions"""
        current_price = df.iloc[i]['close']
        current_time = df.index[i]
        
        # Check if we have an open position
        if self.positions:
            position = self.positions[0]  # We only support one position at a time
            
            # Check for stop loss or take profit
            if position['direction'] == 'long':
                # Stop loss hit
                if current_price <= position['stop_loss']:
                    self._close_position(df, i, current_price, current_time, 'stop_loss')
                # Take profit hit
                elif current_price >= position['take_profit']:
                    self._close_position(df, i, current_price, current_time, 'take_profit')
                # Close on opposite signal
                elif signal < 0:
                    self._close_position(df, i, current_price, current_time, 'signal')
            else:  # Short position
                # Stop loss hit
                if current_price >= position['stop_loss']:
                    self._close_position(df, i, current_price, current_time, 'stop_loss')
                # Take profit hit
                elif current_price <= position['take_profit']:
                    self._close_position(df, i, current_price, current_time, 'take_profit')
                # Close on opposite signal
                elif signal > 0:
                    self._close_position(df, i, current_price, current_time, 'signal')
        
        # Open new position if we don't have one and signal is not zero
        if not self.positions and signal != 0:
            self._open_position(df, i, signal, current_price, current_time)
    
    def _open_position(self, df, i, signal, price, timestamp):
        """Open a new position"""
        direction = 'long' if signal > 0 else 'short'
        
        # Calculate position size based on fixed quantity
        position_size = QUANTITY
        position_value = position_size * price
        
        # Calculate stop loss and take profit levels
        if direction == 'long':
            stop_loss = price * (1 - STOP_LOSS_PERCENT/100)
            take_profit = price * (1 + TAKE_PROFIT_PERCENT/100)
        else:
            stop_loss = price * (1 + STOP_LOSS_PERCENT/100)
            take_profit = price * (1 - TAKE_PROFIT_PERCENT/100)
        
        # Create position
        position = {
            'direction': direction,
            'size': position_size,
            'entry_price': price,
            'entry_time': timestamp,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
        
        self.positions.append(position)
        
        # Update dataframe
        df.loc[df.index[i], 'position'] = 1 if direction == 'long' else -1
        df.loc[df.index[i], 'entry_price'] = price
        df.loc[df.index[i], 'stop_loss'] = stop_loss
        df.loc[df.index[i], 'take_profit'] = take_profit
        
        logger.info(f"Opened {direction} position at {price} with SL: {stop_loss}, TP: {take_profit}")
    
    def _close_position(self, df, i, price, timestamp, reason):
        """Close an existing position"""
        if not self.positions:
            return
            
        position = self.positions[0]
        
        # Calculate PnL
        if position['direction'] == 'long':
            pnl_percent = (price / position['entry_price'] - 1) * 100
            pnl = position['size'] * (price - position['entry_price'])
        else:
            pnl_percent = (1 - price / position['entry_price']) * 100
            pnl = position['size'] * (position['entry_price'] - price)
        
        # Subtract commission
        commission = position['size'] * price * self.commission * 2  # Entry and exit
        pnl -= commission
        
        # Update balance
        self.balance += pnl
        
        # Record trade
        trade = {
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'direction': position['direction'],
            'entry_price': position['entry_price'],
            'exit_price': price,
            'size': position['size'],
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'reason': reason
        }
        
        self.trades.append(trade)
        
        # Update dataframe
        df.loc[df.index[i], 'position'] = 0
        df.loc[df.index[i], 'exit_price'] = price
        df.loc[df.index[i], 'pnl'] = pnl
        
        logger.info(f"Closed {position['direction']} position at {price}. PnL: {pnl:.2f} USDT ({pnl_percent:.2f}%). Reason: {reason}")
        
        # Clear positions
        self.positions = []
    
    def get_performance_metrics(self):
        """Calculate performance metrics from backtest results"""
        if not self.trades:
            logger.warning("No trades to calculate performance metrics")
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_return': 0,
                'max_drawdown': 0
            }
        
        # Calculate basic metrics
        total_trades = len(self.trades)
        winning_trades = sum(1 for trade in self.trades if trade['pnl'] > 0)
        losing_trades = sum(1 for trade in self.trades if trade['pnl'] <= 0)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(trade['pnl'] for trade in self.trades if trade['pnl'] > 0)
        gross_loss = abs(sum(trade['pnl'] for trade in self.trades if trade['pnl'] <= 0))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        total_return = (self.balance - self.initial_balance) / self.initial_balance * 100
        
        # Calculate drawdown
        equity_curve = pd.DataFrame(self.equity_curve)
        if not equity_curve.empty:
            equity_curve['peak'] = equity_curve['balance'].cummax()
            equity_curve['drawdown'] = (equity_curve['balance'] - equity_curve['peak']) / equity_curve['peak'] * 100
            max_drawdown = abs(equity_curve['drawdown'].min())
        else:
            max_drawdown = 0
        
        # Calculate average trade metrics
        avg_profit = sum(trade['pnl'] for trade in self.trades) / total_trades if total_trades > 0 else 0
        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0
        
        # Calculate expectancy
        expectancy = (win_rate * avg_win - (1 - win_rate) * avg_loss) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate * 100,  # as percentage
            'profit_factor': profit_factor,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'avg_profit': avg_profit,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'expectancy': expectancy
        }
    
    def plot_results(self, df, save_path=None):
        """Plot backtest results"""
        if df is None or df.empty:
            logger.error("No data to plot")
            return
        
        # Create figure with subplots
        fig = plt.figure(figsize=(15, 10))
        
        # Price chart with buy/sell signals
        ax1 = plt.subplot2grid((4, 1), (0, 0), rowspan=2)
        ax1.plot(df.index, df['close'], label='Price')
        
        # Plot buy signals
        buy_signals = df[df['signal'] > 0]
        ax1.scatter(buy_signals.index, buy_signals['close'], marker='^', color='green', label='Buy Signal')
        
        # Plot sell signals
        sell_signals = df[df['signal'] < 0]
        ax1.scatter(sell_signals.index, sell_signals['close'], marker='v', color='red', label='Sell Signal')
        
        # Plot entry and exit points
        entries = df[df['entry_price'].notna()]
        exits = df[df['exit_price'].notna()]
        
        ax1.scatter(entries.index, entries['entry_price'], marker='o', color='blue', label='Entry')
        ax1.scatter(exits.index, exits['exit_price'], marker='x', color='black', label='Exit')
        
        ax1.set_title(f'Backtest Results for {SYMBOL}')
        ax1.set_ylabel('Price')
        ax1.legend()
        ax1.grid(True)
        
        # Balance chart
        ax2 = plt.subplot2grid((4, 1), (2, 0))
        ax2.plot(df.index, df['balance'], label='Account Balance')
        ax2.set_ylabel('Balance (USDT)')
        ax2.grid(True)
        
        # PnL per trade
        ax3 = plt.subplot2grid((4, 1), (3, 0))
        pnl_data = [trade['pnl'] for trade in self.trades]
        trade_indices = range(len(pnl_data))
        colors = ['green' if pnl > 0 else 'red' for pnl in pnl_data]
        
        if pnl_data:
            ax3.bar(trade_indices, pnl_data, color=colors)
            ax3.set_xlabel('Trade #')
            ax3.set_ylabel('PnL (USDT)')
            ax3.set_title('Profit/Loss per Trade')
            ax3.grid(True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved backtest plot to {save_path}")
        
        return fig
    
    def create_interactive_chart(self, df, save_path=None):
        """Create an interactive chart with plotly"""
        if df is None or df.empty:
            logger.error("No data to plot")
            return
        
        # Create candlestick chart
        fig = go.Figure()
        
        # Add price candlesticks
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ))
        
        # Add buy signals
        buy_signals = df[df['signal'] > 0]
        if not buy_signals.empty:
            fig.add_trace(go.Scatter(
                x=buy_signals.index,
                y=buy_signals['close'],
                mode='markers',
                marker=dict(symbol='triangle-up', size=10, color='green'),
                name='Buy Signal'
            ))
        
        # Add sell signals
        sell_signals = df[df['signal'] < 0]
        if not sell_signals.empty:
            fig.add_trace(go.Scatter(
                x=sell_signals.index,
                y=sell_signals['close'],
                mode='markers',
                marker=dict(symbol='triangle-down', size=10, color='red'),
                name='Sell Signal'
            ))
        
        # Add entries
        entries = df[df['entry_price'].notna()]
        if not entries.empty:
            fig.add_trace(go.Scatter(
                x=entries.index,
                y=entries['entry_price'],
                mode='markers',
                marker=dict(symbol='circle', size=8, color='blue'),
                name='Entry'
            ))
        
        # Add exits
        exits = df[df['exit_price'].notna()]
        if not exits.empty:
            fig.add_trace(go.Scatter(
                x=exits.index,
                y=exits['exit_price'],
                mode='markers',
                marker=dict(symbol='x', size=8, color='black'),
                name='Exit'
            ))
        
        # Update layout
        fig.update_layout(
            title=f'Backtest Results for {SYMBOL}',
            xaxis_title='Date',
            yaxis_title='Price',
            xaxis_rangeslider_visible=False,
            height=600,
            width=1000
        )
        
        if save_path:
            fig.write_html(save_path)
            logger.info(f"Saved interactive chart to {save_path}")
        
        return fig