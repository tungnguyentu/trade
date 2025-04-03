import logging
import time
import os
import pandas as pd
from datetime import datetime
import config
from binance_client import BinanceClient
from telegram_bot import TelegramNotifier
from indicators import add_combined_strategy

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(config.LOG_DIR, f"trader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BinanceFuturesTrader:
    def __init__(self):
        # Create required directories
        os.makedirs(config.LOG_DIR, exist_ok=True)
        os.makedirs(config.DATA_DIR, exist_ok=True)
        
        # Initialize components
        self.client = BinanceClient()
        self.notifier = TelegramNotifier()
        
        # Trading state
        self.symbol = config.SYMBOL
        self.position = None
        self.stop_loss_price = None
        self.take_profit_price = None
        self.test_mode = config.TEST_MODE
        
        # Log startup
        logger.info(f"Trader initialized. Symbol: {self.symbol}, Test mode: {self.test_mode}")
        
        # Send startup notification
        if self.notifier:
            mode = "TEST MODE" if self.test_mode else "LIVE MODE"
            self.notifier.send_message(f"🚀 *Binance Futures Trader Started*\n*Symbol:* {self.symbol}\n*Mode:* {mode}")
    
    def update_position(self):
        """Update current position info"""
        self.position = self.client.get_open_positions(self.symbol)
        return self.position
    
    def fetch_market_data(self, limit=100):
        """Fetch latest market data and calculate indicators"""
        df = self.client.get_historical_klines(
            symbol=self.symbol,
            interval=config.TIMEFRAME,
            limit=limit
        )
        
        if df.empty:
            logger.error("Failed to fetch market data")
            return None
        
        # Calculate indicators
        df = add_combined_strategy(
            df,
            ema_fast=config.EMA_FAST,
            ema_slow=config.EMA_SLOW,
            rsi_period=config.RSI_PERIOD,
            rsi_oversold=config.RSI_OVERSOLD,
            rsi_overbought=config.RSI_OVERBOUGHT
        )
        
        return df
    
    def calculate_risk_levels(self, entry_price, side):
        """Calculate stop loss and take profit levels"""
        if side.upper() == 'BUY':
            stop_loss = entry_price * (1 - config.STOP_LOSS_PERCENT / 100)
            take_profit = entry_price * (1 + config.TAKE_PROFIT_PERCENT / 100)
        else:  # SELL
            stop_loss = entry_price * (1 + config.STOP_LOSS_PERCENT / 100)
            take_profit = entry_price * (1 - config.TAKE_PROFIT_PERCENT / 100)
            
        return stop_loss, take_profit
    
    def check_for_entry_signals(self, df):
        """Check for entry signals from the latest data"""
        if df is None or len(df) < 2:
            return None
            
        # Get the last two rows for signal checking
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        # Current indicator values for logging/notifications
        current_indicators = {
            f"EMA_{config.EMA_FAST}": round(last_row[f'ema_{config.EMA_FAST}'], 2),
            f"EMA_{config.EMA_SLOW}": round(last_row[f'ema_{config.EMA_SLOW}'], 2),
            f"RSI_{config.RSI_PERIOD}": round(last_row[f'rsi_{config.RSI_PERIOD}'], 2)
        }
        
        # Check for buy signal: EMA crossover and RSI below 50
        if last_row['signal'] == 1 and prev_row['signal'] != 1:
            logger.info(f"BUY signal detected: {current_indicators}")
            
            # Notify about the signal
            self.notifier.send_strategy_signal(
                self.symbol,
                "BUY",
                last_row['close'],
                current_indicators
            )
            
            return "BUY"
            
        # Check for sell signal: EMA crossover or RSI overbought
        elif last_row['signal'] == -1 and prev_row['signal'] != -1:
            logger.info(f"SELL signal detected: {current_indicators}")
            
            # Notify about the signal
            self.notifier.send_strategy_signal(
                self.symbol,
                "SELL",
                last_row['close'],
                current_indicators
            )
            
            return "SELL"
            
        return None
    
    def execute_trade(self, side, price=None):
        """Execute a trade based on the signal"""
        current_price = price or self.client.get_current_price(self.symbol)
        if not current_price:
            logger.error("Could not get current price")
            return False
            
        # Calculate position size 
        account_balance = self.client.get_account_balance()
        quantity = config.TRADE_SIZE
        
        logger.info(f"Executing {side} order. Price: {current_price}, Quantity: {quantity}")
        
        # Execute market order
        order = self.client.place_market_order(self.symbol, side, quantity)
        
        if not order:
            logger.error(f"Failed to place {side} order")
            self.notifier.send_error_notification(f"Failed to place {side} order")
            return False
            
        # Calculate stop loss and take profit levels
        stop_loss, take_profit = self.calculate_risk_levels(current_price, side)
        
        # Place stop loss and take profit orders
        sl_order = self.client.place_stop_loss_order(self.symbol, side, quantity, stop_loss)
        tp_order = self.client.place_take_profit_order(self.symbol, side, quantity, take_profit)
        
        # Save the levels
        self.stop_loss_price = stop_loss
        self.take_profit_price = take_profit
        
        # Send notification
        self.notifier.send_trade_notification(
            self.symbol,
            side,
            quantity,
            current_price,
            "Market"
        )
        
        # Log the order details
        logger.info(f"Order placed: {side} {quantity} {self.symbol} at {current_price}")
        logger.info(f"Stop Loss: {stop_loss}, Take Profit: {take_profit}")
        
        return True
    
    def close_position(self):
        """Close any open position"""
        if not self.position:
            logger.info("No position to close")
            return True
            
        # Determine the side for closing
        side = "SELL" if self.position['amount'] > 0 else "BUY"
        quantity = abs(self.position['amount'])
        
        logger.info(f"Closing position: {side} {quantity} {self.symbol}")
        
        # Cancel any existing orders
        self.client.cancel_all_orders(self.symbol)
        
        # Place market order to close
        order = self.client.place_market_order(self.symbol, side, quantity)
        
        if not order:
            logger.error("Failed to close position")
            self.notifier.send_error_notification("Failed to close position")
            return False
            
        # Send notification
        current_price = self.client.get_current_price(self.symbol)
        self.notifier.send_trade_notification(
            self.symbol,
            side,
            quantity,
            current_price,
            "Position Close"
        )
        
        # Reset position
        self.position = None
        self.stop_loss_price = None
        self.take_profit_price = None
        
        return True
    
    def run_trading_cycle(self):
        """Run a single trading cycle"""
        # Update current position
        self.update_position()
        
        # Fetch latest market data
        df = self.fetch_market_data()
        
        if df is None:
            return
            
        # Check for signals
        signal = self.check_for_entry_signals(df)
        
        # Act on signals
        if signal:
            if signal == "BUY" and (self.position is None or self.position['amount'] <= 0):
                # Close any existing short position
                if self.position and self.position['amount'] < 0:
                    self.close_position()
                    
                # Enter long position
                self.execute_trade("BUY")
                
            elif signal == "SELL" and (self.position is None or self.position['amount'] >= 0):
                # Close any existing long position
                if self.position and self.position['amount'] > 0:
                    self.close_position()
                
                # Note: If you want to go short, uncomment the following:
                # self.execute_trade("SELL")
        
        # Check if we need to exit based on position
        if self.position and self.position['amount'] > 0:
            last_row = df.iloc[-1]
            
            # Exit if sell signal
            if last_row['signal'] == -1:
                logger.info("Exit signal for long position")
                self.close_position()
    
    def run(self, interval_seconds=60):
        """Main trading loop"""
        logger.info(f"Starting trading loop with {interval_seconds}s interval")
        
        try:
            while True:
                try:
                    self.run_trading_cycle()
                except Exception as e:
                    logger.error(f"Error in trading cycle: {e}")
                    self.notifier.send_error_notification(f"Trading error: {e}")
                
                # Update position status to Telegram every 10 cycles
                if int(time.time()) % (interval_seconds * 10) < interval_seconds:
                    self.update_position()
                    self.notifier.send_position_update(self.position)
                
                # Sleep until next cycle
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("Trading stopped by user")
            self.notifier.send_message("⛔ Trading stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            self.notifier.send_error_notification(f"Fatal error: {e}")
            raise
        finally:
            # Final position update
            self.update_position()
            if self.position:
                self.notifier.send_position_update(self.position)
            
            logger.info("Trading stopped")
            self.notifier.send_message("⛔ Trading stopped") 