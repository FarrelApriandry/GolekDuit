/**
 * MoneyWatcher Core Engine
 *
 * This script analyzes stock swing candidates from the latest daily scrape batch, validates them against swing trading criteria,
 * calculates trade plans, and sends formatted alerts to a Telegram channel.
 *
 * Author: RelApri
 * Date: 23-04-2026
 */
const TelegramBot = require('node-telegram-bot-api');
require('dotenv').config();

const fs = require('fs');
const path = require('path');
const axios = require('axios');
const RAPIDAPI_KEY = process.env.RAPIDAPI_KEY;

// ==========================================
// 🛡️ ZERO TRUST CONFIGURATION
// ==========================================

const telegramToken = process.env.TELEGRAM_BOT_TOKEN;
const telegramChatId = process.env.TELEGRAM_CHAT_ID;
const SCRAPE_DIR = path.join(__dirname, 'data', 'daily_scrapes');
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// ==========================================
// 🚀 TELEGRAM SENDER MODULE
// ==========================================
async function sendTelegramAlert(message) {
    const url = `https://api.telegram.org/bot${telegramToken}/sendMessage`;
    try {
        await axios.post(url, {
            chat_id: telegramChatId,
            text: message,
            parse_mode: 'HTML',
            disable_web_page_preview: true
        });
        console.log("✅ [SUCCESS] Telegram Alert dispatched successfully!");
    } catch (error) {
        console.error("❌ [ERROR] Failed to send Telegram alert. Check token/ID.");
        console.error(error.message);
    }
}

// ==========================================
// 🔍 THE AUTO-DISCOVERY MODULE
// ==========================================
function getLatestBatchFile() {
    if (!fs.existsSync(SCRAPE_DIR)) {
        return null;
    }

    const files = fs.readdirSync(SCRAPE_DIR)
        .filter(file => file.endsWith('.json'))
        .map(file => {
            const filePath = path.join(SCRAPE_DIR, file);
            return {
                name: file,
                time: fs.statSync(filePath).mtime.getTime()
            };
        })
        .sort((a, b) => b.time - a.time);

    return files.length > 0 ? files[0].name : null;
}

// ==============================================
// 🐋 THE MARKETMAKERMOLOGY MODULE (INVEZGO API)
// =============================================
async function checkmarketMakermology(ticker) {
    const url = `https://indonesia-stock-exchange-idx.p.rapidapi.com/api/emiten/tradebook-chart?timeInterval=1m&symbol=${ticker}`;
    try {
        const response = await axios.get(url, {
            headers: {
                'x-rapidapi-host': 'indonesia-stock-exchange-idx.p.rapidapi.com',
                'x-rapidapi-key': RAPIDAPI_KEY
            }
        });

        const data = response.data.data;
        if (!data || !data.buy || !data.sell) return "⚪ Unknown Data";

        if (data.buy.length === 0 || data.sell.length === 0) return "⚪ No Transaction History";

        const lastBuy = data.buy[data.buy.length - 1];
        const lastSell = data.sell[data.sell.length - 1];

        if (!lastBuy.lot || !lastSell.lot) return "⚪ No Lot Data";

        const buyLot = parseInt(lastBuy.lot.raw);
        const sellLot = parseInt(lastSell.lot.raw);
        const totalLot = buyLot + sellLot;

        if (totalLot === 0) return "⚪ No Activity";

        // Formatting number to millions for better readability in alerts
        const formatLot = (num) => (num / 1000000).toFixed(2) + "M";
        const bFormat = formatLot(buyLot);
        const sFormat = formatLot(sellLot);

        // Calculate dominance ratio and determine market maker status
        const buyRatio = buyLot / totalLot;
        const sellRatio = sellLot / totalLot;

        if (buyRatio >= 0.60) {
            return `🐋 STRONG ACC (B: ${bFormat} | S: ${sFormat})`;
        } else if (buyRatio > 0.53 && buyRatio < 0.60) {
            return `📈 NORMAL ACC (B: ${bFormat} | S: ${sFormat})`;
        } else if (sellRatio >= 0.60) {
            return `🚨 STRONG DIST (B: ${bFormat} | S: ${sFormat})`;
        } else if (sellRatio > 0.53 && sellRatio < 0.60) {
            return `📉 NORMAL DIST (B: ${bFormat} | S: ${sFormat})`;
        } else {
            return `⚖️ BALANCED (B: ${bFormat} | S: ${sFormat})`;
        }
    } catch (error) {
        console.error(`[WARNING] Failed to fetch marketmakermology for ${ticker}. Delay/Rate Limit?`);
        return "⚠️ API Error";
    }
}

