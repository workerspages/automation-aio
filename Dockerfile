# ===================================================================
# STAGE 1: Base Image & Dependencies
# ===================================================================
FROM ubuntu:22.04

# 避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive

USER root

# 环境变量
ENV TZ=Asia/Shanghai \
    HOME=/home/headless \
    LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8 \
    # ... (其他应用环境变量保持不变) ...
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# ===================================================================
# 核心系统安装 (合并层以减小体积)
# ===================================================================
RUN apt-get update && \
    # 1. 安装基础工具
    apt-get install -y --no-install-recommends \
    software-properties-common gnupg2 wget curl ca-certificates \
    git vim nano sudo tzdata locales net-tools openssh-client \
    iproute2 iputils-ping supervisor cron sqlite3 \
    # 字体 (只保留必要的)
    fonts-wqy-microhei fonts-noto-cjk language-pack-zh-hans \
    # X11 和 VNC
    x11-utils x11-xserver-utils xauth xserver-xorg-core xserver-xorg-video-dummy \
    tigervnc-standalone-server tigervnc-common tigervnc-tools \
    # 桌面环境 (移除 xfce4-goodies 以瘦身)
    xfce4 xfce4-terminal dbus-x11 libgtk-3-0 \
    # Python 和 编译依赖
    python3 python3-pip python3-venv python3-dev python3-gi python3-xdg python3-websockify \
    gir1.2-gtk-3.0 pkg-config gcc g++ make libffi-dev libssl-dev \
    # 其他工具
    xautomation xdotool kdialog imagemagick nginx nodejs npm unzip p7zip-full \
    # 浏览器依赖库
    libnss3 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxrandr2 libasound2 \
    libpangocairo-1.0-0 libpango-1.0-0 libcups2 libdbus-1-3 libxdamage1 libxfixes3 \
    libgbm1 libdrm2 libwayland-client0 libatspi2.0-0 && \
    \
    # 2. 安装 Firefox (PPA版)
    add-apt-repository -y ppa:mozillateam/ppa && \
    echo 'Package: *' > /etc/apt/preferences.d/mozilla-firefox && \
    echo 'Pin: release o=LP-PPA-mozillateam' >> /etc/apt/preferences.d/mozilla-firefox && \
    echo 'Pin-Priority: 1001' >> /etc/apt/preferences.d/mozilla-firefox && \
    apt-get update && apt-get install -y --no-install-recommends firefox firefox-locale-zh-hans && \
    \
    # 3. 安装 AutoKey (GTK)
    apt-get install -y autokey-gtk && \
    \
    # 4. 清理不需要的包 (卸载屏保、文档等)
    apt-get purge -y xfce4-screensaver gnome-screensaver xscreensaver && \
    rm -rf /usr/share/doc /usr/share/man /usr/share/info && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ===================================================================
# 配置 Firefox 启动器
# ===================================================================
RUN cat << 'EOF' > /usr/local/bin/firefox-launcher
#!/bin/bash
export DISPLAY=:1
exec /usr/bin/firefox --no-remote --disable-gpu "$@"
EOF
RUN chmod +x /usr/local/bin/firefox-launcher && \
    mkdir -p /usr/share/applications && \
    cat << 'EOF' > /usr/share/applications/firefox.desktop
[Desktop Entry]
Version=1.0
Name=Firefox
GenericName=Web Browser
Exec=/usr/local/bin/firefox-launcher %u
Terminal=false
Type=Application
Icon=firefox
Categories=Network;WebBrowser;
EOF

