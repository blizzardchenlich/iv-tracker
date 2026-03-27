"""
手动补录工具
当某个标的 API 未返回数据时，手动输入 IV百分位 值
"""

import sqlite3
import datetime
from config import WATCHLIST, DB_PATH


def main():
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)

    # 找出今天缺失的标的
    existing = {
        row[0] for row in
        conn.execute("SELECT symbol FROM iv_history WHERE date=?", (today,))
    }
    missing = [s for s in WATCHLIST if s not in existing]

    if not missing:
        print(f"{today} 所有标的数据已完整")
        conn.close()
        return

    print(f"以下标的今天（{today}）缺少数据，请手动输入 IV百分位（0-100），跳过请直接回车：\n")
    for symbol in missing:
        raw = input(f"  {symbol} IV百分位 = ").strip()
        if not raw:
            continue
        try:
            val = float(raw)
            assert 0 <= val <= 100
            conn.execute(
                "INSERT OR REPLACE INTO iv_history (symbol, date, iv_pct) VALUES (?, ?, ?)",
                (symbol, today, val),
            )
            conn.commit()
            print(f"    已保存 {symbol} = {val}%")
        except (ValueError, AssertionError):
            print(f"    无效值，跳过")

    conn.close()
    print("\n补录完成")


if __name__ == "__main__":
    main()
