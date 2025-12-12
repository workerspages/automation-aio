import os
import sys
import json
import logging
import time
import subprocess
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 引入 pytz 处理时区
import pytz

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# 确保脚本目录在路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:////app/data/tasks.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- 调度器配置 ---
# 1. 强制时区
SYSTEM_TZ_STR = os.environ.get('TZ', 'Asia/Shanghai')
SYSTEM_TZ = pytz.timezone(SYSTEM_TZ_STR)

# 2. 配置调度器，增加 misfire_grace_time 全局默认值 (1小时)
job_defaults = {
    'misfire_grace_time': 3600,
    'coalesce': True,
    'max_instances': 3
}
scheduler = BackgroundScheduler(timezone=SYSTEM_TZ, job_defaults=job_defaults)
scheduler.start()

# 线程池
task_executor_pool = ThreadPoolExecutor(max_workers=5)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 目录配置 ---
BASE_DIRS = {
    'downloads': Path(os.environ.get('SCRIPTS_DIR', '/home/headless/Downloads')),
    'autokey': Path('/home/headless/.config/autokey/data/MyScripts')
}

for p in BASE_DIRS.values():
    try:
        p.mkdir(parents=True, exist_ok=True)
    except:
        pass

# --- 数据库模型 ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    script_path = db.Column(db.String(500), nullable=False)
    cron_expression = db.Column(db.String(100), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    last_status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    schedule_type = db.Column(db.String(20), default='cron') 
    random_delay_max = db.Column(db.Integer, default=0)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- 路由 ---
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
        if user and user.check_password(password):
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
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200

# --- 文件管理 API ---
def get_target_dir(folder_key):
    return BASE_DIRS.get(folder_key, BASE_DIRS['downloads'])

@app.route('/api/files', methods=['GET'])
@login_required
def list_files_api():
    folder = request.args.get('folder', 'downloads')
    target_dir = get_target_dir(folder)
    files = []
    if target_dir.exists():
        try:
            paths = sorted(target_dir.iterdir(), key=os.path.getmtime, reverse=True)
            for p in paths:
                # 过滤 AutoKey 的 .json 文件，只显示脚本
                if p.is_file() and p.name != '.DS_Store' and not p.name.endswith('.json'):
                    files.append({
                        'name': p.name,
                        'size': p.stat().st_size,
                        'modified': datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                        'path': str(p)
                    })
        except Exception as e:
            logger.error(f"List files error: {e}")
    return jsonify({'files': files, 'current_folder': folder})

@app.route('/api/files/content', methods=['GET'])
@login_required
def get_file_content():
    folder = request.args.get('folder', 'downloads')
    filename = request.args.get('filename')
    if not filename: return jsonify({'error': 'Filename required'}), 400
    filename = secure_filename(filename)
    target_dir = get_target_dir(folder)
    file_path = target_dir / filename
    if file_path.exists():
        try:
            return jsonify({'content': file_path.read_text(encoding='utf-8')})
        except Exception as e:
            return jsonify({'error': '无法读取文件内容'}), 400
    return jsonify({'error': '文件不存在'}), 404

@app.route('/api/files', methods=['POST'])
@login_required
def save_file():
    data = request.json
    filename = secure_filename(data.get('filename'))
    content = data.get('content')
    folder = data.get('folder', 'downloads')
    
    if not filename: return jsonify({'error': '文件名不能为空'}), 400
    
    target_dir = get_target_dir(folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = target_dir / filename
    try:
        # 1. 保存脚本文件
        file_path.write_text(content, encoding='utf-8')
        
        # 2. [AutoKey 特殊处理] 自动生成 .json 定义文件
        if folder == 'autokey' and filename.endswith('.py'):
            json_path = file_path.with_suffix('.json')
            if not json_path.exists():
                # 创建默认的 AutoKey JSON 配置
                script_config = {
                    "type": "script",
                    "description": filename,
                    "store": {},
                    "modes": [3], # 3 = Hotkey is handled by AutoKey (Standard)
                    "usageCount": 0,
                    "prompt": False,
                    "omitTrigger": False,
                    "showInTrayMenu": False,
                    "filter": None,
                    "hotkey": {"hotKey": None, "modifiers": []}
                }
                json_path.write_text(json.dumps(script_config, indent=4), encoding='utf-8')
                logger.info(f"AutoKey JSON generated: {json_path}")
                
                # 尝试触发布局刷新 (touch top-level folder)
                os.utime(str(BASE_DIRS['autokey']), None)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['DELETE'])
@login_required
def delete_file():
    folder = request.args.get('folder', 'downloads')
    filename = request.args.get('filename')
    if not filename: return jsonify({'error': 'Filename required'}), 400
    filename = secure_filename(filename)
    target_dir = get_target_dir(folder)
    file_path = target_dir / filename
    if file_path.exists():
        try:
            os.remove(file_path)
            # 同时删除 AutoKey JSON
            if folder == 'autokey':
                json_path = file_path.with_suffix('.json')
                if json_path.exists():
                    os.remove(json_path)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': '文件不存在'}), 404

# --- 任务 API ---
@app.route('/api/scripts', methods=['GET'])
@login_required
def list_scripts():
    scripts = get_available_scripts()
    return jsonify(scripts)

def get_available_scripts():
    scripts = []
    supported_extensions = ['.side', '.py', '.ascr', '.autokey']
    for key, dir_path in BASE_DIRS.items():
        if dir_path.exists():
            for file in dir_path.rglob('*'):
                # 排除 autokey json
                if file.is_file() and file.suffix.lower() in supported_extensions and not file.name.endswith('.json'):
                    display_name = f"[{key}] {file.name}"
                    scripts.append({'name': display_name, 'path': str(file)})
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
            enabled=data.get('enabled', True),
            schedule_type=data.get('schedule_type', 'cron'),
            random_delay_max=data.get('random_delay_max', 0)
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
            'last_status': t.last_status,
            'schedule_type': getattr(t, 'schedule_type', 'cron'),
            'random_delay_max': getattr(t, 'random_delay_max', 0)
        } for t in tasks
    ])

