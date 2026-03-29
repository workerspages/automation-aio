import os
import sys
import json
import logging
import subprocess
import time
from datetime import datetime, timedelta
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
_secret_key = os.environ.get('SECRET_KEY', '')
if not _secret_key:
    import warnings
    warnings.warn('⚠️ SECRET_KEY 未设置，正在使用不安全的默认值，请配置环境变量！', stacklevel=1)
    _secret_key = 'dev-secret-key-change-this'
app.config['SECRET_KEY'] = _secret_key

# --- 数据库连接配置 ---
def get_database_uri():
    db_host = os.environ.get('MARIADB_HOST', '').strip('"\'')
    if db_host:
        db_user = os.environ.get('MARIADB_USER', 'root').strip('"\'')
        db_pass = os.environ.get('MARIADB_PASSWORD', '').strip('"\'')
        db_port = os.environ.get('MARIADB_PORT', '3306').strip('"\'')
        db_name = os.environ.get('MARIADB_DB', 'automation').strip('"\'')
        
        uri = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        
        # SSL Configuration
        # Enable if explicitly set to true OR if a custom CA path is provided
        ssl_enabled = os.environ.get('DB_SSL_ENABLED', 'false').lower() == 'true'
        ca_path = os.environ.get('DB_SSL_CA_PATH')
        
        if ssl_enabled or ca_path:
            # Defaults to system CA if not specified
            final_ca_path = ca_path if ca_path else '/etc/ssl/certs/ca-certificates.crt'
            uri += f"&ssl_ca={final_ca_path}&ssl_verify_cert=true&ssl_verify_identity=true"
            
        return uri
    return os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:////app/data/tasks.db')

app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def auto_backup_browser_state():
    try:
        from scripts.browser_sync import backup_browser_profile
        zip_bytes = backup_browser_profile()
        if zip_bytes:
            with app.app_context():
                record = BrowserProfile.query.first()
                if not record:
                    record = BrowserProfile(profile_data=zip_bytes)
                    db.session.add(record)
                else:
                    record.profile_data = zip_bytes
                db.session.commit()
            import logging
            logging.info("🚗 Auto-backup of browser state completed.")
    except Exception as e:
        import logging
        logging.getLogger().error(f"Auto-backup browser state failed: {e}")

# --- 调度器配置 ---
SYSTEM_TZ_STR = os.environ.get('TZ', 'Asia/Shanghai')
SYSTEM_TZ = pytz.timezone(SYSTEM_TZ_STR)

job_defaults = {
    'misfire_grace_time': 300,  # [FIX] 120→300: 错过触发后 5 分钟内补执行，给看门狗恢复留时间
    'coalesce': True,
    'max_instances': 1  # 闹钟钩子仅需毫秒即返回，永远不会实例堆叠，1 为最纯净设计
}
scheduler = BackgroundScheduler(timezone=SYSTEM_TZ, job_defaults=job_defaults)
# 追加浏览器凭据每 2 小时自动云端快照
scheduler.add_job(
    func=auto_backup_browser_state,
    trigger=CronTrigger(minute=0, hour='*/2'),  # Every 2 hours
    id='auto_browser_backup',
    name='Backup Browser State to DB',
    replace_existing=True
)

# [FIX] 调度器事件监听，用于调试任务触发问题
from apscheduler.events import (EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED,
                                 EVENT_JOB_ADDED, EVENT_JOB_REMOVED,
                                 EVENT_SCHEDULER_SHUTDOWN, EVENT_SCHEDULER_STARTED)

def _on_job_executed(event):
    import logging as _log
    _logger = _log.getLogger('scheduler')
    if hasattr(event, 'exception') and event.exception:
        _logger.error(f"❌ Job {event.job_id} raised an exception: {event.exception}")
    else:
        _logger.info(f"✅ Job {event.job_id} executed successfully at {event.scheduled_run_time}")

def _on_job_missed(event):
    import logging as _log
    _logger = _log.getLogger('scheduler')
    _logger.warning(f"⚠️ Job {event.job_id} was MISSED at {event.scheduled_run_time}")

def _on_job_lifecycle(event):
    """追踪 Job 增删生命周期"""
    import logging as _log
    _logger = _log.getLogger('scheduler')
    event_name = event.__class__.__name__
    job_id = getattr(event, 'job_id', 'unknown')
    _logger.info(f"📋 Job lifecycle: {event_name} for {job_id}")

def _on_scheduler_state(event):
    """调度器自身状态变化告警"""
    import logging as _log
    _logger = _log.getLogger('scheduler')
    event_name = event.__class__.__name__
    _logger.critical(f"🚨 Scheduler state change: {event_name}")

scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)
scheduler.add_listener(_on_job_lifecycle, EVENT_JOB_ADDED | EVENT_JOB_REMOVED)
scheduler.add_listener(_on_scheduler_state, EVENT_SCHEDULER_SHUTDOWN | EVENT_SCHEDULER_STARTED)
scheduler.start()

# [FIX] 线程池扩容 1→2: 防止单线程卡死导致新任务无法提交
task_executor_pool = ThreadPoolExecutor(max_workers=2)

def _get_healthy_pool():
    """获取一个健康的线程池，如果当前池已关闭则重建"""
    global task_executor_pool
    try:
        if task_executor_pool._shutdown:
            logger.warning("🔄 ThreadPool was shut down, recreating...")
            task_executor_pool = ThreadPoolExecutor(max_workers=2)
    except Exception:
        task_executor_pool = ThreadPoolExecutor(max_workers=2)
    return task_executor_pool

# [FIX] 调度器看门狗线程：每 90 秒自检调度器存活状态与 Job 注册完整性
def _scheduler_watchdog():
    """调度器看门狗 (心脏监护仪)
    
    独立守夜线程，每 90 秒执行一次全面健康检查:
    1. APScheduler 是否仍在运行
    2. 所有 enabled Task 是否都有对应的 APScheduler Job
    3. 线程池是否处于可用状态
    如果检测到异常，自动修复。
    """
    _wlog = logging.getLogger('watchdog')
    # 启动后先等待系统初始化完成
    time.sleep(30)
    _wlog.info("🐕 Scheduler watchdog started.")
    while True:
        try:
            time.sleep(90)
            with app.app_context():
                # --- 检查 1: 调度器是否存活 ---
                if not scheduler.running:
                    _wlog.critical("🚨 WATCHDOG: Scheduler is DEAD! Restarting...")
                    try:
                        scheduler.start()
                        _wlog.info("✅ WATCHDOG: Scheduler restarted successfully.")
                    except Exception as e:
                        _wlog.error(f"Failed to restart scheduler: {e}")
                        continue
                
                # --- 检查 2: 所有 enabled 任务是否都有注册的 Job ---
                enabled_tasks = Task.query.filter_by(enabled=True).all()
                registered_job_ids = {job.id for job in scheduler.get_jobs()}
                
                missing_count = 0
                for task in enabled_tasks:
                    job_id = f'task_{task.id}'
                    if job_id not in registered_job_ids:
                        _wlog.warning(f"🚨 WATCHDOG: Job {job_id} ({task.name}) MISSING from scheduler! Re-registering...")
                        schedule_task(task)
                        missing_count += 1
                
                if missing_count > 0:
                    _wlog.warning(f"🔧 WATCHDOG: Re-registered {missing_count} missing job(s).")
                
                # --- 检查 3: 线程池健康 ---
                pool = _get_healthy_pool()
                try:
                    pending = pool._work_queue.qsize()
                    if pending > 2:
                        _wlog.warning(f"⚠️ WATCHDOG: ThreadPool has {pending} pending tasks (possible blockage)")
                except Exception:
                    pass
                    
        except Exception as e:
            _wlog.error(f"WATCHDOG cycle error: {e}")

_watchdog_thread = threading.Thread(target=_scheduler_watchdog, daemon=True, name='scheduler-watchdog')
_watchdog_thread.start()

# === 全局进程管理器：实现抢占强杀机制 ===
import threading
import signal
ACTIVE_PROCESSES = []
active_process_lock = threading.Lock()

def kill_active_processes():
    logger.warning("☠️ Preemption triggered: Killing all active task processes...")
    with active_process_lock:
        for p in ACTIVE_PROCESSES:
            try:
                p.terminate()
            except: pass
            try:
                p.kill()
            except: pass
        ACTIVE_PROCESSES.clear()
        
    try:
        # Also clean up orphaned automation browsers and scripts
        subprocess.run("pkill -9 -f 'chrome'", shell=True, capture_output=True, timeout=5)
        subprocess.run("pkill -9 -f 'chromium'", shell=True, capture_output=True, timeout=5)
        subprocess.run("pkill -9 -f 'autokey-run'", shell=True, capture_output=True, timeout=5)
        subprocess.run("pkill -9 -f 'autokey-gtk'", shell=True, capture_output=True, timeout=5)
        
        # [FIX] 清除 SingletonLock，防止强杀后残留锁文件阻止下次 Chrome 启动
        for lock_path in ['/home/headless/.config/google-chrome/SingletonLock',
                          '/home/headless/.config/chromium/SingletonLock']:
            try:
                os.remove(lock_path)
            except FileNotFoundError:
                pass
        
        # [HOTFIX] 清除 Chrome 异常崩溃导致启动弹出“恢复页面”的干扰气泡 (防止遮挡自动化坐标)
        for pre_path in ['/home/headless/.config/google-chrome/Default/Preferences', '/home/headless/.config/chromium/Default/Preferences']:
            subprocess.run(f"sed -i 's/\"exited_cleanly\":false/\"exited_cleanly\":true/g' {pre_path} 2>/dev/null", shell=True, timeout=3)
            subprocess.run(f"sed -i 's/\"exit_type\":\"Crashed\"/\"exit_type\":\"Normal\"/g' {pre_path} 2>/dev/null", shell=True, timeout=3)
            subprocess.run(f"sed -i 's/\"exit_type\":\"SessionEnded\"/\"exit_type\":\"Normal\"/g' {pre_path} 2>/dev/null", shell=True, timeout=3)
    except: pass

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler(),
                        logging.FileHandler('/app/logs/app.log', encoding='utf-8')
                    ])
