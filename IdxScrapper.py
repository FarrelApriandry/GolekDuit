
"""
IdxScrapper.py

This script scrapes company profile and market data from the Indonesia Stock Exchange (IDX) website for a given list of stock tickers. It extracts fundamental data using Nuxt.js payloads, fetches real-time market data using Yahoo Finance, calculates technical indicators, and exports the results to a JSON file.

Features:
- Robust HTML extraction with retry logic
- Nuxt.js state extraction using Node.js
- Real-time market data and technical analysis (Fibonacci, MA20, volume breakout)
- Batch processing for multiple tickers
- English variable names and documentation
"""

from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import asyncio
import sys
import subprocess
import os
from datetime import datetime
import random
import yfinance as yf

async def scrape_idx_company(ticker_symbol: str, date_str: str, time_str: str):
    """
    Scrape IDX company profile and market data for a given ticker symbol.

    Args:
        ticker_symbol (str): Stock ticker symbol (e.g., 'BBCA').
        date_str (str): Date string in DD-MM-YYYY format.
        time_str (str): Time string in HH.MM.SS format.
    """
    ticker = ticker_symbol.upper()
    html_url = f'https://www.idx.co.id/id/perusahaan-tercatat/profil-perusahaan-tercatat/{ticker}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }

    print(f"\n📡 [TARGET: {ticker}] Accessing IDX website...")

    html_text = ""
    max_retries = 3

    try:
        # 1. HTML Extraction with Auto-Retry
        for attempt in range(max_retries):
            try:
                async with requests.AsyncSession(impersonate="chrome120", headers=headers) as session:
                    if attempt > 0:
                        await session.get("https://www.idx.co.id/", timeout=15.0)
                        await asyncio.sleep(2)

                    response = await session.get(html_url, timeout=20.0)

                    if response.status_code == 200:
                        html_text = response.text
                        break  # Success, exit retry loop
                    elif response.status_code in [503, 403]:
                        print(f"⚠️ [ATTEMPT {attempt+1}/{max_retries}] Blocked by Cloudflare (Status {response.status_code}).")
                        retry_delay = random.uniform(5.0, 9.0)
                        print(f"   Waiting {retry_delay:.2f} seconds before retrying...")
                        await asyncio.sleep(retry_delay)
                    else:
                        print(f"❌ Failed to load HTML for {ticker}. Status Code: {response.status_code}")
                        return
            except Exception as e:
                print(f"⚠️ [ATTEMPT {attempt+1}/{max_retries}] Connection error: {e}")
                await asyncio.sleep(5)

        if not html_text:
            print(f"❌ Giving up on {ticker}. Security is too strict, skipping...")
            return

        # 2. Extract Fundamental Data (via Nuxt/Node.js)
        print(f"✅ HTML success! Extracting Nuxt.js payload for {ticker}...")
        soup = BeautifulSoup(html_text, 'html.parser')

        nuxt_script = None
        for script in soup.find_all('script'):
            if script.string and 'window.__NUXT__' in script.string:
                nuxt_script = script.string
                break

        if not nuxt_script:
            print(f"❌ Failed to find Nuxt.js state for {ticker}!")
            return

        js_hack = f"""
        const window = {{}};
        const document = {{}};
        const navigator = {{}};
        {nuxt_script}
        console.log(JSON.stringify(window.__NUXT__));
        """

        with open("idx_bypass.js", "w", encoding="utf-8") as f:
            f.write(js_hack)

        process = subprocess.run(
            ["node", "idx_bypass.js"],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if process.returncode != 0:
            print(f"❌ Node.js Error: {process.stderr}")
            return

        nuxt_data = json.loads(process.stdout)
        if os.path.exists("idx_bypass.js"):
            os.remove("idx_bypass.js")

        print(f"🧹 Cleaning up web UI artifacts...")
        try:
            profile_data = nuxt_data["data"][0]["profileData"]
        except (KeyError, IndexError):
            profile_data = nuxt_data

        # 3. Inject Real-Time Price & Technical Analysis (via yfinance)
        print(f"📈 Fetching Market Data & Calculating Technicals for {ticker}...")
        try:
            yf_ticker = yf.Ticker(f"{ticker}.JK")

            # Fetch 1 month history
            hist = yf_ticker.history(period="1mo")

            if hist.empty:
                print(f"⚠️ [YFINANCE WARNING] Empty history data for {ticker}. Possibly delisted/suspended.")
                profile_data['Swing_Data'] = None
            else:
                # Prepare today's and previous day's data
                current_day = hist.iloc[-1]
                prev_day = hist.iloc[-2] if len(hist) > 1 else current_day

                current_close = float(current_day['Close'])
                prev_close = float(prev_day['Close'])
                volume_today = int(current_day['Volume'])

                # Find 30-day high/low
                highest_30d = float(hist['High'].max())
                lowest_30d = float(hist['Low'].min())

                # Calculate Fibonacci Retracement
                fibo_382 = highest_30d - ((highest_30d - lowest_30d) * 0.382)
                fibo_500 = highest_30d - ((highest_30d - lowest_30d) * 0.500)
                fibo_618 = highest_30d - ((highest_30d - lowest_30d) * 0.618)

                # Detect Volume Breakout & MA20
                hist_5d = hist.tail(5)
                avg_vol_5d = float(hist_5d['Volume'].mean())
                is_volume_breakout = volume_today > (avg_vol_5d * 1.5)

                ma20 = float(hist['Close'].tail(20).mean()) if len(hist) >= 20 else current_close

                swing_data = {
                    "market_data": {
                        "current_close": current_close,
                        "prev_close": prev_close,
                        "highest_30d": highest_30d,
                        "lowest_30d": lowest_30d,
                        "volume_today": volume_today,
                        "volume_ma5": avg_vol_5d
                    },
                    "technical_signals": {
                        "fibo_levels": {
                            "level_382": round(fibo_382, 2),
                            "level_500": round(fibo_500, 2),
                            "level_618": round(fibo_618, 2)
                        },
                        "ma20": round(ma20, 2),
                        "is_volume_breakout": is_volume_breakout
                    }
                }

                print(f"💵 Close: Rp {current_close} | Volume Breakout: {is_volume_breakout} | Fibo 50%: Rp {fibo_500:.1f}")

                profile_data['Swing_Data'] = swing_data

        except Exception as e:
            profile_data['Swing_Data'] = None
            print(f"❌ Failed to calculate yfinance data for {ticker}: {e}")

        # 4. Export to JSON
        print(f"📁 Preparing output directory...")

        base_folder = "data/daily_scrapes"
        os.makedirs(base_folder, exist_ok=True)

        clean_date = date_str.replace("-", "")
        split_date = clean_date[:2], clean_date[2:4], clean_date[4:]
        format_date = f"{split_date[2]}{split_date[1]}{split_date[0]}"

        clean_time = time_str.replace(".", "")[:4]  # Take HHMM only

        filename = f"{format_date}_{clean_time}_swing_candidates.json"
        full_file_path = os.path.join(base_folder, filename)

        with open(full_file_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=4, ensure_ascii=False)

        print(f"🎉 DATA {ticker} SUCCESSFULLY EXPORTED!")
        return profile_data

    except Exception as e:
        print(f"❌ System Crash for {ticker}: {e}")
        return None

# --- MAIN AUTOMATION ENTRY POINT ---
async def main():
    """
    Main entry point for batch scraping IDX company data.
    Prompts user for input (comma-separated tickers or a .txt file), then processes each ticker.
    """
    print("=== IDX HYBRID TERMINAL (Fundamental + Live Price) ===")
    print("Input Options:")
    print("1. Type tickers separated by commas (e.g., CITY, MNCN, BBCA)")
    print("2. Type a .txt filename (e.g., target.txt)")

    user_input = input("Enter Target: ").strip()

    if user_input.endswith('.txt'):
        try:
            with open(user_input, 'r') as f:
                ticker_list = [line.strip().upper() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"❌ File '{user_input}' not found!")
            return
    else:
        ticker_list = [e.strip().upper() for e in user_input.split(',')]

    print(f"\nTotal targets to scrape: {len(ticker_list)} tickers")

    # Take timestamp ONCE for the whole batch
    now = datetime.now()
    current_date = now.strftime("%d-%m-%Y")
    current_time = now.strftime("%H.%M.%S")

    all_candidates = []

    for i, ticker in enumerate(ticker_list):
        candidate = await scrape_idx_company(ticker, current_date, current_time)
        if candidate:
            all_candidates.append(candidate)

        if i < len(ticker_list) - 1:
            delay = random.uniform(3.5, 7.5)
            print(f"\n⏳ [ANTI-BOT] Waiting {delay:.2f} seconds...")
            await asyncio.sleep(delay)

    print("\n✅ ALL TARGETS SUCCESSFULLY SCRAPED!")


    """
    BATCH EXPORT LOGIC:
    - If we have any valid candidates, we create a single JSON file containing all of them with a timestamp in the filename.
    - The JSON structure includes metadata about the scrape (date, time, total candidates) and an array of candidate data.
    """
    if all_candidates:
        print(f"📁 Preparing output directory for {len(all_candidates)} candidates...")
        base_folder = "data/daily_scrapes"
        os.makedirs(base_folder, exist_ok=True)

        clean_date = current_date.replace("-", "")
        split_date = clean_date[:2], clean_date[2:4], clean_date[4:]
        format_date = f"{split_date[2]}{split_date[1]}{split_date[0]}"
        clean_time = current_time.replace(".", "")[:4]

        filename = f"{format_date}_{clean_time}_swing_candidates_batch.json"
        full_file_path = os.path.join(base_folder, filename)

        final_payload = {
            "metadata": {
                "scrape_date": current_date,
                "scrape_time": current_time,
                "total_candidates": len(all_candidates)
            },
            "candidates": all_candidates
        }

        with open(full_file_path, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, indent=4, ensure_ascii=False)

        print(f"🎉 BATCH DATA SUCCESSFULLY EXPORTED! File: {filename}")
        print(f"📂 Location: {os.path.abspath(full_file_path)}")
    else:
        print("⚠️ No valid candidates were scraped. No batch file created.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())