# ===================================================================
# 安装 Google Chrome (下载后立即删除 deb 包)
# ===================================================================
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb && \
    apt-get update && \
    apt-get install -y /tmp/chrome.deb && \
    rm /tmp/chrome.deb && \
    rm -rf /var/lib/apt/lists/* && \
    # Chrome 启动包装器
    mv /usr/bin/google-chrome-stable /usr/bin/google-chrome-stable.original && \
    echo '#!/bin/bash' > /usr/bin/google-chrome-stable && \
    echo 'exec /usr/bin/google-chrome-stable.original --no-sandbox --disable-gpu --no-default-browser-check --no-first-run "$@"' >> /usr/bin/google-chrome-stable && \
    chmod +x /usr/bin/google-chrome-stable && \
    # Chrome 默认策略
    mkdir -p /etc/opt/chrome/policies/managed && \
    echo '{ "CommandLineFlagSecurityWarningsEnabled": false, "DefaultBrowserSettingEnabled": false }' > /etc/opt/chrome/policies/managed/managed_policies.json

# ===================================================================
# 配置浏览器默认关联
# ===================================================================
RUN update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 && \
    update-alternatives --set x-www-browser /usr/bin/google-chrome-stable

# ===================================================================
# 安装 Cloudflare Tunnel
# ===================================================================
RUN wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && \
    dpkg -i cloudflared-linux-amd64.deb || apt-get install -f -y && \
    rm -f cloudflared-linux-amd64.deb

# ===================================================================
# 系统配置 (时区、用户、目录)
# ===================================================================
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8 && \
    groupadd -g 1001 headless && \
    useradd -u 1001 -g 1001 -m -s /bin/bash headless && \
    echo "headless ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p /app/web-app /app/scripts /app/data /app/logs /home/headless/Downloads \
             /home/headless/.config/autokey/data/MyScripts \
             /home/headless/.config/autokey/data/My\ Phrases \
             /home/headless/.local/share \
             /home/headless/.config/autostart && \
    chown -R headless:headless /app /home/headless

# ===================================================================
# 安装 noVNC (清理 git 历史)
# ===================================================================
WORKDIR /tmp
RUN git clone --depth 1 https://github.com/novnc/noVNC.git /usr/share/novnc && \
    git clone --depth 1 https://github.com/novnc/websockify /usr/share/novnc/utils/websockify && \
    ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html && \
    rm -rf /usr/share/novnc/.git /usr/share/novnc/utils/websockify/.git

# ===================================================================
# VNC 和 AutoKey 配置
# ===================================================================
# ... (此处插入 VNC xstartup 和 autokey.desktop 的 echo 逻辑，与之前一致) ...
# 为了节省篇幅，请保留原 Dockerfile 中 echo VNC xstartup 和 autokey.desktop 的部分
# 务必保留原逻辑！

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

# ===================================================================
# Python 环境 (重点优化：安装后卸载编译工具)
# ===================================================================
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY web-app/requirements.txt /app/web-app/

RUN mkdir -p /opt/playwright && \
    # 1. 更新 pip
    pip install --no-cache-dir --upgrade pip wheel setuptools && \
    # 2. 安装依赖
    pip install --no-cache-dir -r /app/web-app/requirements.txt && \
    # 3. Playwright 浏览器 (只安装 Chrome 和 Firefox，跳过 WebKit)
    playwright install chromium firefox && \
    # 4. 瘦身：卸载编译工具 (gcc 等)，节省约 300MB
    apt-get remove -y --purge gcc g++ make python3-dev && \
    apt-get autoremove -y && \
    apt-get clean && \
    # 5. 清理 pip 缓存
    rm -rf /root/.cache/pip && \
    chmod -R 777 /opt/playwright

# ===================================================================
# 复制应用代码
# ===================================================================
COPY web-app/ /app/web-app/
COPY nginx.conf /etc/nginx/nginx.conf
COPY scripts/ /app/scripts/
COPY services.conf /etc/supervisor/conf.d/services.conf
COPY browser-configs/ /tmp/

# 解压浏览器配置并清理
RUN mkdir -p /home/headless/.config/google-chrome /home/headless/.mozilla && \
    unzip -q /tmp/chrome.zip -d /home/headless/.config/google-chrome/ && \
    unzip -q /tmp/firefox.zip -d /home/headless/.mozilla/ && \
    rm -rf /tmp/chrome.zip /tmp/firefox.zip && \
    rm -f /home/headless/.config/google-chrome/Singleton* && \
    chown -R headless:headless /home/headless/.config /home/headless/.mozilla

# ===================================================================
# 权限与启动
# ===================================================================
# 初始化 DB 脚本 (同原版)
RUN echo '#!/bin/bash' > /usr/local/bin/init-database && \
    echo 'cd /app/web-app && /opt/venv/bin/python3 init_db.py' >> /usr/local/bin/init-database && \
    chmod +x /usr/local/bin/init-database

RUN chown -R headless:headless /app /home/headless /opt/venv \
    && chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true \
    && chmod +x /app/scripts/*.sh 2>/dev/null || true

RUN mkdir -p /tmp/.X11-unix /tmp/.ICE-unix && \
    chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix && \
    echo "allowed_users=anybody" > /etc/X11/Xwrapper.config && \
    mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml && \
    chown -R headless:headless /home/headless/.config

EXPOSE 5000
WORKDIR /app
CMD ["/app/scripts/entrypoint.sh"]
