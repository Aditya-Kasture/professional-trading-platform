# Professional Trading Platform v3.0

A comprehensive, professional-grade trading platform built with PyQt6 and Interactive Brokers API integration. Features a TWS-style interface with real-time market data, advanced charting, portfolio management, and automated trading capabilities.

## 🚀 Features

### Core Trading Features
- **Real-time Market Data**: Live quotes with bid/ask spreads and Level II data
- **Advanced Order Management**: Market, limit, stop, and bracket orders
- **Portfolio Tracking**: Real-time P&L analysis and position monitoring
- **Multi-Symbol Watchlist**: Customizable watchlist with real-time updates
- **Professional Charting**: Candlestick charts with technical indicators (SMA, RSI, Volume)

### Platform Capabilities
- **Interactive Brokers Integration**: Full TWS API connectivity
- **Paper Trading Mode**: Yahoo Finance fallback for demo trading
- **Stock Screener**: Embedded Finviz Elite integration
- **News Feed**: Real-time financial news with TWS news providers
- **Multiple Client IDs**: Support for multiple TWS connections
- **Professional UI**: TWS-style dark theme interface

### Technical Indicators
- Simple Moving Averages (SMA 20, SMA 50)
- Relative Strength Index (RSI)
- Volume analysis
- Multiple timeframes (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk, 1mo)

## 📋 Requirements

### System Requirements
- Python 3.8+
- Windows 10/11, macOS 10.15+, or Linux
- 4GB RAM minimum, 8GB recommended
- Internet connection for market data

### Trading Requirements
- Interactive Brokers account (for live trading)
- TWS (Trader Workstation) or IB Gateway
- API permissions enabled in TWS

## 🛠️ Installation

### 1. Clone the Repository
git clone https://github.com/yourusername/professional-trading-platform.git

cd professional-trading-platform


### 2. Create Virtual Environment
python -m venv venv

### Windows
venv\Scripts\activate

### MacOS/Linux
source venv/bin/activate


### 3. Install Dependencies
pip install -r requirements.txt


### 4. Configure Interactive Brokers (Optional)
1. Install TWS or IB Gateway
2. Enable API connections in TWS:
   - Go to File > Global Configuration > API > Settings
   - Enable "Enable ActiveX and Socket Clients"
   - Add your IP address to trusted IPs
   - Note the Socket Port (default: 7497 for live, 7496 for paper)

## 🚀 Quick Start

### Basic Usage
python trading_platform.py


### TWS Connection
1. Start TWS or IB Gateway
2. In the platform: Connection > Connect to TWS
3. Enter connection details:
   - Host: 127.0.0.1 (localhost)
   - Port: 7496 (paper) or 7497 (live)
   - Client ID: 1 (unique identifier)

### Demo Mode
The platform works without TWS connection using Yahoo Finance data for paper trading and strategy development.

## 📊 Usage Guide

### Watchlist Management
- Add symbols using the input field in the watchlist panel
- Click on any symbol to select it for trading and charting
- Remove symbols by selecting them and clicking "Remove"

### Chart Analysis
- Select timeframes from 1 minute to 1 month
- Toggle technical indicators in chart settings
- Professional candlestick display with volume analysis

### Order Management
1. Select a symbol from the watchlist
2. Choose order type (Market, Limit, Stop, Bracket)
3. Set quantity and price parameters
4. Click "Place Order" to submit

### Portfolio Monitoring
- Real-time position tracking
- P&L analysis with percentage changes
- Account summary with buying power and cash balance

## 🔧 Configuration

### TWS Settings
Default connection parameters
HOST = "127.0.0.1"
PAPER_PORT = 7496
LIVE_PORT = 7497
CLIENT_ID = 1


### Customization
- Modify watchlist symbols in the `AdvancedWatchlistWidget` class
- Adjust update intervals in `DataUpdateWorker`
- Customize chart indicators in `ProfessionalTradingChart`

## 🔌 API Reference

### Key Classes
- `EnhancedIBKRConnection`: Handles TWS connectivity and order management
- `ProfessionalTradingChart`: Advanced charting with technical indicators
- `ProfessionalTradingPanel`: Order entry and market data display
- `EnhancedPortfolioWidget`: Portfolio and position tracking

### Market Data Methods
Get real-time quotes
data = ibkr_connection.get_real_time_data(symbol)

Place orders
success, order_id = ibkr_connection.place_order(
symbol="AAPL",
action="BUY",
quantity=100,
order_type="MKT"
)

## 📈 Screenshots

### Main Interface
- Professional TWS-style layout
- Real-time market data display
- Advanced order entry panel

### Chart Analysis
- Multiple timeframes
- Technical indicators
- Professional candlestick charts

### Portfolio Management
- Position tracking
- P&L analysis
- Account summary

## ⚠️ Disclaimer

**IMPORTANT TRADING DISCLAIMER:**

This software is provided for educational and informational purposes only. Trading stocks, options, and other financial instruments involves significant risk and may not be suitable for all investors. 

**Key Risks:**
- You may lose some or all of your invested capital
- Past performance does not guarantee future results
- Market conditions can change rapidly
- Software bugs or connectivity issues may affect trading

**Usage Terms:**
- Use at your own risk
- Test thoroughly with paper trading before live trading
- The authors assume no responsibility for trading losses
- Always verify orders before submission
- Keep position sizes appropriate to your risk tolerance

**Regulatory Notice:**
- Ensure compliance with local financial regulations
- Interactive Brokers account required for live trading
- Some features may require market data subscriptions

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Submit a pull request with detailed description

### Code Style
- Follow PEP 8 conventions
- Add docstrings for all methods
- Include error handling for trading operations
- Test with both paper and live accounts (carefully)

### Testing
- Always test new features in paper trading mode
- Verify TWS connectivity edge cases
- Test order management functionality
- Validate chart and data accuracy

## 🙏 Acknowledgments

- **Interactive Brokers** for their comprehensive trading API
- **ib_insync** library for Python TWS integration
- **PyQt6** for the professional GUI framework
- **Yahoo Finance** for market data fallback
- **Finviz** for stock screening capabilities

## 📞 Support

### Documentation
- [Interactive Brokers API Guide](https://interactivebrokers.github.io/tws-api/)
- [ib_insync Documentation](https://ib-insync.readthedocs.io/)
- [PyQt6 Documentation](https://doc.qt.io/qtforpython/)

### Common Issues
- **Connection Failed**: Verify TWS is running and API is enabled
- **Import Errors**: Ensure all requirements are installed
- **Chart Not Updating**: Check internet connection and symbol validity
- **Orders Not Executing**: Verify account permissions and buying power

### Getting Help
- Check the [Issues](https://github.com/yourusername/professional-trading-platform/issues) page
- Review the documentation and code comments
- Test in paper trading mode first


### Future Enhancements
- Options trading support
- Advanced technical analysis tools
- Strategy backtesting framework
- Multi-account management
- Mobile companion app

---

**⚡ Happy Trading! Remember to always trade responsibly and never risk more than you can afford to lose.**


