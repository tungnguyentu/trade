import logging
import requests
import os
from config.config import TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("telegram_notifier")

class TelegramNotifier:
    def __init__(self):
        self.enabled = TELEGRAM_ENABLED
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        
        if self.enabled:
            if not self.token or not self.chat_id:
                logger.error("Telegram notifications enabled but missing token or chat ID")
                self.enabled = False
            else:
                logger.info("Telegram notifications initialized")
                self.send_message("🤖 Trading Bot started")
        else:
            logger.info("Telegram notifications disabled")
    
    def send_message(self, message):
        """Send a message to the Telegram chat"""
        if not self.enabled:
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                logger.debug(f"Telegram message sent: {message}")
                return True
            else:
                logger.error(f"Failed to send Telegram message: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_trade_notification(self, action, symbol, quantity, price, pnl=None):
        """Send a notification about a trade"""
        emoji = "🟢" if action == "BUY" else "🔴"
        
        message = f"{emoji} *{action}* {quantity} {symbol} @ {price}"
        
        if pnl is not None:
            emoji = "✅" if pnl > 0 else "❌"
            message += f"\n{emoji} PnL: {pnl:.2f} USDT"
            
        return self.send_message(message)
    
    def send_signal_notification(self, strategy, symbol, signal, indicators=None):
        """Send a notification about a trading signal"""
        signal_text = "BUY" if signal > 0 else "SELL" if signal < 0 else "NEUTRAL"
        emoji = "🟢" if signal > 0 else "🔴" if signal < 0 else "⚪"
        
        message = f"{emoji} *{strategy}* Signal: {signal_text} on {symbol}"
        
        if indicators:
            message += "\n\n*Indicators:*"
            for name, value in indicators.items():
                message += f"\n• {name}: {value}"
                
        return self.send_message(message)
    
    def send_balance_update(self, balance, positions=None):
        """Send a notification with account balance and positions"""
        message = f"💰 *Account Balance*\n"
        
        if isinstance(balance, dict):
            message += f"• Wallet Balance: {balance.get('wallet_balance', 0):.2f} USDT\n"
            message += f"• Unrealized PnL: {balance.get('unrealized_pnl', 0):.2f} USDT\n"
            message += f"• Available Balance: {balance.get('available_balance', 0):.2f} USDT"
        else:
            message += f"• Balance: {balance:.2f} USDT"
            
        if positions:
            message += "\n\n*Open Positions:*\n"
            for pos in positions:
                symbol = pos.get('symbol', 'UNKNOWN')
                size = float(pos.get('positionAmt', 0))
                entry_price = float(pos.get('entryPrice', 0))
                pnl = float(pos.get('unrealizedProfit', 0))
                
                if size != 0:
                    direction = "LONG" if size > 0 else "SHORT"
                    emoji = "🟢" if size > 0 else "🔴"
                    pnl_emoji = "✅" if pnl > 0 else "❌"
                    
                    message += f"{emoji} {direction} {abs(size)} {symbol} @ {entry_price}\n"
                    message += f"{pnl_emoji} PnL: {pnl:.2f} USDT\n"
        
        return self.send_message(message)
    
    def send_error(self, error_message):
        """Send an error notification"""
        message = f"⚠️ *ERROR*\n{error_message}"
        return self.send_message(message)