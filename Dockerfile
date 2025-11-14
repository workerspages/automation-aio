FROM accetto/ubuntu-vnc-xfce-firefox-g3:latest

USER root

# 设置环境变量
ENV TZ=Asia/Shanghai \
    LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8 \
    DEBIAN_FRONTEND=noninteractive

# 更新包管理器并安装所有依赖（一次性完成）
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
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
    && locale-gen zh_CN.UTF-8 \
    && update-locale LANG=zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 创建虚拟环境（避免系统 Python 冲突）
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 创建目录
RUN mkdir -p /app/web-app /app/scripts /app/firefox-xpi /home/headless/Downloads /app/data

# 先安装核心依赖
RUN pip install --no-cache-dir \
    wheel \
    setuptools

# 复制 requirements 文件
COPY web-app/requirements.txt /app/web-app/

# 逐个安装依赖包（更容易定位问题）
RUN pip install --no-cache-dir Flask==3.0.0
RUN pip install --no-cache-dir Flask-Login==0.6.3
RUN pip install --no-cache-dir Flask-SQLAlchemy==3.1.1
RUN pip install --no-cache-dir APScheduler==3.10.4
RUN pip install --no-cache-dir requests==2.31.0
RUN pip install --no-cache-dir selenium==4.15.2
RUN pip install --no-cache-dir cryptography==41.0.7
RUN pip install --no-cache-dir python-telegram-bot==20.7

# 复制应用文件
COPY firefox-xpi/selenium-ide.xpi /app/firefox-xpi/
COPY web-app/ /app/web-app/
COPY scripts/ /app/scripts/

# 安装 Firefox 扩展
RUN mkdir -p /usr/lib/firefox/distribution/extensions && \
    cp /app/firefox-xpi/selenium-ide.xpi /usr/lib/firefox/distribution/extensions/

# 设置 Firefox 中文
RUN mkdir -p /usr/lib/firefox/defaults/pref && \
    echo 'pref("intl.locale.requested", "zh-CN");' > /usr/lib/firefox/defaults/pref/language.js && \
    echo 'pref("intl.accept_languages", "zh-CN, zh, en");' >> /usr/lib/firefox/defaults/pref/language.js

# 设置权限
RUN chmod +x /app/scripts/*.sh /app/scripts/*.py && \
    chown -R 1001:0 /app /home/headless/Downloads /opt/venv

EXPOSE 5000

USER 1001

CMD ["/app/scripts/startup.sh"]
