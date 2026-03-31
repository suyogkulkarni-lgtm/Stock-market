#!/usr/bin/env python3
"""
Indian Stock Market Email Job
==============================
Runs on GitHub Actions — no PC required.
Credentials are read from environment variables (GitHub Secrets).

• Detects BSE open/closed using the official BSE holiday calendar.
• OPEN   → fetches Sensex + top-15 gainers & losers → rich HTML email.
• CLOSED → single "market closed" notification with next holiday info.
"""

import os
import smtplib
import sys
import traceback
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import pandas_market_calendars as mcal
import pytz
import yfinance as yf

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG — all values come from GitHub Secrets (env vars)
# ══════════════════════════════════════════════════════════════════════════════

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
RECIPIENTS     = [r.strip() for r in os.environ["RECIPIENTS"].split(",")]
TOP_N          = int(os.environ.get("TOP_N", "15"))

IST = pytz.timezone("Asia/Kolkata")

# ── Nifty-50 universe ─────────────────────────────────────────────────────────
NIFTY50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
    "INFOSYS.NS", "SBIN.NS", "HINDUNILVR.NS", "ITC.NS", "LT.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS",
    "BAJFINANCE.NS", "WIPRO.NS", "HCLTECH.NS", "ULTRACEMCO.NS", "ONGC.NS",
    "POWERGRID.NS", "NTPC.NS", "TATAMOTORS.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "BAJAJFINSV.NS", "NESTLEIND.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "COALINDIA.NS",
    "DIVISLAB.NS", "EICHERMOT.NS", "GRASIM.NS", "TECHM.NS", "HINDALCO.NS",
    "BAJAJ-AUTO.NS", "CIPLA.NS", "DRREDDY.NS", "BPCL.NS", "BRITANNIA.NS",
    "APOLLOHOSP.NS", "HEROMOTOCO.NS", "INDUSINDBK.NS", "SHREECEM.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "TATACONSUM.NS", "ASIANPAINT.NS", "M&M.NS", "UPL.NS",
]

# Add extra tickers from env (comma-separated), e.g. "IRFC.NS,RAILVIKAS.NS"
_extra = os.environ.get("EXTRA_TICKERS", "")
EXTRA  = [t.strip() for t in _extra.split(",") if t.strip()]
ALL_TICKERS = list(set(NIFTY50 + EXTRA))


# ══════════════════════════════════════════════════════════════════════════════
#  MARKET STATUS
# ══════════════════════════════════════════════════════════════════════════════

def is_trading_day(today: date) -> bool:
    bse      = mcal.get_calendar("BSE")
    schedule = bse.schedule(
        start_date=today.strftime("%Y-%m-%d"),
        end_date=today.strftime("%Y-%m-%d"),
    )
    return not schedule.empty


def is_market_open_now() -> tuple[bool, str]:
    now   = datetime.now(IST)
    today = now.date()

    if today.weekday() >= 5:
        return False, f"Weekend — {today.strftime('%A, %d %b %Y')}"

    if not is_trading_day(today):
        return False, f"BSE Holiday on {today.strftime('%d %b %Y')}"

    open_t  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)

    if now < open_t:
        return False, f"Pre-market — opens 09:15 IST (now {now.strftime('%H:%M')})"
    if now > close_t:
        return False, f"Post-market — closed at 15:30 IST"

    return True, "Market is OPEN"


