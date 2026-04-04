# -*- coding: utf-8 -*-
"""
EasyShare 管理后台路由
处理用户管理、配置管理、日志查看等功能
"""

import os
import sys
import shutil
from flask import request, jsonify
from database import add_log as db_add_log

from routes import admin_bp
from config import config
from database import (
    get_all_users, create_user, update_user, delete_user,
    get_logs, get_log_count, get_trash_items, get_trash_count,
    restore_from_trash, delete_from_trash, empty_trash, get_user_by_id,
    add_log, verify_password
)
from utils.security import admin_required, login_required, get_client_ip, get_current_user, validate_password_strength
from utils.file_utils import delete_file, get_free_filename


@admin_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    """用户修改自己的密码"""
    data = request.json
    current_user = get_current_user()
    
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")
    
    if not old_password or not new_password:
        return jsonify({"success": False, "message": "请填写完整信息"})
    
    if new_password != confirm_password:
        return jsonify({"success": False, "message": "两次输入的新密码不一致"})
    
    # 验证旧密码
    user = get_user_by_id(current_user["id"])
    if not verify_password(old_password, user["password_hash"]):
        return jsonify({"success": False, "message": "原密码错误"})
    
    # 新密码强度验证
    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        return jsonify({"success": False, "message": error_msg})
    
    try:
        update_user(current_user["id"], password=new_password)
        db_add_log(current_user["id"], current_user["username"], "change_password", ip=get_client_ip())
        return jsonify({"success": True, "message": "密码修改成功"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@admin_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    """获取用户列表"""
    users = get_all_users()
    return jsonify({"success": True, "users": users})


@admin_bp.route("/users", methods=["POST"])
@admin_required
def add_user():
    """创建新用户"""
    import re
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "readonly")
    allow_batch_download = data.get("allow_batch_download", True)
    
    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"})
    
    # 用户名格式验证：只能包含字母、数字、下划线，长度3-20
    if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
        return jsonify({"success": False, "message": "用户名只能包含字母、数字、下划线，长度3-20个字符"})
    
    # 密码强度验证
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return jsonify({"success": False, "message": error_msg})
    
    if role not in ["admin", "readonly", "readwrite"]:
        return jsonify({"success": False, "message": "无效的角色"})
    
    try:
        user_id = create_user(username, password, role, allow_batch_download)
        user = get_user_by_id(user_id)
        
        # 记录日志
        current_user = get_current_user()
        db_add_log(current_user["id"], current_user["username"], "create_user", username, f"创建用户: {username}", get_client_ip())
        
        return jsonify({
            "success": True,
            "message": "用户创建成功",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "allow_batch_download": user["allow_batch_download"]
            }
        })
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            return jsonify({"success": False, "message": "用户名已存在"})
        return jsonify({"success": False, "message": str(e)})


