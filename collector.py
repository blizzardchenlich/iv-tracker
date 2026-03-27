"""
数据采集模块
每日收盘后运行：找 ~30 天到期的 ATM Call，读取 option_implied_volatility，存库
"""

import sqlite3
import datetime
import logging
from typing import Optional
import futu as ft

from config import FUTU_HOST, FUTU_PORT, WATCHLIST, DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("iv_tracker.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS iv_history (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol  TEXT NOT NULL,
            date    TEXT NOT NULL,
            iv      REAL NOT NULL,   -- ATM Call 隐含波动率（小数，如 0.35 = 35%）
            UNIQUE (symbol, date)
        )
    """)
    conn.commit()
    conn.close()


def get_atm_iv(ctx: ft.OpenQuoteContext, symbol: str) -> Optional[float]:
    """
    1. 找到距今 21~60 天到期的第一个到期日（避免近月扭曲）
    2. 从期权链里找行权价最接近现价的 Call
    3. 用 get_market_snapshot 读取该合约的 option_implied_volatility
    """
    today = datetime.date.today()

    # ── 当前股价 ──────────────────────────────────────────
    ret, snap = ctx.get_market_snapshot([symbol])
    if ret != ft.RET_OK:
        log.warning("%s 快照失败: %s", symbol, snap)
        return None
    current_price = float(snap["last_price"].iloc[0])

    # ── 选合适的到期日（21~60 天） ──────────────────────
    ret, exp = ctx.get_option_expiration_date(symbol)
    if ret != ft.RET_OK or exp.empty:
        log.warning("%s 无到期日: %s", symbol, exp)
        return None

    target_expiry = None
    for date_str in exp["strike_time"].tolist():
        d = datetime.date.fromisoformat(date_str[:10])
        dte = (d - today).days
        if 21 <= dte <= 60:
            target_expiry = date_str
            break

    if target_expiry is None:
        # 找不到 21-60 天的，退而求其次用最近超过 7 天的
        for date_str in exp["strike_time"].tolist():
            d = datetime.date.fromisoformat(date_str[:10])
            if (d - today).days > 7:
                target_expiry = date_str
                break

    if target_expiry is None:
        log.warning("%s 找不到合适到期日", symbol)
        return None

    # ── 从期权链取 ATM Call 的代码 ─────────────────────
    ret, chain = ctx.get_option_chain(symbol, start=target_expiry, end=target_expiry)
    if ret != ft.RET_OK or chain.empty:
        log.warning("%s 期权链失败: %s", symbol, chain)
        return None

    calls = chain[chain["option_type"] == "CALL"].copy()
    if calls.empty:
        log.warning("%s 无 Call 数据", symbol)
        return None

    calls["diff"] = (calls["strike_price"].astype(float) - current_price).abs()
    atm_code = calls.nsmallest(1, "diff").iloc[0]["code"]
    atm_strike = calls.nsmallest(1, "diff").iloc[0]["strike_price"]

    # ── 用快照读取该合约的 IV ──────────────────────────
    ret, oснap = ctx.get_market_snapshot([atm_code])
    if ret != ft.RET_OK:
        log.warning("%s 期权快照失败: %s", atm_code, oснap)
        return None

    raw_iv = oснap["option_implied_volatility"].iloc[0]
    if raw_iv is None or str(raw_iv) in ("nan", ""):
        log.warning("%s IV 为空", atm_code)
        return None

    iv = float(raw_iv)
    # Futu 返回的是百分比形式（如 35.2），转为小数（0.352）
    if iv > 5:
        iv = iv / 100.0

    dte = (datetime.date.fromisoformat(target_expiry[:10]) - today).days
    log.info("  %-12s 价=%.2f  到期=%s(%dDTE)  行权价=%.1f  IV=%.1f%%",
             symbol, current_price, target_expiry[:10], dte, float(atm_strike), iv * 100)
    return iv


def save(symbol: str, date: str, iv: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO iv_history (symbol, date, iv) VALUES (?, ?, ?)",
        (symbol, date, iv),
    )
    conn.commit()
    conn.close()


def collect_today():
    init_db()
    today_str = datetime.date.today().isoformat()
    log.info("===== 开始采集 %s =====", today_str)

    ctx = ft.OpenQuoteContext(host=FUTU_HOST, port=FUTU_PORT)
    ok = 0
    for symbol in WATCHLIST:
        iv = get_atm_iv(ctx, symbol)
        if iv is not None:
            save(symbol, today_str, iv)
            ok += 1
    ctx.close()

    log.info("===== 完成 %d/%d =====", ok, len(WATCHLIST))


if __name__ == "__main__":
    collect_today()