logger = logging.getLogger(__name__)

# --- 目录配置 (关键修改：指向 Sample Scripts) ---
BASE_DIRS = {
    'downloads': Path(os.environ.get('SCRIPTS_DIR', '/home/headless/Downloads')),
    # AutoKey 脚本存放目录：MyScripts
    'autokey': Path('/home/headless/.config/autokey/data/MyScripts')
}

# 确保目录存在
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
    cron_expression = db.Column(db.String(100), nullable=True) 
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    last_status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    timeout = db.Column(db.Integer, default=600)
    
    schedule_type = db.Column(db.String(20), default='cron') 
    random_start = db.Column(db.String(10), nullable=True)   
    random_end = db.Column(db.String(10), nullable=True)     

class ScriptFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folder = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class BrowserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profile_data = db.Column(db.LargeBinary(length=(2**32)-1))  # 强制生成 LONGBLOB，解决 64KB 限制
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

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
    return '', 204  # 无 favicon 文件，返回 No Content 避免 404

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200

@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    """读取任务执行日志，支持按任务名过滤"""
    lines = int(request.args.get('lines', 200))
    keyword = request.args.get('keyword', '').strip()
    
    log_files = [
        '/app/logs/app.log',
        '/app/data/executor.log',
        '/app/logs/autokey.log'
    ]
    
    all_lines = []
    for log_path in log_files:
        try:
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                    file_lines = f.readlines()
                    # 取最后 N 行
                    tail = file_lines[-lines:] if len(file_lines) > lines else file_lines
                    all_lines.extend(tail)
        except Exception:
            pass
    
    # 按关键词过滤
    if keyword:
        all_lines = [l for l in all_lines if keyword.lower() in l.lower()]
    
    # 只返回最后 lines 行
    result = all_lines[-lines:]
    
    return jsonify({'logs': ''.join(result), 'total_lines': len(result)})

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
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except:
            return jsonify({'files': [], 'error': 'Directory not found'}), 404

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
        # 1. 保存脚本文件
        file_path.write_text(content, encoding='utf-8')
        
        # [NEW] 同步保存到外部数据库
        script_record = ScriptFile.query.filter_by(folder=folder, filename=filename).first()
        if script_record:
            script_record.content = content
        else:
            script_record = ScriptFile(folder=folder, filename=filename, content=content)
            db.session.add(script_record)
        db.session.commit()
        
        # 2. [AutoKey 特殊处理] 自动生成 .json 定义文件
        if folder == 'autokey' and filename.endswith('.py'):
            json_path = file_path.with_suffix('.json')
            if not json_path.exists():
                script_config = {
                    "type": "script",
                    "description": filename, # 这里保存的是完整文件名，例如 test.py
                    "store": {},
                    "modes": [3],
                    "usageCount": 0,
                    "prompt": False,
                    "omitTrigger": False,
                    "showInTrayMenu": False,
                    "filter": None,
                    "hotkey": {"hotKey": None, "modifiers": []}
                }
                json_path.write_text(json.dumps(script_config, indent=4), encoding='utf-8')
                # 触发 AutoKey 重载
                reload_autokey()

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Save file error: {e}")
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
                if json_path.exists():
                    os.remove(json_path)
                reload_autokey()
            
            # [NEW] 同步删除外部数据库记录
            script_record = ScriptFile.query.filter_by(folder=folder, filename=filename).first()
            if script_record:
                db.session.delete(script_record)
                db.session.commit()
                
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
    # 瘦身版仅支持 Python, Selenium Side, AutoKey
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

