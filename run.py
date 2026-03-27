"""
主入口：Barchart API 采集今日 IV百分位 → 刷新图表
每日收盘后运行一次（美东时间 16:00 之后）
"""

from scraper import collect_today
from visualizer import generate_chart


def main():
    collect_today()
    generate_chart()


if __name__ == "__main__":
    main()
