import os
import sys
import subprocess
import time
from datetime import datetime

# 设置日志文件
LOG_FILE = '/app/logs/diagnose.log'

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(formatted_msg + '\n')
    except Exception as e:
        print(f"Error writing to log: {e}")

def run_command(cmd, env=None):
    log(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
        log(f"Return Code: {result.returncode}")
        if result.stdout:
            log(f"STDOUT:\n{result.stdout.strip()}")
        if result.stderr:
            log(f"STDERR:\n{result.stderr.strip()}")
        return result.returncode == 0
    except Exception as e:
        log(f"Execution failed: {e}")
        return False

def main():
    log("=== Starting Diagnostic Script ===")
    
    # 1. 打印当前环境信息
    log(f"User: {os.environ.get('USER')}")
    log(f"Home: {os.environ.get('HOME')}")
    log(f"Display: {os.environ.get('DISPLAY')}")
    log(f"XAuthority: {os.environ.get('XAUTHORITY')}")
    log(f"Current Working Directory: {os.getcwd()}")
    
    # 2. 检查显示变量
    env = os.environ.copy()
    display = env.get('DISPLAY', ':1')
    log(f"Checking Display {display}...")
    
    # 3. 尝试运行简单的 X 命令
    # xset q 是一个常用的检查 X server 状态的命令
    success = run_command(['xset', 'q'], env=env)
    
    if success:
        log("✅ X Server connection successful!")
    else:
        log("❌ Failed to connect to X Server.")
        log("Trying to list /tmp/.X11-unix to check for sockets:")
        run_command(['ls', '-la', '/tmp/.X11-unix'])
        
        log("Checking Xorg processes:")
        run_command(['ps', 'aux'])

    # 4. 检查 Python GUI 库 (Tkinter)
    log("Checking Tkinter support...")
    try:
        import tkinter
        log("Tkinter imported successfully.")
        try:
            root = tkinter.Tk()
            log("Tkinter window created successfully (Headless check passed).")
            root.destroy()
        except Exception as e:
            log(f"❌ Tkinter initialization failed: {e}")
    except ImportError:
        log("Tkinter not installed.")

    log("=== Diagnostic Finished ===")

if __name__ == '__main__':
    main()
