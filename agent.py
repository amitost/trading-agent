import anthropic
import yfinance as yf
import json
import re
import requests
import schedule
import time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import config

# Connect to services
trading_client = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=True)
ai_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def send_telegram(message):
    """Send a message to Telegram"""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
        print("Telegram message sent!")
    except Exception as e:
        print(f"Telegram error: {e}")


def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1mo")
    info = stock.info
    return {
        "ticker": ticker,
        "current_price": round(hist['Close'].iloc[-1], 2),
        "change_1day": round(((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100, 2),
        "change_1month": round(((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100, 2),
        "pe_ratio": info.get("trailingPE", "N/A"),
        "volume": info.get("volume", "N/A"),
    }


def get_portfolio_status():
    account = trading_client.get_account()
    positions = trading_client.get_all_positions()
    current_positions = {}
    for p in positions:
        current_positions[p.symbol] = {
            "qty": float(p.qty),
            "market_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl)
        }
    return {
        "cash": round(float(account.cash), 2),
        "portfolio_value": round(float(account.portfolio_value), 2),
        "positions": current_positions
    }


def execute_trade(ticker, action, qty):
    if action == "BUY":
        side = OrderSide.BUY
    elif action == "SELL":
        side = OrderSide.SELL
    else:
        return
    order = MarketOrderRequest(
        symbol=ticker,
        qty=qty,
        side=side,
        time_in_force=TimeInForce.DAY
    )
    result = trading_client.submit_order(order)
    print(f"Executed {action} of {qty} shares of {ticker}")
    return result


def run_agent():
    from datetime import datetime
    import pytz
    
    # בדוק אם השוק פתוח
    ny_time = datetime.now(pytz.timezone('America/New_York'))
    
    # שבת או ראשון - סגור
    if ny_time.weekday() >= 5:
        print("Market closed - weekend. Skipping.")
        return
    
    # בדוק שעות מסחר 9:30-16:00
    market_open = ny_time.replace(hour=9, minute=30, second=0)
    market_close = ny_time.replace(hour=16, minute=0, second=0)
    if not (market_open <= ny_time <= market_close):
        print("Market closed - outside trading hours. Skipping.")
        return
    
    print("\nAgent starting analysis...")

    market_data = {}
    for ticker in config.PORTFOLIO:
        print(f"  Fetching data for {ticker}...")
        market_data[ticker] = get_stock_data(ticker)

    portfolio = get_portfolio_status()
    print(f"\nPortfolio value: ${portfolio['portfolio_value']} | Cash: ${portfolio['cash']}")

    prompt = f"""You are a professional portfolio manager. Analyze the data below and decide what to do.

Current portfolio status:
{json.dumps(portfolio, indent=2)}

Market data:
{json.dumps(market_data, indent=2)}

Available cash: ${portfolio['cash']}
Total portfolio: ${portfolio['portfolio_value']}

Rules:
- Never put more than {config.MAX_POSITION_SIZE * 100}% of portfolio in one stock
- SPY and QQQ are ETFs - more stable
- Base decisions on daily and monthly changes

Respond ONLY with valid JSON, no other text:
{{"analysis": "brief market analysis here", "trades": [{{"ticker": "AAPL", "action": "BUY", "qty": 2, "reason": "reason here"}}]}}

If no trades needed, use empty list: {{"analysis": "brief analysis", "trades": []}}"""

    response = ai_client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text
    match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if match:
        decision = json.loads(match.group())
    else:
        print("Could not parse response, skipping trades")
        send_telegram("Agent error: could not parse AI response")
        return

    print(f"\nAnalysis: {decision['analysis']}")

    # Build Telegram message
    msg = f"🤖 Agent Analysis\n"
    msg += f"💰 Portfolio: ${portfolio['portfolio_value']} | Cash: ${portfolio['cash']}\n\n"
    msg += f"📊 {decision['analysis']}\n\n"

    if decision['trades']:
        msg += f"📈 Executing {len(decision['trades'])} trades:\n"
        for trade in decision['trades']:
            print(f"  {trade['action']} {trade['qty']} x {trade['ticker']} - {trade['reason']}")
            execute_trade(trade['ticker'], trade['action'], trade['qty'])
            emoji = "🟢" if trade['action'] == "BUY" else "🔴"
            msg += f"{emoji} {trade['action']} {trade['qty']} x {trade['ticker']}\n   {trade['reason']}\n"
    else:
        msg += "⏸️ No trades - holding portfolio"

    send_telegram(msg)
    print("\nAnalysis complete!")


# Schedule the agent to run 3 times a day
schedule.every().day.at("09:35").do(run_agent)
schedule.every().day.at("13:00").do(run_agent)
schedule.every().day.at("15:45").do(run_agent)

print("Agent scheduled! Running at 09:35, 13:00, 15:45")
print("Press Ctrl+C to stop")

# Run once immediately to test
run_agent()

# Keep running
while True:
    schedule.run_pending()
    time.sleep(60)