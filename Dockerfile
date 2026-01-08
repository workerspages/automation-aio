# ===================================================================
# 基础镜像与环境
# ===================================================================
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
USER root

# 环境变量 (保留修复 AutoKey 所需的 HOME 变量)
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
    XDG_CONFIG_DIRS=/etc/xdg/xfce4:/etc/xdg \
    XDG_DATA_DIRS=/usr/local/share:/usr/share/xfce4:/usr/share \
    XDG_CURRENT_DESKTOP=XFCE \
    XDG_SESSION_DESKTOP=xfce \
    # 即使不下载 Playwright 浏览器，也保留路径防止报错
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# ===================================================================
# 系统安装 (合并层：移除 Firefox, Actiona, 移除冗余组件)
# ===================================================================
RUN apt-get update && \
    # 1. 安装核心工具
    apt-get install -y --no-install-recommends \
    git vim nano sudo tzdata locales net-tools openssh-client \
    iproute2 iputils-ping supervisor cron sqlite3 \
    # 字体 (中文字体)
    fonts-wqy-microhei fonts-noto-cjk language-pack-zh-hans \
    # X11 / VNC / Audio
    x11-utils x11-xserver-utils xauth xserver-xorg-core xserver-xorg-video-dummy \
    tigervnc-standalone-server tigervnc-common tigervnc-tools \
    libasound2 \
    # 桌面环境 (仅安装核心组件，不装 xfce4-goodies)
    xfce4 xfce4-terminal dbus-x11 libgtk-3-0 \
    # Python & 编译依赖
    python3 python3-pip python3-venv python3-dev python3-gi python3-xdg python3-websockify \
    gir1.2-gtk-3.0 pkg-config gcc g++ make libffi-dev libssl-dev \
    # 杂项工具 (移除 actiona, 保留 xautomation 用于辅助)
    xautomation xdotool kdialog imagemagick nginx nodejs npm unzip p7zip-full \
    # 2. 安装 AutoKey (GTK) - 唯一保留的桌面自动化工具
    autokey-gtk \
    # 3. 依赖库 (Chrome 运行所需)
    libnss3 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxrandr2 \
    libpangocairo-1.0-0 libpango-1.0-0 libcups2 libdbus-1-3 libxdamage1 libxfixes3 \
    libgbm1 libdrm2 libwayland-client0 libatspi2.0-0 && \
    \
    # 4. 清理卸载
    apt-get purge -y xfce4-screensaver gnome-screensaver xscreensaver && \
    rm -rf /usr/share/doc /usr/share/man /usr/share/info && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ===================================================================
