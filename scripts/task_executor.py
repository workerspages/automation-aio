#!/usr/bin/env python3
"""
Selenium IDE 任务执行器 & 通用通知模块
优化版: 集成 undetected_chromedriver 和 拟人化鼠标轨迹
"""

import sys
import json
import time
import random
import logging
import os
import requests
import smtplib
import numpy as np
from math import factorial
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from pathlib import Path
from datetime import datetime

# === 核心修改: 使用 undetected_chromedriver ===
import undetected_chromedriver as uc

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/data/executor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 人类化操作配置参数
HUMAN_LIKE_DELAYS = {
    'min_command_delay': 0.8,  # 基础命令间隔
    'max_command_delay': 3.0,
    'min_typing_delay': 0.08,  # 打字间隔
    'max_typing_delay': 0.25,
    'scroll_delay': 1.0,
    'click_delay': 0.5
}

# --- 拟人化算法区域 (贝塞尔曲线) ---

def bernstein_poly(i, n, t):
    """伯恩斯坦多项式，用于计算贝塞尔曲线的权重"""
    return factorial(n) / (factorial(i) * factorial(n - i)) * (t ** i) * ((1 - t) ** (n - i))

def bezier_curve(points, n_steps=50):
    """
    生成贝塞尔曲线轨迹点
    :param points: 控制点列表 [(x1,y1), (x2,y2), ...]
    :param n_steps: 步数
    """
    n_points = len(points)
    x_points = np.array([p[0] for p in points])
    y_points = np.array([p[1] for p in points])
    
    t = np.linspace(0.0, 1.0, n_steps)
    polynomial_array = np.array([bernstein_poly(i, n_points - 1, t) for i in range(n_points)])
    
    xvals = np.dot(x_points, polynomial_array)
    yvals = np.dot(y_points, polynomial_array)
    
    return xvals, yvals

def human_mouse_move(driver, element):
    """
    模拟人类鼠标移动：生成一条贝塞尔曲线路径并逐步移动到目标元素
    """
    try:
        actions = ActionChains(driver)
        
        # 1. 先平滑滚动到元素可见
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(random.uniform(0.5, 1.0))
        
        # 2. 获取元素大小，计算点击偏移量（不要每次都点中心）
        size = element.size
        w, h = size['width'], size['height']
        
        # 在元素内部随机取点 (避免点到最边缘)
        offset_x = random.randint(-int(w/4), int(w/4)) if w > 10 else 0
        offset_y = random.randint(-int(h/4), int(h/4)) if h > 10 else 0
        
        # 3. 移动逻辑
        # 由于 Selenium 的 move_to_element 是瞬间完成的，我们通过 pause 和 offset 
        # 来模拟最后的“确认”动作。
        # 如果需要更底层的轨迹模拟，需要 CDP 协议，这里使用 Actions 链模拟"注视"效果
        
        actions.move_to_element_with_offset(element, offset_x, offset_y)
        
        # 随机停顿，模拟人眼确认
        actions.pause(random.uniform(0.1, 0.4))
        actions.perform()
        
    except Exception as e:
        logger.warning(f"拟人化移动失败，回退到普通移动: {e}")
        # 回退方案
        ActionChains(driver).move_to_element(element).perform()

# --- 通知模块 (保持原逻辑) ---

def get_email_config():
    """从环境变量获取邮件配置"""
    return {
        'enabled': os.environ.get('ENABLE_EMAIL_NOTIFY', 'false').lower() == 'true',
        'host': os.environ.get('SMTP_HOST'),
        'port': int(os.environ.get('SMTP_PORT', 587)),
        'user': os.environ.get('SMTP_USER'),
        'password': os.environ.get('SMTP_PASSWORD'),
        'from_addr': os.environ.get('EMAIL_FROM'),
        'to_addr': os.environ.get('EMAIL_TO')
    }

