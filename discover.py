"""
字段探测工具 v2 —— 打印所有可用字段，不做过滤
"""

import futu as ft
from config import FUTU_HOST, FUTU_PORT, WATCHLIST

TEST_SYMBOL = WATCHLIST[0]


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def discover(symbol: str):
    ctx = ft.OpenQuoteContext(host=FUTU_HOST, port=FUTU_PORT)

    # ── 1. 股票快照：打印全部列 ──────────────────────────────
    section(f"[1] get_market_snapshot({symbol!r})  ← 全部字段")
    ret, snap = ctx.get_market_snapshot([symbol])
    if ret == ft.RET_OK:
        row = snap.iloc[0]
        for col in snap.columns:
            print(f"  {col:<50} = {row[col]}")
    else:
        print(f"  失败: {snap}")

    # ── 2. 取第一个期权到期日 ────────────────────────────────
    section(f"[2] get_option_expiration_date({symbol!r})")
    ret2, exp = ctx.get_option_expiration_date(symbol)
    if ret2 != ft.RET_OK or exp.empty:
        print(f"  失败或无到期日: {exp}")
        ctx.close()
        return

    first_date = exp["strike_time"].iloc[0]
    print(f"  最近到期日: {first_date}")
    print(f"  全部列: {list(exp.columns)}")

    # ── 3. 期权链：打印单条记录的全部字段 ───────────────────
    section(f"[3] get_option_chain({symbol!r}, start={first_date!r})  ← 全部字段")
    ret3, chain = ctx.get_option_chain(symbol, start=first_date, end=first_date)
    if ret3 == ft.RET_OK and not chain.empty:
        print(f"  共 {len(chain)} 条期权，以下是第一条记录的所有字段：\n")
        row3 = chain.iloc[0]
        for col in chain.columns:
            print(f"  {col:<50} = {row3[col]}")
    else:
        print(f"  失败: {chain}")

    # ── 4. 用期权代码做快照（看期权层面有无 iv_rank）────────
    if ret3 == ft.RET_OK and not chain.empty:
        option_code = chain["code"].iloc[0]
        section(f"[4] get_market_snapshot({option_code!r})  ← 期权合约快照")
        ret4, oснap = ctx.get_market_snapshot([option_code])
        if ret4 == ft.RET_OK:
            row4 = oснap.iloc[0]
            for col in oснap.columns:
                print(f"  {col:<50} = {row4[col]}")
        else:
            print(f"  失败: {oснap}")

    ctx.close()
    print(f"\n{'='*60}")
    print("探测完成，把上面的输出发给我。")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    discover(TEST_SYMBOL)