def get_next_holiday() -> str:
    bse      = mcal.get_calendar("BSE")
    today    = date.today()
    end_date = today + pd.Timedelta(days=120)

    trading = set(
        d.date() for d in bse.valid_days(
            start_date=today.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
    )
    for d in pd.date_range(today, end_date, freq="B"):
        if d.date() > today and d.weekday() < 5 and d.date() not in trading:
            return d.strftime("%d %b %Y (%A)")
    return "None found in next 120 days"


# ══════════════════════════════════════════════════════════════════════════════
#  DATA FETCHING
# ══════════════════════════════════════════════════════════════════════════════

def fetch_sensex() -> dict:
    ticker = yf.Ticker("^BSESN")
    hist   = ticker.history(period="2d")
    if len(hist) < 1:
        return {"value": 0, "change": 0, "change_pct": 0,
                "prev_close": 0, "day_high": 0, "day_low": 0}

    latest    = hist.iloc[-1]
    prev      = hist.iloc[-2] if len(hist) >= 2 else latest
    current   = latest["Close"]
    prev_close = prev["Close"]
    change    = current - prev_close

    return {
        "value":      round(current, 2),
        "change":     round(change, 2),
        "change_pct": round((change / prev_close) * 100, 2),
        "prev_close": round(prev_close, 2),
        "day_high":   round(latest["High"], 2),
        "day_low":    round(latest["Low"], 2),
    }


def fetch_stock_changes(tickers: list) -> pd.DataFrame:
    data = yf.download(
        tickers, period="2d",
        group_by="ticker", auto_adjust=True,
        progress=False, threads=True,
    )
    rows = []
    for sym in tickers:
        try:
            closes = data[sym]["Close"] if len(tickers) > 1 else data["Close"]
            closes = closes.dropna()
            if len(closes) < 2:
                continue
            prev, curr = closes.iloc[-2], closes.iloc[-1]
            chg  = curr - prev
            rows.append({
                "Symbol": sym.replace(".NS", "").replace(".BO", ""),
                "Price":  round(float(curr), 2),
                "Change": round(float(chg), 2),
                "Chg %":  round(float((chg / prev) * 100), 2),
            })
        except Exception:
            continue

    df = pd.DataFrame(rows)
    return df.sort_values("Chg %", ascending=False).reset_index(drop=True) if not df.empty else df


# ══════════════════════════════════════════════════════════════════════════════
#  EMAIL TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

BG, CARD, ACCENT = "#0f1117", "#1a1d27", "#6c63ff"
GREEN, RED       = "#00c896", "#ff4d6d"
TEXT, MUTED      = "#e8eaf0", "#8b8fa8"
BORDER, YELLOW   = "#2a2d3e", "#ffd166"


def _stock_table_html(df: pd.DataFrame, title: str, color: str) -> str:
    rows = ""
    for _, r in df.iterrows():
        sign = "+" if r["Chg %"] >= 0 else ""
        c    = GREEN if r["Chg %"] >= 0 else RED
        rows += f"""
        <tr>
          <td style="padding:10px 14px;font-weight:600;color:{TEXT}">{r['Symbol']}</td>
          <td style="padding:10px 14px;text-align:right;color:{MUTED}">₹{r['Price']:,.2f}</td>
          <td style="padding:10px 14px;text-align:right;color:{c};font-weight:700">{sign}{r['Chg %']:.2f}%</td>
          <td style="padding:10px 14px;text-align:right;color:{c}">{sign}₹{r['Change']:.2f}</td>
        </tr>"""
    return f"""
    <div style="margin-bottom:28px">
      <h3 style="color:{color};font-size:15px;margin:0 0 12px 0;letter-spacing:1px;
                 text-transform:uppercase;border-left:4px solid {color};padding-left:10px">{title}</h3>
      <table width="100%" cellspacing="0" cellpadding="0"
             style="border-collapse:collapse;background:{CARD};border-radius:10px;overflow:hidden">
        <thead>
          <tr style="background:{BORDER}">
            <th style="padding:10px 14px;text-align:left;color:{MUTED};font-size:11px;letter-spacing:.8px">SYMBOL</th>
            <th style="padding:10px 14px;text-align:right;color:{MUTED};font-size:11px;letter-spacing:.8px">PRICE</th>
            <th style="padding:10px 14px;text-align:right;color:{MUTED};font-size:11px;letter-spacing:.8px">CHG %</th>
            <th style="padding:10px 14px;text-align:right;color:{MUTED};font-size:11px;letter-spacing:.8px">CHG ₹</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


def build_open_html(sensex: dict, gainers: pd.DataFrame, losers: pd.DataFrame,
                    slot: str, fetched_at: str) -> str:
    s_color = GREEN if sensex["change"] >= 0 else RED
    s_sign  = "+" if sensex["change"] >= 0 else ""
    arrow   = "▲" if sensex["change"] >= 0 else "▼"
    badge_c = {"Morning": ACCENT, "Afternoon": YELLOW, "Closing": RED}.get(slot, ACCENT)

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:{BG};font-family:'Segoe UI',Arial,sans-serif;color:{TEXT}">
<div style="max-width:640px;margin:0 auto;padding:24px 16px">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:16px;
              padding:28px 32px;margin-bottom:24px;border:1px solid {BORDER}">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
      <div>
        <p style="margin:0 0 4px;font-size:11px;letter-spacing:1.5px;color:{MUTED};text-transform:uppercase">Indian Market Report</p>
        <h1 style="margin:0;font-size:26px;font-weight:800">📊 BSE / NSE Update</h1>
      </div>
      <div style="background:{badge_c};border-radius:20px;padding:6px 16px;font-size:13px;font-weight:700;color:#fff">
        {slot} Update
      </div>
    </div>
    <p style="margin:14px 0 0;font-size:12px;color:{MUTED}">{fetched_at} IST &nbsp;·&nbsp; Nifty 50 Universe</p>
  </div>

  <!-- Sensex -->
  <div style="background:{CARD};border-radius:14px;padding:24px 28px;margin-bottom:24px;border:1px solid {BORDER}">
    <p style="margin:0 0 6px;font-size:11px;letter-spacing:1.2px;color:{MUTED};text-transform:uppercase">S&P BSE Sensex</p>
    <div style="display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap">
      <span style="font-size:42px;font-weight:800;letter-spacing:-1px">{sensex['value']:,.2f}</span>
      <span style="font-size:20px;font-weight:700;color:{s_color};margin-bottom:6px">
        {arrow} {s_sign}{sensex['change_pct']:.2f}% &nbsp;
        <span style="font-size:15px">({s_sign}₹{sensex['change']:,.2f})</span>
      </span>
    </div>
    <div style="display:flex;gap:24px;margin-top:16px;flex-wrap:wrap">
      <div><span style="font-size:11px;color:{MUTED};text-transform:uppercase">Prev Close</span><br>
           <span style="font-size:15px;font-weight:600">₹{sensex['prev_close']:,.2f}</span></div>
      <div><span style="font-size:11px;color:{MUTED};text-transform:uppercase">Day High</span><br>
           <span style="font-size:15px;font-weight:600;color:{GREEN}">₹{sensex['day_high']:,.2f}</span></div>
      <div><span style="font-size:11px;color:{MUTED};text-transform:uppercase">Day Low</span><br>
           <span style="font-size:15px;font-weight:600;color:{RED}">₹{sensex['day_low']:,.2f}</span></div>
    </div>
  </div>

  {_stock_table_html(gainers, f"🚀 Top {TOP_N} Gainers", GREEN)}
  {_stock_table_html(losers,  f"🔻 Top {TOP_N} Losers",  RED)}

  <div style="text-align:center;padding:16px;border-top:1px solid {BORDER}">
    <p style="margin:0;font-size:11px;color:{MUTED}">
      Data: Yahoo Finance · For informational purposes only · Not financial advice
    </p>
  </div>
</div>
</body></html>"""


def build_closed_html(reason: str, next_holiday: str, fetched_at: str) -> str:
    today_str = datetime.now(IST).strftime("%A, %d %B %Y")
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:{BG};font-family:'Segoe UI',Arial,sans-serif;color:{TEXT}">
<div style="max-width:520px;margin:0 auto;padding:40px 16px">
  <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:16px;
              padding:40px 32px;text-align:center;border:1px solid {BORDER}">
    <div style="font-size:64px;margin-bottom:16px">🔴</div>
    <h1 style="margin:0 0 8px;font-size:28px;font-weight:800">Market Closed</h1>
    <p style="margin:0 0 24px;font-size:15px;color:{MUTED}">{today_str}</p>
    <div style="background:{CARD};border-radius:10px;padding:16px 20px;margin-bottom:16px;border:1px solid {BORDER};text-align:left">
      <p style="margin:0;font-size:12px;color:{YELLOW};font-weight:700;text-transform:uppercase;letter-spacing:.8px">📌 Reason</p>
      <p style="margin:8px 0 0;font-size:16px">{reason}</p>
    </div>
    <div style="background:{CARD};border-radius:10px;padding:16px 20px;border:1px solid {BORDER};text-align:left">
      <p style="margin:0;font-size:12px;color:{MUTED};font-weight:700;text-transform:uppercase;letter-spacing:.8px">📅 Next BSE Holiday</p>
      <p style="margin:8px 0 0;font-size:16px;font-weight:700;color:{ACCENT}">{next_holiday}</p>
    </div>
    <p style="margin:24px 0 0;font-size:11px;color:{MUTED}">Generated at {fetched_at} IST · BSE Calendar via pandas_market_calendars</p>
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  EMAIL SENDER
# ══════════════════════════════════════════════════════════════════════════════

def send_email(subject: str, html_body: str) -> None:
    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())

    print(f"  ✅  Mail sent to {len(RECIPIENTS)} recipient(s)")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def slot_label() -> str:
    h = datetime.now(IST).hour
    return "Morning" if h < 12 else ("Afternoon" if h < 14 else "Closing")


