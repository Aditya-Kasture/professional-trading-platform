import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API*")
import sys
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QTabWidget, QLabel, QPushButton, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QSplitter, QScrollArea, QProgressBar,
    QStatusBar, QMenuBar, QMessageBox, QDialog, QFormLayout, QSlider,
    QFrame, QHeaderView, QListWidget, QListWidgetItem, QButtonGroup
)
from PyQt6.QtCore import (
    QTimer, QThread, pyqtSignal, Qt, QMutex, QWaitCondition, QSize, QUrl
)
from PyQt6.QtGui import QFont, QColor, QPalette, QAction, QPainter, QBrush, QPen
import os
import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
from ib_insync import *
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import mplfinance as mpf
import feedparser
import requests
from bs4 import BeautifulSoup
import seaborn as sns
import nest_asyncio
from math import isnan
import webbrowser
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
from dateutil import parser as date_parser

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Set matplotlib to use Qt backend
plt.switch_backend('Qt5Agg')

from math import isnan

# Explicit imports for IB, Stock, Order, Contract
from ib_insync import IB, Stock, Order, Contract, Trade, Fill, NewsProvider, NewsTick

class EnhancedIBKRConnection:
    """Enhanced IBKR connection with full trading functionality and improved data handling"""
    
    def __init__(self):
        self.ib = None
        self.connected = False
        self.next_order_id = 1
        self.orders = {}
        self.news_headlines = []
        self.news_providers = []
        self.news_subscriptions = {}

        self.load_trade_history()
    
    def save_trade_history(self):
        """Save trade history to file"""
        try:
            import json
            trade_data = {
                'trades': getattr(self, 'trades_history', []),
                'positions': getattr(self, 'positions', {})
            }
            with open('trade_history.json', 'w') as f:
                json.dump(trade_data, f, default=str, indent=2)
            print(f"[TRADES] Saved {len(trade_data['trades'])} trades to history")
        except Exception as e:
            print(f"Error saving trade history: {e}")
    
    def on_execution(self, trade, fill):
        """Handle order executions and save to history"""
        order_id = trade.order.orderId
        print(f"Order {order_id} executed: {fill.shares} shares at ${fill.price}")
        
        # Save to trades history
        trade_record = {
            'symbol': trade.contract.symbol,
            'side': 'BUY' if fill.shares > 0 else 'SELL',
            'quantity': abs(fill.shares),
            'shares': fill.shares,
            'price': fill.price,
            'commission': fill.commissionReport.commission if fill.commissionReport else 0.0,
            'time': fill.time.strftime('%Y-%m-%d %H:%M:%S') if fill.time else '',
            'timestamp': str(fill.time) if fill.time else '',
            'pnl': 0.0  # Will be calculated later
        }
        
        if not hasattr(self, 'trades_history'):
            self.trades_history = []
            
        if hasattr(self, 'portfolio_widget'):
            # Update portfolio widget with new trade
            self.portfolio_widget.on_connection_status_changed(True)
        
        self.trades_history.append(trade_record)
        self.save_trade_history()

    
    def load_trade_history(self):
        """Load trade history from file"""
        try:
            import json
            import os
            if os.path.exists('trade_history.json'):
                with open('trade_history.json', 'r') as f:
                    data = json.load(f)
                    self.trades_history = data.get('trades', [])
                    self.positions = data.get('positions', {})
                    print(f"Loaded {len(self.trades_history)} historical trades")
        except Exception as e:
            print(f"Error loading trade history: {e}")
            self.trades_history = []
            self.positions = {}
        
    def connect(self, host="127.0.0.1", port=7496, client_id=1):
        """Connect to TWS/Gateway with enhanced error handling"""
        try:
            if self.ib:
                try:
                    self.ib.disconnect()
                except:
                    pass
            
            self.ib = IB()
            
            # Add connection timeout and retry logic
            print(f"Attempting to connect to TWS at {host}:{port} with client ID {client_id}")
            self.ib.connect(host, port, clientId=client_id, timeout=20)
            
            if self.ib.isConnected():
                self.connected = True
                self.next_order_id = self.ib.client.getReqId()
                
                # Set up event handlers
                self.ib.orderStatusEvent += self.on_order_status
                self.ib.execDetailsEvent += self.on_execution
                self.ib.tickNewsEvent += self.on_news_tick
                
                # Test the connection with a simple request
                try:
                    account_summary = self.ib.accountSummary()
                    print(f"Connection test successful - Found {len(account_summary)} account values")
                except Exception as test_e:
                    print(f"Connection test warning: {test_e}")
                
                self._setup_news_feeds()
                
                print(f"Successfully connected to TWS at {host}:{port}")
                return True
            else:
                print("Failed to connect to TWS")
                return False
                
        except Exception as e:
            print(f"Connection error: {e}")
            import traceback
            traceback.print_exc()
            self.connected = False
            return False

    
    def disconnect(self):
        """Disconnect from TWS"""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
            self.connected = False
            print("Disconnected from TWS")
        except Exception as e:
            print(f"Disconnect error: {e}")
    
    
    def get_real_time_data(self, symbol: str) -> Dict:
        """Force Yahoo Finance quotes for the UI regardless of TWS connection."""
        print(f"[DATA MODE] Yahoo-only quotes for {symbol} (ignoring TWS)")
        return self.get_fallback_data(symbol)


    def get_fallback_data(self, symbol: str) -> Dict:
        """Fallback to Yahoo Finance for demo/paper trading"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")
            
            if not data.empty:
                last_price = float(data['Close'].iloc[-1])
                prev_close = float(data['Open'].iloc[0])
                change = last_price - prev_close
                percent_change = (change / prev_close * 100) if prev_close else 0
                volume = int(data['Volume'].sum())
                
                print(f"[YAHOO] Got data for {symbol}: Last=${last_price:.2f}, Change={change:+.2f}")
                
                return {
                    'symbol': symbol,
                    'last': last_price,
                    'bid': last_price * 0.999,
                    'ask': last_price * 1.001,
                    'volume': volume,
                    'change': change,
                    'percent_change': percent_change,
                    'source': 'Yahoo Finance (Demo)'
                }
        except Exception as e:
            print(f"Fallback data error for {symbol}: {e}")
        
        # Final fallback - return mock data instead of None
        return self.get_mock_data(symbol)


    def get_mock_data(self, symbol: str) -> Dict:
        """Generate realistic mock data for development"""
        import random
        base_price = {
            'AAPL': 175, 'GOOGL': 135, 'TSLA': 250, 'AMZN': 145, 
            'MSFT': 415, 'NVDA': 430, 'META': 485, 'SPY': 450, 
            'QQQ': 380, 'AMD': 140
        }.get(symbol, 100)
        
        last_price = base_price + random.uniform(-5, 5)
        change = random.uniform(-3, 3)
        
        return {
            'symbol': symbol,
            'last': round(last_price, 2),
            'bid': round(last_price * 0.999, 2),
            'ask': round(last_price * 1.001, 2),
            'volume': random.randint(1000000, 50000000),
            'change': round(change, 2),
            'percent_change': round((change / last_price * 100), 2),
            'source': 'Mock Data (Development)'
        }
    
    def place_order(self, symbol: str, action: str, quantity: int, order_type: str, **kwargs) -> tuple:
        """Place order with enhanced error handling"""
        if not self.connected or self.ib is None or not self.ib.isConnected():
            return False, "Not connected to TWS"
            
        try:
            contract = Stock(symbol, "SMART", "USD")
            qualified_contracts = self.ib.qualifyContracts(contract)
            if not qualified_contracts:
                return False, "Could not qualify contract"
                
            contract = qualified_contracts[0]
            order = Order()
            order.orderId = self.next_order_id
            self.next_order_id += 1
            order.action = action.upper()
            order.totalQuantity = quantity
            order.orderType = order_type
            order.tif = kwargs.get('tif', 'DAY')
            
            if order_type in ['LMT', 'STP LMT']:
                order.lmtPrice = kwargs.get('limit_price', 0.0)
            if order_type in ['STP', 'STP LMT']:
                order.auxPrice = kwargs.get('stop_price', 0.0)
            
            trade = self.ib.placeOrder(contract, order)
            if trade:
                self.orders[order.orderId] = {
                    'symbol': symbol,
                    'action': action,
                    'quantity': quantity,
                    'order_type': order_type,
                    'status': 'Submitted',
                    'trade': trade
                }
                print(f"Order placed: {action} {quantity} {symbol} ({order_type}) - Order ID: {order.orderId}")
                return True, str(order.orderId)
            else:
                return False, "Failed to place order"
        except Exception as e:
            print(f"Order error: {e}")
            return False, str(e)
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders"""
        if not self.connected or self.ib is None or not self.ib.isConnected():
            return False
        try:
            self.ib.reqGlobalCancel()
            print("Requested cancellation of all orders")
            return True
        except Exception as e:
            print(f"Error cancelling orders: {e}")
            return False
    
    def get_portfolio_data(self) -> Dict:
        """Get portfolio data with fallback to mock data"""
        if not self.connected or self.ib is None or not self.ib.isConnected():
            print("[PORTFOLIO] Not connected, using mock data")
            return self.get_mock_portfolio_data()
            
        try:
            account_values = self.ib.accountSummary()
            portfolio_items = self.ib.portfolio()
            print(f"[PORTFOLIO] Found {len(portfolio_items)} portfolio items")
            
            total_value = 0.0
            cash_balance = 0.0
            buying_power = 0.0
            account_summary = {}
            
            for item in account_values:
                if item.tag == 'NetLiquidation':
                    total_value = float(item.value)
                elif item.tag == 'TotalCashValue':
                    cash_balance = float(item.value)
                elif item.tag == 'BuyingPower':
                    buying_power = float(item.value)
                
                try:
                    account_summary[item.tag] = float(item.value)
                except Exception:
                    account_summary[item.tag] = item.value
            
            positions = []
            for item in portfolio_items:
                if item.position != 0:
                    market_value = float(item.marketValue)
                    unrealized_pnl = float(item.unrealizedPNL)
                    avg_cost = float(item.averageCost)
                    current_price = float(item.marketPrice)
                    pnl_pct = (unrealized_pnl / abs(market_value - unrealized_pnl) * 100) if market_value != unrealized_pnl else 0.0
                    
                    positions.append({
                        'symbol': item.contract.symbol,
                        'quantity': int(item.position),
                        'avg_cost': avg_cost,
                        'current_price': current_price,
                        'market_value': market_value,
                        'pnl': unrealized_pnl,
                        'pnl_pct': pnl_pct
                    })
            
            return {
                'total_value': total_value,
                'day_change': 0.0,
                'day_change_pct': 0.0,
                'cash_balance': cash_balance,
                'buying_power': buying_power,
                'positions': positions,
                'account_summary': account_summary
            }
        except Exception as e:
            print(f"Error getting portfolio data: {e}")
            return self.get_mock_portfolio_data()
    
    def get_mock_portfolio_data(self):
        """Return enhanced mock portfolio data when not connected"""
        return {
            'total_value': 125450.00,
            'day_change': 2340.50,
            'day_change_pct': 1.90,
            'cash_balance': 15230.00,
            'buying_power': 45690.00,
            'positions': [
                {
                    "symbol": "AAPL", 
                    "quantity": 100, 
                    "avg_cost": 150.00, 
                    "current_price": 175.43, 
                    "market_value": 17543.00, 
                    "pnl": 2543.00, 
                    "pnl_pct": 16.95
                },
                {
                    "symbol": "TSLA", 
                    "quantity": 50, 
                    "avg_cost": 220.00, 
                    "current_price": 248.50, 
                    "market_value": 12425.00, 
                    "pnl": 1425.00, 
                    "pnl_pct": 12.95
                },
                {
                    "symbol": "NVDA", 
                    "quantity": 25, 
                    "avg_cost": 380.00, 
                    "current_price": 432.10, 
                    "market_value": 10802.50, 
                    "pnl": 1302.50, 
                    "pnl_pct": 13.71
                },
                {
                    "symbol": "META", 
                    "quantity": -30, 
                    "avg_cost": 485.00, 
                    "current_price": 475.20, 
                    "market_value": -14256.00, 
                    "pnl": 294.00, 
                    "pnl_pct": 2.02
                },
            ],
            'account_summary': {
                'NetLiquidation': 125450.00,
                'TotalCashValue': 15230.00,
                'BuyingPower': 45690.00,
                'UnrealizedPnL': 5564.50,
                'RealizedPnL': 1250.00,
            }
        }

    
    def on_order_status(self, trade):
        """Handle order status updates"""
        order_id = trade.order.orderId
        status = trade.orderStatus.status
        
        if order_id in self.orders:
            self.orders[order_id]['status'] = status
            print(f"Order {order_id} status: {status}")
    
    def on_execution(self, trade, fill):
        """Handle order executions"""
        order_id = trade.order.orderId
        print(f"Order {order_id} executed: {fill.shares} shares at ${fill.price}")

    def get_open_orders(self):
        """Get current open orders"""
        if self.connected and self.ib:
            return self.ib.openOrders()
        return []

    def get_executions(self):
        """Get recent executions"""
        if self.connected and self.ib:
            return self.ib.executions()
        return []

    def _setup_news_feeds(self):
        """Setup TWS news feeds"""
        try:
            if self.ib is not None and self.ib.isConnected():
                providers = self.ib.reqNewsProviders()
                self.news_providers = providers
                for provider in self.news_providers:
                    news_contract = Contract()
                    news_contract.symbol = f"{provider.code}:{provider.code}_ALL"
                    news_contract.secType = "NEWS"
                    news_contract.exchange = provider.code
                    self.ib.reqMktData(news_contract, "mdoff,292", False, False)
                    self.news_subscriptions[provider.code] = news_contract
                print(f"Subscribed to {len(self.news_providers)} news providers")
        except Exception as e:
            print(f"Error setting up news feeds: {e}")

    def on_news_tick(self, reqId, timeStamp, providerCode, articleId, headline, extraData=None):
        """Handle news tick events"""
        print(f"News tick received: provider={providerCode}, headline={headline}")
        provider_name = next((p.name for p in self.news_providers if p.code == providerCode), providerCode)
        news_item = {
            'reqId': reqId,
            'timestamp': datetime.fromtimestamp(timeStamp),
            'provider': provider_name,
            'provider_code': providerCode,
            'articleId': articleId,
            'headline': headline,
            'received_at': datetime.now(),
        }
        self.news_headlines.append(news_item)
        if len(self.news_headlines) > 200:
            self.news_headlines = self.news_headlines[-200:]

    def get_tws_news(self, symbol=None):
        """Get TWS news headlines"""
        filtered = self.news_headlines[-200:]
        if symbol:
            symbol = symbol.upper()
            filtered = [n for n in filtered if symbol in n.get('headline', '').upper()]
        return sorted(filtered, key=lambda x: x['received_at'], reverse=True)

