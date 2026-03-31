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
_ETF_FILE       = os.path.join(os.path.dirname(__file__), "etf_watchlist.json")

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

# 合并 ETF 列表（去重，保持原股票列表顺序，ETF 追加在后）
if os.path.exists(_ETF_FILE):
    with open(_ETF_FILE) as _f:
        _etf_data = json.load(_f)["etfs"]
    _etfs = [t for group in _etf_data.values() for t in group]
    _existing = set(WATCHLIST)
    WATCHLIST = WATCHLIST + [t for t in _etfs if t not in _existing]
