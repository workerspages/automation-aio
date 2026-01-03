
# 🤖 Ubuntu Automation AIO (Anti-Detect Edition)

[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![Anti-Bot](https://img.shields.io/badge/Anti--Bot-Undetected-red.svg)](https://github.com/ultramarine-linux/undetected-chromedriver)
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

**Ubuntu Automation AIO** 是一个基于 Docker 的全能自动化工控平台。它不仅仅是一个远程桌面环境，更是一个专为**绕过反爬虫检测**设计的自动化堡垒。

该版本集成了 **Undetected Chromedriver (UC)**、**Stealth Playwright** 以及 **拟人化鼠标算法**，能够有效通过 Cloudflare、Akamai 等 WAF 的机器人验证。

---

## ✨ 核心特性

### 🛡️ 顶级抗检测能力 (Anti-Detect)
- **Undetected Chromedriver (UC)**: 内置深度修改版的 Chrome 驱动，自动修补底层二进制文件，彻底移除 `navigator.webdriver` 等数十种自动化特征。
- **Playwright Stealth**: 预装 Stealth 插件，掩盖 Headless 浏览器的指纹特征。
- **指纹混淆**: 自动处理 WebGL、Canvas 指纹和 User-Agent，使其看起来像真实的普通用户浏览器。

### 🖱️ 拟人化交互 (Human-like)
- **贝塞尔曲线鼠标轨迹**: 拒绝机械的“瞬移”点击。系统利用 `numpy` 计算贝塞尔曲线，模拟人类手部移动时的弧度、加速和减速过程。
- **随机化延迟**: 打字、点击、滚动均包含符合人类生理特征的随机微小延迟，避开基于时间统计的行为分析。

### 🖥️ 完整的桌面与工控
- **XFCE4 + NoVNC**: 浏览器直接访问远程桌面，内置中文环境与输入法。
- **AutoKey 集成**: 支持系统级键盘鼠标宏录制，可跨软件执行自动化（不仅仅是浏览器）。
- **Actiona**: 可视化拖拽式自动化流程设计器。

### 📅 智能调度与管理
- **Web 控制面板**: 可视化管理脚本、查看日志、监控状态。
- **🎲 随机时间窗调度**: 设定如 `09:00 - 10:00`，系统会在该窗口内**随机选择时间点**执行任务，模拟真人不规律的上线时间。
- **双模数据库**: 默认 SQLite 零配置启动，支持一键切换外部 MariaDB/MySQL。

---

## 🛠️ 部署指南

### 1. 创建项目目录
```bash
mkdir -p ubuntu-automation/data ubuntu-automation/logs ubuntu-automation/Downloads
cd ubuntu-automation
```

### 2. 创建 `docker-compose.yml`
```yaml
version: '3.8'

services:
  ubuntu-automation:
    image: ghcr.io/workerspages/automation-aio:main-mariadb-20260103
    container_name: ubuntu-automation
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
      - CLOUDFLARE_TUNNEL_TOKEN=
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
启动后访问 `http://<服务器IP>:5000`。

---

## 📖 使用指南

### 1. 快速创建抗检测脚本
在 Web 面板点击 **"📂 脚本管理"** -> **"+ 新建脚本"**。
编辑器会自动填充一份 **Anti-Detection Template** 代码：
- 自动引入 `undetected_chromedriver`。
- 自动配置防检测参数。
- 包含随机等待和截图示例。

你只需填入你的业务逻辑（`driver.get(...)`）即可，系统会自动处理底层的驱动修补。

### 2. 运行 Selenium IDE 录制文件
1. 使用 Chrome 插件 **Selenium IDE** 录制你的操作，保存为 `.side` 文件。
2. 将文件上传到 Web 面板（或直接放入 `Downloads` 目录）。
3. 创建任务并运行。
   > **注意**: 系统会自动接管 `.side` 文件中的 `click` 和 `type` 命令，强制转换为**贝塞尔曲线拟人移动**操作，无需你手动修改录制文件。

### 3. AutoKey 桌面自动化
如果需要操作非网页应用（如桌面客户端）：
1. 在脚本管理器切换到 **AutoKey** 标签页。
2. 新建脚本，使用 Python 编写键盘宏。
3. 示例：
   ```python
   # 模拟真人打字
   human_type("Hello World") 
   keyboard.send_key("<enter>")
   ```

---

## ⚙️ 进阶配置

| 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `VNC_RESOLUTION` | 1360x768 | 远程桌面的分辨率。 |
| `MAX_SCRIPT_TIMEOUT` | 300 | 脚本最大运行秒数，超时自动杀进程。 |
| `CHROME_BINARY` | /usr/bin/google-chrome-stable | 指定 Chrome 路径（配合 UC 使用）。 |
| `ENABLE_CLOUDFLARE_TUNNEL` | false | 是否启用内网穿透。 |

---

## 📁 目录结构

```text
/ubuntu-automation
├── data/           # 数据库 (tasks.db) 和 运行截图/日志
├── logs/           # 系统服务日志
├── Downloads/      # 你的 Python/Side 脚本存放处
└── docker-compose.yml
```

---

## 常见问题 (FAQ)

**Q: 为什么日志里提示 "Patching chromedriver..."?**
A: 这是 `undetected_chromedriver` 正在工作。它会在每次启动时检查并修补驱动文件，以确保特征码被移除。这是正常且必要的步骤。

**Q: 为什么鼠标点击比平时慢？**
A: 这是有意为之的。为了模拟真人，我们将瞬间的 `.click()` 替换为了“移动 -> 减速 -> 停顿 -> 点击”的过程，这虽然牺牲了一点速度，但极大提高了账号安全性。

**Q: Docker 内 Chrome 崩溃或启动失败？**
A: 请务必检查 `docker-compose.yml` 中是否配置了 **`shm_size: '2gb'`**。现代浏览器在容器中需要较大的共享内存空间。

---

**Enjoy your stealth automation! 🚀**
