import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from app.indicators.technical_indicators import TechnicalIndicators
from app.utils.logger import get_logger

logger = get_logger()

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies
    
    All trading strategies should inherit from this class
    and implement the required methods.
    """
    
    def __init__(self, symbol, timeframes):
        """
        Initialize the base strategy
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            timeframes (list): List of timeframes to analyze (e.g., ['1m', '5m', '15m'])
        """
        self.symbol = symbol
        self.timeframes = timeframes
        self.indicators = TechnicalIndicators()
        self.data = {}  # Data for each timeframe
        
    def prepare_data(self, data_dict):
        """
        Prepare data for the strategy by adding necessary indicators
        
        Args:
            data_dict (dict): Dictionary of DataFrames by timeframe
            
        Returns:
            dict: Dictionary of prepared DataFrames by timeframe
        """
        self.data = {}
        
        for timeframe, df in data_dict.items():
            if timeframe in self.timeframes:
                # Add all indicators needed for this strategy
                prepared_df = self.indicators.add_all_indicators(df.copy())
                self.data[timeframe] = prepared_df
                
        return self.data
    
    @abstractmethod
    def generate_signal(self):
        """
        Generate a trading signal based on the current data
        
        Returns:
            dict: Signal data with action, direction, reasoning, etc.
        """
        pass
    
    @abstractmethod
    def should_enter_trade(self):
        """
        Determine if a new trade should be entered
        
        Returns:
            tuple: (should_enter, signal_data)
        """
        pass
        
    @abstractmethod
    def should_exit_trade(self, position_data):
        """
        Determine if an existing trade should be exited
        
        Args:
            position_data (dict): Current position data
            
        Returns:
            tuple: (should_exit, exit_reason)
        """
        pass
    
    def get_stop_loss_price(self, entry_price, direction, atr_value=None):
        """
        Calculate stop loss price based on ATR or fixed percentage
        
        Args:
            entry_price (float): Entry price
            direction (str): 'long' or 'short'
            atr_value (float, optional): ATR value for dynamic stop loss
            
        Returns:
            float: Stop loss price
        """
        if atr_value:
            # Use ATR for dynamic stop loss
            stop_distance = atr_value * 2  # 2x ATR
        else:
            # Use fixed percentage (2%)
            stop_distance = entry_price * 0.02
            
        if direction == 'long':
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance
            
    def get_take_profit_price(self, entry_price, direction, risk_reward_ratio=2):
        """
        Calculate take profit price based on risk-reward ratio
        
        Args:
            entry_price (float): Entry price
            direction (str): 'long' or 'short'
            risk_reward_ratio (float): Risk-reward ratio (default: 2)
            
        Returns:
            float: Take profit price
        """
        # Calculate stop loss price
        stop_loss = self.get_stop_loss_price(entry_price, direction)
        
        # Calculate take profit based on risk-reward ratio
        if direction == 'long':
            stop_distance = entry_price - stop_loss
            return entry_price + (stop_distance * risk_reward_ratio)
        else:
            stop_distance = stop_loss - entry_price
            return entry_price - (stop_distance * risk_reward_ratio)
    
    def get_signal_reasoning(self, signal_data):
        """
        Generate human-readable reasoning for a signal
        
        Args:
            signal_data (dict): Signal data
            
        Returns:
            str: Human-readable reasoning
        """
        direction = signal_data.get('direction', 'unknown')
        timeframe = signal_data.get('timeframe', 'multiple timeframes')
        indicators = signal_data.get('indicators', {})
        
        reasoning = f"{direction.capitalize()} signal detected on {timeframe} timeframe.\n"
        
        # Add indicator-specific reasoning
        if 'rsi' in indicators:
            rsi_value = indicators['rsi']
            if direction == 'long':
                reasoning += f"RSI ({rsi_value:.2f}) shows oversold conditions.\n"
            else:
                reasoning += f"RSI ({rsi_value:.2f}) shows overbought conditions.\n"
                
        if 'macd' in indicators:
            if direction == 'long':
                reasoning += "MACD crossed above signal line.\n"
            else:
                reasoning += "MACD crossed below signal line.\n"
                
        # Add price action reasoning
        if 'price_action' in signal_data:
            reasoning += signal_data['price_action'] + "\n"
            
        # Add trend reasoning
        if 'trend' in signal_data:
            reasoning += f"Overall trend: {signal_data['trend']}.\n"
            
        return reasoning 