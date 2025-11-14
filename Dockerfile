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
    && locale-gen zh_CN.UTF-8 \
    && update-locale LANG=zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 安装 Actiona AppImage，不解压，直接使用 AppImage 文件
RUN mkdir -p /opt/actiona && \
    wget -O /opt/actiona/actiona.AppImage https://github.com/Jmgr/actiona/releases/download/v3.11.1/actiona-3.11.1-x86_64.AppImage && \
    chmod +x /opt/actiona/actiona.AppImage && \
    ln -s /opt/actiona/actiona.AppImage /usr/local/bin/actiona

# 创建必要目录，权限设置应由宿主机控制，避免容器内 chmod
RUN mkdir -p /app/web-app /app/scripts /home/headless/Downloads /app/data /app/logs

# 创建 Python 虚拟环境
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY web-app/requirements.txt /app/web-app/

RUN pip install --no-cache-dir wheel setuptools && \
    pip install --no-cache-dir -r /app/web-app/requirements.txt

COPY firefox-xpi /app/firefox-xpi/
COPY web-app/ /app/web-app/
COPY scripts/ /app/scripts/

# 安装 Firefox 扩展
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

RUN chmod +x /app/scripts/*.sh /app/scripts/*.py && chown -R 1001:0 /app /home/headless /opt/venv

EXPOSE 5000

USER 1001

CMD ["/app/scripts/startup.sh"]