class ProfessionalTradingChart(FigureCanvas):
    """Professional TWS-style trading chart with multiple timeframes"""
    
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(12, 8), facecolor='#0d1421')
        super().__init__(self.figure)
        self.setParent(parent)
        self.symbol = None
        self.timeframe = "1d"
        self.period = "6mo"
        self.indicators = ['SMA20', 'SMA50', 'Volume', 'RSI']
        
    def update_chart(self, symbol: str, timeframe: str = "1d", period: str = "6mo"):
        """Update chart with professional candlestick display and indicators"""
        self.symbol = symbol
        self.timeframe = timeframe
        self.period = period
        
        try:
            self.figure.clear()
            
            # Get data with proper date handling
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=timeframe)
            
            if df.empty:
                return
            
            # Create subplots: Price (main), Volume, RSI
            gs = self.figure.add_gridspec(4, 1, height_ratios=[3, 1, 1, 0.5], hspace=0.1)
            ax_price = self.figure.add_subplot(gs[0])
            ax_volume = self.figure.add_subplot(gs[1], sharex=ax_price)
            ax_rsi = self.figure.add_subplot(gs[2], sharex=ax_price)
            
            # Plot candlesticks
            self._plot_professional_candlesticks(ax_price, df)
            
            # Add moving averages
            if 'SMA20' in self.indicators and len(df) >= 20:
                sma20 = df['Close'].rolling(20).mean()
                ax_price.plot(range(len(df)), sma20, color='#00d4ff', linewidth=1.5, alpha=0.8, label='SMA 20')
            
            if 'SMA50' in self.indicators and len(df) >= 50:
                sma50 = df['Close'].rolling(50).mean()
                ax_price.plot(range(len(df)), sma50, color='#ff6b35', linewidth=1.5, alpha=0.8, label='SMA 50')
            
            # Volume bars
            if 'Volume' in self.indicators:
                self._plot_volume_bars(ax_volume, df)
            
            # RSI
            if 'RSI' in self.indicators:
                self._plot_rsi(ax_rsi, df)
            
            # Style all axes
            self._style_professional_axes(ax_price, ax_volume, ax_rsi, df)
            
            # Add title and legend
            ax_price.set_title(f'{symbol} - {timeframe} Chart', 
                             color='white', fontsize=14, fontweight='bold', pad=10)
            
            if ax_price.get_legend_handles_labels()[1]:
                ax_price.legend(loc='upper left', frameon=False, fontsize=10)
            
            # Format x-axis with proper dates
            self._format_date_axis(ax_rsi, df)
            
            self.figure.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.08)
            self.draw()
            
        except Exception as e:
            print(f"Error updating chart: {e}")
    
    def _plot_professional_candlesticks(self, ax, df):
        """Plot professional candlestick chart"""
        for i, (index, row) in enumerate(df.iterrows()):
            # Determine color
            if row['Close'] >= row['Open']:
                color = '#26a69a'  # Green for up
                edge_color = '#26a69a'
            else:
                color = '#ef5350'  # Red for down
                edge_color = '#ef5350'
            
            # High-Low line (wick)
            ax.plot([i, i], [row['Low'], row['High']], 
                   color=edge_color, linewidth=1, alpha=0.8)
            
            # Open-Close rectangle (body)
            height = abs(row['Close'] - row['Open'])
            bottom = min(row['Open'], row['Close'])
            
            if height > 0:
                rect = Rectangle((i-0.4, bottom), 0.8, height, 
                                   facecolor=color, edgecolor=edge_color, 
                                   alpha=0.9, linewidth=0.5)
                ax.add_patch(rect)
            else:
                # Doji - draw line
                ax.plot([i-0.4, i+0.4], [row['Close'], row['Close']], 
                       color=edge_color, linewidth=1.5)
        
        ax.set_xlim(-1, len(df))
        ax.grid(True, alpha=0.3, color='#444444')
    
    def _plot_volume_bars(self, ax, df):
        """Plot volume bars"""
        colors = ['#26a69a' if df.iloc[i]['Close'] >= df.iloc[i]['Open'] 
                 else '#ef5350' for i in range(len(df))]
        
        ax.bar(range(len(df)), df['Volume'], color=colors, alpha=0.6, width=0.8)
        ax.set_ylabel('Volume', color='white', fontsize=10)
        
        # Format volume labels
        max_vol = df['Volume'].max()
        if max_vol > 1e9:
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x/1e9:.1f}B'))
        elif max_vol > 1e6:
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x/1e6:.1f}M'))
        elif max_vol > 1e3:
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x/1e3:.1f}K'))
    
    def _plot_rsi(self, ax, df):
        """Plot RSI indicator"""
        if len(df) >= 14:
            rsi = ta.rsi(df['Close'], length=14)
            ax.plot(range(len(df)), rsi, color='#ffd700', linewidth=1.5)
            
            # Add RSI levels
            ax.axhline(y=70, color='#ef5350', linestyle='--', alpha=0.5, linewidth=1)
            ax.axhline(y=30, color='#26a69a', linestyle='--', alpha=0.5, linewidth=1)
            ax.axhline(y=50, color='#888888', linestyle='-', alpha=0.3, linewidth=0.5)
            
            ax.set_ylabel('RSI', color='white', fontsize=10)
            ax.set_ylim(0, 100)
    
    def _style_professional_axes(self, ax_price, ax_volume, ax_rsi, df):
        """Apply professional TWS-style formatting"""
        for ax in [ax_price, ax_volume, ax_rsi]:
            ax.set_facecolor('#0d1421')
            ax.tick_params(colors='white', labelsize=9)
            ax.grid(True, alpha=0.2, color='#444444')
            
            for spine in ax.spines.values():
                spine.set_color('#444444')
                spine.set_linewidth(0.5)
        
        # Hide x-axis labels for upper plots
        ax_price.tick_params(labelbottom=False)
        ax_volume.tick_params(labelbottom=False)
    
    def _format_date_axis(self, ax, df):
        """Format the date axis properly"""
        dates = df.index
        n_ticks = min(8, len(dates))
        
        if len(dates) > 0:
            tick_indices = np.linspace(0, len(dates)-1, n_ticks, dtype=int)
            
            ax.set_xticks(tick_indices)
            date_labels = []
            for i in tick_indices:
                if i < len(dates):
                    date_labels.append(dates[i].strftime('%Y-%m-%d'))
            
            ax.set_xticklabels(date_labels, rotation=45, ha='right')

class ChartControlsWidget(QWidget):
    """Chart controls for timeframe and period selection"""
    
    timeframe_changed = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        
        # Timeframe selection
        layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo"])
        self.timeframe_combo.setCurrentText("1m")
        self.timeframe_combo.currentTextChanged.connect(self.on_timeframe_changed)
        layout.addWidget(self.timeframe_combo)
        
        # Period selection
        layout.addWidget(QLabel("Period:"))
        self.period_combo = QComboBox()
        self.period_combo.addItems(["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"])
        self.period_combo.setCurrentText("1d")
        self.period_combo.currentTextChanged.connect(self.on_timeframe_changed)
        layout.addWidget(self.period_combo)
        
        layout.addStretch()
        
        # Style controls
        for widget in [self.timeframe_combo, self.period_combo]:
            widget.setStyleSheet("""
                QComboBox {
                    background-color: #2a2a2a;
                    color: white;
                    border: 1px solid #444444;
                    padding: 4px;
                    border-radius: 3px;
                    min-width: 60px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid white;
                }
            """)
        
        self.setLayout(layout)
        self.setStyleSheet("QLabel { color: white; }")
    
    def on_timeframe_changed(self):
        timeframe = self.timeframe_combo.currentText()
        period = self.period_combo.currentText()
        self.timeframe_changed.emit(timeframe, period)

class AdvancedWatchlistWidget(QWidget):
    """Advanced watchlist with proper data handling"""
    
    symbol_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.watchlist = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "META", "SPY", "QQQ", "AMD"]
        self.watchlist_data = {}
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title with TWS styling
        title = QLabel("WATCHLIST")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #2c2c2c;
                padding: 8px;
                border-bottom: 2px solid #00d4ff;
            }
        """)
        layout.addWidget(title)
        
        # Add/Remove controls
        controls_layout = QHBoxLayout()
        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("Add Symbol...")
        self.symbol_input.returnPressed.connect(self.add_symbol)
        self.symbol_input.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #444444;
                background-color: #2a2a2a;
                color: white;
                border-radius: 3px;
            }
        """)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_symbol)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_symbol)
        
        for btn in [add_btn, remove_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2c2c2c;
                    color: white;
                    border: 1px solid #00d4ff;
                    padding: 6px 12px;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3c3c3c;
                }
            """)
        
        controls_layout.addWidget(self.symbol_input)
        controls_layout.addWidget(add_btn)
        controls_layout.addWidget(remove_btn)
        layout.addLayout(controls_layout)
        
        # Professional watchlist table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Last", "Change", "Change %", "Bid", "Ask", "Bid Size", "Volume"
        ])
        
        # Set column widths
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 70)
        self.table.setColumnWidth(6, 70)
        
        self.table.cellClicked.connect(self.on_symbol_clicked)
        
        # Professional TWS-style table styling
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #444444;
                background-color: #0d1421;
                alternate-background-color: #1a2332;
                color: white;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                selection-background-color: #1e3a5f;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #2a2a2a;
            }
            QHeaderView::section {
                background-color: #1e3a5f;
                color: white;
                padding: 8px;
                border: 1px solid #00d4ff;
                font-weight: bold;
                font-size: 10px;
            }
        """)
        
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.update_watchlist_display()
        
    def add_symbol(self):
        symbol = self.symbol_input.text().upper().strip()
        if symbol and symbol not in self.watchlist:
            self.watchlist.append(symbol)
            self.update_watchlist_display()
            self.symbol_input.clear()
    
    def remove_symbol(self):
        current_row = self.table.currentRow()
        if current_row >= 0 and current_row < len(self.watchlist):
            symbol = self.watchlist[current_row]
            self.watchlist.remove(symbol)
            if symbol in self.watchlist_data:
                del self.watchlist_data[symbol]
            self.update_watchlist_display()
    
    def update_watchlist_display(self):
        """Updated display logic with proper data validation"""
        self.table.setRowCount(len(self.watchlist))
        
        for i, symbol in enumerate(self.watchlist):
            self.table.setItem(i, 0, QTableWidgetItem(symbol))
            data = self.watchlist_data.get(symbol, {})
            
            print(f"[WATCHLIST] Updating display for {symbol}: {data}")
            
            # Check data source to determine display behavior
            source = data.get('source', 'No TWS Data')
            
            # Last price
            last = data.get('last')
            if last is not None and last > 0:
                last_item = QTableWidgetItem(f"${last:.2f}")
                last_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                last_item.setForeground(QColor('white'))
            else:
                last_item = QTableWidgetItem("N/A")
                last_item.setForeground(QColor('#888888'))
            self.table.setItem(i, 1, last_item)
            
            # Change
            change = data.get('change')
            if change is not None:
                change_color = '#26a69a' if change >= 0 else '#ef5350'
                change_item = QTableWidgetItem(f"{change:+.2f}")
                change_item.setForeground(QColor(change_color))
                change_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            else:
                change_item = QTableWidgetItem("N/A")
                change_item.setForeground(QColor('#888888'))
            self.table.setItem(i, 2, change_item)
            
            # Change %
            percent_change = data.get('percent_change')
            if percent_change is not None:
                change_color = '#26a69a' if percent_change >= 0 else '#ef5350'
                pct_item = QTableWidgetItem(f"{percent_change:+.2f}%")
                pct_item.setForeground(QColor(change_color))
                pct_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            else:
                pct_item = QTableWidgetItem("N/A")
                pct_item.setForeground(QColor('#888888'))
            self.table.setItem(i, 3, pct_item)
            
            # Bid/Ask
            bid = data.get('bid')
            ask = data.get('ask')
            
            if bid is not None and bid > 0:
                bid_item = QTableWidgetItem(f"${bid:.2f}")
            else:
                bid_item = QTableWidgetItem("N/A")
                bid_item.setForeground(QColor('#888888'))
            self.table.setItem(i, 4, bid_item)
            
            if ask is not None and ask > 0:
                ask_item = QTableWidgetItem(f"${ask:.2f}")
            else:
                ask_item = QTableWidgetItem("N/A")
                ask_item.setForeground(QColor('#888888'))
            self.table.setItem(i, 5, ask_item)
            
            # Bid Size (mock for demo)
            bid_size = data.get('bid_size', 100 if last is not None else None)
            if bid_size is not None:
                self.table.setItem(i, 6, QTableWidgetItem(str(bid_size)))
            else:
                size_item = QTableWidgetItem("N/A")
                size_item.setForeground(QColor('#888888'))
                self.table.setItem(i, 6, size_item)
            
            # Volume (formatted)
            volume = data.get('volume')
            if volume is not None and volume > 0:
                if volume > 1e9:
                    vol_text = f"{volume/1e9:.2f}B"
                elif volume > 1e6:
                    vol_text = f"{volume/1e6:.1f}M"
                elif volume > 1e3:
                    vol_text = f"{volume/1e3:.0f}K"
                else:
                    vol_text = str(volume)
            else:
                vol_text = "N/A"
                
            vol_item = QTableWidgetItem(vol_text)
            if vol_text == "N/A":
                vol_item.setForeground(QColor('#888888'))
            self.table.setItem(i, 7, vol_item)
    
    def update_symbol_data(self, symbol: str, data: dict):
        """Update symbol data with validation"""
        if symbol in self.watchlist:
            self.watchlist_data[symbol] = data
            self.update_watchlist_display()
    
    def on_symbol_clicked(self, row, column):
        if row < len(self.watchlist):
            symbol = self.watchlist[row]
            self.symbol_selected.emit(symbol)

