"""
历史数据回填工具（可选）
如果你有历史 IV 数据（CSV 格式），可以用此脚本导入
也可以直接从当前开始积累数据

CSV 格式要求：
symbol,date,iv_pct
AAPL,2024-01-02,35.2
AAPL,2024-01-03,42.1
...
"""

import sqlite3
import pandas as pd
import sys
from scraper import init_db
from config import DB_PATH


def import_csv(filepath: str):
    """从 CSV 文件导入历史数据"""
    init_db()
    df = pd.read_csv(filepath)

    required_cols = {"symbol", "date", "iv_pct"}
    if not required_cols.issubset(df.columns):
        print(f"错误：CSV 必须包含列：{required_cols}")
        sys.exit(1)

    # iv_pct 若为小数形式（0.35）则转换为百分制（35.0）
    if df["iv_pct"].mean() <= 1.0:
        df["iv_pct"] = df["iv_pct"] * 100.0

    conn = sqlite3.connect(DB_PATH)
    for _, row in df.iterrows():
        conn.execute(
            "INSERT OR REPLACE INTO iv_history (symbol, date, iv_pct) VALUES (?, ?, ?)",
            (row["symbol"], str(row["date"])[:10], float(row["iv_pct"])),
        )
    conn.commit()
    conn.close()
    print(f"已导入 {len(df)} 条记录")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python backfill.py your_history.csv")
    else:
        import_csv(sys.argv[1])
