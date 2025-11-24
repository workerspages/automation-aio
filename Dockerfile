# ===================================================================
# STAGE 1: Base Image & Dependencies
# ===================================================================
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

USER root

# 环境变量配置
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
    CHROME_BINARY=/usr/bin/google-chrome-stable \
    FLASK_ENV=production \
    FLASK_DEBUG=false \
    HOST=0.0.0.0 \
    PORT=5000 \
    DISPLAY=:1 \
    VNC_PORT=5901 \
    NOVNC_PORT=6901 \
    VNC_RESOLUTION=1360x768 \
    VNC_COL_DEPTH=24 \
    VNC_PW=admin \
    ADMIN_USERNAME=admin \
    ADMIN_PASSWORD=admin123 \
    XDG_CONFIG_DIRS=/etc/xdg/xfce4:/etc/xdg \
    XDG_DATA_DIRS=/usr/local/share:/usr/share/xfce4:/usr/share \
    XDG_CURRENT_DESKTOP=XFCE \
    XDG_SESSION_DESKTOP=xfce \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# ===================================================================
# 核心修复：准备 PPA 环境以安装非 Snap 版 Firefox
# ===================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common gnupg2 wget curl ca-certificates

# 添加 Mozilla Team PPA 并设置优先级，强制使用 deb 版本而非 Snap
RUN add-apt-repository -y ppa:mozillateam/ppa && \
    echo 'Package: *' > /etc/apt/preferences.d/mozilla-firefox && \
    echo 'Pin: release o=LP-PPA-mozillateam' >> /etc/apt/preferences.d/mozilla-firefox && \
    echo 'Pin-Priority: 1001' >> /etc/apt/preferences.d/mozilla-firefox

# ===================================================================
# 安装系统依赖 (含 Firefox .deb 版本) & 卸载屏保
# ===================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    git vim nano sudo tzdata locales net-tools \
    iproute2 iputils-ping supervisor cron sqlite3 fonts-wqy-microhei \
    fonts-wqy-zenhei fonts-noto-cjk fonts-noto-cjk-extra language-pack-zh-hans \
    x11-utils x11-xserver-utils x11-apps xauth xserver-xorg-core xserver-xorg-video-dummy \
    tigervnc-standalone-server tigervnc-common tigervnc-tools \
    xfce4 xfce4-goodies xfce4-terminal dbus-x11 libgtk-3-0 libgtk2.0-0 \
    python3 python3-pip python3-venv python3-dev python3-gi python3-xdg python3-websockify \
    gir1.2-gtk-3.0 build-essential pkg-config gcc g++ make libffi-dev libssl-dev \
    libxml2-dev libxslt1-dev zlib1g-dev libjpeg-dev libpng-dev \
    gsettings-desktop-schemas dconf-cli gnome-icon-theme policykit-1 \
    xautomation xdotool kdialog imagemagick nginx nodejs npm unzip libnss3 libatk-bridge2.0-0 \
    libx11-xcb1 libxcomposite1 libxrandr2 libasound2 libpangocairo-1.0-0 libpango-1.0-0 \
    libcups2 libdbus-1-3 libxdamage1 libxfixes3 libgbm1 libxshmfence1 libxext6 libdrm2 \
    libwayland-client0 libwayland-cursor0 libatspi2.0-0 libepoxy0 \
    actiona p7zip-full \
    firefox firefox-locale-zh-hans \
    # === 在清理缓存前执行卸载 ===
    && apt-get purge -y xfce4-screensaver gnome-screensaver xscreensaver \
    && apt-get autoremove -y \
    # ==========================
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && echo "Firefox installed version:" && firefox --version

# +++ 关键修复 1：创建 Firefox 启动器脚本 +++
# ===================================================================
RUN cat << 'EOF' > /usr/local/bin/firefox-launcher
#!/bin/bash
export DISPLAY=:1
exec /usr/bin/firefox --no-remote --disable-gpu "$@"
EOF
RUN chmod +x /usr/local/bin/firefox-launcher

# +++ 关键修复 2：修改桌面快捷方式文件，使其指向启动器脚本 +++
# ===================================================================
RUN mkdir -p /usr/share/applications && \
    cat << 'EOF' > /usr/share/applications/firefox.desktop
[Desktop Entry]
Version=1.0
Name=Firefox
Name[zh_CN]=火狐浏览器
Comment=Browse the World Wide Web
GenericName=Web Browser
Exec=/usr/local/bin/firefox-launcher %u
Terminal=false
Type=Application
Icon=firefox
Categories=Network;WebBrowser;
MimeType=text/html;text/xml;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;
StartupNotify=true
EOF

