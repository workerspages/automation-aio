#!/bin/bash
set -e

echo "==================================="
echo "Ubuntu 自动化平台 (Slim) 启动中..."
echo "==================================="

# 1. 检查 Chrome 安装
if command -v google-chrome-stable &> /dev/null; then
    echo "✅ Google Chrome 已安装"
    google-chrome-stable --version
else
    echo "❌ Google Chrome 未找到"
fi

# 2. 配置 VNC 密码
echo "配置 VNC 密码..."
mkdir -p /home/headless/.vnc
chown headless:headless /home/headless/.vnc
su - headless -c "echo ${VNC_PW:-admin} | vncpasswd -f > /home/headless/.vnc/passwd"
chmod 600 /home/headless/.vnc/passwd
chown headless:headless /home/headless/.vnc/passwd

# 3. 权限修正
echo "修正 AutoKey 配置权限..."
mkdir -p "/home/headless/.config/autokey/data/My Phrases"
mkdir -p "/home/headless/.config/autokey/data/MyScripts"
chown -R headless:headless /home/headless/.config

# 4. 初始化数据库
echo "初始化数据库..."
# 使用 Python 直接初始化，更稳健
cd /app/web-app
/opt/venv/bin/python3 init_db.py

# 5. 配置 Cloudflare Tunnel (可选)
CF_ENABLE=$(echo "${ENABLE_CLOUDFLARE_TUNNEL}" | tr '[:upper:]' '[:lower:]')
if [ "$CF_ENABLE" == "true" ] && [ -n "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    echo "✅ [Cloudflare] 启用..."
    cat << EOF >> /etc/supervisor/conf.d/services.conf

[program:cloudflared]
command=/usr/bin/cloudflared tunnel run --token ${CLOUDFLARE_TUNNEL_TOKEN}
autostart=true
autorestart=true
stdout_logfile=/app/logs/cloudflared.log
stderr_logfile=/app/logs/cloudflared-error.log
user=root
priority=60
EOF
fi

echo "修正数据目录权限..."
chown -R headless:headless /app/data /app/logs

echo "==================================="
echo "启动 Supervisor 服务..."
echo "==================================="

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/services.conf
