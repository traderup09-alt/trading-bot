"""
===========================================
  TELEGRAM TRADING SIGNALS BOT - FINAL
  
  Features:
  - Delta Exchange Auto Coins
  - RSI + MACD + EMA + Bollinger Bands
  - RSI Divergence
  - Volume + Trend + Session Filters
  - Signal Repeat Protection
  - ATR Smart SL/TP (1:3 RR)
  - 8 Candlestick Patterns
  - Multi Timeframe (1H + 15M)
  - 300 Candles
  - Daily Summary 11 PM
===========================================
"""

import time
import requests
from datetime import datetime

# ============================================
#   VALUES
# ============================================
TELEGRAM_TOKEN = "8744139332:AAFTVl1kJjDTPTmUgFPRgdopdyoDs0RecOw"
CHAT_ID        = "-5171845392"
# ============================================

CHECK_INTERVAL     = 300   # Har 5 minute
SIGNAL_COOLDOWN    = 14400 # 4 ghante (seconds)
VOLUME_THRESHOLD   = 1.5   # 1.5x average volume
MIN_SCORE          = 4     # Minimum score

# Signal history (repeat protection)
signal_history = {}

# Daily stats
daily_stats = {"date": "", "total": 0, "signals": []}

# ============================================
#   TELEGRAM
# ============================================
def send_message(text):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
        print("[OK] Message bheja!")
    except Exception as e:
        print(f"[ERROR] {e}")

# ============================================
#   DELTA EXCHANGE SE AUTO COINS FETCH
# ============================================
def get_delta_coins():
    try:
        url = "https://api.delta.exchange/v2/products"
        r   = requests.get(url, timeout=10)
        data = r.json()
        coins = []
        if "result" in data:
            for product in data["result"]:
                if (product.get("contract_type") == "perpetual_futures" and
                    product.get("quoting_asset", {}).get("symbol") == "USDT" and
                    product.get("is_active") == True):
                    symbol = product["underlying_asset"]["symbol"] + "USDT"
                    coins.append(symbol)
        print(f"[OK] Delta Exchange se {len(coins)} coins mile!")
        return coins if coins else get_default_coins()
    except Exception as e:
        print(f"[ERROR] Delta coins nahi mile: {e}")
        return get_default_coins()

def get_default_coins():
    return [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
        "LTCUSDT", "SHIBUSDT", "LINKUSDT", "ADAUSDT", "AVAXUSDT",
        "DOTUSDT", "ATOMUSDT", "DOGEUSDT", "TRXUSDT", "MATICUSDT",
        "BCHUSDT", "XTZUSDT",  "NEARUSDT", "APTUSDT", "PAXGUSDT",
        "PEPEUSDT"
    ]

# ============================================
#   BINANCE SE CANDLES
# ============================================
def get_candles(symbol, interval="1h", limit=300):
    url    = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r    = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not isinstance(data, list) or len(data) < 50:
            return None
        candles = []
        for d in data:
            candles.append({
                "open":   float(d[1]),
                "high":   float(d[2]),
                "low":    float(d[3]),
                "close":  float(d[4]),
                "volume": float(d[5]),
            })
        return candles
    except:
        return None

# ============================================
#   ATR
# ============================================
def calculate_atr(candles, period=14):
    true_ranges = []
    for i in range(1, len(candles)):
        high       = candles[i]["high"]
        low        = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    return sum(true_ranges[-period:]) / period

# ============================================
#   RSI
# ============================================
def calculate_rsi(candles, period=14):
    closes = [c["close"] for c in candles]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period-1) + gains[i]) / period
        avg_loss = (avg_loss * (period-1) + losses[i]) / period
    if avg_loss == 0:
        return 100
    return round(100 - (100 / (1 + avg_gain/avg_loss)), 2)

