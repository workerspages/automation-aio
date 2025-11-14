from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import os
import json
import requests
from pathlib import Path
import subprocess
import sys

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

# 数据库模型
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
    return User.query.get(int(user_id))

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
    scripts = get_selenium_scripts()
    return render_template('dashboard.html', tasks=tasks, scripts=scripts)

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200

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
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'script_path': t.script_path,
        'cron_expression': t.cron_expression,
        'enabled': t.enabled,
        'last_run': t.last_run.isoformat() if t.last_run else None,
        'last_status': t.last_status
    } for t in tasks])

@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    
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
    task = Task.query.get_or_404(task_id)
    execute_selenium_script(task.id)
    return jsonify({'success': True, 'message': '任务已开始执行'})

def get_selenium_scripts():
    scripts_dir = Path(os.environ.get('SCRIPTS_DIR', '/home/headless/Downloads'))
    scripts = []
    
    if scripts_dir.exists():
        for file in scripts_dir.glob('*.side'):
            scripts.append({
                'name': file.name,
                'path': str(file)
            })
    
    return scripts

def schedule_task(task):
    if task.enabled:
        try:
            trigger = CronTrigger.from_crontab(task.cron_expression)
            scheduler.add_job(
                func=execute_selenium_script,
                trigger=trigger,
                id=f'task_{task.id}',
                args=[task.id],
                replace_existing=True
            )
            print(f'任务 {task.name} (ID: {task.id}) 已调度')
        except Exception as e:
            print(f'调度任务失败: {e}')

def execute_selenium_script(task_id):
    task = Task.query.get(task_id)
    if not task:
        return
    
    print(f'开始执行任务: {task.name}')
    task.last_run = datetime.utcnow()
    
    try:
        # 调用 task_executor.py 执行脚本
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        
        result = subprocess.run(
            [
                '/opt/venv/bin/python3',
                '/app/scripts/task_executor.py',
                task.script_path,
                bot_token,
                chat_id
            ],
            capture_output=True,
            text=True,
            timeout=int(os.environ.get('MAX_SCRIPT_TIMEOUT', 300))
        )
        
        if result.returncode == 0:
            task.last_status = 'success'
            print(f'任务 {task.name} 执行成功')
        else:
            task.last_status = 'failed'
            print(f'任务 {task.name} 执行失败: {result.stderr}')
            
    except subprocess.TimeoutExpired:
        task.last_status = 'timeout'
        print(f'任务 {task.name} 执行超时')
        send_telegram_notification(task, 'timeout', '脚本执行超时')
        
    except Exception as e:
        task.last_status = 'error'
        print(f'任务 {task.name} 执行异常: {e}')
        send_telegram_notification(task, 'error', str(e))
    
    db.session.commit()

def send_telegram_notification(task, status, error=None):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        return
    
    status_emoji = {
        'success': '✅',
        'failed': '❌',
        'timeout': '⏱️',
        'error': '⚠️'
    }.get(status, '❓')
    
    status_text = {
        'success': '成功',
        'failed': '失败',
        'timeout': '超时',
        'error': '错误'
    }.get(status, '未知')
    
    html_message = f"""
<b>{status_emoji} 任务执行通知</b>

<b>任务名称:</b> {task.name}
<b>脚本路径:</b> <code>{task.script_path}</code>
<b>执行状态:</b> {status_text}
<b>执行时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    if error:
        html_message += f"\n<b>错误信息:</b> <code>{error}</code>"
    
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {
        'chat_id': chat_id,
        'text': html_message,
        'parse_mode': 'HTML'
    }
    
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f'发送Telegram通知失败: {e}')

if __name__ == '__main__':
    with app.app_context():
        # 创建数据库表
        db.create_all()
        
        # 从环境变量获取管理员账号密码
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        # 创建默认管理员用户（如果不存在）
        if not User.query.filter_by(username=admin_username).first():
            user = User(username=admin_username, password=admin_password)
            db.session.add(user)
            db.session.commit()
            print(f'已创建默认管理员账号: {admin_username}')
        
        # 加载现有任务到调度器
        tasks = Task.query.filter_by(enabled=True).all()
        for task in tasks:
            try:
                schedule_task(task)
                print(f'已加载任务: {task.name}')
            except Exception as e:
                print(f'加载任务失败 {task.name}: {e}')
    
    print('=' * 50)
    print('Selenium 自动化管理平台已启动')
    print(f'Web 界面: http://0.0.0.0:5000')
    print(f'默认管理员: {os.environ.get("ADMIN_USERNAME", "admin")}')
    print('=' * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
