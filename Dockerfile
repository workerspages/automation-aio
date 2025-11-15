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

RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    language-pack-zh-hans \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    python3-full \
    python3-pip \
    python3-venv \
    python3-dev \
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
    libpng-dev \
    cron \
    sqlite3 \
    curl \
    wget \
    ca-certificates \
    sudo \
    fuse \
    autokey-gtk \
    autokey-common \
    python3-gi \
    gir1.2-gtk-3.0 \
    xvfb \
    xfce4-session \
    xfce4-panel \
    xfce4-terminal \
    xfce4-appfinder \
    xfce4-settings \
    python3-websockify \
    git \
    && git clone https://github.com/novnc/noVNC.git /usr/share/novnc \
    && locale-gen zh_CN.UTF-8 \
    && update-locale LANG=zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

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

# 创建并配置VNC xstartup文件
RUN mkdir -p /home/headless/.vnc && \
    echo '#!/bin/sh' > /home/headless/.vnc/xstartup && \
    echo 'unset SESSION_MANAGER' >> /home/headless/.vnc/xstartup && \
    echo 'unset DBUS_SESSION_BUS_ADDRESS' >> /home/headless/.vnc/xstartup && \
    echo 'exec startxfce4' >> /home/headless/.vnc/xstartup && \
    chmod +x /home/headless/.vnc/xstartup

# 禁用XFCE电源管理和屏幕保护
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

# 禁用屏幕保护程序
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
