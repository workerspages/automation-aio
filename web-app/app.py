import os
import sys
import json
import logging
import time
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 将上级目录加入路径，以便导入 scripts 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:////app/data/tasks.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

scheduler = BackgroundScheduler()
scheduler.start()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 数据库模型 ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    script_path = db.Column(db.String(500), nullable=False)
    cron_expression = db.Column(db.String(100), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    last_status = db.Column(db.String(50))
    # 修改点 1: 使用 datetime.now 确保创建时间符合系统时区
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.errorhandler(Exception)
def handle_error(e):
    logger.exception(e)
    return jsonify({'success': False, 'error': str(e)}), 500

# --- 路由视图 ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    tasks = Task.query.all()
    scripts = get_available_scripts()
    return render_template('dashboard.html', tasks=tasks, scripts=scripts)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200

# --- API 接口 ---
@app.route('/api/scripts', methods=['GET'])
@login_required
def list_scripts():
    scripts = get_available_scripts()
    return jsonify(scripts)

def get_available_scripts():
    """扫描 Downloads 目录获取支持的脚本类型"""
    scripts_dir = Path(os.environ.get('SCRIPTS_DIR', '/home/headless/Downloads'))
    scripts = []
    supported_extensions = ['.side', '.py', '.ascr', '.autokey']
    if scripts_dir.exists():
        for file in scripts_dir.iterdir():
            if file.suffix.lower() in supported_extensions:
                scripts.append({'name': file.name, 'path': str(file)})
    return scripts

@app.route('/api/tasks', methods=['GET', 'POST'])
@login_required
def manage_tasks():
    if request.method == 'POST':
        data = request.json
        task = Task(
            name=data['name'],
            script_path=data['script_path'],
            cron_expression=data['cron_expression'],
            enabled=data.get('enabled', True)
        )
        db.session.add(task)
        db.session.commit()
        if task.enabled:
            schedule_task(task)
        return jsonify({'success': True, 'task_id': task.id})
    tasks = Task.query.all()
    return jsonify([
        {
            'id': t.id,
            'name': t.name,
            'script_path': t.script_path,
            'cron_expression': t.cron_expression,
            'enabled': t.enabled,
            'last_run': t.last_run.isoformat() if t.last_run else None,
            'last_status': t.last_status
        } for t in tasks
    ])

@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if request.method == 'GET':
        return jsonify({
            'id': task.id,
            'name': task.name,
            'script_path': task.script_path,
            'cron_expression': task.cron_expression,
            'enabled': task.enabled,
            'last_run': task.last_run.isoformat() if task.last_run else None,
            'last_status': task.last_status
        })
    if request.method == 'DELETE':
        try:
            scheduler.remove_job(f'task_{task_id}')
        except:
            pass
        db.session.delete(task)
        db.session.commit()
        return jsonify({'success': True})
    if request.method == 'PUT':
        data = request.json
        task.name = data.get('name', task.name)
        task.cron_expression = data.get('cron_expression', task.cron_expression)
        task.enabled = data.get('enabled', task.enabled)
        db.session.commit()
        try:
            scheduler.remove_job(f'task_{task_id}')
        except:
            pass
        if task.enabled:
            schedule_task(task)
        return jsonify({'success': True})

@app.route('/api/tasks/<int:task_id>/run', methods=['POST'])
@login_required
def run_task_now(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    execute_script(task.id)
    return jsonify({'success': True, 'message': '任务已开始执行，请在VNC窗口查看执行过程'})

# --- 新增: 切换任务启用状态的接口 ---
@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # 切换状态
    task.enabled = not task.enabled
    db.session.commit()
    
    # 更新调度器
    try:
        if task.enabled:
            schedule_task(task)
            logger.info(f"Task {task.id} enabled and scheduled")
        else:
            scheduler.remove_job(f'task_{task.id}')
            logger.info(f"Task {task.id} disabled and removed from scheduler")
    except Exception as e:
        # 即使调度器报错（如任务本来就不在调度中），也视为成功切换了数据库状态
        logger.warning(f"Scheduler update warning for task {task.id}: {e}")
        pass

    return jsonify({'success': True, 'enabled': task.enabled})

# --- 核心调度逻辑 ---
def schedule_task(task):
    if task.enabled:
        try:
            trigger = CronTrigger.from_crontab(task.cron_expression)
            scheduler.add_job(
                func=execute_script,
                trigger=trigger,
                id=f'task_{task.id}',
                args=[task.id],
                replace_existing=True
            )
            logger.info(f'任务 {task.name} (ID: {task.id}) 已调度')
        except Exception as e:
            logger.error(f'调度任务失败: {e}')

def get_desktop_env():
    """
    关键函数：获取 VNC 桌面的环境变量 (DISPLAY, DBUS)。
    确保后台进程能与前台桌面应用（如 AutoKey, Chrome）通信。
    """
    env = os.environ.copy()
    env['DISPLAY'] = ':1' # 强制指定显示编号
    
    dbus_file = Path('/home/headless/.dbus-env')
    if dbus_file.exists():
        try:
            content = dbus_file.read_text().strip()
            # 解析 export DBUS_SESSION_BUS_ADDRESS='...'
            if content.startswith('export '):
                parts = content.replace('export ', '').split('=', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().strip("'").strip('"')
                    env[key] = value
        except Exception as e:
            logger.warning(f"读取 .dbus-env 失败: {e}")
    return env

def get_telegram_config():
    return os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')

def execute_script(task_id):
    """任务分发入口"""
    with app.app_context():
        task = db.session.get(Task, task_id)
        if not task: return False
        
        # 修改点 2: 使用 datetime.now() 获取当前系统时间(含时区修正)
        task.last_run = datetime.now()
        db.session.commit()

        script_path = task.script_path.lower()
        success = False
        
        try:
            if script_path.endswith('.side'):
                success = execute_selenium_script(task.name, task.script_path)
            elif script_path.endswith('.py'):
                success = execute_python_script(task.name, task.script_path)
            elif script_path.endswith('.ascr'):
                success = execute_actiona_script(task.name, task.script_path)
            elif script_path.endswith('.autokey'):
                # AutoKey 使用文件名（不带后缀）作为脚本ID
                success = execute_autokey_script(Path(task.script_path).stem, task.name)
            else:
                logger.error(f"不支持的脚本类型: {script_path}")
                success = False
            
            task.last_status = 'Success' if success else 'Failed'
            db.session.commit()
            return success

        except Exception as e:
            logger.error(f"执行任务异常 {task.name}: {e}")
            task.last_status = 'Error'
            db.session.commit()
            return False

# --- 1. 执行 Selenium IDE (.side) ---
def execute_selenium_script(task_name, script_path):
    from scripts.task_executor import SeleniumIDEExecutor, send_telegram_notification, send_email_notification
    bot_token, chat_id = get_telegram_config()
    
    # 注入桌面环境
    os.environ.update(get_desktop_env())
    
    try:
        executor = SeleniumIDEExecutor(script_path)
        success, message = executor.execute()
        
        # 发送 Telegram
        if bot_token and chat_id:
            send_telegram_notification(f"{task_name} (Selenium)", success, message, bot_token, chat_id)
        
        # 发送邮件
        send_email_notification(f"{task_name} (Selenium)", success, message)
        
        return success
    except Exception as e:
        logger.error(f"Selenium执行错误: {e}")
        return False

# --- 2. 执行 Playwright/Python (.py) ---
def execute_python_script(task_name, script_path):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    
    try:
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )
        success = result.returncode == 0
        log_msg = (result.stdout + "\n" + result.stderr).strip()
        if not log_msg: log_msg = "脚本执行完成 (无控制台输出)"
        
        if success:
            logger.info(f"Python脚本 {task_name} 执行成功")
        else:
            logger.error(f"Python脚本执行失败: {result.stderr}")
            
        from scripts.task_executor import send_telegram_notification, send_email_notification
        
        # 发送 Telegram
        if bot_token and chat_id:
            send_telegram_notification(f"{task_name} (Playwright)", success, log_msg, bot_token, chat_id)
            
        # 发送邮件
        send_email_notification(f"{task_name} (Playwright)", success, log_msg)
            
        return success
    except Exception as e:
        logger.error(f"Python执行异常: {e}")
        return False

# --- 3. 执行 Actiona (.ascr) ---
def execute_actiona_script(task_name, script_path):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    
    try:
        # -C: 执行后关闭, -e: 自动执行
        result = subprocess.run(
            ['actiona', '-s', script_path, '-e', '-C'],
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )
        success = result.returncode == 0
        log_msg = (result.stdout + "\n" + result.stderr).strip()
        if not log_msg: log_msg = "Actiona 任务已触发"

        if success:
            logger.info(f"Actiona脚本 {task_name} 执行成功")
        else:
            logger.error(f"Actiona脚本执行失败: {result.stderr}")

        from scripts.task_executor import send_telegram_notification, send_email_notification
        
        # 发送 Telegram
        if bot_token and chat_id:
            send_telegram_notification(f"{task_name} (Actiona)", success, log_msg, bot_token, chat_id)
        
        # 发送邮件
        send_email_notification(f"{task_name} (Actiona)", success, log_msg)
            
        return success
    except Exception as e:
        logger.error(f"Actiona执行异常: {e}")
        return False

# --- 4. 执行 AutoKey (.autokey) ---
def execute_autokey_script(script_stem, task_name):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    
    try:
        # 这里的 env 必须包含正确的 DBUS_SESSION_BUS_ADDRESS
        result = subprocess.run(
            ['autokey-run', '-s', script_stem],
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )
        
        success = result.returncode == 0
        log_msg = (result.stdout + "\n" + result.stderr).strip()
        if not log_msg: log_msg = "命令已发送 (无控制台输出)"
        
        if success:
            logger.info(f"AutoKey脚本 {script_stem} 执行成功")
        else:
            logger.error(f"AutoKey脚本执行失败: {result.stderr}")
            
        from scripts.task_executor import send_telegram_notification, send_email_notification
        
        # 发送 Telegram
        if bot_token and chat_id:
            send_telegram_notification(f"{task_name} (AutoKey)", success, log_msg, bot_token, chat_id)
            
        # 发送邮件
        send_email_notification(f"{task_name} (AutoKey)", success, log_msg)

        return success
    except Exception as e:
        logger.error(f"AutoKey执行异常: {e}")
        return False

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        if not User.query.filter_by(username=admin_username).first():
            user = User(username=admin_username, password=admin_password)
            db.session.add(user)
            db.session.commit()
            print(f'已创建默认管理员账号: {admin_username}')
        tasks = Task.query.filter_by(enabled=True).all()
        for task in tasks:
            try:
                schedule_task(task)
                print(f'已加载任务: {task.name}')
            except Exception as e:
                print(f'加载任务失败 {task.name}: {e}')
    print('='*50)
    print('自动化全能管理平台已启动')
    print(f'Web 界面: http://0.0.0.0:5000')
    print(f'支持脚本: .side (Selenium), .py (Playwright), .ascr (Actiona), .autokey')
    print('='*50)
    app.run(host='0.0.0.0', port=5000, debug=False)
