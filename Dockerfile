FROM accetto/ubuntu-vnc-xfce-firefox-g3:latest

USER root

ENV TZ=Asia/Shanghai \
    LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
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
    DISPLAY=:1

# 第一批：基础环境及字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    curl \
    wget \
    ca-certificates \
    sudo \
    git \
    cron \
    sqlite3

RUN apt-get install -y --no-install-recommends language-pack-zh-hans || true
RUN apt-get install -y --no-install-recommends fonts-noto-cjk fonts-noto-cjk-extra || true

RUN locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8

# 第二批：Python环境
RUN apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev

RUN apt-get install -y --no-install-recommends python3-full || true

# 第三批：编译工具及库
RUN apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev

# 第四批：X11和桌面依赖
RUN apt-get install -y --no-install-recommends \
    python3-gi \
    gir1.2-gtk-3.0 \
    xvfb \
    xfce4-session \
    xfce4-panel \
    xfce4-terminal \
    xfce4-appfinder \
    xfce4-settings \
    dbus-x11

# 第五批：图形驱动及mesa
RUN apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libegl1-mesa \
    libpci3 \
    mesa-utils

# 第六批：GTK/Gnome 相关，容错处理
RUN apt-get install -y --no-install-recommends gsettings-desktop-schemas || true
RUN apt-get install -y --no-install-recommends dconf-cli || true
RUN apt-get install -y --no-install-recommends gnome-icon-theme || true
RUN apt-get install -y --no-install-recommends policykit-1 || true

RUN apt-get install -y --no-install-recommends fuse || true
RUN apt-get install -y --no-install-recommends python3-websockify || true

# 手动下载并指定正确的autokey-common deb包
WORKDIR /tmp
RUN wget https://github.com/autokey/autokey/releases/download/v0.96.0/autokey-common_0.96.0_all.deb \
    && wget https://github.com/autokey/autokey/releases/download/v0.96.0/autokey-gtk_0.96.0-0_all.deb \
    && dpkg -i autokey-common_0.96.0_all.deb autokey-gtk_0.96.0-0_all.deb || apt-get install -f -y \
    && rm -f autokey-common_0.96.0_all.deb autokey-gtk_0.96.0-0_all.deb

# noVNC安装
RUN git clone https://github.com/novnc/noVNC.git /usr/share/novnc

# 清理APT缓存
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p /app/web-app /app/scripts /home/headless/Downloads /app/data /app/logs

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY web-app/requirements.txt /app/web-app/

RUN pip install --no-cache-dir wheel setuptools && \
    pip install --no-cache-dir -r /app/web-app/requirements.txt

COPY firefox-xpi /app/firefox-xpi/
COPY web-app/ /app/web-app/
COPY scripts/ /app/scripts/

RUN mkdir -p /usr/lib/firefox/distribution && \
    cp /app/firefox-xpi/selenium-ide.xpi /usr/lib/firefox/distribution/ && \
    echo '{' > /usr/lib/firefox/distribution/policies.json && \
    echo '  "policies": {' >> /usr/lib/firefox/distribution/policies.json && \
    echo '    "Extensions": {' >> /usr/lib/firefox/distribution/policies.json && \
    echo '      "Install": [' >> /usr/lib/firefox/distribution/policies.json && \
    echo '        "file:///usr/lib/firefox/distribution/selenium-ide.xpi"' >> /usr/lib/firefox/distribution/policies.json && \
    echo '      ]' >> /usr/lib/firefox/distribution/policies.json && \
    echo '    },' >> /usr/lib/firefox/distribution/policies.json && \
    echo '    "ExtensionSettings": {' >> /usr/lib/firefox/distribution/policies.json && \
    echo '      "*": {' >> /usr/lib/firefox/distribution/policies.json && \
    echo '        "installation_mode": "allowed",' >> /usr/lib/firefox/distribution/policies.json && \
    echo '        "blocked_install_message": "Custom addons are disabled"' >> /usr/lib/firefox/distribution/policies.json && \
    echo '      }' >> /usr/lib/firefox/distribution/policies.json && \
    echo '    }' >> /usr/lib/firefox/distribution/policies.json && \
    echo '  }' >> /usr/lib/firefox/distribution/policies.json && \
    echo '}' >> /usr/lib/firefox/distribution/policies.json

RUN mkdir -p /home/headless/.vnc && \
    echo '#!/bin/sh' > /home/headless/.vnc/xstartup && \
    echo 'unset SESSION_MANAGER' >> /home/headless/.vnc/xstartup && \
    echo 'unset DBUS_SESSION_BUS_ADDRESS' >> /home/headless/.vnc/xstartup && \
    echo 'exec startxfce4' >> /home/headless/.vnc/xstartup && \
    chmod +x /home/headless/.vnc/xstartup

RUN mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml && \
    echo '<?xml version="1.0" encoding="UTF-8"?>' > /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '<channel name="xfce4-power-manager" version="1.0">' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '  <property name="xfce4-power-manager" type="empty">' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '    <property name="blank-on-ac" type="int" value="0"/>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '    <property name="blank-on-battery" type="int" value="0"/>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '    <property name="dpms-enabled" type="bool" value="false"/>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '    <property name="dpms-on-ac-sleep" type="uint" value="0"/>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '    <property name="dpms-on-ac-off" type="uint" value="0"/>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '  </property>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml && \
    echo '</channel>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml

RUN mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml && \
    echo '<?xml version="1.0" encoding="UTF-8"?>' > /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml && \
    echo '<channel name="xfce4-screensaver" version="1.0">' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml && \
    echo '  <property name="saver" type="empty">' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml && \
    echo '    <property name="enabled" type="bool" value="false"/>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml && \
    echo '    <property name="mode" type="int" value="0"/>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml && \
    echo '  </property>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml && \
    echo '</channel>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml

RUN chmod +x /app/scripts/*.sh /app/scripts/*.py && chown -R 1001:0 /app /home/headless /opt/venv

EXPOSE 5000 5901 6901

USER 1001

CMD ["/app/scripts/startup.sh"]
