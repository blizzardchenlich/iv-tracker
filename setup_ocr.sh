#!/bin/bash
echo "=== 安装 OCR 依赖 ==="

# 1. Tesseract OCR 引擎
if ! command -v tesseract &>/dev/null; then
    echo "安装 Tesseract..."
    brew install tesseract
else
    echo "Tesseract 已安装: $(tesseract --version 2>&1 | head -1)"
fi

# 2. Python 包
pip3 install pyautogui mss Pillow pytesseract

echo ""
echo "=== 安装完成 ==="
echo ""
echo "重要：还需要给终端授权"
echo "  系统设置 → 隐私与安全性 → 辅助功能 → 添加「终端」"
echo "  系统设置 → 隐私与安全性 → 屏幕录制 → 添加「终端」"
