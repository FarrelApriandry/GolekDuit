
/**
 * MoneyWatcher Core Engine
 *
 * This script analyzes stock swing candidates from the latest daily scrape batch, validates them against swing trading criteria,
 * calculates trade plans, and sends formatted alerts to a Telegram channel.
 *
 * Author: [Your Name]
 * Date: [Update Date]
 */

require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');

const telegramToken = process.env.TELEGRAM_BOT_TOKEN;
const telegramChatId = process.env.TELEGRAM_CHAT_ID;

// ==========================================
// ⚙️ CONFIGURATION
// ==========================================
const DATA_DIRECTORY = path.join(__dirname, 'data', 'daily_scrapes');
const SWING_PARAMETERS = {
    RISK_PERCENT: 0.03,      // Stop Loss 3%
    REWARD_PERCENT: 0.15,    // Take Profit 15%
    FIBONACCI_TOLERANCE: 0.02 // Fibonacci bounce tolerance (± 2%)
};

// ==========================================
// 🔍 FILE READER ENGINE
// ==========================================
/**
 * Returns the path to the latest batch JSON file in the data directory.
 * @returns {string|null} Path to the latest batch file or null if not found.
 */
function getLatestBatchFile() {
    try {
        if (!fs.existsSync(DATA_DIRECTORY)) return null;
        const files = fs.readdirSync(DATA_DIRECTORY);
        const batchFiles = files.filter(f => f.endsWith('_batch.json'));
        if (batchFiles.length === 0) return null;
        batchFiles.sort();
        return path.join(DATA_DIRECTORY, batchFiles[batchFiles.length - 1]);
    } catch (error) {
        console.error("[ERROR] Failed to read data directory:", error);
        return null;
    }
}

// ==========================================
// 🧮 TRADE CALCULATOR ENGINE
// ==========================================
/**
 * Calculates the trade plan (entry, take profit, stop loss, risk/reward ratio) for a given entry price.
 * @param {number} entryPrice - The entry price for the trade.
 * @returns {Object} Trade plan object.
 */
function calculateTradePlan(entryPrice) {
    // Take Profit: +15% (rounded down for realistic queue)
    let takeProfitRaw = entryPrice * (1 + SWING_PARAMETERS.REWARD_PERCENT);
    let takeProfit = Math.floor(takeProfitRaw);

    // Stop Loss: -3% (rounded up to avoid late cut loss)
    let stopLossRaw = entryPrice * (1 - SWING_PARAMETERS.RISK_PERCENT);
    let stopLoss = Math.ceil(stopLossRaw);

    // Calculate risk/reward ratio based on rounded prices
    let risk = entryPrice - stopLoss;
    let reward = takeProfit - entryPrice;
    let rrRatio = risk > 0 ? (reward / risk).toFixed(2) : 0;

    return {
        entry: entryPrice,
        take_profit: takeProfit,
        stop_loss: stopLoss,
        risk_reward_ratio: rrRatio
    };
}

// ==========================================
// 🧠 SWING VALIDATION CORE
// ==========================================
/**
 * Parses swing candidates from a batch file and validates them against swing trading criteria.
 * @param {string} filePath - Path to the batch JSON file.
 * @returns {Array} Array of qualified stock objects.
 */
function parseSwingCandidates(filePath) {
    let rawData = fs.readFileSync(filePath, 'utf-8');
    // Replace bare NaN from Python with null for JSON compliance
    rawData = rawData.replace(/:\s*NaN/g, ': null');

    const parsedData = JSON.parse(rawData);
    const candidates = parsedData.candidates || [];
    let qualifiedStocks = [];

    console.log(`\n[INFO] Analyzing ${candidates.length} candidate(s) for swing setup...`);

    candidates.forEach(candidate => {
        const ticker = candidate.Search?.KodeEmiten;
        const swingData = candidate.Swing_Data;

        // Validate market data
        if (!swingData || !swingData.market_data || swingData.market_data.current_close === null) {
            console.log(`[WARNING] Skipped ${ticker}: Invalid market data (contains null/NaN).`);
            return;
        }

        const currentPrice = swingData.market_data.current_close;
        const fibonacci = swingData.technical_signals.fibo_levels;
        const volumeBreakout = swingData.technical_signals.is_volume_breakout;

        const isNear382 = Math.abs(currentPrice - fibonacci.level_382) / fibonacci.level_382 <= SWING_PARAMETERS.FIBONACCI_TOLERANCE;
        const isNear500 = Math.abs(currentPrice - fibonacci.level_500) / fibonacci.level_500 <= SWING_PARAMETERS.FIBONACCI_TOLERANCE;
        const isNear618 = Math.abs(currentPrice - fibonacci.level_618) / fibonacci.level_618 <= SWING_PARAMETERS.FIBONACCI_TOLERANCE;

        if (isNear382 || isNear500 || isNear618) {
            console.log(`[SUCCESS] Trigger: ${ticker} is currently bouncing at Fibonacci support!`);
            const tradePlan = calculateTradePlan(currentPrice);
            qualifiedStocks.push({
                ticker: ticker,
                plan: tradePlan,
                volume_breakout: volumeBreakout
            });
        } else {
            console.log(`[REJECTED] ${ticker}: Price (Rp ${currentPrice}) is far from any Fibonacci support.`);
        }
    });

    return qualifiedStocks;
}