class ProfessionalTradingPanel(QWidget):
    """Enhanced trading panel with improved data handling"""
    
    order_placed = pyqtSignal(str, str)
    
    def __init__(self, ibkr_connection):
        super().__init__()
        self.ibkr_connection = ibkr_connection
        self.selected_symbol = None
        self.current_price = 0.0
        self.bid_price = 0.0
        self.ask_price = 0.0
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Connection status
        self.connection_status = QLabel("DISCONNECTED")
        self.connection_status.setStyleSheet("""
            QLabel {
                color: #ef5350;
                background-color: #2c2c2c;
                font-weight: bold;
                padding: 8px;
                border-bottom: 2px solid #ef5350;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.connection_status)
        
        # Symbol display
        self.symbol_label = QLabel("No Symbol Selected")
        self.symbol_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.symbol_label.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                padding: 10px;
                background-color: #0d1421;
                border: 1px solid #444444;
            }
        """)
        layout.addWidget(self.symbol_label)
        
        # Market data panel
        market_frame = QFrame()
        market_frame.setFrameStyle(QFrame.Shape.Box)
        market_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border: 1px solid #444444;
                border-radius: 5px;
            }
        """)
        market_layout = QGridLayout()
        
        # Market data labels 
        self.last_label = QLabel("Last: No Data")
        self.change_label = QLabel("Change: No Data")
        self.bid_label = QLabel("Bid: No Data")
        self.ask_label = QLabel("Ask: No Data")
        self.volume_label = QLabel("Volume: No Data")
        self.spread_label = QLabel("Spread: No Data")
        
        labels = [self.last_label, self.change_label, self.bid_label, 
                 self.ask_label, self.volume_label, self.spread_label]
        
        for label in labels:
            label.setFont(QFont("Consolas", 11))
            label.setStyleSheet("color: white; padding: 4px;")
        
        market_layout.addWidget(self.last_label, 0, 0)
        market_layout.addWidget(self.change_label, 0, 1)
        market_layout.addWidget(self.bid_label, 1, 0)
        market_layout.addWidget(self.ask_label, 1, 1)
        market_layout.addWidget(self.volume_label, 2, 0)
        market_layout.addWidget(self.spread_label, 2, 1)
        
        market_frame.setLayout(market_layout)
        layout.addWidget(market_frame)
        
        # Order entry panel
        order_frame = QGroupBox("ORDER ENTRY")
        order_frame.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 2px solid #2c2c2c;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #0d1421;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #00d4ff;
            }
        """)
        order_layout = QFormLayout()
        
        # Order controls
        control_style = """
            QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #444444;
                padding: 6px;
                border-radius: 3px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
            }
        """
        
        # Action (Buy/Sell)
        self.action_combo = QComboBox()
        self.action_combo.addItems(["BUY", "SELL"])
        self.action_combo.setStyleSheet(control_style)
        
        # Quantity
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setMinimum(1)
        self.quantity_spin.setMaximum(10000)
        self.quantity_spin.setValue(100)
        self.quantity_spin.setStyleSheet(control_style)
        
        # Order type
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["MKT", "LMT", "STP", "BRACKET"])
        self.order_type_combo.currentTextChanged.connect(self.on_order_type_changed)
        self.order_type_combo.setStyleSheet(control_style)
        
        # Price fields
        self.limit_price_spin = QDoubleSpinBox()
        self.limit_price_spin.setDecimals(2)
        self.limit_price_spin.setMinimum(0.01)
        self.limit_price_spin.setMaximum(10000.00)
        self.limit_price_spin.setValue(0.00)  # Will be auto-populated when symbol selected
        self.limit_price_spin.setEnabled(False)
        self.limit_price_spin.setStyleSheet(control_style)
        
        self.take_profit_spin = QDoubleSpinBox()
        self.take_profit_spin.setDecimals(2)
        self.take_profit_spin.setMinimum(0.01)
        self.take_profit_spin.setMaximum(10000.00)
        self.take_profit_spin.setValue(0.00)
        self.take_profit_spin.setEnabled(False)
        self.take_profit_spin.setStyleSheet(control_style)
        
        self.stop_loss_spin = QDoubleSpinBox()
        self.stop_loss_spin.setDecimals(2)
        self.stop_loss_spin.setMinimum(0.01)
        self.stop_loss_spin.setMaximum(10000.00)
        self.stop_loss_spin.setValue(0.00)
        self.stop_loss_spin.setEnabled(False)
        self.stop_loss_spin.setStyleSheet(control_style)
        
        # Time in force
        self.tif_combo = QComboBox()
        self.tif_combo.addItems(["DAY", "GTC", "IOC", "FOK"])
        self.tif_combo.setCurrentText("DAY")
        self.tif_combo.setStyleSheet(control_style)
        
        order_layout.addRow("Action:", self.action_combo)
        order_layout.addRow("Quantity:", self.quantity_spin)
        order_layout.addRow("Order Type:", self.order_type_combo)
        order_layout.addRow("Limit Price:", self.limit_price_spin)
        order_layout.addRow("Take Profit:", self.take_profit_spin)
        order_layout.addRow("Stop Loss:", self.stop_loss_spin)
        order_layout.addRow("Time in Force:", self.tif_combo)
        
        # Risk metrics
        self.risk_label = QLabel("No market data available")
        self.risk_label.setStyleSheet("color: #ffd700; font-size: 10px; padding: 5px;")
        order_layout.addRow(self.risk_label)
        
        # Order buttons
        button_layout = QHBoxLayout()
        
        self.place_order_btn = QPushButton("PLACE ORDER")
        self.place_order_btn.clicked.connect(self.place_order)
        self.place_order_btn.setEnabled(False)
        self.place_order_btn.setStyleSheet("""
            QPushButton {
                background-color: #26a69a;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 5px;
                font-size: 12px;
                border: 2px solid #26a69a;
            }
            QPushButton:hover {
                background-color: #2e7d6b;
                border-color: #2e7d6b;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
                border-color: #555555;
            }
        """)
        
        self.cancel_orders_btn = QPushButton("CANCEL ALL")
        self.cancel_orders_btn.clicked.connect(self.cancel_all_orders)
        self.cancel_orders_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef5350;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 5px;
                font-size: 12px;
                border: 2px solid #ef5350;
            }
            QPushButton:hover {
                background-color: #d32f2f;
                border-color: #d32f2f;
            }
        """)
        
        button_layout.addWidget(self.place_order_btn)
        button_layout.addWidget(self.cancel_orders_btn)
        order_layout.addRow(button_layout)
        
        order_frame.setLayout(order_layout)
        layout.addWidget(order_frame)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def update_connection_status(self, connected: bool):
        """Update connection status display"""
        if connected:
            self.connection_status.setText("CONNECTED TO TWS")
            self.connection_status.setStyleSheet("""
                QLabel {
                    color: #26a69a;
                    background-color: #2c2c2c;
                    font-weight: bold;
                    padding: 8px;
                    border-bottom: 2px solid #26a69a;
                    font-size: 12px;
                }
            """)
        else:
            self.connection_status.setText("DISCONNECTED")
            self.connection_status.setStyleSheet("""
                QLabel {
                    color: #ef5350;
                    background-color: #2c2c2c;
                    font-weight: bold;
                    padding: 8px;
                    border-bottom: 2px solid #ef5350;
                    font-size: 12px;
                }
            """)
    
    def set_selected_symbol(self, symbol: str):
            """Set selected symbol and auto-populate prices if available"""
            self.previous_symbol = self.selected_symbol  # Track previous symbol
            self.selected_symbol = symbol.upper()  # ENSURE UPPERCASE
            self.symbol_label.setText(f"Trading: {self.selected_symbol}")
            
            # RESET all market data when changing symbols
            self.current_price = 0.0
            self.bid_price = 0.0
            self.ask_price = 0.0
            
            # Clear displays until new data arrives
            self.last_label.setText(f"Last: Waiting for {self.selected_symbol} data...")
            self.change_label.setText("Change: Loading...")
            self.bid_label.setText("Bid: Loading...")
            self.ask_label.setText("Ask: Loading...")
            self.volume_label.setText("Volume: Loading...")
            self.spread_label.setText("Spread: Loading...")
            
            # Disable trading until valid data arrives
            self.place_order_btn.setEnabled(False)

    
    def update_market_data(self, symbol: str, data: dict):
            """Enhanced market data update with selective updating and animations"""
            # Always check if symbol matches AND validate data source matches symbol
            if symbol != self.selected_symbol:
                return  # Ignore data for symbols we're not tracking
                
            print(f"[TRADING PANEL] Updating market data for {symbol}: {data}")
            
            # Validate that the data actually belongs to this symbol
            data_symbol = data.get('symbol', '').upper()
            if data_symbol and data_symbol != symbol.upper():
                print(f"[TRADING PANEL] Data mismatch: Expected {symbol}, got {data_symbol}")
                return
            
            # Check if we have valid data
            source = data.get('source', 'No TWS Data')
            last = data.get('last')
            bid = data.get('bid')
            ask = data.get('ask')
            volume = data.get('volume')
            change = data.get('change')
            percent_change = data.get('percent_change')

            # If data is None or invalid, show "No Data" for this specific symbol
            if (last is None or last <= 0):
                print(f"[TRADING PANEL] No valid data for {symbol}")
                
                self.current_price = 0.0
                self.bid_price = 0.0
                self.ask_price = 0.0
                
                # Show "No Data" for this specific symbol
                self.last_label.setText(f"Last: No Data for {symbol}")
                self.change_label.setText(f"Change: No Data for {symbol}")
                self.bid_label.setText(f"Bid: No Data for {symbol}")
                self.ask_label.setText(f"Ask: No Data for {symbol}")
                self.volume_label.setText(f"Volume: No Data for {symbol}")
                self.spread_label.setText(f"Spread: No Data for {symbol}")
                self.risk_label.setText(f"No market data available for {symbol}")
                
                # Disable trading when no data
                self.place_order_btn.setEnabled(False)
                return
            
            # Check for price changes to add visual feedback
            price_changed = (self.current_price != last)
            
            # Valid data - proceed with normal updates
            print(f"[TRADING PANEL] Valid data received for {symbol}")
            
            self.current_price = last
            self.bid_price = bid
            self.ask_price = ask
            
            # Update displays with source indicator and price change animation
            source_indicator = f" ({source})"
            
            # Last price with flash effect on change
            last_text = f"Last: ${last:.2f}"
            self.last_label.setText(last_text)
            if price_changed:
                # Flash effect for price changes
                flash_color = '#26a69a' if change >= 0 else '#ef5350'
                self.last_label.setStyleSheet(f"""
                    color: {flash_color}; 
                    font-weight: bold; 
                    padding: 4px;
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 3px;
                """)
                # Reset style after 500ms
                QTimer.singleShot(500, lambda: self.last_label.setStyleSheet("color: white; font-weight: bold; padding: 4px;"))
            
            # Change with color coding
            change_color = '#26a69a' if change >= 0 else '#ef5350'
            self.change_label.setText(f"Change: {change:+.2f} ({percent_change:+.2f}%)")
            self.change_label.setStyleSheet(f"color: {change_color}; font-weight: bold; padding: 4px;")
            
            # Bid/Ask with real-time highlighting
            self.bid_label.setText(f"Bid: ${bid:.2f}")
            self.ask_label.setText(f"Ask: ${ask:.2f}")
            
            # Format volume with real-time updates
            if volume > 1e6:
                vol_text = f"{volume/1e6:.1f}M"
            elif volume > 1e3:
                vol_text = f"{volume/1e3:.0f}K"
            else:
                vol_text = str(volume)
            self.volume_label.setText(f"Volume: {vol_text}")
            
            # Calculate and display spread with real-time color coding
            spread = ask - bid
            spread_color = '#26a69a' if spread < 0.05 else '#ffd700' if spread < 0.10 else '#ef5350'
            self.spread_label.setText(f"Spread: ${spread:.2f}")
            self.spread_label.setStyleSheet(f"color: {spread_color}; font-weight: bold; padding: 4px;")
            
            # Update risk metrics
            self.update_risk_metrics()
            
            # Auto-populate prices for bracket orders (only update if values are 0 or this is a symbol change)
            if self.order_type_combo.currentText() == "BRACKET":
                self.limit_price_spin.setValue(last)
                # Update bracket prices if this is a new symbol or if current values are 0
                symbol_changed = (self.previous_symbol != self.selected_symbol)
                current_tp = self.take_profit_spin.value()
                current_sl = self.stop_loss_spin.value()
                
                if symbol_changed or current_tp == 0.0 or current_sl == 0.0:
                    self.take_profit_spin.setValue(last * 1.02)  # 2% profit target
                    self.stop_loss_spin.setValue(last * 0.98)    # 2% stop loss
                    self.previous_symbol = self.selected_symbol  # Update tracking
            
            # Enable trading
            self.place_order_btn.setEnabled(True)

    
    def update_risk_metrics(self):
        """Calculate and display enhanced risk metrics"""
        if self.current_price > 0:
            quantity = self.quantity_spin.value()
            order_value = quantity * self.current_price
            
            # Commission calculation
            commission = max(1.0, min(quantity * 0.005, order_value * 0.001))
            
            # Margin requirement (varies by stock, using 25% as default)
            margin_requirement = order_value * 0.25
            
            self.risk_label.setText(
                f"Order Value: ${order_value:,.2f} | "
                f"Est. Commission: ${commission:.2f} | "
                f"Margin Req: ${margin_requirement:,.2f}"
            )
        else:
            self.risk_label.setText("No market data - Cannot calculate risk metrics")
    
    def on_order_type_changed(self, order_type: str):
        """Handle order type changes"""
        self.limit_price_spin.setEnabled(order_type in ["LMT", "BRACKET"])
        self.take_profit_spin.setEnabled(order_type == "BRACKET")
        self.stop_loss_spin.setEnabled(order_type == "BRACKET")
        
        if order_type == "BRACKET" and self.current_price > 0:
            self.limit_price_spin.setValue(self.current_price)
            self.take_profit_spin.setValue(self.current_price * 1.02)
            self.stop_loss_spin.setValue(self.current_price * 0.98)
    
    def place_bracket_order(self, symbol, action, quantity, limit_price, take_profit, stop_loss):
        """Place bracket order (parent + take profit + stop loss)"""
        if not self.ibkr_connection.connected:
            return False
        try:
            contract = Stock(symbol, "SMART", "USD")
            qualified = self.ibkr_connection.ib.qualifyContracts(contract)
            if not qualified:
                return False
            contract = qualified[0]
            
            # Parent order
            parent = Order()
            parent.orderId = self.ibkr_connection.next_order_id
            self.ibkr_connection.next_order_id += 1
            parent.action = action.upper()
            parent.orderType = 'LMT'
            parent.lmtPrice = limit_price
            parent.totalQuantity = quantity
            parent.transmit = False  # Don't transmit yet
            
            # Take profit
            tp = Order()
            tp.orderId = self.ibkr_connection.next_order_id
            self.ibkr_connection.next_order_id += 1
            tp.action = 'SELL' if action == 'BUY' else 'BUY'
            tp.orderType = 'LMT'
            tp.lmtPrice = take_profit
            tp.totalQuantity = quantity
            tp.parentId = parent.orderId
            tp.transmit = False
            
            # Stop loss
            sl = Order()
            sl.orderId = self.ibkr_connection.next_order_id
            self.ibkr_connection.next_order_id += 1
            sl.action = 'SELL' if action == 'BUY' else 'BUY'
            sl.orderType = 'STP'
            sl.auxPrice = stop_loss
            sl.totalQuantity = quantity
            sl.parentId = parent.orderId
            sl.transmit = True  # Transmit the bracket
            
            # Place orders
            self.ibkr_connection.ib.placeOrder(contract, parent)
            self.ibkr_connection.ib.placeOrder(contract, tp)
            self.ibkr_connection.ib.placeOrder(contract, sl)
            return True
        except Exception as e:
            print(f"Bracket order error: {e}")
            return False
    
    def place_order(self):
        """Enhanced order placement with validation"""
        if not self.selected_symbol:
            QMessageBox.warning(self, "Warning", "No symbol selected")
            return
        
        if self.current_price <= 0:
            QMessageBox.warning(self, "Warning", "No valid market data available for trading")
            return
        
        action = self.action_combo.currentText()
        quantity = self.quantity_spin.value()
        order_type = self.order_type_combo.currentText()
        
        if order_type == "BRACKET":
            limit_price = self.limit_price_spin.value()
            take_profit = self.take_profit_spin.value()
            stop_loss = self.stop_loss_spin.value()
            
            reply = QMessageBox.question(
                self, "Confirm Bracket Order", 
                f"Place bracket order for {self.selected_symbol}?\n\n"
                f"Action: {action}\n"
                f"Quantity: {quantity}\n"
                f"Entry: ${limit_price:.2f}\n"
                f"Take Profit: ${take_profit:.2f}\n"
                f"Stop Loss: ${stop_loss:.2f}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                success = self.place_bracket_order(
                    self.selected_symbol, action, quantity, limit_price, take_profit, stop_loss
                )
                if success:
                    QMessageBox.information(self, "Order Placed", "Bracket order submitted successfully!")
                    self.order_placed.emit(self.selected_symbol, f"Bracket {action} {quantity} {self.selected_symbol}")
        else:
            # Regular order logic
            limit_price = self.limit_price_spin.value() if order_type == "LMT" else None
            stop_price = self.stop_loss_spin.value() if order_type == "STP" else None
            tif = self.tif_combo.currentText()
            
            success, order_id_or_msg = self.ibkr_connection.place_order(
                self.selected_symbol,
                action,
                quantity,
                order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                tif=tif
            )
            
            if success:
                QMessageBox.information(self, "Order Placed", f"{order_type} order placed! Order ID: {order_id_or_msg}")
                self.order_placed.emit(self.selected_symbol, f"{order_type} {action} {quantity} {self.selected_symbol}")
            else:
                QMessageBox.warning(self, "Order Failed", f"Order failed: {order_id_or_msg}")
    
    def cancel_all_orders(self):
        """Cancel all orders with confirmation"""
        reply = QMessageBox.question(
            self, "Cancel Orders", 
            "Cancel ALL open orders?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.ibkr_connection.cancel_all_orders()
            QMessageBox.information(self, "Orders Cancelled", "All orders cancelled")

class EnhancedPortfolioWidget(QWidget):
    """Enhanced portfolio widget matching TWS portfolio display"""
    
    def __init__(self, ibkr_connection):
        super().__init__()
        self.ibkr_connection = ibkr_connection
        self.portfolio_data = {}  # Initialize this FIRST
        self.init_ui()
        self.refresh_portfolio()  # Initial load

    def init_ui(self):
        # Initialize the main layout - THIS WAS MISSING
        layout = QVBoxLayout()
        
        # Title and refresh button
        title_layout = QHBoxLayout()
        
        title = QLabel("PORTFOLIO")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #1e3a5f;
                padding: 8px;
                border-bottom: 2px solid #00d4ff;
            }
        """)
        
        refresh_btn = QPushButton("Refresh Portfolio")
        refresh_btn.clicked.connect(self.refresh_portfolio)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #26a69a;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2e7d6b;
            }
        """)
        
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(refresh_btn)
        layout.addLayout(title_layout)
        
        # Account summary section
        summary_frame = QGroupBox("Account Summary")
        summary_frame.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 2px solid #2c2c2c;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #0d1421;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #00d4ff;
            }
        """)
        
        summary_layout = QGridLayout()
        
        # Account summary labels
        self.net_liquidation_label = QLabel("Net Liquidation: $0.00")
        self.total_cash_label = QLabel("Total Cash: $0.00")
        self.buying_power_label = QLabel("Buying Power: $0.00")
        self.unrealized_pnl_label = QLabel("Unrealized P&L: $0.00")
        self.day_pnl_label = QLabel("Day P&L: $0.00")
        self.realized_pnl_label = QLabel("Realized P&L: $0.00")
        
        summary_labels = [
            self.net_liquidation_label, self.total_cash_label, self.buying_power_label,
            self.unrealized_pnl_label, self.day_pnl_label, self.realized_pnl_label
        ]
        
        for label in summary_labels:
            label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            label.setStyleSheet("color: white; padding: 4px;")
        
        # Arrange labels in grid
        summary_layout.addWidget(self.net_liquidation_label, 0, 0)
        summary_layout.addWidget(self.total_cash_label, 0, 1)
        summary_layout.addWidget(self.buying_power_label, 1, 0)
        summary_layout.addWidget(self.unrealized_pnl_label, 1, 1)
        summary_layout.addWidget(self.day_pnl_label, 2, 0)
        summary_layout.addWidget(self.realized_pnl_label, 2, 1)
        
        summary_frame.setLayout(summary_layout)
        layout.addWidget(summary_frame)
        
        # Positions table
        positions_label = QLabel("Positions")
        positions_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        positions_label.setStyleSheet("color: #00d4ff; padding: 8px 0px;")
        layout.addWidget(positions_label)
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(8)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Position", "Avg Cost", "Current Price", 
            "Market Value", "Unrealized P&L", "Unrealized P&L %", "Day P&L"
        ])
        
        # Set column widths
        header = self.positions_table.horizontalHeader()
        if header is not None:
            for i in range(self.positions_table.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        
        # Style the table
        self.positions_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #444444;
                background-color: #0d1421;
                alternate-background-color: #1a2332;
                color: white;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                selection-background-color: #1e3a5f;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #2a2a2a;
            }
            QHeaderView::section {
                background-color: #1e3a5f;
                color: white;
                padding: 8px;
                border: 1px solid #00d4ff;
                font-weight: bold;
                font-size: 10px;
            }
        """)
        
        layout.addWidget(self.positions_table)
        
        # Set the main layout 
        self.setLayout(layout)

    
    def update_portfolio(self, portfolio_data: dict):
        """Update portfolio with new data"""
        self.portfolio_data = portfolio_data
        self.update_portfolio_display()
    
    def update_portfolio_display(self):
        """Update the portfolio display with current data"""
        if not self.portfolio_data:
            # Use mock data if no real data available
            self.portfolio_data = self.ibkr_connection.get_mock_portfolio_data()
        
        # Update account summary
        account_summary = self.portfolio_data.get('account_summary', {})
        
        net_liq = float(account_summary.get('NetLiquidation', 0))
        total_cash = float(account_summary.get('TotalCashValue', 0))
        buying_power = float(account_summary.get('BuyingPower', 0))
        
        self.net_liquidation_label.setText(f"Net Liquidation: ${net_liq:,.2f}")
        self.total_cash_label.setText(f"Total Cash: ${total_cash:,.2f}")
        self.buying_power_label.setText(f"Buying Power: ${buying_power:,.2f}")
        
        # Calculate totals for P&L
        positions = self.portfolio_data.get('positions', [])
        total_unrealized = sum(pos.get('pnl', 0) for pos in positions)
        
        self.unrealized_pnl_label.setText(f"Unrealized P&L: ${total_unrealized:+,.2f}")
        pnl_color = '#26a69a' if total_unrealized >= 0 else '#ef5350'
        self.unrealized_pnl_label.setStyleSheet(f"color: {pnl_color}; font-weight: bold; padding: 4px;")
        
        # Day P&L and realized P&L
        day_pnl = self.portfolio_data.get('day_change', total_unrealized * 0.3)
        realized_pnl = float(account_summary.get('RealizedPnL', 1250.00))
        
        self.day_pnl_label.setText(f"Day P&L: ${day_pnl:+,.2f}")
        day_color = '#26a69a' if day_pnl >= 0 else '#ef5350'
        self.day_pnl_label.setStyleSheet(f"color: {day_color}; font-weight: bold; padding: 4px;")
        
        self.realized_pnl_label.setText(f"Realized P&L: ${realized_pnl:+,.2f}")
        real_color = '#26a69a' if realized_pnl >= 0 else '#ef5350'
        self.realized_pnl_label.setStyleSheet(f"color: {real_color}; font-weight: bold; padding: 4px;")
        
        # Update positions table with error handling
        self.positions_table.setRowCount(len(positions))
        
        for i, position in enumerate(positions):
            try:
                symbol = position.get('symbol', 'N/A')
                pos_size = position.get('quantity', 0)
                avg_cost = position.get('avg_cost', 0)
                market_value = position.get('market_value', 0)
                current_price = position.get('current_price', 0)
                pnl = position.get('pnl', 0)
                pnl_pct = position.get('pnl_pct', 0)
                
                # Symbol
                self.positions_table.setItem(i, 0, QTableWidgetItem(symbol))
                
                # Position size with color for long/short
                pos_item = QTableWidgetItem(str(int(pos_size)))
                pos_color = '#26a69a' if pos_size > 0 else '#ef5350' if pos_size < 0 else 'white'
                pos_item.setForeground(QColor(pos_color))
                self.positions_table.setItem(i, 1, pos_item)
                
                # Average cost
                self.positions_table.setItem(i, 2, QTableWidgetItem(f"${avg_cost:.2f}"))
                
                # Current price
                self.positions_table.setItem(i, 3, QTableWidgetItem(f"${current_price:.2f}"))
                
                # Market value
                self.positions_table.setItem(i, 4, QTableWidgetItem(f"${market_value:,.2f}"))
                
                # Unrealized P&L with color
                unrealized_item = QTableWidgetItem(f"${pnl:+,.2f}")
                unrealized_color = '#26a69a' if pnl >= 0 else '#ef5350'
                unrealized_item.setForeground(QColor(unrealized_color))
                unrealized_item.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
                self.positions_table.setItem(i, 5, unrealized_item)
                
                # Unrealized P&L %
                unrealized_pct_item = QTableWidgetItem(f"{pnl_pct:+.2f}%")
                unrealized_pct_item.setForeground(QColor(unrealized_color))
                unrealized_pct_item.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
                self.positions_table.setItem(i, 6, unrealized_pct_item)
                
                # Day P&L (estimate or calculate)
                day_pnl_pos = pnl * 0.2  # Mock calculation
                day_pnl_item = QTableWidgetItem(f"${day_pnl_pos:+,.2f}")
                day_pnl_color = '#26a69a' if day_pnl_pos >= 0 else '#ef5350'
                day_pnl_item.setForeground(QColor(day_pnl_color))
                day_pnl_item.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
                self.positions_table.setItem(i, 7, day_pnl_item)
                
            except Exception as e:
                print(f"Error updating position row {i}: {e}")
                # Add empty row on error
                for col in range(8):
                    self.positions_table.setItem(i, col, QTableWidgetItem("Error"))

    def refresh_portfolio(self):
        """Force refresh portfolio data"""
        try:
            portfolio_data = self.ibkr_connection.get_portfolio_data()
            self.update_portfolio(portfolio_data)
        except Exception as e:
            print(f"Error refreshing portfolio: {e}")
            # Use mock data as fallback
            self.update_portfolio(self.ibkr_connection.get_mock_portfolio_data())
    def on_connection_status_changed(self, connected):
        """Handle connection status changes and refresh portfolio"""
        if connected:
            print("[PORTFOLIO] Connection established, refreshing portfolio...")
            # Wait a moment for connection to stabilize
            QTimer.singleShot(2000, self.refresh_portfolio)


class ConnectionDialog(QDialog):
    """Connection dialog for TWS setup"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to TWS")
        self.setModal(True)
        self.init_ui()
    
    def init_ui(self):
        layout = QFormLayout()
        
        self.host_input = QLineEdit("127.0.0.1")
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(7496)
        
        self.client_id_input = QSpinBox()
        self.client_id_input.setRange(1, 100)
        self.client_id_input.setValue(1)
        
        layout.addRow("Host:", self.host_input)
        layout.addRow("Port:", self.port_input)
        layout.addRow("Client ID:", self.client_id_input)
        
        buttons = QHBoxLayout()
        connect_btn = QPushButton("Connect")
        cancel_btn = QPushButton("Cancel")
        
        connect_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(connect_btn)
        buttons.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons)
        
        self.setLayout(main_layout)
    
    def get_connection_params(self):
        return {
            'host': self.host_input.text(),
            'port': self.port_input.value(),
            'client_id': self.client_id_input.value()
        }