@app.route('/api/browser/backup', methods=['POST'])
@login_required
def manual_browser_backup():
    try:
        from scripts.browser_sync import backup_browser_profile
        zip_bytes = backup_browser_profile()
        if zip_bytes:
            with app.app_context():
                record = BrowserProfile.query.first()
                if not record:
                    record = BrowserProfile(profile_data=zip_bytes)
                    db.session.add(record)
                else:
                    record.profile_data = zip_bytes
                db.session.commit()
            return jsonify({'success': True, 'message': 'Browser state backed up successfully to cloud db.'})
        return jsonify({'error': 'No profile files found'}), 404
    except Exception as e:
        logger.error(f"Manual browser backup failed: {e}")
        return jsonify({'error': str(e)}), 500

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
            except:
                pass

        task = Task(
            name=data['name'],
            script_path=data['script_path'],
            cron_expression=cron_expression,
            enabled=data.get('enabled', True),
            schedule_type=schedule_type,
            random_start=random_start,
            random_end=random_end,
            timeout=data.get('timeout', 600)
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
            'random_start': getattr(t, 'random_start', ''),
            'random_end': getattr(t, 'random_end', ''),
            'timeout': getattr(t, 'timeout', 600)
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
            'random_start': getattr(task, 'random_start', ''),
            'random_end': getattr(task, 'random_end', ''),
            'timeout': getattr(task, 'timeout', 600)
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
        task.timeout = data.get('timeout', task.timeout)
        
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
    
    # 抢占机制：立刻清场排他
    kill_active_processes()
    
    safe_submit(_get_healthy_pool(), run_task_with_context, app, task_id)
    return jsonify({'success': True, 'message': '任务执行已强行接管并在后台启动'})

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

def _future_done_callback(future):
    """Future 完成回调：捕获被 ThreadPoolExecutor 静默吞掉的异常"""
    try:
        exc = future.exception(timeout=0)
        if exc:
            logger.error(f"❌ ThreadPool task raised unhandled exception: {exc}", exc_info=exc)
    except Exception:
        pass

def safe_submit(pool, fn, *args, **kwargs):
    """提交任务到线程池，自动附加异常监控回调"""
    future = pool.submit(fn, *args, **kwargs)
    future.add_done_callback(_future_done_callback)
    return future

def run_task_with_context(app_instance, task_id):
    logger.info(f"🧵 Thread started for task {task_id}")
    try:
        with app_instance.app_context():
            success = execute_script_core(task_id)
            logger.info(f"🧵 Thread finished for task {task_id}, Success: {success}")
    except Exception as e:
        logger.error(f"❌ Thread error for task {task_id}: {e}", exc_info=True)

def execute_script_core(task_id):
    """
    核心执行逻辑，需在 App Context 内调用
    """
    task = db.session.get(Task, task_id)
    if not task:
        logger.error(f"❌ execute_script_core: Task {task_id} not found in DB")
        return False
    
    logger.info(f"🚀 Executing task: {task.name} ({task.script_path})")
    
    # 抢占机制：清场当前正在执行的后台一切任务 (尤其是针对定时任务触发进来的)
    kill_active_processes()
    
    # 更新运行时间
    task.last_run = datetime.now(SYSTEM_TZ).replace(tzinfo=None)
    db.session.commit()

    script_path = task.script_path
    
    # 路径清理
    # 路径清理与绝对路径解析
    original_path = script_path
    if script_path.startswith("[downloads] "): 
        filename = script_path.replace("[downloads] ", "", 1)
        script_path = str(BASE_DIRS['downloads'] / filename)
    elif script_path.startswith("[autokey] "): 
        filename = script_path.replace("[autokey] ", "", 1)
        script_path = str(BASE_DIRS['autokey'] / filename)
    
    # 检查文件是否存在
    if not os.path.exists(script_path) and not ('autokey/data' in script_path or 'MyScripts' in script_path):
         # AutoKey 脚本可能只是目录或逻辑名，先不强制检查物理路径，但在 try block 里会处理
         # 这里主要拦截 Python/Side 脚本
         logger.error(f"❌ Script file not found: {script_path} (Original: {original_path})")
         task.last_status = 'File Missing'
         db.session.commit()
         return False
    
    success = False
    
    try:
        task_timeout = getattr(task, 'timeout', 600)
        try:
            task_timeout = int(task_timeout)
        except:
            task_timeout = 600
        if not task_timeout or task_timeout <= 0: task_timeout = 600
        
        # 优先识别 AutoKey (匹配 MyScripts 或 autokey/data)
        if 'autokey/data' in script_path or 'MyScripts' in script_path:
             # === 关键修复：传递完整文件名 (含后缀) ===
             script_name = Path(script_path).name
             logger.info(f"🔄 Detected AutoKey script by path: {script_name}")
             success = execute_autokey_script(script_name, task.name, timeout_sec=task_timeout)
             
        elif script_path.lower().endswith('.py'):
            logger.info(f"🐍 Running as standard Python script: {script_path}")
            success = execute_python_script(task.name, script_path, timeout_sec=task_timeout)
            
        elif script_path.lower().endswith('.side'):
            success = execute_selenium_script(task.name, script_path, timeout_sec=task_timeout)
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

def execute_scheduled_task(task_id):
    """调度专用毫秒级非阻塞钩子 (闹钟模式)

    APScheduler 线程触发后，本函数在数毫秒内完成以下工作并立即返回:
    1. 强杀当前线程池中卡住的任务进程 (抢占断氧)
    2. 将真正繁重的自动化工作打包 submit 到后台单线程池
    3. 向 APScheduler 交还名额，调度器上绝不留下阻塞脚印
    """
    logger.info(f"⏰ Scheduler alarm fired for task {task_id}, dispatching...")
    # 第一步: 闹钟响起的瞬间，立刻给线程池里卡住的任务断氧
    kill_active_processes()
    # 第二步: 获取健康线程池，将苦力工作无缝推入后台 (safe_submit 自动附加异常监控)
    pool = _get_healthy_pool()
    safe_submit(pool, run_task_with_context, app, task_id)
    # 第三步: 本函数生命终结，APScheduler 线程瞬间自由
    logger.info(f"Task {task_id} dispatched to executor pool (pool_shutdown={pool._shutdown}), scheduler thread released.")

# --- 具体执行器 ---

def get_desktop_env():
    env = os.environ.copy()
    env['DISPLAY'] = ':1'
    env['HOME'] = '/home/headless'
    env['USER'] = 'headless'
    env['XAUTHORITY'] = '/home/headless/.Xauthority'
    
    # 增强：支持多行 .dbus-env 文件解析
    dbus_file = Path('/home/headless/.dbus-env')
    if dbus_file.exists():
        try:
            for line in dbus_file.read_text().strip().splitlines():
                line = line.strip()
                if line.startswith('export '):
                    line = line[7:]  # 移除 'export '
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip("'").strip('"')
                    if key and value:
                        env[key] = value
        except Exception as e:
            logger.warning(f"Failed to parse .dbus-env: {e}")
    return env

def get_telegram_config():
    return os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')

def execute_selenium_script(task_name, script_path, timeout_sec=600):
    """通过子进程执行 Selenium IDE 脚本，避免阻塞 Flask worker 和污染全局环境"""
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()  # 仅传递给子进程，不污染全局 os.environ
    
    try:
        cmd = [sys.executable, '-m', 'scripts.task_executor', script_path]
        # 如果有 Telegram 配置，通过命令行参数传递
        if bot_token and chat_id:
            cmd.extend([bot_token, chat_id])
        
        logger.info(f"Running Selenium script as subprocess: {script_path}")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                            text=True, env=env, cwd='/app')
        
        with active_process_lock:
            ACTIVE_PROCESSES.append(p)
        
        try:
            stdout, stderr = p.communicate(timeout=timeout_sec)
            success = p.returncode == 0
            log_msg = (stdout + "\n" + stderr).strip() or "No output"
        except subprocess.TimeoutExpired:
            p.kill()
            success = False
            log_msg = f"Selenium script timeout ({timeout_sec}s)"
        finally:
            with active_process_lock:
                if p in ACTIVE_PROCESSES: ACTIVE_PROCESSES.remove(p)
        
        if success: logger.info(f"Selenium {task_name} Success")
        else: logger.error(f"Selenium {task_name} Failed: {log_msg[:200]}")
        
        from scripts.task_executor import send_telegram_notification, send_email_notification
        if bot_token and chat_id: send_telegram_notification(f"{task_name} (Selenium)", success, log_msg, bot_token, chat_id)
        send_email_notification(f"{task_name} (Selenium)", success, log_msg)
        return success
    except Exception as e:
        logger.error(f"Selenium Error: {e}")
        return False

