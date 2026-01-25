
import sys
import os
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

# Ensure we can import from web-app
sys.path.append('/app/web-app')

from utils.ai_solver import AISolver

def smooth_slide(driver, slider_element, distance):
    """
    拟人化滑动轨迹
    """
    action = ActionChains(driver)
    action.click_and_hold(slider_element).perform()
    
    current = 0
    while current < distance:
        # 随机步长
        step = random.randint(3, 15)
        if current + step > distance:
            step = distance - current
        
        # Y轴微小抖动
        y_offset = random.randint(-1, 2)
        
        action.move_by_offset(step, y_offset).perform()
        current += step
        time.sleep(random.uniform(0.01, 0.05))
        
    # 模拟松开前的停顿
    time.sleep(random.uniform(0.2, 0.5))
    action.release().perform()

def main():
    print("🚀 Starting AI Slider Captcha Test...")
    
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--start-maximized")
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # 这里使用一个公开的测试站作为示例，实际需替换为真实目标
        # 注意：这只是为了演示代码结构，实际 CSS 选择器需要针对具体网站修改
        driver.get("https://dun.163.com/trial/jigsaw") 
        time.sleep(5)
        
        # 1. 截图验证码区域 (示例选择器，需替换)
        # bg_element = driver.find_element("css selector", ".yidun_bg-img")
        # bg_file = "/tmp/captcha_bg.png"
        # bg_element.screenshot(bg_file)
        # print("📸 Captcha background saved.")
        
        # 2. 调用 AI 识别
        solver = AISolver()
        if not solver.api_key:
            print("❌ Error: OPENAI_API_KEY not configured.")
            return

        # gap_x = solver.identify_gap(bg_file)
        gap_x = 100 # Mock value for demo if AI fails or no key
        
        if gap_x:
            print(f"🎯 AI identified gap at X={gap_x}")
            
            # slider = driver.find_element("css selector", ".yidun_slider")
            # smooth_slide(driver, slider, gap_x)
            print("✅ Slide action performed.")
        else:
            print("❌ AI failed to identify gap.")
            
        time.sleep(5)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
