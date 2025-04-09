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
        
        # Add daily profit tracking
        self.daily_profit = 0.0
        self.profit_target = 10.0  # $10 daily profit target
        self.last_profit_reset = time.time()
        self.check_profit_interval = 60  # Check profit every 60 seconds
        self.last_profit_check = 0
        
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
            
        # Check if daily profit target has been reached
        if self.daily_profit >= self.profit_target:
            logger.info(f"Daily profit target of ${self.profit_target} reached (${self.daily_profit:.2f}). Skipping trade.")
            self.telegram.send_message(f"🎯 Daily profit target reached: ${self.daily_profit:.2f}. Skipping new trades until tomorrow.")
            return
            
        # Reset daily profit if a day has passed
        current_time = time.time()
        if current_time - self.last_profit_reset > 86400:  # 24 hours in seconds
            logger.info(f"Resetting daily profit from ${self.daily_profit:.2f} to $0.00")
            self.daily_profit = 0.0
            self.last_profit_reset = current_time
            
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
            # Calculate minimum quantity needed
            min_quantity = 100 / current_price
            
            # Add a 20% buffer to ensure we're well above the minimum
            min_quantity = min_quantity * 1.2
            
            # Get the precision for the symbol (usually 3 decimal places for BTC)
            precision = 3  # Default precision for BTC
            
            # Round to the appropriate precision
            adjusted_quantity = round(min_quantity, precision)
            
            # Ensure the adjusted quantity meets the minimum notional value
            while adjusted_quantity * current_price < 100:
                # If still below minimum, increase by 10%
                min_quantity = min_quantity * 1.1
                adjusted_quantity = round(min_quantity, precision)
            
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
                    pnl = self._paper_close_position(side, quantity, current_price)
                    self.daily_profit += pnl if pnl else 0
                else:
                    # Set limit price slightly better than market for faster execution
                    limit_price = current_price * 1.001 if side == 'BUY' else current_price * 0.999
                    limit_price = round(limit_price, 1)  # Round to appropriate precision
                    
                    # Close position with limit order
                    result = self.client.place_limit_order(SYMBOL, side, quantity, limit_price, reduce_only=True)
                    if result:
                        logger.info(f"Successfully placed limit order to close position: {result}")
                        
                        # Calculate PnL if available
                        pnl = None
                        positions = self.client.get_open_positions(SYMBOL)
                        if positions:
                            for pos in positions:
                                if pos['symbol'] == SYMBOL:
                                    pnl = float(pos['unrealizedProfit'])
                                    # Add to daily profit
                                    if pnl:
                                        self.daily_profit += pnl
                                        logger.info(f"Added ${pnl:.2f} to daily profit. Total: ${self.daily_profit:.2f}")
                        
                        # Send notification
                        self.telegram.send_trade_notification(side, SYMBOL, quantity, limit_price, pnl)
                        
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
                # Set limit price slightly better than market for higher chance of execution
                limit_price = current_price * 0.999 if side == 'BUY' else current_price * 1.001
                limit_price = round(limit_price, 1)  # Round to appropriate precision
                
                # Place limit order
                result = self.client.place_limit_order(SYMBOL, side, actual_quantity, limit_price)
                if result:
                    logger.info(f"Successfully placed limit order to open position: {result}")
                    self.current_position = actual_quantity if signal > 0 else -actual_quantity
                    
                    # Send notification
                    self.telegram.send_trade_notification(side, SYMBOL, actual_quantity, limit_price)
                    
                    # Set stop loss and take profit
                    stop_loss_price = current_price * (1 - STOP_LOSS_PERCENT/100) if signal > 0 else current_price * (1 + STOP_LOSS_PERCENT/100)
                    take_profit_price = current_price * (1 + TAKE_PROFIT_PERCENT/100) if signal > 0 else current_price * (1 - TAKE_PROFIT_PERCENT/100)
                    
                    # Round prices to the correct precision for the asset
                    # For BTCUSDT, price precision is typically 1 decimal place
                    price_precision = 1  # Default for BTCUSDT
                    stop_loss_price = round(stop_loss_price, price_precision)
                    take_profit_price = round(take_profit_price, price_precision)
                    
                    # Place stop loss
                    sl_result = self.client.place_stop_loss(side, actual_quantity, stop_loss_price)
                    if sl_result:
                        logger.info(f"Stop loss set at {stop_loss_price}")
                    else:
                        logger.warning(f"Failed to set stop loss at {stop_loss_price}")
                    
                    # Place take profit
                    tp_result = self.client.place_take_profit(side, actual_quantity, take_profit_price)
                    if tp_result:
                        logger.info(f"Take profit set at {take_profit_price}")
                    else:
                        logger.warning(f"Failed to set take profit at {take_profit_price}")
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
            return 0
            
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
        logger.info(f"Daily profit: ${self.daily_profit:.2f} / ${self.profit_target:.2f} target")
        
        # Send notification
        self.telegram.send_trade_notification(side, SYMBOL, quantity, price, pnl)
        
        # Clear positions
        self.paper_positions = []
        self.current_position = 0
        
        return pnl
        
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
                # Check if profit target is reached
                self.check_profit_target()
                
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

    def check_profit_target(self):
        """Check if unrealized PnL meets or exceeds profit target and close positions if needed"""
        # Skip if no position or already checked recently
        if self.current_position == 0 or (time.time() - self.last_profit_check < self.check_profit_interval):
            return
            
        self.last_profit_check = time.time()
        
        # Get current unrealized PnL
        unrealized_pnl = 0
        
        if self.paper_trading:
            if not self.paper_positions:
                return
                
            position = self.paper_positions[0]
            current_price = self.client.get_market_price(SYMBOL)
            
            if not current_price:
                return
                
            # Calculate unrealized PnL
            if position['direction'] == 'long':
                unrealized_pnl = position['size'] * (current_price - position['entry_price'])
            else:
                unrealized_pnl = position['size'] * (position['entry_price'] - current_price)
                
            # Subtract commission (0.04% for Binance futures)
            commission = position['size'] * current_price * 0.0004
            unrealized_pnl -= commission
        else:
            # Get position information from Binance
            positions = self.client.get_open_positions(SYMBOL)
            if not positions:
                return
                
            for position in positions:
                if position['symbol'] == SYMBOL:
                    # Check if unrealizedProfit exists in the position data
                    if 'unRealizedProfit' in position:
                        unrealized_pnl = float(position['unRealizedProfit'])
                    elif 'unrealizedProfit' in position:
                        unrealized_pnl = float(position['unrealizedProfit'])
                    else:
                        # If unrealizedProfit is not available, calculate it manually
                        entry_price = float(position.get('entryPrice', 0))
                        position_amt = float(position.get('positionAmt', 0))
                        current_price = self.client.get_market_price(SYMBOL)
                        
                        if entry_price > 0 and position_amt != 0 and current_price:
                            if position_amt > 0:  # Long position
                                unrealized_pnl = position_amt * (current_price - entry_price)
                            else:  # Short position
                                unrealized_pnl = abs(position_amt) * (entry_price - current_price)
                                
                            # Subtract estimated fees
                            unrealized_pnl -= abs(position_amt) * current_price * 0.0004
                    break
        
        # Log the unrealized PnL for debugging
        logger.info(f"Current unrealized PnL: ${unrealized_pnl:.2f}, Daily profit: ${self.daily_profit:.2f}")
        
        # Check if unrealized PnL plus daily profit meets or exceeds target
        total_profit = self.daily_profit + unrealized_pnl
        
        if total_profit >= self.profit_target:
            logger.info(f"Profit target reached! Unrealized PnL: ${unrealized_pnl:.2f}, Daily profit: ${self.daily_profit:.2f}, Total: ${total_profit:.2f}")
            logger.info(f"Closing position to secure profit target of ${self.profit_target:.2f}")
            
            # Close position
            side = 'SELL' if self.current_position > 0 else 'BUY'
            quantity = abs(self.current_position)
            
            if self.paper_trading:
                current_price = self.client.get_market_price(SYMBOL)
                if current_price:
                    pnl = self._paper_close_position(side, quantity, current_price)
                    self.daily_profit += pnl if pnl else 0
                    self.telegram.send_message(f"🎯 Profit target reached! Closed position with ${pnl:.2f} profit. Daily total: ${self.daily_profit:.2f}")
            else:
                current_price = self.client.get_market_price(SYMBOL)
                if not current_price:
                    return
                    
                # Use market order for immediate execution when profit target is reached
                result = self.client.place_market_order(side, quantity, reduce_only=True)
                if result:
                    logger.info(f"Successfully closed position to secure profit: {result}")
                    
                    # Add unrealized PnL to daily profit
                    self.daily_profit += unrealized_pnl
                    logger.info(f"Added ${unrealized_pnl:.2f} to daily profit. Total: ${self.daily_profit:.2f}")
                    
                    # Send notification
                    self.telegram.send_trade_notification(side, SYMBOL, quantity, current_price, unrealized_pnl)
                    self.telegram.send_message(f"🎯 Profit target reached! Closed position with ${unrealized_pnl:.2f} profit. Daily total: ${self.daily_profit:.2f}")
                    
                    self.current_position = 0
                    
                    # Cancel any open orders
                    self.client.cancel_all_orders()