# ============================================
#   RSI DIVERGENCE
# ============================================
def check_rsi_divergence(candles, period=14):
    if len(candles) < 30:
        return None
    
    closes     = [c["close"] for c in candles]
    rsi_values = []
    
    for i in range(period, len(candles)):
        subset = candles[i-period:i+1]
        rsi_values.append(calculate_rsi(subset))
    
    if len(rsi_values) < 10:
        return None
    
    recent_closes = closes[-10:]
    recent_rsi    = rsi_values[-10:]
    
    # Bullish Divergence: Price neeche, RSI upar
    if (recent_closes[-1] < recent_closes[0] and
        recent_rsi[-1]    > recent_rsi[0] and
        recent_rsi[-1]    < 50):
        return "bullish"
    
    # Bearish Divergence: Price upar, RSI neeche
    if (recent_closes[-1] > recent_closes[0] and
        recent_rsi[-1]    < recent_rsi[0] and
        recent_rsi[-1]    > 50):
        return "bearish"
    
    return None

# ============================================
#   EMA
# ============================================
def calculate_ema(candles, period):
    closes = [c["close"] for c in candles]
    k      = 2 / (period + 1)
    ema    = closes[0]
    for price in closes[1:]:
        ema = price * k + ema * (1 - k)
    return ema

# ============================================
#   MACD
# ============================================
def calculate_macd(candles):
    closes      = [c["close"] for c in candles]
    k12, k26    = 2/13, 2/27
    e12, e26    = closes[0], closes[0]
    macd_values = []
    for price in closes:
        e12 = price * k12 + e12 * (1 - k12)
        e26 = price * k26 + e26 * (1 - k26)
        macd_values.append(e12 - e26)
    k9     = 2/10
    signal = macd_values[0]
    for m in macd_values[1:]:
        signal = m * k9 + signal * (1 - k9)
    return macd_values[-1], signal, macd_values[-1] - signal

# ============================================
#   BOLLINGER BANDS
# ============================================
def calculate_bollinger(candles, period=20, std_dev=2):
    closes = [c["close"] for c in candles[-period:]]
    sma    = sum(closes) / period
    std    = (sum((x - sma)**2 for x in closes) / period) ** 0.5
    upper  = sma + std_dev * std
    lower  = sma - std_dev * std
    price  = candles[-1]["close"]
    
    if price <= lower:
        return "oversold", round(upper, 8), round(lower, 8)
    elif price >= upper:
        return "overbought", round(upper, 8), round(lower, 8)
    else:
        return "neutral", round(upper, 8), round(lower, 8)

# ============================================
#   VOLUME FILTER
# ============================================
def volume_filter(candles, period=20):
    volumes    = [c["volume"] for c in candles]
    avg_volume = sum(volumes[-period-1:-1]) / period
    last_vol   = volumes[-1]
    ratio      = last_vol / avg_volume if avg_volume > 0 else 0
    return ratio >= VOLUME_THRESHOLD, round(ratio, 2)

# ============================================
#   TREND FILTER
# ============================================
def trend_filter(candles):
    if len(candles) < 200:
        return "UNKNOWN"
    ema50  = calculate_ema(candles, 50)
    ema200 = calculate_ema(candles, 200)
    price  = candles[-1]["close"]
    if price > ema200 and ema50 > ema200:
        return "UPTREND 📈"
    elif price < ema200 and ema50 < ema200:
        return "DOWNTREND 📉"
    else:
        return "SIDEWAYS ↔️"

# ============================================
#   SESSION FILTER (IST)
#   London: 13:30 - 21:30
#   New York: 18:30 - 01:30
# ============================================
def session_filter():
    now  = datetime.utcnow()
    hour = now.hour + 5  # UTC to IST (+5:30)
    mins = now.minute
    if hour >= 24:
        hour -= 24
    
    ist_minutes = hour * 60 + mins + 30  # +30 for IST
    if ist_minutes >= 1440:
        ist_minutes -= 1440
    
    # London: 13:30 - 21:30 (810 - 1290 minutes)
    london = 810 <= ist_minutes <= 1290
    # New York: 18:30 - 01:30 (1110 - 1530 or 0 - 90 minutes)
    newyork = ist_minutes >= 1110 or ist_minutes <= 90
    
    if london and newyork:
        return True, "London + NY 🌍🌎"
    elif london:
        return True, "London Session 🌍"
    elif newyork:
        return True, "NY Session 🌎"
    else:
        return False, "Off Session"

# ============================================
#   SIGNAL REPEAT PROTECTION
# ============================================
def check_cooldown(symbol, direction):
    key     = f"{symbol}_{direction}"
    now     = time.time()
    if key in signal_history:
        if now - signal_history[key] < SIGNAL_COOLDOWN:
            return False
    signal_history[key] = now
    return True

