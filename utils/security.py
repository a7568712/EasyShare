# -*- coding: utf-8 -*-
"""
EasyShare 安全工具
提供路径安全检查和权限验证
"""

import os
import re
from pathlib import Path
from functools import wraps
from flask import session, jsonify, request, redirect

from config import config
from database import get_user_by_username


def is_safe_path(base_path, target_path):
    """
    检查目标路径是否在基础路径内，防止目录遍历攻击

    Args:
        base_path: 基础路径（共享目录）
        target_path: 目标路径

    Returns:
        bool: 是否安全
    """
    # 先标准化路径
    base_path = os.path.normpath(base_path)
    target_path = os.path.normpath(target_path)

    # Windows 特殊处理：禁用 UNC 路径（防止 \\server\share 攻击）
    if target_path.startswith('\\\\'):
        return False

    # 使用 os.path.abspath 获取绝对路径（不解析符号链接）
    try:
        base_abs = os.path.abspath(base_path)
        target_abs = os.path.abspath(target_path)

        # 规范化路径（解析 . 和 .. 但不解析符号链接）
        base_abs = os.path.normpath(base_abs)
        target_abs = os.path.normpath(target_abs)

        # 关键检查：确保目标路径以基础路径开头
        # 使用 os.sep 确保路径分隔符匹配
        base_prefix = base_abs.rstrip(os.sep) + os.sep
        if not target_abs.startswith(base_prefix) and target_abs != base_abs.rstrip(os.sep):
            return False

        # 额外检查：禁止包含 .. 路径穿越
        if '..' in target_abs.split(os.sep):
            return False

        # Windows 额外检查：禁止驱动器穿越（如 C:\Windows\System32）
        if len(target_abs) > 3 and target_abs[1:3] == ':\\' and target_abs[:1].isalpha():
            if target_abs[:2].upper() != base_abs[:2].upper():
                return False

        return True
    except (ValueError, OSError):
        return False


def is_hidden_folder(folder_name):
    """检查文件夹是否应该隐藏"""
    hidden_folders = config.hidden_folders or []
    return folder_name in hidden_folders or folder_name.startswith('.')


def check_file_permission(user, file_path, require_write=False):
    """
    检查用户对文件的权限
    
    Args:
        user: 用户信息字典
        file_path: 文件路径
        require_write: 是否需要写权限
        
    Returns:
        bool: 是否有权限
    """
    if not user:
        return config.anonymous_access
    
    role = user.get('role', 'readonly')
    
    # 管理员拥有所有权限
    if role == 'admin':
        return True
    
    # 只读用户没有写权限
    if require_write and role == 'readonly':
        return False
    
    return True



def login_required(f):
    """登录验证装饰器 - 自动区分页面和API请求"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # 检查是否是 AJAX/API 请求（通过 Accept 或 X-Requested-With 判断）
            if request.headers.get('Accept') == 'application/json' or \
               request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
               request.is_json:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            # 页面请求，重定向到登录页
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        if session.get('role') != 'admin':
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function


def get_client_ip():
    """获取客户端IP地址（防止伪造）"""
    # 只有在信任代理的情况下才读取代理头
    # 在直接访问的情况下，X-Forwarded-For可以被客户端伪造
    if config.get('trusted_proxies', False):
        # 信任代理模式（通常在nginx/reverse proxy后面时使用）
        if request.headers.get('X-Forwarded-For'):
            # X-Forwarded-For可能包含多个IP，第一个是真实客户端IP
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
    
    # 直接模式：使用remote_addr（更安全，但本地访问时可能是127.0.0.1）
    return request.remote_addr or '0.0.0.0'


def get_current_user():
    """获取当前登录用户"""
    if 'user_id' in session:
        return {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'allow_batch_download': session.get('allow_batch_download', True)
        }
    return None


def validate_password_strength(password):
    """
    验证密码强度
    
    Args:
        password: 密码字符串
        
    Returns:
        tuple: (是否通过, 错误消息或空)
    """
    # 最小长度检查
    min_length = config.password_min_length
    if len(password) < min_length:
        return False, f"密码长度不能少于 {min_length} 个字符"
    
    # 大写字母检查
    if config.password_require_uppercase:
        if not re.search(r'[A-Z]', password):
            return False, "密码必须包含至少一个大写字母"
    
    # 数字检查
    if config.password_require_number:
        if not re.search(r'[0-9]', password):
            return False, "密码必须包含至少一个数字"
    
    # 特殊字符检查
    if config.password_require_special:
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "密码必须包含至少一个特殊字符 (!@#$%^&*...)"
    
    return True, ""


def get_password_strength_info(password):
    """
    获取密码强度信息（用于前端显示）
    
    Returns:
        dict: {score: 0-4, feedback: str, rules: {length, uppercase, number, special}}
    """
    rules = {
        "length": len(password) >= config.password_min_length,
        "uppercase": bool(re.search(r'[A-Z]', password)) if config.password_require_uppercase else True,
        "number": bool(re.search(r'[0-9]', password)) if config.password_require_number else True,
        "special": bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)) if config.password_require_special else True
    }
    
    score = sum(rules.values()) if all(rules.values()) else 0
    
    feedback_map = {
        4: "密码强度：强",
        3: "密码强度：中等",
        2: "密码强度：弱",
        1: "密码强度：非常弱",
        0: "密码强度：不合格"
    }
    
    return {
        "score": score,
        "feedback": feedback_map.get(score, ""),
        "rules": rules,
        "requirements": {
            "min_length": config.password_min_length,
            "require_uppercase": config.password_require_uppercase,
            "require_number": config.password_require_number,
            "require_special": config.password_require_special
        }
    }
