import pandas as pd
import numpy as np
import ta

def add_ema_indicators(df, fast_period=12, slow_period=26):
    """
    Add EMA indicators to the dataframe
    
    :param df: Price dataframe with 'close' column
    :param fast_period: Fast EMA period
    :param slow_period: Slow EMA period
    :return: DataFrame with added indicators
    """
    # Make a copy to avoid modifying the original dataframe
    df = df.copy()
    
    # Add EMAs
    df[f'ema_{fast_period}'] = ta.trend.ema_indicator(df['close'], window=fast_period)
    df[f'ema_{slow_period}'] = ta.trend.ema_indicator(df['close'], window=slow_period)
    
    # Calculate EMA crossover signal
    df['ema_cross'] = 0
    df.loc[df[f'ema_{fast_period}'] > df[f'ema_{slow_period}'], 'ema_cross'] = 1
    df.loc[df[f'ema_{fast_period}'] < df[f'ema_{slow_period}'], 'ema_cross'] = -1
    
    # Calculate crossover point (signal change)
    df['ema_cross_signal'] = df['ema_cross'].diff().fillna(0)
    
    return df

def add_rsi_indicator(df, period=14, oversold=30, overbought=70):
    """
    Add RSI indicator to the dataframe
    
    :param df: Price dataframe with 'close' column
    :param period: RSI period
    :param oversold: Oversold threshold
    :param overbought: Overbought threshold
    :return: DataFrame with added indicators
    """
    # Make a copy to avoid modifying the original dataframe
    df = df.copy()
    
    # Calculate RSI
    df[f'rsi_{period}'] = ta.momentum.rsi(df['close'], window=period)
    
    # Calculate RSI signals
    df['rsi_signal'] = 0
    df.loc[df[f'rsi_{period}'] < oversold, 'rsi_signal'] = 1  # Oversold, potential buy
    df.loc[df[f'rsi_{period}'] > overbought, 'rsi_signal'] = -1  # Overbought, potential sell
    
    return df

def add_combined_strategy(df, ema_fast=12, ema_slow=26, rsi_period=14, rsi_oversold=30, rsi_overbought=70):
    """
    Add combined EMA crossover and RSI strategy signals
    
    :param df: Price dataframe with 'close' column
    :param ema_fast: Fast EMA period
    :param ema_slow: Slow EMA period
    :param rsi_period: RSI period
    :param rsi_oversold: RSI oversold threshold
    :param rsi_overbought: RSI overbought threshold
    :return: DataFrame with added indicators and combined signals
    """
    # Add EMA indicators
    df = add_ema_indicators(df, ema_fast, ema_slow)
    
    # Add RSI indicator
    df = add_rsi_indicator(df, rsi_period, rsi_oversold, rsi_overbought)
    
    # Combine signals for entry/exit
    df['signal'] = 0
    
    # Buy signal: EMA crossover (fast crosses above slow) AND RSI was oversold
    buy_condition = (df['ema_cross_signal'] > 0) & (df[f'rsi_{rsi_period}'] < 50)
    df.loc[buy_condition, 'signal'] = 1
    
    # Sell signal: EMA crossover (fast crosses below slow) OR RSI is overbought
    sell_condition = (df['ema_cross_signal'] < 0) | (df[f'rsi_{rsi_period}'] > rsi_overbought)
    df.loc[sell_condition, 'signal'] = -1
    
    return df

def calculate_support_resistance(df, window=20):
    """
    Calculate basic support and resistance levels
    
    :param df: Price dataframe with 'high' and 'low' columns
    :param window: Look-back window for calculating support/resistance
    :return: DataFrame with support and resistance levels
    """
    df = df.copy()
    
    # Calculate rolling min/max
    df['support'] = df['low'].rolling(window=window).min()
    df['resistance'] = df['high'].rolling(window=window).max()
    
    return df 