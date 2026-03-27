"""
数据采集模块 - 数据来源：optioncharts.io
每日采集：IV Rank、IV Percentile、IV30
无需账号，完全免费

IV Rank       = (当前IV - 52周低) / (52周高 - 52周低) × 100
IV Percentile = 过去1年中 IV 低于当前 IV 的天数占比 × 100
"""

import sqlite3
import datetime
import logging
import time
import re

import requests

from config import WATCHLIST, DB_PATH

BASE_URL        = "https://optioncharts.io/async/options_ticker_info"
REQUEST_INTERVAL = 1.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("iv_tracker.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://optioncharts.io/",
}


# ── 数据库 ──────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS iv_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol        TEXT NOT NULL,
            date          TEXT NOT NULL,
            iv_pct        REAL NOT NULL,
            iv_percentile REAL,
            iv30          REAL,
            UNIQUE (symbol, date)
        )
    """)
    # 旧数据库迁移：补充 iv_percentile 列（如果不存在）
    try:
        conn.execute("ALTER TABLE iv_history ADD COLUMN iv_percentile REAL")
    except Exception:
        pass
    conn.commit()
    conn.close()


def save(symbol: str, date: str, iv_rank: float,
         iv_percentile: float = None, iv30: float = None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO iv_history
           (symbol, date, iv_pct, iv_percentile, iv30)
           VALUES (?, ?, ?, ?, ?)""",
        (symbol, date, iv_rank, iv_percentile, iv30),
    )
    conn.commit()
    conn.close()


# ── 数据提取 ─────────────────────────────────────────────────

def fetch_iv(ticker: str):
    """
    从 optioncharts.io 获取单个标的数据。
    返回 {'iv_rank', 'iv_percentile', 'iv30'}，失败返回 None。
    """
    try:
        r = requests.get(
            BASE_URL,
            params={"ticker": ticker},
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        log.error("%s 请求失败: %s", ticker, e)
        return None

    # IV Rank（JS 变量）
    vars_found   = dict(re.findall(r"var\s+(\w+)\s*=\s*([\d.]+);", r.text))
    iv_rank_raw  = vars_found.get("iv_rank")
    iv30_raw     = vars_found.get("implied_volatility_30d")

    if iv_rank_raw is None:
        log.warning("%s 未找到 iv_rank（页面结构可能有变化）", ticker)
        return None

    # IV Percentile（HTML 文本节点）
    m_pct = re.search(
        r'IV Percentile.*?<div class="tw-font-semibold">([\d.]+)%</div>',
        r.text, re.DOTALL
    )
    iv_percentile_raw = m_pct.group(1) if m_pct else None

    return {
        "iv_rank":       round(float(iv_rank_raw), 2),
        "iv_percentile": round(float(iv_percentile_raw), 2) if iv_percentile_raw else None,
        "iv30":          round(float(iv30_raw), 2) if iv30_raw else None,
    }


# ── 主采集流程 ───────────────────────────────────────────────

def collect_today():
    init_db()
    today = datetime.date.today().isoformat()
    log.info("===== 开始采集 %s =====", today)

    ok, fail = 0, []

    for i, ticker in enumerate(WATCHLIST):
        if i > 0:
            time.sleep(REQUEST_INTERVAL)

        result = fetch_iv(ticker)

        if result:
            save(ticker, today,
                 result["iv_rank"],
                 result.get("iv_percentile"),
                 result.get("iv30"))
            log.info(
                "  %-10s IV Rank=%5.1f%%  IV Percentile=%s  IV30=%s",
                ticker,
                result["iv_rank"],
                f"{result['iv_percentile']:.1f}%" if result.get("iv_percentile") is not None else "N/A",
                f"{result['iv30']:.1f}%"          if result.get("iv30")          is not None else "N/A",
            )
            ok += 1
        else:
            fail.append(ticker)

    log.info("===== 完成 %d/%d =====", ok, len(WATCHLIST))

    if fail:
        print(f"\n以下标的未获取到数据，可手动补录：")
        for s in fail:
            print(f"  {s}")
        print("运行手动补录: python3 manual_fix.py")


if __name__ == "__main__":
    collect_today()
