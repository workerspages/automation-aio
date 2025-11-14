FROM accetto/ubuntu-vnc-xfce-firefox-g3:latest

USER root

ENV TZ=Asia/Shanghai \
    LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    python3 \
    python3-pip \
    python3-dev \
    python3-setuptools \
    build-essential \
    pkg-config \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    cron \
    sqlite3 \
    curl \
    ca-certificates \
    && locale-gen zh_CN.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# 创建目录
RUN mkdir -p /app/web-app /app/scripts /app/firefox-xpi /home/headless/Downloads /app/data

# 复制 requirements
COPY web-app/requirements.txt /tmp/

# 分步安装 Python 包（避免内存问题）
RUN python3 -m pip install --upgrade pip && \
    pip3 install --no-cache-dir wheel setuptools && \
    pip3 install --no-cache-dir Flask==3.0.0 Werkzeug==3.0.1 && \
    pip3 install --no-cache-dir Flask-Login==0.6.3 && \
    pip3 install --no-cache-dir Flask-SQLAlchemy==3.1.1 SQLAlchemy==2.0.23 && \
    pip3 install --no-cache-dir pytz tzdata && \
    pip3 install --no-cache-dir APScheduler==3.10.4 && \
    pip3 install --no-cache-dir requests==2.31.0 certifi && \
    pip3 install --no-cache-dir selenium==4.15.2 && \
    pip3 install --no-cache-dir cryptography==41.0.7 && \
    pip3 install --no-cache-dir python-telegram-bot==20.7

# 复制应用文件
COPY firefox-xpi/selenium-ide.xpi /app/firefox-xpi/
COPY web-app/ /app/web-app/
COPY scripts/ /app/scripts/

# Firefox 配置
RUN mkdir -p /usr/lib/firefox/distribution/extensions && \
    cp /app/firefox-xpi/selenium-ide.xpi /usr/lib/firefox/distribution/extensions/ && \
    mkdir -p /usr/lib/firefox/defaults/pref && \
    echo 'pref("intl.locale.requested", "zh-CN");' > /usr/lib/firefox/defaults/pref/language.js && \
    echo 'pref("intl.accept_languages", "zh-CN, zh, en");' >> /usr/lib/firefox/defaults/pref/language.js

# 设置权限
RUN chmod +x /app/scripts/*.sh /app/scripts/*.py && \
    chown -R 1001:0 /app /home/headless/Downloads

EXPOSE 5000

USER 1001

CMD ["/app/scripts/startup.sh"]
