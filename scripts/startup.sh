#!/bin/bash

# 创建数据目录
mkdir -p /app/data

# 启动Web应用（后台运行）
cd /app/web-app
python3 app.py &

# 启动原始VNC服务
exec /dockerstartup/vnc_startup.sh