class DataUpdateWorker(QThread):
    """Background worker for updating market data and portfolio"""
    
    data_ready = pyqtSignal(str, dict)  # symbol, data
    portfolio_ready = pyqtSignal(dict)  # portfolio_data
    orders_ready = pyqtSignal(list)  # open orders
    trades_ready = pyqtSignal(list)  # executions
    error_occurred = pyqtSignal(str)    # error_message
    
    def __init__(self, symbols: List[str], ibkr_connection):
        super().__init__()
        self.symbols = symbols
        self.ibkr_connection = ibkr_connection
        self.running = False
        self.update_interval = 1  # Faster updates - 1 second instead of 2
        
    def run(self):
        """Main worker thread loop with better error handling"""
        self.running = True
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.running:
            try:
                # Check connection health first
                if not self.ibkr_connection.connected: 
                    print("[WORKER] Connection not healthy, using fallback data")
                    pass
                
                # Update market data for all symbols
                for symbol in self.symbols:
                    if not self.running:
                        break
                    
                    try:
                        data = self.ibkr_connection.get_fallback_data(symbol)
                        self.data_ready.emit(symbol, data)
                        consecutive_errors = 0  # Reset error counter on success
                    except Exception as e:
                        consecutive_errors += 1
                        self.error_occurred.emit(f"Error updating {symbol}: {str(e)}")
                        
                        if consecutive_errors >= max_consecutive_errors:
                            self.error_occurred.emit(f"Too many consecutive errors ({consecutive_errors}), slowing down updates")
                            # Sleep longer after many errors
                            for _ in range(50):  # 5 second pause
                                if not self.running:
                                    break
                                self.msleep(100)
                
                # Update portfolio and other data
                if self.running:
                    try:
                        portfolio_data = self.ibkr_connection.get_portfolio_data()
                        self.portfolio_ready.emit(portfolio_data)
                    except Exception as e:
                        self.error_occurred.emit(f"Error updating portfolio: {str(e)}")
                
                # Update orders and trades
                if self.running:
                    try:
                        open_orders = self.ibkr_connection.get_open_orders()
                        self.orders_ready.emit(open_orders)
                    except Exception as e:
                        self.error_occurred.emit(f"Error updating orders: {str(e)}")
                    
                    try:
                        executions = self.ibkr_connection.get_executions()
                        self.trades_ready.emit(executions)
                    except Exception as e:
                        self.error_occurred.emit(f"Error updating trades: {str(e)}")
                
                # Sleep for the update interval
                for _ in range(self.update_interval * 10):
                    if not self.running:
                        break
                    self.msleep(100)
                
            except Exception as e:
                self.error_occurred.emit(f"Worker thread error: {str(e)}")
                consecutive_errors += 1
                
                if consecutive_errors >= max_consecutive_errors:
                    print(f"[WORKER] Too many errors, stopping worker thread")
                    break
        
        print("[WORKER] Data worker thread stopped")

    
    def stop(self):
        """Stop the worker thread"""
        self.running = False
    
    def add_symbol(self, symbol: str):
        """Add a symbol to the update list"""
        if symbol not in self.symbols:
            self.symbols.append(symbol)
    
    def remove_symbol(self, symbol: str):
        """Remove a symbol from the update list"""
        if symbol in self.symbols:
            self.symbols.remove(symbol)
    
    def set_update_interval(self, interval: int):
        """Set the update interval in seconds"""
        self.update_interval = max(1, interval)

