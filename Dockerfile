FROM accetto/ubuntu-vnc-xfce-firefox-g3:latest

USER root

# 设置时区和语言为简体中文
ENV TZ=Asia/Shanghai \
    LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8

# 安装必要的软件包
RUN apt-get update && apt-get install -y \
    locales \
    python3 \
    python3-pip \
    cron \
    sqlite3 \
    && locale-gen zh_CN.UTF-8 \
    && update-locale LANG=zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 创建必要的目录
RUN mkdir -p /app/web-app /app/scripts /app/firefox-xpi /home/headless/Downloads

# 复制Firefox扩展
COPY firefox-xpi/selenium-ide.xpi /app/firefox-xpi/

# 安装Firefox扩展（使用Firefox策略）
RUN mkdir -p /usr/lib/firefox/distribution/extensions && \
    cp /app/firefox-xpi/selenium-ide.xpi /usr/lib/firefox/distribution/extensions/

# 设置Firefox语言为简体中文
RUN mkdir -p /usr/lib/firefox/defaults/pref && \
    echo 'pref("intl.locale.requested", "zh-CN");' > /usr/lib/firefox/defaults/pref/language.js && \
    echo 'pref("intl.accept_languages", "zh-CN, zh, en");' >> /usr/lib/firefox/defaults/pref/language.js

# 复制Web应用
COPY web-app/ /app/web-app/
COPY scripts/ /app/scripts/

# 安装Python依赖
RUN pip3 install --no-cache-dir -r /app/web-app/requirements.txt

# 设置权限
RUN chmod +x /app/scripts/*.sh /app/scripts/*.py && \
    chown -R 1001:0 /app /home/headless/Downloads

# 暴露Web端口
EXPOSE 5000

USER 1001

# 启动脚本
CMD ["/app/scripts/startup.sh"]
