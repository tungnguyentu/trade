import logging
import time
from config.config import SYMBOL, QUANTITY, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, STRATEGY
from src.binance_client import BinanceFuturesClient
from src.data_processor import DataProcessor
from src.telegram_notifier import TelegramNotifier
from strategies.ma_crossover import MACrossoverStrategy
from strategies.rsi_strategy import RSIStrategy

logger = logging.getLogger("trading_bot")

class TradingBot:
    # In the __init__ method, add the debug parameter
    def __init__(self, testnet=None, paper_trading=False, debug=False):
        self.paper_trading = paper_trading
        self.debug = debug
        self.client = BinanceFuturesClient(testnet=testnet)
        self.data_processor = DataProcessor()
        self.telegram = TelegramNotifier()
        
        # Load strategy based on configuration
        if STRATEGY == 'simple_ma_crossover':
            self.strategy = MACrossoverStrategy()
        elif STRATEGY == 'rsi':
            self.strategy = RSIStrategy()
        else:
            error_msg = f"Unknown strategy: {STRATEGY}"
            logger.error(error_msg)
            self.telegram.send_error(error_msg)
            raise ValueError(error_msg)
            
        logger.info(f"Trading bot initialized with {STRATEGY} strategy")
        if paper_trading:
            logger.info("Running in paper trading mode (no real orders)")
            self.paper_balance = 1000.0  # Starting paper trading balance
            self.paper_positions = []
        
        # Track current position
        self.current_position = self._get_current_position()
        
    def _get_current_position(self):
        """Get current position size and direction"""
        if self.paper_trading:
            # In paper trading mode, use simulated positions
            position_size = 0
            for pos in self.paper_positions:
                position_size += pos['size'] if pos['direction'] == 'long' else -pos['size']
            return position_size
            
        positions = self.client.get_open_positions(SYMBOL)
        if not positions:
            return 0
            
        for position in positions:
            if position['symbol'] == SYMBOL:
                position_size = float(position['positionAmt'])
                return position_size
                
        return 0
        
    # In the fetch_and_process_data method, add debug logging
    def fetch_and_process_data(self, interval='1h', limit=100):
        """Fetch and process market data"""
        if self.debug:
            logger.debug(f"Fetching {limit} klines for {SYMBOL} at {interval} interval")
        
        klines = self.client.get_historical_klines(SYMBOL, interval, limit)
        if not klines:
            error_msg = "Failed to fetch klines data"
            logger.error(error_msg)
            self.telegram.send_error(error_msg)
            return None
            
        if self.debug:
            logger.debug(f"Successfully fetched {len(klines)} klines")
            
        df = self.data_processor.klines_to_dataframe(klines)
        df = self.data_processor.add_indicators(df)
        
        if self.debug and not df.empty:
            last_row = df.iloc[-1]
            logger.debug(f"Latest candle: Open={last_row['open']}, High={last_row['high']}, Low={last_row['low']}, Close={last_row['close']}")
            logger.debug(f"Indicators: SMA({SHORT_WINDOW})={last_row.get(f'sma_{SHORT_WINDOW}', 0):.2f}, SMA({LONG_WINDOW})={last_row.get(f'sma_{LONG_WINDOW}', 0):.2f}, RSI({RSI_PERIOD})={last_row.get(f'rsi_{RSI_PERIOD}', 0):.2f}")
        
        return df

    # In the run method, add the force_check parameter and debug logging
    def run(self, interval='1h', check_interval=3600, force_check=False):
        """Run the trading bot"""
        logger.info(f"Starting trading bot with {interval} interval, checking every {check_interval} seconds")
        
        if force_check:
            logger.info("Force check enabled - will check strategy immediately")
        
        while True:
            try:
                # Fetch and process data
                df = self.fetch_and_process_data(interval)
                if df is not None:
                    # Generate signal
                    signal = self.strategy.generate_signal(df)
                    
                    if self.debug:
                        # Get last two rows to check for crossover conditions
                        if len(df) >= 2:
                            last_two = df.tail(2)
                            logger.debug(f"Previous candle: SMA({SHORT_WINDOW})={last_two['sma_' + str(SHORT_WINDOW)].iloc[0]:.2f}, SMA({LONG_WINDOW})={last_two['sma_' + str(LONG_WINDOW)].iloc[0]:.2f}")
                            logger.debug(f"Current candle: SMA({SHORT_WINDOW})={last_two['sma_' + str(SHORT_WINDOW)].iloc[1]:.2f}, SMA({LONG_WINDOW})={last_two['sma_' + str(LONG_WINDOW)].iloc[1]:.2f}")
                            
                            # Check for crossover conditions
                            if SHORT_WINDOW and LONG_WINDOW:
                                prev_diff = last_two['sma_' + str(SHORT_WINDOW)].iloc[0] - last_two['sma_' + str(LONG_WINDOW)].iloc[0]
                                curr_diff = last_two['sma_' + str(SHORT_WINDOW)].iloc[1] - last_two['sma_' + str(LONG_WINDOW)].iloc[1]
                                
                                logger.debug(f"MA Difference: Previous={prev_diff:.2f}, Current={curr_diff:.2f}")
                                
                                if prev_diff <= 0 and curr_diff > 0:
                                    logger.debug("BULLISH CROSSOVER DETECTED (but signal may be filtered by strategy)")
                                elif prev_diff >= 0 and curr_diff < 0:
                                    logger.debug("BEARISH CROSSOVER DETECTED (but signal may be filtered by strategy)")
                    
                    logger.info(f"Strategy signal: {signal} (1=Buy, -1=Sell, 0=Hold)")
                    
                    # Send signal notification with indicators
                    if signal != 0:
                        # Get last row of dataframe for indicator values
                        last_row = df.iloc[-1]
                        indicators = {
                            f"SMA({SHORT_WINDOW})": round(last_row.get(f'sma_{SHORT_WINDOW}', 0), 2),
                            f"SMA({LONG_WINDOW})": round(last_row.get(f'sma_{LONG_WINDOW}', 0), 2),
                            f"RSI({RSI_PERIOD})": round(last_row.get(f'rsi_{RSI_PERIOD}', 0), 2),
                            "Price": round(last_row['close'], 2)
                        }
                        self.telegram.send_signal_notification(STRATEGY, SYMBOL, signal, indicators)
                    
                    # Execute trade based on signal
                    self.execute_trade(signal)
                    
                    # Update current position
                    self.current_position = self._get_current_position()
                    
                    # Log account balance
                    if self.paper_trading:
                        logger.info(f"Paper trading balance: {self.paper_balance} USDT")
                        self.telegram.send_balance_update(self.paper_balance)
                    else:
                        balance = self.client.get_account_balance()
                        if balance:
                            logger.info(f"Account balance: {balance}")
                            positions = self.client.get_open_positions(SYMBOL)
                            self.telegram.send_balance_update(balance, positions)
                    
                    # Sleep until next check
                    if not force_check:
                        logger.info(f"Sleeping for {check_interval} seconds")
                        time.sleep(check_interval)
                    else:
                        logger.info("Force check completed. Exiting.")
                        break
                    
                except Exception as e:
                    error_msg = f"Error in trading loop: {e}"
                    logger.error(error_msg)
                    self.telegram.send_error(error_msg)
                    time.sleep(60)  # Sleep for a minute before retrying