class EnhancedNewsWidget(QWidget):
    """TWS-style news feed with fallback RSS import for paper trading."""

    def __init__(self, ibkr_connection):
        super().__init__()
        self.ibkr_connection = ibkr_connection
        self.current_symbol = None
        self.init_ui()
        self.news_timer = QTimer()
        self.news_timer.timeout.connect(self.refresh_news)
        self.news_timer.start(2000)  # Refresh every 2 seconds
        self.refresh_news()

    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("NEWS FEED (TWS Delayed)")
        title.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #1e3a5f;
                padding: 6px;
                border-bottom: 2px solid #00d4ff;
            }
        """)
        layout.addWidget(title)
        self.news_list = QListWidget()
        self.news_list.setStyleSheet("""
            QListWidget {
                background-color: #0d1421;
                color: white;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                border: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #23272e;
                padding: 0px 2px 0px 2px;
                line-height: 160%;
            }
            QListWidget::item:selected {
                background: #1e3a5f;
            }
        """)
        self.news_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.news_list.itemClicked.connect(self.on_news_item_clicked)
        self.news_list.setWordWrap(True)
        layout.addWidget(self.news_list)
        self.setLayout(layout)

    def get_provider_acronym(self, provider_name):
        """Convert provider name to TWS-style acronym"""
        acronym_map = {
            'YAHOO FINANCE': 'YAH',
            'REUTERS': 'RTR',
            'BLOOMBERG': 'BBG', 
            'MARKETWATCH': 'MW',
            'CNBC': 'CNBC',
            'FINANCIAL TIMES': 'FT',
            'WALL STREET JOURNAL': 'WSJ',
            'SEEKING ALPHA': 'SA',
            'ZACKS': 'ZAC',
            'BENZINGA': 'BZ',
            'THE MOTLEY FOOL': 'TMF',
            'TOP NEWS': 'TOP',
            'BARRONS': 'BAR',
            'FORBES': 'FOR'
        }
        
        # Check for exact matches first
        if provider_name in acronym_map:
            return acronym_map[provider_name]
        
        # Check for partial matches
        for full_name, acronym in acronym_map.items():
            if full_name in provider_name:
                return acronym
        
        # Default: create acronym from first letters of words
        words = provider_name.split()
        if len(words) >= 2:
            return ''.join(word[0] for word in words[:3])  # Max 3 letters
        elif len(words) == 1 and len(words[0]) >= 3:
            return words[0][:3]
        else:
            return provider_name[:3] if provider_name else 'UNK'
        
    def on_news_item_clicked(self, item):
        """Handle news item click to open URL in browser"""
        url = item.data(Qt.ItemDataRole.UserRole)
        if url and url.startswith(('http://', 'https://')):
            try:
                webbrowser.open(url)
            except Exception as e:
                print(f"Error opening URL: {e}")
        else:
            print("No valid URL found for this news item")

    def refresh_news(self):
        # Get TWS news
        tws_items = self.ibkr_connection.get_tws_news(self.current_symbol)
        # If no TWS news, fallback to RSS
        if not tws_items:
            tws_items = self.import_rss_news()
        items = sorted(tws_items, key=lambda x: x.get('timestamp', datetime.min), reverse=True)[:50]  # Newest first, limit 50
        self.news_list.clear()
        if not items:
            self.news_list.addItem("No news available - Check connection or subscriptions")
            return
        for news in items:
            # Parse timestamp to DD/MM/YY HH:MM:SS format
            timestamp = news.get('timestamp')
            date_time_str = ""
            try:
                if isinstance(timestamp, datetime):
                    date_time_str = timestamp.strftime("%d/%m/%y %H:%M:%S")
                elif isinstance(timestamp, (int, float)):
                    date_time_str = datetime.fromtimestamp(timestamp).strftime("%d/%m/%y %H:%M:%S")
                elif isinstance(timestamp, str):
                    try:
                        parsed_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                        date_time_str = parsed_dt.strftime("%d/%m/%y %H:%M:%S")
                    except Exception:
                        try:
                            parsed_dt = datetime.strptime(timestamp, "%a, %d %b %Y %H:%M:%S %Z")
                            date_time_str = parsed_dt.strftime("%d/%m/%y %H:%M:%S")
                        except Exception:
                            # Default to current time if parsing fails
                            date_time_str = datetime.now().strftime("%d/%m/%y %H:%M:%S")
            except Exception:
                date_time_str = datetime.now().strftime("%d/%m/%y %H:%M:%S")
            
            # Get provider acronym
            provider = news.get('provider', '').upper()
            provider_acronym = self.get_provider_acronym(provider)
            
            # Get headline only
            headline = news.get('headline', '')
            
            # Format as: "DD/MM/YY HH:MM:SS ACRONYM HEADLINE"
            display_text = f"{date_time_str} {provider_acronym} {headline}".strip()
            
            # Create clickable item
            item = QListWidgetItem(display_text)
            item.setForeground(QColor('#e0e0e0'))
            
            # Store the URL for click handling
            url = news.get('url', news.get('link', ''))
            item.setData(Qt.ItemDataRole.UserRole, url)
            
            self.news_list.addItem(item)


    def import_rss_news(self):
        """Fallback RSS import for paper trading with no subscriptions."""
        try:
            feed_url = "https://finance.yahoo.com/news/rssindex"
            feed = feedparser.parse(feed_url)
            news_items = []
            provider_name = 'YAHOO FINANCE'
            
            if hasattr(feed, 'feed') and not isinstance(feed.feed, list) and hasattr(feed.feed, 'title'):
                provider_name = feed.feed.title.upper()
            
            for entry in feed.entries[:50]:  # Limit to 50 recent items
                title = entry.title if hasattr(entry, 'title') else ''
                published = entry.published if hasattr(entry, 'published') else ''
                link = entry.link if hasattr(entry, 'link') else ''
                
                # Parse published date
                try:
                    if published:
                        parsed_date = date_parser.parse(published)
                    else:
                        parsed_date = datetime.now()
                except:
                    parsed_date = datetime.now()
                
                news_items.append({
                    'timestamp': parsed_date,
                    'provider': provider_name,
                    'symbol': '',
                    'headline': title,
                    'url': link,
                    'received_at': datetime.now()
                })
            return news_items
        except Exception as e:
            print(f"Error fetching RSS news: {e}")
            return []

    def update_news_for_symbol(self, symbol):
        self.current_symbol = symbol
        self.refresh_news()

class AdvancedScreenerWidget(QWidget):
    """Advanced stock screener with embedded Finviz Elite auto-login"""
    def check_webengine(self):
        """Check if WebEngine is available with better error reporting"""
        try:
            # Attempt to import WebEngine components
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
            print("[SCREENER] WebEngine components successfully imported")
            return True
        except ImportError as e:
            print(f"[SCREENER] WebEngine not available: {e}")
            print("Install with: pip install PyQt6-WebEngine")
            return False
        except Exception as e:
            print(f"[SCREENER] WebEngine check failed: {e}")
            return False
    
    def __init__(self):
        super().__init__()
        self.finviz_email = "YOUR_EMAIL"
        self.finviz_password = "YOUR_PASSWORD"
        self.login_attempted = False
        
        # Check if WebEngine is available first
        self.webengine_available = self.check_webengine()
        
        # Initialize UI based on WebEngine availability - ONLY CALL ONCE
        if self.webengine_available:
            self.init_ui()
        else:
            self.init_ui_fallback()


    def init_ui_fallback(self):
        """Fallback UI when WebEngine is not available"""
        layout = QVBoxLayout()
        
        title = QLabel("STOCK SCREENER")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background-color: #2c2c2c; padding: 8px;")
        layout.addWidget(title)
        
        error_label = QLabel("WebEngine not available. Opening screener in external browser.")
        error_label.setStyleSheet("color: #ef5350; padding: 10px; text-align: center;")
        layout.addWidget(error_label)
        
        open_btn = QPushButton("Open Finviz Screener")
        open_btn.clicked.connect(lambda: webbrowser.open("https://elite.finviz.com/screener.ashx"))
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #26a69a;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        layout.addWidget(open_btn)
        
        self.setLayout(layout)

    def init_ui(self):
        """Initialize UI with embedded web view"""
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
            from PyQt6.QtCore import QUrl, QTimer
        except ImportError:
            # Fallback if imports fail
            self.init_ui_fallback()
            return

        layout = QVBoxLayout()
        
        # Title
        title = QLabel("STOCK SCREENER - FINVIZ ELITE")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #1e3a5f;
                padding: 8px;
                border-bottom: 2px solid #00d4ff;
            }
        """)
        layout.addWidget(title)
        
        # Controls row
        controls_layout = QHBoxLayout()
        
        # Login status indicator
        self.login_status = QLabel("Status: Initializing...")
        self.login_status.setStyleSheet("color: #ffd700; font-weight: bold; padding: 4px;")
        controls_layout.addWidget(self.login_status)
        
        # Button to open external Finviz
        open_finviz_btn = QPushButton("Open External Finviz")
        open_finviz_btn.clicked.connect(self.open_finviz)
        open_finviz_btn.setStyleSheet("""
            QPushButton {
                background-color: #26a69a;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 3px;
                border: 1px solid #26a69a;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2e7d6b;
            }
        """)
        
        # Button to reload embedded screener
        reload_btn = QPushButton("Reload Screener")
        reload_btn.clicked.connect(self.reload_screener)
        reload_btn.setStyleSheet(open_finviz_btn.styleSheet())
        
        # Manual login button
        login_btn = QPushButton("Force Login")
        login_btn.clicked.connect(self.force_login)
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e3a5f;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 3px;
                border: 1px solid #00d4ff;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2a4a6f;
            }
        """)
        
        controls_layout.addWidget(open_finviz_btn)
        controls_layout.addWidget(reload_btn)
        controls_layout.addWidget(login_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        try:
            # Create persistent web profile for login sessions
            self.profile = QWebEngineProfile("FinvizElite", self)
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
            
            # Configure profile settings
            settings = self.profile.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
            
            # Embedded Finviz screener using QWebEngineView with persistent profile
            self.web_view = QWebEngineView()
            
            # Use the persistent profile
            self.page = QWebEnginePage(self.profile, self.web_view)
            self.web_view.setPage(self.page)
            
            self.web_view.setStyleSheet("""
                QWebEngineView {
                    border: 1px solid #444444;
                    background-color: white;
                }
            """)
            
            # Set up page loading handlers
            self.web_view.loadFinished.connect(self.on_page_loaded)
            self.web_view.loadStarted.connect(self.on_page_loading)
            
            # Load the exact Elite screener URL
            self.screener_url = "https://elite.finviz.com/screener.ashx?v=152&p=i1&f=cap_0.001to,geo_usa|china|france|europe|australia|belgium|canada|chinahongkong|germany|hongkong|iceland|japan|newzealand|ireland|netherlands|norway|singapore|southkorea|sweden|taiwan|unitedarabemirates|unitedkingdom|switzerland|spain,sh_curvol_o100,sh_relvol_o1,ta_change_u&ft=4&o=-change&ar=10&c=0,1,6,24,25,85,26,27,28,29,30,31,84,50,51,83,61,63,64,67,65,66,71,72"
            
            # First try to load the screener directly (may work if already logged in via cookies)
            self.web_view.load(QUrl(self.screener_url))
            
            layout.addWidget(self.web_view)
            
        except Exception as e:
            # If WebEngine setup fails, show error message
            error_label = QLabel(f"WebEngine setup failed: {str(e)}")
            error_label.setStyleSheet("color: #ef5350; padding: 10px;")
            layout.addWidget(error_label)
            
            # Add fallback button
            fallback_btn = QPushButton("Open in Browser")
            fallback_btn.clicked.connect(self.open_finviz)
            fallback_btn.setStyleSheet(open_finviz_btn.styleSheet())
            layout.addWidget(fallback_btn)
        
        self.setLayout(layout)
    
    def on_page_loading(self):
        """Handle page loading start"""
        if hasattr(self, 'login_status'):
            self.login_status.setText("Status: Loading...")
            self.login_status.setStyleSheet("color: #ffd700; font-weight: bold; padding: 4px;")
    
    def on_page_loaded(self, success):
        """Handle page loading completion and auto-login if needed"""
        if not hasattr(self, 'login_status'):
            return
            
        if not success:
            self.login_status.setText("Status: Load Failed")
            self.login_status.setStyleSheet("color: #ef5350; font-weight: bold; padding: 4px;")
            return
        
        current_url = self.web_view.url().toString()
        print(f"[SCREENER] Page loaded: {current_url}")
        
        # Check if we're on the login page
        if "login" in current_url.lower() or "signin" in current_url.lower():
            self.login_status.setText("Status: Login Required")
            self.login_status.setStyleSheet("color: #ef5350; font-weight: bold; padding: 4px;")
            if not self.login_attempted:
                self.attempt_auto_login()
        elif "elite.finviz.com" in current_url and "screener" in current_url:
            self.login_status.setText("Status: Logged In Successfully")
            self.login_status.setStyleSheet("color: #26a69a; font-weight: bold; padding: 4px;")
        else:
            self.login_status.setText("Status: Unknown Page")
            self.login_status.setStyleSheet("color: #ffd700; font-weight: bold; padding: 4px;")
    
    def attempt_auto_login(self):
        """Attempt automatic login using stored credentials"""
        if self.login_attempted or not hasattr(self, 'web_view'):
            return
            
        self.login_attempted = True
        if hasattr(self, 'login_status'):
            self.login_status.setText("Status: Attempting Auto-Login...")
            self.login_status.setStyleSheet("color: #ffd700; font-weight: bold; padding: 4px;")
        
        # JavaScript to fill login form and submit
        login_script = f"""
        // Wait for page to be ready
        setTimeout(function() {{
            // Try to find email/username field (multiple possible selectors)
            var emailField = document.querySelector('input[name="email"]') || 
                           document.querySelector('input[type="email"]') || 
                           document.querySelector('input[name="username"]') ||
                           document.querySelector('#email') ||
                           document.querySelector('#username');
            
            // Try to find password field
            var passwordField = document.querySelector('input[name="password"]') || 
                              document.querySelector('input[type="password"]') ||
                              document.querySelector('#password');
            
            // Try to find submit button
            var submitButton = document.querySelector('input[type="submit"]') || 
                             document.querySelector('button[type="submit"]') ||
                             document.querySelector('button:contains("Sign In")') ||
                             document.querySelector('button:contains("Login")') ||
                             document.querySelector('.btn-primary');
            
            if (emailField && passwordField) {{
                console.log('Found login fields, filling them...');
                emailField.value = '{self.finviz_email}';
                passwordField.value = '{self.finviz_password}';
                
                // Trigger change events
                emailField.dispatchEvent(new Event('change'));
                passwordField.dispatchEvent(new Event('change'));
                
                // Submit the form
                if (submitButton) {{
                    console.log('Clicking submit button...');
                    submitButton.click();
                }} else {{
                    // Try to find and submit the form
                    var form = emailField.closest('form');
                    if (form) {{
                        console.log('Submitting form...');
                        form.submit();
                    }}
                }}
                return 'Login attempted';
            }} else {{
                console.log('Login fields not found');
                return 'Login fields not found';
            }}
        }}, 2000); // Wait 2 seconds for page to fully load
        """
        
        if hasattr(self, 'web_view'):
            self.web_view.page().runJavaScript(login_script, self.on_login_script_result)
    
    def on_login_script_result(self, result):
        """Handle the result of the login script"""
        print(f"[SCREENER] Login script result: {result}")
        
        # Import QTimer here to avoid import issues
        from PyQt6.QtCore import QTimer
        
        # Wait a moment, then check if we need to redirect to screener
        QTimer.singleShot(3000, self.check_login_success)
    
    def check_login_success(self):
        """Check if login was successful and redirect to screener"""
        if not hasattr(self, 'web_view'):
            return
            
        current_url = self.web_view.url().toString()
        
        if "elite.finviz.com" in current_url and "screener" not in current_url:
            # We're logged in but not on the screener page, redirect
            print(f"[SCREENER] Login successful, redirecting to screener...")
            from PyQt6.QtCore import QUrl
            self.web_view.load(QUrl(self.screener_url))
        elif "login" in current_url.lower():
            # Still on login page, login may have failed
            if hasattr(self, 'login_status'):
                self.login_status.setText("Status: Auto-Login Failed - Try Manual")
                self.login_status.setStyleSheet("color: #ef5350; font-weight: bold; padding: 4px;")
        else:
            # Check again in a moment
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, self.verify_screener_loaded)

    def verify_screener_loaded(self):
        """Final verification that screener is loaded"""
        if not hasattr(self, 'web_view') or not hasattr(self, 'login_status'):
            return
            
        current_url = self.web_view.url().toString()
        if "elite.finviz.com" in current_url and "screener" in current_url:
            self.login_status.setText("Status: Screener Loaded Successfully")
            self.login_status.setStyleSheet("color: #26a69a; font-weight: bold; padding: 4px;")
        else:
            self.login_status.setText("Status: Please Login Manually")
            self.login_status.setStyleSheet("color: #ef5350; font-weight: bold; padding: 4px;")
    
    def force_login(self):
        """Force a fresh login attempt"""
        if not hasattr(self, 'web_view'):
            return
            
        self.login_attempted = False
        # Clear cookies to force fresh login
        if hasattr(self, 'profile'):
            self.profile.cookieStore().deleteAllCookies()
        
        # Navigate to login page first
        login_url = "https://elite.finviz.com/login.ashx"
        from PyQt6.QtCore import QUrl
        self.web_view.load(QUrl(login_url))
    
    def open_finviz(self):
        """Open Finviz screener in external browser"""
        finviz_url = "https://elite.finviz.com/screener.ashx?v=152&p=i1&f=cap_0.001to,geo_usa|china|france|europe|australia|belgium|canada|chinahongkong|germany|hongkong|iceland|japan|newzealand|ireland|netherlands|norway|singapore|southkorea|sweden|taiwan|unitedarabemirates|unitedkingdom|switzerland|spain,sh_curvol_o100,sh_relvol_o1,ta_change_u&ft=4&o=-change&ar=10&c=0,1,6,24,25,85,26,27,28,29,30,31,84,50,51,83,61,63,64,67,65,66,71,72"
        webbrowser.open(finviz_url)
    
    def reload_screener(self):
        """Reload the embedded screener"""
        if not hasattr(self, 'web_view'):
            return
            
        self.login_attempted = False
        self.web_view.reload()

class OrdersWidget(QWidget):
    """Orders and positions tracking widget"""
    
    def __init__(self, ibkr_connection):
        super().__init__()
        self.ibkr_connection = ibkr_connection
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("ORDERS & TRADES")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #1e3a5f;
                padding: 8px;
                border-bottom: 2px solid #00d4ff;
            }
        """)
        layout.addWidget(title)
        
        # Tab widget for orders and trades
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444444;
                background-color: #0d1421;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: white;
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #1e3a5f;
                border-bottom: 2px solid #00d4ff;
            }
        """)
        
        # Open orders table
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(8)
        self.orders_table.setHorizontalHeaderLabels([
            "Order ID", "Symbol", "Action", "Qty", "Type", "Price", "Status", "Time"
        ])
        
        # Trades table
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(7)
        self.trades_table.setHorizontalHeaderLabels([
            "Symbol", "Action", "Qty", "Price", "Commission", "P&L", "Time"
        ])
        
        # Style tables
        for table in [self.orders_table, self.trades_table]:
            table.setStyleSheet("""
                QTableWidget {
                    gridline-color: #444444;
                    background-color: #0d1421;
                    alternate-background-color: #1a2332;
                    color: white;
                    font-family: 'Consolas', monospace;
                    font-size: 10px;
                    selection-background-color: #1e3a5f;
                }
                QTableWidget::item {
                    padding: 4px;
                    border-bottom: 1px solid #2a2a2a;
                }
                QHeaderView::section {
                    background-color: #1e3a5f;
                    color: white;
                    padding: 6px;
                    border: 1px solid #00d4ff;
                    font-weight: bold;
                    font-size: 9px;
                }
            """)
            
            header = table.horizontalHeader()
            for i in range(table.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        
        tab_widget.addTab(self.orders_table, "Open Orders")
        tab_widget.addTab(self.trades_table, "Trades")
        
        layout.addWidget(tab_widget)
        self.setLayout(layout)
        
    def update_orders(self, open_orders):
        """Update open orders table"""
        self.orders_table.setRowCount(len(open_orders))
        for i, order in enumerate(open_orders):
            try:
                # Extract order details safely
                order_id = getattr(order, 'orderId', '')
                symbol = ''
                if hasattr(order, 'contract') and order.contract:
                    symbol = getattr(order.contract, 'symbol', '')
                else:
                    # Sometimes contract might be missing; try other fields or set as Unknown
                    symbol = getattr(order, 'symbol', 'Unknown')
                
                action = getattr(order, 'action', '')
                qty = getattr(order, 'totalQuantity', '')
                order_type = getattr(order, 'orderType', '')
                status = 'Unknown'
                if hasattr(order, 'status'):
                    status = str(getattr(order, 'status', 'Unknown'))
                elif hasattr(order, 'orderStatus') and order.orderStatus:
                    status = str(getattr(order.orderStatus, 'status', 'Unknown'))

                # Price information is not always directly on order, try lmtPrice or auxPrice
                price = ''
                if hasattr(order, 'lmtPrice') and order.lmtPrice > 0:
                    price = f"${order.lmtPrice:.2f}"
                elif hasattr(order, 'auxPrice') and order.auxPrice > 0:
                    price = f"${order.auxPrice:.2f}"
                else:
                    price = "$0.00"

                # Time info may be in transmitTime or createdTime if available
                time_str = ""
                if hasattr(order, 'transmitTime') and order.transmitTime:
                    time_str = str(order.transmitTime)
                elif hasattr(order, 'createdTime') and order.createdTime:
                    time_str = str(order.createdTime)
                else:
                    time_str = ""

                # Populate table cells
                self.orders_table.setItem(i, 0, QTableWidgetItem(str(order_id)))
                self.orders_table.setItem(i, 1, QTableWidgetItem(symbol))
                self.orders_table.setItem(i, 2, QTableWidgetItem(action))
                self.orders_table.setItem(i, 3, QTableWidgetItem(str(qty)))
                self.orders_table.setItem(i, 4, QTableWidgetItem(order_type))
                self.orders_table.setItem(i, 5, QTableWidgetItem(price))
                self.orders_table.setItem(i, 6, QTableWidgetItem(status))
                self.orders_table.setItem(i, 7, QTableWidgetItem(time_str))
            except Exception as e:
                print(f"Error updating order row {i}: {e}")

                
    def update_trades(self, executions):
        """Update trades table with all historical trades"""
        # Try to get historical trades from self.ibkr_connection.trades_history if available
        trades = []
        if hasattr(self.ibkr_connection, 'trades_history') and self.ibkr_connection.trades_history:
            trades = self.ibkr_connection.trades_history
        else:
            # Fallback to executions passed in
            trades = executions

        self.trades_table.setRowCount(len(trades))
        for i, trade in enumerate(trades):
            try:
                # When dealing with executions from IB, attributes differ from dicts saved in trades_history
                # For dict type entries (historical trades saved), access keys
                if isinstance(trade, dict):
                    symbol = trade.get('symbol', 'N/A')
                    side = trade.get('side', 'N/A')
                    qty = trade.get('quantity', trade.get('shares', 0))
                    price = trade.get('price', 0.0)
                    commission = trade.get('commission', 0.0)
                    pnl = trade.get('pnl', 0.0)
                    time_str = trade.get('time', '') or trade.get('timestamp', '')
                else:
                    # Assume IB execution object
                    symbol = getattr(trade.contract if hasattr(trade, 'contract') else trade, 'symbol', 'N/A')
                    side = getattr(trade, 'side', 'N/A')
                    qty = getattr(trade, 'shares', 0)
                    price = getattr(trade, 'price', 0.0)
                    commission = 0.0  # commission info typically not on execution object
                    pnl = 0.0  # pnl info typically not on execution object
                    time_str = ''  # time not usually on execution object

                self.trades_table.setItem(i, 0, QTableWidgetItem(symbol))
                self.trades_table.setItem(i, 1, QTableWidgetItem(side))
                self.trades_table.setItem(i, 2, QTableWidgetItem(str(qty)))
                self.trades_table.setItem(i, 3, QTableWidgetItem(f"${price:.2f}"))
                self.trades_table.setItem(i, 4, QTableWidgetItem(f"${commission:.2f}"))
                self.trades_table.setItem(i, 5, QTableWidgetItem(f"${pnl:.2f}"))
                self.trades_table.setItem(i, 6, QTableWidgetItem(str(time_str)))
            except Exception as e:
                print(f"Error updating trade row {i}: {e}")


class ProfessionalTradingPlatform(QMainWindow):
    """Main trading platform window with professional TWS-style interface"""
    
    def __init__(self):
        super().__init__()
        self.ibkr_connection = EnhancedIBKRConnection()
        self.data_worker = None
        self.init_ui()
        self.setup_connections()
        self.setup_timers()
        
      # Start initial data updates immediately
        QTimer.singleShot(1000, self.initial_data_load)

    def initial_data_load(self):
        """Load initial data for all watchlist symbols"""
        for symbol in self.watchlist_widget.watchlist:
            try:
                data = self.ibkr_connection.get_real_time_data(symbol)
                self.on_market_data_update(symbol, data)
            except Exception as e:
                print(f"Error loading initial data for {symbol}: {e}")
        
    def init_ui(self):
        """Initialize the main user interface"""
        self.setWindowTitle("Professional Trading Platform v3.0 - TWS Style")
        self.setGeometry(100, 100, 1800, 1200)
        
        # Set theme
        self.setStyleSheet("""
