import pandas as pd
import numpy as np
from app.strategies.base_strategy import BaseStrategy
from app.indicators.technical_indicators import TechnicalIndicators
from app.config.config import (
    SCALPING_PROFIT_TARGET,
    SCALPING_STOP_LOSS,
    SCALPING_RSI_OVERBOUGHT,
    SCALPING_RSI_OVERSOLD
)
from app.utils.logger import get_logger

logger = get_logger()

class ScalpingStrategy(BaseStrategy):
    """
    Scalping strategy implementation for short-term trades
    
    Uses a combination of RSI, Bollinger Bands, and short-term EMAs
    to identify short-term trading opportunities.
    """
    
    def __init__(self, symbol, timeframes=None):
        """
        Initialize the scalping strategy
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            timeframes (list, optional): List of timeframes to analyze
        """
        # Scalping focuses on shorter timeframes
        self.default_timeframes = ['1m', '5m', '15m']
        super().__init__(symbol, timeframes or self.default_timeframes)
        self.profit_target = SCALPING_PROFIT_TARGET
        self.stop_loss_pct = SCALPING_STOP_LOSS
        self.primary_timeframe = '5m'  # Primary timeframe for signals
    
    def generate_signal(self):
        """
        Generate trading signal based on scalping strategy
        
        Returns:
            dict: Signal data with action, direction, entry price, etc.
        """
        if not self.data or self.primary_timeframe not in self.data:
            logger.warning(f"No data available for {self.primary_timeframe} timeframe")
            return {
                "action": "none",
                "timestamp": pd.Timestamp.now()
            }
        
        # Get the latest data for primary timeframe
        df = self.data[self.primary_timeframe]
        if len(df) < 10:  # Require at least 10 candles for analysis
            return {"action": "none"}
            
        # Get the most recent data points
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Check for entry conditions
        signal = self._check_entry_conditions(df, current, previous)
        
        if signal["action"] == "entry":
            # Calculate stop loss and take profit levels
            entry_price = float(current['close'])
            direction = signal["direction"]
            
            if 'atr' in current and not pd.isna(current['atr']):
                atr_value = current['atr']
                stop_loss = self.get_stop_loss_price(entry_price, direction, atr_value)
            else:
                stop_loss = self.get_stop_loss_price(entry_price, direction)
                
            take_profit = self.get_take_profit_price(entry_price, direction)
            
            # Add price levels to signal
            signal.update({
                "entry_price": entry_price,
                "stop_loss_price": stop_loss,
                "take_profit_price": take_profit,
                "risk_per_trade": self.stop_loss_pct,
                "strategy_name": "Scalping"
            })
            
        return signal
    
    def _check_entry_conditions(self, df, current, previous):
        """Check entry conditions for scalping strategy"""
        # Initialize with no action
        signal = {
            "action": "none",
            "timestamp": current.name if hasattr(current, 'name') else pd.Timestamp.now(),
            "timeframe": self.primary_timeframe
        }
        
        # Check for oversold conditions (long entry)
        if (
            # RSI crossed below oversold threshold and now moving up
            previous['rsi'] < SCALPING_RSI_OVERSOLD and current['rsi'] > previous['rsi'] and
            # Price is below lower Bollinger Band
            current['close'] < current['bollinger_lower'] and
            # Volume is increasing
            current['volume'] > previous['volume']
        ):
            # Long entry signal
            signal.update({
                "action": "entry",
                "direction": "long",
                "indicators": {
                    "rsi": current['rsi'],
                    "bb_lower": current['bollinger_lower'],
                    "price": current['close']
                },
                "reasoning": f"Oversold conditions with RSI at {current['rsi']:.2f} and price below lower Bollinger Band"
            })
            
        # Check for overbought conditions (short entry)
        elif (
            # RSI crossed above overbought threshold and now moving down
            previous['rsi'] > SCALPING_RSI_OVERBOUGHT and current['rsi'] < previous['rsi'] and
            # Price is above upper Bollinger Band
            current['close'] > current['bollinger_upper'] and
            # Volume is increasing
            current['volume'] > previous['volume']
        ):
            # Short entry signal
            signal.update({
                "action": "entry",
                "direction": "short",
                "indicators": {
                    "rsi": current['rsi'],
                    "bb_upper": current['bollinger_upper'],
                    "price": current['close']
                },
                "reasoning": f"Overbought conditions with RSI at {current['rsi']:.2f} and price above upper Bollinger Band"
            })
            
        return signal
    
    def should_enter_trade(self, market_data=None):
        """
        Determine if a new trade should be entered
        
        Args:
            market_data (dict, optional): Latest market data. If provided, will use this instead of self.data
            
        Returns:
            tuple: (should_enter, signal_data)
        """
        # If market_data is provided directly, analyze it
        if market_data is not None:
            try:
                # Check if we have the required indicators
                if 'rsi' in market_data and 'bollinger_upper' in market_data and 'bollinger_lower' in market_data:
                    # Initialize with no action
                    signal = {
                        "action": "none",
                        "timestamp": pd.Timestamp.now(),
                        "timeframe": self.primary_timeframe
                    }
                    
                    # Check for oversold conditions (long entry)
                    if (
                        # RSI below oversold threshold
                        market_data['rsi'] < SCALPING_RSI_OVERSOLD and
                        # Price is below lower Bollinger Band
                        market_data['close'] < market_data['bollinger_lower']
                    ):
                        # Long entry signal
                        signal = {
                            "action": "entry",
                            "direction": "long",
                            "indicators": {
                                "rsi": market_data['rsi'],
                                "bb_lower": market_data['bollinger_lower'],
                                "price": market_data['close']
                            },
                            "reasoning": f"Oversold conditions with RSI at {market_data['rsi']:.2f} and price below lower Bollinger Band",
                            "entry_price": float(market_data['close']),
                            "strategy_name": "Scalping"
                        }
                        
                    # Check for overbought conditions (short entry)
                    elif (
                        # RSI above overbought threshold
                        market_data['rsi'] > SCALPING_RSI_OVERBOUGHT and
                        # Price is above upper Bollinger Band
                        market_data['close'] > market_data['bollinger_upper']
                    ):
                        # Short entry signal
                        signal = {
                            "action": "entry",
                            "direction": "short",
                            "indicators": {
                                "rsi": market_data['rsi'],
                                "bb_upper": market_data['bollinger_upper'],
                                "price": market_data['close']
                            },
                            "reasoning": f"Overbought conditions with RSI at {market_data['rsi']:.2f} and price above upper Bollinger Band",
                            "entry_price": float(market_data['close']),
                            "strategy_name": "Scalping"
                        }
                    
                    # If we have an entry signal, calculate stop loss and take profit
                    if signal["action"] == "entry":
                        entry_price = float(market_data['close'])
                        direction = signal["direction"]
                        
                        if 'atr' in market_data and not pd.isna(market_data['atr']):
                            atr_value = market_data['atr']
                            stop_loss = self.get_stop_loss_price(entry_price, direction, atr_value)
                        else:
                            stop_loss = self.get_stop_loss_price(entry_price, direction)
                            
                        take_profit = self.get_take_profit_price(entry_price, direction)
                        
                        # Add price levels to signal
                        signal["stop_loss_price"] = stop_loss
                        signal["take_profit_price"] = take_profit
                        signal["risk_per_trade"] = self.stop_loss_pct
                    
                    should_enter = signal["action"] == "entry"
                    return should_enter, signal
                else:
                    logger.warning(f"Missing required indicators in market data for {self.symbol}")
                    return False, {"action": "none", "reason": "Missing indicators"}
            except Exception as e:
                logger.error(f"Error analyzing market data for {self.symbol}: {e}")
                return False, {"action": "none", "reason": f"Error: {str(e)}"}
        
        # Otherwise use the signal generated from historical data
        signal = self.generate_signal()
        should_enter = signal["action"] == "entry"
        return should_enter, signal
    
    def should_exit_trade(self, market_data=None, position_data=None):
        """
        Determine if an existing trade should be exited
        
        Args:
            market_data (dict, optional): Latest market data
            position_data (dict): Current position data
            
        Returns:
            tuple: (should_exit, exit_reason)
        """
        # If no position data provided, can't make exit decision
        if position_data is None:
            return False, "No position data available"
            
        # Use provided market data if available
        if market_data is not None:
            try:
                # Check if we have the required indicators
                if 'rsi' in market_data and 'bollinger_upper' in market_data and 'bollinger_lower' in market_data:
                    # Extract position details
                    entry_price = position_data.get("entry_price", 0)
                    direction = "long" if position_data.get("side") == "BUY" else "short"
                    
                    # Calculate current profit/loss
                    current_price = float(market_data['close'])
                    if direction == "long":
                        profit_pct = (current_price - entry_price) / entry_price
                    else:
                        profit_pct = (entry_price - current_price) / entry_price
                    
                    # Check exit conditions
                    
                    # 1. Check for profit target hit
                    if profit_pct >= self.profit_target:
                        return True, f"Profit target reached: {profit_pct:.2%}"
                        
                    # 2. Check for RSI reversal
                    if direction == "long" and market_data['rsi'] > 70:
                        return True, f"RSI overbought: {market_data['rsi']:.2f}"
                        
                    if direction == "short" and market_data['rsi'] < 30:
                        return True, f"RSI oversold: {market_data['rsi']:.2f}"
                        
                    # 3. Check for Bollinger Band mean reversion
                    if direction == "long" and current_price > market_data['bollinger_upper']:
                        return True, "Price above upper Bollinger Band"
                        
                    if direction == "short" and current_price < market_data['bollinger_lower']:
                        return True, "Price below lower Bollinger Band"
                else:
                    logger.warning(f"Missing required indicators in market data for exit decision on {self.symbol}")
            except Exception as e:
                logger.error(f"Error analyzing market data for exit decision on {self.symbol}: {e}")
                return False, f"Error: {str(e)}"
        
        # If market_data wasn't provided or we couldn't use it, use stored data
        if not self.data or self.primary_timeframe not in self.data:
            return False, "No data available"
            
        df = self.data[self.primary_timeframe]
        if len(df) < 2:
            return False, "Insufficient data"
            
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Extract position details
        entry_price = position_data.get("entry_price", 0)
        direction = "long" if position_data.get("side") == "BUY" else "short"
        
        # Calculate current profit/loss
        current_price = current['close']
        if direction == "long":
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price
        
        # Check exit conditions
        
        # 1. Check for profit target hit
        if profit_pct >= self.profit_target:
            return True, f"Profit target reached: {profit_pct:.2%}"
            
        # 2. Check for RSI reversal
        if direction == "long" and current['rsi'] > 70 and previous['rsi'] > current['rsi']:
            return True, f"RSI overbought and turning down: {current['rsi']:.2f}"
            
        if direction == "short" and current['rsi'] < 30 and previous['rsi'] < current['rsi']:
            return True, f"RSI oversold and turning up: {current['rsi']:.2f}"
            
        # 3. Check for Bollinger Band mean reversion
        if direction == "long" and current['close'] > current['bollinger_upper']:
            return True, "Price above upper Bollinger Band"
            
        if direction == "short" and current['close'] < current['bollinger_lower']:
            return True, "Price below lower Bollinger Band"
            
        # No exit signal
        return False, "No exit conditions met"
    
    def get_stop_loss_price(self, entry_price, direction, atr_value=None):
        """Calculate stop loss price based on strategy parameters"""
        if atr_value:
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return self.calculate_stop_loss(entry_price, direction)
    
    def get_take_profit_price(self, entry_price, direction):
        """Calculate take profit price based on strategy parameters"""
        if direction == "long":
            return entry_price * (1 + self.profit_target)
        else:
            return entry_price * (1 - self.profit_target)
    
    def calculate_stop_loss(self, entry_price, is_long=True):
        """Calculate stop loss price for scalping strategy"""
        if is_long:
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return entry_price * (1 + self.stop_loss_pct)
    
    def calculate_take_profit(self, entry_price, is_long=True):
        """Calculate take profit price for scalping strategy"""
        if is_long:
            return entry_price * (1 + self.profit_target)
        else:
            return entry_price * (1 - self.profit_target)
    
    def get_signal_reasoning(self, signal_data):
        """Generate human-readable reasoning for a scalping signal"""
        if not signal_data:
            return "No signal data available"
            
        signal_type = signal_data['type']
        indicators = signal_data['indicators']
        
        if signal_type == 'long':
            reasoning = [
                f"Scalping long signal detected for {self.symbol} on {signal_data['timeframe']} timeframe.",
                f"Entry price: {signal_data['price']:.2f}",
            ]
            
            # Add reasoning based on indicators
            if indicators['rsi'] < 30:
                reasoning.append(f"RSI shows oversold conditions at {indicators['rsi']:.2f} (below 30)")
            
            if 'bb_lower' in indicators and indicators['bb_pct'] < 0.2:
                reasoning.append(f"Price is near lower Bollinger Band (BB%: {indicators['bb_pct']:.2f})")
            
            if 'ema12' in indicators and 'ema26' in indicators and indicators['ema12'] > indicators['ema26']:
                reasoning.append(f"Bullish EMA crossover (EMA12: {indicators['ema12']:.2f} > EMA26: {indicators['ema26']:.2f})")
            
            if 'volume' in indicators and 'avg_volume' in indicators and indicators['volume'] > indicators['avg_volume']:
                volume_ratio = indicators['volume'] / indicators['avg_volume']
                reasoning.append(f"Volume confirmation ({volume_ratio:.1f}x average volume)")
                
            reasoning.append(f"Signal strength: {signal_data['strength']:.2f}")
            
            if 'confirmed' in signal_data and signal_data['confirmed']:
                reasoning.append("Signal confirmed on higher timeframe")
                
        elif signal_type == 'short':
            reasoning = [
                f"Scalping short signal detected for {self.symbol} on {signal_data['timeframe']} timeframe.",
                f"Entry price: {signal_data['price']:.2f}",
            ]
            
            # Add reasoning based on indicators
            if indicators['rsi'] > 70:
                reasoning.append(f"RSI shows overbought conditions at {indicators['rsi']:.2f} (above 70)")
            
            if 'bb_upper' in indicators and indicators['bb_pct'] > 0.8:
                reasoning.append(f"Price is near upper Bollinger Band (BB%: {indicators['bb_pct']:.2f})")
            
            if 'ema12' in indicators and 'ema26' in indicators and indicators['ema12'] < indicators['ema26']:
                reasoning.append(f"Bearish EMA crossover (EMA12: {indicators['ema12']:.2f} < EMA26: {indicators['ema26']:.2f})")
            
            if 'volume' in indicators and 'avg_volume' in indicators and indicators['volume'] > indicators['avg_volume']:
                volume_ratio = indicators['volume'] / indicators['avg_volume']
                reasoning.append(f"Volume confirmation ({volume_ratio:.1f}x average volume)")
                
            reasoning.append(f"Signal strength: {signal_data['strength']:.2f}")
            
            if 'confirmed' in signal_data and signal_data['confirmed']:
                reasoning.append("Signal confirmed on higher timeframe")
        
        return "\n• ".join(reasoning) 