# 安装 Google Chrome (唯一保留的浏览器)
# ===================================================================
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb && \
    apt-get update && \
    apt-get install -y /tmp/chrome.deb && \
    rm /tmp/chrome.deb && \
    rm -rf /var/lib/apt/lists/* && \
    # 配置 Chrome 启动脚本 (No-Sandbox)
    mv /usr/bin/google-chrome-stable /usr/bin/google-chrome-stable.original && \
    echo '#!/bin/bash' > /usr/bin/google-chrome-stable && \
    echo 'exec /usr/bin/google-chrome-stable.original --no-sandbox --disable-gpu --no-default-browser-check --no-first-run "$@"' >> /usr/bin/google-chrome-stable && \
    chmod +x /usr/bin/google-chrome-stable && \
    # 配置策略 (禁止弹窗)
    mkdir -p /etc/opt/chrome/policies/managed && \
    echo '{ "CommandLineFlagSecurityWarningsEnabled": false, "DefaultBrowserSettingEnabled": false }' > /etc/opt/chrome/policies/managed/managed_policies.json

# 设置默认浏览器
RUN update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 && \
    update-alternatives --set x-www-browser /usr/bin/google-chrome-stable

# 配置 XDG 默认打开方式
RUN mkdir -p /etc/xdg && \
    { \
        echo '[Default Applications]'; \
        echo 'text/html=google-chrome.desktop'; \
        echo 'x-scheme-handler/http=google-chrome.desktop'; \
        echo 'x-scheme-handler/https=google-chrome.desktop'; \
    } >> /etc/xdg/mimeapps.list

# ===================================================================
# 安装 Cloudflare Tunnel
# ===================================================================
RUN wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && \
    dpkg -i cloudflared-linux-amd64.deb || apt-get install -f -y && \
    rm -f cloudflared-linux-amd64.deb

# ===================================================================
# 系统配置 & 用户目录 (包含 AutoKey 权限修复)
# ===================================================================
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8 && \
    groupadd -g 1001 headless && \
    useradd -u 1001 -g 1001 -m -s /bin/bash headless && \
    echo "headless ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    # 预创建目录结构
    mkdir -p /app/web-app /app/scripts /app/data /app/logs /home/headless/Downloads \
             /home/headless/.config/autokey/data/MyScripts \
             /home/headless/.config/autokey/data/My\ Phrases \
             /home/headless/.local/share \
             /home/headless/.config/autostart && \
    chown -R headless:headless /app /home/headless

# ===================================================================
# 注入浏览器配置 (仅 Chrome)
# ===================================================================
COPY browser-configs/chrome.zip /tmp/chrome.zip
RUN mkdir -p /home/headless/.config/google-chrome && \
    unzip -q /tmp/chrome.zip -d /home/headless/.config/google-chrome/ && \
    rm /tmp/chrome.zip && \
    rm -f /home/headless/.config/google-chrome/SingletonLock && \
    chown -R headless:headless /home/headless/.config

# ===================================================================
# VNC 配置
# ===================================================================
RUN mkdir -p /home/headless/.vnc && chown headless:headless /home/headless/.vnc
RUN cat << 'EOF' > /home/headless/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS
echo "export DBUS_SESSION_BUS_ADDRESS='$DBUS_SESSION_BUS_ADDRESS'" > $HOME/.dbus-env
chmod 644 $HOME/.dbus-env
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

# AutoKey 桌面启动项 (保留文件，但 Services.conf 会管理它)
RUN printf "[Desktop Entry]\nType=Application\nName=AutoKey\nExec=autokey-gtk\nTerminal=false\n" > /home/headless/.config/autostart/autokey.desktop && \
    chown -R headless:headless /home/headless/.config

# ===================================================================
# noVNC
# ===================================================================
WORKDIR /tmp
RUN git clone --depth 1 https://github.com/novnc/noVNC.git /usr/share/novnc && \
    git clone --depth 1 https://github.com/novnc/websockify /usr/share/novnc/utils/websockify && \
    ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html && \
    rm -rf /usr/share/novnc/.git

# ===================================================================
# XFCE 电源管理
# ===================================================================
RUN mkdir -p /tmp/.X11-unix /tmp/.ICE-unix && \
    chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix && \
    echo "allowed_users=anybody" > /etc/X11/Xwrapper.config && \
    mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml && \
    chown -R headless:headless /home/headless/.config

RUN cat << 'EOF' > /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-power-manager" version="1.0">
  <property name="xfce4-power-manager" type="empty">
    <property name="blank-on-ac" type="int" value="0"/>
    <property name="dpms-enabled" type="bool" value="false"/>
    <property name="presentation-mode" type="bool" value="true"/>
  </property>
</channel>
EOF

# ===================================================================
# Python 环境 (极致瘦身)
# ===================================================================
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY web-app/requirements.txt /app/web-app/

RUN mkdir -p /opt/playwright && \
    pip install --no-cache-dir --upgrade pip wheel setuptools && \
    # 安装依赖
    pip install --no-cache-dir -r /app/web-app/requirements.txt && \
    # === 关键修改：不运行 playwright install ===
    # 我们只使用 Selenium (配合 Chrome) 或者 Playwright (连接现有 Chrome)
    # 这步节省 500MB+
    # ========================================
    # 卸载编译工具，再省 300MB
    apt-get remove -y --purge gcc g++ make python3-dev && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /root/.cache/pip

# ===================================================================
# 复制代码与配置
# ===================================================================
COPY web-app/ /app/web-app/
COPY nginx.conf /etc/nginx/nginx.conf
COPY scripts/ /app/scripts/
COPY services.conf /etc/supervisor/conf.d/services.conf

# 数据库初始化
RUN echo '#!/bin/bash' > /usr/local/bin/init-database && \
    echo 'cd /app/web-app && /opt/venv/bin/python3 init_db.py' >> /usr/local/bin/init-database && \
    chmod +x /usr/local/bin/init-database

# 最终权限修正
RUN chown -R headless:headless /app /home/headless /opt/venv \
    && chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true \
    && chmod +x /app/scripts/*.sh 2>/dev/null || true

EXPOSE 5000
WORKDIR /app
CMD ["/app/scripts/entrypoint.sh"]