# ===================================================================
# 安装 Google Chrome
# ===================================================================
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb && \
    apt-get update && \
    apt-get install -y /tmp/chrome.deb && \
    rm /tmp/chrome.deb && \
    rm -rf /var/lib/apt/lists/*

# ===================================================================
# 配置 Chrome 启动包装器 (No-Sandbox + 禁止默认浏览器检查)
# ===================================================================
RUN mv /usr/bin/google-chrome-stable /usr/bin/google-chrome-stable.original && \
    echo '#!/bin/bash' > /usr/bin/google-chrome-stable && \
    echo 'exec /usr/bin/google-chrome-stable.original --no-sandbox --disable-gpu --no-default-browser-check --no-first-run "$@"' >> /usr/bin/google-chrome-stable && \
    chmod +x /usr/bin/google-chrome-stable

# ===================================================================
# +++ 新增配置：将 Chrome 设置为系统默认浏览器 +++
# ===================================================================
# 1. 设置 update-alternatives 优先级，使其高于 Firefox
RUN update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 && \
    update-alternatives --set x-www-browser /usr/bin/google-chrome-stable && \
    update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/bin/google-chrome-stable 200 && \
    update-alternatives --set gnome-www-browser /usr/bin/google-chrome-stable

# 2. 配置 XDG/MIME 默认关联 (针对 XFCE 桌面环境点击链接)
RUN mkdir -p /etc/xdg && \
    { \
        echo '[Default Applications]'; \
        echo 'text/html=google-chrome.desktop'; \
        echo 'x-scheme-handler/http=google-chrome.desktop'; \
        echo 'x-scheme-handler/https=google-chrome.desktop'; \
        echo 'x-scheme-handler/about=google-chrome.desktop'; \
        echo 'x-scheme-handler/unknown=google-chrome.desktop'; \
    } >> /etc/xdg/mimeapps.list

# ===================================================================
# 配置 Chrome 企业策略 (禁用默认浏览器检查、禁用安全横幅、禁用首次运行欢迎页)
# ===================================================================
RUN mkdir -p /etc/opt/chrome/policies/managed && \
    echo '{ \
      "CommandLineFlagSecurityWarningsEnabled": false, \
      "DefaultBrowserSettingEnabled": false, \
      "MetricsReportingEnabled": false, \
      "RestoreOnStartup": 4, \
      "WelcomePageOnOSUpgradeEnabled": false, \
      "CheckDefaultBrowser": false \
    }' > /etc/opt/chrome/policies/managed/managed_policies.json && \
    chmod 644 /etc/opt/chrome/policies/managed/managed_policies.json

# ===================================================================
# 配置 Firefox 插件 (可选，需确保本地有此目录，否则可注释掉)
# ===================================================================
COPY firefox-plugin/ /app/firefox-plugin/

RUN mkdir -p /etc/firefox/policies && \
    cat << 'EOF' > /etc/firefox/policies/policies.json
{
  "policies": {
    "DisplayLang": "zh-CN",
    "Extensions": {
      "Install": [
        "file:///app/firefox-plugin/selenium-ide.xpi"
      ]
    },
    "AppUpdateURL": "https://0.0.0.0/never-update"
  }
}
EOF

# ===================================================================
# 设置时区和语言
# ===================================================================
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8

# ===================================================================
# 安装AutoKey
# ===================================================================
RUN apt-get update && \
    apt-get install -y autokey-gtk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

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
# +++ 新增：注入浏览器个人配置 (Zip版) +++
# ===================================================================
# 1. 复制压缩包到临时目录
COPY browser-configs/chrome.zip /tmp/chrome.zip
COPY browser-configs/firefox.zip /tmp/firefox.zip

# 2. 解压配置、清理锁文件、修复权限
RUN mkdir -p /home/headless/.config/google-chrome && \
    mkdir -p /home/headless/.mozilla && \
    \
    echo "正在解压 Chrome 配置..." && \
    unzip -q /tmp/chrome.zip -d /home/headless/.config/google-chrome/ && \
    \
    echo "正在解压 Firefox 配置..." && \
    unzip -q /tmp/firefox.zip -d /home/headless/.mozilla/ && \
    \
    echo "清理临时文件和浏览器锁文件(防止启动崩溃)..." && \
    rm /tmp/chrome.zip /tmp/firefox.zip && \
    rm -f /home/headless/.config/google-chrome/SingletonLock && \
    rm -f /home/headless/.config/google-chrome/SingletonSocket && \
    rm -f /home/headless/.config/google-chrome/SingletonCookie && \
    find /home/headless/.mozilla -name "lock" -delete && \
    find /home/headless/.mozilla -name ".parentlock" -delete && \
    \
    echo "修正文件权限..." && \
    chown -R headless:headless /home/headless/.config /home/headless/.mozilla

# ===================================================================
# VNC xstartup脚本 (含防休眠命令)
# ===================================================================
RUN mkdir -p /home/headless/.vnc && \
    chown headless:headless /home/headless/.vnc

RUN cat << 'EOF' > /home/headless/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS

# 启动 D-Bus 并获取地址
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS

# 将 D-Bus 地址写入文件，供 WebApp 读取
echo "export DBUS_SESSION_BUS_ADDRESS='$DBUS_SESSION_BUS_ADDRESS'" > $HOME/.dbus-env
chmod 644 $HOME/.dbus-env

[ -r /etc/X11/Xresources ] && xrdb /etc/X11/Xresources
[ -r "$HOME/.Xresources" ] && xrdb -merge "$HOME/.Xresources"

# 核心：设置 X11 背景并禁用屏保、电源管理信号
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
# 配置 AutoKey 自启动 (双重保障：Desktop Entry + Supervisor)
# ===================================================================
RUN mkdir -p /home/headless/.config/autostart && \
    printf "[Desktop Entry]\nType=Application\nName=AutoKey\nExec=autokey-gtk\nTerminal=false\n" > /home/headless/.config/autostart/autokey.desktop && \
    chown -R headless:headless /home/headless/.config

# ===================================================================
# noVNC安装
# ===================================================================
WORKDIR /tmp
RUN git clone --depth 1 https://github.com/novnc/noVNC.git /usr/share/novnc && \
    git clone --depth 1 https://github.com/novnc/websockify /usr/share/novnc/utils/websockify && \
    ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# ===================================================================
# X11和XFCE配置 (增强防休眠配置)
# ===================================================================
RUN mkdir -p /tmp/.X11-unix /tmp/.ICE-unix && \
    chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix && \
    echo "allowed_users=anybody" > /etc/X11/Xwrapper.config

RUN mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml && \
    chown -R headless:headless /home/headless/.config

# 配置电源管理器：强制演示模式，禁止任何睡眠/休眠动作
RUN cat << 'EOF' > /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-power-manager" version="1.0">
  <property name="xfce4-power-manager" type="empty">
    <property name="blank-on-ac" type="int" value="0"/>
    <property name="blank-on-battery" type="int" value="0"/>
    <property name="dpms-enabled" type="bool" value="false"/>
    <property name="dpms-on-ac-sleep" type="uint" value="0"/>
    <property name="dpms-on-ac-off" type="uint" value="0"/>
    <property name="inactivity-on-ac" type="uint" value="14"/>
    <property name="lock-screen-suspend-hibernate" type="bool" value="false"/>
    <property name="presentation-mode" type="bool" value="true"/>
  </property>
</channel>
EOF

# ===================================================================
# 设置Python虚拟环境和安装依赖
# ===================================================================
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY web-app/requirements.txt /app/web-app/
RUN mkdir -p /opt/playwright && \
    pip install --no-cache-dir wheel setuptools && \
    pip install --no-cache-dir -r /app/web-app/requirements.txt && \
    playwright install chromium firefox && \
    chmod -R 777 /opt/playwright

# ===================================================================
# 复制应用代码和配置
# ===================================================================
COPY web-app/ /app/web-app/
COPY nginx.conf /etc/nginx/nginx.conf
COPY scripts/ /app/scripts/

# ===================================================================
# Supervisor配置
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

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autostart=true
autorestart=true
stdout_logfile=/app/logs/nginx.log
stderr_logfile=/app/logs/nginx-error.log
priority=30

[program:webapp]
command=/bin/bash -c "while [ ! -f /home/headless/.dbus-env ]; do sleep 1; done; source /home/headless/.dbus-env; exec /opt/venv/bin/gunicorn --workers 1 --threads 8 --timeout 300 --bind 0.0.0.0:8000 app:app"
directory=/app/web-app
autostart=true
autorestart=true
stdout_logfile=/app/logs/webapp.log
stderr_logfile=/app/logs/webapp-error.log
user=headless
environment=HOME="/home/headless",USER="headless",PATH="/opt/venv/bin:%(ENV_PATH)s",DISPLAY=":1",PLAYWRIGHT_BROWSERS_PATH="/opt/playwright"
priority=40

[program:autokey]
command=/usr/bin/autokey-gtk --verbose
environment=DISPLAY=":1"
user=headless
autostart=true
autorestart=true
stdout_logfile=/app/logs/autokey.log
stderr_logfile=/app/logs/autokey-error.log
priority=25
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
# 设置权限及端口暴露
# ===================================================================
RUN chown -R headless:headless /app /home/headless /opt/venv \
    && chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true \
    && chmod +x /app/scripts/*.sh 2>/dev/null || true

EXPOSE 5000

WORKDIR /app

CMD ["/app/scripts/entrypoint.sh"]
