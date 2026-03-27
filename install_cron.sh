#!/bin/bash
# 设置每日自动采集（美股收盘后，北京时间凌晨 5:05 / 夏令时 4:05）
# 根据你的时区调整

PYTHON=$(which python3)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 夏令时（3月-11月）：美股16:00 ET = 北京4:00 AM
# 非夏令时（11月-3月）：美股16:00 ET = 北京5:00 AM

# 写入 crontab（每天 4:15 AM 和 5:15 AM 都跑，自动跳过非交易日不会报错）
CRON_LINE_1="15 4 * * 2-6 cd $SCRIPT_DIR && $PYTHON run.py >> $SCRIPT_DIR/iv_tracker.log 2>&1"
CRON_LINE_2="15 5 * * 2-6 cd $SCRIPT_DIR && $PYTHON run.py >> $SCRIPT_DIR/iv_tracker.log 2>&1"

# 添加到 crontab（避免重复）
(crontab -l 2>/dev/null | grep -v "iv_tracker"; echo "$CRON_LINE_1"; echo "$CRON_LINE_2") | crontab -

echo "Cron 任务已安装："
crontab -l | grep iv_tracker
echo ""
echo "日志文件: $SCRIPT_DIR/iv_tracker.log"
