#!/bin/bash
set -e

echo "==================================="
echo "Ubuntu Automation (Ultra-Slim) Starting..."
echo "==================================="

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
mkdir -p "/home/headless/.config/autokey/data/MyScripts"
chown -R headless:headless /home/headless/.config

# 4. DB Init (系统 Python)
echo "Init DB..."
cd /app/web-app
python3 init_db.py

# 5. Cloudflare
CF_ENABLE=$(echo "${ENABLE_CLOUDFLARE_TUNNEL}" | tr '[:upper:]' '[:lower:]')
if [ "$CF_ENABLE" == "true" ] && [ -n "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    cat << EOF >> /etc/supervisor/conf.d/services.conf
[program:cloudflared]
command=/usr/bin/cloudflared tunnel run --token ${CLOUDFLARE_TUNNEL_TOKEN}
autostart=true
autorestart=true
user=root
priority=60
EOF
fi

chown -R headless:headless /app/data /app/logs

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/services.conf
