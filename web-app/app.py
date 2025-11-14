import os
import sys
import json
import logging
import time
import random
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 关键补丁: 保证 scripts/ 在包路径
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.errorhandler(Exception)
def handle_error(e):
    logger.exception(e)
    return jsonify({'success': False, 'error': str(e)}), 500

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

@app.route('/api/scripts', methods=['GET'])
@login_required
def list_scripts():
    scripts = get_available_scripts()
    return jsonify(scripts)

def get_available_scripts():
    scripts_dir = Path(os.environ.get('SCRIPTS_DIR', '/home/headless/Downloads'))
    scripts = []
    if scripts_dir.exists():
        for file in scripts_dir.iterdir():
            if file.suffix.lower() in ['.side', '.a5s']:
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
    return jsonify({'success': True, 'message': '任务已开始执行'})

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

def execute_script(task_id):
    with app.app_context():
        task = db.session.get(Task, task_id)
        if not task:
            return
        script_path = task.script_path.lower()
        if script_path.endswith('.side'):
            return execute_selenium_script(task_id)
        elif script_path.endswith('.a5s'):
            return execute_actiona_script(task.script_path)
        else:
            logger.error(f"不支持的脚本类型: {script_path}")
            return False

def execute_selenium_script(task_id):
    from scripts.task_executor import SeleniumIDEExecutor, send_telegram_notification
    with app.app_context():
        task = db.session.get(Task, task_id)
        if not task:
            return False
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        executor = SeleniumIDEExecutor(task.script_path)
        success, message = executor.execute()
        if bot_token and chat_id:
            send_telegram_notification(task.name, success, message, bot_token, chat_id)
        return success

def execute_actiona_script(script_path):
    try:
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        result = subprocess.run(
            ['/usr/local/bin/actiona', '-s', script_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        success = result.returncode == 0
        if success:
            logger.info("Actiona脚本执行成功")
        else:
            logger.error(f"Actiona脚本执行失败: {result.stderr}")
        if bot_token and chat_id:
            from scripts.task_executor import send_telegram_notification
            send_telegram_notification(Path(script_path).name, success, result.stdout + result.stderr, bot_token, chat_id)
        return success
    except Exception as e:
        logger.error(f"执行Actiona脚本异常: {e}")
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
    print('Selenium 自动化管理平台已启动')
    print(f'Web 界面: http://0.0.0.0:5000')
    print(f'默认管理员: {admin_username}')
    print('='*50)
    app.run(host='0.0.0.0', port=5000, debug=False)
