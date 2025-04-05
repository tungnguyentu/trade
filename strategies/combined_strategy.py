import logging
from config.config import SHORT_WINDOW, LONG_WINDOW, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD

logger = logging.getLogger("combined_strategy")

class CombinedStrategy:
    def __init__(self, short_window=SHORT_WINDOW, long_window=LONG_WINDOW, 
                 rsi_period=RSI_PERIOD, rsi_overbought=RSI_OVERBOUGHT, rsi_oversold=RSI_OVERSOLD):
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        logger.info(f"Initialized Combined Strategy with MA windows {short_window}/{long_window} and RSI {rsi_period}/{rsi_overbought}/{rsi_oversold}")

    def generate_signal(self, df):
        """
        Generate trading signals based on both MA crossover and RSI
        Returns: 1 for buy, -1 for sell, 0 for hold
        """
        if df is None or df.empty:
            logger.error("Empty dataframe provided to strategy")
            return 0
            
        try:
            # Get the last two rows to check for crossover and RSI
            last_two = df.tail(2)
            
            if len(last_two) < 2:
                logger.warning("Not enough data to generate signal")
                return 0
                
            # Check MA crossover
            ma_signal = 0
            
            # Check for bullish crossover (short MA crosses above long MA)
            if (last_two['sma_' + str(self.short_window)].iloc[0] <= last_two['sma_' + str(self.long_window)].iloc[0] and 
                last_two['sma_' + str(self.short_window)].iloc[1] > last_two['sma_' + str(self.long_window)].iloc[1]):
                ma_signal = 1
                
            # Check for bearish crossover (short MA crosses below long MA)
            elif (last_two['sma_' + str(self.short_window)].iloc[0] >= last_two['sma_' + str(self.long_window)].iloc[0] and 
                  last_two['sma_' + str(self.short_window)].iloc[1] < last_two['sma_' + str(self.long_window)].iloc[1]):
                ma_signal = -1
            
            # Check RSI
            rsi_signal = 0
            
            # Check for oversold to normal (buy signal)
            if (last_two['rsi_' + str(self.rsi_period)].iloc[0] <= self.rsi_oversold and 
                last_two['rsi_' + str(self.rsi_period)].iloc[1] > self.rsi_oversold):
                rsi_signal = 1
                
            # Check for overbought to normal (sell signal)
            elif (last_two['rsi_' + str(self.rsi_period)].iloc[0] >= self.rsi_overbought and 
                  last_two['rsi_' + str(self.rsi_period)].iloc[1] < self.rsi_overbought):
                rsi_signal = -1
            
            # Combine signals - only generate a signal if both agree or one is neutral
            if ma_signal == 1 and rsi_signal >= 0:
                logger.info("Bullish MA crossover with neutral/bullish RSI")
                return 1
            elif ma_signal == -1 and rsi_signal <= 0:
                logger.info("Bearish MA crossover with neutral/bearish RSI")
                return -1
            elif ma_signal == 0 and rsi_signal != 0:
                logger.info(f"RSI signal: {rsi_signal} with neutral MA")
                return rsi_signal
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return 0