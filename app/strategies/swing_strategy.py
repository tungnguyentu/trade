import pandas as pd
import numpy as np
from app.strategies.base_strategy import BaseStrategy
from app.config.config import SWING_PROFIT_TARGET, SWING_STOP_LOSS
from app.utils.logger import get_logger

logger = get_logger()

class SwingStrategy(BaseStrategy):
    def __init__(self, symbol, timeframes=None):
        if timeframes is None:
            # Swing trading primarily uses longer timeframes
            timeframes = ['1h', '4h', '1d']
            
        super().__init__(symbol, timeframes)
        self.name = "Swing"
        self.profit_target = SWING_PROFIT_TARGET
        self.stop_loss_pct = SWING_STOP_LOSS
    
    def generate_signals(self):
        """
        Generate swing trading signals based on Ichimoku Cloud, MACD, and volume analysis
        
        Returns:
            dict: Signal information with entry/exit points
        """
        signals = []
        
        try:
            # Ensure we have data for the primary timeframe (4h for swing trading)
            if '4h' not in self.data or self.data['4h'].empty:
                logger.warning(f"No 4h data available for {self.symbol}")
                return signals
                
            # Get the latest data for primary timeframe
            df_4h = self.data['4h'].copy()
            
            # Look for swing trading opportunities
            for i in range(1, len(df_4h)):
                # Skip if we already have signals for this candle
                if i < len(df_4h) - 1:
                    continue
                    
                # Price data
                close = df_4h['close'].iloc[i]
                prev_close = df_4h['close'].iloc[i-1]
                
                # Ichimoku Cloud indicators
                cloud_bullish = df_4h['ichimoku_cloud_bullish'].iloc[i]
                ichimoku_a = df_4h['ichimoku_a'].iloc[i]
                ichimoku_b = df_4h['ichimoku_b'].iloc[i]
                ichimoku_conv = df_4h['ichimoku_conv'].iloc[i]
                ichimoku_base = df_4h['ichimoku_base'].iloc[i]
                
                # MACD indicators
                macd = df_4h['macd'].iloc[i]
                macd_signal = df_4h['macd_signal'].iloc[i]
                macd_diff = df_4h['macd_diff'].iloc[i]
                prev_macd_diff = df_4h['macd_diff'].iloc[i-1]
                
                # Volume indicators
                volume = df_4h['volume'].iloc[i]
                obv = df_4h['obv'].iloc[i]
                prev_obv = df_4h['obv'].iloc[i-1]
                avg_volume = df_4h['volume'].rolling(window=20).mean().iloc[i]
                
                # Ichimoku Cloud conditions
                price_above_cloud = close > max(ichimoku_a, ichimoku_b)
                price_below_cloud = close < min(ichimoku_a, ichimoku_b)
                
                # Tenkan-sen and Kijun-sen crossover
                tk_bullish_cross = ichimoku_conv > ichimoku_base and df_4h['ichimoku_conv'].iloc[i-1] <= df_4h['ichimoku_base'].iloc[i-1]
                tk_bearish_cross = ichimoku_conv < ichimoku_base and df_4h['ichimoku_conv'].iloc[i-1] >= df_4h['ichimoku_base'].iloc[i-1]
                
                # MACD conditions
                macd_bullish_cross = macd_diff > 0 and prev_macd_diff <= 0
                macd_bearish_cross = macd_diff < 0 and prev_macd_diff >= 0
                
                # Volume conditions
                volume_increasing = volume > avg_volume * 1.2
                obv_increasing = obv > prev_obv
                
                # Long signal conditions
                if (
                    (cloud_bullish and price_above_cloud) or
                    (tk_bullish_cross and cloud_bullish) or
                    (macd_bullish_cross and price_above_cloud)
                ) and (volume_increasing and obv_increasing):
                    timestamp = df_4h.index[i]
                    signal = {
                        'timestamp': timestamp,
                        'type': 'long',
                        'price': close,
                        'timeframe': '4h',
                        'strength': self._calculate_signal_strength(
                            cloud_bullish, price_above_cloud, tk_bullish_cross, 
                            macd_bullish_cross, volume_increasing, obv_increasing
                        ),
                        'indicators': {
                            'ichimoku_a': ichimoku_a,
                            'ichimoku_b': ichimoku_b,
                            'ichimoku_conv': ichimoku_conv,
                            'ichimoku_base': ichimoku_base,
                            'macd': macd,
                            'macd_signal': macd_signal,
                            'macd_diff': macd_diff,
                            'volume': volume,
                            'avg_volume': avg_volume,
                            'obv': obv
                        }
                    }
                    signals.append(signal)
                
                # Short signal conditions
                elif (
                    (not cloud_bullish and price_below_cloud) or
                    (tk_bearish_cross and not cloud_bullish) or
                    (macd_bearish_cross and price_below_cloud)
                ) and (volume_increasing and not obv_increasing):
                    timestamp = df_4h.index[i]
                    signal = {
                        'timestamp': timestamp,
                        'type': 'short',
                        'price': close,
                        'timeframe': '4h',
                        'strength': self._calculate_signal_strength(
                            not cloud_bullish, price_below_cloud, tk_bearish_cross, 
                            macd_bearish_cross, volume_increasing, not obv_increasing
                        ),
                        'indicators': {
                            'ichimoku_a': ichimoku_a,
                            'ichimoku_b': ichimoku_b,
                            'ichimoku_conv': ichimoku_conv,
                            'ichimoku_base': ichimoku_base,
                            'macd': macd,
                            'macd_signal': macd_signal,
                            'macd_diff': macd_diff,
                            'volume': volume,
                            'avg_volume': avg_volume,
                            'obv': obv
                        }
                    }
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating swing signals for {self.symbol}: {e}")
            return []
    
    def _calculate_signal_strength(self, cloud_direction, price_cloud_position, tk_cross, macd_cross, volume_increasing, obv_direction):
        """Calculate signal strength based on how many conditions align"""
        strength = 0
        if cloud_direction:
            strength += 1
        if price_cloud_position:
            strength += 1
        if tk_cross:
            strength += 1
        if macd_cross:
            strength += 1
        if volume_increasing:
            strength += 0.5
        if obv_direction:
            strength += 0.5
            
        # Return normalized strength (0-1)
        return strength / 5.0
    
    def should_enter_trade(self):
        """
        Check if we should enter a swing trade
        
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
            if '1d' in self.data and not self.data['1d'].empty:
                df_1d = self.data['1d']
                latest_1d = df_1d.iloc[-1]
                
                if latest_signal['type'] == 'long':
                    # Confirm long signal with daily data
                    if latest_1d['ichimoku_cloud_bullish'] and latest_1d['macd_diff'] > 0:
                        logger.info(f"Swing long signal confirmed on daily timeframe for {self.symbol}")
                        latest_signal['confirmed'] = True
                        return True, latest_signal
                        
                elif latest_signal['type'] == 'short':
                    # Confirm short signal with daily data
                    if not latest_1d['ichimoku_cloud_bullish'] and latest_1d['macd_diff'] < 0:
                        logger.info(f"Swing short signal confirmed on daily timeframe for {self.symbol}")
                        latest_signal['confirmed'] = True
                        return True, latest_signal
            else:
                # If higher timeframe not available, use signal strength as confirmation
                if latest_signal['strength'] >= 0.8:  # At least 4 out of 5 conditions
                    logger.info(f"Strong swing signal (no daily confirmation) for {self.symbol}")
                    latest_signal['confirmed'] = True
                    return True, latest_signal
        
        return False, None
    
    def should_exit_trade(self, entry_price, current_position):
        """
        Check if we should exit a swing trade
        
        Args:
            entry_price (float): Entry price
            current_position (dict): Current position information
            
        Returns:
            tuple: (bool, str) - (should_exit, reason)
        """
        if not self.data or '4h' not in self.data or self.data['4h'].empty:
            return False, "No data available"
            
        # Get latest price
        latest_data = self.data['4h'].iloc[-1]
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
            
        # Check for Ichimoku Cloud reversal
        cloud_bullish = latest_data['ichimoku_cloud_bullish']
        price = current_price
        ichimoku_a = latest_data['ichimoku_a']
        ichimoku_b = latest_data['ichimoku_b']
        
        if is_long and not cloud_bullish and price < min(ichimoku_a, ichimoku_b):
            return True, "Price moved below bearish cloud"
            
        if not is_long and cloud_bullish and price > max(ichimoku_a, ichimoku_b):
            return True, "Price moved above bullish cloud"
            
        # Check for MACD signal line crossover
        macd = latest_data['macd']
        macd_signal = latest_data['macd_signal']
        
        if is_long and macd < macd_signal:
            return True, f"MACD bearish crossover: {macd:.6f} < {macd_signal:.6f}"
            
        if not is_long and macd > macd_signal:
            return True, f"MACD bullish crossover: {macd:.6f} > {macd_signal:.6f}"
            
        return False, "No exit signal"
    
    def calculate_stop_loss(self, entry_price, is_long=True):
        """Calculate stop loss price for swing strategy"""
        if is_long:
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return entry_price * (1 + self.stop_loss_pct)
    
    def calculate_take_profit(self, entry_price, is_long=True):
        """Calculate take profit price for swing strategy"""
        if is_long:
            return entry_price * (1 + self.profit_target)
        else:
            return entry_price * (1 - self.profit_target)
    
    def get_signal_reasoning(self, signal_data):
        """Generate human-readable reasoning for a swing signal"""
        if not signal_data:
            return "No signal data available"
            
        signal_type = signal_data['type']
        indicators = signal_data['indicators']
        
        if signal_type == 'long':
            reasoning = [
                f"Swing Trading long signal detected for {self.symbol} on {signal_data['timeframe']} timeframe.",
                f"Entry price: {signal_data['price']:.2f}",
            ]
            
            # Add reasoning based on indicators
            if 'ichimoku_a' in indicators and 'ichimoku_b' in indicators:
                cloud_thickness = abs(indicators['ichimoku_a'] - indicators['ichimoku_b'])
                cloud_midpoint = (indicators['ichimoku_a'] + indicators['ichimoku_b']) / 2
                
                # Check if price is above cloud
                if signal_data['price'] > max(indicators['ichimoku_a'], indicators['ichimoku_b']):
                    reasoning.append(f"Price is above Ichimoku Cloud ({(signal_data['price'] / cloud_midpoint - 1) * 100:.1f}% above cloud midpoint)")
            
            if 'ichimoku_conv' in indicators and 'ichimoku_base' in indicators:
                # Check for Tenkan-sen/Kijun-sen crossover
                if indicators['ichimoku_conv'] > indicators['ichimoku_base']:
                    reasoning.append(f"Bullish Tenkan-sen/Kijun-sen crossover (Tenkan: {indicators['ichimoku_conv']:.2f} > Kijun: {indicators['ichimoku_base']:.2f})")
            
            if 'macd' in indicators and 'macd_signal' in indicators:
                # Check for MACD signal line crossover
                if indicators['macd'] > indicators['macd_signal']:
                    reasoning.append(f"Bullish MACD signal line crossover (MACD: {indicators['macd']:.6f} > Signal: {indicators['macd_signal']:.6f})")
            
            if 'volume' in indicators and 'avg_volume' in indicators:
                # Check for volume confirmation
                volume_ratio = indicators['volume'] / indicators['avg_volume']
                if volume_ratio > 1:
                    reasoning.append(f"Volume confirmation ({volume_ratio:.1f}x average volume)")
                
            reasoning.append(f"Signal strength: {signal_data['strength']:.2f}")
            
            if 'confirmed' in signal_data and signal_data['confirmed']:
                reasoning.append("Signal confirmed on daily timeframe")
                
        elif signal_type == 'short':
            reasoning = [
                f"Swing Trading short signal detected for {self.symbol} on {signal_data['timeframe']} timeframe.",
                f"Entry price: {signal_data['price']:.2f}",
            ]
            
            # Add reasoning based on indicators
            if 'ichimoku_a' in indicators and 'ichimoku_b' in indicators:
                cloud_thickness = abs(indicators['ichimoku_a'] - indicators['ichimoku_b'])
                cloud_midpoint = (indicators['ichimoku_a'] + indicators['ichimoku_b']) / 2
                
                # Check if price is below cloud
                if signal_data['price'] < min(indicators['ichimoku_a'], indicators['ichimoku_b']):
                    reasoning.append(f"Price is below Ichimoku Cloud ({(1 - signal_data['price'] / cloud_midpoint) * 100:.1f}% below cloud midpoint)")
            
            if 'ichimoku_conv' in indicators and 'ichimoku_base' in indicators:
                # Check for Tenkan-sen/Kijun-sen crossover
                if indicators['ichimoku_conv'] < indicators['ichimoku_base']:
                    reasoning.append(f"Bearish Tenkan-sen/Kijun-sen crossover (Tenkan: {indicators['ichimoku_conv']:.2f} < Kijun: {indicators['ichimoku_base']:.2f})")
            
            if 'macd' in indicators and 'macd_signal' in indicators:
                # Check for MACD signal line crossover
                if indicators['macd'] < indicators['macd_signal']:
                    reasoning.append(f"Bearish MACD signal line crossover (MACD: {indicators['macd']:.6f} < Signal: {indicators['macd_signal']:.6f})")
            
            if 'volume' in indicators and 'avg_volume' in indicators:
                # Check for volume confirmation
                volume_ratio = indicators['volume'] / indicators['avg_volume']
                if volume_ratio > 1:
                    reasoning.append(f"Volume confirmation ({volume_ratio:.1f}x average volume)")
                
            reasoning.append(f"Signal strength: {signal_data['strength']:.2f}")
            
            if 'confirmed' in signal_data and signal_data['confirmed']:
                reasoning.append("Signal confirmed on daily timeframe")
        
        return "\n• ".join(reasoning) 