# ============================================
#   CANDLESTICK PATTERNS
# ============================================
def detect_patterns(candles):
    patterns = []
    o1,h1,l1,c1 = candles[-1]["open"],candles[-1]["high"],candles[-1]["low"],candles[-1]["close"]
    o2,h2,l2,c2 = candles[-2]["open"],candles[-2]["high"],candles[-2]["low"],candles[-2]["close"]
    o3,h3,l3,c3 = candles[-3]["open"],candles[-3]["high"],candles[-3]["low"],candles[-3]["close"]

    body1       = abs(c1 - o1)
    lower_wick1 = min(c1, o1) - l1
    upper_wick1 = h1 - max(c1, o1)

    if lower_wick1 > 2*body1 and upper_wick1 < body1*0.3 and c1 > o1:
        patterns.append(("🔨 Hammer", "bullish"))
    if upper_wick1 > 2*body1 and lower_wick1 < body1*0.3 and c1 < o1:
        patterns.append(("🌟 Shooting Star", "bearish"))
    if o2>c2 and c1>o1 and c1>o2 and o1<c2:
        patterns.append(("📈 Bullish Engulfing", "bullish"))
    if c2>o2 and o1>c1 and o1>c2 and c1<o2:
        patterns.append(("📉 Bearish Engulfing", "bearish"))
    if o3>c3 and abs(c2-o2)<abs(c3-o3)*0.3 and c1>o1 and c1>(o3+c3)/2:
        patterns.append(("🌅 Morning Star", "bullish"))
    if c3>o3 and abs(c2-o2)<abs(c3-o3)*0.3 and o1>c1 and c1<(o3+c3)/2:
        patterns.append(("🌆 Evening Star", "bearish"))
    if c3>o3 and c2>o2 and c1>o1 and c2>c3 and c1>c2:
        patterns.append(("💂 3 White Soldiers", "bullish"))
    if o3>c3 and o2>c2 and o1>c1 and c2<c3 and c1<c2:
        patterns.append(("🦅 3 Black Crows", "bearish"))

    return patterns

# ============================================
#   DAILY SUMMARY
# ============================================
def check_daily_summary():
    now  = datetime.utcnow()
    # IST 11 PM = UTC 17:30
    if now.hour == 17 and 29 <= now.minute <= 34:
        today = now.strftime("%Y-%m-%d")
        if daily_stats["date"] != today:
            daily_stats["date"] = today
            send_daily_summary()

def send_daily_summary():
    total   = daily_stats["total"]
    signals = daily_stats["signals"]
    
    if total == 0:
        send_message("📊 <b>AAJ KA SUMMARY</b>\n\nAaj koi signal nahi aaya!")
        return
    
    long_count  = sum(1 for s in signals if s == "LONG")
    short_count = sum(1 for s in signals if s == "SHORT")
    
    msg = f"""
📊 <b>AAJ KA DAILY SUMMARY</b>

📅 Date: {daily_stats['date']}

📈 Total Signals: {total}
🟢 LONG Signals: {long_count}
🔴 SHORT Signals: {short_count}

⏰ Kal bhi strong signals aayenge!

⚠️ <i>Hamesha risk management karo!</i>
"""
    send_message(msg)
    # Reset daily stats
    daily_stats["total"]   = 0
    daily_stats["signals"] = []