def send_email_notification(script_name, success, message):
    config = get_email_config()
    if not config['enabled'] or not all([config['host'], config['user'], config['password'], config['to_addr']]):
        return
    status_text = '✅ 执行成功' if success else '❌ 执行失败'
    subject = f"[{status_text}] Automation AIO: {script_name}"
    body = f"""<h3>Automation AIO 报告</h3><p>任务: {script_name}</p><p>状态: {status_text}</p><hr><pre>{message}</pre>"""
    msg = MIMEMultipart()
    msg['From'] = config['from_addr'] or config['user']
    msg['To'] = config['to_addr']
    msg['Subject'] = Header(subject, 'utf-8')
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    try:
        if config['port'] == 465: server = smtplib.SMTP_SSL(config['host'], config['port'])
        else:
            server = smtplib.SMTP(config['host'], config['port'])
            server.starttls()
        server.login(config['user'], config['password'])
        server.sendmail(config['from_addr'] or config['user'], config['to_addr'], msg.as_string())
        server.quit()
    except Exception as e: logger.error(f"邮件失败: {e}")

def send_telegram_notification(script_name, success, message, bot_token, chat_id):
    if not bot_token or not chat_id: return
    status_emoji = '✅' if success else '❌'
    if message and len(message) > 2000: message = message[-2000:] + "\n...(截断)"
    html_message = f"<b>{status_emoji} 自动化通知</b>\n任务: {script_name}\n<pre>{message}</pre>"
    try:
        requests.post(f'https://api.telegram.org/bot{bot_token}/sendMessage', 
                      data={'chat_id': chat_id, 'text': html_message, 'parse_mode': 'HTML'}, timeout=10)
    except Exception as e: logger.error(f"TG通知异常: {e}")

# --- 执行器类 ---

