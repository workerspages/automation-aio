# ===================================================================
# 基础镜像及环境变量
# ===================================================================
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

USER root

ENV TZ=Asia/Shanghai \
    LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8 \
    DATABASE_URL=sqlite:////app/data/tasks.db \
    SQLALCHEMY_DATABASE_URI=sqlite:////app/data/tasks.db \
    SQLALCHEMY_TRACK_MODIFICATIONS=false \
    SCHEDULER_TIMEZONE=Asia/Shanghai \
    SCHEDULER_API_ENABLED=true \
    SCRIPTS_DIR=/home/headless/Downloads \
    MAX_SCRIPT_TIMEOUT=300 \
    RETRY_FAILED_TASKS=true \
    MAX_RETRIES=3 \
    LOG_LEVEL=INFO \
    LOG_FILE=/app/data/automation.log \
    FIREFOX_BINARY=/usr/bin/chromium-browser \
    GECKODRIVER_PATH=/usr/bin/geckodriver \
    FLASK_ENV=production \
    FLASK_DEBUG=false \
    HOST=0.0.0.0 \
    PORT=5000 \
    DISPLAY=:1 \
    VNC_PORT=5901 \
    NOVNC_PORT=6901 \
    VNC_RESOLUTION=1360x768 \
    VNC_COL_DEPTH=24 \
    VNC_PW=xPuCyg4h \
    ADMIN_USERNAME=admin \
    ADMIN_PASSWORD=xPuCyg4hE7c9Eq6r \
    XDG_CONFIG_DIRS=/etc/xdg/xfce4:/etc/xdg \
    XDG_DATA_DIRS=/usr/local/share:/usr/share/xfce4:/usr/share \
    XDG_CURRENT_DESKTOP=XFCE \
    XDG_SESSION_DESKTOP=xfce

# ===================================================================
# 安装系统依赖及Chromium浏览器
# ===================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git vim nano sudo tzdata locales \
    software-properties-common gnupg2 apt-transport-https net-tools \
    iproute2 iputils-ping supervisor cron sqlite3 fonts-wqy-microhei \
    fonts-wqy-zenhei fonts-noto-cjk fonts-noto-cjk-extra language-pack-zh-hans \
    x11-utils x11-xserver-utils x11-apps xauth xserver-xorg-core xserver-xorg-video-dummy \
    tigervnc-standalone-server tigervnc-common tigervnc-tools \
    xfce4 xfce4-goodies xfce4-terminal dbus-x11 libgtk-3-0 libgtk2.0-0 \
    python3 python3-pip python3-venv python3-dev python3-gi python3-xdg python3-websockify \
    gir1.2-gtk-3.0 build-essential pkg-config gcc g++ make libffi-dev libssl-dev \
    libxml2-dev libxslt1-dev zlib1g-dev libjpeg-dev libpng-dev chromium-browser \
    gsettings-desktop-schemas dconf-cli gnome-icon-theme policykit-1 \
    xautomation kdialog imagemagick nginx nodejs npm unzip libnss3 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxrandr2 libasound2 libpangocairo-1.0-0 libpango-1.0-0 libcups2 libdbus-1-3 libxdamage1 libxfixes3 libgbm1 libxshmfence1 libxext6 libdrm2 libwayland-client0 libwayland-cursor0 libatspi2.0-0 libepoxy0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ===================================================================
# 安装Playwright及浏览器依赖
# ===================================================================
RUN export PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net && \
    npm install -g playwright && \
    npx playwright install --with-deps chromium

# ===================================================================
# 设置时区和语言
# ===================================================================
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8

# ===================================================================
# 安装GeckoDriver
# ===================================================================
RUN GECKODRIVER_VERSION="0.34.0" && \
    wget --timeout=30 --tries=3 -O /tmp/geckodriver.tar.gz \
    "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/bin/ && \
    chmod +x /usr/bin/geckodriver && \
    rm /tmp/geckodriver.tar.gz

# ===================================================================
# 安装AutoKey三件套
# ===================================================================
RUN wget https://github.com/autokey/autokey/releases/download/v0.96.0/autokey-common_0.96.0_all.deb && \
    wget https://github.com/autokey/autokey/releases/download/v0.96.0/autokey-gtk_0.96.0_all.deb && \
    wget https://github.com/autokey/autokey/releases/download/v0.96.0/autokey-qt_0.96.0_all.deb && \
    dpkg -i autokey-common_0.96.0_all.deb autokey-gtk_0.96.0_all.deb autokey-qt_0.96.0_all.deb || apt-get install -f -y && \
    rm -f autokey-common_0.96.0_all.deb autokey-gtk_0.96.0_all.deb autokey-qt_0.96.0_all.deb

