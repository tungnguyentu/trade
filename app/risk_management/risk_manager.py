import pandas as pd
import numpy as np
from app.config.config import RISK_PER_TRADE, MAX_DRAWDOWN, BASE_ORDER_SIZE
from app.utils.binance_client import BinanceClient
from app.utils.logger import get_logger

logger = get_logger()

class RiskManager:
    def __init__(self):
        self.binance_client = BinanceClient()
        self.risk_per_trade = RISK_PER_TRADE
        self.max_drawdown = MAX_DRAWDOWN
        self.base_order_size = BASE_ORDER_SIZE
        self.open_trades = {}
        self.trade_history = []
        self.initial_balance = self._get_account_balance()
        self.current_balance = self.initial_balance
        self.peak_balance = self.initial_balance
    
    def _get_account_balance(self):
        """Get current account balance"""
        balance = self.binance_client.get_account_balance()
        return balance['free']
    
    def calculate_position_size(self, symbol, entry_price, stop_loss_price):
        """
        Calculate position size based on risk per trade
        
        Args:
            symbol (str): Trading pair symbol
            entry_price (float): Entry price
            stop_loss_price (float): Stop-loss price
            
        Returns:
            float: Position size in base currency
        """
        try:
            # Update current balance
            self.current_balance = self._get_account_balance()
            
            # Calculate risk amount in USDT
            risk_amount = self.current_balance * self.risk_per_trade
            
            # Calculate price difference percentage
            price_diff_pct = abs(entry_price - stop_loss_price) / entry_price
            
            if price_diff_pct == 0:
                logger.warning("Stop loss is identical to entry price, using default position size")
                return self.base_order_size / entry_price
            
            # Calculate position size in quote currency (USDT)
            position_size_quote = risk_amount / price_diff_pct
            
            # Limit position size to configured base order size
            position_size_quote = min(position_size_quote, self.base_order_size)
            
            # Convert to base currency (e.g., BTC)
            position_size_base = position_size_quote / entry_price
            
            # Get symbol information to apply quantity precision
            symbol_info = self.binance_client.get_symbol_info(symbol)
            if symbol_info:
                # Find the LOT_SIZE filter
                lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
                if lot_size_filter:
                    step_size = float(lot_size_filter['stepSize'])
                    # Round to step size precision
                    position_size_base = self._round_step_size(position_size_base, step_size)
            
            logger.info(f"Calculated position size for {symbol}: {position_size_base}")
            return position_size_base
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            # Return a safe default value if there's an error
            return self.base_order_size / entry_price
    
    def _round_step_size(self, quantity, step_size):
        """Round quantity to step size precision"""
        precision = 0
        if '.' in str(step_size):
            precision = len(str(step_size).split('.')[1])
        return np.floor(quantity / step_size) * step_size
    
    def update_trade_history(self, trade):
        """Update trade history with new completed trade"""
        self.trade_history.append(trade)
        
        # Update current balance based on PnL
        self.current_balance += trade['pnl']
        
        # Update peak balance if current balance is higher
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
    
    def calculate_metrics(self):
        """Calculate risk metrics based on trade history"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'average_win': 0,
                'average_loss': 0,
                'max_drawdown_pct': 0,
                'sharpe_ratio': 0
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
        
        average_win = total_profit / win_count if win_count > 0 else 0
        average_loss = total_loss / loss_count if loss_count > 0 else 0
        
        # Calculate max drawdown
        max_drawdown_pct = 0
        if self.peak_balance > 0:
            max_drawdown_pct = (self.peak_balance - self.current_balance) / self.peak_balance
        
        # Calculate Sharpe Ratio (simplified)
        if len(self.trade_history) > 1:
            returns = [trade['pnl'] / trade['investment'] for trade in self.trade_history]
            sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'average_win': average_win,
            'average_loss': average_loss,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio
        }
    
    def should_continue_trading(self):
        """Check if trading should continue based on drawdown limits"""
        if not self.initial_balance or self.initial_balance == 0:
            return True
            
        current_drawdown = (self.peak_balance - self.current_balance) / self.peak_balance if self.peak_balance > 0 else 0
        
        if current_drawdown >= self.max_drawdown:
            logger.warning(f"Max drawdown limit reached: {current_drawdown:.2%} > {self.max_drawdown:.2%}")
            return False
            
        return True 