@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task: return jsonify({'error': 'Task not found'}), 404
    if request.method == 'GET':
        return jsonify({
            'id': task.id,
            'name': task.name,
            'script_path': task.script_path,
            'cron_expression': task.cron_expression,
            'enabled': task.enabled,
            'last_run': task.last_run.isoformat() if task.last_run else None,
            'last_status': task.last_status,
            'schedule_type': getattr(task, 'schedule_type', 'cron'),
            'random_delay_max': getattr(task, 'random_delay_max', 0)
        })
    if request.method == 'DELETE':
        try: scheduler.remove_job(f'task_{task_id}')
        except: pass
        db.session.delete(task)
        db.session.commit()
        return jsonify({'success': True})
    if request.method == 'PUT':
        data = request.json
        task.name = data.get('name', task.name)
        task.cron_expression = data.get('cron_expression', task.cron_expression)
        task.enabled = data.get('enabled', task.enabled)
        task.schedule_type = data.get('schedule_type', 'cron')
        task.random_delay_max = data.get('random_delay_max', 0)
        db.session.commit()
        try: scheduler.remove_job(f'task_{task_id}')
        except: pass
        if task.enabled: schedule_task(task)
        return jsonify({'success': True})

@app.route('/api/tasks/<int:task_id>/run', methods=['POST'])
@login_required
def run_task_now(task_id):
    task = db.session.get(Task, task_id)
    if not task: return jsonify({'error': 'Task not found'}), 404
    
    # 将任务提交到线程池，并传入 app 实例以建立上下文
    task_executor_pool.submit(run_task_with_context, app, task_id)
    return jsonify({'success': True, 'message': '任务已加入执行队列'})

