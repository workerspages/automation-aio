#!/bin/bash
set -e

# --- 初始化环境 ---
echo "正在初始化环境..."
USERNAME="headless"
USERID=1001
GROUPID=1001

# 确保目录存在且权限正确
mkdir -p /app/data /app/logs /home/$USERNAME/.vnc
chown -R $USERID:$GROUPID /app /home/$USERNAME

# 创建VNC密码文件
if [ ! -f "/home/$USERNAME/.vncpasswd" ]; then
    echo "创建VNC密码文件..."
    echo "${VNC_PW:-vncpassword}" | vncpasswd -f > "/home/$USERNAME/.vncpasswd"
    chmod 600 "/home/$USERNAME/.vncpasswd"
fi

# 确保 Xauthority 文件存在
touch "/home/$USERNAME/.Xauthority"
chown $USERID:$GROUPID "/home/$USERNAME/.Xauthority"
chmod 600 "/home/$USERNAME/.Xauthority"

# 启动 Cloudflare Tunnel (如果启用)
if [ "$ENABLE_CLOUDFLARE_TUNNEL" = "true" ]; then
    echo "启动 Cloudflare Tunnel..."
    if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
        cloudflared tunnel --no-autoupdate run --token "$CLOUDFLARE_TUNNEL_TOKEN" > /app/logs/cloudflared.log 2>&1 &
    else
        echo "缺少 Cloudflare 隧道令牌，隧道未启动"
    fi
fi

# 初始化数据库和管理员账户，通过执行外部 Python 脚本
echo "正在初始化数据库..."
cd /app/web-app
/opt/venv/bin/python3 init_db.py

echo "初始化完成，启动 supervisord..."
exec /usr/bin/supervisord -c /app/scripts/supervisord.conf
