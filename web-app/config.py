import os

class Config:
    """应用配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:////app/data/tasks.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Selenium脚本目录
    SCRIPTS_DIR = '/home/headless/Downloads'
    
    # Telegram配置
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
    
    # 任务执行配置
    MAX_SCRIPT_TIMEOUT = 300  # 脚本最大执行时间（秒）
    RETRY_FAILED_TASKS = True
    MAX_RETRIES = 3
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = '/app/data/automation.log'
    
    # Chrome配置 (标准化为 Chrome)
    CHROME_BINARY = '/usr/bin/google-chrome-stable'
    
    # Web应用配置
    HOST = '0.0.0.0'
    PORT = 8080
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # 定时器配置
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Asia/Shanghai'

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False

# 根据环境变量选择配置
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """获取当前配置"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
