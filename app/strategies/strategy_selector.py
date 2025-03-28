import pandas as pd
import numpy as np
from app.strategies.scalping_strategy import ScalpingStrategy
from app.strategies.swing_strategy import SwingStrategy
from app.config.config import SCALPING_ENABLED, SWING_TRADING_ENABLED
from app.utils.logger import get_logger

logger = get_logger()

class StrategySelector:
    """
    Class for selecting the best strategy based on market conditions
    """
    
    def __init__(self, symbol, timeframes):
        """
        Initialize strategy selector
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            timeframes (list): List of timeframes to analyze
        """
        self.symbol = symbol
        self.timeframes = timeframes
        
        # Initialize strategies based on config
        self.strategies = {}
        
        # Only initialize enabled strategies
        if SCALPING_ENABLED:
            self.strategies['scalping'] = ScalpingStrategy(symbol, timeframes)
            
        if SWING_TRADING_ENABLED:
            # For now, return a placeholder until SwingStrategy is implemented
            self.strategies['swing'] = None
        
        self.current_market_state = "unknown"
        
    def prepare_strategies(self, data_dict):
        """
        Prepare data for all active strategies
        
        Args:
            data_dict (dict): Dictionary of DataFrames by timeframe
            
        Returns:
            dict: Dictionary of prepared data by strategy
        """
        prepared_data = {}
        
        # Analyze market state first
        self._analyze_market_state(data_dict)
        
        # Prepare data for each active strategy
        for strategy_name, strategy in self.strategies.items():
            if strategy is not None:
                prepared_data[strategy_name] = strategy.prepare_data(data_dict)
                
        return prepared_data
    
    def _analyze_market_state(self, data_dict):
        """
        Analyze market state to determine the best strategy
        
        Looks at volatility (ATR) and directional movement to determine
        if the market is in a state that favors scalping or swing trading.
        
        Args:
            data_dict (dict): Dictionary of DataFrames by timeframe
            
        Returns:
            str: 'scalping', 'swing', or 'mixed'
        """
        # Default to mixed if we can't determine
        self.current_market_state = "mixed"
        
        try:
            # Use 1h timeframe for market state analysis if available
            if '1h' in data_dict and not data_dict['1h'].empty:
                df = data_dict['1h']
                
                # Calculate market volatility using ATR
                if 'atr' not in df.columns:
                    from app.indicators.technical_indicators import TechnicalIndicators
                    df = TechnicalIndicators.add_indicators(df)
                
                # Analyze last 20 candles
                recent_df = df.tail(20)
                
                # Check volatility relative to price
                atr = recent_df['atr'].iloc[-1]
                close = recent_df['close'].iloc[-1]
                volatility_pct = atr / close
                
                # Check trend strength
                directional_movement = abs(recent_df['close'].iloc[-1] - recent_df['close'].iloc[0]) / recent_df['close'].iloc[0]
                
                # Determine market state
                if volatility_pct > 0.02:  # High volatility (2%+)
                    if directional_movement < 0.03:  # Range-bound
                        self.current_market_state = "scalping"
                    else:  # Trending with high volatility
                        self.current_market_state = "mixed"
                else:  # Low volatility
                    if directional_movement > 0.05:  # Strong trend
                        self.current_market_state = "swing"
                    else:  # Low volatility, weak trend
                        self.current_market_state = "mixed"
                        
                logger.info(f"Market state for {self.symbol}: {self.current_market_state} (volatility: {volatility_pct:.4f}, directional: {directional_movement:.4f})")
                
        except Exception as e:
            logger.error(f"Error analyzing market state: {e}")
            
        return self.current_market_state
    
    def get_best_strategy(self):
        """
        Get the best strategy based on current market conditions
        
        Returns:
            tuple: (strategy_name, strategy_object)
        """
        if not self.strategies:
            logger.warning("No strategies available")
            return None, None
            
        # If only one strategy is enabled, return it
        if len(self.strategies) == 1:
            strategy_name = list(self.strategies.keys())[0]
            return strategy_name, self.strategies[strategy_name]
            
        # Determine best strategy based on market state
        if self.current_market_state == "scalping" and "scalping" in self.strategies:
            return "scalping", self.strategies["scalping"]
            
        elif self.current_market_state == "swing" and "swing" in self.strategies:
            return "swing", self.strategies["swing"]
            
        # For mixed state or if preferred strategy is not available,
        # choose based on signal strength
        scalping_score = 0
        swing_score = 0
        
        # Check signals from each strategy
        if "scalping" in self.strategies and self.strategies["scalping"] is not None:
            should_enter, signal = self.strategies["scalping"].should_enter_trade()
            if should_enter:
                scalping_score = 1
                
        if "swing" in self.strategies and self.strategies["swing"] is not None:
            should_enter, signal = self.strategies["swing"].should_enter_trade()
            if should_enter:
                swing_score = 1
                
        # Choose the strategy with the higher score
        if scalping_score > swing_score:
            return "scalping", self.strategies["scalping"]
        elif swing_score > scalping_score:
            return "swing", self.strategies["swing"]
        else:
            # If tied or no signals, default to scalping for now
            return "scalping", self.strategies.get("scalping")
    
    def should_enter_trade(self, market_data=None):
        """
        Check if any strategy indicates a trade entry
        
        Args:
            market_data (dict, optional): Latest market data. If None, will use data from prepare_strategies
            
        Returns:
            dict: Dictionary with entry info or None if no entry signal
        """
        strategy_name, strategy = self.get_best_strategy()
        
        if strategy is None:
            return None
        
        try:
            # Pass market_data to strategy's should_enter_trade if available
            if market_data is not None and hasattr(strategy, 'should_enter_trade'):
                should_enter, signal_data = strategy.should_enter_trade(market_data)
            else:
                should_enter, signal_data = strategy.should_enter_trade()
            
            if should_enter and signal_data:
                logger.info(f"Trade entry signal from {strategy_name} strategy for {self.symbol}")
                return {
                    "should_enter": True,
                    "strategy_name": strategy_name,
                    "signal_data": signal_data
                }
        except Exception as e:
            logger.error(f"Error checking entry signal for {self.symbol} with {strategy_name} strategy: {e}")
            
        return None
        
    def get_strategy_by_name(self, strategy_name):
        """
        Get a strategy by name
        
        Args:
            strategy_name (str): Name of the strategy
            
        Returns:
            object: Strategy object or None if not found
        """
        return self.strategies.get(strategy_name.lower(), None) 