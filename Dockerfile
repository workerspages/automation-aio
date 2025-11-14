FROM accetto/ubuntu-vnc-xfce-firefox-g3:latest

USER root

# 设置所有环境变量
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
    PORT=5000

# 更新包管理器并安装所有依赖
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
    supervisor \
    && locale-gen zh_CN.UTF-8 \
    && update-locale LANG=zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 创建虚拟环境
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 创建必要的目录
RUN mkdir -p /app/web-app /app/scripts /app/firefox-xpi /home/headless/Downloads /app/data /app/logs

# 安装核心 Python 工具
RUN pip install --no-cache-dir \
    wheel \
    setuptools

# 复制 requirements 文件
COPY web-app/requirements.txt /app/web-app/

# 逐个安装 Python 依赖包
RUN pip install --no-cache-dir Flask==3.0.0
RUN pip install --no-cache-dir Flask-Login==0.6.3
RUN pip install --no-cache-dir Flask-SQLAlchemy==3.1.1
RUN pip install --no-cache-dir APScheduler==3.10.4
RUN pip install --no-cache-dir requests==2.31.0
RUN pip install --no-cache-dir selenium==4.15.2
RUN pip install --no-cache-dir cryptography==41.0.7
RUN pip install --no-cache-dir python-telegram-bot==20.7

# 复制 Firefox 扩展文件
COPY firefox-xpi/selenium-ide.xpi /app/firefox-xpi/

# 复制 Web 应用文件
COPY web-app/ /app/web-app/

# 复制启动脚本
COPY scripts/ /app/scripts/

# 安装 Firefox 扩展到系统目录
RUN mkdir -p /usr/lib/firefox/distribution/extensions && \
    cp /app/firefox-xpi/selenium-ide.xpi /usr/lib/firefox/distribution/extensions/

# 配置 Firefox 中文界面
RUN mkdir -p /usr/lib/firefox/defaults/pref && \
    echo 'pref("intl.locale.requested", "zh-CN");' > /usr/lib/firefox/defaults/pref/language.js && \
    echo 'pref("intl.accept_languages", "zh-CN, zh, en");' >> /usr/lib/firefox/defaults/pref/language.js

# 创建 supervisor 配置文件
RUN echo '[supervisord]' > /etc/supervisor/conf.d/automation.conf && \
    echo 'nodaemon=true' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'user=root' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'logfile=/app/logs/supervisord.log' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'pidfile=/tmp/supervisord.pid' >> /etc/supervisor/conf.d/automation.conf && \
    echo '' >> /etc/supervisor/conf.d/automation.conf && \
    echo '[program:webapp]' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'command=/opt/venv/bin/python3 /app/web-app/app.py' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'directory=/app/web-app' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'user=1001' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'autostart=true' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'autorestart=true' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'stdout_logfile=/app/logs/webapp.log' >> /etc/supervisor/conf.d/automation.conf && \
    echo 'stderr_logfile=/app/logs/webapp-error.log' >> /etc/supervisor/conf.d/automation.conf

# 设置脚本可执行权限和目录所有权
RUN chmod +x /app/scripts/*.sh /app/scripts/*.py && \
    chown -R 1001:0 /app /home/headless/Downloads /opt/venv /app/logs

# 暴露 Web 应用端口
EXPOSE 5000

# 切换回 root 用户来启动 supervisord（它会以指定用户运行子进程）
USER root

# 使用 supervisor 管理所有服务
CMD ["/bin/bash", "-c", "supervisord -c /etc/supervisor/supervisord.conf && exec /dockerstartup/vnc_startup.sh || tail -f /app/logs/supervisord.log"]
