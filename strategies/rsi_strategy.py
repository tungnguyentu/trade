import logging
from config.config import RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD

logger = logging.getLogger("rsi_strategy")

class RSIStrategy:
    def __init__(self, period=RSI_PERIOD, overbought=RSI_OVERBOUGHT, oversold=RSI_OVERSOLD):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        logger.info(f"Initialized RSI Strategy with period {period}, overbought {overbought}, oversold {oversold}")

    def generate_signal(self, df):
        """
        Generate trading signals based on RSI
        Returns: 1 for buy, -1 for sell, 0 for hold
        """
        if df is None or df.empty:
            logger.error("Empty dataframe provided to strategy")
            return 0
            
        try:
            # Get the last two rows to check for RSI crossing
            last_two = df.tail(2)
            
            if len(last_two) < 2:
                logger.warning("Not enough data to generate signal")
                return 0
                
            # Check for oversold to normal (buy signal)
            if (last_two['rsi_' + str(self.period)].iloc[0] <= self.oversold and 
                last_two['rsi_' + str(self.period)].iloc[1] > self.oversold):
                logger.info(f"RSI crossed above oversold level ({self.oversold})")
                return 1
                
            # Check for overbought to normal (sell signal)
            elif (last_two['rsi_' + str(self.period)].iloc[0] >= self.overbought and 
                  last_two['rsi_' + str(self.period)].iloc[1] < self.overbought):
                logger.info(f"RSI crossed below overbought level ({self.overbought})")
                return -1
                
            # No crossing of thresholds
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return 0