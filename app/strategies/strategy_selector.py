import pandas as pd
import numpy as np
from app.strategies.scalping_strategy import ScalpingStrategy
from app.strategies.swing_strategy import SwingStrategy
from app.config.config import SCALPING_ENABLED, SWING_TRADING_ENABLED
from app.utils.logger import get_logger

logger = get_logger()

class StrategySelector:
    def __init__(self, symbol, timeframes=None):
        self.symbol = symbol
        self.timeframes = timeframes or ['1m', '5m', '15m', '1h', '4h', '1d']
        
        # Initialize strategies
        self.scalping_strategy = ScalpingStrategy(symbol) if SCALPING_ENABLED else None
        self.swing_strategy = SwingStrategy(symbol) if SWING_TRADING_ENABLED else None
        
        self.market_state = None
    
    def prepare_strategies(self, data_dict):
        """
        Prepare data for all active strategies
        
        Args:
            data_dict (dict): Dictionary with timeframe as key and DataFrame as value
            
        Returns:
            dict: Dictionary with prepared data for each strategy
        """
        prepared_data = {}
        
        if self.scalping_strategy:
            prepared_data['scalping'] = self.scalping_strategy.prepare_data(data_dict)
            
        if self.swing_strategy:
            prepared_data['swing'] = self.swing_strategy.prepare_data(data_dict)
            
        # Analyze market state for strategy selection
        self._analyze_market_state(data_dict)
            
        return prepared_data
    
    def _analyze_market_state(self, data_dict):
        """
        Analyze market state to determine which strategy to use
        
        Args:
            data_dict (dict): Dictionary with timeframe as key and DataFrame as value
        """
        try:
            # Default to mixed state
            self.market_state = "mixed"
            
            # Analyze market volatility and trend to determine optimal strategy
            if '1h' not in data_dict or data_dict['1h'].empty:
                logger.warning(f"No 1h data available for {self.symbol}, using default market state")
                return
                
            df_1h = data_dict['1h'].copy()
            
            # Calculate volatility (using ATR or similar measure)
            high_low_range = df_1h['high'] - df_1h['low']
            close_to_close = abs(df_1h['close'] - df_1h['close'].shift(1))
            true_range = pd.concat([high_low_range, close_to_close], axis=1).max(axis=1)
            atr_14 = true_range.rolling(window=14).mean().iloc[-1]
            
            # Normalize ATR by current price
            current_price = df_1h['close'].iloc[-1]
            normalized_atr = atr_14 / current_price
            
            # Calculate directional movement for trending or ranging market
            df_1h['daily_return'] = df_1h['close'].pct_change()
            df_1h['direction'] = np.where(df_1h['daily_return'] > 0, 1, -1)
            
            # Check if market has been consistently moving in one direction
            directional_consistency = abs(df_1h['direction'].tail(14).sum()) / 14
            
            # Determine market conditions based on volatility and consistency
            high_volatility = normalized_atr > 0.015  # 1.5% volatility threshold
            trending_market = directional_consistency > 0.6  # 60% consistency threshold
            
            if high_volatility and trending_market:
                # High volatility trending market favors swing trading
                self.market_state = "swing"
                logger.info(f"Market state for {self.symbol}: High volatility trending market - selecting Swing Trading")
            elif high_volatility and not trending_market:
                # High volatility ranging market can work with both strategies
                self.market_state = "mixed"
                logger.info(f"Market state for {self.symbol}: High volatility ranging market - using mixed strategies")
            elif not high_volatility and trending_market:
                # Low volatility trending market can work with both strategies
                self.market_state = "mixed"
                logger.info(f"Market state for {self.symbol}: Low volatility trending market - using mixed strategies")
            else:
                # Low volatility ranging market favors scalping
                self.market_state = "scalping"
                logger.info(f"Market state for {self.symbol}: Low volatility ranging market - selecting Scalping")
                
        except Exception as e:
            logger.error(f"Error analyzing market state for {self.symbol}: {e}")
            self.market_state = "mixed"  # Default to mixed strategies
    
    def get_best_strategy(self):
        """
        Get the best strategy based on current market conditions
        
        Returns:
            tuple: (strategy, name) - (strategy object, strategy name)
        """
        if self.market_state == "scalping" and self.scalping_strategy:
            return self.scalping_strategy, "Scalping"
        elif self.market_state == "swing" and self.swing_strategy:
            return self.swing_strategy, "Swing"
        else:
            # For mixed state, evaluate signals from both strategies and pick the strongest
            scalping_should_enter, scalping_signal = self.scalping_strategy.should_enter_trade() if self.scalping_strategy else (False, None)
            swing_should_enter, swing_signal = self.swing_strategy.should_enter_trade() if self.swing_strategy else (False, None)
            
            # Compare signal strengths
            if scalping_should_enter and swing_should_enter:
                if scalping_signal['strength'] > swing_signal['strength']:
                    return self.scalping_strategy, "Scalping"
                else:
                    return self.swing_strategy, "Swing"
            elif scalping_should_enter:
                return self.scalping_strategy, "Scalping"
            elif swing_should_enter:
                return self.swing_strategy, "Swing"
            else:
                # No clear signals, default to scalping for higher frequency
                return self.scalping_strategy if self.scalping_strategy else self.swing_strategy, "Default"
    
    def should_enter_trade(self):
        """
        Check if any strategy should enter a trade
        
        Returns:
            tuple: (bool, dict, str) - (should_enter, signal_data, strategy_name)
        """
        # Get best strategy for current market conditions
        best_strategy, strategy_name = self.get_best_strategy()
        
        if not best_strategy:
            return False, None, None
            
        # Check if best strategy has a trade signal
        should_enter, signal_data = best_strategy.should_enter_trade()
        
        if should_enter and signal_data:
            logger.info(f"Trade entry signal from {strategy_name} strategy for {self.symbol}")
            return True, signal_data, strategy_name
            
        return False, None, None 