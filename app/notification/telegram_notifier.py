import telegram
import asyncio
from telegram.error import TelegramError
from datetime import datetime
from app.config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.utils.logger import get_logger

logger = get_logger()

class TelegramNotifier:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramNotifier, cls).__new__(cls)
            cls._instance._bot = None
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialize_bot()
            self._initialized = True
    
    def _initialize_bot(self):
        try:
            if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
                logger.warning("Telegram credentials not set, notifications disabled")
                self._bot = None
                return
                
            self._bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
            logger.info("Telegram bot initialized")
        except TelegramError as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self._bot = None
    
    def _send_message_sync(self, message):
        """Send message synchronously since python-telegram-bot 13.x doesn't support await"""
        if not self._bot:
            logger.warning("Telegram bot not initialized, message not sent")
            return False
            
        try:
            self._bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_message(self, message):
        """Send message to Telegram channel"""
        if not self._bot:
            return False
            
        # Use synchronous function instead of async
        return self._send_message_sync(message)
    
    def send_trade_entry(self, symbol, entry_price, quantity, strategy_type, reasoning):
        """Send trade entry notification with reasoning"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = (
            f"🚀 *NEW TRADE ENTRY* 🚀\n\n"
            f"*Symbol:* {symbol}\n"
            f"*Time:* {timestamp}\n"
            f"*Strategy:* {strategy_type}\n"
            f"*Entry Price:* {entry_price}\n"
            f"*Quantity:* {quantity}\n\n"
            f"*Reasoning:*\n{reasoning}"
        )
        
        return self.send_message(message)
    
    def send_trade_exit(self, symbol, entry_price, exit_price, quantity, pnl, pnl_percent, duration, strategy_type, reasoning):
        """Send trade exit notification with reasoning and performance"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Determine emoji based on profit/loss
        if pnl > 0:
            emoji = "✅"
        else:
            emoji = "❌"
            
        message = (
            f"{emoji} *TRADE EXIT* {emoji}\n\n"
            f"*Symbol:* {symbol}\n"
            f"*Time:* {timestamp}\n"
            f"*Strategy:* {strategy_type}\n"
            f"*Entry Price:* {entry_price}\n"
            f"*Exit Price:* {exit_price}\n"
            f"*Quantity:* {quantity}\n"
            f"*PnL:* {pnl:.2f} USDT ({pnl_percent:.2%})\n"
            f"*Duration:* {duration}\n\n"
            f"*Exit Reasoning:*\n{reasoning}"
        )
        
        return self.send_message(message)
    
    def send_error(self, error_message):
        """Send error notification"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = (
            f"⚠️ *ERROR* ⚠️\n\n"
            f"*Time:* {timestamp}\n"
            f"*Message:* {error_message}"
        )
        
        return self.send_message(message)
    
    def send_system_status(self, metrics):
        """Send system status with performance metrics"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = (
            f"📊 *SYSTEM STATUS* 📊\n\n"
            f"*Time:* {timestamp}\n"
            f"*Total Trades:* {metrics['total_trades']}\n"
            f"*Win Rate:* {metrics['win_rate']:.2%}\n"
            f"*Profit Factor:* {metrics['profit_factor']:.2f}\n"
            f"*Average Win:* {metrics['average_win']:.2f} USDT\n"
            f"*Average Loss:* {metrics['average_loss']:.2f} USDT\n"
            f"*Max Drawdown:* {metrics['max_drawdown_pct']:.2%}\n"
            f"*Sharpe Ratio:* {metrics['sharpe_ratio']:.2f}"
        )
        
        return self.send_message(message) 