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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/tasks.db'
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
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
        schedule_task(task)
        return jsonify({'success': True, 'task_id': task.id})
    
    tasks = Task.query.all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'script_path': t.script_path,
        'cron_expression': t.cron_expression,
        'enabled': t.enabled,
        'last_run': t.last_run.isoformat() if t.last_run else None
    } for t in tasks])

@app.route('/api/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if request.method == 'DELETE':
        scheduler.remove_job(f'task_{task_id}', jobstore='default')
        db.session.delete(task)
        db.session.commit()
        return jsonify({'success': True})
    
    data = request.json
    task.name = data.get('name', task.name)
    task.cron_expression = data.get('cron_expression', task.cron_expression)
    task.enabled = data.get('enabled', task.enabled)
    db.session.commit()
    
    scheduler.remove_job(f'task_{task_id}', jobstore='default')
    if task.enabled:
        schedule_task(task)
    
    return jsonify({'success': True})

def get_selenium_scripts():
    downloads_path = Path('/home/headless/Downloads')
    scripts = []
    if downloads_path.exists():
        for file in downloads_path.glob('*.side'):
            scripts.append({
                'name': file.name,
                'path': str(file)
            })
    return scripts

def schedule_task(task):
    if task.enabled:
        trigger = CronTrigger.from_crontab(task.cron_expression)
        scheduler.add_job(
            func=execute_selenium_script,
            trigger=trigger,
            id=f'task_{task.id}',
            args=[task.id],
            replace_existing=True
        )

def execute_selenium_script(task_id):
    task = Task.query.get(task_id)
    if not task:
        return
    
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        
        options = Options()
        options.add_argument('--headless')
        driver = webdriver.Firefox(options=options)
        
        # 加载并执行Selenium IDE脚本
        with open(task.script_path, 'r') as f:
            script_data = json.load(f)
        
        # 执行脚本命令
        for test in script_data.get('tests', []):
            for command in test.get('commands', []):
                # 这里需要根据Selenium IDE的命令格式来执行
                pass
        
        driver.quit()
        
        task.last_run = datetime.utcnow()
        db.session.commit()
        
        # 发送Telegram通知
        send_telegram_notification(task, 'success')
        
    except Exception as e:
        send_telegram_notification(task, 'failed', str(e))

def send_telegram_notification(task, status, error=None):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        return
    
    status_emoji = '✅' if status == 'success' else '❌'
    html_message = f"""
<b>{status_emoji} 任务执行通知</b>

<b>任务名称:</b> {task.name}
<b>脚本路径:</b> <code>{task.script_path}</code>
<b>执行状态:</b> {status}
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
        requests.post(url, data=data)
    except Exception as e:
        print(f'发送Telegram通知失败: {e}')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # 创建默认用户
        if not User.query.filter_by(username='admin').first():
            user = User(username='admin', password='admin123')
            db.session.add(user)
            db.session.commit()
    
    app.run(host='0.0.0.0', port=5000)
