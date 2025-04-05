import pandas as pd
import numpy as np
import ta
import logging

logger = logging.getLogger("data_processor")

class DataProcessor:
    @staticmethod
    def klines_to_dataframe(klines):
        """Convert Binance klines to pandas DataFrame"""
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                   'close_time', 'quote_asset_volume', 'number_of_trades', 
                   'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
        
        df = pd.DataFrame(klines, columns=columns)
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Convert string values to float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        # Set timestamp as index
        df.set_index('timestamp', inplace=True)
        
        return df

    @staticmethod
    def add_indicators(df):
        """Add technical indicators to DataFrame"""
        try:
            # Moving Averages
            df['sma_9'] = ta.trend.sma_indicator(df['close'], window=9)
            df['sma_21'] = ta.trend.sma_indicator(df['close'], window=21)
            df['ema_9'] = ta.trend.ema_indicator(df['close'], window=9)
            df['ema_21'] = ta.trend.ema_indicator(df['close'], window=21)
            
            # RSI
            df['rsi_14'] = ta.momentum.rsi(df['close'], window=14)
            
            # MACD
            macd = ta.trend.MACD(df['close'])
            df['macd_line'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_histogram'] = macd.macd_diff()
            
            # Bollinger Bands
            bollinger = ta.volatility.BollingerBands(df['close'])
            df['bollinger_upper'] = bollinger.bollinger_hband()
            df['bollinger_lower'] = bollinger.bollinger_lband()
            df['bollinger_middle'] = bollinger.bollinger_mavg()
            
            # ATR (Average True Range)
            df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'])
            
            return df
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            return df