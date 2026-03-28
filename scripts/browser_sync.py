import os
import zipfile
import io
import shutil
from pathlib import Path
import logging

logger = logging.getLogger('browser_sync')

CHROME_CONFIG_DIR = Path('/home/headless/.config/google-chrome')

# 需要重点备份的核心相对路径列表
CORE_PATHS = [
    'Local State',
    'Default/Network/Cookies',
    'Default/Local Storage',
    'Default/Session Storage',
    'Default/Login Data',
    'Default/Web Data'
]

def backup_browser_profile() -> bytes:
    """
    将用户的核心浏览器认证状态（Cookies、LocalStorage等）打包封装为一个 ZIP 字节流。
    如果浏览器配置不存在则返回 None。
    """
    if not CHROME_CONFIG_DIR.exists():
        logger.warning(f"Chrome config directory not found at {CHROME_CONFIG_DIR}")
        return None
        
    memory_zip = io.BytesIO()
    found_files = 0
    
    with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel_path in CORE_PATHS:
            target_path = CHROME_CONFIG_DIR / rel_path
            
            if not target_path.exists():
                continue
                
            if target_path.is_file():
                zf.write(target_path, arcname=rel_path)
                found_files += 1
            elif target_path.is_dir():
                for root, dirs, files in os.walk(target_path):
                    for file in files:
                        file_path = Path(root) / file
                        # 排除不必要的系统缓存碎片 (如 .ldb 的临时文件) 如果需要的话，
                        # 但这里为了简单，把整个 Local Storage 打包
                        arcname = file_path.relative_to(CHROME_CONFIG_DIR)
                        zf.write(file_path, arcname=str(arcname))
                        found_files += 1
                        
    if found_files == 0:
        logger.warning("No core browser profile files found to backup.")
        return None
        
    memory_zip.seek(0)
    logger.info(f"Successfully backed up {found_files} core browser files.")
    return memory_zip.read()

def restore_browser_profile(zip_bytes: bytes) -> bool:
    """
    从数据库中提取出的二进制 ZIP 流恢复到本地 Chrome 目录。
    """
    if not zip_bytes:
        return False
        
    try:
        memory_zip = io.BytesIO(zip_bytes)
        
        # 确保根目录存在
        CHROME_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(memory_zip, 'r') as zf:
            zf.extractall(CHROME_CONFIG_DIR)
            
        logger.info("Successfully restored browser profile from cloud backup.")
        
        # 修正权限 (因为我们是在 supervisor 下以 root 或者其他权限运行)
        # 假设都在 headless 用户下
        shutil.chown(CHROME_CONFIG_DIR, user="headless", group="headless")
        for root, dirs, files in os.walk(CHROME_CONFIG_DIR):
            for d in dirs:
                shutil.chown(os.path.join(root, d), user="headless", group="headless")
            for f in files:
                shutil.chown(os.path.join(root, f), user="headless", group="headless")
                
        return True
    except Exception as e:
        logger.error(f"Failed to restore browser profile: {e}")
        return False
