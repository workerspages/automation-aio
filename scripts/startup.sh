#!/bin/bash
set -e
set -x

echo "=========================================="
echo "启动 Ubuntu 自动化管理平台"
echo "=========================================="

USERNAME=$(whoami)
USERID=$(id -u)
echo "当前用户: $USERNAME (UID: $USERID)"

echo "准备X11环境..."
# 不删除目录本身，仅清理可能的旧lock文件
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true

touch /home/$USERNAME/.Xauthority
chmod 600 /home/$USERNAME/.Xauthority
xauth generate :1 . trusted 2>/dev/null || true

if [ ! -f "/home/$USERNAME/.vncpasswd" ]; then
  echo "创建VNC密码文件..."
  echo "${VNC_PW:-vncpassword}" | vncpasswd -f > "/home/$USERNAME/.vncpasswd"
  chmod 600 "/home/$USERNAME/.vncpasswd"
fi

export DISPLAY=:1
export XAUTHORITY="/home/$USERNAME/.Xauthority"

echo "DISPLAY设置为: $DISPLAY"
echo "XAUTHORITY设置为: $XAUTHORITY"

echo "启动VNC服务器..."
/usr/bin/Xvnc :1 -desktop "Ubuntu自动化平台" -geometry 1360x768 -depth 24 \
    -rfbport 5901 -rfbauth /home/$USERNAME/.vncpasswd -auth $XAUTHORITY \
    -SecurityTypes VncAuth -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents \
    -AcceptCutText -SendCutText -localhost no > /tmp/vnc.log 2>&1 &

VNC_PID=$!
echo "VNC服务器已启动 (PID: $VNC_PID)"
sleep 5

if ! ps -p $VNC_PID > /dev/null; then
    echo "错误: VNC服务器启动失败"
    cat /tmp/vnc.log
    exit 1
fi

echo "启动Xfce桌面环境..."
DISPLAY=:1 startxfce4 > /tmp/xfce.log 2>&1 &
XFCE_PID=$!
echo "Xfce已启动 (PID: $XFCE_PID)"
sleep 10

if ! ps -p $XFCE_PID > /dev/null; then
    echo "警告: Xfce进程可能已退出,检查日志..."
    cat /tmp/xfce.log
fi

echo "验证X服务器连接..."
DISPLAY=:1 xdpyinfo > /dev/null 2>&1 && echo "X服务器连接正常" || echo "警告: X服务器连接异常"

echo "启动noVNC服务..."
/usr/bin/websockify --web=/usr/share/novnc 6901 localhost:5901 > /tmp/novnc.log 2>&1 &
NOVNC_PID=$!
echo "noVNC已启动 (PID: $NOVNC_PID)"
sleep 3

echo "启动Flask Web管理平台..."
cd /app/web-app
python3 /app/web-app/app.py > /tmp/flask.log 2>&1 &
FLASK_PID=$!
echo "Flask应用已启动 (PID: $FLASK_PID)"

echo "=========================================="
echo "所有服务启动完成!"
echo "=========================================="
echo "VNC端口: 5901 (密码: ${VNC_PW:-vncpassword})"
echo "noVNC Web访问: http://localhost:6901/vnc.html"
echo "Web管理平台: http://localhost:5000"
echo "=========================================="
echo "进程状态:"
echo "  VNC (PID: $VNC_PID): $(ps -p $VNC_PID > /dev/null && echo '运行中' || echo '已停止')"
echo "  Xfce (PID: $XFCE_PID): $(ps -p $XFCE_PID > /dev/null && echo '运行中' || echo '已停止')"
echo "  noVNC (PID: $NOVNC_PID): $(ps -p $NOVNC_PID > /dev/null && echo '运行中' || echo '已停止')"
echo "  Flask (PID: $FLASK_PID): $(ps -p $FLASK_PID > /dev/null && echo '运行中' || echo '已停止')"
echo "=========================================="

while true; do
    sleep 60
    if ! ps -p $VNC_PID > /dev/null; then
        echo "错误: VNC服务器已停止"
        exit 1
    fi
    if ! ps -p $FLASK_PID > /dev/null; then
        echo "警告: Flask应用已停止,尝试重启..."
        cd /app/web-app
        python3 /app/web-app/app.py > /tmp/flask.log 2>&1 &
        FLASK_PID=$!
    fi
done
