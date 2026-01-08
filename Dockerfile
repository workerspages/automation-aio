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
# 系统安装 (Openbox 方案)
# ===================================================================
RUN apt-get update && \
    # 1. 安装核心工具 (含 wget, curl 用于下载)
    apt-get install -y --no-install-recommends \
    wget curl ca-certificates \
    sudo tzdata locales net-tools openssh-client \
    iproute2 iputils-ping supervisor cron sqlite3 \
    # 2. 字体 (仅保留微米黑，节省空间)
    fonts-wqy-microhei language-pack-zh-hans \
    # 3. X11 / VNC / Audio
    x11-utils x11-xserver-utils xauth xserver-xorg-core xserver-xorg-video-dummy \
    tigervnc-standalone-server tigervnc-common tigervnc-tools \
    libasound2 \
    # 4. === 关键修改：Openbox + Tint2 替代 XFCE ===
    openbox tint2 pcmanfm lxterminal dbus-x11 libgtk-3-0 \
    # 5. 剪贴板同步工具
    autocutsel \
    # 6. Python & 编译依赖
    python3 python3-pip python3-dev python3-gi python3-xdg python3-websockify \
    gir1.2-gtk-3.0 pkg-config gcc g++ make libffi-dev libssl-dev \
    # 7. 杂项工具 (移除无用工具)
    xautomation xdotool kdialog imagemagick nginx nodejs npm unzip p7zip-full \
    # 8. AutoKey
    autokey-gtk \
    # 9. Chrome 依赖库
    libnss3 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxrandr2 \
    libpangocairo-1.0-0 libpango-1.0-0 libcups2 libdbus-1-3 libxdamage1 libxfixes3 \
    libgbm1 libdrm2 libwayland-client0 libatspi2.0-0 && \
    \
    # ============================================
    # 安装 Google Chrome
    # ============================================
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb && \
    apt-get install -y /tmp/chrome.deb && \
    rm /tmp/chrome.deb && \
    # Chrome 优化
    mv /usr/bin/google-chrome-stable /usr/bin/google-chrome-stable.original && \
    echo '#!/bin/bash' > /usr/bin/google-chrome-stable && \
    echo 'exec /usr/bin/google-chrome-stable.original --no-sandbox --disable-gpu --no-default-browser-check --no-first-run "$@"' >> /usr/bin/google-chrome-stable && \
    chmod +x /usr/bin/google-chrome-stable && \
    # Chrome 策略
    mkdir -p /etc/opt/chrome/policies/managed && \
    echo '{ "CommandLineFlagSecurityWarningsEnabled": false, "DefaultBrowserSettingEnabled": false }' > /etc/opt/chrome/policies/managed/managed_policies.json && \
    \
    # ============================================
    # 安装 Cloudflare Tunnel
    # ============================================
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && \
    dpkg -i cloudflared-linux-amd64.deb || apt-get install -f -y && \
    rm -f cloudflared-linux-amd64.deb && \
    \
    # ============================================
    # 系统配置
    # ============================================
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8 && \
    groupadd -g 1001 headless && \
    useradd -u 1001 -g 1001 -m -s /bin/bash headless && \
    echo "headless ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    \
    # ============================================
    # 💥 暴力瘦身清理 (关键步骤)
    # ============================================
    # 卸载编译工具 (gcc, g++, make, python-dev) - 节省 ~300MB
    apt-get remove -y --purge gcc g++ make python3-dev && \
    apt-get autoremove -y && \
    # 删除文档、手册、图标缓存 - 节省 ~100MB
    rm -rf /usr/share/doc /usr/share/man /usr/share/info /usr/share/icons/Adwaita /usr/share/icons/HighContrast && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ===================================================================
# 配置 Openbox (替代 XFCE)
# ===================================================================
# 预创建所有必要目录
RUN mkdir -p /app/web-app /app/scripts /app/data /app/logs /home/headless/Downloads \
             /home/headless/.config/autokey/data/MyScripts \
             /home/headless/.config/autokey/data/My\ Phrases \
             /home/headless/.config/openbox \
             /home/headless/.config/tint2 \
             /home/headless/.vnc && \
    chown -R headless:headless /app /home/headless

# 写入 Openbox 自动启动脚本
# 这里配置了：剪贴板同步、任务栏、文件管理器、AutoKey
RUN echo 'autocutsel -fork -selection PRIMARY & \n\
autocutsel -fork -selection CLIPBOARD & \n\
tint2 & \n\
pcmanfm --desktop --profile LXDE & \n\
/usr/bin/autokey-gtk --verbose &' > /home/headless/.config/openbox/autostart && \
    chown headless:headless /home/headless/.config/openbox/autostart

# VNC 启动脚本 (适配 Openbox)
RUN cat << 'EOF' > /home/headless/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS
echo "export DBUS_SESSION_BUS_ADDRESS='$DBUS_SESSION_BUS_ADDRESS'" > $HOME/.dbus-env
chmod 644 $HOME/.dbus-env
# 设置纯色背景 (深灰色)
xsetroot -solid "#333333" &
xset s off &
xset -dpms &
xset s noblank &
export GTK_IM_MODULE=xim
export XMODIFIERS=@im=none
export LANG=zh_CN.UTF-8
# 启动 Openbox
exec /usr/bin/openbox-session
EOF
RUN chmod +x /home/headless/.vnc/xstartup && chown headless:headless /home/headless/.vnc/xstartup

# ===================================================================
# 安装 noVNC (使用 wget 避免 git 依赖)
# ===================================================================
WORKDIR /tmp
RUN mkdir -p /usr/share/novnc && \
    wget -qO- https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.tar.gz | tar xz --strip-components=1 -C /usr/share/novnc && \
    mkdir -p /usr/share/novnc/utils/websockify && \
    wget -qO- https://github.com/novnc/websockify/archive/refs/tags/v0.11.0.tar.gz | tar xz --strip-components=1 -C /usr/share/novnc/utils/websockify && \
    ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# ===================================================================
# Python 环境 (无 venv，直接安装到系统)
# ===================================================================
COPY web-app/requirements.txt /app/web-app/
# 直接安装到系统路径，不创建 venv，节省体积
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -r /app/web-app/requirements.txt && \
    rm -rf /root/.cache/pip

# ===================================================================
# 最终文件复制
# ===================================================================
COPY web-app/ /app/web-app/
COPY nginx.conf /etc/nginx/nginx.conf
COPY scripts/ /app/scripts/
COPY services.conf /etc/supervisor/conf.d/services.conf
COPY browser-configs/chrome.zip /tmp/chrome.zip

# 解压浏览器配置
RUN mkdir -p /home/headless/.config/google-chrome && \
    unzip -q /tmp/chrome.zip -d /home/headless/.config/google-chrome/ && \
    rm /tmp/chrome.zip && \
    rm -f /home/headless/.config/google-chrome/SingletonLock && \
    chown -R headless:headless /home/headless/.config

# DB 初始化
RUN echo '#!/bin/bash' > /usr/local/bin/init-database && \
    echo 'cd /app/web-app && python3 init_db.py' >> /usr/local/bin/init-database && \
    chmod +x /usr/local/bin/init-database

# 权限修正
RUN chown -R headless:headless /app /home/headless \
    && chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true \
    && chmod +x /app/scripts/*.sh 2>/dev/null || true \
    && mkdir -p /tmp/.X11-unix /tmp/.ICE-unix \
    && chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix

EXPOSE 5000
WORKDIR /app
CMD ["/app/scripts/entrypoint.sh"]
