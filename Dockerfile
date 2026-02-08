# ===================================================================
# 基础镜像与环境
# ===================================================================
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ARG TARGETARCH
USER root

# 环境变量
ENV TZ=Asia/Shanghai \
  HOME=/home/headless \
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
  CHROME_BINARY=/usr/bin/google-chrome-stable \
  FLASK_ENV=production \
  FLASK_DEBUG=false \
  HOST=0.0.0.0 \
  PORT=8080 \
  DISPLAY=:1 \
  VNC_PORT=5901 \
  NOVNC_PORT=6901 \
  VNC_RESOLUTION=1360x768 \
  VNC_COL_DEPTH=16 \
  VNC_PW=admin \
  ADMIN_USERNAME=admin \
  ADMIN_PASSWORD=admin123 \
  XDG_CONFIG_DIRS=/etc/xdg \
  XDG_DATA_DIRS=/usr/local/share:/usr/share \
  PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# ===================================================================
# 系统安装 (核心层)
# ===================================================================
RUN apt-get update && \
  # 1. 安装核心工具
  apt-get install -y --no-install-recommends \
  software-properties-common gpg-agent \
  wget curl ca-certificates git \
  vim nano sudo tzdata locales net-tools openssh-client \
  iproute2 iputils-ping supervisor cron sqlite3 \
  # 2. 字体
  fonts-wqy-microhei language-pack-zh-hans \
  # 3. X11 / VNC / Audio
  x11-utils x11-xserver-utils xauth xserver-xorg-core xserver-xorg-video-dummy \
  tigervnc-standalone-server tigervnc-common tigervnc-tools \
  libasound2 \
  # 4. Openbox 桌面环境
  openbox tint2 pcmanfm lxterminal dbus-x11 libgtk-3-0 \
  # 5. 剪贴板同步工具
  autocutsel \
  # 6. Python & 编译依赖
  python3 python3-pip python3-dev python3-gi python3-xdg python3-websockify \
  gir1.2-gtk-3.0 pkg-config gcc g++ make libffi-dev libssl-dev \
  # 7. 杂项工具
  xautomation xdotool kdialog imagemagick nginx nodejs npm unzip p7zip-full \
  # 8. AutoKey
  autokey-gtk \
  # 9. Chrome 依赖库 (Common)
  libnss3 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxrandr2 \
  libpangocairo-1.0-0 libpango-1.0-0 libcups2 libdbus-1-3 libxdamage1 libxfixes3 \
  libgbm1 libdrm2 libwayland-client0 libatspi2.0-0 && \
  \
  # ============================================
  # 浏览器安装 (Multi-Arch)
  # ============================================
  if [ "$TARGETARCH" = "amd64" ]; then \
      echo "🔵 Installing Google Chrome for AMD64..."; \
      wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb; \
      apt-get install -y /tmp/chrome.deb; \
      rm /tmp/chrome.deb; \
      mv /usr/bin/google-chrome-stable /usr/bin/google-chrome-stable.original; \
      # === 预装 ChromeDriver (避免运行时下载) ===
      echo "🔧 Installing ChromeDriver for AMD64..."; \
      CHROME_VERSION=$(google-chrome-stable.original --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+\.\d+' | head -1 || echo "131.0.6778.264"); \
      CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d. -f1); \
      DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"; \
      wget -q "$DRIVER_URL" -O /tmp/chromedriver.zip 2>/dev/null || \
      wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}" -O /tmp/driver_version && \
      wget -q "https://chromedriver.storage.googleapis.com/$(cat /tmp/driver_version)/chromedriver_linux64.zip" -O /tmp/chromedriver.zip; \
      unzip -q /tmp/chromedriver.zip -d /tmp/; \
      mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver 2>/dev/null || mv /tmp/chromedriver /usr/bin/chromedriver; \
      chmod +x /usr/bin/chromedriver; \
      rm -rf /tmp/chromedriver* /tmp/driver_version; \
      echo "✅ ChromeDriver installed: $(/usr/bin/chromedriver --version 2>/dev/null || echo 'installed')"; \
  elif [ "$TARGETARCH" = "arm64" ]; then \
      echo "🟠 Installing Chromium for ARM64 (using xtradeb PPA)..."; \
      add-apt-repository -y ppa:xtradeb/apps; \
      apt-get update; \
      apt-get install -y chromium chromium-driver; \
      ln -s /usr/bin/chromium /usr/bin/google-chrome-stable.original; \
      ln -sf /usr/bin/chromedriver /usr/bin/chromedriver 2>/dev/null || true; \
      echo "✅ Chromium + ChromeDriver installed for ARM64"; \
  else \
      echo "❌ Unsupported architecture: $TARGETARCH"; exit 1; \
  fi && \
  \
  # 创建统一的启动包装脚本 (含 --disable-dev-shm-usage)
  echo '#!/bin/bash' > /usr/bin/google-chrome-stable && \
  echo 'exec /usr/bin/google-chrome-stable.original --no-sandbox --disable-dev-shm-usage --disable-gpu --no-default-browser-check --no-first-run --disable-extensions --disable-background-networking --disable-sync --disable-translate --disable-software-rasterizer --memory-pressure-off --js-flags="--max-old-space-size=256" "$@"' >> /usr/bin/google-chrome-stable && \
  chmod +x /usr/bin/google-chrome-stable && \
  \
  # Chrome 策略
  mkdir -p /etc/opt/chrome/policies/managed && \
  echo '{ "CommandLineFlagSecurityWarningsEnabled": false, "DefaultBrowserSettingEnabled": false }' > /etc/opt/chrome/policies/managed/managed_policies.json && \
  \
  # ============================================
  # 配置浏览器默认关联
  # ============================================
  update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 && \
  update-alternatives --set x-www-browser /usr/bin/google-chrome-stable && \
  \
  # ============================================
  # 安装 Cloudflare Tunnel
  # ============================================
  echo "Downloading Cloudflared for $TARGETARCH..." && \
  wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$TARGETARCH.deb" -O cloudflared.deb && \
  dpkg -i cloudflared.deb || apt-get install -f -y && \
  rm -f cloudflared.deb && \
  \
  # ============================================
  # 系统配置
  # ============================================
  ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
  locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8 && \
  groupadd -g 1001 headless && \
  useradd -u 1001 -g 1001 -m -s /bin/bash headless && \
  echo "headless ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
  \
  # ============================================
  # 瘦身清理
  # ============================================
  apt-get remove -y --purge gcc g++ make python3-dev software-properties-common gpg-agent && \
  apt-get autoremove -y && \
  rm -rf /usr/share/doc /usr/share/man /usr/share/info /usr/share/icons/Adwaita /usr/share/icons/HighContrast && \
  apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ===================================================================
# 配置 Openbox (替代 XFCE)
# ===================================================================
RUN mkdir -p /app/web-app /app/scripts /app/data /app/logs /home/headless/Downloads \
  /home/headless/.config/autokey/data/Sample\ Scripts \
  /home/headless/.config/autokey/data/My\ Phrases \
  /home/headless/.config/autokey/data/MyScripts \
  /home/headless/.config/openbox \
  /home/headless/.config/tint2 \
  /home/headless/.vnc && \
  chown -R headless:headless /app /home/headless

# === 强制 Tint2 任务栏在屏幕顶部 ===
RUN echo 'panel_position = top center horizontal\n\
  panel_size = 100% 30\n\
  panel_layer = top\n\
  panel_items = TSC\n\
  panel_background_id = 1\n\
  wm_menu = 1\n\
  panel_dock = 0\n\
  rounded = 0\n\
  border_width = 0\n\
  background_color = #222222 100\n\
  border_color = #000000 0\n\
  taskbar_mode = single_desktop\n\
  taskbar_padding = 2 2 2\n\
  taskbar_background_id = 0\n\
  taskbar_active_background_id = 1\n\
  systray_padding = 4 2 4\n\
  systray_sort = right2left\n\
  systray_background_id = 0\n\
  systray_icon_size = 20\n\
  time1_format = %H:%M\n\
  time2_format = %A %d %B\n\
  clock_font_color = #eeeeee 100\n\
  clock_padding = 4 2\n\
  clock_background_id = 0' > /home/headless/.config/tint2/tint2rc && \
  chown -R headless:headless /home/headless/.config/tint2

# === 自定义 Openbox 右键菜单 (menu.xml) ===
RUN cat << 'EOF' > /home/headless/.config/openbox/menu.xml
<?xml version="1.0" encoding="UTF-8"?>
<openbox_menu xmlns="http://openbox.org/3.4/menu">
<menu id="root-menu" label="Openbox 3">
<item label="Google Chrome">
<action name="Execute">
<command>google-chrome-stable --no-sandbox</command>
</action>
</item>
<item label="AutoKey">
<action name="Execute">
<command>autokey-gtk --verbose</command>
</action>
</item>
<separator />
<item label="Terminal">
<action name="Execute">
<command>lxterminal</command>
</action>
</item>
<item label="File Manager">
<action name="Execute">
<command>pcmanfm</command>
</action>
</item>
<separator />
<item label="Restart Openbox">
<action name="Restart" />
</item>
</menu>
</openbox_menu>
EOF
RUN chown headless:headless /home/headless/.config/openbox/menu.xml

# === Openbox 配置文件 (rc.xml) - 终端置顶 ===
RUN mkdir -p /home/headless/.config/openbox && \
  cp /etc/xdg/openbox/rc.xml /home/headless/.config/openbox/rc.xml && \
  sed -i 's|</applications>|  <application class="Lxterminal">\n    <layer>above</layer>\n  </application>\n</applications>|' /home/headless/.config/openbox/rc.xml && \
  chown headless:headless /home/headless/.config/openbox/rc.xml

# === 关键修改：Openbox 自动启动脚本 ===
# 移除了 'pcmanfm --desktop'，防止它遮挡 Openbox 的右键菜单
RUN echo 'autocutsel -fork -selection PRIMARY & \n\
  autocutsel -fork -selection CLIPBOARD & \n\
  tint2 & \n\
  /usr/bin/autokey-gtk --verbose &' > /home/headless/.config/openbox/autostart && \
  chown headless:headless /home/headless/.config/openbox/autostart

# VNC 启动脚本
RUN cat << 'EOF' > /home/headless/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
eval $(dbus-launch --sh-syntax)
export DBUS_SESSION_BUS_ADDRESS
echo "export DBUS_SESSION_BUS_ADDRESS='$DBUS_SESSION_BUS_ADDRESS'" > $HOME/.dbus-env
chmod 644 $HOME/.dbus-env
# 纯色背景 (因为我们去掉了 pcmanfm --desktop，所以需要手动设置背景)
xsetroot -solid "#333333" &
xset s off &
xset -dpms &
xset s noblank &
export GTK_IM_MODULE=xim
export XMODIFIERS=@im=none
export LANG=zh_CN.UTF-8
exec /usr/bin/openbox-session
EOF
RUN chmod +x /home/headless/.vnc/xstartup && chown headless:headless /home/headless/.vnc/xstartup

# ===================================================================
# 安装 noVNC
# ===================================================================
WORKDIR /tmp
RUN mkdir -p /usr/share/novnc && \
  wget -qO- https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.tar.gz | tar xz --strip-components=1 -C /usr/share/novnc && \
  mkdir -p /usr/share/novnc/utils/websockify && \
  wget -qO- https://github.com/novnc/websockify/archive/refs/tags/v0.11.0.tar.gz | tar xz --strip-components=1 -C /usr/share/novnc/utils/websockify && \
  ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html && \
  chown -R headless:headless /usr/share/novnc && \
  chmod -R 755 /usr/share/novnc

# ===================================================================
# Python 环境
# ===================================================================
COPY web-app/requirements.txt /app/web-app/
RUN pip install --no-cache-dir --upgrade pip setuptools && \
  pip install --no-cache-dir -r /app/web-app/requirements.txt && \
  rm -rf /root/.cache/pip

# ===================================================================
# 复制与配置
# ===================================================================
COPY web-app/ /app/web-app/
COPY nginx.conf /etc/nginx/nginx.conf
COPY scripts/ /app/scripts/
COPY services.conf /etc/supervisor/conf.d/services.conf
COPY browser-configs/chrome.zip /tmp/chrome.zip

RUN mkdir -p /home/headless/.config/google-chrome && \
  unzip -q /tmp/chrome.zip -d /home/headless/.config/google-chrome/ && \
  rm /tmp/chrome.zip && \
  rm -f /home/headless/.config/google-chrome/SingletonLock && \
  chown -R headless:headless /home/headless/.config

RUN echo '#!/bin/bash' > /usr/local/bin/init-database && \
  echo 'cd /app/web-app && python3 init_db.py' >> /usr/local/bin/init-database && \
  chmod +x /usr/local/bin/init-database

RUN chown -R headless:headless /app /home/headless \
  && chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true \
  && chmod +x /app/scripts/*.sh 2>/dev/null || true \
  && mkdir -p /tmp/.X11-unix /tmp/.ICE-unix \
  && chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix

EXPOSE 8080
WORKDIR /app
CMD ["/app/scripts/entrypoint.sh"]
