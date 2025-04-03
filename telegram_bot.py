import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token=None, chat_id=None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.bot = None
        
        if self.token and self.chat_id:
            self.bot = Bot(token=self.token)
            logger.info("Telegram bot initialized")
        else:
            logger.warning("Telegram token or chat ID not provided. Notifications disabled.")
    
    async def send_message_async(self, message):
        """Send a message asynchronously"""
        if not self.bot:
            logger.warning("Telegram bot not initialized. Message not sent.")
            return False
        
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='Markdown')
            return True
        except TelegramError as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_message(self, message):
        """Send a message (blocking)"""
        if not self.bot:
            logger.warning("Telegram bot not initialized. Message not sent.")
            return False
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.send_message_async(message))
        loop.close()
        return result
    
    def send_trade_notification(self, symbol, side, quantity, price, trade_type="Market"):
        """Send a trade notification"""
        emoji = "🟢" if side.upper() == "BUY" else "🔴"
        message = f"{emoji} *{trade_type} {side.upper()} Order*\n"
        message += f"*Symbol:* {symbol}\n"
        message += f"*Quantity:* {quantity}\n"
        message += f"*Price:* {price}"
        
        return self.send_message(message)
    
    def send_error_notification(self, error_message):
        """Send an error notification"""
        message = f"⚠️ *Error*\n{error_message}"
        return self.send_message(message)
    
    def send_position_update(self, position):
        """Send a position update notification"""
        if position is None:
            message = "ℹ️ *Position Update*\nNo open positions"
            return self.send_message(message)
            
        direction = "LONG" if position['amount'] > 0 else "SHORT"
        emoji = "🟢" if direction == "LONG" else "🔴"
        
        message = f"{emoji} *Position Update*\n"
        message += f"*Symbol:* {position['symbol']}\n"
        message += f"*Direction:* {direction}\n"
        message += f"*Size:* {abs(position['amount'])}\n"
        message += f"*Entry Price:* {position['entry_price']}\n"
        message += f"*PnL:* {position['unrealized_profit']}"
        
        return self.send_message(message)
    
    def send_strategy_signal(self, symbol, signal_type, price, indicators=None):
        """Send a strategy signal notification"""
        if signal_type.upper() == "BUY":
            emoji = "🟢"
        elif signal_type.upper() == "SELL":
            emoji = "🔴"
        else:
            emoji = "ℹ️"
            
        message = f"{emoji} *Strategy Signal: {signal_type.upper()}*\n"
        message += f"*Symbol:* {symbol}\n"
        message += f"*Price:* {price}\n"
        
        if indicators:
            message += "\n*Indicators:*\n"
            for key, value in indicators.items():
                message += f"- {key}: {value}\n"
        
        return self.send_message(message)
    
    def send_backtest_results(self, symbol, timeframe, start_date, end_date, total_trades, win_rate, profit_loss):
        """Send backtest results notification"""
        emoji = "🟢" if profit_loss > 0 else "🔴"
        
        message = f"📊 *Backtest Results*\n"
        message += f"*Symbol:* {symbol}\n"
        message += f"*Timeframe:* {timeframe}\n"
        message += f"*Period:* {start_date} to {end_date}\n\n"
        message += f"*Total Trades:* {total_trades}\n"
        message += f"*Win Rate:* {win_rate:.2f}%\n"
        message += f"*P&L:* {emoji} {profit_loss:.2f}%"
        
        return self.send_message(message) 