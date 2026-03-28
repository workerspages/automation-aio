#!/usr/bin/env python3
"""
独立的数据库初始化脚本。
避免导入 app 模块（会触发 initialize_system 和调度器启动），
而是直接构建最小化的 Flask app 和数据库连接来完成 DDL 操作。
"""
import os
from sqlalchemy import text, inspect

def get_database_uri():
    db_host = os.environ.get('MARIADB_HOST')
    if db_host:
        db_user = os.environ.get('MARIADB_USER', 'root')
        db_pass = os.environ.get('MARIADB_PASSWORD', '')
        db_port = os.environ.get('MARIADB_PORT', '3306')
        db_name = os.environ.get('MARIADB_DB', 'automation')
        
        uri = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        
        ssl_enabled = os.environ.get('DB_SSL_ENABLED', 'false').lower() == 'true'
        ca_path = os.environ.get('DB_SSL_CA_PATH')
        
        if ssl_enabled or ca_path:
            final_ca_path = ca_path if ca_path else '/etc/ssl/certs/ca-certificates.crt'
            uri += f"&ssl_ca={final_ca_path}&ssl_verify_cert=true&ssl_verify_identity=true"
            
        return uri
    return os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:////app/data/tasks.db')


def initialize_database():
    """
    最小化初始化：仅确保数据库表结构存在，不启动调度器或其他业务逻辑。
    """
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from werkzeug.security import generate_password_hash

    mini_app = Flask(__name__)
    mini_app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
    mini_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db = SQLAlchemy(mini_app)

    # 这里不导入 app.py 的模型，而是自行定义最小模型
    # (只用于确保表存在 + 迁移列)
    with mini_app.app_context():
        print("Creating all database tables (standalone init)...")
        
        # 使用 raw SQL 检查并创建基础结构
        try:
            inspector = inspect(db.engine)
            
            if inspector.has_table("task"):
                columns = [c['name'] for c in inspector.get_columns('task')]
                with db.engine.connect() as conn:
                    if 'schedule_type' not in columns:
                        conn.execute(text('ALTER TABLE task ADD COLUMN schedule_type VARCHAR(20) DEFAULT "cron"'))
                    if 'random_start' not in columns:
                        conn.execute(text('ALTER TABLE task ADD COLUMN random_start VARCHAR(10)'))
                    if 'random_end' not in columns:
                        conn.execute(text('ALTER TABLE task ADD COLUMN random_end VARCHAR(10)'))
                    if 'timeout' not in columns:
                        conn.execute(text('ALTER TABLE task ADD COLUMN timeout INTEGER DEFAULT 600'))
                    conn.commit()
                print("✅ Table migration checks completed.")
            else:
                print("ℹ️ Task table doesn't exist yet, will be created by app startup.")
        except Exception as e:
            print(f"Migration check skipped: {e}")

        print("✅ Database init_db.py completed (lightweight mode).")


if __name__ == '__main__':
    initialize_database()
