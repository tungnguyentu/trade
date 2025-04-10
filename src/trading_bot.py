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
            
        # Get exchange info for the symbol to determine correct precision
        exchange_info = self.client.get_exchange_info(SYMBOL)
        if not exchange_info:
            error_msg = f"Failed to get exchange info for {SYMBOL}"
            logger.error(error_msg)
            self.telegram.send_error(error_msg)
            return
            
        # Extract precision information from exchange info
        price_precision = 0
        quantity_precision = 0
        min_qty = 0
        
        # Find price filter
        for filter in exchange_info.get('filters', []):
            if filter.get('filterType') == 'PRICE_FILTER':
                # Calculate price precision from tick size
                tick_size = filter.get('tickSize', '0.00010')
                # Convert to string first if it's a float
                if isinstance(tick_size, float):
                    tick_size = str(tick_size)
                # Calculate precision from decimal places
                if '.' in tick_size:
                    price_precision = len(tick_size.split('.')[-1])
                    # If tick size ends with zeros, adjust precision
                    price_precision = len(tick_size.rstrip('0').split('.')[-1])
                else:
                    price_precision = 0
                
            elif filter.get('filterType') == 'LOT_SIZE':
                # Get minimum quantity
                min_qty = float(filter.get('minQty', '1'))
                # Calculate quantity precision from step size
                step_size = filter.get('stepSize', '1')
                # Convert to string first if it's a float
                if isinstance(step_size, float):
                    step_size = str(step_size)
                if '.' in step_size:
                    quantity_precision = len(step_size.split('.')[-1])
                    # If step size ends with zeros, adjust precision
                    quantity_precision = len(step_size.rstrip('0').split('.')[-1])
                else:
                    quantity_precision = 0
        
        logger.info(f"Using price precision: {price_precision}, quantity precision: {quantity_precision}")
        logger.info(f"Minimum quantity: {min_qty}")
            
        current_price = self.client.get_market_price(SYMBOL)
        if not current_price:
            error_msg = "Failed to get current market price"
            logger.error(error_msg)
            self.telegram.send_error(error_msg)
            return
        
        # Get account balance to calculate optimal position size
        if self.paper_trading:
            account_balance = self.paper_balance
            available_balance = self.paper_balance
        else:
            account_data = self.client.get_account_balance()
            if not account_data:
                error_msg = "Failed to get account balance"
                logger.error(error_msg)
                self.telegram.send_error(error_msg)
                return
            
            # Extract balance values from the account data
            if isinstance(account_data, dict):
                # If we get a dictionary with balance information
                if 'wallet_balance' in account_data:
                    account_balance = float(account_data['wallet_balance'])
                    logger.info(f"Using wallet_balance as account balance: {account_balance}")
                    available_balance = float(account_data.get('available_balance', account_balance))
                elif 'balance' in account_data:
                    account_balance = float(account_data['balance'])
                    available_balance = float(account_data.get('availableBalance', account_balance))
                elif 'totalWalletBalance' in account_data:
                    account_balance = float(account_data['totalWalletBalance'])
                    available_balance = float(account_data.get('availableBalance', account_balance))
                else:
                    # Try to find any numeric value in the dictionary
                    for key, value in account_data.items():
                        if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit()):
                            account_balance = float(value)
                            logger.info(f"Using {key} as account balance: {account_balance}")
                            break
                    else:
                        logger.error(f"Could not extract balance from account data: {account_data}")
                        return
                    
                    # Try to find available balance
                    for key, value in account_data.items():
                        if 'available' in key.lower() and (isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit())):
                            available_balance = float(value)
                            logger.info(f"Using {key} as available balance: {available_balance}")
                            break
                    else:
                        available_balance = account_balance
                        logger.warning("Could not find available balance, using total balance instead")
            else:
                # If we get a direct numeric value
                account_balance = float(account_data)
                available_balance = account_balance
                logger.warning("Received direct balance value, using same value for available balance")
        
        # Calculate optimal quantity based on risk management
        # Use 2% of account balance per trade as a default risk
        risk_percentage = 0.02  # 2% risk per trade
        risk_amount = account_balance * risk_percentage
        
        # Calculate quantity based on risk amount and current price
        # For futures, consider leverage
        optimal_quantity = risk_amount / current_price
        
        # If configured quantity is provided, use it as a starting point
        if QUANTITY > 0:
            actual_quantity = QUANTITY
        else:
            # Otherwise use the calculated optimal quantity
            actual_quantity = optimal_quantity
        
        logger.info(f"Account balance: ${account_balance:.2f}, Available balance: ${available_balance:.2f}, Risk amount: ${risk_amount:.2f}")
        logger.info(f"Optimal quantity calculated: {optimal_quantity}, Using: {actual_quantity}")
        
        # Get current leverage
        leverage = self.client.get_leverage(SYMBOL)
        if not leverage and not self.paper_trading:
            logger.warning(f"Could not get leverage for {SYMBOL}, assuming default leverage of 20x")
            leverage = 20  # Updated to match your 20x leverage setting
        
        logger.info(f"Using leverage: {leverage}x")
        
        # Calculate the maximum quantity we can trade with available balance
        # For futures, the formula is: (available_balance * leverage) / current_price
        max_quantity = (available_balance * leverage) / current_price
        
        # Apply a 10% safety buffer to avoid margin issues (increased from 5%)
        max_quantity = max_quantity * 0.9
        
        # Round to appropriate precision
        max_quantity = round(max_quantity, quantity_precision)
        
        logger.info(f"Maximum possible quantity: {max_quantity} (based on available balance and {leverage}x leverage)")
        
        # If user wants to use all balance, or if actual_quantity is too large
        if QUANTITY == -1 or (not self.paper_trading and actual_quantity > max_quantity):
            logger.info(f"Adjusting quantity from {actual_quantity} to {max_quantity} to fit within available margin")
            actual_quantity = max_quantity
            
            # If max quantity is very small, try a more conservative approach
            if max_quantity < 1 and min_qty <= 1:
                logger.info("Max quantity is very small, using minimum quantity instead")
                actual_quantity = min_qty
        
        # Ensure quantity meets minimum requirement
        if actual_quantity < min_qty:
            actual_quantity = min_qty
            logger.info(f"Adjusting quantity to minimum allowed: {actual_quantity}")
        
        # Round to appropriate precision
        actual_quantity = round(actual_quantity, quantity_precision)
        
        # Calculate notional value (price × quantity)
        notional_value = current_price * actual_quantity
        
        # Check if notional value meets minimum requirement (100 USDT for Binance Futures)
        if notional_value < 100 and not self.paper_trading:
            # Calculate minimum quantity needed
            min_notional_qty = 100 / current_price
            
            # Add a 20% buffer to ensure we're well above the minimum
            min_notional_qty = min_notional_qty * 1.2
            
            # Round to the appropriate precision
            adjusted_quantity = round(min_notional_qty, quantity_precision)
            
            # Ensure the adjusted quantity meets the minimum notional value
            while adjusted_quantity * current_price < 100:
                # If still below minimum, increase by 10%
                min_notional_qty = min_notional_qty * 1.1
                adjusted_quantity = round(min_notional_qty, quantity_precision)
            
            logger.info(f"Adjusting order quantity from {actual_quantity} to {adjusted_quantity} to meet minimum notional value (100 USDT)")
            logger.info(f"Estimated notional value: {adjusted_quantity * current_price:.2f} USDT")
            actual_quantity = adjusted_quantity
        
        # Rest of the method remains the same...
            
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
                    limit_price = round(limit_price, price_precision)
                    
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
                # Set limit price with correct precision
                limit_price = current_price * 0.999 if side == 'BUY' else current_price * 1.001
                limit_price = round(limit_price, price_precision)
                
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
                    
                    # Try with progressively smaller quantities if the order fails
                    retry_quantities = [
                        actual_quantity * 0.75,  # Try with 75% of original quantity
                        actual_quantity * 0.5,   # Try with 50% of original quantity
                        actual_quantity * 0.25,  # Try with 25% of original quantity
                        min_qty                  # Finally, try with minimum quantity
                    ]
                    
                    for retry_qty in retry_quantities:
                        retry_qty = round(retry_qty, quantity_precision)
                        if retry_qty < min_qty:
                            retry_qty = min_qty
                            
                        logger.info(f"Retrying with reduced quantity: {retry_qty}")
                        retry_result = self.client.place_limit_order(SYMBOL, side, retry_qty, limit_price)
                        
                        if retry_result:
                            logger.info(f"Successfully placed limit order with reduced quantity: {retry_result}")
                            self.current_position = retry_qty if signal > 0 else -retry_qty
                            self.telegram.send_trade_notification(side, SYMBOL, retry_qty, limit_price)
                            
                            # Set stop loss and take profit for the reduced position
                            sl_result = self.client.place_stop_loss(side, retry_qty, stop_loss_price)
                            if sl_result:
                                logger.info(f"Stop loss set at {stop_loss_price}")
                            
                            tp_result = self.client.place_take_profit(side, retry_qty, take_profit_price)
                            if tp_result:
                                logger.info(f"Take profit set at {take_profit_price}")
                                
                            # Successfully placed order with reduced quantity
                            break
                    else:
                        # If all retries failed
                        self.telegram.send_error(f"Failed to open position after multiple retries. Last attempt was with quantity {min_qty}")
    
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

    def fetch_and_display_exchange_info(self):
        """Fetch and display exchange information for the trading symbol"""
        # Get exchange info for the symbol to determine correct precision
        exchange_info = self.client.get_exchange_info(SYMBOL)
        if not exchange_info:
            error_msg = f"Failed to get exchange info for {SYMBOL}"
            logger.error(error_msg)
            self.telegram.send_error(error_msg)
            return
            
        # Get price and quantity precision from exchange info
        price_precision = exchange_info.get('pricePrecision', 1)
        quantity_precision = exchange_info.get('quantityPrecision', 3)
        
        # Display filters
        filters = exchange_info.get('filters', [])
        for filter in filters:
            filter_type = filter.get('filterType', '')
            if filter_type == 'PRICE_FILTER':
                logger.info(f"Min price: {filter.get('minPrice', 'N/A')}")
                logger.info(f"Max price: {filter.get('maxPrice', 'N/A')}")
                logger.info(f"Tick size: {filter.get('tickSize', 'N/A')}")
            elif filter_type == 'LOT_SIZE':
                logger.info(f"Min qty: {filter.get('minQty', 'N/A')}")
                logger.info(f"Max qty: {filter.get('maxQty', 'N/A')}")
                logger.info(f"Step size: {filter.get('stepSize', 'N/A')}")