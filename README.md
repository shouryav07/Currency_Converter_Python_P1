# Currency_Converter_Python_P1
FX Pulse is a modern desktop currency converter built with Python and CustomTkinter that delivers real-time exchange rates, interactive financial charts, offline caching, and a professional dark/light mode interface.

Designed as an engineering-level mini project, the application combines live currency conversion with financial data visualization using Matplotlib and yfinance, while maintaining a smooth and responsive user experience through threaded API operations and SQLite caching

# FX Pulse — Real-time Currency Converter

A professional-grade desktop currency converter with live rates, interactive trend charts,
and a polished dark/light-mode UI — built with **CustomTkinter**, **Matplotlib**, and **yfinance**.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Real-time conversion** | Rates update instantly as you type (ExchangeRate-API) |
| **Interactive trend chart** | Sparkline + candlestick overlays; 1D / 1W / 1M timeframes |
| **30 currency pairs** | USD, EUR, GBP, JPY, INR, CAD, AUD, CHF, CNY, and 21 more |
| **Quick Pairs sidebar** | Click any popular pair to load it instantly |
| **Offline mode** | SQLite cache keeps the last known rates when there's no internet |
| **Dark / Light mode** | Toggle with one click; chart re-themes automatically |
| **Trend indicators** | Green ▲ for rising, Red ▼ for falling, based on regression |

---

## 📁 Project Structure

```
currency_converter/
├── run.py                        # ← Launch the app from here
├── requirements.txt
├── .env.example                  # Copy to .env and add your API keys
├── cache.db                      # Auto-created SQLite cache (offline mode)
└── app/
    ├── __init__.py
    ├── main.py                   # Window + controller
    ├── api_client.py             # Network calls + SQLite cache layer
    ├── utils.py                  # Pure math + formatting helpers
    └── ui_components/
        ├── __init__.py
        ├── header.py             # Top bar (logo, clock, theme toggle)
        ├── converter_card.py     # Hero conversion widget
        ├── trend_graph.py        # Matplotlib chart (sparkline + candlestick)
        └── sidebar.py            # Quick Pairs sidebar
```

---

## 🚀 Quick Start

### 1. Clone / copy the project
```bash
cd currency_converter
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API keys
```bash
cp .env.example .env
# Open .env and fill in your keys:
# EXCHANGE_RATE_API_KEY=your_key_here   (free at exchangerate-api.com)
# ALPHA_VANTAGE_API_KEY=your_key_here   (free at alphavantage.co — optional)
```

> **No key?** The app falls back to the free open.er-api.com endpoint (no key needed,
> slightly fewer currencies) and yfinance for history (also no key needed).

### 5. Run
```bash
python run.py
```

---

## 🔑 API Keys

| Service | Purpose | Free tier |
|---|---|---|
| [ExchangeRate-API](https://www.exchangerate-api.com/) | Live spot rates | 1 500 req/month |
| [Alpha Vantage](https://www.alphavantage.co/support/#api-key) | Optional historical | 25 req/day |
| [yfinance](https://pypi.org/project/yfinance/) | Historical OHLC (**no key needed**) | Unlimited |

yfinance is used by default for historical data — no key required.

---

## 🖥️ System Requirements

- Python **3.10+**
- Works on **macOS**, **Windows**, and **Linux** (with Tk installed)
- On Ubuntu/Debian: `sudo apt-get install python3-tk`

---

## 💡 Usage Tips

- **Type** in the amount field for instant conversion
- **Click ⇅** to swap the pair  
- **Click any row** in the sidebar to load that pair  
- **Toggle 1D / 1W / 1M** buttons above the chart to change the timeframe  
- **Click ⟳ Refresh** to force a live data pull  
- Works **offline** — the last fetched rates are cached in `cache.db`

---

## 🏗️ Architecture Notes

### Threading model
All network calls (`fetch_all_rates`, `fetch_history`) run in daemon threads.
Results are delivered back to the main thread via `widget.after(0, callback, result)` —
this keeps the UI fully responsive during fetches.

### Caching strategy
- **Rates** are cached per base currency with a 1-hour TTL.
- **Historical OHLC** is cached per symbol with a 24-hour TTL.
- On total network failure the app silently falls back to any available stale cache.

### Chart rendering
The Matplotlib figure is created once and mutated on each redraw (`ax.clear()` then
re-plot) rather than recreating the `FigureCanvasTkAgg` object — this avoids flicker
and keeps rendering fast.

---

## 📜 License
MIT — do whatever you like with it.