// ==========================================
// 🧱 THE ORDERBOOK WALL DETECTOR MODULE
// ==========================================
async function checkOrderbookWall(ticker) {
    const url = `https://indonesia-stock-exchange-idx.p.rapidapi.com/api/emiten/${ticker}/orderbook`;
    try {
        const response = await axios.get(url, {
            headers: {
                'x-rapidapi-host': 'indonesia-stock-exchange-idx.p.rapidapi.com',
                'x-rapidapi-key': RAPIDAPI_KEY,
                'Content-Type': 'application/json'
            }
        });

        const data = response.data.data;
        if (!data) return "⚪ Unknown Orderbook";

        let maxOfferLot = 0;
        let maxOfferPrice = 0;
        let maxBidLot = 0;
        let maxBidPrice = 0;

        const offers = data.offer || data.ask || data.asks || data.offers || [];
        const bids = data.bid || data.bids || [];

        // Find the thickest Offer wall (Resistance)
        offers.forEach(o => {
            const lot = parseInt(o.lot || o.volume || 0);
            if (lot > maxOfferLot) {
                maxOfferLot = lot;
                maxOfferPrice = o.price;
            }
        });

        // Find the thickest Bid wall (Support)
        bids.forEach(b => {
            const lot = parseInt(b.lot || b.volume || 0);
            if (lot > maxBidLot) {
                maxBidLot = lot;
                maxBidPrice = b.price;
            }
        });

        const formatLot = (num) => (num / 1000).toFixed(1) + "k";

        let wallStr = "";
        if (maxOfferLot > 0) wallStr += `🧱 Res: ${formatLot(maxOfferLot)} lot @ Rp${maxOfferPrice} | `;
        if (maxBidLot > 0) wallStr += `🛡️ Sup: ${formatLot(maxBidLot)} lot @ Rp${maxBidPrice}`;

        return wallStr !== "" ? wallStr : "⚪ No Wall Detected";

    } catch (error) {
        console.error(`[WARNING] Failed to fetch orderbook for ${ticker}.`);
        return "⚠️ API Error";
    }
}

