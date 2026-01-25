# ===================================================================
# AutoKey NodeLoc签到脚本 (Chrome版 + AI 验证码识别)
# ===================================================================
# 注意：此脚本在 AutoKey 环境下运行，但需要额外导入系统 Python 库。
# 确保 /app/web-app 目录在 PYTHONPATH 中，或者手动添加 path。

import time
import random
import subprocess
import sys
import os

# === AI 模块导入 ===
# 在 Docker 容器中，web-app 代码在 /app/web-app
sys.path.append('/app/web-app') 
try:
    from utils.ai_solver import AISolver
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    # dialog.info_dialog("AI Warning", "AI 模块导入失败，验证码功能将不可用")

# -------------------------------------------------------------------

# 辅助函数：执行 shell 命令
def sh(cmd):
    subprocess.run(cmd, shell=True, check=False)

# 辅助函数：模拟打字
def type_like_human(text):
    for c in text:
        keyboard.send_keys(c)
        time.sleep(random.uniform(0.05, 0.15))

# 辅助函数：坐标点击
def click_xy(x, y, delay=1.0):
    sh(f"xdotool mousemove {x} {y}")
    time.sleep(0.2)
    sh(f"xdotool click 1")
    time.sleep(delay)

# 辅助函数：截图指定区域 (需要系统安装 scrot 或 import -window root)
# 这里简化为全屏截图，然后让 AI 找图中的位置。
# 如果需要从全屏坐标换算，AI 返回的通常是绝对坐标（如果是让 AI 看全屏图的话）
def capture_screen_and_solve_captcha():
    if not AI_AVAILABLE:
        return False
    
    screenshot_path = "/tmp/autokey_screen.png"
    # 全屏截图
    sh(f"scrot -o {screenshot_path}")
    
    if not os.path.exists(screenshot_path):
        return False

    solver = AISolver()
    # 提示词微调：告诉 AI 这是全屏截图，寻找滑动验证码缺口的绝对屏幕坐标
    prompt = "这是一张全屏截图。请找到屏幕中央附近的滑动验证码缺口。请返回缺口中心在整个屏幕上的绝对像素坐标 (X, Y)，以 JSON 格式返回，例如 {'x': 123, 'y': 456}。只返回 JSON。"
    
    # 注意：AISolver 默认只返回一个数字 X。我们需要稍微修改一下调用逻辑或者 prompt
    # 这里为了演示简单，我们假设滑块也是水平滑动的，只需要 X 坐标，Y 坐标通常和滑块按钮 Y 一致
    # 或者我们使用内置的 identify_gap
    
    gap_x = solver.identify_gap(screenshot_path, prompt_text="这张图里有个滑动拼图验证码。请告诉我缺口中心的 X 轴像素坐标（绝对坐标）。只返回数字。")
    
    return gap_x

# ------- 账号密码 -------
my_username = "xxxxxxxxxx"
my_password = "xxxxxxxxxxxxxx"

try:
    # 1. 启动 Chrome
    system.exec_command("google-chrome --start-maximized", getOutput=False)
    time.sleep(5) 

    # 2. 激活窗口
    if window.wait_for_exist(".*Chrome.*", timeOut=10):
        window.activate(".*Chrome.*")
        time.sleep(1)
    else:
        raise Exception("Chrome 启动超时")

    # 3. 输入网址
    keyboard.send_keys("<ctrl>+l")
    time.sleep(0.5)
    
    login_url = "https://www.nodeloc.com/login"
    keyboard.send_keys(login_url)
    time.sleep(0.5)
    keyboard.send_keys("<enter>")
    
    time.sleep(10)

    # 4. 输入账号
    username_box_X = 441
    username_box_Y = 372
    click_xy(username_box_X, username_box_Y, delay=0.5)
    keyboard.send_keys("<ctrl>+a")
    keyboard.send_keys("<backspace>")
    type_like_human(my_username)

    # 5. 输入密码
    password_box_X = 458
    password_box_Y = 448
    click_xy(password_box_X, password_box_Y, delay=0.5)
    keyboard.send_keys("<ctrl>+a")
    keyboard.send_keys("<backspace>")
    type_like_human(my_password)

    # 6. 人机验证 (AI 介入)
    # 假设验证码就在屏幕中间，或者你需要先点击某个点触发它
    # robot_button_X = 461
    # robot_button_Y = 584
    # click_xy(robot_button_X, robot_button_Y, delay=3)
    
    # === AI 处理逻辑 ===
    # 1. 截图并识别
    # 注意：AutoKey 是系统级操作，它可以截取整个屏幕
    detected_x = capture_screen_and_solve_captcha()
    
    if detected_x:
        # print(f"AI Detected X: {detected_x}")
        
        # 2. 找到滑块起始按钮的位置（这个通常是固定的，你需要事先量好）
        slider_start_x = 460 # 假设滑块起始 X
        slider_start_y = 600 # 假设滑块起始 Y
        
        # 3. 计算拖动距离
        # 如果 AI 返回的是绝对坐标 X，那么 drag_distance = detected_x - slider_start_x
        # 请根据 AI 返回值的实际含义调整（是距离还是坐标）
        drag_distance = detected_x - slider_start_x
        
        if drag_distance > 0:
            # 4. 执行拖动
            sh(f"xdotool mousemove {slider_start_x} {slider_start_y}")
            time.sleep(0.2)
            sh(f"xdotool mousedown 1")
            time.sleep(0.2)
            
            # 使用 xdotool 模拟平滑拖动 (分段移动)
            current_x = slider_start_x
            target_x = slider_start_x + drag_distance
            step = 10
            while current_x < target_x:
                current_x += step
                if current_x > target_x: current_x = target_x
                # 加一点随机 Y 抖动
                rand_y = slider_start_y + random.randint(-1, 1)
                sh(f"xdotool mousemove {current_x} {rand_y}")
                time.sleep(random.uniform(0.01, 0.03))
            
            time.sleep(0.5)
            sh(f"xdotool mouseup 1")
            time.sleep(2)
    # ===================

    # 7. 点击登录按钮
    login_1_button_X = 493
    login_1_button_Y = 514
    click_xy(login_1_button_X, login_1_button_Y, delay=8)
    
    # 8. 点击主页签到入口
    main_page_check_in_link_X = 1194
    main_page_check_in_link_Y = 147
    click_xy(main_page_check_in_link_X, main_page_check_in_link_Y, delay=5)

    # 10. 关闭
    keyboard.send_keys("<ctrl>+w") 

except Exception as e:
    pass
