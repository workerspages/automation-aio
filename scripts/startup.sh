#!/bin/bash
set -e
set -x

# 获取用户信息
USERNAME=$(whoami)
USERID=$(id -u)
echo "当前用户: $USERNAME (UID: $USERID)"

echo "准备X11环境..."
# 清理X1锁文件
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true

# 确保用户目录存在并创建 Xauthority 文件
if [ ! -d "/home/$USERNAME" ]; then
  mkdir -p "/home/$USERNAME"
  chown $USERID:$USERID "/home/$USERNAME"
fi
touch "/home/$USERNAME/.Xauthority"
chmod 600 "/home/$USERNAME/.Xauthority"

export DISPLAY=:1
export XAUTHORITY="/home/$USERNAME/.Xauthority"

echo "DISPLAY设置为: $DISPLAY"
echo "XAUTHORITY设置为: $XAUTHORITY"

# 如果没有VNC密码文件，创建一个
if [ ! -f "/home/$USERNAME/.vncpasswd" ]; then
  echo "创建VNC密码文件..."
  echo "${VNC_PW:-vncpassword}" | vncpasswd -f > "/home/$USERNAME/.vncpasswd"
  chmod 600 "/home/$USERNAME/.vncpasswd"
fi

# 启动 VNC 服务器保证 DISPLAY 可用
echo "启动VNC服务器..."
/usr/bin/Xvnc :1 -desktop "Ubuntu自动化平台" -geometry 1360x768 -depth 24 \
    -rfbport 5901 -rfbauth "/home/$USERNAME/.vncpasswd" -auth "$XAUTHORITY" \
    -SecurityTypes VncAuth -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents \
    -AcceptCutText -SendCutText -localhost no > /tmp/vnc.log 2>&1 &

VNC_PID=$!
sleep 5

if ! ps -p $VNC_PID > /dev/null; then
  echo "错误: VNC服务器启动失败"
  cat /tmp/vnc.log
  exit 1
fi

# VNC启动后再处理xauth
if [ -z "$(xauth list :1 2>/dev/null)" ]; then
  xauth generate :1 . trusted || xauth add :1 . $(mcookie)
fi

# 启动Xfce桌面环境
echo "启动Xfce桌面环境..."
DISPLAY=:1 startxfce4 > /tmp/xfce.log 2>&1 &
XFCE_PID=$!
sleep 10
if ! ps -p $XFCE_PID > /dev/null; then
  echo "警告: Xfce进程可能已退出，检查日志..."
  cat /tmp/xfce.log
fi

echo "验证X服务器连接..."
DISPLAY=:1 xdpyinfo > /dev/null 2>&1 && echo "X服务器连接正常" || echo "警告: X服务器连接异常"

echo "启动noVNC服务..."
/usr/bin/websockify --web=/usr/share/novnc 6901 localhost:5901 > /tmp/novnc.log 2>&1 &
NOVNC_PID=$!
sleep 3

echo "启动Flask Web管理平台..."
cd /app/web-app
python3 app.py > /tmp/flask.log 2>&1 &
FLASK_PID=$!

echo "所有服务启动完成!"

# 守护进程，监控关键服务
while true; do
  sleep 60
  if ! ps -p $VNC_PID > /dev/null; then
    echo "错误: VNC服务器已停止"
    exit 1
  fi
  if ! ps -p $FLASK_PID > /dev/null; then
    echo "Flask服务已停止，尝试重启..."
    cd /app/web-app
    python3 app.py > /tmp/flask.log 2>&1 &
    FLASK_PID=$!
  fi
done
