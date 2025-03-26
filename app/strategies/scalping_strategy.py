import pandas as pd
import numpy as np
from app.strategies.base_strategy import BaseStrategy
from app.config.config import SCALPING_PROFIT_TARGET, SCALPING_STOP_LOSS
from app.utils.logger import get_logger

logger = get_logger()

class ScalpingStrategy(BaseStrategy):
    def __init__(self, symbol, timeframes=None):
        if timeframes is None:
            # Scalping primarily uses shorter timeframes
            timeframes = ['1m', '5m', '15m']
            
        super().__init__(symbol, timeframes)
        self.name = "Scalping"
        self.profit_target = SCALPING_PROFIT_TARGET
        self.stop_loss_pct = SCALPING_STOP_LOSS
    
    def generate_signals(self):
        """
        Generate scalping signals based on RSI, Bollinger Bands, and short-term MAs
        
        Returns:
            dict: Signal information with entry/exit points
        """
        signals = []
        
        try:
            # Ensure we have data for the primary timeframe (1m for scalping)
            if '1m' not in self.data or self.data['1m'].empty:
                logger.warning(f"No 1m data available for {self.symbol}")
                return signals
                
            # Get the latest data for primary timeframe
            df_1m = self.data['1m'].copy()
            
            # Look for scalping opportunities
            for i in range(1, len(df_1m)):
                # Skip if we already have signals for this candle
                if i < len(df_1m) - 1:
                    continue
                    
                # Price data
                close = df_1m['close'].iloc[i]
                prev_close = df_1m['close'].iloc[i-1]
                
                # Indicator values
                rsi = df_1m['rsi'].iloc[i]
                bb_lower = df_1m['bb_lower'].iloc[i]
                bb_upper = df_1m['bb_upper'].iloc[i]
                bb_pct = df_1m['bb_pct'].iloc[i]
                
                # Check if price is near Bollinger Bands
                near_lower_band = close <= bb_lower * 1.005  # Within 0.5% of lower band
                near_upper_band = close >= bb_upper * 0.995  # Within 0.5% of upper band
                
                # Check for RSI conditions
                rsi_oversold = rsi is not None and rsi <= 30
                rsi_overbought = rsi is not None and rsi >= 70
                
                # Candlestick pattern signals
                bullish_pattern = df_1m['bullish_engulfing'].iloc[i] or df_1m['hammer'].iloc[i]
                bearish_pattern = df_1m['bearish_engulfing'].iloc[i] or df_1m['shooting_star'].iloc[i]
                
                # Check for moving average crossovers
                ema12 = df_1m['ema_12'].iloc[i]
                ema26 = df_1m['ema_26'].iloc[i]
                prev_ema12 = df_1m['ema_12'].iloc[i-1]
                prev_ema26 = df_1m['ema_26'].iloc[i-1]
                
                ema_bullish_cross = prev_ema12 <= prev_ema26 and ema12 > ema26
                ema_bearish_cross = prev_ema12 >= prev_ema26 and ema12 < ema26
                
                # Check for volume confirmation
                volume = df_1m['volume'].iloc[i]
                avg_volume = df_1m['volume'].rolling(window=20).mean().iloc[i]
                volume_increase = volume > avg_volume * 1.5  # 50% above average
                
                # Long signal conditions (multiple conditions must align)
                if (
                    (near_lower_band and rsi_oversold) or
                    (bullish_pattern and rsi < 40) or
                    (ema_bullish_cross and volume_increase)
                ):
                    timestamp = df_1m.index[i]
                    signal = {
                        'timestamp': timestamp,
                        'type': 'long',
                        'price': close,
                        'timeframe': '1m',
                        'strength': self._calculate_signal_strength(
                            near_lower_band, rsi_oversold, bullish_pattern, 
                            ema_bullish_cross, volume_increase
                        ),
                        'indicators': {
                            'rsi': rsi,
                            'bb_lower': bb_lower,
                            'bb_pct': bb_pct,
                            'ema12': ema12,
                            'ema26': ema26,
                            'volume': volume,
                            'avg_volume': avg_volume
                        }
                    }
                    signals.append(signal)
                
                # Short signal conditions (multiple conditions must align)
                elif (
                    (near_upper_band and rsi_overbought) or
                    (bearish_pattern and rsi > 60) or
                    (ema_bearish_cross and volume_increase)
                ):
                    timestamp = df_1m.index[i]
                    signal = {
                        'timestamp': timestamp,
                        'type': 'short',
                        'price': close,
                        'timeframe': '1m',
                        'strength': self._calculate_signal_strength(
                            near_upper_band, rsi_overbought, bearish_pattern, 
                            ema_bearish_cross, volume_increase
                        ),
                        'indicators': {
                            'rsi': rsi,
                            'bb_upper': bb_upper,
                            'bb_pct': bb_pct,
                            'ema12': ema12,
                            'ema26': ema26,
                            'volume': volume,
                            'avg_volume': avg_volume
                        }
                    }
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating scalping signals for {self.symbol}: {e}")
            return []
    
    def _calculate_signal_strength(self, near_band, rsi_extreme, pattern, ema_cross, volume_increase):
        """Calculate signal strength based on how many conditions align"""
        strength = 0
        if near_band:
            strength += 1
        if rsi_extreme:
            strength += 1
        if pattern:
            strength += 1
        if ema_cross:
            strength += 1
        if volume_increase:
            strength += 1
            
        # Return normalized strength (0-1)
        return strength / 5.0
    
    def should_enter_trade(self):
        """
        Check if we should enter a scalping trade
        
        Returns:
            tuple: (bool, dict) - (should_enter, signal_data)
        """
        signals = self.generate_signals()
        
        if not signals:
            return False, None
            
        # Get the latest signal
        latest_signal = signals[-1]
        
        # Check for signal strength and confirmation
        if latest_signal['strength'] >= 0.6:  # At least 3 out of 5 conditions
            # Check for confirmation on higher timeframe if available
            if '5m' in self.data and not self.data['5m'].empty:
                df_5m = self.data['5m']
                latest_5m = df_5m.iloc[-1]
                
                if latest_signal['type'] == 'long':
                    # Confirm long signal with 5m data
                    if latest_5m['rsi'] < 50 and latest_5m['close'] < latest_5m['bb_middle']:
                        logger.info(f"Scalping long signal confirmed on 5m timeframe for {self.symbol}")
                        latest_signal['confirmed'] = True
                        return True, latest_signal
                        
                elif latest_signal['type'] == 'short':
                    # Confirm short signal with 5m data
                    if latest_5m['rsi'] > 50 and latest_5m['close'] > latest_5m['bb_middle']:
                        logger.info(f"Scalping short signal confirmed on 5m timeframe for {self.symbol}")
                        latest_signal['confirmed'] = True
                        return True, latest_signal
            else:
                # If higher timeframe not available, use signal strength as confirmation
                if latest_signal['strength'] >= 0.8:  # At least 4 out of 5 conditions
                    logger.info(f"Strong scalping signal (no 5m confirmation) for {self.symbol}")
                    latest_signal['confirmed'] = True
                    return True, latest_signal
        
        return False, None
    
    def should_exit_trade(self, entry_price, current_position):
        """
        Check if we should exit a scalping trade
        
        Args:
            entry_price (float): Entry price
            current_position (dict): Current position information
            
        Returns:
            tuple: (bool, str) - (should_exit, reason)
        """
        if not self.data or '1m' not in self.data or self.data['1m'].empty:
            return False, "No data available"
            
        # Get latest price
        latest_data = self.data['1m'].iloc[-1]
        current_price = latest_data['close']
        
        # Calculate P&L percentage
        is_long = current_position['type'] == 'long'
        if is_long:
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
            
        # Check for take profit
        if pnl_pct >= self.profit_target:
            return True, f"Take profit reached: {pnl_pct:.2%} >= {self.profit_target:.2%}"
            
        # Check for stop loss
        if pnl_pct <= -self.stop_loss_pct:
            return True, f"Stop loss triggered: {pnl_pct:.2%} <= -{self.stop_loss_pct:.2%}"
            
        # Check for reversal signals
        rsi = latest_data['rsi']
        
        if is_long and rsi > 70:
            return True, f"RSI overbought: {rsi:.2f} > 70"
            
        if not is_long and rsi < 30:
            return True, f"RSI oversold: {rsi:.2f} < 30"
            
        # Check for EMA crossover (exit signal)
        ema12 = latest_data['ema_12']
        ema26 = latest_data['ema_26']
        
        if is_long and ema12 < ema26:
            return True, f"EMA bearish crossover: {ema12:.2f} < {ema26:.2f}"
            
        if not is_long and ema12 > ema26:
            return True, f"EMA bullish crossover: {ema12:.2f} > {ema26:.2f}"
            
        return False, "No exit signal"
    
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