QMainWindow {
    background-color: #181c24;
    color: #e0e0e0;
}
QWidget {
    background-color: #181c24;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 11pt;
}
QMenuBar, QMenu, QStatusBar {
    background-color: #23272e;
    color: #e0e0e0;
    border: none;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #2a82da;
    color: #fff;
}
QTabWidget::pane {
    border: 1px solid #353535;
    background: #181c24;
}
QTabBar::tab {
    background: #23272e;
    color: #e0e0e0;
    padding: 8px 20px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #2a82da;
    color: #fff;
}
QTableWidget, QTableView {
    background-color: #181c24;
    alternate-background-color: #23272e;
    color: #e0e0e0;
    gridline-color: #353535;
    selection-background-color: #2a82da;
    selection-color: #fff;
    border: 1px solid #353535;
}
QHeaderView::section {
    background-color: #23272e;
    color: #e0e0e0;
    border: 1px solid #353535;
    font-weight: bold;
    font-size: 10pt;
    padding: 6px;
}
QGroupBox {
    background-color: #23272e;
    border: 1px solid #353535;
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 10px;
    color: #e0e0e0;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
    color: #2a82da;
}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #23272e;
    color: #e0e0e0;
    border: 1px solid #353535;
    padding: 6px;
    border-radius: 3px;
    font-size: 11pt;
}
QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
    border: none;
    background: transparent;
}
QPushButton {
    background-color: #23272e;
    color: #e0e0e0;
    border: 1px solid #353535;
    padding: 8px 16px;
    border-radius: 3px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #353535;
}
QPushButton:disabled {
    background-color: #23272e;
    color: #888888;
    border: 1px solid #353535;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: #23272e;
    border: 1px solid #353535;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #353535;
    border-radius: 4px;
}
QListWidget, QListView {
    background-color: #181c24;
    color: #e0e0e0;
    border: 1px solid #353535;
}
QLabel {
    color: #e0e0e0;
}
""")
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Not Connected to TWS")
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout with splitters for professional look
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel (Watchlist and Trading)
        left_panel = QWidget()
        left_panel.setFixedWidth(380)
        left_panel.setStyleSheet("""
            QWidget {
                background-color: #1a2332;
                border-right: 2px solid #444444;
            }
        """)
        
        left_layout = QVBoxLayout()
        
        # Watchlist
        self.watchlist_widget = AdvancedWatchlistWidget()
        left_layout.addWidget(self.watchlist_widget)
        
        # Trading panel
        self.trading_panel = ProfessionalTradingPanel(self.ibkr_connection)
        left_layout.addWidget(self.trading_panel)
        
        left_panel.setLayout(left_layout)
        main_splitter.addWidget(left_panel)
        
        # Center panel (Charts and main content)
        center_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Chart controls
        chart_container = QWidget()
        chart_layout = QVBoxLayout()
        
        self.chart_controls = ChartControlsWidget()
        chart_layout.addWidget(self.chart_controls)
        
        # Main tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444444;
                background-color: #0d1421;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: white;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #1e3a5f;
                border-bottom: 2px solid #00d4ff;
            }
            QTabBar::tab:hover {
                background-color: #3a3a3a;
            }
        """)
        
        # Chart tab
        self.chart_widget = ProfessionalTradingChart()
        self.tab_widget.addTab(self.chart_widget, "Chart")
        
        # Portfolio tab
        self.portfolio_widget = EnhancedPortfolioWidget(self.ibkr_connection)
        self.tab_widget.addTab(self.portfolio_widget, "Portfolio")
        
        # Screener tab
        self.screener_widget = AdvancedScreenerWidget()
        self.tab_widget.addTab(self.screener_widget, "Screener")
        
        # Orders tab
        self.orders_widget = OrdersWidget(self.ibkr_connection)
        self.tab_widget.addTab(self.orders_widget, "Orders")
        
        chart_layout.addWidget(self.tab_widget)
        chart_container.setLayout(chart_layout)
        
        center_splitter.addWidget(chart_container)
        
        main_splitter.addWidget(center_splitter)
        
        # Right panel (News and additional info)
        right_panel = QWidget()
        right_panel.setFixedWidth(320)
        right_panel.setStyleSheet("""
            QWidget {
                background-color: #1a2332;
                border-left: 2px solid #444444;
            }
        """)
        
        right_layout = QVBoxLayout()
        
        # News widget
        self.news_widget = EnhancedNewsWidget(self.ibkr_connection)
        right_layout.addWidget(self.news_widget)
        
        right_panel.setLayout(right_layout)
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        main_splitter.setSizes([380, 1000, 320])
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(main_splitter)
        central_widget.setLayout(main_layout)
    
    def create_menu_bar(self):
        """Create the professional menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        new_action = QAction('New Workspace', self)
        new_action.setShortcut('Ctrl+N')
        file_menu.addAction(new_action)
        
        save_action = QAction('Save Workspace', self)
        save_action.setShortcut('Ctrl+S')
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Connection menu
        connection_menu = menubar.addMenu('Connection')
        
        connect_action = QAction('Connect to TWS...', self)
        connect_action.setShortcut('Ctrl+T')
        connect_action.triggered.connect(self.show_connection_dialog)
        connection_menu.addAction(connect_action)
        
        disconnect_action = QAction('Disconnect', self)
        disconnect_action.triggered.connect(self.disconnect_from_tws)
        connection_menu.addAction(disconnect_action)
        
        connection_menu.addSeparator()
        
        # Client ID submenu
        client_menu = connection_menu.addMenu('Client ID')
        for i in range(1, 11):
            client_action = QAction(f'Client ID {i}', self)
            client_action.triggered.connect(lambda checked, cid=i: self.set_client_id(cid))
            client_menu.addAction(client_action)
        
        # Trading menu
        trading_menu = menubar.addMenu('Trading')
        
        quick_buy_action = QAction('Quick Buy', self)
        quick_buy_action.setShortcut('Ctrl+B')
        trading_menu.addAction(quick_buy_action)
        
        quick_sell_action = QAction('Quick Sell', self)
        quick_sell_action.setShortcut('Ctrl+Shift+S')
        trading_menu.addAction(quick_sell_action)
        
        trading_menu.addSeparator()
        
        cancel_all_action = QAction('Cancel All Orders', self)
        cancel_all_action.triggered.connect(self.cancel_all_orders)
        trading_menu.addAction(cancel_all_action)
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        fullscreen_action = QAction('Toggle Fullscreen', self)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        view_menu.addSeparator()
        
        # Layout submenu
        layout_menu = view_menu.addMenu('Layout')
        
        default_layout_action = QAction('Default Layout', self)
        layout_menu.addAction(default_layout_action)
        
        trading_layout_action = QAction('Trading Layout', self)
        layout_menu.addAction(trading_layout_action)
        
        analysis_layout_action = QAction('Analysis Layout', self)
        layout_menu.addAction(analysis_layout_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        shortcuts_action = QAction('Keyboard Shortcuts', self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        help_menu.addSeparator()
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_connections(self):
        """Setup signal connections between widgets"""
        # Watchlist to chart and trading
        self.watchlist_widget.symbol_selected.connect(self.on_symbol_selected)
        
        # Chart controls
        self.chart_controls.timeframe_changed.connect(self.on_timeframe_changed)
        
        # Trading panel signals
        self.trading_panel.order_placed.connect(self.on_order_placed)
        
    def setup_timers(self):
        """Setup update timers"""
        # Main update timer - Faster updates for real-time feel
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(1000)  # Update every 1 second instead of 2
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update status every second
    
    def show_connection_dialog(self):
        """Show connection dialog"""
        dialog = ConnectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            params = dialog.get_connection_params()
            self.connect_to_tws(**params)
    
    def connect_to_tws(self, host="127.0.0.1", port=7496, client_id=1):
        """Connect to TWS/Gateway with specified parameters"""
        try:
            success = self.ibkr_connection.connect(host, port, client_id)
            if success:
                self.status_bar.showMessage(f"Connected to TWS - Client ID: {client_id}")
                self.trading_panel.update_connection_status(True)
                
                # Start data worker
                symbols = self.watchlist_widget.watchlist
                self.data_worker = DataUpdateWorker(symbols, self.ibkr_connection)
                self.data_worker.data_ready.connect(self.on_market_data_update)
                self.data_worker.portfolio_ready.connect(self.on_portfolio_update)
                self.data_worker.orders_ready.connect(self.on_orders_update)
                self.data_worker.trades_ready.connect(self.on_trades_update)
                self.data_worker.error_occurred.connect(self.on_data_error)
                self.data_worker.start()
                
                QMessageBox.information(self, "Connection Success", 
                                      f"Successfully connected to TWS!\n\n"
                                      f"Host: {host}\n"
                                      f"Port: {port}\n"
                                      f"Client ID: {client_id}")
            else:
                self.status_bar.showMessage("Connection failed - Using demo mode")
                QMessageBox.warning(self, "Connection Failed", 
                                  "Failed to connect to TWS. Using demo mode (paper trading fallbacks).\n\n"
                                  "Please ensure:\n"
                                  "TWS or Gateway is running\n"
                                  "API is enabled in TWS\n"
                                  "Correct host and port")
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Error connecting to TWS:\n{str(e)}")
    
    def disconnect_from_tws(self):
        """Disconnect from TWS"""
        try:
            if self.data_worker:
                self.data_worker.stop()
                self.data_worker.wait()
                self.data_worker = None
            
            self.ibkr_connection.disconnect()
            self.status_bar.showMessage("Disconnected from TWS")
            self.trading_panel.update_connection_status(False)
            
            QMessageBox.information(self, "Disconnected", "Successfully disconnected from TWS")
        except Exception as e:
            QMessageBox.critical(self, "Disconnection Error", f"Error disconnecting:\n{str(e)}")
    
    def set_client_id(self, client_id):
        """Set client ID for connection"""
        if self.ibkr_connection.connected:
            reply = QMessageBox.question(
                self, "Change Client ID", 
                f"Disconnect and reconnect with Client ID {client_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.disconnect_from_tws()
                self.connect_to_tws(client_id=client_id)
        else:
            self.connect_to_tws(client_id=client_id)
    
    def on_symbol_selected(self, symbol: str):
        """Handle symbol selection from watchlist"""
        self.trading_panel.set_selected_symbol(symbol)
        self.chart_widget.update_chart(symbol)
        self.status_bar.showMessage(f"Selected: {symbol}")
        self.news_widget.update_news_for_symbol(symbol)
    
    def on_timeframe_changed(self, timeframe: str, period: str):
        """Handle timeframe change from chart controls"""
        if hasattr(self.chart_widget, 'symbol') and self.chart_widget.symbol:
            self.chart_widget.update_chart(self.chart_widget.symbol, timeframe, period)
    
    def on_order_placed(self, symbol: str, order_details: str):
        """Handle order placement"""
        self.status_bar.showMessage(f"Order placed: {order_details}")
    
    def on_market_data_update(self, symbol: str, data: dict):
        """Handle market data updates with proper validation"""
        print(f"[MAIN] Market data update for {symbol}: {data}")
        
        # Update watchlist first
        self.watchlist_widget.update_symbol_data(symbol, data)

        # Update trading panel
        self.trading_panel.update_market_data(symbol, data)

        # Update status based on data source
        source = data.get('source', '')
        if source in ['Yahoo Finance (Demo)', 'Yahoo Finance']:
            msg = ("Quotes: Yahoo Finance | TWS: Connected"
                if self.ibkr_connection.connected
                else "Quotes: Yahoo Finance | TWS: Disconnected")
        elif source == 'Mock Data (Development)':
            msg = ("Quotes: Mock Data | TWS: Connected"
                if self.ibkr_connection.connected
                else "Quotes: Mock Data | TWS: Disconnected")
        else:
            msg = ("Quotes: Live | TWS: Connected"
                if self.ibkr_connection.connected
                else "Quotes: Live | TWS: Disconnected")
        self.status_bar.showMessage(msg)


    def on_portfolio_update(self, portfolio_data: dict):
        """Handle portfolio updates"""
        print(f"[MAIN] Portfolio update received: {portfolio_data}")
        self.portfolio_widget.update_portfolio(portfolio_data)
    
    def on_orders_update(self, open_orders):
        """Handle orders updates"""
        self.orders_widget.update_orders(open_orders)
    
    def on_trades_update(self, executions):
        """Handle trades updates"""
        self.orders_widget.update_trades(executions)
    
    def on_data_error(self, error_message: str):
        """Handle data update errors"""
        print(f"Data error: {error_message}")
    
    def update_data(self):
        """Update data when not using background worker"""
        if not self.data_worker:
            print("[MAIN] Manual data update triggered")
            connection_working = False
            
            # Update market data
            for symbol in self.watchlist_widget.watchlist:
                data = self.ibkr_connection.get_real_time_data(symbol)
                if data.get('source') not in ['No TWS Data', 'Mock Data (Development)']:
                    connection_working = True
                self.on_market_data_update(symbol, data)
            
            # IMPORTANT: Also update portfolio data manually
            try:
                portfolio_data = self.ibkr_connection.get_portfolio_data()
                self.on_portfolio_update(portfolio_data)
            except Exception as e:
                print(f"Error updating portfolio: {e}")


    def update_status(self):
        """Update status bar with current time and connection status"""
        current_time = datetime.now().strftime("%H:%M:%S")
        connection_status = "Connected" if self.ibkr_connection.connected else "Disconnected (Paper Mode)"
        self.status_bar.showMessage(f"{connection_status} | {current_time}")
    
    def cancel_all_orders(self):
        """Cancel all open orders"""
        reply = QMessageBox.question(
            self, "Cancel All Orders", 
            "Are you sure you want to cancel ALL open orders?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.ibkr_connection.cancel_all_orders()
            QMessageBox.information(self, "Orders Cancelled", "All open orders have been cancelled")
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        shortcuts_text = """
KEYBOARD SHORTCUTS