def main() -> None:
    now_str = datetime.now(IST).strftime("%d %b %Y, %H:%M")
    print(f"\n{'='*52}")
    print(f"  Indian Market Job — {now_str} IST")
    print(f"{'='*52}")

    is_open, reason = is_market_open_now()
    print(f"  Status : {'OPEN 🟢' if is_open else 'CLOSED 🔴'} — {reason}")

    if not is_open:
        html    = build_closed_html(reason, get_next_holiday(), now_str)
        subject = f"🔴 BSE Market Closed — {datetime.now(IST).strftime('%d %b %Y')}"
        print("  Sending closed notification…")
        send_email(subject, html)
        return

    slot = slot_label()
    print(f"  Slot   : {slot}")
    print("  Fetching Sensex & Nifty 50 data…")

    sensex = fetch_sensex()
    print(f"  Sensex : {sensex['value']:,}  ({sensex['change_pct']:+.2f}%)")

    df = fetch_stock_changes(ALL_TICKERS)
    if df.empty:
        print("  ⚠️  No stock data received. Aborting.")
        sys.exit(1)

    gainers = df.head(TOP_N)
    losers  = df.tail(TOP_N).sort_values("Chg %").reset_index(drop=True)
    html    = build_open_html(sensex, gainers, losers, slot, now_str)

    date_str = datetime.now(IST).strftime("%d %b %Y")
    subject  = (f"📊 [{slot}] BSE Update — "
                f"Sensex {sensex['value']:,.0f} ({sensex['change_pct']:+.2f}%) — {date_str}")
    print(f"  Sending {slot} report…")
    send_email(subject, html)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌  Error: {e}")
        traceback.print_exc()
        sys.exit(1)
