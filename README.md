# 🚀 Ubuntu Automation AIO (Ultra-Slim Edition)

[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![Size](https://img.shields.io/badge/Image%20Size-~500MB-green)](https://github.com/workerspages/automation-aio)
[![License](https://img.shields.io/badge/License-MIT-orange.svg)](LICENSE)

**Ubuntu Automation AIO (Slim)** 是一个专为轻量化、高性能自动化任务设计的 Docker 工控平台。

相比于传统的臃肿桌面镜像，本项目移除了 60% 以上的冗余组件（如 Firefox、Office 等），使用极简的 **Openbox** 窗口管理器替代了 XFCE。它在一个极其精简的容器内集成了 **Google Chrome**、**AutoKey**、**Python (Selenium/Playwright)** 以及一套可视化的 **Web 任务调度面板**。

非常适合用于：**网页爬虫、RPA 自动化、定时签到、浏览器操作录制**等场景。

---

## ✨ 核心特性

### ⚡ 极致轻量 (Ultra-Slim)

* **Openbox + Tint2**: 替换了 XFCE 桌面，待机内存占用极低（仅约 100MB），启动速度飞快。
* **体积缩减**: 镜像体积大幅减小，更适合低配 VPS 部署。
* **中文支持**: 内置文泉驿微米黑字体 (`fonts-wqy-microhei`)，完美解决 Chrome 中文乱码问题。

### 🤖 强大的自动化工具链

* **Google Chrome**: 官方稳定版，预置了防检测配置 (Anti-bot)，隐藏 WebDriver 特征。
* **Selenium & Playwright**: 环境已预装，可直接调用系统 Chrome 运行。
* **AutoKey (GTK)**: 系统级键盘/鼠标宏工具，已修复崩溃问题，支持 Python 脚本控制系统输入。

### 📅 可视化 Web 调度台

* **任务管理**: 在网页上添加、编辑、删除定时任务。
* **在线代码编辑**: 内置代码编辑器，直接在浏览器中编写 Python 脚本。
* **拟人化调度**: 支持 **Cron** 表达式，独创 **“随机时间窗口”** (Random Delay) 模式，模拟真人操作时间的不确定性。

### 🛠️ 远程管理与辅助

* **NoVNC**: 直接在浏览器中访问远程桌面，无需安装客户端。
* **剪贴板同步**: 完美支持宿主机与容器之间的复制粘贴（由 `autocutsel` 驱动）。
* **Cloudflare Tunnel**: 内置内网穿透支持，无需公网 IP 即可远程管理。
* **消息推送**: 任务成功或失败可推送到 Telegram Bot 或 Email。

### ☁️ PaaS 平台优化 (NEW)

* **低内存运行**: 针对 Railway/Zeabur/Koyeb 等 PaaS 平台优化，支持在 1GB 内存环境下运行。
* **Chrome 内存优化**: 预置 7 项内存节省参数，V8 堆限制为 256MB。
* **自动 Swap**: 启动时自动创建 512MB swap 文件，应对内存压力峰值。
* **分辨率适配**: 默认 1024x600 分辨率 + 16bit 色深，减少 VNC 带宽占用。

---

## 🛠️ 3分钟快速部署指南

### 前置条件

你需要一台安装了 [Docker](https://docs.docker.com/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/) 的服务器（Linux/Windows/Mac 均可）。

### 1. 创建项目目录

在你的服务器上执行：

```bash
mkdir -p automation-aio/data automation-aio/logs automation-aio/Downloads
cd automation-aio
```

### 2. 创建配置文件

创建名为 `docker-compose.yml` 的文件，并填入以下内容：

```yaml
version: '3.8'

services:
  automation-aio:
    image: ghcr.io/workerspages/automation-aio:autokey
    container_name: automation-aio
    ports:
      - "5000:5000"
    environment:
      - VNC_RESOLUTION=1360x768               # 远程桌面分辨率 (PaaS优化: 降低至1360x768节省内存)
      - TZ=Asia/Shanghai                      # 容器时区
      - VNC_PW=admin
      - SECRET_KEY=your-secret-key-change-this
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=admin123
      - DISPLAY=:1                            # 显示面画在编号为 1 的虚拟显示器上 (请误修改)
      - MAX_SCRIPT_TIMEOUT=600                # 全局环境变量-如果你代码里的 sleep 时间超过了 600 秒，Flask 后端会认为任务卡死

      # === 数据库配置 (可选：连接外部 MariaDB) ===
      # --- 数据库 (可选，留空默认使用内置 SQLite) ---
      # 如需外接 MariaDB/MySQL，请填写以下变量:
    # - MARIADB_HOST= # 例如: 192.168.1.100
    # - MARIADB_PORT=3306
    # - MARIADB_USER=root
    # - MARIADB_PASSWORD=root
    # - MARIADB_DB=automation_aio
      # =======================================

      # === Telegram 通知配置 ===
      - TELEGRAM_BOT_TOKEN=
      - TELEGRAM_CHAT_ID=

      # === 邮件通知配置 ===
       # 开启邮件通知:true   关闭邮件通知:false 
      - ENABLE_EMAIL_NOTIFY=false
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USER=your_email@gmail.com
      - SMTP_PASSWORD=your_app_password
      - EMAIL_FROM=your_email@gmail.com
      - EMAIL_TO=receiver@example.com

      # === Cloudflare Tunnel 配置 ===
      # 必须提供 Token，否则脚本会报错并跳过启动  开启:true 关闭:false 
      - ENABLE_CLOUDFLARE_TUNNEL=false
      - CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoi...
      - APP_PUBLIC_DOMAIN=                                         # Cloudflare Tunnel后台配置的域名
    volumes:
      - ./Downloads:/home/headless/Downloads
      - ./data:/app/data
      - ./logs:/app/logs
      - ./scripts:/home/headless/.config/autokey/data/MyScripts    # autokey脚本文件目录
    restart: unless-stopped
    shm_size: '2gb'
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:5000/health" ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 3. 启动服务

```bash
docker-compose up -d
```

等待几秒钟，服务即可启动。

---

## 📖 使用指南

### 1. 访问控制台

打开浏览器访问 `http://<服务器IP>:5000`。

* **默认账号**: `admin`
* **默认密码**: `admin123`

### 2. 远程桌面 (重要：Openbox 操作说明)

点击面板右上角的 **"🖥️ 远程桌面"** 按钮进入 NoVNC 界面。

* **界面布局**:
  * 你会看到一个 **纯色背景**（通常是深灰色），这**不是**死机了，而是 Openbox 的极简风格。
  * 屏幕底部有一个细长的任务栏 (`tint2`)，显示当前打开的窗口和时间。
  * 右下角托盘区应该能看到红色的 **AutoKey 图标**。

* **如何打开菜单？**
  * **点击鼠标右键**：在桌面任意空白处点击右键，即可弹出主菜单。
  * 从中可以打开 **Terminal (终端)**、**File Manager (文件管理器)** 等工具。

* **📋 剪贴板如何同步？**
  * **从 VNC 复制到 电脑**: 在 VNC 里选中文字复制 -> 打开 VNC 侧边栏 -> 点击 **Clipboard** -> 文本框中会出现内容 -> 手动复制出来。
  * **从 电脑 复制到 VNC**: 电脑复制 -> 打开 VNC 侧边栏 -> 点击 **Clipboard** -> 粘贴到文本框 -> 在 VNC 内部按 `Ctrl+V`。

### 3. 编写与运行脚本

#### 方式 A：编写 Python/Selenium 脚本

1. 在 Web 面板点击 **"📂 脚本管理"** -> **Downloads** 选项卡。
2. 点击 **"+ 新建脚本"**，输入文件名（如 `test_chrome.py`）。
3. 输入以下示例代码并保存：

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

options = Options()
options.add_argument("--no-sandbox")
# 注意：在 Openbox 环境下，可以设为 False 观察浏览器动作
browser = webdriver.Chrome(options=options)

browser.get("https://www.baidu.com")
print(browser.title)
time.sleep(5)
browser.quit()
```

1. 回到首页，**"+ 新建任务"**，选择该脚本并点击 **"▶ 立即运行"**。

#### 方式 B：使用 AutoKey 模拟键鼠

1. 在 **"📂 脚本管理"** -> **AutoKey** 选项卡新建脚本。
2. 输入 AutoKey 代码（例如模拟键盘输入）：

```python
# 输入 Hello World 并回车
keyboard.send_keys("Hello World")
keyboard.send_keys("<enter>")
```

1. **自动重载**: 系统会自动检测 AutoKey 脚本的变更并重载服务，新建脚本后可立即使用。
2. 注意：AutoKey 脚本通常配合窗口触发，但在本平台中，你可以通过 Web 面板直接触发它。

---

## ⚙️ 进阶配置

### 关于 Playwright 的使用

为了极致压缩体积，镜像中**未预装** Playwright 自带的庞大浏览器二进制包。
如果你使用 Playwright，必须在代码中指定使用系统安装的 Chrome：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome-stable", # 👈 必须指定此路径
        headless=False
    )
    page = browser.new_page()
    page.goto("http://example.com")
    print(page.title())
    browser.close()
```

---

## ❓ 常见问题 (FAQ)

**Q: 为什么启动后看不到“开始菜单”？**
A: 这是 **Openbox** 的特性。它没有开始菜单。请在桌面空白处 **点击鼠标右键** 呼出菜单。

**Q: Chrome 启动时崩溃或报错 "Crashpad"?**
A: 请检查 `docker-compose.yml` 中是否配置了 `shm_size: '2gb'`。现代浏览器在 Docker 中需要较大的共享内存空间。

**Q: 为什么没有 Firefox 了？**
A: 这是 **Ultra-Slim (极致瘦身)** 版本。为了将镜像体积控制在最小，我们移除了 Firefox。如果你必须使用 Firefox，请使用本项目的旧版分支或自行修改 Dockerfile 安装。

**Q: 如何查看脚本的运行日志？**
A: 在 Web 面板的任务卡片上，会显示最后一次运行的状态。你可以通过 SSH 进入容器查看详细日志：`/app/data/automation.log`。

**Q: 部署到 PaaS 平台（Railway/Zeabur/Koyeb）很卡怎么办？**
A: 本项目已针对 PaaS 平台进行优化。如仍卡顿，请确保：
1. 平台分配至少 1GB RAM
2. 使用优化后的默认配置（VNC_RESOLUTION=1024x600）
3. 避免同时运行多个 Chrome 实例

**Q: shm_size 在 PaaS 上不生效怎么办？**
A: 本镜像已内置 `--disable-dev-shm-usage` 参数绕过此限制，无需额外配置。

---

## 👨‍💻 开发者信息

如果你想自己构建镜像：

1. **克隆代码**:

    ```bash
    git clone https://github.com/workerspages/automation-aio.git
    ```

2. **准备依赖文件**:
    构建前必须确保 `browser-configs/chrome.zip` 存在（可以是个空的 zip，但在构建时必须要有）：

    ```bash
    mkdir -p browser-configs && touch browser-configs/dummy && zip browser-configs/chrome.zip browser-configs/dummy
    ```

3. **构建镜像**:

    ```bash
    docker build -t automation-aio .
    ```

---

## Enjoy your automation! 🚀