# ============================================
#   MAIN SIGNAL FUNCTION
# ============================================
def get_signal(symbol):
    # Session check
    in_session, session_name = session_filter()
    if not in_session:
        return None

    df_1h  = get_candles(symbol, "1h",  300)
    df_15m = get_candles(symbol, "15m", 300)

    if not df_1h or not df_15m:
        return None
    if len(df_1h) < 200 or len(df_15m) < 50:
        return None

    price = df_1h[-1]["close"]

    # --- Calculate Indicators ---
    rsi_1h                    = calculate_rsi(df_1h)
    macd_1h, sig_1h, hist_1h  = calculate_macd(df_1h)
    ema_fast_1h               = calculate_ema(df_1h, 9)
    ema_slow_1h               = calculate_ema(df_1h, 21)
    rsi_15m                   = calculate_rsi(df_15m)
    ema_fast_15m              = calculate_ema(df_15m, 9)
    ema_slow_15m              = calculate_ema(df_15m, 21)
    bb_signal, bb_upper, bb_lower = calculate_bollinger(df_1h)
    divergence                = check_rsi_divergence(df_1h)
    atr                       = calculate_atr(df_1h)
    high_volume, vol_ratio    = volume_filter(df_1h)
    trend                     = trend_filter(df_1h)
    patterns                  = detect_patterns(df_15m)

    # --- Volume Filter ---
    if not high_volume:
        return None

    # --- Sideways mein sirf strong signals ---
    if "SIDEWAYS" in trend:
        min_score_required = 5
    else:
        min_score_required = MIN_SCORE

    # ============================================
    #   SCORE SYSTEM
    # ============================================
    score   = 0
    reasons = []

    # RSI 1H
    if rsi_1h < 35:
        score += 1
        reasons.append(f"RSI 1H={rsi_1h} 🟢 Oversold")
    elif rsi_1h > 65:
        score -= 1
        reasons.append(f"RSI 1H={rsi_1h} 🔴 Overbought")
    else:
        reasons.append(f"RSI 1H={rsi_1h} ⚪ Neutral")

    # MACD 1H
    if macd_1h > sig_1h and hist_1h > 0:
        score += 1
        reasons.append("MACD 1H 🟢 Bullish")
    elif macd_1h < sig_1h and hist_1h < 0:
        score -= 1
        reasons.append("MACD 1H 🔴 Bearish")
    else:
        reasons.append("MACD 1H ⚪ Neutral")

    # EMA 1H
    if ema_fast_1h > ema_slow_1h:
        score += 1
        reasons.append("EMA 1H 🟢 Bullish")
    else:
        score -= 1
        reasons.append("EMA 1H 🔴 Bearish")

    # RSI 15M
    if rsi_15m < 35:
        score += 1
        reasons.append(f"RSI 15M={rsi_15m} 🟢 Oversold")
    elif rsi_15m > 65:
        score -= 1
        reasons.append(f"RSI 15M={rsi_15m} 🔴 Overbought")
    else:
        reasons.append(f"RSI 15M={rsi_15m} ⚪ Neutral")

    # EMA 15M
    if ema_fast_15m > ema_slow_15m:
        score += 1
        reasons.append("EMA 15M 🟢 Bullish")
    else:
        score -= 1
        reasons.append("EMA 15M 🔴 Bearish")

    # Bollinger Bands
    if bb_signal == "oversold":
        score += 1
        reasons.append("BB 🟢 Price at Lower Band")
    elif bb_signal == "overbought":
        score -= 1
        reasons.append("BB 🔴 Price at Upper Band")
    else:
        reasons.append("BB ⚪ Neutral")

    # RSI Divergence
    if divergence == "bullish":
        score += 1
        reasons.append("RSI Divergence 🟢 Bullish")
    elif divergence == "bearish":
        score -= 1
        reasons.append("RSI Divergence 🔴 Bearish")

    # Candlestick Patterns
    pattern_text = ""
    for name, ptype in patterns:
        if ptype == "bullish":
            score += 1
            pattern_text += f"  {name} 🟢\n"
        elif ptype == "bearish":
            score -= 1
            pattern_text += f"  {name} 🔴\n"

    # ============================================
    #   TREND FILTER CHECK
    # ============================================
    if score >= min_score_required and "DOWNTREND" in trend:
        return None
    if score <= -min_score_required and "UPTREND" in trend:
        return None

    # ============================================
    #   SIGNAL DECIDE
    # ============================================
    if score >= min_score_required:
        direction = "LONG 🟢"
        emoji     = "🚀"
        sl  = round(price - 1.5 * atr, 8)
        tp1 = round(price + 1.5 * atr, 8)
        tp2 = round(price + 2.5 * atr, 8)
        tp3 = round(price + 3.5 * atr, 8)

    elif score <= -min_score_required:
        direction = "SHORT 🔴"
        emoji     = "📉"
        sl  = round(price + 1.5 * atr, 8)
        tp1 = round(price - 1.5 * atr, 8)
        tp2 = round(price - 2.5 * atr, 8)
        tp3 = round(price - 3.5 * atr, 8)

    else:
        return None

    # Cooldown check
    dir_key = "LONG" if score > 0 else "SHORT"
    if not check_cooldown(symbol, dir_key):
        return None

    # Confidence
    total_indicators = 7 + len(patterns)
    confidence       = round(abs(score) / max(total_indicators, 1) * 100)
    strength         = "💪 STRONG" if confidence >= 75 else "👍 MEDIUM" if confidence >= 55 else "⚠️ WEAK"
    coin_name        = symbol.replace("USDT", "/USDT")

    # TP percentages
    tp1_pct = round(abs(tp1 - price) / price * 100, 2)
    tp2_pct = round(abs(tp2 - price) / price * 100, 2)
    tp3_pct = round(abs(tp3 - price) / price * 100, 2)
    sl_pct  = round(abs(sl  - price) / price * 100, 2)

    # Daily stats update
    daily_stats["total"] += 1
    daily_stats["signals"].append(dir_key)

    msg = f"""
{emoji} <b>TRADING SIGNAL</b> {emoji}

📌 <b>Coin:</b> {coin_name}
📊 <b>Signal:</b> {direction}
💰 <b>Entry:</b> {price}

🎯 <b>TP1:</b> {tp1} (+{tp1_pct}%)
🎯 <b>TP2:</b> {tp2} (+{tp2_pct}%)
🎯 <b>TP3:</b> {tp3} (+{tp3_pct}%)
🛑 <b>SL:</b>  {sl}  (-{sl_pct}%)

📈 <b>Trend:</b> {trend}
🕐 <b>Session:</b> {session_name}
📊 <b>Volume:</b> {vol_ratio}x Average
📊 <b>BB Upper:</b> {bb_upper}
📊 <b>BB Lower:</b> {bb_lower}

{strength} | Score: {abs(score)}/{total_indicators} | {confidence}%
⚖️ <b>Risk:Reward = 1:3</b>

📈 <b>Indicators:</b>
{chr(10).join('  • ' + r for r in reasons)}

🕯 <b>Patterns:</b>
{pattern_text if pattern_text else '  • Koi pattern nahi'}

⚠️ <i>Sirf educational hai. Trading mein risk hota hai!</i>
"""
    return msg

