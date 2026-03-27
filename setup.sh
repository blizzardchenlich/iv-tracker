#!/bin/bash
# 安装依赖（macOS）

echo "=== 安装 IV 追踪器依赖 ==="

# 检查 Python 版本
python3 --version || { echo "请先安装 Python 3.8+"; exit 1; }

# 安装 Python 包
pip3 install requests pandas plotly

echo ""
echo "=== 安装完成 ==="
echo ""
echo "下一步："
echo "1. 在 config.py 中填入你的 Barchart API Key"
echo "   免费注册：https://www.barchart.com/ondemand/free-api-key"
echo "2. 在 config.py 中编辑你要追踪的标的列表（WATCHLIST）"
echo "3. 运行: python3 run.py"
