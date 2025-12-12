
# 🤖 Ubuntu Automation AIO Platform

**全能型 Ubuntu 自动化/爬虫容器平台**

[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web_UI-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Supported-2EAD33?style=flat&logo=playwright&logoColor=white)](https://playwright.dev/)

**签到**、**GUI 宏操作**，还是**定时截图监控**，这个项目都能满足，并且可以通过 Web 界面轻松管理和调度。

---

## ✨ 核心功能

### 🖥️ 可视化与交互
*   **Web 管理面板**：基于 Flask 开发，支持任务的添加、编辑、删除和**立即执行**。
*   **VNC 远程桌面**：内置 NoVNC，直接在浏览器中查看。


这是一个基于 Docker 的开箱即用自动化平台。它集成了图形化桌面 (自动化脚本的实时执行过程（所见即所得）。
*   **异步任务执行**：点击执行后后台运行，不会卡顿网页，支持长时间运行的任务。

### 🚀 多引擎支持
1.  **Selenium IDE** (XFCE/VNC)、Web 管理面板和多种主流自动化工具。你可以在 Web 界面上管理定时任务，并在 VNC 中实时观看脚本的执行过程。

---

## ✨ 核心功能

1.  **可视化的 Web 管理面板**：
    *   基于 Flask 开发，支持任务的增删改查。
    *   支持 **Cron 表达式** 定时调度（精确到分钟）。
    *   **异步执行机制**：任务后台运行，不会导致网页`.side`)：
    *   直接运行录制的脚本，无需导出代码。
    *   **内置反检测**：自动隐藏 WebDriver 特征，模拟人类操作延迟，通过大多数反爬虫检测。
2.  **Playwright** (`.py`)：
    *   预装 Python 环境和浏览器。
    *   支持 `headless=False` 卡顿或超时。
    *   支持立即手动触发执行。

2.  **集成的远程桌面 (NoVNC)**：
    *   内置 XFCE4 轻量级桌面环境。
    *   直接通过浏览器访问 VNC，无需安装客户端。
    *   预装中文支持（字体、输入法环境模式，在 VNC 中实时显示操作。
3.  **Actiona** (`.ascr`)：
    *   **零代码**图形化自动化工具。
    *   支持找图点击、模拟鼠标键盘、窗口控制，适合非网页类的桌面自动化。
4.  **AutoKey** (`.autokey`)：
    *   强大的键盘宏工具，支持 Python 脚本控制系统级按键。

### 🔔 通知系统
*   **Telegram 推）。

3.  **四大自动化引擎支持**：
    *   **Selenium IDE (.side)**：直接运行录制好的 `.side` 文件，内置反爬虫检测机制。
    *   **Playwright (Python)**：支持现代 Web 自动化，已预装 Chromium 浏览器。
    *   **Actiona (.ascr)**：图形送**：任务执行结束后（无论成功或失败），自动发送包含详细日志的 Telegram 消息。

---

## 🛠️ 部署指南

### 前置要求
*   安装 [Docker](https://docs.docker.com/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/)。

### 1. 获取项目
创建项目目录并将文件放入结构中：
```text
automation/
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── web-app/          # Web 源码
├── scripts/          # 执行器源码
└── addons/           # (可选) 插件文件
```

### 2. 启动容器
在项目根目录下运行：

```bash
docker-compose up -d --build
```

### 3. 访问服务
*   **Web 管理面板**: `http://localhost:5000`
    *   默认账号: `admin`
    *   默认密码: `admin123`
*   **VNC 远程桌面**: 登录面板后，点击右上角的 **"远程桌面"** 按钮。
    *   VNC 密码: `admin` (可在环境变量中修改)

---

## ⚙️ 配置说明 (`docker-compose.yml`)

你可以通过修改环境变量来定制你的容器：

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `ADMIN_USERNAME` | `admin` | Web 面板登录用户名 |
| `ADMIN_PASSWORD` | `admin123` | Web 面板登录密码 |
| `VNC_PW` | `admin` | VNC 连接密码 |
| `VNC_RESOLUTION` | `1360x768` | 远程桌面的分辨率 (建议保持此分辨率以匹配脚本坐标) |
| `TELEGRAM_BOT_TOKEN` | - | (可选) 你的 Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | - | (可选) 接收通知的 Chat ID |
| `TZ` | `Asia/Shanghai` | 容器时区设置 |

---

## 📖 使用教程：如何添加任务

所有脚本文件都需要放在宿主机的 `./Downloads` 目录中（该目录已映射到容器内）。

### 🟢 场景 1：运行 Playwright (Python) 脚本
适合复杂的网页交互和数据抓取。

1.  **编写脚本**：在本地编写 Python 脚本（例如 `baidu_test.py`）。
    *   *提示*：代码中使用 `headless=False` 可以在 VNC 中看到界面。
    *   *提示*：文件名不要叫 `playwright.py`，否则会报错。
2.  **上传**：将 `.py` 文件放入宿主机的 `Downloads` 目录。
3.  **添加任务**：
    *   进入 Web 面板 -> **化自动化工具，支持模拟鼠标点击、图像识别。
    *   **AutoKey (.autokey)**：Linux 下的键盘宏工具，支持桌面级热键和文本替换。

4.  **通知系统**：
    *   集成 **Telegram Bot**，任务成功或失败都会发送详细日志通知。

5.  **企业级稳定性**：
    *   Chrome 浏览器经过特殊修改，彻底解决 Docker 内 Crash 问题。
    *   解决 AutoKey D-Bus 通信难题，完美支持 GUI 自动化。
    *   Playwright 浏览器路径全局共享，权限无忧。

---

## 🚀 快速部署指南

### 1. 环境要求
*   Docker
*   Docker Compose

### 2. 目录结构准备
请确保你的本地目录包含以下文件结构：
```text
project-root/
├── docker-compose.yml   # 容器编排文件
├── Dockerfile           # 镜像构建文件
├── nginx.conf           # Nginx 配置文件
├── web-app/             # Web 源码目录
│   ├── app.py           # 核心后端
│   ├── templates/       # 前端页面
│   ├── static/          # 静态资源
│   └── requirements.txt # Python依赖
├── scripts/             # 脚本目录
│   └── task_executor.py # 执行器逻辑
└── addons/              # 插件目录 (可选)
```

### 3. 启动容器
在项目根目录下运行：

```bash
# 构建并后台启动
docker-compose up -d --build
```

### 4. 访问服务
*   **Web 管理面板**: `http://localhost:5000`
    *   默认账号: `admin`
    *   默认密码: `admin123` (可在 `docker-compose.yml` 中修改)
*   **VNC 远程桌面**:
    *   登录面板后，点击顶部导航栏的 **"远程桌面"** 按钮。
    *   VNC 密码: `admin`

---

## ⚙️ 配置说明 (docker-compose.yml)

你可以通过修改 `docker-compose.yml` 中的环境变量来调整配置：

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `ADMIN_USERNAME` | `admin` | Web 面板登录用户名 |
| `ADMIN_PASSWORD` | `admin123` | Web 面板登录密码 |
| `VNC_PW` | `admin` | VNC 连接密码 |
| `VNC_RESOLUTION` | `1360x768` | 远程桌面分辨率 |
| `TELEGRAM_BOT_TOKEN`| - | (可选) Telegram 机器人的 Token |
| `TELEGRAM_CHAT_ID` | - | (可选) 接收通知的 Chat ID |
| `TZ` | `Asia/Shanghai` | 容器时区 |

---

## 📖 脚本使用教程添加任务**。
    *   选择脚本：`baidu_test.py`。
    *   设置 Cron 表达式（如 `0 9 * * *` 每天9点）。
    *   保存并点击“ (新手必读)

所有脚本文件都需要放入宿主机的 `./Downloads` 目录（该目录映射到了立即执行”测试。

### 🔵 场景 2：运行 Selenium IDE 脚本
适合快速录制简单的网页操作，无需写代码。

1.  **录制**：在本地 Chrome/Firefox 安装 Selenium IDE 插件，录制操作并保存为 `.side` 文件。
    *   *建议*：录制时调整浏览器窗口大小约为 1360x768，以匹配容器环境。
2.  **上传**：将 `.side` 文件放入 `Downloads` 目录。
3.  **添加任务**：Web 面板选择该文件即可容器内的 `/home/headless/Downloads`）。

### 1. 使用 Playwright (Python)
*   **编写**：在本地编写 Python 脚本（例如 `baidu_test.py`）。
    *   **注意**：代码中请设置 `headless=False` 以便在 VNC 中看到界面。
*   **上传**：将。系统会自动应用反爬虫策略执行它。

### 🟣 场景 3：运行 Actiona 脚本 (图形化)
适合需要“找图点击”或控制非浏览器软件的场景。

1.  ** `.py` 文件放入 `./Downloads` 目录。
*   **运行**：在 Web 面板添加任务，选择该脚本，设置定时即可。

### 2. 使用 Selenium IDE (.side)
*   **录制**：在本地电脑的 Chrome/Firefox 安装 Selenium IDE 插件，录制操作并保存为 `.side` 文件。
    *   *建议*：录制时将浏览器窗口大小调整为约 1360x768，以匹配容器分辨率。
*   **上传**：将 `.side` 文件放入 `./Downloads` 目录。
*   **运行**：在 Web 面板选择该文件。平台会自动解析并在无插件的纯进入 VNC**：在 Web 面板打开远程桌面。
2.  **打开软件**：在桌面左上角菜单 -> Accessories -> Actiona。
3.  **制作脚本**：拖拽动作（如 Click, Write text），制作完成后**保存到** `/home/headless/Downloads/`，后缀名为 `.ascr`。
4.  **添加净 Chrome 中复现操作。

### 3. 使用 Actiona (图形化动作)
Actiona 类似于按键精灵，适合非 Web 类的桌面自动化。
*   **制作**：
    1.  进入 VNC 桌面。
    2.  打开终端输入 `actiona` 启动软件。
    3.  拖拽指令任务**：Web 面板选择该 `.ascr` 文件。

### 🟠 场景 4：运行 AutoKey 脚本
适合全局键盘宏。

1.  **进入 VNC**：打开 AutoKey 软件。
2.  **新建制作脚本，**保存时后缀必须为 `.ascr`**。
    4.  保存路径必须是 `/home/headless/Downloads/`。
*   **运行**：Web 面板会自动识别 `.ascr脚本**：在软件内新建脚本（例如命名为 `mylogin`），编写 Python 代码并保存。
3.  **创建触发器**：在宿主机 `Downloads` 目录下创建一个**空文件**，命名必须与脚本名一致，后缀` 文件，添加任务即可。

### 4. 使用 AutoKey (键盘宏)
AutoKey 的逻辑比较特殊，请严格按照以下步骤：
1.  **进入 VNC**，打开 AutoKey 软件（为 `.autokey`（例如 `mylogin.autokey`）。
4.  **添加任务**：Web 面板选择 随系统自启）。
2.  在软件内 **新建脚本**，取名为 `demo`，编写代码并`mylogin.autokey`。

---

## 📂 项目结构概览 (开发者参考)

```text
.
├── Dockerfile              # 构建镜像，集成 Chrome, VNC, Flask 等
├── docker-compose.yml      **保存**。
3.  **回到宿主机**，在 `./Downloads` 目录下创建一个**空的**文件，命名为 `demo.autokey`。
    *   *原理*：Web 面板扫描到 `demo.autokey`，会发送指令让 AutoKey 运行它内部名为 `demo` 的脚本。

# 容器编排
├── nginx.conf              # 反向代理，处理 HTTP 和 WebSocket (NoVNC)
├── web-app/
│   ├── app.py              # Flask 后端核心，包含任务调度和执行逻辑
│   ├── templates---

## 🛠️ 开发者信息

如果你想对项目进行二次开发，以下是核心文件说明：

*   **`Dockerfile/          # 前端 HTML
│   └── static/             # 前端 CSS/JS
└── scripts/
    ├── entrypoint.`**:
    *   基于 Ubuntu 22.04。
    *   处理了 Chrome 沙盒权限sh       # 容器启动脚本 (权限修正、服务启动)
    └── task_executor.py    # Selenium 解析 (`--no-sandbox` wrapper)。
    *   配置了 AutoKey 的 D-Bus 环境变量导出，确保后台器 & 通用通知发送模块
```

## ❓ 常见问题 (FAQ)

**Q: 点击“立即执行”后，网页提示成功，但 VNC 里没反应？**
A:
1.  检查能控制前台。
    *   安装了 Playwright 依赖及浏览器到 `/opt/playwright` 公共目录。

*   **`web-app/app.py`**:
    *   Flask 后端 Web 面板日志，看是否有报错。
2.  确认脚本文件已放入 `Downloads` 目录。
3.  如果是 Playwright，检查代码里是否加了 `headless=False`。
4.  如果是 AutoKey，确认。
    *   `run_task_now`: 使用 `scheduler.add_job` 实现了异步非阻塞执行。
    *   `get_desktop_env()`: 动态读取 VNC 的环境变量，这是 GUI 自动化能运行的关键。

*   **`scripts/task_executor.py`**:
    *    AutoKey 软件在 VNC 里是启动状态（系统托盘有图标）。

**Q: 为什么 Selenium包含 Selenium IDE 文件的解析引擎。
    *   封装了 `send_telegram_notification` 函数，统一处理 IDE 插件在 Chrome 里无法使用？**
A: Chrome 已禁用 Manifest V2 扩展。但这**所有类型的通知。

---

## ❓ 常见问题 (FAQ)

**Q: 为什么我看不到 VNC 里的不影响任务执行**。我们的平台是通过 Python 后端直接解析 `.side` 文件并驱动浏览器的，并不浏览器窗口？**
A: 1. 检查脚本是否报错（查看 Web 面板日志）。2. 确保依赖浏览器内的插件。

**Q: 保存任务时提示 "readonly database"？**
A: 这是权限问题。请确保使用了脚本中包含 `headless=False`。3. 确保 `DISPLAY=:1` 环境变量正确传递（目前的 `app.py` 已自动处理）。

**Q: 为什么 AutoKey 脚本执行没反应？**
A: 必须最新的 `Dockerfile` 和 `entrypoint.sh`，我们在启动时会自动执行 `chown` 修复数据库权限。重启容器通常能解决。

---

## 🤝 贡献与支持

本项目旨在简化 Linux 下的 GUI 自动化部署。如果你发现 Bug先在 VNC 的 AutoKey 软件界面里创建并保存同名脚本。Downloads 里的 `.autokey` 只是一个触发器文件。

**Q: 任务执行显示成功，但没有 Telegram 通知？**
A: 请 或有新功能建议，欢迎提交 Issue 或 Pull Request！

**License**: MIT
