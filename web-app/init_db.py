import os
from sqlalchemy import text, inspect
from app import app, db, User

def initialize_database():
    """
    在应用上下文中创建数据库表并初始化管理员账户。
    """
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        
        # 简单的迁移检查 (防止旧版DB报错)
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
                    conn.commit()
        except Exception as e:
            print(f"Migration check skipped: {e}")

        # 初始化管理员
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')

        if not User.query.filter_by(username=admin_username).first():
            print(f"Creating admin user: {admin_username}")
            user = User(username=admin_username)
            user.set_password(admin_password)
            db.session.add(user)
            db.session.commit()
        else:
            print(f"Admin user '{admin_username}' exists.")

if __name__ == '__main__':
    initialize_database()
