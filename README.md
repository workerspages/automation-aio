# Ubuntu Automation - Selenium IDE 定时任务管理平台


一个功能强大的自动化任务管理平台，旨在通过一个现代化的 Web 界面，简化对 Selenium、Python 和 AutoKey 脚本的调度、管理和执行。[1]

该项目在一个预装了桌面环境（Xfce）、VNC 服务和主流浏览器的 Docker 容器中运行，让您不仅能安排定时任务，还能通过浏览器实时监控脚本的每一个执行步骤。[1]

[1]

## ✨ 核心功能

*   **一体化 Web 界面**:
    *   **任务管理**: 在一个直观的仪表盘上轻松添加、编辑、删除、手动触发和监控所有自动化任务。[1]
    *   **Cron 调度**: 使用 Cron 表达式灵活设置任务的执行周期，或从预设的常用时间中一键选择。[1]
    *   **用户认证**: 通过 Flask-Login 实现安全的登录认证，保护您的自动化平台。[1]

*   **多脚本支持**:
    *   **Selenium IDE**: 直接执行 `.side` 格式的脚本，无需额外转换。[1]
    *   **Python**: 支持原生 Python 脚本（`.py`），可用于任何需要 Python 环境的自动化任务。[1]
    *   **AutoKey**: 运行 `.autokey` 脚本，实现复杂的键盘和鼠标宏操作。[1]

*   **强大的反机器人检测策略**:
    *   **模拟人类行为**: 在执行 Selenium 任务时，自动模拟随机延迟，让操作看起来更像真实用户。[1]
    *   **伪装浏览器指纹**: 自动修改 `navigator.webdriver` 属性并使用常见的 `User-Agent`，有效绕过多数网站的机器人检测。[1]

*   **实时监控与通知**:
    *   **VNC 远程桌面**: 通过浏览器或 VNC 客户端连接到容器的桌面环境，实时观看脚本执行的全过程，便于调试和监控。[1]
    *   **Telegram 通知**: 任务执行完成后，可配置通过 Telegram Bot 自动发送包含执行结果（成功/失败）的消息，让您随时掌握任务状态。[1]

*   **简单部署与持久化**:
    *   **Docker Compose**: 提供 `docker-compose.yml` 文件，一键即可完成所有服务的部署。[1]
    *   **数据持久化**: 通过挂载数据卷，确保您的任务配置和脚本文件在容器重启后依然存在。[1]

## 🚀 部署指南

本项目推荐使用 `docker-compose` 进行部署，这能为您自动处理网络、数据卷和环境变量的配置。[1]

**先决条件**:
*   已安装 [Docker](https://docs.docker.com/get-docker/)
*   已安装 [Docker Compose](https://docs.docker.com/compose/install/) (对于 Docker Desktop 用户，它已包含在内)

**部署步骤**:

1.  **创建项目目录**
    在你希望存放项目的位置创建一个文件夹，例如 `ubuntu-automation`。[1]

2.  **创建 `docker-compose.yml` 文件**
    在该文件夹中，创建一个名为 `docker-compose.yml` 的文件，并将以下内容复制进去：

    ```yaml
    version: '3.8'

    services:
      ubuntu-automation:
        image: workerspages/ubuntu-automation:latest # 您也可以使用 ghcr.io/workerspages/ubuntu-automation:latest
        container_name: ubuntu-automation
        restart: unless-stopped
        ports:
          - "5000:5000" # Web UI 访问端口
          - "6901:6901" # noVNC (浏览器 VNC) 访问端口
        volumes:
          - ./data:/app/data # 持久化 SQLite 数据库和日志
          - ./scripts:/home/headless/Downloads # 存放您的自动化脚本
        environment:
          - VNC_PASSWORD=your_vnc_password # 设置 VNC 连接密码
          - ADMIN_USERNAME=admin # 设置 Web UI 管理员用户名
          - ADMIN_PASSWORD=your_admin_password # 设置 Web UI 管理员密码
          - TELEGRAM_BOT_TOKEN=your_telegram_bot_token # (可选) Telegram Bot Token
          - TELEGRAM_CHAT_ID=your_telegram_chat_id # (可选) Telegram 聊天 ID
        shm_size: '2gb' # 推荐为浏览器提供足够的共享内存
    ```

3.  **启动容器**
    在终端中，进入该项目目录，然后运行以下命令：

    ```bash
    docker-compose up -d
    ```

4.  **访问平台**
    *   **Web 管理界面**: 打开浏览器，访问 `http://<服务器IP>:5000`。  使用您在 `docker-compose.yml` 中设置的管理员用户名和密码登录。[1]
    *   **VNC 远程桌面**: 打开浏览器，访问 `http://<服务器IP>:6901`。  输入您设置的 VNC 密码即可连接。[1]

## ⚙️ 配置详解

您可以通过修改 `docker-compose.yml` 文件中的 `environment` 部分来定制您的自动化平台。[1]

| 环境变量 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `VNC_PASSWORD` | 用于连接 VNC 远程桌面的密码。 [1] **强烈建议修改**。 | `headless` |
| `ADMIN_USERNAME` | Web UI 的管理员用户名。 [1] | `admin` |
| `ADMIN_PASSWORD` | Web UI 的管理员密码。 [1] **强烈建议修改**。 | `password` |
| `TELEGRAM_BOT_TOKEN` | (可选) 您的 Telegram Bot 的 Token，用于发送任务通知。 [1] | `""` |
| `TELEGRAM_CHAT_ID` | (可选) 您的 Telegram 聊天或频道的 ID，用于接收通知。 [1] | `""` |
| `TZ` | 设置容器的时区，以确保 Cron 任务按预期时间执行。 [1] | `Asia/Shanghai` |
| `LANG`, `LANGUAGE`, `LC_ALL` | 设置系统语言为中文，并解决终端乱码问题。 [1] | `zh_CN.UTF-8` |
| `MAX_SCRIPT_TIMEOUT` | 脚本执行的最长超时时间（秒）。 [1] | `300` |
| `LOG_LEVEL` | 应用日志的级别（如 INFO, DEBUG）。 [1] | `INFO` |

## ✍️ 如何使用

1.  **上传脚本**: 将您的 `.side`, `.py` 或 `.autokey` 脚本文件放入您在本地创建的 `scripts` 文件夹中。  这些文件会自动出现在容器的 `/home/headless/Downloads` 目录。[1]
2.  **添加任务**:
    *   登录 Web UI (`http://<服务器IP>:5000`)。[1]
    *   点击 "Add New Task" 按钮。[1]
    *   在弹出的窗口中，填写任务名称，从下拉列表中选择您的脚本，然后设置一个 Cron 表达式（或使用预设值）。[1]
    *   点击 "Save Task" 保存。[1]
3.  **管理任务**:
    *   **手动执行**: 点击任务旁的 "▶️" (Run Now) 按钮可立即执行该任务。[1]
    *   **监控**: 您可以通过 VNC 实时观察脚本执行情况。[1]
    *   **查看日志**: 任务的输出和错误日志会保存在 `data/automation.log` 文件中。[1]

## 👨‍💻 致开发者

该项目旨在提供一个灵活且易于扩展的自动化框架。  欢迎您 Fork、修改或提出建议。  如果您发现了 Bug 或有任何好的想法，请随时在 GitHub 上提交 Issues 或 Pull Requests。[1]

**项目地址**: [https://github.com/workerspages/ubuntu-automation](https://github.com/workerspages/ubuntu-automation)

---

[1](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/104051761/f19527bc-37e7-43a6-b9f6-5ac0f2f129dc/paste.txt)
