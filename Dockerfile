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
    XDG_SESSION_DESKTOP=xfce

# ===================================================================
# 安装系统依赖
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
    libxml2-dev libxslt1-dev zlib1g-dev libjpeg-dev libpng-dev \
    gsettings-desktop-schemas dconf-cli gnome-icon-theme policykit-1 \
    xautomation kdialog imagemagick nginx nodejs npm unzip libnss3 libatk-bridge2.0-0 \
    libx11-xcb1 libxcomposite1 libxrandr2 libasound2 libpangocairo-1.0-0 libpango-1.0-0 \
    libcups2 libdbus-1-3 libxdamage1 libxfixes3 libgbm1 libxshmfence1 libxext6 libdrm2 \
    libwayland-client0 libwayland-cursor0 libatspi2.0-0 libepoxy0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ===================================================================
# 安装 Google Chrome
# ===================================================================
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb && \
    apt-get install -y /tmp/chrome.deb && \
    rm /tmp/chrome.deb

# ===================================================================
# 设置时区和语言
# ===================================================================
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8

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
# 下载并解压Selenium IDE扩展
# ===================================================================
RUN wget --tries=3 -O /tmp/selenium-ide.crx "https://raw.githubusercontent.com/workerspages/ubuntu-automation/aio/addons/selenium-ide.crx" && \
    mkdir -p /opt/selenium-ide-unpacked && \
    python3 -c "import zipfile; zf = zipfile.ZipFile('/tmp/selenium-ide.crx'); zf.extractall('/opt/selenium-ide-unpacked'); zf.close()" && \
    rm /tmp/selenium-ide.crx

# ===================================================================
# VNC xstartup脚本
# ===================================================================
RUN mkdir -p /home/headless/.vnc && \
    chown headless:headless /home/headless/.vnc

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

RUN mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml && \
    chown -R headless:headless /home/headless/.config

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
# 复制应用代码和配置 (这里会包含你手动保存的 scripts/entrypoint.sh)
# ===================================================================
COPY web-app/ /app/web-app/
COPY scripts/ /app/scripts/
COPY nginx.conf /etc/nginx/nginx.conf

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

[rpcinterface:superv