// ==========================================
// ⚙️ THE FILTRATION ENGINE (MAIN LOGIC)
// ==========================================
async function runFiltrationEngine() {
    console.log("=== MONEY WATCHER: FILTRATION ENGINE ===");
    
    const latestFile = getLatestBatchFile();
    if (!latestFile) {
        console.log("⚠️ [WARNING] No scrape files found in directory.");
        return;
    }

    const filePath = path.join(SCRAPE_DIR, latestFile);
    console.log(`📁 Loading massive payload: ${latestFile} ...`);
    
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const jsonData = JSON.parse(rawData);

    const candidates = jsonData.candidates || [];
    console.log(`🔍 Sifting through ${candidates.length} raw targets...`);

    let validSwings = [];

    candidates.forEach(company => {
        if (!company || !company.Swing_Data) return;
        
        // Check TickerSymbol, then profileData.TickerSymbol, then Symbol, else mark as UNKNOWN
        const ticker = company.TickerSymbol || 
                       (company.profileData && company.profileData.TickerSymbol) || 
                       company.Symbol || 
                       "UNKNOWN";
        
        const swing = company.Swing_Data;
        if (!swing.market_data || !swing.technical_signals) return;

        const close = swing.market_data.current_close;

        // Ticker under 60 IDR or with very low volume is usually not suitable for swing trading due to high volatility and low liquidity.
        if (close <= 60 || swing.market_data.volume_today < 1000) return;

        const fibo500 = swing.technical_signals.fibo_levels.level_500;
        const isBreakout = swing.technical_signals.is_volume_breakout;

        const diffFibo = Math.abs(close - fibo500) / fibo500;
        const isNearFibo = diffFibo <= 0.03;

        if (isBreakout || isNearFibo) {
            const entry = close;
            const target = Math.round(entry * 1.15);
            const stopLoss = Math.round(entry * 0.97);
            
            const risk = entry - stopLoss;
            const reward = target - entry;
            const rrRatio = risk > 0 ? (reward / risk).toFixed(2) : 0;

            let reasonTag = isBreakout ? "🚀 Vol Breakout" : "🛡️ Fibo Bounce";
            if (isBreakout && isNearFibo) reasonTag = "🔥 PERFECT SETUP (Vol+Fibo)";

            validSwings.push({
                ticker,
                entry,
                target,
                stopLoss,
                rrRatio,
                reason: reasonTag
            });
        }
    });

    console.log(`🎯 Found ${validSwings.length} raw swing candidates!`);

    if (validSwings.length === 0) {
        console.log("🤷‍♂️ No good setups today. Cash is king. Skipping Telegram alert.");
        return;
    }

    // ZERO TRUST FILTER: Sort by R/R ratio
    // Take top 10 to avoid overwhelming the Telegram channel with too many alerts.
    validSwings.sort((a, b) => b.rrRatio - a.rrRatio);
    const topSwings = validSwings.slice(0, 10);

    console.log(`🔥 Filtering down to TOP ${topSwings.length} best setups...`);
    console.log(`🕵️‍♂️ Initiating MarketMaker mology Check for Top 10 via Invezgo API...`);

    // ==========================================
    // ✉️ MESSAGE FORMATTING & DISPATCH
    // ==========================================
    let message = `🎯 <b>MONEY WATCHER SWING ALERT</b>\n`;
    message += `📅 Batch: <code>${latestFile}</code>\n\n`;
    message += `Found ${validSwings.length} candidates, showing <b>TOP ${topSwings.length}</b> best R/R:\n\n`;

    let rank = 1;
    for (const s of topSwings) {

        console.log(`[API] Checking Market Maker for ${s.ticker}...`);
        const marketMakerStatus = await checkmarketMakermology(s.ticker);
        
        await sleep(1000);

        console.log(`[API] Checking Orderbook Wall for ${s.ticker}...`);
        const orderbookWall = await checkOrderbookWall(s.ticker);
        
        message += `<b>${rank}. ${s.ticker}</b> [${s.reason}]\n`;
        message += `├ marketMaker: <b>${marketMakerStatus}</b>\n`;
        message += `├ Wall : ${orderbookWall}\n`;
        message += `├ Entry : Rp ${s.entry}\n`;
        message += `├ Target: Rp ${s.target} (+15%)\n`;
        message += `├ Stop L: Rp ${s.stopLoss} (-3%)\n`;
        message += `└ R/R   : 1:${s.rrRatio}\n\n`;
        
        s.marketMakerStatus = marketMakerStatus;
        s.orderbookWall = orderbookWall;
        rank++;

        await sleep(1000); // Delay 1.5 second between API calls to avoid hitting rate limits
    }

    message += `<i>Disclaimer: Trade at your own risk. Do not FOMO!</i>`;

    // Print the message to terminal for verification before sending
    console.log("\n" + "=".repeat(100));
    console.log("📊 TOP 10 SWING CANDIDATES & marketMakerMOLOGY (TERMINAL LOG):");
    console.log("=".repeat(100));
    
    // Mapping data for console.table
    const tableData = topSwings.map((s, index) => ({
        "Rank": index + 1,
        "Ticker": s.ticker,
        "Entry": `Rp ${s.entry}`,
        "Target": `Rp ${s.target}`,
        "Stop Loss": `Rp ${s.stopLoss}`,
        "Signal": s.reason.replace(/<\/?[^>]+(>|$)/g, ""),
        "Market Maker": s.marketMakerStatus,
        "Wall": s.orderbookWall
    }));

    console.table(tableData);
    console.log("=".repeat(100) + "\n");

    await sendTelegramAlert(message);
}

// Jalankan mesinnya!
runFiltrationEngine();