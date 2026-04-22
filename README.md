# MoneyWatcher

A comprehensive stock analysis tool that scrapes fundamental data from the Indonesia Stock Exchange (IDX), combines it with real-time market data and technical analysis, and generates swing trading alerts via Telegram.

## Overview

MoneyWatcher is a hybrid system consisting of two main components:
1. **IdxScrapper.py** - Python script that scrapes company profiles and fundamental data from IDX website
2. **GolekDuitCore.js** - Node.js script that analyzes scraped data for swing trading setups and sends Telegram alerts

The system automatically:
- Scrapes fundamental data from IDX using Nuxt.js state extraction
- Fetches real-time market data and calculates technical indicators (Fibonacci retracements, MA20, volume breakout)
- Validates stocks against swing trading criteria (price near Fibonacci support levels)
- Calculates trade plans (entry, take profit, stop loss, risk/reward ratio)
- Sends formatted alerts to Telegram channel

## Features

### IdxScrapper.py
- Robust HTML extraction with retry logic and Cloudflare bypass
- Nuxt.js state extraction using Node.js subprocess
- Real-time market data via Yahoo Finance API
- Technical analysis: Fibonacci retracement levels (38.2%, 50%, 61.8%), MA20, volume breakout detection
- Batch processing for multiple stock tickers
- Automatic JSON export with timestamped filenames
- Anti-bot measures with randomized delays

### GolekDuitCore.js
- Automatic detection of latest batch scrape file
- Swing trading validation based on Fibonacci support levels
- Trade plan calculation with configurable risk/reward ratios
- Telegram integration for instant alerts
- Formatted message output with emojis and markdown
- Console output for monitoring and debugging

## Project Structure

```
MoneyWatcher/
├── IdxScrapper.py                # Python IDX scraper
├── GolekDuitCore.js              # Node.js swing analyzer & alerter
├── package.json                  # Node.js dependencies
├── .env                          # Environment variables (API keys)
├── target.txt                    # List of stock tickers to scan
├── README.md                     # This file
├── ANALYSIS_TODO.md              # Analysis notes
├── .gitignore                    # Git ignore rules
└── data/
    └── daily_scrapes/            # Scraped data storage
        ├── 20260423_0109_swing_candidates.json
        ├── 20260423_0109_swing_candidates_batch.json
        └── ...
```

## Installation

### Prerequisites
- Node.js (v14+ recommended)
- Python (v3.7+ recommended)
- Telegram Bot Token and Chat ID

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/FarrelApriandry/MoneyWatcher.git
   cd MoneyWatcher
   ```

2. **Install Node.js dependencies**
   ```bash
   npm install
   ```

3. **Install Python dependencies**
   ```bash
   pip install curl_cffi beautifulsoup4 yfinance
   ```

4. **Configure environment variables**
   Create a `.env` file in the root directory with:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   GEMINI_API_KEY=your_gemini_api_key  # Optional, for future AI features
   ```

5. **Prepare target stocks**
   Edit `target.txt` with the stock tickers you want to scan (one per line or comma-separated):
   ```
   BTPS
   TLKM
   FORE
   CITY
   MNCN
   ```

## Usage

### Running the Scraper (IdxScrapper.py)
```bash
python IdxScrapper.py
```
When prompted:
1. Enter stock tickers separated by commas (e.g., `BBCA, TLKM, FORE`)
2. OR enter a filename containing tickers (e.g., `target.txt`)

The scraper will:
- Fetch fundamental data from IDX for each ticker
- Retrieve real-time market data and calculate technical indicators
- Save results to timestamped JSON files in `data/daily_scrapes/`

### Running the Analyzer (GolekDuitCore.js)
```bash
node GolekDuitCore.js
```
The analyzer will:
- Automatically detect the latest batch scrape file
- Validate candidates against swing trading criteria
- Calculate trade plans (entry, TP, SL, R/R ratio)
- Send formatted alerts to your Telegram channel
- Display results in the console

### Automated Workflow
For best results, run the scraper first to collect fresh data, then run the analyzer:
```bash
python IdxScrapper.py
# (Enter your targets when prompted)
node GolekDuitCore.js
```

## Configuration

### Swing Trading Parameters
Adjust these in `GolekDuitCore.js` (lines 24-28):
```javascript
const SWING_PARAMETERS = {
    RISK_PERCENT: 0.03,      // Stop Loss 3%
    REWARD_PERCENT: 0.15,    // Take Profit 15%
    FIBONACCI_TOLERANCE: 0.02 // Fibonacci bounce tolerance (± 2%)
};
```

