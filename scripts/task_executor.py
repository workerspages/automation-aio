#!/usr/bin/env python3
"""
Selenium IDE 任务执行器 & 通用通知模块
"""

import sys
import json
import time
import random
import logging
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from pathlib import Path
from datetime import datetime

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# Driver Manager
from webdriver_manager.chrome import ChromeDriverManager

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

# 人类化操作配置
HUMAN_LIKE_DELAYS = {
    'min_command_delay': 0.5,
    'max_command_delay': 2.0,
    'min_typing_delay': 0.05,
    'max_typing_delay': 0.15,
    'scroll_delay': 0.5,
    'click_delay': 0.3
}

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
    """发送邮件通知"""
    config = get_email_config()
    
    if not config['enabled']:
        return
    
    if not all([config['host'], config['user'], config['password'], config['to_addr']]):
        logger.warning("邮件配置不完整，跳过发送")
        return

    status_text = '✅ 执行成功' if success else '❌ 执行失败'
    subject = f"[{status_text}] Automation AIO 任务执行通知: {script_name}"
    
    # 邮件正文内容
    body = f"""
    <h3>🤖 Automation AIO 任务执行报告</h3>
    <p><b>任务名称:</b> {script_name}</p>
    <p><b>执行状态:</b> <span style="color: {'green' if success else 'red'}">{status_text}</span></p>
    <p><b>执行时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <hr>
    <p><b>详细日志:</b></p>
    <pre style="background-color: #f4f4f4; padding: 10px; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word;">{message}</pre>
    """

    msg = MIMEMultipart()
    msg['From'] = config['from_addr'] or config['user']
    msg['To'] = config['to_addr']
    msg['Subject'] = Header(subject, 'utf-8')
    msg.attach(MIMEText(body, 'html', 'utf-8'))

    try:
        # 连接 SMTP 服务器
        if config['port'] == 465:
            server = smtplib.SMTP_SSL(config['host'], config['port'])
        else:
            server = smtplib.SMTP(config['host'], config['port'])
            server.starttls() # 启用 TLS 加密
        
        server.login(config['user'], config['password'])
        server.sendmail(config['from_addr'] or config['user'], config['to_addr'], msg.as_string())
        server.quit()
        logger.info(f"邮件通知已发送至: {config['to_addr']}")
    except Exception as e:
        logger.error(f"发送邮件通知失败: {e}")

def send_telegram_notification(script_name, success, message, bot_token, chat_id):
    """
    通用 Telegram 通知发送函数
    适用于: Selenium, Playwright, Actiona, AutoKey
    """
    if not bot_token or not chat_id:
        return
    
    status_emoji = '✅' if success else '❌'
    status_text = '执行成功' if success else '执行失败'
    
    # 截断过长消息
    if message and len(message) > 2000:
        message = message[-2000:] + "\n...(日志过长已截断)"
    
    html_message = f"""
<b>{status_emoji} 自动化任务通知</b>

<b>任务名称:</b> {script_name}
<b>执行状态:</b> {status_text}
<b>执行时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>详细信息:</b>
<pre>{message}</pre>
"""
    
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {
        'chat_id': chat_id,
        'text': html_message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"Telegram通知已发送: {script_name}")
        else:
            logger.warning(f"Telegram通知发送失败: {response.text}")
    except Exception as e:
        logger.error(f"发送Telegram通知异常: {e}")


