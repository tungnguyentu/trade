import pandas as pd
import numpy as np
import ta
from app.config.config import (
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    BOLLINGER_PERIOD, BOLLINGER_STD_DEV,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL
)
from app.utils.logger import get_logger

logger = get_logger()

class TechnicalIndicators:
    @staticmethod
    def add_rsi(df, period=RSI_PERIOD, column='close'):
        """Add Relative Strength Index to dataframe"""
        try:
            df['rsi'] = ta.momentum.RSIIndicator(
                close=df[column], 
                window=period
            ).rsi()
            return df
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            df['rsi'] = np.nan
            return df
    
    @staticmethod
    def add_bollinger_bands(df, period=BOLLINGER_PERIOD, std_dev=BOLLINGER_STD_DEV, column='close'):
        """Add Bollinger Bands to dataframe"""
        try:
            bollinger = ta.volatility.BollingerBands(
                close=df[column], 
                window=period, 
                window_dev=std_dev
            )
            df['bb_upper'] = bollinger.bollinger_hband()
            df['bb_middle'] = bollinger.bollinger_mavg()
            df['bb_lower'] = bollinger.bollinger_lband()
            df['bb_pct'] = bollinger.bollinger_pband()  # Percentage B
            return df
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            df['bb_upper'] = df['bb_middle'] = df['bb_lower'] = df['bb_pct'] = np.nan
            return df
    
    @staticmethod
    def add_macd(df, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL, column='close'):
        """Add MACD to dataframe"""
        try:
            macd = ta.trend.MACD(
                close=df[column], 
                window_slow=slow, 
                window_fast=fast, 
                window_sign=signal
            )
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_diff'] = macd.macd_diff()
            return df
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            df['macd'] = df['macd_signal'] = df['macd_diff'] = np.nan
            return df
    
    @staticmethod
    def add_ichimoku_cloud(df):
        """Add Ichimoku Cloud to dataframe"""
        try:
            ichimoku = ta.trend.IchimokuIndicator(
                high=df['high'],
                low=df['low'],
                window1=9,   # Tenkan-sen period
                window2=26,  # Kijun-sen period
                window3=52   # Senkou B period
            )
            df['ichimoku_a'] = ichimoku.ichimoku_a()  # Senkou Span A
            df['ichimoku_b'] = ichimoku.ichimoku_b()  # Senkou Span B
            df['ichimoku_conv'] = ichimoku.ichimoku_conversion_line()  # Tenkan-sen
            df['ichimoku_base'] = ichimoku.ichimoku_base_line()  # Kijun-sen
            
            # Calculate the cloud direction (bullish when A > B, bearish when B > A)
            df['ichimoku_cloud_bullish'] = df['ichimoku_a'] > df['ichimoku_b']
            
            return df
        except Exception as e:
            logger.error(f"Error calculating Ichimoku Cloud: {e}")
            df['ichimoku_a'] = df['ichimoku_b'] = df['ichimoku_conv'] = df['ichimoku_base'] = np.nan
            df['ichimoku_cloud_bullish'] = False
            return df
    
    @staticmethod
    def add_moving_averages(df, column='close'):
        """Add Moving Averages to dataframe"""
        try:
            # Add common moving averages
            df['sma_20'] = ta.trend.sma_indicator(df[column], window=20)
            df['sma_50'] = ta.trend.sma_indicator(df[column], window=50)
            df['sma_100'] = ta.trend.sma_indicator(df[column], window=100)
            df['sma_200'] = ta.trend.sma_indicator(df[column], window=200)
            
            # Exponential Moving Averages
            df['ema_12'] = ta.trend.ema_indicator(df[column], window=12)
            df['ema_26'] = ta.trend.ema_indicator(df[column], window=26)
            df['ema_50'] = ta.trend.ema_indicator(df[column], window=50)
            df['ema_200'] = ta.trend.ema_indicator(df[column], window=200)
            
            return df
        except Exception as e:
            logger.error(f"Error calculating Moving Averages: {e}")
            return df
    
    @staticmethod
    def add_volume_indicators(df):
        """Add Volume-based indicators to dataframe"""
        try:
            # Money Flow Index
            df['mfi'] = ta.volume.MFIIndicator(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                volume=df['volume'],
                window=14
            ).money_flow_index()
            
            # On-Balance Volume
            df['obv'] = ta.volume.OnBalanceVolumeIndicator(
                close=df['close'],
                volume=df['volume']
            ).on_balance_volume()
            
            # Volume Weighted Average Price
            df['vwap'] = (df['volume'] * df['close']).cumsum() / df['volume'].cumsum()
            
            return df
        except Exception as e:
            logger.error(f"Error calculating volume indicators: {e}")
            df['mfi'] = df['obv'] = df['vwap'] = np.nan
            return df
    
    @staticmethod
    def add_candlestick_patterns(df):
        """Add candlestick pattern recognition to dataframe"""
        try:
            # Bullish patterns
            df['bullish_engulfing'] = ta.candlestick.bullish_engulfing(
                open=df['open'], high=df['high'], low=df['low'], close=df['close']
            )
            
            df['hammer'] = ta.candlestick.hammer(
                open=df['open'], high=df['high'], low=df['low'], close=df['close']
            )
            
            df['morning_star'] = ta.candlestick.morning_star(
                open=df['open'], high=df['high'], low=df['low'], close=df['close']
            )
            
            # Bearish patterns
            df['bearish_engulfing'] = ta.candlestick.bearish_engulfing(
                open=df['open'], high=df['high'], low=df['low'], close=df['close']
            )
            
            df['shooting_star'] = ta.candlestick.shooting_star(
                open=df['open'], high=df['high'], low=df['low'], close=df['close']
            )
            
            df['evening_star'] = ta.candlestick.evening_star(
                open=df['open'], high=df['high'], low=df['low'], close=df['close']
            )
            
            return df
        except Exception as e:
            logger.error(f"Error calculating candlestick patterns: {e}")
            return df
    
    @staticmethod
    def add_all_indicators(df):
        """Add all technical indicators to dataframe"""
        df = TechnicalIndicators.add_rsi(df)
        df = TechnicalIndicators.add_bollinger_bands(df)
        df = TechnicalIndicators.add_macd(df)
        df = TechnicalIndicators.add_ichimoku_cloud(df)
        df = TechnicalIndicators.add_moving_averages(df)
        df = TechnicalIndicators.add_volume_indicators(df)
        df = TechnicalIndicators.add_candlestick_patterns(df)
        
        return df 