@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = db.session.get(Task, task_id)
    if not task: return jsonify({'error': 'Task not found'}), 404
    task.enabled = not task.enabled
    db.session.commit()
    try:
        if task.enabled: schedule_task(task)
        else: scheduler.remove_job(f'task_{task.id}')
    except: pass
    return jsonify({'success': True, 'enabled': task.enabled})

# --- 执行逻辑 ---

def run_task_with_context(app_instance, task_id):
    """
    专门的线程入口函数，确保 Flask Context 和 DB Session 正确
    """
    print(f"🧵 Thread started for task {task_id}")
    try:
        with app_instance.app_context():
            # 在新线程中执行
            success = execute_script_core(task_id)
            print(f"🧵 Thread finished for task {task_id}, Success: {success}")
    except Exception as e:
        print(f"❌ Thread error: {e}")
        import traceback
        traceback.print_exc()

def execute_script_core(task_id):
    """
    核心执行逻辑，需在 App Context 内调用
    """
    task = db.session.get(Task, task_id)
    if not task:
        print(f"❌ execute_script_core: Task {task_id} not found in DB")
        return False
    
    print(f"🚀 Executing task: {task.name} ({task.script_path})")
    
    # 更新运行时间
    task.last_run = datetime.now()
    db.session.commit()

    script_path = task.script_path
    # 简单的路径清理
    if script_path.startswith("[downloads] "): script_path = script_path.replace("[downloads] ", "", 1)
    if script_path.startswith("[autokey] "): script_path = script_path.replace("[autokey] ", "", 1)
    
    success = False
    
    try:
        if script_path.lower().endswith('.side'):
            success = execute_selenium_script(task.name, script_path)
        elif script_path.lower().endswith('.py'):
            success = execute_python_script(task.name, script_path)
        elif script_path.lower().endswith('.ascr'):
            success = execute_actiona_script(task.name, script_path)
        elif 'autokey' in script_path.lower(): # 简单判断
            # AutoKey 只需要文件名 stem
            stem = Path(script_path).stem
            success = execute_autokey_script(stem, task.name)
        else:
            logger.error(f"Unsupported script type: {script_path}")
            success = False
        
        task.last_status = 'Success' if success else 'Failed'
        db.session.commit()
        return success

    except Exception as e:
        logger.error(f"Execution Exception {task.name}: {e}")
        task.last_status = 'Error'
        db.session.commit()
        return False

# 调度器的回调函数 (APScheduler 也会在线程中运行)
def execute_script(task_id):
    # APScheduler 没有 request context，需要手动 push app context
    with app.app_context():
        execute_script_core(task_id)

# --- 具体执行器 ---

