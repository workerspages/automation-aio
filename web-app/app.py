import os
import sys
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytz

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# 确保脚本目录在路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')

# --- 数据库连接配置 ---
def get_database_uri():
    db_host = os.environ.get('MARIADB_HOST')
    if db_host:
        db_user = os.environ.get('MARIADB_USER', 'root')
        db_pass = os.environ.get('MARIADB_PASSWORD', '')
        db_port = os.environ.get('MARIADB_PORT', '3306')
        db_name = os.environ.get('MARIADB_DB', 'automation')
        return f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    return os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:////app/data/tasks.db')

app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- 调度器配置 ---
SYSTEM_TZ_STR = os.environ.get('TZ', 'Asia/Shanghai')
SYSTEM_TZ = pytz.timezone(SYSTEM_TZ_STR)

job_defaults = {
    'misfire_grace_time': 3600,
    'coalesce': True,
    'max_instances': 3
}
scheduler = BackgroundScheduler(timezone=SYSTEM_TZ, job_defaults=job_defaults)
scheduler.start()

task_executor_pool = ThreadPoolExecutor(max_workers=5)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 目录配置 ---
BASE_DIRS = {
    'downloads': Path(os.environ.get('SCRIPTS_DIR', '/home/headless/Downloads')),
    'autokey': Path('/home/headless/.config/autokey/data/MyScripts')
}

for p in BASE_DIRS.values():
    try: p.mkdir(parents=True, exist_ok=True)
    except: pass

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
    cron_expression = db.Column(db.String(100), nullable=True) 
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    last_status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    schedule_type = db.Column(db.String(20), default='cron') 
    random_start = db.Column(db.String(10), nullable=True)   
    random_end = db.Column(db.String(10), nullable=True)     

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
    
    if not target_dir.exists():
        try: target_dir.mkdir(parents=True, exist_ok=True)
        except: return jsonify({'files': [], 'error': 'Directory not found'}), 404

    try:
        paths = sorted(target_dir.iterdir(), key=os.path.getmtime, reverse=True)
        for p in paths:
            if p.is_file() and p.name != '.DS_Store' and not p.name.endswith('.json'):
                files.append({
                    'name': p.name,
                    'size': p.stat().st_size,
                    'modified': datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                    'path': str(p)
                })
    except Exception as e:
        logger.error(f"List files error: {e}")
        return jsonify({'error': str(e)}), 500
        
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
            return jsonify({'error': '无法读取文件内容: ' + str(e)}), 400
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
        file_path.write_text(content, encoding='utf-8')
        # AutoKey JSON 自动生成
        if folder == 'autokey' and filename.endswith('.py'):
            json_path = file_path.with_suffix('.json')
            if not json_path.exists():
                script_config = {
                    "type": "script", "description": filename, "store": {}, "modes": [3],
                    "usageCount": 0, "prompt": False, "omitTrigger": False, "showInTrayMenu": False,
                    "filter": None, "hotkey": {"hotKey": None, "modifiers": []}
                }
                json_path.write_text(json.dumps(script_config, indent=4), encoding='utf-8')
                try: os.utime(str(BASE_DIRS['autokey']), None)
                except: pass

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
            if folder == 'autokey':
                json_path = file_path.with_suffix('.json')
                if json_path.exists(): os.remove(json_path)
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
    # 移除 .ascr 支持，仅保留 Python (.py) 和 Selenium (.side) 和 AutoKey
    supported_extensions = ['.side', '.py', '.autokey']
    
    for key, dir_path in BASE_DIRS.items():
        if dir_path.exists():
            try:
                for file in dir_path.rglob('*'):
                    if file.is_file() and \
                       file.suffix.lower() in supported_extensions and \
                       not file.name.endswith('.json') and \
                       not file.name.startswith('.'):
                        
                        display_name = f"[{key}] {file.name}"
                        scripts.append({'name': display_name, 'path': str(file)})
            except Exception as e:
                logger.error(f"Error scanning dir {dir_path}: {e}")
    return scripts

@app.route('/api/tasks', methods=['GET', 'POST'])
@login_required
def manage_tasks():
    if request.method == 'POST':
        data = request.json
        schedule_type = data.get('schedule_type', 'cron')
        random_start = data.get('random_start')
        random_end = data.get('random_end')
        cron_expression = data.get('cron_expression')

        if schedule_type == 'random' and random_start:
            try:
                hour, minute = random_start.split(':')
                cron_expression = f"{int(minute)} {int(hour)} * * *"
            except: pass

        task = Task(
            name=data['name'],
            script_path=data['script_path'],
            cron_expression=cron_expression,
            enabled=data.get('enabled', True),
            schedule_type=schedule_type,
            random_start=random_start,
            random_end=random_end
        )
        db.session.add(task)
        db.session.commit()
        if task.enabled: schedule_task(task)
        return jsonify({'success': True, 'task_id': task.id})
    
    tasks = Task.query.all()
    return jsonify([{
        'id': t.id, 'name': t.name, 'script_path': t.script_path,
        'cron_expression': t.cron_expression, 'enabled': t.enabled,
        'last_run': t.last_run.isoformat() if t.last_run else None,
        'last_status': t.last_status,
        'schedule_type': getattr(t, 'schedule_type', 'cron'),
        'random_start': getattr(t, 'random_start', ''),
        'random_end': getattr(t, 'random_end', '')
    } for t in tasks])