def execute_python_script(task_name, script_path, timeout_sec=600):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    
    # 健康检查：确保 X11 显示可用（对于需要 GUI 的脚本至关重要）
    try:
        check = subprocess.run(['xdpyinfo'], env=env, capture_output=True, timeout=5)
        if check.returncode != 0:
            logger.warning(f"⚠️ X11 display not available, attempting to restart VNC...")
            subprocess.run(['supervisorctl', 'restart', 'vncserver'], capture_output=True, timeout=30)
            time.sleep(5)  # 等待 VNC 重启
    except Exception as e:
        logger.warning(f"X11 check skipped: {e}")
    
    try:
        cmd = [sys.executable, script_path]
        logger.info(f"Running command: {cmd}")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        
        with active_process_lock:
            ACTIVE_PROCESSES.append(p)
            
        try:
            stdout, stderr = p.communicate(timeout=timeout_sec)
            success = p.returncode == 0
            log_msg = (stdout + "\n" + stderr).strip() or "No output"
        except subprocess.TimeoutExpired:
            p.kill()
            success = False
            log_msg = f"Timeout ({timeout_sec}s)"
        finally:
            with active_process_lock:
                if p in ACTIVE_PROCESSES: ACTIVE_PROCESSES.remove(p)
        
        if success: logger.info(f"Python {task_name} Success: {log_msg[:100]}...")
        else: logger.error(f"Python {task_name} Failed")
        
        script_type = "(Py)"
        try:
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                if 'playwright' in content:
                    script_type = "(Playwright)"
                elif 'selenium' in content or 'webdriver' in content:
                    script_type = "(Selenium)"
        except:
            pass
        
        from scripts.task_executor import send_telegram_notification, send_email_notification
        if bot_token and chat_id: send_telegram_notification(f"{task_name} {script_type}", success, log_msg, bot_token, chat_id)
        send_email_notification(f"{task_name} {script_type}", success, log_msg)
        return success
    except Exception as e:
        logger.error(f"Python Exception: {e}")
        return False

