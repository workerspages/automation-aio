# ===================================================================
# 从 Ubuntu 基础镜像开始构建,完全控制 VNC 和 XFCE 环境
# ===================================================================
FROM ubuntu:22.04

# 设置为非交互模式
ENV DEBIAN_FRONTEND=noninteractive

# 切换到 root 用户
USER root

# ===================================================================
# 环境变量配置
# ===================================================================
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
    FIREFOX_BINARY=/usr/bin/firefox \
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
    VNC_PW=vncpassword \
    XDG_CONFIG_DIRS=/etc/xdg/xfce4:/etc/xdg \
    XDG_DATA_DIRS=/usr/local/share:/usr/share/xfce4:/usr/share \
    XDG_CURRENT_DESKTOP=XFCE \
    XDG_SESSION_DESKTOP=xfce

# ===================================================================
# 步骤 1: 安装基础系统工具和依赖(包括Firefox)
# ===================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基础工具
    ca-certificates \
    curl \
    wget \
    git \
    vim \
    nano \
    sudo \
    tzdata \
    locales \
    software-properties-common \
    gnupg2 \
    apt-transport-https \
    # 网络工具
    net-tools \
    iproute2 \
    iputils-ping \
    # 进程管理
    supervisor \
    cron \
    # 数据库
    sqlite3 \
    # 中文字体
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    language-pack-zh-hans \
    # X11 基础
    x11-utils \
    x11-xserver-utils \
    x11-apps \
    xauth \
    xserver-xorg-core \
    xserver-xorg-video-dummy \
    # VNC 服务器 (TigerVNC) - 完整安装
    tigervnc-standalone-server \
    tigervnc-common \
    tigervnc-xorg-extension \
    # XFCE 桌面环境
    xfce4 \
    xfce4-goodies \
    xfce4-terminal \
    # D-Bus
    dbus-x11 \
    # GTK 库
    libgtk-3-0 \
    libgtk2.0-0 \
    # Python 依赖
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-gi \
    python3-xdg \
    python3-websockify \
    gir1.2-gtk-3.0 \
    # 编译工具
    build-essential \
    pkg-config \
    gcc \
    g++ \
    make \
    # 库文件
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    # Firefox 及其依赖库
    firefox \
    # 其他图形工具
    gsettings-desktop-schemas \
    dconf-cli \
    gnome-icon-theme \
    policykit-1 \
    xautomation \
    kdialog \
    imagemagick \
    # Nginx
    nginx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ===================================================================
# 步骤 2: 配置时区和语言
# ===================================================================
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && locale-gen zh_CN.UTF-8 \
    && update-locale LANG=zh_CN.UTF-8

# ===================================================================
# 步骤 3: 验证并配置 Firefox
# ===================================================================
RUN if [ -f /usr/bin/firefox ]; then \
    echo "✅ Firefox 已从 apt 安装"; \
    elif [ -f /snap/bin/firefox ]; then \
    echo "Firefox 是 snap 包,创建符号链接"; \
    ln -sf /snap/bin/firefox /usr/bin/firefox; \
    else \
    echo "⚠️ Firefox 未找到,安装 Chromium 作为备选"; \
    apt-get update && apt-get install -y chromium-browser && apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

# ===================================================================
# 步骤 4: 安装 GeckoDriver (Selenium WebDriver for Firefox)
# ===================================================================
RUN GECKODRIVER_VERSION=$(curl -sS https://api.github.com/repos/mozilla/geckodriver/releases/latest | grep tag_name | cut -d '"' -f 4 | sed 's/v//') \
    && echo "安装 GeckoDriver ${GECKODRIVER_VERSION}" \
    && wget -q https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz \
    && tar -xzf geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz -C /usr/bin/ \
    && chmod +x /usr/bin/geckodriver \
    && rm geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz

# ===================================================================
# 步骤 5: 创建用户和目录
# ===================================================================
RUN groupadd -g 1001 headless \
    && useradd -u 1001 -g 1001 -m -s /bin/bash headless \
    && echo "headless ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# 创建应用目录
RUN mkdir -p /app/web-app /app/scripts /app/data /app/logs /home/headless/Downloads \
    && chown -R headless:headless /app /home/headless

# ===================================================================
# 步骤 6: 创建 VNC 配置目录和脚本
# ===================================================================
RUN mkdir -p /home/headless/.vnc \
    && chown -R headless:headless /home/headless/.vnc

# 创建 VNC xstartup 脚本
RUN cat << 'EOF' > /home/headless/.vnc/xstartup
#!/bin/sh
# VNC xstartup script for XFCE4

unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS

# 启动 D-Bus
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax)
    export DBUS_SESSION_BUS_ADDRESS
