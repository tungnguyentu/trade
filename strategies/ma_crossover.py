import logging
from config.config import SHORT_WINDOW, LONG_WINDOW

logger = logging.getLogger("ma_crossover")

class MACrossoverStrategy:
    def __init__(self, short_window=SHORT_WINDOW, long_window=LONG_WINDOW):
        self.short_window = short_window
        self.long_window = long_window
        logger.info(f"Initialized MA Crossover Strategy with windows {short_window} and {long_window}")

    def generate_signal(self, df):
        """
        Generate trading signals based on moving average crossover
        Returns: 1 for buy, -1 for sell, 0 for hold
        """
        if df is None or df.empty:
            logger.error("Empty dataframe provided to strategy")
            return 0
            
        try:
            # Get the last two rows to check for crossover
            last_two = df.tail(2)
            
            if len(last_two) < 2:
                logger.warning("Not enough data to generate signal")
                return 0
                
            # Check for bullish crossover (short MA crosses above long MA)
            if (last_two['sma_' + str(self.short_window)].iloc[0] <= last_two['sma_' + str(self.long_window)].iloc[0] and 
                last_two['sma_' + str(self.short_window)].iloc[1] > last_two['sma_' + str(self.long_window)].iloc[1]):
                logger.info("Bullish crossover detected")
                return 1
                
            # Check for bearish crossover (short MA crosses below long MA)
            elif (last_two['sma_' + str(self.short_window)].iloc[0] >= last_two['sma_' + str(self.long_window)].iloc[0] and 
                  last_two['sma_' + str(self.short_window)].iloc[1] < last_two['sma_' + str(self.long_window)].iloc[1]):
                logger.info("Bearish crossover detected")
                return -1
                
            # No crossover
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return 0