#!/bin/bash
set -e

echo "==================================="
echo "Ubuntu Automation (Ultra-Slim) Starting..."
echo "==================================="

# === PaaS Swap 优化 ===
if [ ! -f /swapfile ] && [ -w / ]; then
    echo "Creating 512MB swap file for PaaS optimization..."
    dd if=/dev/zero of=/swapfile bs=1M count=512 2>/dev/null || true
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
