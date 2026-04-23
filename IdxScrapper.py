

"""
IdxScrapper.py

This script scrapes company profiles and market data from the Indonesia Stock Exchange (IDX) website for a given list of stock tickers. It extracts fundamental data using Nuxt.js payloads, fetches real-time market data using Yahoo Finance, calculates technical indicators, and exports the results to a JSON file.

Features:
- Robust HTML extraction with retry logic
- Nuxt.js state extraction using Node.js
- Real-time market data and technical analysis (Fibonacci retracement, MA20, volume breakout)
- Batch processing for multiple tickers
- English variable names and documentation throughout
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
    Returns:
        dict or None: The profile data with technical analysis, or None if failed.
    """
    ticker = ticker_symbol.upper()
    html_url = f'https://www.idx.co.id/id/perusahaan-tercatat/profil-perusahaan-tercatat/{ticker}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }

    print(f"\n[INFO] [TARGET: {ticker}] Accessing IDX website...")

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
                        print(f"[WARNING] [ATTEMPT {attempt+1}/{max_retries}] Blocked by Cloudflare (Status {response.status_code}).")
                        retry_delay = random.uniform(5.0, 9.0)
                        print(f"   Waiting {retry_delay:.2f} seconds before retrying...")
                        await asyncio.sleep(retry_delay)
                    else:
                        print(f"[ERROR] Failed to load HTML for {ticker}. Status Code: {response.status_code}")
                        return
            except Exception as e:
                print(f"[WARNING] [ATTEMPT {attempt+1}/{max_retries}] Connection error: {e}")
                await asyncio.sleep(5)

        if not html_text:
            print(f"[ERROR] Giving up on {ticker}. Security is too strict, skipping...")
            return

        # 2. Extract Fundamental Data (via Nuxt/Node.js)
        print(f"[INFO] HTML successfully retrieved! Extracting Nuxt.js payload for {ticker}...")
        soup = BeautifulSoup(html_text, 'html.parser')

        nuxt_script = None
        for script in soup.find_all('script'):
            if script.string and 'window.__NUXT__' in script.string:
                nuxt_script = script.string
                break

        if not nuxt_script:
            print(f"[ERROR] Failed to find Nuxt.js state for {ticker}!")
            return

        js_payload = f"""
        const window = {{}};
        const document = {{}};
        const navigator = {{}};
        {nuxt_script}
        console.log(JSON.stringify(window.__NUXT__));
        """

        with open("idx_bypass.js", "w", encoding="utf-8") as f:
            f.write(js_payload)

        process = subprocess.run(
            ["node", "idx_bypass.js"],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if process.returncode != 0:
            print(f"[ERROR] Node.js Error: {process.stderr}")
            return

        nuxt_data = json.loads(process.stdout)
        if os.path.exists("idx_bypass.js"):
            os.remove("idx_bypass.js")

        print(f"[INFO] Cleaning up web UI artifacts...")
        try:
            profile_data = nuxt_data["data"][0]["profileData"]
        except (KeyError, IndexError):
            profile_data = nuxt_data

        # 3. Inject Real-Time Price & Technical Analysis (via yfinance)
        print(f"[INFO] Fetching market data and calculating technical indicators for {ticker}...")
        try:
            yf_ticker = yf.Ticker(f"{ticker}.JK")

            # Run yfinance in a background thread for async performance
            hist = await asyncio.to_thread(yf_ticker.history, period="1mo")

            if hist.empty:
                print(f"[WARNING] [YFINANCE] Empty history data for {ticker}. Possibly delisted or suspended.")
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

                print(f"[INFO] Close: Rp {current_close} | Volume Breakout: {is_volume_breakout} | Fibo 50%: Rp {fibo_500:.1f}")

                profile_data['TickerSymbol'] = ticker
                profile_data['Swing_Data'] = swing_data

        except Exception as e:
            profile_data['Swing_Data'] = None
            print(f"[ERROR] Failed to calculate yfinance data for {ticker}: {e}")

        # 4. Export to JSON
        print(f"[INFO] Preparing output directory...")

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

        print(f"[SUCCESS] Data for {ticker} successfully exported!")
        return profile_data

    except Exception as e:
        print(f"[ERROR] System crash for {ticker}: {e}")
        return None
    

async def fetch_idx_tickers():
    """
    The Zero Trust Seeker: Bypass IDX WAF entirely by scraping the live, 
    community-maintained list of companies from Wikipedia.
    """
    print("\n[INFO] Bypassing IDX WAF: Scraping active tickers from Wikipedia...")
    
    # URL Daftar Emiten di Wikipedia
    url = "https://id.wikipedia.org/wiki/Daftar_perusahaan_yang_tercatat_di_Bursa_Efek_Indonesia"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        async with requests.AsyncSession(impersonate="chrome120", headers=headers) as session:
            response = await session.get(url, timeout=20.0)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Wikipedia biasanya pake class 'wikitable' buat tabel datanya
                tables = soup.find_all('table', class_='wikitable')
                
                tickers = []
                for table in tables:
                    rows = table.find_all('tr')[1:] # Skip header row
                    
                    for row in rows:
                        cols = row.find_all(['td', 'th'])
                        if len(cols) >= 2:
                            # Kolom ke-2 (index 1) adalah "Kode"
                            kode_text = cols[1].get_text(strip=True)
                            
                            # Format di Wiki biasanya "BEI: AALI"
                            if "BEI:" in kode_text:
                                ticker = kode_text.split("BEI:")[1].strip()
                                
                                # Bersihin kalo ada footnote kayak BBCA[1]
                                ticker = ticker.split('[')[0].strip()
                                
                                # Pastiin panjangnya 4 huruf (standar ticker IDX)
                                if len(ticker) == 4 and ticker.isalpha():
                                    tickers.append(ticker)
                
                # Hilangkan duplikat dan urutkan sesuai abjad
                tickers = sorted(list(set(tickers)))
                print(f"[SUCCESS] Intercepted {len(tickers)} active tickers from Wikipedia!")
                return tickers
            else:
                print(f"[ERROR] Failed to scrape Wikipedia. Status Code: {response.status_code}")
                return []
                
    except Exception as e:
        print(f"[ERROR] Wikipedia scraping failed: {e}")
        return []


# --- MAIN AUTOMATION ENTRY POINT ---
async def process_with_semaphore(semaphore, ticker, current_date, current_time):
    """
    Wrap the scrape function with a semaphore for concurrency control.
    Args:
        semaphore (asyncio.Semaphore): The semaphore object for limiting concurrency.
        ticker (str): The stock ticker symbol.
        current_date (str): The current date string.
        current_time (str): The current time string.
    Returns:
        dict or None: The result of the scrape function.
    """
    async with semaphore:
        return await scrape_idx_company(ticker, current_date, current_time)

async def main():
    print("=== MONEY WATCHER: AUTONOMOUS SEEKER ENGINE ===")

    # 1. Fetch all tickers from IDX
    ticker_list = await fetch_idx_tickers()

    if not ticker_list:
        print("[ERROR] Cannot proceed without tickers. Exiting...")
        return

    # Take timestamp ONCE for the whole batch
    now = datetime.now()
    current_date = now.strftime("%d-%m-%Y")
    current_time = now.strftime("%H.%M.%S")

    # 2. Set up concurrency limiter
    MAX_CONCURRENT_TASKS = 15  # Process 15 stocks concurrently
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    print(f"\n[INFO] Launching parallel engine: {MAX_CONCURRENT_TASKS} concurrent tasks...")

    # 3. Dispatch all tickers to the async event loop
    tasks = [process_with_semaphore(semaphore, ticker, current_date, current_time) for ticker in ticker_list]

    # Gather results in parallel
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter valid results (exclude errors/None)
    all_candidates = [res for res in raw_results if res and not isinstance(res, Exception)]

    print(f"\n[SUCCESS] All {len(all_candidates)} targets successfully scraped and processed!")

    # BATCH EXPORT LOGIC
    if all_candidates:
        print(f"[INFO] Preparing output directory for {len(all_candidates)} candidates...")
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

        print(f"[SUCCESS] Batch data successfully exported! File: {filename}")
        print(f"[INFO] Location: {os.path.abspath(full_file_path)}")
    else:
        print("[WARNING] No valid candidates were scraped. No batch file created.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())