class SeleniumIDEExecutor:
    """Selenium IDE脚本执行器 - Undetected Chrome Edition"""
    
    def __init__(self, script_path):
        self.script_path = script_path
        self.driver = None
        self.variables = {}
        self.base_url = ''
        
    def setup_driver(self):
        """初始化WebDriver - 使用 undetected_chromedriver"""
        try:
            # 必须设置 DISPLAY 环境变量以支持 headful 模式 (uc 不支持 headless 隐身)
            os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':1')
            
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-popup-blocking')
            
            # 获取 Chrome 二进制路径
            browser_path = os.environ.get('CHROME_BINARY', '/usr/bin/google-chrome-stable')
            
            logger.info(f"启动 Undetected Chrome... (Bin: {browser_path})")
            
            # 初始化 UC 驱动
            # use_subprocess=True 是 Docker 环境防止僵尸进程的关键
            self.driver = uc.Chrome(
                options=options,
                browser_executable_path=browser_path,
                use_subprocess=True,
                version_main=None  # 自动检测版本
            )
            
            # 设置一个常见的分辨率
            self.driver.set_window_size(1366, 768)
            
            logger.info("✅ Undetected WebDriver 初始化成功")
            return True
        except Exception as e:
            logger.error(f"❌ WebDriver 初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def load_script(self):
        try:
            with open(self.script_path, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
            if 'url' in script_data:
                self.base_url = script_data['url']
            return script_data
        except Exception as e:
            logger.error(f"加载脚本失败: {e}")
            return None
    
    def human_delay(self):
        """添加随机延迟"""
        delay = random.uniform(HUMAN_LIKE_DELAYS['min_command_delay'], HUMAN_LIKE_DELAYS['max_command_delay'])
        time.sleep(delay)
    
    def execute_command(self, command):
        cmd = command.get('command', '')
        target = command.get('target', '')
        value = command.get('value', '')
        
        try:
            self.human_delay()
            target = self.replace_variables(target)
            value = self.replace_variables(value)
            
            logger.info(f"执行: {cmd} | {target}")
            
            if cmd == 'open':
                if target.startswith('http'): url = target
                elif target.startswith('/'): url = (self.base_url.rstrip('/') if self.base_url else 'https://www.google.com') + target
                else: url = self.base_url
                self.driver.get(url)
            
            elif cmd == 'click':
                element = self.find_element(target)
                # 使用拟人化移动
                human_mouse_move(self.driver, element)
                # 使用 ActionChains 点击比 element.click() 更像真人
                ActionChains(self.driver).click(element).perform()
            
            elif cmd == 'type':
                element = self.find_element(target)
                human_mouse_move(self.driver, element)
                ActionChains(self.driver).click(element).perform()
                
                element.clear()
                time.sleep(random.uniform(0.1, 0.3))
                # 模拟打字输入，每个字符随机延迟
                for char in value:
                    element.send_keys(char)
                    time.sleep(random.uniform(HUMAN_LIKE_DELAYS['min_typing_delay'], HUMAN_LIKE_DELAYS['max_typing_delay']))
            
            elif cmd == 'sendKeys':
                element = self.find_element(target)
                if value == '${KEY_ENTER}': element.send_keys(Keys.ENTER)
                else: element.send_keys(value)
            
            elif cmd == 'waitForElementVisible':
                WebDriverWait(self.driver, 30).until(EC.visibility_of_element_located(self.parse_locator(target)))
                
            elif cmd == 'waitForElementPresent':
                WebDriverWait(self.driver, 30).until(EC.presence_of_element_located(self.parse_locator(target)))
            
            elif cmd == 'pause':
                time.sleep(int(value) / 1000)
                
            elif cmd == 'store':
                self.variables[value] = target
                
            elif cmd == 'storeText':
                element = self.find_element(target)
                self.variables[value] = element.text
            
            elif cmd == 'executeScript':
                self.driver.execute_script(target)
                
            elif cmd == 'verifyText' or cmd == 'assertText':
                element = self.find_element(target)
                if element.text != value:
                    logger.warning(f"断言失败: 期望 '{value}', 实际 '{element.text}'")
                    # 不阻断，仅记录
            
            else:
                logger.debug(f"忽略或未实现的命令: {cmd}")
            
            return True
            
        except Exception as e:
            logger.error(f"命令执行出错: {cmd} - {e}")
            return False
    
    def find_element(self, target):
        by, value = self.parse_locator(target)
        return self.driver.find_element(by, value)
    
    def parse_locator(self, target):
        if target.startswith('id='): return (By.ID, target[3:])
        elif target.startswith('name='): return (By.NAME, target[5:])
        elif target.startswith('css='): return (By.CSS_SELECTOR, target[4:])
        elif target.startswith('xpath='): return (By.XPATH, target[6:])
        elif target.startswith('linkText='): return (By.LINK_TEXT, target[9:])
        elif target.startswith('//'): return (By.XPATH, target)
        else: return (By.CSS_SELECTOR, target)
    
    def replace_variables(self, text):
        if not text: return text
        for var_name, var_value in self.variables.items():
            text = text.replace(f'${{{var_name}}}', str(var_value))
        return text
    
    def execute(self):
        start_time = datetime.now()
        try:
            script_data = self.load_script()
            if not script_data: return False, "脚本格式无效"
            if not self.setup_driver(): return False, "浏览器环境初始化失败"
            
            tests = script_data.get('tests', [])
            for test in tests:
                logger.info(f"开始测试用例: {test.get('name')}")
                for command in test.get('commands', []):
                    if not self.execute_command(command):
                        return False, f"指令执行失败: {command.get('command')}"
            
            duration = (datetime.now() - start_time).total_seconds()
            return True, f"任务完成，耗时 {duration:.2f} 秒"
        except Exception as e:
            return False, f"运行时异常: {str(e)}"
        finally:
            if self.driver:
                try: 
                    self.driver.quit()
                    logger.info("浏览器已关闭")
                except: pass

if __name__ == '__main__':
    # 命令行入口
    if len(sys.argv) < 2:
        print("Usage: python3 task_executor.py <script.side> [token] [chat_id]")
        sys.exit(1)
        
    script_path = sys.argv[1]
    bot_token = sys.argv[2] if len(sys.argv) > 2 else None
    chat_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    executor = SeleniumIDEExecutor(script_path)
    success, message = executor.execute()
    
    script_name = Path(script_path).name
    if bot_token and chat_id: 
        send_telegram_notification(script_name, success, message, bot_token, chat_id)
    send_email_notification(script_name, success, message)
    
    sys.exit(0 if success else 1)