// ==========================================
// 📱 TELEGRAM BROADCASTER ENGINE
// ==========================================
/**
 * Sends a formatted swing alert message to a Telegram channel.
 * @param {Array} validSwings - Array of qualified swing stocks.
 * @param {string} batchName - Name of the batch file being processed.
 */
async function broadcastToTelegram(validSwings, batchName) {
    if (!telegramToken || !telegramChatId) {
        console.log("[ERROR] Telegram token or chat ID not found in .env file!");
        return;
    }

    // Polling: false because this bot only sends messages (push notification), not listening for chat
    const bot = new TelegramBot(telegramToken, { polling: false });

    // T7.2: Message Formatting
    let message = `🎯 *MONEY WATCHER SWING ALERT*\n`;
    message += `📅 Batch: \`${batchName}\`\n\n`;

    if (validSwings.length === 0) {
        message += `No stocks are currently bouncing at Fibonacci support today. Stay in cash! 💸`;
    } else {
        message += `Found *${validSwings.length} candidate(s)* bouncing at support:\n\n`;
        validSwings.forEach((s, index) => {
            message += `*${index + 1}. ${s.ticker}* ${s.volume_breakout ? '🔥(Volume Breakout)' : ''}\n`;
            message += `├ Entry : Rp ${s.plan.entry}\n`;
            message += `├ Target: Rp ${s.plan.take_profit} (+15%)\n`;
            message += `├ Stop L: Rp ${s.plan.stop_loss} (-3%)\n`;
            message += `└ R/R   : 1:${s.plan.risk_reward_ratio}\n\n`;
        });
        message += `_Disclaimer: Trade at your own risk. Do not FOMO!_`;
    }

    // Send the message
    console.log("\n[INFO] Sending alert to Telegram...");
    try {
        await bot.sendMessage(telegramChatId, message, { parse_mode: "Markdown" });
        console.log("[SUCCESS] Alert successfully sent to Telegram channel.");
    } catch (error) {
        console.error("[ERROR] Failed to send message to Telegram:", error.message);
    }
}

// ==========================================
// 🚀 MAIN EXECUTION
// ==========================================
/**
 * Main function to run the MoneyWatcher core engine.
 * Finds the latest batch, validates swing candidates, prints results, and sends Telegram alert.
 */
async function runEngine() {
    console.log("=== MONEY WATCHER CORE ENGINE ===");
    const latestBatchFile = getLatestBatchFile();

    if (latestBatchFile) {
        const batchName = path.basename(latestBatchFile);
        console.log(`[INFO] Processing latest batch: ${batchName}`);

        const validSwings = parseSwingCandidates(latestBatchFile);
        console.log(`\n[INFO] Validation complete: Found ${validSwings.length} stock(s) ready for swing trading.`);

        // Print table to terminal for monitoring
        if (validSwings.length > 0) {
            console.log("\n[INFO] SWING TRADE PLAN:");
            console.table(validSwings.map(s => ({
                Ticker: s.ticker,
                Entry: `Rp ${s.plan.entry}`,
                'Take Profit': `Rp ${s.plan.take_profit}`,
                'Stop Loss': `Rp ${s.plan.stop_loss}`
            })));
        }

        // Send alert to Telegram
        await broadcastToTelegram(validSwings, batchName);
    } else {
        console.log("[INFO] No batch file found to process.");
    }
}

// Run the system
runEngine();