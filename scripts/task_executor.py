#!/usr/bin/env python3
"""
Selenium IDE任务执行器
用于执行.side格式的Selenium脚本文件
支持可视化执行和反机器人检测
"""

import sys
import json
import time
import random
import logging
import os
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import requests

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

class SeleniumIDEExecutor:
    """Selenium IDE脚本执行器 - 可视化模式"""
    
    def __init__(self, script_path):
        self.script_path = script_path
        self.driver = None
        self.variables = {}
        self.base_url = ''
        
    def setup_driver(self):
        """初始化WebDriver - 可视化模式，支持反检测"""
        try:
            # 首先设置 DISPLAY 环境变量
            os.environ['DISPLAY'] = ':1'
            
            options = Options()
            
            # 不使用无头模式 - 在VNC中可见
            # options.add_argument('--headless')  # 注释掉
            
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.set_preference('intl.accept_languages', 'zh-CN')
            
            # 反检测配置
            options.set_preference('dom.webdriver.enabled', False)
            options.set_preference('useAutomationExtension', False)
            options.set_preference('general.useragent.override', 
                                 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            self.driver = webdriver.Firefox(options=options)
            self.driver.implicitly_wait(10)
            
            # 执行反检测脚本
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                window.navigator.chrome = {
                    runtime: {}
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });
            """)
            
            logger.info("WebDriver初始化成功（可视化模式 + 反检测）")
            return True
        except Exception as e:
            logger.error(f"WebDriver初始化失败: {e}")
            return False
    
    def load_script(self):
        """加载Selenium IDE脚本"""
        try:
            with open(self.script_path, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
            
            # 读取 base URL
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
        """执行单个命令 - 带人类化操作"""
        cmd = command.get('command', '')
        target = command.get('target', '')
        value = command.get('value', '')
        
        try:
            # 命令执行前的随机延迟
            self.human_delay()
            
            # 替换变量
            target = self.replace_variables(target)
            value = self.replace_variables(value)
            
            logger.info(f"执行命令: {cmd} | {target} | {value}")
            
            if cmd == 'open':
                # 智能处理 URL
                if target.startswith('http://') or target.startswith('https://'):
                    # 完整 URL
                    url = target
                elif target.startswith('/'):
                    # 相对路径
                    if self.base_url:
                        url = self.base_url.rstrip('/') + target
                    else:
                        # 如果没有 base_url，默认使用百度
                        url = 'https://www.baidu.com' + target
                        logger.warning(f"未设置 base_url，使用默认: {url}")
                elif target:
                    # 不带协议的域名
                    url = f"https://{target}"
                else:
                    # 空目标，使用 base_url
                    url = self.base_url if self.base_url else 'https://www.baidu.com'
                
                logger.info(f"访问 URL: {url}")
                self.driver.get(url)
            
            elif cmd == 'click':
                element = self.find_element(target)
                # 滚动到元素可见
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(HUMAN_LIKE_DELAYS['scroll_delay'])
                # 移动到元素上
                ActionChains(self.driver).move_to_element(element).pause(HUMAN_LIKE_DELAYS['click_delay']).click().perform()
            
            elif cmd == 'type':
                element = self.find_element(target)
                element.clear()
                time.sleep(0.2)
                # 逐字输入，模拟人类打字
                for char in value:
                    element.send_keys(char)
                    time.sleep(random.uniform(
                        HUMAN_LIKE_DELAYS['min_typing_delay'],
                        HUMAN_LIKE_DELAYS['max_typing_delay']
                    ))
            
            elif cmd == 'sendKeys':
                element = self.find_element(target)
                # 逐字输入
                for char in value:
                    element.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
            
            elif cmd == 'select':
                from selenium.webdriver.support.select import Select
                element = self.find_element(target)
                select = Select(element)
                select.select_by_visible_text(value)
            
            elif cmd == 'waitForElementVisible':
                WebDriverWait(self.driver, 30).until(
                    EC.visibility_of_element_located(self.parse_locator(target))
                )
            
            elif cmd == 'waitForElementPresent':
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located(self.parse_locator(target))
                )
            
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
                assert element.text == value, f"文本不匹配: 期望 '{value}', 实际 '{element.text}'"
            
            elif cmd == 'assertTitle':
                assert self.driver.title == target, f"标题不匹配: 期望 '{target}', 实际 '{self.driver.title}'"
            
            elif cmd == 'mouseOver':
                element = self.find_element(target)
                ActionChains(self.driver).move_to_element(element).perform()
            
            elif cmd == 'doubleClick':
                element = self.find_element(target)
                ActionChains(self.driver).double_click(element).perform()
            
            elif cmd == 'executeScript':
                self.driver.execute_script(target)
            
            elif cmd == 'refresh':
                self.driver.refresh()
            
            elif cmd == 'close':
                self.driver.close()
            
            elif cmd == 'runScript':
                self.driver.execute_script(target)
            
            elif cmd == 'setWindowSize':
                if not value or 'x' not in value:
                    logger.warning(f"setWindowSize 参数格式错误或为空: {value}")
                    return False
                sizes = value.split('x')
                if len(sizes) != 2:
                    logger.warning(f"setWindowSize 参数数量不对: {value}")
                    return False
                try:
                    width = int(sizes[0])
                    height = int(sizes[1])
                    self.driver.set_window_size(width, height)
                except ValueError as e:
                    logger.error(f"setWindowSize 转换失败: {value}，错误: {e}")
                    return False
            
            else:
                logger.warning(f"未知命令: {cmd}")
            
            return True
            
        except Exception as e:
            logger.error(f"命令执行失败: {cmd} - {e}")
            return False
    
    def find_element(self, target):
        """查找元素"""
        by, value = self.parse_locator(target)
        return self.driver.find_element(by, value)
    
    def parse_locator(self, target):
        """解析定位器"""
        if target.startswith('id='):
            return (By.ID, target[3:])
        elif target.startswith('name='):
            return (By.NAME, target[5:])
        elif target.startswith('css='):
            return (By.CSS_SELECTOR, target[4:])
        elif target.startswith('xpath='):
            return (By.XPATH, target[6:])
        elif target.startswith('linkText='):
            return (By.LINK_TEXT, target[9:])
        elif target.startswith('//'):
            return (By.XPATH, target)
        else:
            return (By.CSS_SELECTOR, target)
    
    def replace_variables(self, text):
        """替换变量"""
        if not text:
            return text
        for var_name, var_value in self.variables.items():
            text = text.replace(f'${{{var_name}}}', str(var_value))
        return text
    
    def execute(self):
        """执行完整脚本"""
        start_time = datetime.now()
        
        try:
            # 加载脚本
            script_data = self.load_script()
            if not script_data:
                return False, "脚本加载失败"
            
            # 初始化浏览器
            if not self.setup_driver():
                return False, "浏览器初始化失败"
            
            # 执行测试
            tests = script_data.get('tests', [])
            for test in tests:
                logger.info(f"执行测试: {test.get('name', 'Unnamed')}")
                commands = test.get('commands', [])
                
                for i, command in enumerate(commands):
                    if not self.execute_command(command):
                        error_msg = f"命令执行失败 (第{i+1}条): {command.get('command')}"
                        return False, error_msg
            
            # 任务完成后保持浏览器打开一段时间（便于观察）
            logger.info("任务执行完成，浏览器将在10秒后关闭")
            time.sleep(10)
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"脚本执行成功，耗时: {duration:.2f}秒")
            return True, f"执行成功，耗时{duration:.2f}秒"
            
        except Exception as e:
            logger.error(f"脚本执行异常: {e}")
            return False, str(e)
        
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass

def send_telegram_notification(script_name, success, message, bot_token, chat_id):
    """发送Telegram通知"""
    if not bot_token or not chat_id:
        return
    
    status_emoji = '✅' if success else '❌'
    status_text = '成功' if success else '失败'
    
    html_message = f"""
<b>{status_emoji} Selenium任务执行通知</b>

<b>脚本名称:</b> {script_name}
<b>执行状态:</b> {status_text}
<b>执行时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>详细信息:</b> {message}
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
            logger.info("Telegram通知发送成功")
        else:
            logger.warning(f"Telegram通知发送失败: {response.status_code}")
    except Exception as e:
        logger.error(f"发送Telegram通知异常: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 task_executor.py <script_path> [bot_token] [chat_id]")
        sys.exit(1)
    
    script_path = sys.argv[1]
    bot_token = sys.argv[2] if len(sys.argv) > 2 else None
    chat_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    # 执行脚本
    executor = SeleniumIDEExecutor(script_path)
    success, message = executor.execute()
    
    # 发送通知
    if bot_token and chat_id:
        script_name = Path(script_path).name
        send_telegram_notification(script_name, success, message, bot_token, chat_id)
    
    # 返回执行结果
    sys.exit(0 if success else 1)
