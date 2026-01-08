
# 🚀 Ubuntu Automation AIO (Ultra-Slim Edition)

[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![Size](https://img.shields.io/badge/Image%20Size-~500MB-green)]()
[![License](https://img.shields.io/badge/License-MIT-orange.svg)]()

**Ubuntu Automation AIO (Slim)** 是一个极致轻量化的 Docker 自动化工控平台。

相比于传统的 XFCE 版本，该版本将体积减少了 **60% 以上**，移除了所有冗余组件，专为 **Chrome 浏览器自动化** 和 **AutoKey 桌面宏** 任务设计。它使用 **Openbox** 窗口管理器替代了臃肿的桌面环境，在此基础上保留了完整的 Web 调度面板和远程管理功能。

---

## ✨ 核心特性

### ⚡ 极致轻量 (Ultra-Slim)
- **Openbox + Tint2**: 替换了 XFCE，待机内存占用极低 (<100MB)，镜像体积大幅缩减。
- **精简依赖**: 移除 Firefox、Actiona、LibreOffice 等非必要组件，仅保留 Chrome。
- **中文字体**: 内置文泉驿微米黑 (`fonts-wqy-microhei`)，完美支持中文显示。

### 🤖 核心自动化工具
- **Google Chrome**: 官方稳定版，预置防检测 (Anti-bot) 配置。
- **Selenium & Playwright**: Python 环境已预装驱动，开箱即用。
- **AutoKey (GTK)**: 强大的键盘/鼠标宏工具，支持 Python 脚本控制系统级输入。

### 📅 Web 智能调度台
- **可视化管理**: 通过 Web 界面添加、编辑、运行 Python/AutoKey 脚本。
- **在线编辑**: 集成 CodeMirror 编辑器，直接在浏览器中写代码。
- **拟人化调度**: 支持 **CRON** 定时和 **随机时间窗口** (Random Delay) 执行，有效规避风控。

### 🛠️ 辅助功能
- **NoVNC**: 浏览器直接访问远程桌面，支持剪贴板同步 (由 `autocutsel` 驱动)。
- **Cloudflare Tunnel**: 内置内网穿透支持，无需公网 IP。
- **通知推送**: 集成 Telegram Bot 和 Email 通知。

---

## 🛠️ 快速部署

### 1. 创建项目目录
```bash
mkdir -p automation-slim/data automation-slim/logs automation-slim/Downloads
cd automation-slim
```

### 2. 创建 `docker-compose.yml`
```yaml
version: '3.8'

services:
  automation:
    image: ghcr.io/workerspages/automation-aio:autokey
    container_name: automation-slim
    ports:
      - "5000:5000"
    environment:
      - VNC_PW=admin          # VNC 连接密码
      - ADMIN_USERNAME=admin  # Web 面板账号
      - ADMIN_PASSWORD=admin123
      - TZ=Asia/Shanghai
      
      # === 通知配置 (可选) ===
      - TELEGRAM_BOT_TOKEN=
      - TELEGRAM_CHAT_ID=
      
      # === 内网穿透 (可选) ===
      - ENABLE_CLOUDFLARE_TUNNEL=false
      - CLOUDFLARE_TUNNEL_TOKEN=
      
      # === 数据库 (可选，默认SQLite) ===
      - MARIADB_HOST=
    volumes:
      - ./Downloads:/home/headless/Downloads
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    shm_size: '2gb' # Chrome 必须配置，否则易崩溃
```

### 3. 启动服务
```bash
docker-compose up -d
```

---

## 📖 使用指南

### 1. 访问控制台
浏览器访问 `http://<服务器IP>:5000`。
*   默认账号: `admin`
*   默认密码: `admin123`

### 2. 远程桌面 (Openbox 操作说明)
点击右上角的 **"🖥️ 远程桌面"** 进入 NoVNC。

*   **界面布局**: 你会看到一个纯色背景（通常是深灰色），底部有一个简单的任务栏 (`tint2`)。
*   **右键菜单**: **Openbox 的核心操作都在右键菜单里**。在桌面任意空白处 **点击鼠标右键**，可以打开终端、文件管理器或重启服务。
*   **AutoKey**: 图标会显示在底部任务栏的右侧托盘区。
*   **剪贴板同步**:
    *   **VNC -> 电脑**: 在 VNC 里复制内容 -> 打开 NoVNC 左侧栏 -> 点击 **Clipboard** -> 在文本框中复制。
    *   **电脑 -> VNC**: 电脑复制 -> 打开 NoVNC **Clipboard** -> 粘贴到文本框 -> 在 VNC 里按 Ctrl+V。

### 3. 编写脚本
在 Web 面板点击 **"📂 脚本管理"**：
*   **Downloads 目录**: 存放普通 Python 脚本 (Selenium/Playwright)。
    *   示例：`from selenium import webdriver...`
*   **AutoKey 目录**: 存放 AutoKey 脚本 (模拟键鼠)。
    *   示例：`keyboard.send_keys("Hello World")`

---

## ⚙️ 环境变量参数

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `VNC_PW` | admin | VNC 远程桌面密码 |
| `VNC_RESOLUTION` | 1360x768 | 桌面分辨率 |
| `ADMIN_USERNAME` | admin | Web 面板用户名 |
| `ADMIN_PASSWORD` | admin123 | Web 面板密码 |
| `TZ` | Asia/Shanghai | 容器时区 |
| `MARIADB_HOST` | (空) | 设置后自动切换为 MySQL/MariaDB 模式 |
| `ENABLE_CLOUDFLARE_TUNNEL` | false | 是否启用 Cloudflare Tunnel |
| `CLOUDFLARE_TUNNEL_TOKEN` | (空) | Cloudflare Token |

---

## 📦 目录结构

```text
/automation-slim
├── data/           # 数据库 (tasks.db) 和 运行日志 (automation.log)
├── logs/           # 系统日志 (Supervisor, VNC, Nginx)
└── Downloads/      # 脚本存放目录
```

---

## ❓ 常见问题 (FAQ)

**Q: 为什么桌面是灰色的，没有开始菜单？**
A: 这是 **Openbox** 的特性。为了追求极致的性能和体积，我们去掉了传统桌面环境。**请点击鼠标右键** 呼出菜单。

**Q: AutoKey 报错 "Fatal Error" 弹窗？**
A: 请确保使用了最新的 `services.conf` 配置。我们已经修复了 XFCE/Openbox 的会话竞争问题。如果仍出现，请重启容器。

**Q: Chrome 启动崩溃？**
A: 请检查 `docker-compose.yml` 中是否配置了 `shm_size: '2gb'`。Chrome 在 Docker 中需要较大的共享内存。

**Q: 如何在脚本中使用 Playwright？**
A: 镜像中已安装 Playwright 库，但为了减小体积，**未安装** Playwright 自带的浏览器二进制文件。请在代码中指定 Chrome 路径：
```python
browser = p.chromium.launch(
    executable_path="/usr/bin/google-chrome-stable", 
    headless=False
)
```

---

**Enjoy your ultra-fast automation! 🚀**
