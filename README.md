# Binance Futures Trading Bot

An advanced cryptocurrency trading bot for Binance Futures, implementing Scalping and Swing Trading strategies with dynamic strategy selection based on market conditions.

## Features

- **Dual Trading Strategies**:
  - **Scalping Strategy**: Fast trades using RSI, Bollinger Bands, and short-term Moving Averages
  - **Swing Trading Strategy**: Holds trades for hours to days using Ichimoku Cloud, MACD, and volume analysis

- **Intelligent Strategy Selection**:
  - Dynamically chooses between strategies based on market volatility and trend
  - Analyzes multiple timeframes for signal confirmation

- **Advanced Risk Management**:
  - Dynamic position sizing based on risk per trade
  - Implements trailing stop-losses and take-profit targets
  - Max drawdown limits to protect capital

- **Order Execution**:
  - Full integration with Binance Futures API
  - Support for advanced order types: Market, Limit, Stop Market, Take Profit Market
  - Support for reduce-only orders and custom trigger prices (mark price or contract price)
  - Position leverage adjustment using the Binance Futures API

- **Performance Analytics**:
  - Tracks win rate, profit factor, and Sharpe ratio
  - Calculates maximum drawdown
  - Equity curve visualization

- **Real-time Notifications**:
  - Telegram alerts for trade entries, exits, and system status
  - Detailed trade reasoning in natural language

- **Multiple Operation Modes**:
  - Backtesting with historical data
  - Paper trading on Binance Futures Testnet
  - Live trading on Binance Futures

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/binance-futures-trading-bot.git
   cd binance-futures-trading-bot
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create your configuration file:
   ```bash
   cp .env.example .env
   ```

4. Edit the `.env` file with your Binance API credentials and trading parameters.

## Configuration

Edit the `.env` file to configure your trading parameters. The bot supports a wide range of configuration options:

```
# Binance API Credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Telegram Bot Settings
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Trading Parameters
RISK_PER_TRADE=0.01
MAX_DRAWDOWN=0.20
BASE_ORDER_SIZE=100  # USDT
TRADING_MODE=backtest  # backtest, paper, live

# Strategy Parameters
SCALPING_ENABLED=True
SWING_TRADING_ENABLED=True

# Markets to trade (comma-separated)
TRADING_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT

# Timeframes to analyze (comma-separated)
TIMEFRAMES=1m,5m,15m,1h,4h

# Futures-specific Parameters
DEFAULT_LEVERAGE=5
MARGIN_TYPE=ISOLATED  # ISOLATED or CROSSED
```

See the `.env.example` file for the complete list of configuration options.

## Binance Futures API Integration

This bot is built specifically for Binance Futures trading with support for:

- USDⓈ-M Futures markets
- Isolated and Cross margin modes
- Adjustable leverage settings
- Advanced order types: MARKET, LIMIT, STOP_MARKET, TAKE_PROFIT_MARKET
- Reduce-only orders for position management
- Mark price triggers for stop orders

The bot uses the official [python-binance](https://github.com/binance/binance-connector-python) library for API interaction, ensuring compatibility with the latest Binance Futures API features.

## Usage

### Backtesting

Run the bot in backtesting mode to test strategies with historical data:

```bash
python -m app.main --mode backtest --backtest-start 2023-01-01 --backtest-end 2023-12-31
```

### Paper Trading

Test the bot with real-time data on the Binance Futures Testnet:

```bash
python -m app.main --mode paper
```

### Live Trading

Run the bot in live trading mode with real money on Binance Futures:

```bash
python -m app.main --mode live
```

### Additional Options

```bash
# Specify trading symbols
python -m app.main --symbols BTCUSDT,ETHUSDT

# Specify timeframes to analyze
python -m app.main --timeframes 1m,5m,15m,1h,4h

# Change trading cycle interval (in minutes)
python -m app.main --interval 5

# Set initial balance for backtesting
python -m app.main --mode backtest --initial-balance 10000

# Set leverage
python -m app.main --leverage 3
```

## Running as a Service on Ubuntu Server

1. Create a systemd service file:

```bash
sudo nano /etc/systemd/system/trading-bot.service
```

2. Add the following configuration:

```
[Unit]
Description=Binance Futures Trading Bot
After=network.target

[Service]
User=your_username
WorkingDirectory=/path/to/binance-futures-trading-bot
ExecStart=/usr/bin/python3 -m app.main --mode paper
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:

```bash
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
```

4. Check the status:

```bash
sudo systemctl status trading-bot
```

## API Rate Limits and Error Handling

The bot includes built-in error handling for Binance API errors, including automatic retry logic for rate limit errors. It will handle API errors gracefully to prevent crashes during trading operations.

## Disclaimer

This trading bot is provided for educational and informational purposes only. Trading cryptocurrency futures involves substantial risk of loss and is not suitable for all investors. You should carefully consider whether trading is appropriate for you in light of your experience, objectives, financial resources, and risk tolerance.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 