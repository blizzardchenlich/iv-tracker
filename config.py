# ============================================================
# 配置文件 - 按需修改
# ============================================================
import json
import os

# 数据存储路径
DB_PATH = "iv_data.db"

# 图表输出路径
CHART_OUTPUT = "index.html"

# ── 追踪标的 ─────────────────────────────────────────────────
# 优先读取 watchlist.json（由 update_watchlist.py 生成）
# 若文件不存在，则使用下方手动列表

_WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "watchlist.json")

if os.path.exists(_WATCHLIST_FILE):
    with open(_WATCHLIST_FILE) as _f:
        WATCHLIST = json.load(_f)["tickers"]
else:
    # 手动自选列表（未运行 update_watchlist.py 时生效）
    WATCHLIST = [
        "AAPL",
        "TSLA",
        "NVDA",
        "AMZN",
        "MSFT",
        "META",
        "GOOGL",
    ]