def execute_autokey_script(script_name, task_name, timeout_sec=600):
    bot_token, chat_id = get_telegram_config()
    env = get_desktop_env()
    log_msg = ""
    
    # === 日志捕获改进 (Start) ===
    # 记录当前日志位置
    start_pos = 0
    try:
        if os.path.exists('/app/logs/autokey.log'):
            start_pos = os.path.getsize('/app/logs/autokey.log')
    except: pass
    
    # === 增强逻辑：服务健康检查与自动恢复 ===
    try:
        # 预检查：探测 AutoKey 服务是否存活
        check_res = subprocess.run(['autokey-run', '-l'], capture_output=True, env=env, timeout=5)
        if check_res.returncode != 0:
            logger.warning("⚠️ AutoKey service seems down (check failed). Triggering self-healing...")
            reload_autokey()
            time.sleep(2) # 给一点额外缓冲
    except Exception as e:
        logger.error(f"AutoKey health check error: {e}")
        reload_autokey()

    # 策略 1: 尝试完整文件名 (例如 test_browser.py)
    cmd = ['autokey-run', '-s', script_name]
    logger.info(f"Running AutoKey (Try 1): {cmd}")
    # 为保证稳定，我们对挂着的部分加上 timeout 处理
    try:
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        with active_process_lock: ACTIVE_PROCESSES.append(p1)
        try:
            stdout1, stderr1 = p1.communicate(timeout=timeout_sec)
            result_code = p1.returncode
        except subprocess.TimeoutExpired as e:
            p1.kill()
            logger.error(f"AutoKey Timeout Try 1: {e}")
            reload_autokey() # Force restart AutoKey engine to abort the runaway script
            from scripts.task_executor import send_telegram_notification
            import traceback
            if bot_token and chat_id: send_telegram_notification(f"{task_name} (AutoKey)", False, f"任务超时 ({timeout_sec}s)", bot_token, chat_id)
            return False
        finally:
            with active_process_lock:
                if p1 in ACTIVE_PROCESSES: ACTIVE_PROCESSES.remove(p1)
                
    except Exception as e:
        logger.error(f"AutoKey Exception Try 1: {e}")
        return False
    
    # 策略 2: 如果失败，尝试去掉后缀 (例如 test_browser)
    # 注意：如果 result_code < 0 (例如 -9)，说明是被抢占机制强杀了，绝对不能死灰复燃触发重试！
    if result_code != 0 and result_code >= 0 and script_name.endswith('.py'):
        stem = Path(script_name).stem
        cmd_retry = ['autokey-run', '-s', stem]
        logger.info(f"Running AutoKey (Try 2): {cmd_retry}")
        try:
            p2 = subprocess.Popen(cmd_retry, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            with active_process_lock: ACTIVE_PROCESSES.append(p2)
            try:
                stdout2, stderr2 = p2.communicate(timeout=timeout_sec)
                result_code2 = p2.returncode
                stdout_final, stderr_final = stdout2, stderr2
            except subprocess.TimeoutExpired as e:
                p2.kill()
                logger.error(f"AutoKey Timeout Try 2: {e}")
                reload_autokey() # Force restart AutoKey engine to abort the runaway script
                from scripts.task_executor import send_telegram_notification
                if bot_token and chat_id: send_telegram_notification(f"{task_name} (AutoKey)", False, f"任务重试超时 ({timeout_sec}s)", bot_token, chat_id)
                return False
            finally:
                with active_process_lock:
                    if p2 in ACTIVE_PROCESSES: ACTIVE_PROCESSES.remove(p2)
        except Exception as e:
            logger.error(f"AutoKey Exception Try 2: {e}")
            return False
    else:
        stdout_final, stderr_final = stdout1, stderr1
        result_code2 = result_code

    success = result_code2 == 0
    
    # === 构建日志通知 ===
    # 1. 控制台输出 (Stdout/Stderr)
    console_out = (stdout_final + "\n" + stderr_final).strip()
    if console_out:
        log_msg += f"--- Console Output ---\n{console_out}\n\n"

    # 2. AutoKey 日志文件 (Hack: 等待异步写入)
    if success:
        time.sleep(2) # 等待脚本可能的输出
        try:
            with open('/app/logs/autokey.log', 'r') as f:
                f.seek(start_pos)
                new_logs = f.read()
                if new_logs.strip():
                    log_msg += f"--- Script Log (autokey.log) ---\n{new_logs}"
        except Exception as e:
            logger.error(f"Failed to read autokey logs: {e}")

    log_msg = log_msg.strip() or "No output captured."
    
    if success: logger.info(f"AutoKey {script_name} Success")
    else: logger.error(f"AutoKey Failed: {stderr_final}")
    
    from scripts.task_executor import send_telegram_notification, send_email_notification
    if bot_token and chat_id: send_telegram_notification(f"{task_name} (AutoKey)", success, log_msg, bot_token, chat_id)
    send_email_notification(f"{task_name} (AutoKey)", success, log_msg)
    return success

def reload_autokey():
    """强制重启 AutoKey 以加载新脚本 (带健康检查)"""
    try:
        logger.info("♻️ Reloading AutoKey...")
        
        # 1. Kill existing
        subprocess.run(['pkill', '-f', 'autokey'], capture_output=True)
        time.sleep(1)
        
        # 2. Restart (headless environment)
        env = get_desktop_env()
        
        # redirect autokey output to log file (使用 context manager 避免句柄泄漏)
        log_file = open('/app/logs/autokey.log', 'a')
        
        pro = subprocess.Popen(['autokey-gtk', '--verbose'], 
                         env=env,
                         stdout=log_file, 
                         stderr=log_file,
                         start_new_session=True)
        
        # 子进程已拿到 fd 副本，父进程可以安全关闭自己的句柄
        log_file.close()
        
        # 3. Wait for DBus service polling
        logger.info("⏳ Waiting for AutoKey DBus service...")
        for i in range(20): # Max 10 seconds
            time.sleep(0.5)
            # 尝试列出脚本，如果成功则说明 DBus 服务已就绪
            check_cmd = ['autokey-run', '-l']
            try:
                res = subprocess.run(check_cmd, env=env, capture_output=True, timeout=3)
                if res.returncode == 0:
                    logger.info(f"✅ AutoKey restarted and ready (waited {i*0.5}s)")
                    return
            except subprocess.TimeoutExpired:
                logger.warning("AutoKey DBus check timed out.")
            
            # 检查进程是否意外退出
            if pro.poll() is not None:
                logger.error("❌ AutoKey process died unexpectedly")
                return

        logger.warning("⚠️ AutoKey restart timed out waiting for DBus (but process is running)")

    except Exception as e:
        logger.error(f"❌ Failed to reload AutoKey: {e}")

# [FIX] 调度器诊断 API：实时查看调度器状态
@app.route('/api/scheduler/status')
@login_required
def scheduler_status():
    """返回调度器运行状态、注册 Job 列表和线程池健康信息"""
    jobs = []
    try:
        for job in scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
    except Exception as e:
        logger.error(f"Failed to list scheduler jobs: {e}")
    
    pool = _get_healthy_pool()
    try:
        pool_pending = pool._work_queue.qsize()
        pool_shutdown = pool._shutdown
    except Exception:
        pool_pending = -1
        pool_shutdown = None
    
    return jsonify({
        'scheduler_running': scheduler.running,
        'total_jobs': len(jobs),
        'jobs': jobs,
        'pool_workers': 2,
        'pool_pending': pool_pending,
        'pool_shutdown': pool_shutdown,
        'watchdog_alive': _watchdog_thread.is_alive() if _watchdog_thread else False,
        'server_time': datetime.now(SYSTEM_TZ).isoformat()
    })

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
                    
                    if end_dt < start_dt:
                        end_dt += timedelta(days=1)
                    
                    diff_seconds = int((end_dt - start_dt).total_seconds())
                    if diff_seconds < 60: diff_seconds = 60
                    
                    trigger = CronTrigger(
                        hour=start_h, 
                        minute=start_m, 
                        jitter=diff_seconds, 
                        timezone=SYSTEM_TZ
                    )
                    logger.info(f"Task {task.name}: Random schedule {task.random_start}-{task.random_end} (window: {diff_seconds}s)")
                except Exception as e:
                    logger.error(f"Random schedule parse error for {task.name}: {e}")
                    trigger = CronTrigger.from_crontab(task.cron_expression, timezone=SYSTEM_TZ)
            else:
                trigger = CronTrigger.from_crontab(task.cron_expression, timezone=SYSTEM_TZ)
            
            if trigger:
                job = scheduler.add_job(
                    func=execute_scheduled_task,
                    trigger=trigger,
                    id=f'task_{task.id}',
                    args=[task.id],
                    replace_existing=True
                )
                logger.info(f'✅ Task {task.name} scheduled. Next run range: {job.next_run_time}')
        except Exception as e:
            logger.error(f'Schedule failed for {task.name}: {e}')

def initialize_system():
    with app.app_context():
        # [NEW] 创建可能缺失的表 (比如新的 ScriptFile)
        db.create_all()
        
        try:
            db.session.execute(text("ALTER TABLE task ADD COLUMN timeout INTEGER DEFAULT 600"))
            db.session.commit()
        except:
            db.session.rollback()
            
        try:
            # [HOTFIX] 针对 MySQL/MariaDB，强制升级 profile_data 的容量为 LONGBLOB，解决 Data too long 报错
            db.session.execute(text("ALTER TABLE browser_profile MODIFY COLUMN profile_data LONGBLOB"))
            db.session.commit()
        except:
            db.session.rollback()
            
        # [NEW] 重启/初次启动时，从数据库恢复所有脚本到本地临时文件系统
        try:
            script_files = ScriptFile.query.all()
            for record in script_files:
                target_dir = get_target_dir(record.folder)
                target_dir.mkdir(parents=True, exist_ok=True)
                file_path = target_dir / record.filename
                # 写入文件代码
                file_path.write_text(record.content, encoding='utf-8')
                # 修复权限: 防止 root (entrypoint) 写入导致 headless 无法覆盖
                try:
                    import shutil
                    shutil.chown(file_path, user="headless", group="headless")
                except: pass
                
                # 如果是 autokey 脚本，还需要恢复 .json 定义文件才能被系统识别
                if record.folder == 'autokey' and record.filename.endswith('.py'):
                    json_path = file_path.with_suffix('.json')
                    if not json_path.exists():
                        script_config = {
                            "type": "script",
                            "description": record.filename,
                            "store": {},
                            "modes": [3],
                            "usageCount": 0,
                            "prompt": False,
                            "omitTrigger": False,
                            "showInTrayMenu": False,
                            "filter": None,
                            "hotkey": {"hotKey": None, "modifiers": []}
                        }
                        json_path.write_text(json.dumps(script_config, indent=4), encoding='utf-8')
                        try:
                            shutil.chown(json_path, user="headless", group="headless")
                        except: pass
            if script_files:
                logger.info(f"✅ Synced {len(script_files)} script files from database to local filesystem.")
        except Exception as e:
            logger.error(f"Error restoring scripts from database: {e}")
            
        # [NEW] 恢复云端保存的浏览器 Profile 数据 (Cookie, Localstorage)
        try:
            browser_record = BrowserProfile.query.first()
            if browser_record and browser_record.profile_data:
                from scripts.browser_sync import restore_browser_profile
                if restore_browser_profile(browser_record.profile_data):
                    logger.info("✅ Synced browser profile state from database.")
        except Exception as e:
            logger.error(f"Error restoring browser profile from database: {e}")
        
        try:
            admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
            admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
            
            user = User.query.filter_by(username=admin_user).first()
            if not user:
                # Create new user
                user = User(username=admin_user)
                user.set_password(admin_pass)
                db.session.add(user)
                print(f"Created admin user: {admin_user}")
            else:
                # Force update password for existing user
                user.set_password(admin_pass)
                print(f"Updated password for admin user: {admin_user}")
            
            db.session.commit()

            # Security Fix: Strict Single User Policy
            # Delete any user that does not match the current configured admin_user
            all_users = User.query.all()
            for u in all_users:
                if u.username != admin_user:
                    db.session.delete(u)
                    print(f"Security: Removed stale user '{u.username}'")
            db.session.commit()
            
            tasks = Task.query.filter_by(enabled=True).all()
            for task in tasks:
                schedule_task(task)
        except Exception as e:
            print(f"Init error: {e}")

initialize_system()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