Connection:
Ctrl+T          Connect to TWS
Ctrl+D          Disconnect

Trading:
Ctrl+B          Quick Buy
Ctrl+Shift+S    Quick Sell
Ctrl+C          Cancel All Orders

View:
F11             Toggle Fullscreen
Ctrl+1          Chart Tab
Ctrl+2          Portfolio Tab
Ctrl+3          Screener Tab
Ctrl+4          Orders Tab

General:
Ctrl+N          New Workspace
Ctrl+S          Save Workspace
Ctrl+Q          Exit
        """
        
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
<h2>Professional Trading Platform v3.0</h2>
<p>A comprehensive trading platform built with PyQt6 and Interactive Brokers API integration.</p>

<h3>Features:</h3>
<ul>
<li>Real-time market data with bid/ask spreads</li>
<li>Professional candlestick charts with technical indicators</li>
<li>Advanced order management with bracket orders</li>
<li>Portfolio tracking with P&L analysis</li>
<li>Stock screener with multiple filters</li>
<li>Financial news feed</li>
<li>Multiple client ID support</li>
<li>Professional TWS-style interface</li>
</ul>

<h3>Technical Stack:</h3>
<ul>
<li>PyQt6 for GUI</li>
<li>ib_insync for Interactive Brokers API</li>
<li>matplotlib for charting</li>
</ul>
"""
        
        QMessageBox.information(self, "About", about_text)

def main():
    """Main application entry point with WebEngine fix"""
    import warnings
    import sys
    from PyQt6.QtCore import Qt, QCoreApplication
    
    warnings.filterwarnings("ignore", category=UserWarning, message="pkg_resources is deprecated as an API*")
    
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    
    # Import QtWebEngineWidgets after setting the attribute
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        print("[WEBENGINE] Successfully imported QtWebEngineWidgets after setting attribute")
    except ImportError as e:
        print(f"[WEBENGINE] Import failed: {e}")
        print("Please install with: pip install PyQt6-WebEngine")
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Professional Trading Platform")
    app.setApplicationVersion("3.0")
    app.setOrganizationName("Trading Solutions")
    
    try:
        # Create and show main window
        window = ProfessionalTradingPlatform()
        window.show()
        
        # Your welcome message code...
        
        sys.exit(app.exec())
        
    except Exception as e:
        import traceback
        print(f"Startup error: {e}")
        print(traceback.format_exc())
        
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Icon.Critical)
        error_msg.setWindowTitle("Startup Error")
        error_msg.setText("Failed to start the trading platform")
        error_msg.setInformativeText(f"Error details:\n{str(e)}")
        error_msg.exec()
        sys.exit(1)
        
if __name__ == "__main__":
    main()