@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task: return jsonify({'error': 'Task not found'}), 404
    
    if request.method == 'GET':
        return jsonify({
            'id': task.id, 'name': task.name, 'script_path': task.script_path,
            'cron_expression': task.cron_expression, 'enabled': task.enabled,
            'last_run': task.last_run.isoformat() if task.last_run else None,
            'last_status': task.last_status,
            'schedule_type': getattr(task, 'schedule_type', 'cron'),
            'random_start': getattr(task, 'random_start', ''),
            'random_end': getattr(task, 'random_end', '')
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
        task.enabled = data.get('enabled', task.enabled)
        schedule_type = data.get('schedule_type', 'cron')
        task.schedule_type = schedule_type
        
        if schedule_type == 'random':
            task.random_start = data.get('random_start')
            task.random_end = data.get('random_end')
            if task.random_start:
                try:
                    hour, minute = task.random_start.split(':')
                    task.cron_expression = f"{int(minute)} {int(hour)} * * *"
                except: pass
        else:
            task.cron_expression = data.get('cron_expression', task.cron_expression)
            task.random_start = None
            task.random_end = None

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
    try:
        with app_instance.app_context():
            execute_script_core(task_id)
    except Exception as e:
        import traceback
        traceback.print_exc()

def execute_script_core(task_id):
    task = db.session.get(Task, task_id)
    if not task: return False
    
    print(f"🚀 Executing task: {task.name} ({task.script_path})")
    task.last_run = datetime.now(SYSTEM_TZ).replace(tzinfo=None)
    db.session.commit()

    script_path = task.script_path
    if script_path.startswith("[downloads] "): script_path = script_path.replace("[downloads] ", "", 1)
    if script_path.startswith("[autokey] "): script_path = script_path.replace("[autokey] ", "", 1)
    
    success = False
    try:
        if 'autokey/data' in script_path or 'MyScripts' in script_path:
             stem = Path(script_path).stem
             print(f"🔄 Detected AutoKey script: {stem}")
             success = execute_autokey_script(stem, task.name)
        elif script_path.lower().endswith('.py'):
            print(f"🐍 Running Python script: {script_path}")
            success = execute_python_script(task.name, script_path)
        elif script_path.lower().endswith('.side'):
            success = execute_selenium_script(task.name, script_path)
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

def execute_script(task_id):
    with app.app_context(): execute_script_core(task_id)

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
                    env[parts[0].strip()] = parts[1].strip().strip("'").strip('"')
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
        cmd = [sys.executable, script_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        success = result.returncode == 0
        log_msg = (result.stdout + "\n" + result.stderr).strip() or "No output"
        
        if success: logger.info(f"Python {task_name} Success")
        else: logger.error(f"Python {task_name} Failed: {result.stderr}")
        
        script_type = "(Py)"
        try:
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                if 'playwright' in content: script_type = "(Playwright)"
                elif 'selenium' in content: script_type = "(Selenium)"
        except: pass
        
        from scripts.task_executor import send_telegram_notification, send_email_notification
        if bot_token and chat_id: send_telegram_notification(f"{task_name} {script_type}", success, log_msg, bot_token, chat_id)
        send_email_notification(f"{task_name} {script_type}", success, log_msg)
        return success
    except Exception as e:
        logger.error(f"Python Exception: {e}")
        return False

def execute_autokey_script(script_stem, task_name):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    try:
        cmd = ['autokey-run', '-s', script_stem]
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

def schedule_task(task):
    if task.enabled:
        try:
            trigger = None
            if getattr(task, 'schedule_type', 'cron') == 'random' and task.random_start and task.random_end:
                try:
                    start_h, start_m = map(int, task.random_start.split(':'))
                    end_h, end_m = map(int, task.random_end.split(':'))
                    now = datetime.now(SYSTEM_TZ)
                    start_dt = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                    end_dt = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
                    if end_dt < start_dt: end_dt += timedelta(days=1)
                    diff_seconds = int((end_dt - start_dt).total_seconds())
                    if diff_seconds < 60: diff_seconds = 60
                    trigger = CronTrigger(hour=start_h, minute=start_m, jitter=diff_seconds, timezone=SYSTEM_TZ)
                except: trigger = CronTrigger.from_crontab(task.cron_expression, timezone=SYSTEM_TZ)
            else:
                trigger = CronTrigger.from_crontab(task.cron_expression, timezone=SYSTEM_TZ)
            
            if trigger:
                scheduler.add_job(func=execute_script, trigger=trigger, id=f'task_{task.id}', args=[task.id], replace_existing=True)
        except Exception as e:
            logger.error(f'Schedule failed for {task.name}: {e}')

def initialize_system():
    with app.app_context():
        try:
            admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
            if not User.query.filter_by(username=admin_user).first():
                user = User(username=admin_user)
                user.set_password(os.environ.get('ADMIN_PASSWORD', 'admin123'))
                db.session.add(user)
                db.session.commit()
            for task in Task.query.filter_by(enabled=True).all(): schedule_task(task)
        except Exception as e: print(f"Init error: {e}")

initialize_system()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