fi

# 加载 X 资源
[ -r /etc/X11/Xresources ] && xrdb /etc/X11/Xresources
[ -r "$HOME/.Xresources" ] && xrdb -merge "$HOME/.Xresources"

# X 服务器设置
xsetroot -solid grey &
xset s off &
xset -dpms &
xset s noblank &

# 环境变量
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

# 启动 XFCE4
exec /usr/bin/startxfce4
EOF

RUN chmod +x /home/headless/.vnc/xstartup \
    && chown headless:headless /home/headless/.vnc/xstartup

# ===================================================================
# 步骤 7: 创建 VNC 密码生成脚本 (使用 Python)
# ===================================================================
RUN cat << 'EOF' > /usr/local/bin/create-vnc-passwd
#!/usr/bin/env python3
import sys
import os
from d3des import deskey

def create_vnc_passwd(password, filename):
    """创建 VNC 密码文件"""
    # VNC 密码最多8个字符
    password = password[:8].ljust(8, '\0')
    
    # VNC 使用 DES 加密,密钥是固定的
    key = b'\xe8\x4a\xd6\x60\xc4\x72\x1a\xe0'
    
    # 加密密码
    encrypted = bytearray(8)
    for i in range(8):
        encrypted[i] = password[i] ^ key[i]
    
    # 写入文件
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'wb') as f:
        f.write(bytes(encrypted))
    
    os.chmod(filename, 0o600)
    print(f"VNC 密码文件已创建: {filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        password = os.environ.get('VNC_PW', 'vncpassword')
    else:
        password = sys.argv[1]
    
    filename = os.path.expanduser('~/.vnc/passwd')
    if len(sys.argv) >= 3:
        filename = sys.argv[2]
    
    create_vnc_passwd(password, filename)
EOF

# 简化版本:直接使用 Perl 创建密码(更可靠)
RUN cat << 'EOF' > /usr/local/bin/create-vnc-passwd
#!/bin/bash
set -e

PASSWORD="${1:-${VNC_PW:-vncpassword}}"
PASSWD_FILE="${2:-$HOME/.vnc/passwd}"

# 创建目录
mkdir -p "$(dirname "$PASSWD_FILE")"

# 使用 Perl 创建 VNC 密码文件 (VNC 使用简单的 DES 加密)
perl << 'PERLSCRIPT'
use strict;
my $password = $ENV{'VNC_PW'} || 'vncpassword';
$password = substr($password, 0, 8);  # VNC 密码最多8个字符
$password .= "\0" x (8 - length($password));  # 填充到8字节

# VNC 固定密钥
my $key = pack("C8", 0xe8, 0x4a, 0xd6, 0x60, 0xc4, 0x72, 0x1a, 0xe0);

# 简单 XOR 加密
my $encrypted = '';
for (my $i = 0; $i < 8; $i++) {
    $encrypted .= chr(ord(substr($password, $i, 1)) ^ ord(substr($key, $i, 1)));
}

# 写入文件
my $file = $ENV{'HOME'} . '/.vnc/passwd';
open(my $fh, '>', $file) or die "Cannot write to $file: $!";
binmode($fh);
print $fh $encrypted;
close($fh);
chmod 0600, $file;
print "VNC password file created: $file\n";
PERLSCRIPT

echo "✅ VNC 密码文件已创建: $PASSWD_FILE"
EOF

RUN chmod +x /usr/local/bin/create-vnc-passwd

# ===================================================================
# 步骤 8: 安装 noVNC
# ===================================================================
WORKDIR /tmp
RUN git clone https://github.com/novnc/noVNC.git /usr/share/novnc \
    && git clone https://github.com/novnc/websockify /usr/share/novnc/utils/websockify \
    && ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# ===================================================================
# 步骤 9: 安装 AutoKey
# ===================================================================
RUN wget https://github.com/autokey/autokey/releases/download/v0.96.0/autokey-common_0.96.0_all.deb \
    && wget https://github.com/autokey/autokey/releases/download/v0.96.0/autokey-gtk_0.96.0_all.deb \
    && wget https://github.com/autokey/autokey/releases/download/v0.96.0/autokey-qt_0.96.0_all.deb \
    && dpkg -i autokey-common_0.96.0_all.deb autokey-gtk_0.96.0_all.deb autokey-qt_0.96.0_all.deb || apt-get install -f -y \
    && rm -f *.deb

# ===================================================================
# 步骤 10: 安装 Cloudflare Tunnel (可选)
# ===================================================================
RUN wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
    && dpkg -i cloudflared-linux-amd64.deb || apt-get install -f -y \
    && rm -f cloudflared-linux-amd64.deb

# 清理临时文件
RUN rm -rf /tmp/* /var/tmp/*

# ===================================================================
# 步骤 11: 配置 X11
# ===================================================================
RUN mkdir -p /tmp/.X11-unix /tmp/.ICE-unix \
    && chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix \
    && echo "allowed_users=anybody" > /etc/X11/Xwrapper.config

# ===================================================================
# 步骤 12: 配置 XFCE (禁用屏幕保护和电源管理)
# ===================================================================
RUN mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml

# XFCE 电源管理
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

# XFCE 屏幕保护
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
# 步骤 13: 安装 Python 依赖
# ===================================================================
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY web-app/requirements.txt /app/web-app/
RUN pip install --no-cache-dir wheel setuptools \
    && pip install --no-cache-dir -r /app/web-app/requirements.txt

# ===================================================================
# 步骤 14: 复制应用代码和配置
# ===================================================================
COPY firefox-xpi /app/firefox-xpi/
COPY web-app/ /app/web-app/
COPY scripts/ /app/scripts/
COPY nginx.conf /etc/nginx/nginx.conf

# ===================================================================
# 步骤 15: 配置 Firefox Selenium IDE 插件
# ===================================================================
RUN if [ -f /app/firefox-xpi/selenium-ide.xpi ]; then \
    mkdir -p /usr/lib/firefox/distribution /snap/firefox/current/distribution 2>/dev/null || true; \
    cp /app/firefox-xpi/selenium-ide.xpi /usr/lib/firefox/distribution/ 2>/dev/null || true; \
    cp /app/firefox-xpi/selenium-ide.xpi /snap/firefox/current/distribution/ 2>/dev/null || true; \
    fi

# ===================================================================
# 步骤 16: 创建 Supervisor 配置
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
command=/opt/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:8000 app:app
directory=/app/web-app
autostart=true
autorestart=true
stdout_logfile=/app/logs/webapp.log
stderr_logfile=/app/logs/webapp-error.log
environment=HOME="/home/headless",USER="headless",PATH="/opt/venv/bin:%(ENV_PATH)s"
priority=40
EOF

# ===================================================================
# 步骤 17: 创建 Entrypoint 脚本
# ===================================================================
RUN cat << 'EOF' > /app/scripts/entrypoint.sh
#!/bin/bash
set -e

echo "==================================="
echo "Ubuntu 自动化平台启动中..."
echo "==================================="

# 验证浏览器安装
if command -v firefox &> /dev/null; then
    echo "✅ Firefox 已安装"
    firefox --version 2>/dev/null || echo "Firefox version: snap package"
elif command -v chromium-browser &> /dev/null; then
    echo "✅ Chromium 已安装"
    chromium-browser --version
    export FIREFOX_BINARY=/usr/bin/chromium-browser
else
    echo "❌ 警告: 未找到浏览器"
fi

# 使用自定义脚本创建 VNC 密码文件
echo "创建 VNC 密码文件..."
su - headless -c "/usr/local/bin/create-vnc-passwd"

# 确保目录存在
mkdir -p /app/data /app/logs /home/headless/Downloads

# 设置权限
chown -R headless:headless /app /home/headless /opt/venv

# 初始化数据库
if [ ! -f /app/data/tasks.db ]; then
    echo "初始化数据库..."
    cd /app/web-app
    /opt/venv/bin/python3 -c "from app import db; db.create_all()" || true
fi

# 启动 Supervisor
echo "启动 Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/services.conf
EOF

RUN chmod +x /app/scripts/entrypoint.sh

# ===================================================================
# 步骤 18: 设置最终权限
# ===================================================================
RUN chown -R headless:headless /app /home/headless /opt/venv \
    && chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true \
    && chmod +x /app/scripts/*.sh 2>/dev/null || true

# 暴露端口
EXPOSE 5000

# 工作目录
WORKDIR /app

# 启动命令
CMD ["/app/scripts/entrypoint.sh"]
