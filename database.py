# -*- coding: utf-8 -*-
"""
EasyShare 数据库模块
负责数据库初始化和所有数据库操作
"""

import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

# 数据库文件路径
DB_FILE = "data/easyshare.db"


def get_db_path():
    """获取数据库文件路径"""
    import sys
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent
    db_dir = base_dir / "data"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "easyshare.db"


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """初始化数据库，创建所有必要的表"""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    # 用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'readonly',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME,
            is_active BOOLEAN DEFAULT 1,
            allow_batch_download BOOLEAN DEFAULT 0
        )
    """)
    
    # 为已有用户添加批量下载字段（如果不存在）
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'allow_batch_download' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN allow_batch_download BOOLEAN DEFAULT 0")
    
    # 配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key VARCHAR(50) PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    # 操作日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username VARCHAR(50),
            action VARCHAR(50) NOT NULL,
            path TEXT,
            detail TEXT,
            ip VARCHAR(50),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # 回收站表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trash (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_path TEXT NOT NULL,
            file_type VARCHAR(20),
            file_size INTEGER,
            deleted_by INTEGER,
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deleted_by) REFERENCES users(id)
        )
    """)
    
    # 登录失败记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) NOT NULL,
            ip VARCHAR(50),
            attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN DEFAULT 0
        )
    """)
    
    # 清理超过24小时的失败记录（启动时清理）
    cursor.execute("DELETE FROM login_attempts WHERE attempted_at < datetime('now', '-1 day')")
    
    conn.commit()
    
    # 创建默认管理员账户
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    if cursor.fetchone()[0] == 0:
        admin_password = hash_password("admin")
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", admin_password, "admin")
        )
        conn.commit()
    
    conn.close()
    print("[数据库] 初始化完成")


def hash_password(password, salt=None):
    """密码哈希加密"""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${hash_obj.hex()}"


def verify_password(password, password_hash):
    """验证密码"""
    try:
        salt, hash_value = password_hash.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return new_hash.hex() == hash_value
    except:
        return False


def generate_token(length=32):
    """生成随机令牌"""
    return secrets.token_urlsafe(length)


# ============ 用户操作 ============

def create_user(username, password, role='readonly', allow_batch_download=True):
    """创建新用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, allow_batch_download) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, 1 if allow_batch_download else 0)
        )
        return cursor.lastrowid


def get_user_by_username(username):
    """根据用户名获取用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    """根据ID获取用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_users():
    """获取所有用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, created_at, last_login, is_active, allow_batch_download FROM users ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]


def update_user(user_id, username=None, password=None, role=None, is_active=None, allow_batch_download=None):
    """更新用户信息"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        if username:
            updates.append("username = ?")
            params.append(username)
        if password:
            updates.append("password_hash = ?")
            params.append(hash_password(password))
        if role:
            updates.append("role = ?")
            params.append(role)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if allow_batch_download is not None:
            updates.append("allow_batch_download = ?")
            params.append(1 if allow_batch_download else 0)
        if updates:
            params.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)


def delete_user(user_id):
    """删除用户"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))


def update_last_login(user_id):
    """更新最后登录时间"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now(), user_id))


# ============ 日志操作 ============

def add_log(user_id, username, action, path=None, detail=None, ip=None):
    """添加操作日志"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (user_id, username, action, path, detail, ip) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, action, path, detail, ip)
        )


def get_logs(limit=100, offset=0, user_id=None, action=None):
    """获取日志列表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM logs WHERE 1=1"
        params = []
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        if action:
            sql += " AND action = ?"
            params.append(action)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_log_count(user_id=None, action=None):
    """获取日志数量"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT COUNT(*) FROM logs WHERE 1=1"
        params = []
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        if action:
            sql += " AND action = ?"
            params.append(action)
        cursor.execute(sql, params)
        return cursor.fetchone()[0]



# ============ 回收站操作 ============

def add_to_trash(original_path, file_type, file_size, deleted_by):
    """添加文件到回收站"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO trash (original_path, file_type, file_size, deleted_by) VALUES (?, ?, ?, ?)",
            (original_path, file_type, file_size, deleted_by)
        )


def get_trash_items(limit=100, offset=0):
    """获取回收站项目"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM trash ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_trash_count():
    """获取回收站项目数量"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trash")
        return cursor.fetchone()[0]


def restore_from_trash(trash_id):
    """从回收站恢复文件"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trash WHERE id = ?", (trash_id,))
        item = cursor.fetchone()
        if item:
            return dict(item)
        return None


def delete_from_trash(trash_id):
    """从数据库删除回收站记录"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trash WHERE id = ?", (trash_id,))


def empty_trash():
    """清空回收站"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trash")


# ============ 登录安全操作 ============

def record_login_attempt(username, ip, success=True):
    """记录登录尝试"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO login_attempts (username, ip, success) VALUES (?, ?, ?)",
            (username, ip, 1 if success else 0)
        )


def get_recent_failed_attempts(username, minutes=15, max_attempts=5):
    """
    获取最近N分钟内的失败登录尝试次数
    
    Args:
        username: 用户名
        minutes: 时间窗口（分钟）
        max_attempts: 失败次数阈值
        
    Returns:
        tuple: (是否锁定, 剩余时间, 剩余尝试次数)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 获取最近N分钟内的失败尝试
        cursor.execute("""
            SELECT COUNT(*) as failed_count, 
                   MAX(attempted_at) as last_attempt
            FROM login_attempts 
            WHERE username = ? 
              AND success = 0 
              AND attempted_at >= datetime('now', '-' || ? || ' minutes')
        """, (username, minutes))
        
        row = cursor.fetchone()
        failed_count = row[0] if row else 0
        
        if failed_count >= max_attempts:
            # 获取锁定到期时间
            cursor.execute("""
                SELECT datetime(MAX(attempted_at), '+' || ? || ' minutes') as locked_until
                FROM login_attempts 
                WHERE username = ? AND success = 0
            """, (minutes, username))
            lock_row = cursor.fetchone()
            locked_until = lock_row[0] if lock_row and lock_row[0] else None
            
            return True, locked_until, 0
        
        return False, None, max_attempts - failed_count


def clear_failed_attempts(username):
    """清除用户的失败登录记录（登录成功后）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM login_attempts WHERE username = ? AND success = 0", (username,))


def cleanup_expired_trash(retention_days=30):
    """清理过期的回收站记录"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 删除超过指定天数的回收站记录
        cursor.execute("""
            DELETE FROM trash 
            WHERE deleted_at < datetime('now', '-' || ? || ' days')
        """, (retention_days,))
        return cursor.rowcount
