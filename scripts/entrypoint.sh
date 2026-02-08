#!/bin/bash
set -e

echo "==================================="
echo "Ubuntu Automation (Ultra-Slim) Starting..."
echo "==================================="

# === PaaS Swap 优化 ===
if [ ! -f /swapfile ] && [ -w / ]; then
    SWAP_SIZE=${SWAP_SIZE_MB:-512}
    echo "Creating ${SWAP_SIZE}MB swap file for PaaS optimization..."
    dd if=/dev/zero of=/swapfile bs=1M count=${SWAP_SIZE} 2>/dev/null || true
    chmod 600 /swapfile 2>/dev/null || true
    mkswap /swapfile 2>/dev/null || true
    swapon /swapfile 2>/dev/null || true
    echo "Swap file created successfully."
fi

# === VNC Resolution Fix ===
if [ -n "${VNC_RESOLUTION}" ]; then
    echo "Using custom VNC resolution: ${VNC_RESOLUTION}"
    sed -i "s/1024x600/${VNC_RESOLUTION}/g" /etc/supervisor/conf.d/services.conf
fi

# 1. 检查 Chrome
if command -v google-chrome-stable &> /dev/null; then
    echo "✅ Google Chrome Installed"
else
    echo "❌ Chrome Not Found"
fi

# === 关键修复：清理 Chrome Profile 锁文件 ===
# 在 PaaS/K8s 环境中，共享存储上的锁文件可能被旧容器遗留
# 导致新容器无法启动 Chrome
CHROME_CONFIG="/home/headless/.config/google-chrome"
if [ -d "$CHROME_CONFIG" ]; then
    echo "🧹 Cleaning Chrome profile locks..."
    rm -f "$CHROME_CONFIG/SingletonLock" 2>/dev/null || true
    rm -f "$CHROME_CONFIG/SingletonSocket" 2>/dev/null || true
    rm -f "$CHROME_CONFIG/SingletonCookie" 2>/dev/null || true
    # 清理崩溃恢复锁
    rm -rf "$CHROME_CONFIG/Crash Reports/lock" 2>/dev/null || true
    echo "✅ Chrome profile locks cleaned"
fi

# 2. VNC Pass
mkdir -p /home/headless/.vnc
chown headless:headless /home/headless/.vnc
su - headless -c "echo ${VNC_PW:-admin} | vncpasswd -f > /home/headless/.vnc/passwd"
chmod 600 /home/headless/.vnc/passwd

# 3. 权限修正
mkdir -p "/home/headless/.config/autokey/data/My Phrases"
mkdir -p "/home/headless/.config/autokey/data/My Phrases"
mkdir -p "/home/headless/.config/autokey/data/Sample Scripts"
mkdir -p "/home/headless/.config/autokey/data/MyScripts"
chown -R headless:headless /home/headless/.config

# 4. DB Init (系统 Python)
echo "Init DB..."
cd /app/web-app
python3 init_db.py

# 5. Cloudflare
CF_ENABLE=$(echo "${ENABLE_CLOUDFLARE_TUNNEL}" | tr '[:upper:]' '[:lower:]')
if [ "$CF_ENABLE" == "true" ]; then
    CMD=""
    if [ -n "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
        echo "☁️ Cloudflare Tunnel: Token Mode (Remote Management)"
        CMD="/usr/bin/cloudflared tunnel run --token ${CLOUDFLARE_TUNNEL_TOKEN}"
    else
        echo "☁️ Cloudflare Tunnel: Quick Tunnel Mode (Random Domain)"
        CMD="/usr/bin/cloudflared tunnel --url http://localhost:5000"
    fi

    cat << EOF >> /etc/supervisor/conf.d/services.conf
[program:cloudflared]
command=${CMD}
autostart=true
autorestart=true
user=root
priority=60
stdout_logfile=/app/logs/cloudflared.log
stderr_logfile=/app/logs/cloudflared-error.log
EOF
fi

chown -R headless:headless /app/data /app/logs

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/services.conf
