"""
成分股列表更新工具
从以下来源获取最新成分股，合并去重后保存到 watchlist.json：
  - S&P 500：GitHub (datasets/s-and-p-500-companies)
  - Nasdaq 100：slickcharts.com

建议每月运行一次（成分股调整不频繁）：
  python3 update_watchlist.py
"""

import json
import requests
import csv
from io import StringIO
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
OUTPUT_FILE = "watchlist.json"


def fetch_sp500():
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    tickers = [row["Symbol"].strip() for row in csv.DictReader(StringIO(r.text))]
    # BRK.B → BRK-B（Yahoo/optioncharts 格式）
    tickers = [t.replace(".", "-") for t in tickers]
    print(f"  S&P 500:    {len(tickers)} 个")
    return tickers


def fetch_nasdaq100():
    r = requests.get("https://www.slickcharts.com/nasdaq100", headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    tickers = []
    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if len(cols) >= 3:
            ticker = cols[2].get_text(strip=True)
            if ticker:
                tickers.append(ticker)
    print(f"  Nasdaq 100: {len(tickers)} 个")
    return tickers


def update():
    print("正在获取成分股列表...")

    sp500  = fetch_sp500()
    nasdaq = fetch_nasdaq100()

    # 合并去重，保持顺序（S&P 500 优先）
    combined = list(dict.fromkeys(sp500 + nasdaq))
    print(f"  合并去重后: {len(combined)} 个标的")

    with open(OUTPUT_FILE, "w") as f:
        json.dump({"tickers": combined}, f, indent=2)

    print(f"\n已保存到 {OUTPUT_FILE}")
    print(f"前10个: {combined[:10]}")


if __name__ == "__main__":
    update()