# ============================================
#   MAIN LOOP
# ============================================
def main():
    print("=" * 50)
    print("  FINAL TRADING BOT START HO GAYA!")
    print("=" * 50)

    # Delta Exchange se coins fetch karo
    print("\n[...] Delta Exchange se coins fetch ho rahe hain...")
    COINS = get_delta_coins()
    print(f"[OK] {len(COINS)} coins ready!")

    send_message(f"""
🤖 <b>Advanced Trading Bot Active!</b>

✅ Coins: {len(COINS)} (Delta Exchange)
✅ RSI + MACD + EMA
✅ Bollinger Bands
✅ RSI Divergence
✅ Volume + Trend + Session Filter
✅ Signal Repeat Protection
✅ ATR Smart SL/TP
✅ 8 Candlestick Patterns
✅ Timeframe: 1H + 15M
✅ Risk:Reward = 1:3
✅ Daily Summary: Raat 11 PM

Sirf <b>STRONG signals</b> aayenge! 📡
""")

    last_coin_update = time.time()

    while True:
        # Har 1 ghante mein coins update karo
        if time.time() - last_coin_update > 3600:
            print("\n[...] Coins update ho rahe hain...")
            COINS = get_delta_coins()
            last_coin_update = time.time()

        # Daily summary check
        check_daily_summary()

        print(f"\n[{time.strftime('%H:%M:%S')}] {len(COINS)} coins check ho rahe hain...")

        # Session check
        in_session, session_name = session_filter()
        if not in_session:
            print(f"  ⏸️  Off session — wait kar rahe hain...")
            time.sleep(CHECK_INTERVAL)
            continue

        print(f"  ✅ Session: {session_name}")

        for coin in COINS:
            print(f"  → {coin}...")
            try:
                msg = get_signal(coin)
                if msg:
                    send_message(msg)
                    print(f"  ✅ Signal bheja!")
                    time.sleep(3)
                else:
                    print(f"  ⏭️  Filter ya weak signal")
                time.sleep(1)
            except Exception as e:
                print(f"  ❌ {coin} error: {e}")

        print(f"\n  ⏰ Next check {CHECK_INTERVAL//60} min mein...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
