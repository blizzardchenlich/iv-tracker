"""
一次性校准工具
告诉脚本：① IV百分位数字在屏幕哪个区域  ② 每个标的在富途列表的位置
"""

import json
import time
import pyautogui
import mss
from PIL import Image

from config import WATCHLIST

CAL_FILE = "calibration.json"


def countdown(seconds=3):
    for i in range(seconds, 0, -1):
        print(f"  {i}...", end="\r", flush=True)
        time.sleep(1)
    x, y = pyautogui.position()
    print(f"  坐标: ({x}, {y})          ")
    return x, y


def grab(region) -> Image.Image:
    with mss.mss() as sct:
        shot = sct.grab(region)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def main():
    cal = {}
    print("=" * 55)
    print("  富途 IV百分位 屏幕校准工具")
    print("=" * 55)
    print("\n请确保富途牛牛已打开，并显示在屏幕上\n")

    # ── 步骤 1：定位 IV百分位 数字区域 ──────────────────
    print("【步骤 1/2】定位 IV百分位 数值")
    print("1. 在富途中打开任意一支有期权的美股（如 AAPL）的期权页面")
    print("2. 找到页面上「IV百分位」旁边的数字（如 67%）")
    input("3. 将鼠标悬停在那个数字正上方，按 Enter 开始倒计时 → ")

    x, y = countdown()
    region = {"left": x - 80, "top": y - 28, "width": 160, "height": 56}
    cal["iv_pct_region"] = region

    # 保存测试截图供验证
    img = grab(region)
    img.save("calibration_test.png")
    print(f"\n  已截图 → calibration_test.png")
    print("  用访达打开该图片，确认数字完整显示在图中")
    answer = input("  数字是否清晰完整？(y/n) → ").strip().lower()
    if answer != "y":
        print("  请重新运行此脚本，调整鼠标位置后再试")
        return

    # ── 步骤 2：定位每个标的在富途列表中的位置 ─────────
    print(f"\n【步骤 2/2】记录每个标的的列表位置（共 {len(WATCHLIST)} 个）")
    print("做法：在富途客户端点击该标的（使其期权页面出现），")
    print("     然后将鼠标移回那个列表行上，按 Enter\n")

    cal["stocks"] = {}
    for i, symbol in enumerate(WATCHLIST, 1):
        name = symbol.split(".")[-1]
        input(f"  [{i}/{len(WATCHLIST)}] 点开 {name} 的期权页，鼠标移到列表行，按 Enter → ")
        x, y = countdown()
        cal["stocks"][symbol] = {"x": x, "y": y}
        # 顺手保存一份当前截图用于调试
        img = grab(region)
        img.save(f"cal_check_{name}.png")

    with open(CAL_FILE, "w", encoding="utf-8") as f:
        json.dump(cal, f, indent=2, ensure_ascii=False)

    print(f"\n✓ 校准完成，保存到 {CAL_FILE}")
    print("现在可以运行:  python3 run.py")


if __name__ == "__main__":
    main()
