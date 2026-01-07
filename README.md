
# 🤖 Automation AIO Platform

[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()
[![Database](https://img.shields.io/badge/Database-SQLite%20%7C%20MariaDB-orange)]()

**Ubuntu Automation AIO (All-In-One)** 是一个基于 Docker 的全能自动化工控平台。它集成了一个完整的 Ubuntu 桌面环境、强大的 Web 管理面板、可视化任务调度器以及多种自动化工具（Selenium, Playwright, AutoKey, Actiona）。

该项目旨在为开发者和自动化爱好者提供一个**开箱即用、防检测、支持远程管理**的自动化执行环境。

---

## ✨ 核心功能

### 🖥️ 完整的桌面环境
- **XFCE4 桌面**: 轻量级、稳定。
- **NoVNC**: 直接在浏览器中访问远程桌面，无需安装客户端。
- **中文字体支持**: 内置文泉驿微米黑等字体，解决中文乱码问题。
- **输入法支持**: 预装中文输入法环境。

### 🤖 强大的自动化工具链
- **浏览器自动化**:
  - **Chrome**: 预置防检测配置 (Anti-bot)，隐藏 `navigator.webdriver` 特征。
  - **Firefox**: 强制使用 `.deb` 版本（非 Snap），确保 Selenium/Playwright 兼容性。
  - **Playwright & Selenium**: 环境已预装，开箱即用。
- **桌面自动化**:
  - **AutoKey**: 键盘/鼠标宏录制与脚本执行。
  - **Actiona**: 可视化自动化流程设计工具。

### 📅 智能任务调度 (Web 面板)
- **可视化管理**: 通过 Web 界面添加、编辑、删除任务。
- **Cron 调度**: 支持标准的 Cron 表达式（如 `0 9 * * *`）。
- **🎲 拟人化随机调度**: 设定时间段（如 `09:00 - 10:00`），系统会在此范围内**随机选择时间点**执行任务，有效规避风控检测。

### 🔌 数据持久化 (New!)
- **双模数据库支持**:
  - **SQLite (默认)**: 零配置，开箱即用，数据存储在本地文件。
  - **MariaDB / MySQL**: 支持连接外部数据库，适合集群部署或数据量较大的场景。只需配置环境变量即可自动切换。

### 📝 在线脚本开发
- **在线代码编辑器**: 集成 CodeMirror，支持 Python 语法高亮。
- **直接调试**: 在网页上编写代码 -> 保存 -> 立即运行，告别繁琐的文件上传步骤。
- **AutoKey 无缝集成**: 在网页端编写 AutoKey 脚本，VNC 桌面内即时生效。

### 📢 多渠道通知
- **Telegram Bot**: 任务成功或失败时推送到 TG。
- **Email 通知**: 支持 SMTP 邮件发送执行报告。

### 🌐 内网穿透
- **Cloudflare Tunnel**: 内置支持，只需一个 Token，无需公网 IP 即可远程访问。

---

## 🛠️ 部署指南

### 前置条件
- 安装了 [Docker](https://docs.docker.com/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/) 的服务器（Linux/Windows/Mac）。

### 1. 准备目录
在服务器上创建一个目录用于存放项目文件：

```bash
mkdir -p ubuntu-automation/data ubuntu-automation/logs ubuntu-automation/Downloads
cd ubuntu-automation
```

### 2. 创建 `docker-compose.yml`
新建文件并粘贴以下内容：

```yaml
version: '3.8'

services:
  automation-aio:
    image: ghcr.io/workerspages/automation-aio:mariadb
    container_name: automation-aio
    ports:
      - "5000:5000"
    environment:
      - VNC_PW=admin
      - SECRET_KEY=your-secret-key-change-this
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=admin123
      
      # === 数据库配置 (可选：连接外部 MariaDB) ===
      # 如果留空或注释，默认使用容器内置的 SQLite
      - MARIADB_HOST=           # 例如: 192.168.1.100
      - MARIADB_PORT=3306
      - MARIADB_USER=root
      - MARIADB_PASSWORD=root
      - MARIADB_DB=automation_aio
      # =======================================

      # Telegram 通知配置
      - TELEGRAM_BOT_TOKEN=
      - TELEGRAM_CHAT_ID=

      # === 邮件通知配置 ===
      - ENABLE_EMAIL_NOTIFY=true
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USER=your_email@gmail.com
      - SMTP_PASSWORD=your_app_password
      - EMAIL_FROM=your_email@gmail.com
      - EMAIL_TO=receiver@example.com
      
      - ENABLE_CLOUDFLARE_TUNNEL=false
      - CLOUDFLARE_TUNNEL_TOKEN=xxxxxxxxx
      - DISPLAY=:1
    volumes:
      - ./Downloads:/home/headless/Downloads
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    shm_size: '2gb'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 3. 启动服务

```bash
docker-compose up -d
```

等待几秒钟，容器初始化完成后即可访问。

---

## 📖 使用指南

### 1. 访问控制台
打开浏览器访问 `http://<服务器IP>:5000`。
- **默认账号**: `admin`
- **默认密码**: `admin123`

### 2. 远程桌面 (VNC)
点击右上角的 **"🖥️ 远程桌面"** 按钮，或者直接访问 `http://<IP>:5000/vnc/vnc.html`。
- **连接密码**: 你在环境变量 `VNC_PW` 中设置的值（默认 `admin`）。

### 3. 脚本管理与开发
点击导航栏的 **"📂 脚本管理"** 按钮：
*   **Downloads 目录**: 存放 Selenium/Playwright 等常规 Python 脚本。
*   **AutoKey 目录**: 存放 AutoKey 的系统级自动化脚本。
*   **在线编辑**: 点击文件名右侧的 "✎ 编辑"，在弹出的代码编辑器中直接修改并保存。

### 4. 添加任务
点击 **"+ 新建任务"**：
1.  **任务名称**: 起个名字。
2.  **选择脚本**: 从下拉菜单选择刚刚编写的脚本。
3.  **调度模式**:
    *   **常规 Cron**: 传统的定时执行（如每天 9 点：`0 9 * * *`）。
    *   **🎲 随机时间段**: 选择开始时间（如 10:00）和结束时间（如 10:05）。系统会计算差值，并在每天的这个窗口期内**随机延迟**执行，模拟真人操作的不确定性。

---

## ⚙️ 详细配置参数

| 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `TZ` | Asia/Shanghai | 系统时区，影响 Cron 调度时间。 |
| `VNC_PW` | admin | VNC 远程连接密码。 |
| `ADMIN_USERNAME` | admin | Web 面板登录用户名。 |
| `ADMIN_PASSWORD` | admin123 | Web 面板登录密码。 |
| **`MARIADB_HOST`** | (空) | **新增**：MariaDB/MySQL 主机地址。如果设置此项，系统将切换到 MariaDB 模式。 |
| `MARIADB_PORT` | 3306 | MariaDB 端口。 |
| `MARIADB_USER` | root | 数据库用户名。 |
| `MARIADB_PASSWORD` | (空) | 数据库密码。 |
| `MARIADB_DB` | automation | 数据库名称 (首次连接会自动建表)。 |
| `ENABLE_EMAIL_NOTIFY`| false | 是否启用邮件通知。 |
| `SMTP_USER` | - | 发件人邮箱账号。 |
| `SMTP_PASSWORD` | - | 邮箱授权码/应用密码（非登录密码）。 |
| `ENABLE_CLOUDFLARE_TUNNEL` | false | 是否启用 Cloudflare 内网穿透。 |
| `CLOUDFLARE_TUNNEL_TOKEN` | - | Cloudflare Tunnel 的 Token。 |

---

## 📁 目录结构说明

```text
/ubuntu-automation
├── data/           # 存放 tasks.db (SQLite模式下) 和 automation.log (运行日志)
├── logs/           # 存放 Nginx, VNC, Supervisor 等系统日志
├── Downloads/      # 映射到容器内的 /home/headless/Downloads，存放常规脚本
└── docker-compose.yml
```

---

## 👨‍💻 开发者信息

如果你想自己构建镜像或修改源码：

1.  **克隆项目**:
    ```bash
    git clone https://github.com/workerspages/automation-aio.git
    cd ubuntu-automation
    ```

2.  **修改代码**:
    *   `Dockerfile`: 系统环境构建。
    *   `web-app/`: Flask 后端与前端代码。
    *   `scripts/`: 启动脚本与辅助工具。

3.  **本地构建**:
    ```bash
    docker-compose build
    docker-compose up -d
    ```

### 常见问题 (FAQ)

**Q: 如何从 SQLite 迁移到 MariaDB？**
A: 目前系统会在启动时检测 `MARIADB_HOST`。如果配置了该变量，系统将自动连接 MariaDB 并初始化空表。**注意：** 原 SQLite 中的任务数据**不会**自动迁移到 MariaDB，你需要手动重新添加任务或自行编写数据迁移脚本。

**Q: 启动后访问 5000 端口报 "502 Bad Gateway"?**
A: 这通常是因为容器内的 VNC Server 还没完全启动，导致 WebApp 等待依赖文件。请等待 1-2 分钟。如果一直报错，请检查日志：`docker logs ubuntu-automation`。

**Q: Selenium 报错 "DevToolsActivePort file doesn't exist"?**
A: 请确保 `docker-compose.yml` 中配置了 `shm_size: '2gb'`。Chrome 需要较大的共享内存。

---

**Enjoy your automation! 🚀**