### Telegram Setup
1. Create a bot using [@BotFather](https://t.me/BotFather) on Telegram
2. Get your bot token
3. Get your chat ID (you can use [@userinfobot](https://t.me/userinfobot) to find it)
4. Add both to your `.env` file

## Data Files

### Scraped Data Format
Each scraped stock data includes:
- **Profile Data**: Company information from IDX
- **Swing_Data**: 
  - `market_data`: Current price, previous close, 30-day high/low, volume
  - `technical_signals`: Fibonacci levels, MA20, volume breakout status

### Batch Files
Batch files combine multiple scraped stocks with metadata:
```json
{
  "metadata": {
    "scrape_date": "DD-MM-YYYY",
    "scrape_time": "HH.MM.SS",
    "total_candidates": N
  },
  "candidates": [/* Array of individual stock data */]
}
```

## Technical Details

### IDX Scraping Process
1. **HTML Extraction**: Uses `curl_cffi` with Chrome impersonation to bypass basic protections
2. **Retry Logic**: Automatic retries with exponential backoff for Cloudflare/rate limiting
3. **Nuxt.js State Extraction**: 
   - Extracts `window.__NUXT__` from page scripts
   - Executes via Node.js subprocess to get structured data
4. **Yahoo Finance Integration**: 
   - Fetches 1-month history for technical calculations
   - Calculates Fibonacci retracements from 30-day high/low
   - Computes MA20 and volume breakout signals
5. **Data Export**: Saves structured JSON with proper formatting

### Swing Trading Logic
1. **Fibonacci Support Detection**: Checks if current price is within 2% of:
   - 38.2% retracement level
   - 50% retracement level
   - 61.8% retracement level
2. **Trade Plan Calculation**:
   - Entry: Current closing price
   - Take Profit: Entry + 15% (rounded down)
   - Stop Loss: Entry - 3% (rounded up)
   - Risk/Reward Ratio: Calculated based on rounded prices
3. **Validation**: 
   - Filters out stocks with null/NaN data
   - Only considers stocks bouncing at Fibonacci support
   - Notes volume breakout status in alerts

## Example Output

### Console Output (Analyzer)
```
=== MONEY WATCHER CORE ENGINE ===
[INFO] Processing latest batch: 20260423_0109_swing_candidates_batch.json
[INFO] Analyzing 1 candidate(s) for swing setup...
[WARNING] Skipped BBCA: Invalid market data (contains null/NaN).
[SUCCESS] Trigger: FORE is currently bouncing at Fibonacci support!
[INFO] Validation complete: Found 1 stock(s) ready for swing trading.

[INFO] SWING TRADE PLAN:
┌─────────┬───────────┬──────────────┬────────────┐
│ (index) │ Ticker    │ Entry        │ Take Profit│
├─────────┼───────────┼──────────────┼────────────┤
│    0    │ 'FORE'    │ 'Rp 945'     │ 'Rp 1086'  │
│    1    │ 'FORE'    │ 'Rp 945'     │ 'Rp 876'   │
└─────────┴───────────┴──────────────┴────────────┘
[INFO] Sending alert to Telegram...
[SUCCESS] Alert successfully sent to Telegram channel.
```

### Telegram Alert
```
🎯 *MONEY WATCHER SWING ALERT*
📅 Batch: `20260423_0109_swing_candidates_batch.json`

Found *1 candidate(s)* bouncing at support:

*1. FORE* 
├ Entry : Rp 945
├ Target: Rp 1086 (+15%)
├ Stop L: Rp 876 (-3%)
└ R/R   : 1:5.00

_Disclaimer: Trade at your own risk. Do not FOMO!_
```

## Disclaimer

**MoneyWatcher is for educational and informational purposes only.** 
- This tool provides automated stock analysis based on technical indicators
- It does not constitute financial advice or investment recommendations
- Trading stocks involves substantial risk of loss
- Past performance does not guarantee future results
- Always conduct your own research and consult with a licensed financial advisor
- The developers are not liable for any trading decisions made based on this tool's output

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the ISC License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Indonesia Stock Exchange (IDX) for providing company data
- Yahoo Finance for market data API
- Telegram Bot API for alert notifications
- Open-source libraries: axios, dotenv, node-telegram-bot-api, curl_cffi, beautifulsoup4, yfinance