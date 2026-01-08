# ===================================================================
# 基础镜像
# ===================================================================
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
USER root

# 环境变量
ENV TZ=Asia/Shanghai \
    HOME=/home/headless \
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
    XDG_CONFIG_DIRS=/etc/xdg \
    XDG_DATA_DIRS=/usr/local/share:/usr/share \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# ===================================================================
# 系统安装
# ===================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget curl ca-certificates \
    sudo tzdata locales net-tools openssh-client \
    iproute2 iputils-ping supervisor cron sqlite3 \
    fonts-wqy-microhei language-pack-zh-hans \
    x11-utils x11-xserver-utils xauth xserver-xorg-core xserver-xorg-video-dummy \
    tigervnc-standalone-server tigervnc-common tigervnc-tools \
    libasound2 \
    openbox tint2 pcmanfm lxterminal dbus-x11 libgtk-3-0 \
    autocutsel \
    python3 python3-pip python3-dev python3-gi python3-xdg python3-websockify \
    gir1.2-gtk-3.0 pkg-config gcc g++ make libffi-dev libssl-dev \
    xautomation xdotool kdialog imagemagick nginx nodejs npm unzip p7zip-full \
    autokey-gtk \
    libnss3 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxrandr2 \
    libpangocairo-1.0-0 libpango-1.0-0 libcups2 libdbus-1-3 libxdamage1 libxfixes3 \
    libgbm1 libdrm2 libwayland-client0 libatspi2.0-0 && \
    \
    # ============================================
    # 安装 Google Chrome (PaaS 修正版)
    # ============================================
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb && \
    apt-get install -y /tmp/chrome.deb && \
    rm /tmp/chrome.deb && \
    # 重命名原始二进制
    mv /usr/bin/google-chrome-stable /usr/bin/google-chrome-stable.original && \
    # 创建启动包装脚本
    echo '#!/bin/bash' > /usr/bin/google-chrome-stable && \
    echo 'exec /usr/bin/google-chrome-stable.original --no-sandbox --disable-dev-shm-usage --disable-gpu --no-default-browser-check --no-first-run "$@"' >> /usr/bin/google-chrome-stable && \
    chmod +x /usr/bin/google-chrome-stable && \
    mkdir -p /etc/opt/chrome/policies/managed && \
    echo '{ "CommandLineFlagSecurityWarningsEnabled": false, "DefaultBrowserSettingEnabled": false }' > /etc/opt/chrome/policies/managed/managed_policies.json && \
    \
    # Cloudflare Tunnel
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && \
    dpkg -i cloudflared-linux-amd64.deb || apt-get install -f -y && \
    rm -f cloudflared-linux-amd64.deb && \
    \
    # 系统配置
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8 && \
    groupadd -g 1001 headless && \
    useradd -u 1001 -g 1001 -m -s /bin/bash headless && \
    echo "headless ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    \
    # 瘦身清理
    apt-get remove -y --purge gcc g++ make python3-dev && \
    apt-get autoremove -y && \
    rm -rf /usr/share/doc /usr/share/man /usr/share/info /usr/share/icons/Adwaita /usr/share/icons/HighContrast && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ===================================================================
# Openbox 配置
# ===================================================================
RUN mkdir -p /app/web-app /app/scripts /app/data /app/logs /home/headless/Downloads \
             /home/headless/.config/autokey/data/MyScripts \
             /home/headless/.config/autokey/data/My\ Phrases \
             /home/headless/.config/openbox \
             /home/headless/.config/tint2 \
             /home/headless/.vnc && \
    chown -R headless:headless /app /home/headless

RUN echo 'autocutsel -fork -selection PRIMARY & \n\
autocutsel -fork -selection CLIPBOARD & \n\
tint2 & \n\
pcmanfm --desktop --profile LXDE & \n\
/usr/bin/autokey-gtk --verbose &' > /home/headless/.config/openbox/autostart && \
    chown headless:headless /home/headless/.config/openbox/autostart

RUN cat << 'EOF' > /home/headless/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS
echo "export DBUS_SESSION_BUS_ADDRESS='$DBUS_SESSION_BUS_ADDRESS'" > $HOME/.dbus-env
chmod 644 $HOME/.dbus-env
xsetroot -solid "#333333" &
xset s off &
xset -dpms &
xset s noblank &
export GTK_IM_MODULE=xim
export XMODIFIERS=@im=none
export LANG=zh_CN.UTF-8
exec /usr/bin/openbox-session
EOF
RUN chmod +x /home/headless/.vnc/xstartup && chown headless:headless /home/headless/.vnc/xstartup

# ===================================================================
# noVNC (wget)
# ===================================================================
WORKDIR /tmp
RUN mkdir -p /usr/share/novnc && \
    wget -qO- https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.tar.gz | tar xz --strip-components=1 -C /usr/share/novnc && \
    mkdir -p /usr/share/novnc/utils/websockify && \
    wget -qO- https://github.com/novnc/websockify/archive/refs/tags/v0.11.0.tar.gz | tar xz --strip-components=1 -C /usr/share/novnc/utils/websockify && \
    ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# ===================================================================
# Python 环境
# ===================================================================
COPY web-app/requirements.txt /app/web-app/
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -r /app/web-app/requirements.txt && \
    rm -rf /root/.cache/pip

# ===================================================================
# 复制与配置
# ===================================================================
COPY web-app/ /app/web-app/
COPY nginx.conf /etc/nginx/nginx.conf
COPY scripts/ /app/scripts/
COPY services.conf /etc/supervisor/conf.d/services.conf
COPY browser-configs/chrome.zip /tmp/chrome.zip

RUN mkdir -p /home/headless/.config/google-chrome && \
    unzip -q /tmp/chrome.zip -d /home/headless/.config/google-chrome/ && \
    rm /tmp/chrome.zip && \
    rm -f /home/headless/.config/google-chrome/SingletonLock && \
    chown -R headless:headless /home/headless/.config

RUN echo '#!/bin/bash' > /usr/local/bin/init-database && \
    echo 'cd /app/web-app && python3 init_db.py' >> /usr/local/bin/init-database && \
    chmod +x /usr/local/bin/init-database

RUN chown -R headless:headless /app /home/headless \
    && chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true \
    && chmod +x /app/scripts/*.sh 2>/dev/null || true \
    && mkdir -p /tmp/.X11-unix /tmp/.ICE-unix \
    && chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix

EXPOSE 5000
WORKDIR /app
CMD ["/app/scripts/entrypoint.sh"]
