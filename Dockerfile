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

# 更新包管理器并安装所有依赖（包含中文字体）
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
    && locale-gen zh_CN.UTF-8 \
    && update-locale LANG=zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 配置系统语言
RUN echo "LANG=zh_CN.UTF-8" > /etc/default/locale && \
    echo "LC_ALL=zh_CN.UTF-8" >> /etc/default/locale

# 创建虚拟环境
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 创建必要的目录并设置权限
RUN mkdir -p /app/web-app /app/scripts /app/firefox-xpi /home/headless/Downloads /app/data /app/logs && \
    chmod -R 777 /app/data /app/logs

# 安装核心 Python 工具
RUN pip install --no-cache-dir wheel setuptools

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

# 配置 Firefox 中文界面和字体
RUN mkdir -p /usr/lib/firefox/defaults/pref && \
    echo 'pref("intl.locale.requested", "zh-CN");' > /usr/lib/firefox/defaults/pref/language.js && \
    echo 'pref("intl.accept_languages", "zh-CN, zh, en");' >> /usr/lib/firefox/defaults/pref/language.js && \
    echo 'pref("font.name.serif.zh-CN", "WenQuanYi Zen Hei");' >> /usr/lib/firefox/defaults/pref/language.js && \
    echo 'pref("font.name.sans-serif.zh-CN", "WenQuanYi Zen Hei");' >> /usr/lib/firefox/defaults/pref/language.js && \
    echo 'pref("font.name.monospace.zh-CN", "WenQuanYi Zen Hei Mono");' >> /usr/lib/firefox/defaults/pref/language.js

# 配置 XFCE 中文界面
RUN mkdir -p /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml && \
    echo '<?xml version="1.0" encoding="UTF-8"?>' > /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml && \
    echo '<channel name="xsettings" version="1.0">' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml && \
    echo '  <property name="Gtk" type="empty">' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml && \
    echo '    <property name="FontName" type="string" value="WenQuanYi Zen Hei 10"/>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml && \
    echo '  </property>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml && \
    echo '</channel>' >> /home/headless/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml

# 给 headless 用户 sudo 权限（无需密码）
RUN echo "headless ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# 设置脚本可执行权限和目录所有权
RUN chmod +x /app/scripts/*.sh /app/scripts/*.py && \
    chown -R 1001:0 /app /home/headless /opt/venv

# 暴露端口
EXPOSE 5000

# 保持 root 用户启动（startup.sh 会处理权限和服务启动）
USER root

# 启动命令
CMD ["/app/scripts/startup.sh"]
