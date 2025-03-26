from loguru import logger
import sys
import os
from datetime import datetime
from app.config.config import LOG_LEVEL

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logger
log_file = f"logs/trading_bot_{datetime.now().strftime('%Y%m%d')}.log"

logger.remove()  # Remove default handler
logger.add(sys.stderr, level=LOG_LEVEL)  # Add stderr handler
logger.add(log_file, rotation="00:00", level=LOG_LEVEL)  # Add file handler with daily rotation

def get_logger():
    return logger 