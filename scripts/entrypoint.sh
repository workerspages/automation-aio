#!/bin/bash
set -e

echo "==================================="
echo "Ubuntu 自动化平台启动中..."
echo "==================================="

# 检查 Chrome 安装
if command -v google-chrome-stable &> /dev/null; then
    echo "✅ Google Chrome 已安装"
    google-chrome-stable --version
else
    echo "❌ Google Chrome 未找到"
fi

# 配置 VNC 密码 (动态生成)
echo "配置 VNC 密码..."
mkdir -p /home/headless/.vnc
chown headless:headless /home/headless/.vnc
# 使用环境变量 VNC_PW，默认值为 admin
su - headless -c "echo ${VNC_PW:-admin} | vncpasswd -f > /home/headless/.vnc/passwd"
chmod 600 /home/headless/.vnc/passwd
chown headless:headless /home/headless/.vnc/passwd

echo "VNC密码文件已生成"

mkdir -p /app/data /app/logs /home/headless/Downloads
chown -R headless:headless /app /home/headless /opt/venv

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

echo "==================================="
echo "启动服务..."
echo "==================================="

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/services.conf