def get_desktop_env():
    env = os.environ.copy()
    env['DISPLAY'] = ':1'
    dbus_file = Path('/home/headless/.dbus-env')
    if dbus_file.exists():
        try:
            content = dbus_file.read_text().strip()
            if content.startswith('export '):
                parts = content.replace('export ', '').split('=', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().strip("'").strip('"')
                    env[key] = value
        except: pass
    return env

def get_telegram_config():
    return os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')

def execute_selenium_script(task_name, script_path):
    from scripts.task_executor import SeleniumIDEExecutor, send_telegram_notification, send_email_notification
    bot_token, chat_id = get_telegram_config()
    os.environ.update(get_desktop_env())
    try:
        executor = SeleniumIDEExecutor(script_path)
        success, message = executor.execute()
        if bot_token and chat_id: send_telegram_notification(f"{task_name} (Selenium)", success, message, bot_token, chat_id)
        send_email_notification(f"{task_name} (Selenium)", success, message)
        return success
    except Exception as e:
        logger.error(f"Selenium Error: {e}")
        return False

def execute_python_script(task_name, script_path):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    try:
        # 使用 sys.executable 确保使用 venv 中的 python
        cmd = [sys.executable, script_path]
        print(f"Running command: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        
        success = result.returncode == 0
        log_msg = (result.stdout + "\n" + result.stderr).strip() or "No output"
        
        if success: logger.info(f"Python {task_name} Success: {log_msg[:100]}...")
        else: logger.error(f"Python {task_name} Failed: {result.stderr}")
        
        from scripts.task_executor import send_telegram_notification, send_email_notification
        if bot_token and chat_id: send_telegram_notification(f"{task_name} (Py)", success, log_msg, bot_token, chat_id)
        send_email_notification(f"{task_name} (Py)", success, log_msg)
        return success
    except Exception as e:
        logger.error(f"Python Exception: {e}")
        return False

def execute_actiona_script(task_name, script_path):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    try:
        result = subprocess.run(['actiona', '-s', script_path, '-e', '-C'], capture_output=True, text=True, timeout=300, env=env)
        success = result.returncode == 0
        log_msg = (result.stdout + "\n" + result.stderr).strip() or "Actiona Triggered"
        from scripts.task_executor import send_telegram_notification, send_email_notification
        if bot_token and chat_id: send_telegram_notification(f"{task_name} (Actiona)", success, log_msg, bot_token, chat_id)
        send_email_notification(f"{task_name} (Actiona)", success, log_msg)
        return success
    except Exception as e:
        logger.error(f"Actiona Error: {e}")
        return False

def execute_autokey_script(script_stem, task_name):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    try:
        # AutoKey 必须在运行中
        cmd = ['autokey-run', '-s', script_stem]
        print(f"Running AutoKey: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        
        success = result.returncode == 0
        log_msg = (result.stdout + "\n" + result.stderr).strip() or "Command Sent"
        
        if success: logger.info(f"AutoKey {script_stem} Success")
        else: logger.error(f"AutoKey Failed: {result.stderr}")
        
        from scripts.task_executor import send_telegram_notification, send_email_notification
        if bot_token and chat_id: send_telegram_notification(f"{task_name} (AutoKey)", success, log_msg, bot_token, chat_id)
        send_email_notification(f"{task_name} (AutoKey)", success, log_msg)
        return success
    except Exception as e:
        logger.error(f"AutoKey Error: {e}")
        return False

# --- 调度逻辑 ---
def schedule_task(task):
    """
    将任务添加到 APScheduler
    """
    if task.enabled:
        try:
            trigger_kwargs = {}
            if getattr(task, 'schedule_type', 'cron') == 'random':
                jitter_seconds = getattr(task, 'random_delay_max', 0)
                if jitter_seconds > 0:
                    trigger_kwargs['jitter'] = jitter_seconds
            
            trigger = CronTrigger.from_crontab(
                task.cron_expression, 
                timezone=SYSTEM_TZ, 
                **trigger_kwargs
            )
            
            job = scheduler.add_job(
                func=execute_script,
                trigger=trigger,
                id=f'task_{task.id}',
                args=[task.id],
                replace_existing=True
            )
            
            logger.info(f'✅ Task {task.name} scheduled. Next run: {job.next_run_time}')
            
        except Exception as e:
            logger.error(f'Schedule failed for {task.name}: {e}')

def initialize_system():
    with app.app_context():
        try:
            db.create_all()
            # 迁移逻辑... (简化)
            with db.engine.connect() as conn:
                try: conn.execute(text('ALTER TABLE task ADD COLUMN schedule_type VARCHAR(20) DEFAULT "cron"'))
                except: pass
                try: conn.execute(text('ALTER TABLE task ADD COLUMN random_delay_max INTEGER DEFAULT 0'))
                except: pass
                conn.commit()
            
            admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
            if not User.query.filter_by(username=admin_user).first():
                user = User(username=admin_user)
                user.set_password(os.environ.get('ADMIN_PASSWORD', 'admin123'))
                db.session.add(user)
                db.session.commit()
            
            tasks = Task.query.filter_by(enabled=True).all()
            for task in tasks:
                schedule_task(task)
        except Exception as e:
            print(f"Init error: {e}")

initialize_system()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
