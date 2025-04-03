# Binance Futures Trading Bot

A simple, customizable trading bot for Binance Futures with backtesting capabilities and Telegram notifications.

## Features

- **Test Mode**: Simulate trades without risking real money
- **Live Trading**: Execute real trades on Binance Futures
- **Backtesting**: Test your strategy against historical data
- **Strategy Optimization**: Find the best parameters for your strategy
- **Telegram Notifications**: Receive trade signals and position updates
- **Risk Management**: Automatic stop-loss and take-profit orders
- **Customizable Strategy**: Combine EMA crossover and RSI indicators

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd binance-futures-bot
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Copy the `.env.example` file to `.env` and fill in your credentials:
   ```
   cp .env.example .env
   ```

## Configuration

Edit the `.env` file with your personal settings:

```
# Binance API credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Telegram settings
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Trading settings
SYMBOL=BTCUSDT
TRADE_SIZE=0.001
TEST_MODE=True

# Strategy parameters
EMA_FAST=12
EMA_SLOW=26
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70

# Risk management
STOP_LOSS_PERCENT=2
TAKE_PROFIT_PERCENT=4
```

## Usage

### Trading Mode

Run the bot in trading mode:

```
python main.py --mode trade --interval 60
```

Options:
- `--interval`: Time in seconds between trading cycles (default: 60)

### Backtesting Mode

Run a backtest on historical data:

```
python main.py --mode backtest --symbol BTCUSDT --timeframe 1h --start-date "1 month ago UTC"
```

Options:
- `--symbol`: Trading pair (default: from .env)
- `--timeframe`: Candlestick interval (default: from config)
- `--start-date`: Start date for backtest (default: "1 month ago UTC")
- `--end-date`: End date for backtest (default: now)
- `--no-plot`: Disable generation of result plots

### Strategy Optimization

Optimize strategy parameters:

```
python main.py --mode optimize --symbol BTCUSDT --timeframe 1h --start-date "3 months ago UTC"
```

## Strategy

The bot uses a combined strategy of EMA crossover and RSI indicators:

1. **Buy Signal**: When the fast EMA crosses above the slow EMA and RSI is below 50
2. **Sell Signal**: When the fast EMA crosses below the slow EMA or RSI is above the overbought level

## Telegram Bot Setup

1. Create a Telegram bot using [BotFather](https://t.me/botfather)
2. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)
3. Add your bot token and chat ID to the `.env` file

## Directory Structure

- `data/`: Stores downloaded market data and backtest results
- `logs/`: Contains application logs
- `config.py`: Configuration settings
- `binance_client.py`: Binance API wrapper
- `indicators.py`: Technical indicators and strategy logic
- `telegram_bot.py`: Telegram notification system
- `backtest.py`: Backtesting module
- `trader.py`: Main trading logic
- `main.py`: Application entry point

## Risk Warning

Trading cryptocurrencies involves significant risk and can lead to loss of capital. Always start with small amounts in test mode before using real funds.

## License

This project is licensed under the MIT License - see the LICENSE file for details.