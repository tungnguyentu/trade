from datetime import datetime
from app.utils.logger import get_logger
from app.config.config import (
    RISK_PER_TRADE,
    MAX_POSITION_SIZE,
    MIN_POSITION_SIZE,
    MAX_DAILY_LOSS,
    MAX_DAILY_TRADES
)

logger = get_logger()

class RiskManager:
    def __init__(self):
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.trade_history = []
        self.last_reset = datetime.now()
        
    def calculate_position_size(self, symbol, entry_price, stop_loss_price, risk_per_trade=None):
        """
        Calculate position size based on risk management rules
        
        Args:
            symbol (str): Trading pair symbol
            entry_price (float): Entry price
            stop_loss_price (float): Stop loss price
            risk_per_trade (float, optional): Risk per trade in percentage
            
        Returns:
            float: Position size in base currency
        """
        # Reset daily counters if needed
        self._reset_daily_counters()
        
        # Check if we've hit daily limits
        if self.daily_trades >= MAX_DAILY_TRADES:
            logger.warning("Daily trade limit reached")
            return 0
            
        if self.daily_pnl <= -MAX_DAILY_LOSS:
            logger.warning("Daily loss limit reached")
            return 0
            
        # Use provided risk per trade or default from config
        risk = risk_per_trade if risk_per_trade is not None else RISK_PER_TRADE
        
        # Calculate position size based on risk
        risk_amount = self._get_account_balance() * risk
        price_risk = abs(entry_price - stop_loss_price)
        
        if price_risk == 0:
            logger.warning("Invalid stop loss price - no risk")
            return 0
            
        position_size = risk_amount / price_risk
        
        # Apply position size limits
        position_size = min(position_size, MAX_POSITION_SIZE)
        position_size = max(position_size, MIN_POSITION_SIZE)
        
        # Round to appropriate precision
        position_size = round(position_size, 3)
        
        return position_size
        
    def update_trade_history(self, symbol, entry_price, exit_price, quantity, pnl, pnl_percent, duration, strategy):
        """
        Update trade history and daily statistics
        
        Args:
            symbol (str): Trading pair symbol
            entry_price (float): Entry price
            exit_price (float): Exit price
            quantity (float): Position size
            pnl (float): Profit/Loss in quote currency
            pnl_percent (float): Profit/Loss percentage
            duration (datetime.timedelta): Trade duration
            strategy (str): Strategy name
        """
        # Reset daily counters if needed
        self._reset_daily_counters()
        
        # Update trade history
        trade = {
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "duration": duration,
            "strategy": strategy,
            "timestamp": datetime.now()
        }
        self.trade_history.append(trade)
        
        # Update daily statistics
        self.daily_trades += 1
        self.daily_pnl += pnl
        
        # Log trade result
        logger.info(f"Trade completed: {symbol} | PnL: {pnl:.2f} ({pnl_percent:.2%}) | Duration: {duration}")
        
    def _reset_daily_counters(self):
        """Reset daily counters if it's a new day"""
        current_time = datetime.now()
        if current_time.date() != self.last_reset.date():
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_reset = current_time
            
    def _get_account_balance(self):
        """
        Get current account balance
        
        Returns:
            float: Account balance in quote currency
        """
        # TODO: Implement actual balance fetching from Binance
        # For now, return a default balance for testing
        return 10000.0  # Default balance for testing 