# ===================================================================
# 安装Cloudflare Tunnel
# ===================================================================
RUN wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && \
    dpkg -i cloudflared-linux-amd64.deb || apt-get install -f -y && \
    rm -f cloudflared-linux-amd64.deb

RUN rm -rf /tmp/* /var/tmp/*

# ===================================================================
# 创建用户与目录
# ===================================================================
RUN groupadd -g 1001 headless && \
    useradd -u 1001 -g 1001 -m -s /bin/bash headless && \
    echo "headless ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /app/web-app /app/scripts /app/data /app/logs /home/headless/Downloads && \
    chown -R headless:headless /app /home/headless

# ===================================================================
# 复制Selenium IDE扩展并解压
# ===================================================================
COPY addons/selenium-ide.crx /opt/selenium-ide.crx
RUN mkdir -p /opt/selenium-ide-unpacked && unzip /opt/selenium-ide.crx -d /opt/selenium-ide-unpacked

# ===================================================================
# 配置VNC密码
# ===================================================================
RUN mkdir -p /home/headless/.vnc && \
    chown headless:headless /home/headless/.vnc && \
    su - headless -c "echo xPuCyg4h | vncpasswd -f > /home/headless/.vnc/passwd" && \
    chmod 600 /home/headless/.vnc/passwd && \
    chown headless:headless /home/headless/.vnc/passwd

# ===================================================================
# VNC xstartup脚本
# ===================================================================
RUN cat << 'EOF' > /home/headless/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS

if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax)
    export DBUS_SESSION_BUS_ADDRESS
fi

[ -r /etc/X11/Xresources ] && xrdb /etc/X11/Xresources
[ -r "$HOME/.Xresources" ] && xrdb -merge "$HOME/.Xresources"

xsetroot -solid grey &
xset s off &
xset -dpms &
xset s noblank &

export GTK_IM_MODULE=xim
export QT_IM_MODULE=xim
export XMODIFIERS=@im=none
export LANG=zh_CN.UTF-8
export LANGUAGE=zh_CN:zh
export LC_ALL=zh_CN.UTF-8
export XDG_CONFIG_DIRS=/etc/xdg/xfce4:/etc/xdg
export XDG_DATA_DIRS=/usr/local/share:/usr/share/xfce4:/usr/share
export XDG_CURRENT_DESKTOP=XFCE
export XDG_SESSION_DESKTOP=xfce

exec /usr/bin/startxfce4
EOF
RUN chmod +x /home/headless/.vnc/xstartup && chown headless:headless /home/headless/.vnc/xstartup

# ===================================================================
# noVNC安装
# ===================================================================
WORKDIR /tmp
RUN git clone --depth 1 https://github.com/novnc/noVNC.git /usr/share/novnc && \
    git clone --depth 1 https://github.com/novnc/websockify /usr/share/novnc/utils/websockify && \
    ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# ===================================================================
# X11和XFCE配置
# ===================================================================
RUN mkdir -p /tmp/.X11-unix /tmp/.ICE-unix && \
    chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix && \
    echo "allowed_users=anybody" > /etc/X11/Xwrapper.config

RUN mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml

RUN cat << 'EOF' > /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-power-manager" version="1.0">
  <property name="xfce4-power-manager" type="empty">
    <property name="blank-on-ac" type="int" value="0"/>
    <property name="blank-on-battery" type="int" value="0"/>
    <property name="dpms-enabled" type="bool" value="false"/>
    <property name="dpms-on-ac-sleep" type="uint" value="0"/>
    <property name="dpms-on-ac-off" type="uint" value="0"/>
  </property>
</channel>
EOF

RUN cat << 'EOF' > /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-screensaver" version="1.0">
  <property name="saver" type="empty">
    <property name="enabled" type="bool" value="false"/>
    <property name="mode" type="int" value="0"/>
  </property>
</channel>
EOF

# ===================================================================
# 设置Python虚拟环境和安装依赖
# ===================================================================
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY web-app/requirements.txt /app/web-app/
RUN pip install --no-cache-dir wheel setuptools && pip install --no-cache-dir -r /app/web-app/requirements.txt

# ===================================================================
# 复制应用代码和配置
# ===================================================================
COPY web-app/ /app/web-app/
COPY scripts/ /app/scripts/
COPY nginx.conf /etc/nginx/nginx.conf

# ===================================================================
# Supervisor配置，启动Chromium加载扩展
# ===================================================================
RUN cat << 'EOF' > /etc/supervisor/conf.d/services.conf
[supervisord]
nodaemon=true
user=root
logfile=/app/logs/supervisord.log
pidfile=/var/run/supervisord.pid

[unix_http_server]
file=/var/run/supervisor.sock
chmod=0700

[supervisorctl]
serverurl=unix:///var/run/supervisor.sock

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:vncserver]
command=/bin/bash -c "rm -f /tmp/.X1-lock /tmp/.X11-unix/X1; su - headless -c 'vncserver :1 -geometry 1360x768 -depth 24 -rfbport 5901 -localhost no -fg'"
autostart=true
autorestart=true
stdout_logfile=/app/logs/vncserver.log
stderr_logfile=/app/logs/vncserver-error.log
priority=10

[program:novnc]
command=/usr/bin/websockify --web=/usr/share/novnc 6901 localhost:5901
autostart=true
autorestart=true
stdout_logfile=/app/logs/novnc.log
stderr_logfile=/app/logs/novnc-error.log
user=headless
priority=20

[program:chromium]
command=su - headless -c "/usr/bin/chromium-browser --no-sandbox --disable-gpu --load-extension=/opt/selenium-ide-unpacked --user-data-dir=/home/headless/.config/chromium --start-maximized"
autostart=true
autorestart=true
stdout_logfile=/app/logs/chromium.log
stderr_logfile=/app/logs/chromium-error.log
user=headless
priority=15

[program:nginx]
command=/usr/sbin/nginx -g \"daemon off;\"
autostart=true
autorestart=true
stdout_logfile=/app/logs/nginx.log
stderr_logfile=/app/logs/nginx-error.log
priority=30

[program:webapp]
command=/opt/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:8000 app:app
directory=/app/web-app
autostart=true
autorestart=true
stdout_logfile=/app/logs/webapp.log
stderr_logfile=/app/logs/webapp-error.log
environment=HOME=\"/home/headless\",USER=\"headless\",PATH=\"/opt/venv/bin:%(ENV_PATH)s\"
priority=40
EOF

# ===================================================================
# 数据库初始化脚本
# ===================================================================
RUN cat << 'EOF' > /usr/local/bin/init-database
#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, '/app/web-app')

try:
    from app import app, db, User
    
    with app.app_context():
        print("创建数据库表...")
        db.create_all()
        
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        existing_user = User.query.filter_by(username=admin_username).first()
        if not existing_user:
            user = User(username=admin_username)
            user.password = admin_password
            db.session.add(user)
            db.session.commit()
            print(f"✅ 管理员用户已创建: {admin_username}")
        else:
            print(f"✅ 管理员用户已存在: {admin_username}")
        print("数据库初始化完成!")
        sys.exit(0)
except Exception as e:
    print(f"❌ 数据库初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

RUN chmod +x /usr/local/bin/init-database

# ===================================================================
# Entrypoint脚本
# ===================================================================
RUN cat << 'EOF' > /app/scripts/entrypoint.sh
#!/bin/bash
set -e

echo "==================================="
echo "Ubuntu 自动化平台启动中..."
echo "==================================="

if command -v chromium-browser &> /dev/null; then
    echo "✅ Chromium 已安装"
    chromium-browser --version
else
    echo "❌ Chromium 未找到"
fi

echo "VNC密码文件:"
ls -lh /home/headless/.vnc/passwd
hexdump -C /home/headless/.vnc/passwd | head -1

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
EOF

RUN chmod +x /app/scripts/entrypoint.sh

# ===================================================================
# 设置权限及端口暴露
# ===================================================================
RUN chown -R headless:headless /app /home/headless /opt/venv \
    && chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true \
    && chmod +x /app/scripts/*.sh 2>/dev/null || true

EXPOSE 5000

WORKDIR /app

CMD ["/app/scripts/entrypoint.sh"]
