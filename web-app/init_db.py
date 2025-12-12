import os
from sqlalchemy import text, inspect
from app import app, db, User

def initialize_database():
    """
    在应用上下文中创建数据库表并初始化管理员账户。
    包含自动迁移逻辑，支持从旧版本平滑升级。
    """
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        print("Tables created.")

        # === 数据库自动迁移逻辑 (新增) ===
        try:
            inspector = inspect(db.engine)
            # 检查 task 表是否存在
            if inspector.has_table("task"):
                columns = [c['name'] for c in inspector.get_columns('task')]
                
                with db.engine.connect() as conn:
                    # 检查并添加 schedule_type 字段
                    if 'schedule_type' not in columns:
                        print("Migrating: Adding schedule_type column...")
                        conn.execute(text('ALTER TABLE task ADD COLUMN schedule_type VARCHAR(20) DEFAULT "cron"'))
                    
                    # 检查并添加 random_start 字段
                    if 'random_start' not in columns:
                        print("Migrating: Adding random_start column...")
                        conn.execute(text('ALTER TABLE task ADD COLUMN random_start VARCHAR(10)'))
                    
                    # 检查并添加 random_end 字段
                    if 'random_end' not in columns:
                        print("Migrating: Adding random_end column...")
                        conn.execute(text('ALTER TABLE task ADD COLUMN random_end VARCHAR(10)'))
                    
                    conn.commit()
                print("Database schema migration checked/completed.")
        except Exception as e:
            print(f"Warning during migration check: {e}")
        # =================================

        # 从环境变量获取管理员凭据，提供默认值
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')

        # 检查管理员用户是否已存在
        if not User.query.filter_by(username=admin_username).first():
            print(f"Admin user '{admin_username}' not found. Creating it...")
            # 创建新用户
            user = User(username=admin_username)
            user.set_password(admin_password)
            db.session.add(user)
            db.session.commit()
            print(f"Default admin user '{admin_username}' created successfully.")
        else:
            print(f"Admin user '{admin_username}' already exists.")

if __name__ == '__main__':
    print("Starting database initialization...")
    initialize_database()
    print("Database initialization finished.")
