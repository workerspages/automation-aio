#!/usr/bin/env python3
"""
Selenium IDE 任务执行器 (Chrome Only Edition)
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

# Driver Manager (Only Chrome)
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
    'min_command_delay': 0.5, 'max_command_delay': 2.0,
    'min_typing_delay': 0.05, 'max_typing_delay': 0.15,
    'scroll_delay': 0.5, 'click_delay': 0.3
}

# --- 通知函数保持不变 ---
def get_email_config():
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
    if not config['enabled'] or not all([config['host'], config['user']]): return
    
    status_text = '✅ 执行成功' if success else '❌ 执行失败'
    subject = f"[{status_text}] 任务通知: {script_name}"
    public_domain = os.environ.get('APP_PUBLIC_DOMAIN', '').rstrip('/')
    link_html = f'<p><a href="{public_domain}">View Dashboard</a></p>' if public_domain else ''
    
    body = f"<h3>任务报告</h3><p><b>任务:</b> {script_name}</p><p><b>状态:</b> {status_text}</p><p><b>时间:</b> {datetime.now()}</p>{link_html}<hr><pre>{message}</pre>"
    
    msg = MIMEMultipart()
    msg['From'] = config['from_addr'] or config['user']
    msg['To'] = config['to_addr']
    msg['Subject'] = Header(subject, 'utf-8')
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    
    try:
        server = smtplib.SMTP_SSL(config['host'], config['port']) if config['port'] == 465 else smtplib.SMTP(config['host'], config['port'])
        if config['port'] != 465: server.starttls()
        server.login(config['user'], config['password'])
        server.sendmail(msg['From'], config['to_addr'], msg.as_string())
        server.quit()
    except Exception as e: logger.error(f"Email fail: {e}")

def send_telegram_notification(script_name, success, message, bot_token, chat_id):
    if not bot_token or not chat_id: return
    status_emoji = '✅' if success else '❌'
    public_domain = os.environ.get('APP_PUBLIC_DOMAIN', '').rstrip('/')
    link_text = f"\n<a href='{public_domain}'>Open Dashboard</a>" if public_domain else ""
    
    text = f"<b>{status_emoji} 任务通知</b>\n\n<b>任务:</b> {script_name}\n<b>时间:</b> {datetime.now()}{link_text}\n<pre>{message[-2000:] if message else 'No Log'}</pre>"
    try:
        requests.post(f'https://api.telegram.org/bot{bot_token}/sendMessage', data={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
    except Exception as e: logger.error(f"Telegram fail: {e}")

# --- 执行器类 ---
class SeleniumIDEExecutor:
    def __init__(self, script_path):
        self.script_path = script_path
        self.driver = None
        self.variables = {}
        self.base_url = ''
        
    def setup_driver(self):
        try:
            os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':1')
            options = Options()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 强制使用 Chrome，不尝试其他浏览器
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.maximize_window()
            self.driver.implicitly_wait(10)
            
            # Anti-detection CDP
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            })
            return True
        except Exception as e:
            logger.error(f"Chrome Init Failed: {e}")
            return False
    
    def load_script(self):
        try:
            with open(self.script_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.base_url = data.get('url', '')
            return data
        except Exception as e:
            return None
    
    def human_delay(self):
        time.sleep(random.uniform(HUMAN_LIKE_DELAYS['min_command_delay'], HUMAN_LIKE_DELAYS['max_command_delay']))
    
    def execute_command(self, command):
        cmd = command.get('command', '')
        target = self.replace_variables(command.get('target', ''))
        value = self.replace_variables(command.get('value', ''))
        
        try:
            self.human_delay()
            logger.info(f"CMD: {cmd} | {target} | {value}")
            
            if cmd == 'open':
                url = target if target.startswith('http') else (self.base_url.rstrip('/') + target)
                self.driver.get(url)
            elif cmd == 'click':
                el = self.find_element(target)
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
                time.sleep(HUMAN_LIKE_DELAYS['scroll_delay'])
                ActionChains(self.driver).move_to_element(el).pause(0.2).click().perform()
            elif cmd == 'type':
                el = self.find_element(target)
                el.clear()
                for char in value:
                    el.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
            elif cmd == 'sendKeys':
                el = self.find_element(target)
                el.send_keys(Keys.ENTER if value == '${KEY_ENTER}' else value)
            elif cmd == 'select':
                from selenium.webdriver.support.select import Select
                select = Select(self.find_element(target))
                if value.startswith('label='): select.select_by_visible_text(value[6:])
                elif value.startswith('value='): select.select_by_value(value[6:])
                else: select.select_by_visible_text(value)
            elif cmd == 'pause':
                time.sleep(int(value) / 1000)
            elif cmd == 'store':
                self.variables[value] = target
            elif cmd == 'storeText':
                self.variables[value] = self.find_element(target).text
            elif cmd == 'executeScript':
                self.driver.execute_script(target)
            
            return True
        except Exception as e:
            logger.error(f"Exec Fail: {cmd} - {e}")
            return False
    
    def find_element(self, target):
        if target.startswith('id='): by, val = By.ID, target[3:]
        elif target.startswith('name='): by, val = By.NAME, target[5:]
        elif target.startswith('css='): by, val = By.CSS_SELECTOR, target[4:]
        elif target.startswith('xpath='): by, val = By.XPATH, target[6:]
        elif target.startswith('//'): by, val = By.XPATH, target
        else: by, val = By.CSS_SELECTOR, target
        return self.driver.find_element(by, val)
    
    def replace_variables(self, text):
        for k, v in self.variables.items():
            text = text.replace(f'${{{k}}}', str(v))
        return text
    
    def execute(self):
        try:
            data = self.load_script()
            if not data: return False, "Load script failed"
            if not self.setup_driver(): return False, "Driver init failed"
            
            for test in data.get('tests', []):
                for cmd in test.get('commands', []):
                    if not self.execute_command(cmd): return False, f"Failed at {cmd.get('command')}"
            
            return True, "Finished"
        except Exception as e:
            return False, str(e)
        finally:
            if self.driver: self.driver.quit()

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(1)
    executor = SeleniumIDEExecutor(sys.argv[1])
    success, msg = executor.execute()
    
    # 获取 Telegram 配置 (优先使用命令行参数，否则读取环境变量)
    tg_token = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('TELEGRAM_BOT_TOKEN')
    tg_chat_id = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('TELEGRAM_CHAT_ID')

    if tg_token and tg_chat_id:
        send_telegram_notification(Path(sys.argv[1]).name, success, msg, tg_token, tg_chat_id)
    else:
        logger.warning("⚠️ Telegram notification skipped: No token/chat_id provided in args or environment.")
    
    send_email_notification(Path(sys.argv[1]).name, success, msg)
    sys.exit(0 if success else 1)