@admin_bp.route("/users/<int:user_id>", methods=["PUT"])
@admin_required
def edit_user(user_id):
    """更新用户信息"""
    import re
    data = request.json
    current_user = get_current_user()
    
    # 不能修改自己的角色
    if user_id == current_user["id"] and data.get("role"):
        return jsonify({"success": False, "message": "不能修改自己的角色"})
    
    # 不能禁用自己
    if user_id == current_user["id"] and data.get("is_active") is False:
        return jsonify({"success": False, "message": "不能禁用自己"})
    
    # 不能将唯一的管理员降级
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "用户不存在"})
    
    new_role = data.get("role")
    if target_user["role"] == "admin" and new_role and new_role != "admin":
        # 检查是否还有其他管理员
        admins = [u for u in get_all_users() if u["role"] == "admin" and u["id"] != user_id]
        if len(admins) == 0:
            return jsonify({"success": False, "message": "不能将唯一的管理员降级"})
    
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")
    is_active = data.get("is_active")
    allow_batch_download = data.get("allow_batch_download")
    
    # 用户名格式验证：只能包含字母、数字、下划线，长度3-20
    if username is not None:
        username = username.strip()
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            return jsonify({"success": False, "message": "用户名只能包含字母、数字、下划线，长度3-20个字符"})
    
    # 如果要修改密码，进行密码强度验证
    if password:
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            return jsonify({"success": False, "message": error_msg})
    
    try:
        update_user(user_id, username, password, role, is_active, allow_batch_download)
        db_add_log(current_user["id"], current_user["username"], "update_user", str(user_id), f"更新用户ID: {user_id}", get_client_ip())
        return jsonify({"success": True, "message": "用户更新成功"})
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            return jsonify({"success": False, "message": "用户名已存在"})
        return jsonify({"success": False, "message": str(e)})


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def remove_user(user_id):
    """删除用户"""
    current_user = get_current_user()
    
    if user_id == current_user["id"]:
        return jsonify({"success": False, "message": "不能删除自己"})
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "message": "用户不存在"})
    
    if user["role"] == "admin":
        # 检查是否还有其他管理员
        admins = [u for u in get_all_users() if u["role"] == "admin"]
        if len(admins) <= 1:
            return jsonify({"success": False, "message": "不能删除最后一个管理员"})
    
    try:
        delete_user(user_id)
        db_add_log(current_user["id"], current_user["username"], "delete_user", str(user_id), f"删除用户: {user['username']}", get_client_ip())
        return jsonify({"success": True, "message": "用户删除成功"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@admin_bp.route("/config", methods=["GET"])
@admin_required
def get_config():
    """获取配置"""
    return jsonify({
        "success": True,
        "config": {
            # 网站设置
            "site_title": config.site_title,
            "page_title": config.page_title,
            # 系统配置
            "share_path": config.share_path,
            "port": config.port,
            "host": config.host,
            "theme": config.theme,
            "anonymous_access": config.anonymous_access,
            "anonymous_readonly": config.anonymous_readonly,
            "anonymous_upload": config.anonymous_upload,
            "anonymous_batch_download": config.anonymous_batch_download,
            "hidden_folders": config.hidden_folders,
            "max_upload_size": config.max_upload_size,
            # 安全策略配置
            "password_min_length": config.password_min_length,
            "password_require_uppercase": config.password_require_uppercase,
            "password_require_number": config.password_require_number,
            "password_require_special": config.password_require_special,
            "login_max_attempts": config.login_max_attempts,
            "login_lock_minutes": config.login_lock_minutes,
            "trash_retention_days": config.trash_retention_days
        }
    })


@admin_bp.route("/site-config", methods=["PUT"])
@admin_required
def save_site_config():
    """保存网站设置"""
    data = request.json
    
    try:
        # 网站标题
        if "site_title" in data and data["site_title"].strip():
            config.set("site_title", data["site_title"].strip())
        
        # 浏览器标签标题
        if "page_title" in data and data["page_title"].strip():
            config.set("page_title", data["page_title"].strip())
        
        # 保存到配置文件
        config.save()
        
        return jsonify({"success": True, "message": "网站设置已保存"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@admin_bp.route("/config", methods=["PUT"])
@admin_required
def save_config():
    """保存配置"""
    data = request.json
    current_user = get_current_user()
    
    # 更新配置
    if "share_path" in data:
        new_path = os.path.abspath(data["share_path"])
        if os.path.exists(new_path) and os.path.isdir(new_path):
            config.set("share_path", new_path)
        else:
            return jsonify({"success": False, "message": "共享目录不存在"})
    
    if "port" in data:
        port = int(data["port"])
        if 1 <= port <= 65535:
            config.set("port", port)
        else:
            return jsonify({"success": False, "message": "端口号无效"})
    
    if "host" in data:
        config.set("host", data["host"])
    
    if "theme" in data:
        config.set("theme", data["theme"])
    
    if "anonymous_access" in data:
        config.set("anonymous_access", bool(data["anonymous_access"]))
    
    if "anonymous_readonly" in data:
        config.set("anonymous_readonly", bool(data["anonymous_readonly"]))
    
    if "anonymous_upload" in data:
        config.set("anonymous_upload", bool(data["anonymous_upload"]))
    
    if "anonymous_batch_download" in data:
        config.set("anonymous_batch_download", bool(data["anonymous_batch_download"]))
    
    if "hidden_folders" in data:
        config.set("hidden_folders", data["hidden_folders"])
    
    if "max_upload_size" in data:
        size = int(data["max_upload_size"])
        max_limit = 100 * 1024 * 1024 * 1024  # 100GB
        if size > max_limit:
            return jsonify({"success": False, "message": "单文件大小不能超过 100GB"})
        if size < 0:
            return jsonify({"success": False, "message": "文件大小不能为负数"})
        config.set("max_upload_size", size)
    
    # 安全策略配置
    if "password_min_length" in data:
        length = int(data["password_min_length"])
        if 4 <= length <= 32:
            config.set("password_min_length", length)
        else:
            return jsonify({"success": False, "message": "密码最小长度应在 4-32 之间"})
    
    if "password_require_uppercase" in data:
        config.set("password_require_uppercase", bool(data["password_require_uppercase"]))
    
    if "password_require_number" in data:
        config.set("password_require_number", bool(data["password_require_number"]))
    
    if "password_require_special" in data:
        config.set("password_require_special", bool(data["password_require_special"]))
    
    if "login_max_attempts" in data:
        attempts = int(data["login_max_attempts"])
        if 3 <= attempts <= 20:
            config.set("login_max_attempts", attempts)
        else:
            return jsonify({"success": False, "message": "登录最大尝试次数应在 3-20 之间"})
    
    if "login_lock_minutes" in data:
        minutes = int(data["login_lock_minutes"])
        if 1 <= minutes <= 1440:
            config.set("login_lock_minutes", minutes)
        else:
            return jsonify({"success": False, "message": "锁定时间应在 1-1440 分钟之间"})
    
    if "trash_retention_days" in data:
        days = int(data["trash_retention_days"])
        if 1 <= days <= 365:
            config.set("trash_retention_days", days)
        else:
            return jsonify({"success": False, "message": "回收站保留天数应在 1-365 之间"})
    
    # 保存到文件
    if not config.save():
        return jsonify({"success": False, "message": "保存配置文件失败，请检查权限"})
    
    db_add_log(current_user["id"], current_user["username"], "update_config", ip=get_client_ip())
    
    return jsonify({"success": True, "message": "配置已保存"})


@admin_bp.route("/logs", methods=["GET"])
@admin_required
def list_logs():
    """获取日志列表"""
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 50, type=int)
    action = request.args.get("action")
    
    offset = (page - 1) * limit
    logs = get_logs(limit, offset, action=action)
    total = get_log_count(action=action)
    
    return jsonify({
        "success": True,
        "logs": logs,
        "total": total,
        "page": page,
        "limit": limit
    })


@admin_bp.route("/trash", methods=["GET"])
@admin_required
def list_trash():
    """获取回收站"""
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 50, type=int)
    
    offset = (page - 1) * limit
    items = get_trash_items(limit, offset)
    total = get_trash_count()
    
    return jsonify({
        "success": True,
        "items": items,
        "total": total,
        "page": page,
        "limit": limit
    })


@admin_bp.route("/trash/restore", methods=["POST"])
@admin_required
def restore_trash():
    """恢复文件"""
    data = request.json
    trash_id = data.get("id")
    
    if not trash_id:
        return jsonify({"success": False, "message": "请指定要恢复的文件"})
    
    item = restore_from_trash(trash_id)
    if not item:
        return jsonify({"success": False, "message": "文件不存在"})
    
    original_path = os.path.join(config.share_path, item["original_path"])
    
    # 检查原目录是否存在
    parent_dir = os.path.dirname(original_path)
    if not os.path.exists(parent_dir):
        return jsonify({"success": False, "message": "原目录已被删除，无法恢复"})
    
    # 检查是否已存在同名文件
    if os.path.exists(original_path):
        # 重命名
        filename = get_free_filename(parent_dir, os.path.basename(original_path))
        original_path = os.path.join(parent_dir, filename)
    
    # 恢复文件
    # 检查备份目录是否存在对应的备份文件
    # 获取应用根目录（兼容打包后的exe环境）
    if getattr(sys, 'frozen', False):
        app_root = Path(sys.executable).parent
    else:
        app_root = Path(__file__).parent.parent
    backup_dir = app_root / 'backups'
    backup_path = backup_dir / item["original_path"].replace('/', '_').replace('\\', '_')
    
    if os.path.exists(backup_path):
        # 从备份恢复
        try:
            if item["file_type"] == "dir":
                shutil.copytree(backup_path, original_path)
            else:
                shutil.copy2(backup_path, original_path)
        except Exception as e:
            return jsonify({"success": False, "message": f"恢复失败: {str(e)}"})
    else:
        # 没有备份，无法恢复
        delete_from_trash(trash_id)
        return jsonify({
            "success": False,
            "message": "文件已被永久删除，无备份可恢复"
        })
    
    # 删除回收站记录
    delete_from_trash(trash_id)
    
    current_user = get_current_user()
    db_add_log(current_user["id"], current_user["username"], "restore", item["original_path"], ip=get_client_ip())
    
    return jsonify({
        "success": True,
        "message": "文件已恢复",
        "path": item["original_path"]
    })


@admin_bp.route("/trash", methods=["DELETE"])
@admin_required
def clear_trash():
    """清空回收站"""
    empty_trash()
    
    current_user = get_current_user()
    db_add_log(current_user["id"], current_user["username"], "empty_trash", ip=get_client_ip())
    
    return jsonify({"success": True, "message": "回收站已清空"})


@admin_bp.route("/trash/permanent", methods=["POST"])
@admin_required
def permanent_delete():
    """永久删除文件"""
    data = request.json
    trash_id = data.get("id")
    
    if not trash_id:
        return jsonify({"success": False, "message": "请指定要删除的文件"})
    
    item = restore_from_trash(trash_id)
    if not item:
        return jsonify({"success": False, "message": "文件不存在"})
    
    # 删除实际文件
    full_path = os.path.join(config.share_path, item["original_path"])
    if os.path.exists(full_path):
        success, message = delete_file(full_path)
        if not success:
            return jsonify({"success": False, "message": f"删除失败: {message}"})
    
    # 从数据库删除记录
    delete_from_trash(trash_id)
    
    current_user = get_current_user()
    db_add_log(current_user["id"], current_user["username"], "permanent_delete", item["original_path"], ip=get_client_ip())
    
    return jsonify({"success": True, "message": "文件已永久删除"})


@admin_bp.route("/restart", methods=["POST"])
@admin_required
def restart_server():
    """重启服务器"""
    import subprocess
    import time
    import threading
    import os
    
    current_user = get_current_user()
    db_add_log(current_user["id"], current_user["username"], "restart", ip=get_client_ip())
    
    # 获取当前程序路径（兼容exe和py）
    exe_path = sys.executable
    
    # 获取当前脚本路径
    script_path = os.path.abspath(__file__)
    main_path = os.path.join(os.path.dirname(script_path), 'main.py')
    
    # 获取当前工作目录
    cwd = os.getcwd()
    
    # 获取启动参数（端口等）
    port = config.port
    host = config.host
    share_path = config.share_path
    
    def do_restart():
        """执行重启"""
        time.sleep(1)
        try:
            if sys.platform == 'win32':
                # 检查是否是exe打包程序
                if exe_path.lower().endswith('.exe'):
                    # exe模式：直接启动exe
                    cmd = f'cmd /c "cd /d {cwd} && start "" "{exe_path}" -p {port} -a {host} -d "{share_path}"'
                else:
                    # Python模式：启动python解释器
                    cmd = f'cmd /c "cd /d {cwd} && start "" "{exe_path}" "{main_path}" -p {port} -a {host} -d "{share_path}"'
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen(
                    [exe_path, main_path, "-p", str(port), "-a", host, "-d", share_path],
                    cwd=cwd,
                    start_new_session=True
                )
        except Exception as e:
            print(f"启动新进程失败: {e}")
        
        # 退出当前进程
        time.sleep(0.5)
        os._exit(0)
    
    try:
        threading.Thread(target=do_restart, daemon=True).start()
        return jsonify({"success": True, "message": "服务器正在重启..."})
    except Exception as e:
        return jsonify({"success": False, "message": f"重启失败: {str(e)}"})


@admin_bp.route("/autostart", methods=["GET"])
@admin_required
def get_autostart_status():
    """获取开机自启动状态"""
    try:
        import winreg
        APP_NAME_LOCAL = "EasyShare"
        
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME_LOCAL)
            enabled = value is not None
        except FileNotFoundError:
            enabled = False
        finally:
            winreg.CloseKey(key)
        
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        return jsonify({"success": True, "enabled": False})


@admin_bp.route("/autostart", methods=["POST"])
@admin_required
def toggle_autostart():
    """配置开机自启动"""
    data = request.json or {}
    enable = data.get("enable", True)
    
    try:
        import winreg
        APP_NAME_LOCAL = "EasyShare"
        
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        
        if enable:
            exe_path = sys.executable
            winreg.SetValueEx(key, APP_NAME_LOCAL, 0, winreg.REG_SZ, f'"{exe_path}"')
            message = "开机自启动已开启"
        else:
            try:
                winreg.DeleteValue(key, APP_NAME_LOCAL)
                message = "开机自启动已关闭"
            except FileNotFoundError:
                message = "开机自启动本来就没有开启"
        
        winreg.CloseKey(key)
        
        current_user = get_current_user()
        db_add_log(current_user["id"], current_user["username"], "autostart", detail=message, ip=get_client_ip())
        
        return jsonify({"success": True, "message": message})
    except PermissionError:
        return jsonify({"success": False, "message": "需要管理员权限"})
    except Exception as e:
        return jsonify({"success": False, "message": f"配置失败: {str(e)}"})
