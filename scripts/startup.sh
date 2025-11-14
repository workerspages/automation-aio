#!/bin/bash

# 自动创建VNC认证文件（初次构建或重置容器时可选，生产环境建议配置为固定密码）
VNC_PASSWD_FILE="/home/headless/.vncpasswd"
if [ ! -f "$VNC_PASSWD_FILE" ]; then
  mkdir -p /home/headless
  # 设置默认密码为：vncpassword（可根据需要进行更改）
  echo "vncpassword" | vncpasswd -f > "$VNC_PASSWD_FILE"
  chown headless:headless "$VNC_PASSWD_FILE"
  chmod 600 "$VNC_PASSWD_FILE"
fi

# 自动创建Xauthority文件（避免X server权限问题）
if [ ! -f "/home/headless/.Xauthority" ]; then
  touch /home/headless/.Xauthority
  chown headless:headless /home/headless/.Xauthority
fi

# 启动VNC服务器
/usr/bin/Xvnc :1 \
    -depth 24 \
    -geometry 1360x768 \
    -rfbport 5901 \
    -auth /home/headless/.Xauthority \
    -rfbauth /home/headless/.vncpasswd \
    -desktop vncdesktop \
    -pn &

# 保证VNC服务已经启动，再启动桌面环境
sleep 4

export DISPLAY=:1

# 启动Xfce桌面（会在VNC窗口中可见）
startxfce4 &

# 可选：提前启动AutoKey主界面(手动录制或交互时用，需要窗口)
# nohup autokey-gtk &

# 等待桌面完全准备好
sleep 8

# 启动主程序(自动化平台、Flask等)
python3 /app/web-app/app.py
