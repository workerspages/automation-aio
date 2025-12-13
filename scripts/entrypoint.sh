#!/bin/bash
set -e

echo "==================================="
echo "Ubuntu 自动化平台启动中..."
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
# 使用环境变量 VNC_PW，默认值为 admin
su - headless -c "echo ${VNC_PW:-admin} | vncpasswd -f > /home/headless/.vnc/passwd"
chmod 600 /home/headless/.vnc/passwd
chown headless:headless /home/headless/.vnc/passwd

echo "VNC密码文件已生成"

# 3. 权限修正 (通用)
echo "修正通用目录权限..."
mkdir -p /app/data /app/logs /home/headless/Downloads
chown -R headless:headless /app /home/headless /opt/venv

# ===================================================================
# 3.5 [修复] 强制修正 AutoKey 目录权限 (解决 Errno 13 错误)
# ===================================================================
echo "修正 AutoKey 配置权限..."
# 预先创建 AutoKey 需要的目录结构
mkdir -p "/home/headless/.config/autokey/data/My Phrases"
mkdir -p "/home/headless/.config/autokey/data/MyScripts"
# 确保整个 .config 目录属于 headless 用户
chown -R headless:headless /home/headless/.config
# ===================================================================

# 4. 初始化数据库
echo "初始化数据库..."
/usr/local/bin/init-database || {
    echo "数据库初始化备用方法..."
    cd /app/web-app
    /opt/venv/bin/python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app/web-app')
try:
    from app import app, db, User
    import os
    with app.app_context():
        db.create_all()
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        if not User.query.filter_by(username=admin_username).first():
            user = User(username=admin_username)
            user.password = admin_password
            db.session.add(user)
            db.session.commit()
            print(f"✅ Admin user {admin_username} created")
        else:
            print(f"✅ Admin user {admin_username} exists")
except Exception as e:
    print(f"❌ Database init failed: {e}")
    import traceback
    traceback.print_exc()
PYEOF
}

# 5. 配置 Cloudflare Tunnel
CF_ENABLE=$(echo "${ENABLE_CLOUDFLARE_TUNNEL}" | tr '[:upper:]' '[:lower:]')

if [ "$CF_ENABLE" == "true" ]; then
    echo "🌐 [Cloudflare] 检测到启用开关..."
    if [ -z "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
        echo "❌ [Cloudflare] 错误: 启用了开关但未提供 Token！"
    else
        echo "✅ [Cloudflare] 正在写入 Supervisor 配置..."
        cat << EOF >> /etc/supervisor/conf.d/services.conf

[program:cloudflared]
command=/usr/bin/cloudflared tunnel run --token ${CLOUDFLARE_TUNNEL_TOKEN}
autostart=true
autorestart=true
stdout_logfile=/app/logs/cloudflared.log
stderr_logfile=/app/logs/cloudflared-error.log
user=root
priority=50
EOF
        echo "✅ [Cloudflare] 配置写入完成。"
    fi
else
    echo "⚪ [Cloudflare] 未启用 (ENABLE=${CF_ENABLE})"
fi

echo "修正数据库权限..."
chown -R headless:headless /app/data

echo "==================================="
echo "启动服务..."
echo "==================================="

tail -n 15 /etc/supervisor/conf.d/services.conf

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/services.conf
