#!/bin/bash
# 小水对话版 · 双击启动

cd ~/小水对话版

echo "💧 正在启动小水对话版..."
echo ""

(sleep 2 && open http://localhost:8002) &

python3 server.py
