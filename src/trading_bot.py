import logging
import time
from config.config import (
    SYMBOL, QUANTITY, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, 
    STRATEGY, SHORT_WINDOW, LONG_WINDOW, RSI_PERIOD, 
    RSI_OVERBOUGHT, RSI_OVERSOLD
)
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
        
    def execute_trade(self, signal):
        """Execute trade based on signal"""
        if signal == 0:
            logger.info("No trading signal")
            return
            
        current_price = self.client.get_market_price(SYMBOL)
        if not current_price:
            error_msg = "Failed to get current market price"
            logger.error(error_msg)
            self.telegram.send_error(error_msg)
            return
            
        # Calculate notional value (price × quantity)
        notional_value = current_price * QUANTITY
        
        # Check if notional value meets minimum requirement (100 USDT for Binance Futures)
        if notional_value < 100 and not self.paper_trading:
            # Calculate minimum quantity needed with a 5% buffer to ensure we're above the minimum
            min_quantity = (100 * 1.05) / current_price
            
            # Get the precision for the symbol (usually 3 decimal places for BTC)
            precision = 3  # Default precision for BTC
            
            # Round to the appropriate precision
            adjusted_quantity = round(min_quantity, precision)
            
            # Double-check that the adjusted quantity meets the minimum notional value
            adjusted_notional = adjusted_quantity * current_price
            if adjusted_notional < 100:
                # If still below minimum, increase slightly and round again
                adjusted_quantity = round((100 * 1.1) / current_price, precision)
            
            logger.info(f"Adjusting order quantity from {QUANTITY} to {adjusted_quantity} to meet minimum notional value (100 USDT)")
            logger.info(f"Estimated notional value: {adjusted_quantity * current_price:.2f} USDT")
            actual_quantity = adjusted_quantity
        else:
            actual_quantity = QUANTITY
            
        # If we have a position already
        if self.current_position != 0:
            # If signal is opposite to our position, close the position
            if (self.current_position > 0 and signal < 0) or (self.current_position < 0 and signal > 0):
                logger.info(f"Closing current position of {self.current_position} {SYMBOL}")
                
                side = 'SELL' if self.current_position > 0 else 'BUY'
                quantity = abs(self.current_position)
                
                if self.paper_trading:
                    # Simulate closing position in paper trading mode
                    self._paper_close_position(side, quantity, current_price)
                else:
                    # Close position with market order
                    result = self.client.place_market_order(side, quantity, reduce_only=True)
                    if result:
                        logger.info(f"Successfully closed position: {result}")
                        
                        # Calculate PnL if available
                        pnl = None
                        positions = self.client.get_open_positions(SYMBOL)
                        if positions:
                            for pos in positions:
                                if pos['symbol'] == SYMBOL:
                                    pnl = float(pos['unrealizedProfit'])
                        
                        # Send notification
                        self.telegram.send_trade_notification(side, SYMBOL, quantity, current_price, pnl)
                        
                        self.current_position = 0
                        
                        # Cancel any open orders
                        self.client.cancel_all_orders()
                    else:
                        error_msg = "Failed to close position"
                        logger.error(error_msg)
                        self.telegram.send_error(error_msg)
                        return
        
        # Open new position if signal is not zero
        if signal != 0:
            side = 'BUY' if signal > 0 else 'SELL'
            logger.info(f"Opening new {side} position of {actual_quantity} {SYMBOL}")
            
            if self.paper_trading:
                # Simulate opening position in paper trading mode
                self._paper_open_position(side, actual_quantity, current_price)
            else:
                # Place market order
                result = self.client.place_market_order(side, actual_quantity)
                if result:
                    logger.info(f"Successfully opened position: {result}")
                    self.current_position = actual_quantity if signal > 0 else -actual_quantity
                    
                    # Send notification
                    self.telegram.send_trade_notification(side, SYMBOL, actual_quantity, current_price)
                    
                    # Set stop loss and take profit
                    stop_loss_price = current_price * (1 - STOP_LOSS_PERCENT/100) if signal > 0 else current_price * (1 + STOP_LOSS_PERCENT/100)
                    take_profit_price = current_price * (1 + TAKE_PROFIT_PERCENT/100) if signal > 0 else current_price * (1 - TAKE_PROFIT_PERCENT/100)
                    
                    # Place stop loss
                    sl_result = self.client.place_stop_loss(side, actual_quantity, stop_loss_price)
                    if sl_result:
                        logger.info(f"Stop loss set at {stop_loss_price}")
                    
                    # Place take profit
                    tp_result = self.client.place_take_profit(side, actual_quantity, take_profit_price)
                    if tp_result:
                        logger.info(f"Take profit set at {take_profit_price}")
                else:
                    error_msg = "Failed to open position"
                    logger.error(error_msg)
                    self.telegram.send_error(error_msg)
    
    def _paper_open_position(self, side, quantity, price):
        """Simulate opening a position in paper trading mode"""
        direction = 'long' if side == 'BUY' else 'short'
        
        # Calculate stop loss and take profit levels
        if direction == 'long':
            stop_loss = price * (1 - STOP_LOSS_PERCENT/100)
            take_profit = price * (1 + TAKE_PROFIT_PERCENT/100)
        else:
            stop_loss = price * (1 + STOP_LOSS_PERCENT/100)
            take_profit = price * (1 - TAKE_PROFIT_PERCENT/100)
        
        # Create position
        position = {
            'direction': direction,
            'size': quantity,
            'entry_price': price,
            'entry_time': time.time(),
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
        
        self.paper_positions.append(position)
        self.current_position = quantity if direction == 'long' else -quantity
        
        logger.info(f"Paper trading: Opened {direction} position at {price} with SL: {stop_loss}, TP: {take_profit}")
        
        # Send notification
        self.telegram.send_trade_notification(side, SYMBOL, quantity, price)
    
    def _paper_close_position(self, side, quantity, price):
        """Simulate closing a position in paper trading mode"""
        if not self.paper_positions:
            logger.warning("No paper trading positions to close")
            return
            
        position = self.paper_positions[0]  # We only support one position at a time
        
        # Calculate PnL
        if position['direction'] == 'long':
            pnl_percent = (price / position['entry_price'] - 1) * 100
            pnl = position['size'] * (price - position['entry_price'])
        else:
            pnl_percent = (1 - price / position['entry_price']) * 100
            pnl = position['size'] * (position['entry_price'] - price)
        
        # Subtract commission (0.04% for Binance futures)
        commission = position['size'] * price * 0.0004 * 2  # Entry and exit
        pnl -= commission
        
        # Update paper balance
        self.paper_balance += pnl
        
        logger.info(f"Paper trading: Closed {position['direction']} position at {price}. PnL: {pnl:.2f} USDT ({pnl_percent:.2f}%)")
        logger.info(f"Paper trading: New balance: {self.paper_balance:.2f} USDT")
        
        # Send notification
        self.telegram.send_trade_notification(side, SYMBOL, quantity, price, pnl)
        
        # Clear positions
        self.paper_positions = []
        self.current_position = 0
        
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