class SeleniumIDEExecutor:
    """Selenium IDE脚本执行器 - Chrome Edition"""
    
    def __init__(self, script_path):
        self.script_path = script_path
        self.driver = None
        self.variables = {}
        self.base_url = ''
        
    def setup_driver(self):
        """初始化WebDriver - 使用Chrome + 反检测配置"""
        try:
            # 确保 DISPLAY 变量设置正确，用于 VNC 显示
            os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':1')
            
            options = Options()
            
            # 基础配置
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-gpu')
            # 禁用沙盒提示条
            options.add_argument('--disable-infobars')
            
            # 反检测配置 (Anti-bot)
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
            
            # 设置 User-Agent
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 使用 webdriver_manager 自动获取匹配的 chromedriver
            service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.maximize_window()
            self.driver.implicitly_wait(10)
            
            # 执行 CDP 命令进行隐身
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.navigator.chrome = {
                        runtime: {}
                    };
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['zh-CN', 'zh', 'en']
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                '''
            })
            
            logger.info("WebDriver (Chrome) 初始化成功")
            return True
        except Exception as e:
            logger.error(f"WebDriver 初始化失败: {e}")
            # 尝试 fallback 到系统路径
            try:
                logger.info("尝试使用系统路径 /usr/bin/chromedriver ...")
                service = Service('/usr/bin/chromedriver')
                self.driver = webdriver.Chrome(service=service, options=options)
                return True
            except Exception as e2:
                logger.error(f"系统路径启动也失败: {e2}")
                return False
    
    def load_script(self):
        """加载Selenium IDE脚本"""
        try:
            with open(self.script_path, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
            
            if 'url' in script_data:
                self.base_url = script_data['url']
                logger.info(f"读取到 base URL: {self.base_url}")
            
            logger.info(f"成功加载脚本: {self.script_path}")
            return script_data
        except Exception as e:
            logger.error(f"加载脚本失败: {e}")
            return None
    
    def human_delay(self, min_delay=None, max_delay=None):
        """添加人类化随机延迟"""
        if min_delay is None:
            min_delay = HUMAN_LIKE_DELAYS['min_command_delay']
        if max_delay is None:
            max_delay = HUMAN_LIKE_DELAYS['max_command_delay']
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def execute_command(self, command):
        """执行单个命令"""
        cmd = command.get('command', '')
        target = command.get('target', '')
        value = command.get('value', '')
        
        try:
            self.human_delay()
            target = self.replace_variables(target)
            value = self.replace_variables(value)
            
            logger.info(f"执行命令: {cmd} | {target} | {value}")
            
            if cmd == 'open':
                if target.startswith('http'):
                    url = target
                elif target.startswith('/'):
                    url = (self.base_url.rstrip('/') if self.base_url else 'https://www.baidu.com') + target
                else:
                    url = self.base_url if self.base_url else 'https://www.baidu.com'
                self.driver.get(url)
            
            elif cmd == 'click':
                element = self.find_element(target)
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(HUMAN_LIKE_DELAYS['scroll_delay'])
                ActionChains(self.driver).move_to_element(element).pause(HUMAN_LIKE_DELAYS['click_delay']).click().perform()
            
            elif cmd == 'type':
                element = self.find_element(target)
                element.clear()
                time.sleep(0.2)
                for char in value:
                    element.send_keys(char)
                    time.sleep(random.uniform(HUMAN_LIKE_DELAYS['min_typing_delay'], HUMAN_LIKE_DELAYS['max_typing_delay']))
            
            elif cmd == 'sendKeys':
                element = self.find_element(target)
                if value == '${KEY_ENTER}':
                    element.send_keys(Keys.ENTER)
                else:
                    element.send_keys(value)
            
            elif cmd == 'select':
                from selenium.webdriver.support.select import Select
                element = self.find_element(target)
                select = Select(element)
                if value.startswith('label='):
                    select.select_by_visible_text(value.replace('label=', ''))
                elif value.startswith('value='):
                    select.select_by_value(value.replace('value=', ''))
                else:
                    select.select_by_visible_text(value)
            
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
            
            elif cmd == 'storeValue':
                element = self.find_element(target)
                self.variables[value] = element.get_attribute('value')
            
            elif cmd == 'assertText':
                element = self.find_element(target)
                assert element.text == value
            
            elif cmd == 'assertTitle':
                assert self.driver.title == target
            
            elif cmd == 'executeScript':
                self.driver.execute_script(target)
            
            elif cmd == 'setWindowSize':
                if 'x' in value:
                    sizes = value.split('x')
                    self.driver.set_window_size(int(sizes[0]), int(sizes[1]))
            
            else:
                logger.warning(f"未知命令: {cmd}")
            
            return True
            
        except Exception as e:
            logger.error(f"命令执行失败: {cmd} - {e}")
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
            if not script_data: return False, "脚本加载失败"
            
            if not self.setup_driver(): return False, "浏览器初始化失败"
            
            tests = script_data.get('tests', [])
            for test in tests:
                logger.info(f"执行测试: {test.get('name', 'Unnamed')}")
                commands = test.get('commands', [])
                for i, command in enumerate(commands):
                    if not self.execute_command(command):
                        error_msg = f"命令执行失败 (第{i+1}条): {command.get('command')}"
                        return False, error_msg
            
            time.sleep(5)
            duration = (datetime.now() - start_time).total_seconds()
            return True, f"执行成功，耗时{duration:.2f}秒"
            
        except Exception as e:
            logger.error(f"脚本执行异常: {e}")
            return False, str(e)
        finally:
            if self.driver:
                try: self.driver.quit()
                except: pass

if __name__ == '__main__':
    # 命令行测试入口
    if len(sys.argv) < 2:
        print("Usage: python3 task_executor.py <script_path> [bot_token] [chat_id]")
        sys.exit(1)
    
    script_path = sys.argv[1]
    bot_token = sys.argv[2] if len(sys.argv) > 2 else None
    chat_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    executor = SeleniumIDEExecutor(script_path)
    success, message = executor.execute()
    
    script_name = Path(script_path).name
    
    # 发送 Telegram
    if bot_token and chat_id:
        send_telegram_notification(script_name, success, message, bot_token, chat_id)
    
    # 发送邮件
    send_email_notification(script_name, success, message)
    
    sys.exit(0 if success else 1)
