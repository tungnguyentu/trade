import pandas as pd
import numpy as np
from datetime import datetime
from app.utils.binance_client import BinanceClient
from app.utils.logger import get_logger
from app.indicators.technical_indicators import TechnicalIndicators

logger = get_logger()

class DataHandler:
    def __init__(self):
        self.binance_client = BinanceClient()
        self.indicator_manager = TechnicalIndicators()
        self.cached_data = {}  # Simple cache for fetched data
        
    def fetch_ohlcv_data(self, symbol, interval, limit=500, start_time=None, end_time=None):
        """
        Fetch OHLCV (Open, High, Low, Close, Volume) data from Binance
        
        Args:
            symbol (str): Trading pair symbol
            interval (str): Kline interval
            limit (int, optional): Number of candles to fetch
            start_time (str, optional): Start time in ISO format
            end_time (str, optional): End time in ISO format
            
        Returns:
            pandas.DataFrame: DataFrame with OHLCV data
        """
        try:
            klines = self.binance_client.get_klines(
                symbol=symbol,
                interval=interval,
                start_str=start_time,
                end_str=end_time,
                limit=limit
            )
            
            if not klines:
                logger.warning(f"No data returned for {symbol} {interval}")
                return pd.DataFrame()
                
            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert types
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 
                              'quote_asset_volume', 'taker_buy_base_asset_volume', 
                              'taker_buy_quote_asset_volume']
            
            df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"Fetched {len(df)} {interval} candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV data for {symbol} {interval}: {e}")
            return pd.DataFrame()
    
    def prepare_data_for_strategy(self, symbol, timeframes):
        """
        Prepare data for multiple timeframes for strategy execution
        
        Args:
            symbol (str): Trading pair symbol
            timeframes (list): List of timeframe intervals
            
        Returns:
            dict: Dictionary with timeframe as key and DataFrame as value
        """
        data = {}
        try:
            for timeframe in timeframes:
                df = self.fetch_ohlcv_data(symbol, timeframe)
                if not df.empty:
                    # Add technical indicators to the dataframe
                    try:
                        df = TechnicalIndicators.add_all_indicators(df)
                    except Exception as e:
                        logger.error(f"Error adding indicators for {symbol} {timeframe}: {e}")
                        # Continue with basic data even if indicators fail
                    
                    data[timeframe] = df
                
            return data
        except Exception as e:
            logger.error(f"Error preparing data for {symbol}: {e}")
            return data
    
    def get_latest_market_data(self, symbol):
        """
        Get the latest market data for a symbol with technical indicators
        
        Args:
            symbol (str): Trading pair symbol
            
        Returns:
            dict: Dictionary with market data and indicators
        """
        try:
            # Get the latest candle from 1m timeframe
            df = self.fetch_ohlcv_data(symbol, '1m', limit=100)
            
            if df.empty:
                logger.warning(f"No market data available for {symbol}")
                return {}
            
            # Add technical indicators
            try:
                df = TechnicalIndicators.add_all_indicators(df)
            except Exception as e:
                logger.error(f"Error adding indicators for {symbol}: {e}")
                # Continue with basic data even if indicators fail
            
            # Get the latest row
            latest = df.iloc[-1].to_dict()
            
            # Add some timestamp information
            latest['timestamp'] = df.index[-1]
            
            return latest
            
        except Exception as e:
            logger.error(f"Error getting latest market data for {symbol}: {e}")
            return {}
    
    def resample_data(self, df, timeframe):
        """
        Resample data to a higher timeframe
        
        Args:
            df (pandas.DataFrame): DataFrame with OHLCV data
            timeframe (str): Target timeframe for resampling
            
        Returns:
            pandas.DataFrame: Resampled DataFrame
        """
        try:
            # Map Binance intervals to pandas resample rules
            resample_map = {
                '1m': '1min', '3m': '3min', '5m': '5min', '15m': '15min',
                '30m': '30min', '1h': '1H', '2h': '2H', '4h': '4H',
                '6h': '6H', '8h': '8H', '12h': '12H', '1d': 'D',
                '3d': '3D', '1w': 'W', '1M': 'M'
            }
            
            if timeframe not in resample_map:
                logger.error(f"Unsupported timeframe for resampling: {timeframe}")
                return df
                
            resample_rule = resample_map[timeframe]
            
            resampled = df.resample(resample_rule).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            return resampled
        
        except Exception as e:
            logger.error(f"Error resampling data to {timeframe}: {e}")
            return df 