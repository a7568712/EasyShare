# -*- coding: utf-8 -*-
"""
EasyShare 文件操作路由
处理文件浏览、上传、下载等操作
"""

import os
import tempfile
from flask import render_template, request, jsonify, session, send_file, redirect, Response

from routes import file_bp
from config import config, APP_NAME, APP_VERSION
from database import add_log, add_to_trash, get_user_by_id
from utils.security import (
    login_required, admin_required, get_client_ip,
    get_current_user, is_safe_path, check_file_permission
)
from utils.file_utils import (
    list_directory, get_path_info, create_directory,
    rename_path, delete_file, get_breadcrumbs, get_parent_path,
    save_upload_file, get_free_filename, create_zip_archive,
    get_dir_size, format_file_size, search_files
)


@file_bp.route("/")
def index():
    """主页面"""
    user = get_current_user()
    theme = config.theme
    
    # 检查匿名访问
    if not user and not config.anonymous_access:
        return redirect("/login")
    
    # 网站标题和浏览器标签（完全自定义）
    welcome_title = config.site_title
    page_title = config.page_title
    
    # 传递配置到模板
    return render_template("index.html", theme=theme, user=user, 
                          anonymous_upload=config.anonymous_upload,
                          anonymous_batch_download=config.anonymous_batch_download,
                          welcome_title=welcome_title,
                          page_title=page_title,
                          app_version=APP_VERSION)


@file_bp.route("/login")
def login_page():
    """登录页面"""
    if get_current_user():
        return redirect("/")
    return render_template("login.html", theme=config.theme, 
                          page_title=config.page_title)


@file_bp.route("/admin")
@login_required
def admin_page():
    """管理后台页面"""
    user = get_current_user()
    if user['role'] != 'admin':
        return redirect("/")
    return render_template("admin.html", theme=config.theme, user=user, 
                          page_title=config.page_title)


# ============ API 接口 ============

@file_bp.route("/api/auth/login", methods=["POST"])
def api_login():
    """用户登录"""
    from database import get_user_by_username, verify_password, update_last_login, record_login_attempt, clear_failed_attempts, get_recent_failed_attempts
    
    username = request.json.get("username", "").strip()
    password = request.json.get("password", "")
    ip = get_client_ip()
    
    if not username or not password:
        return jsonify({"success": False, "message": "请输入用户名和密码"})
    
    # 检查账户是否被锁定
    is_locked, locked_until, remaining = get_recent_failed_attempts(
        username, 
        config.login_lock_minutes, 
        config.login_max_attempts
    )
    
    if is_locked:
        # 计算剩余锁定时间
        from datetime import datetime
        try:
            lock_time_str = locked_until.replace('Z', '+00:00') if locked_until else None
            if lock_time_str:
                lock_time = datetime.fromisoformat(lock_time_str)
                remaining_seconds = int((lock_time - datetime.now()).total_seconds())
                if remaining_seconds < 0:
                    remaining_seconds = 0
                remaining_minutes = (remaining_seconds + 59) // 60
                return jsonify({
                    "success": False, 
                    "message": f"账户已被锁定，请在 {remaining_minutes} 分钟后重试",
                    "locked": True,
                    "remaining_seconds": remaining_seconds
                })
        except:
            pass
        return jsonify({
            "success": False, 
            "message": "账户已被锁定，请稍后再试",
            "locked": True
        })
    
    user = get_user_by_username(username)
    if not user:
        # 记录失败的登录尝试
        record_login_attempt(username, ip, success=False)
        is_locked, locked_until, remaining = get_recent_failed_attempts(
            username, 
            config.login_lock_minutes, 
            config.login_max_attempts
        )
        if is_locked:
            return jsonify({
                "success": False, 
                "message": f"登录失败次数过多，账户已被锁定，请在 {config.login_lock_minutes} 分钟后重试",
                "locked": True,
                "remaining_attempts": 0
            })
        return jsonify({
            "success": False, 
            "message": "用户名或密码错误",
            "remaining_attempts": remaining
        })
    
    if not verify_password(password, user["password_hash"]):
        # 记录失败的登录尝试
        record_login_attempt(username, ip, success=False)
        is_locked, locked_until, remaining = get_recent_failed_attempts(
            username, 
            config.login_lock_minutes, 
            config.login_max_attempts
        )
        if is_locked:
            return jsonify({
                "success": False, 
                "message": f"登录失败次数过多，账户已被锁定，请在 {config.login_lock_minutes} 分钟后重试",
                "locked": True,
                "remaining_attempts": 0
            })
        return jsonify({
            "success": False, 
            "message": "用户名或密码错误",
            "remaining_attempts": remaining
        })
    
    if not user["is_active"]:
        return jsonify({"success": False, "message": "账户已被禁用"})
    
    # 登录成功，清除失败记录
    clear_failed_attempts(username)
    record_login_attempt(username, ip, success=True)
    
    # 防止Session固定攻击：登录后重新生成session ID
    session.clear()
    session.permanent = True
    from datetime import timedelta
    from flask import current_app
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["allow_batch_download"] = user.get("allow_batch_download", True)
    
    update_last_login(user["id"])
    add_log(user["id"], user["username"], "login", ip=ip)
    
    return jsonify({
        "success": True,
        "message": "登录成功",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "allow_batch_download": user.get("allow_batch_download", True)
        }
    })


@file_bp.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    """用户登出"""
    user = get_current_user()
    add_log(user["id"], user["username"], "logout", ip=get_client_ip())
    session.clear()
    return jsonify({"success": True, "message": "已退出登录"})


@file_bp.route("/api/auth/check")
def api_check():
    """检查登录状态"""
    user = get_current_user()
    if user:
        return jsonify({
            "success": True,
            "logged_in": True,
            "user": user
        })
    else:
        return jsonify({
            "success": True,
            "logged_in": False,
            "anonymous_access": config.anonymous_access
        })


@file_bp.route("/api/theme", methods=["POST"])
def api_toggle_theme():
    """切换主题"""
    data = request.json
    new_theme = data.get("theme", "light")
    
    if new_theme not in ["light", "dark"]:
        return jsonify({"success": False, "message": "无效的主题"})
    
    # 保存到配置
    config.set("theme", new_theme)
    config.save()
    
    return jsonify({"success": True, "theme": new_theme})


@file_bp.route("/api/files/list")
def api_list():
    """获取文件列表"""
    user = get_current_user()

    # 检查权限
    if not user and not config.anonymous_access:
        return jsonify({"success": False, "message": "需要登录"})

    # 获取当前路径
    path_param = request.args.get("path", "/")
    if path_param == "/":
        current_path = config.share_path
    else:
        # 解码并处理路径
        path_param = path_param.lstrip("/")
        current_path = os.path.join(config.share_path, path_param)

    # 安全检查
    if not is_safe_path(config.share_path, current_path):
        return jsonify({"success": False, "message": "路径不合法"})

    # 获取文件列表
    items = list_directory(current_path)
    if items is None:
        return jsonify({"success": False, "message": "无法访问该目录"})

    # 获取面包屑
    breadcrumbs = get_breadcrumbs(current_path)
    parent_path = get_parent_path(current_path)

    # 获取目录大小
    if os.path.isdir(current_path):
        dir_size = get_dir_size(current_path)
        dir_size_str = format_file_size(dir_size)
    else:
        dir_size_str = "-"

    return jsonify({
        "success": True,
        "path": path_param or "/",
        "parent_path": os.path.relpath(parent_path, config.share_path) if parent_path != config.share_path else "/",
        "items": items,
        "breadcrumbs": breadcrumbs,
        "dir_size": dir_size_str,
        "readonly": not check_file_permission(user, current_path, require_write=True) if user else not config.anonymous_readonly
    })



@file_bp.route("/api/files/upload", methods=["POST"])
def api_upload():
    """上传文件"""
    user = get_current_user()
    
    # 检查权限
    if not user and not config.anonymous_access:
        return jsonify({"success": False, "message": "需要登录"})
    
    # 检查上传权限
    if not user and not config.anonymous_upload:
        return jsonify({"success": False, "message": "访客不允许上传"})
    
    if not check_file_permission(user, config.share_path, require_write=True) if user else not config.anonymous_readonly:
        return jsonify({"success": False, "message": "没有上传权限"})
    
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "没有选择文件"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "没有选择文件"})
    
    # 检查文件大小
    file.seek(0, 2)  # 移到文件末尾
    file_size = file.tell()
    file.seek(0)  # 重置位置
    max_size = config.max_upload_size
    if file_size > max_size:
        from utils.file_utils import format_file_size
        return jsonify({
            "success": False, 
            "message": f"文件大小超过限制 ({format_file_size(max_size)})",
            "max_size": max_size
        })
    
    # 获取目标路径
    path_param = request.form.get("path", "/")
    if path_param == "/":
        dest_dir = config.share_path
    else:
        path_param = path_param.lstrip("/")
        dest_dir = os.path.join(config.share_path, path_param)
    
    # 检查是否是文件夹上传模式
    folder_name = request.form.get("folderName")
    relative_path = request.form.get("relativePath")
    
    # 如果是文件夹上传，需要在目标目录下创建子文件夹
    if folder_name:
        dest_dir = os.path.join(dest_dir, folder_name)
        os.makedirs(dest_dir, exist_ok=True)
        
        # 如果有相对路径，需要创建子目录结构
        if relative_path and '/' in relative_path:
            sub_dir = os.path.join(dest_dir, os.path.dirname(relative_path))
            os.makedirs(sub_dir, exist_ok=True)
            dest_dir = sub_dir
    
    if not is_safe_path(config.share_path, dest_dir):
        return jsonify({"success": False, "message": "路径不合法"})
    
    # 保存文件 - 使用标准流式写入
    filename = get_free_filename(dest_dir, file.filename)
    dest_path = os.path.join(dest_dir, filename)
    
    try:
        # 直接遍历文件流，逐块写入，避免内存占用
        with open(dest_path, 'wb') as f:
            for chunk in file:
                f.write(chunk)
        
        # 记录日志
        relative_path = os.path.relpath(dest_path, config.share_path)
        if user:
            add_log(user["id"], user["username"], "upload", relative_path, ip=get_client_ip())
        else:
            add_log(None, "anonymous", "upload", relative_path, ip=get_client_ip())
        
        return jsonify({
            "success": True,
            "message": "上传成功",
            "filename": filename,
            "path": relative_path
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"上传失败: {str(e)}"})






# @file_bp.route("/api/files/upload-folder", methods=["POST"])
# @login_required
# def api_upload_folder():
#     """上传整个文件夹（支持ZIP格式和直接文件夹上传）- 已禁用ZIP解压功能"""
#     return jsonify({"success": False, "message": "ZIP上传功能已禁用"})


def upload_single_file_from_folder(user, dest_dir, folder_name, relative_path):
    """上传文件夹中的单个文件"""
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "没有选择文件"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "没有选择文件"})

    try:
        # 构建目标文件夹路径
        folder_dir = os.path.join(dest_dir, folder_name)

        # 构建文件的完整路径
        file_path = os.path.join(folder_dir, relative_path)

        # 安全检查
        if not is_safe_path(config.share_path, file_path):
            return jsonify({"success": False, "message": "路径不合法"})

        # 确保父目录存在
        parent_dir = os.path.dirname(file_path)
        os.makedirs(parent_dir, exist_ok=True)

        # 流式保存文件
        with open(file_path, 'wb') as f:
            for chunk in file:
                f.write(chunk)

        # 记录日志
        relative_path_full = os.path.relpath(file_path, config.share_path)
        add_log(user["id"], user["username"], "upload", relative_path_full, f"上传文件 {relative_path}", get_client_ip())

        return jsonify({
            "success": True,
            "message": "上传成功",
            "path": relative_path_full,
            "folder_name": folder_name
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"上传失败: {str(e)}"})


@file_bp.route("/api/files/upload-batch", methods=["POST"])
@login_required
def api_upload_batch():
    """批量上传文件"""
    from utils.file_utils import format_file_size
    
    user = get_current_user()

    # 检查权限
    if not check_file_permission(user, config.share_path, require_write=True):
        return jsonify({"success": False, "message": "没有上传权限"})

    if 'files' not in request.files:
        return jsonify({"success": False, "message": "没有选择文件"})

    files = request.files.getlist('files')
    if not files:
        return jsonify({"success": False, "message": "没有选择文件"})

    # 获取目标路径
    path_param = request.form.get("path", "/")
    if path_param == "/":
        dest_dir = config.share_path
    else:
        path_param = path_param.lstrip("/")
        dest_dir = os.path.join(config.share_path, path_param)

    if not is_safe_path(config.share_path, dest_dir):
        return jsonify({"success": False, "message": "路径不合法"})

    results = []
    success_count = 0
    error_count = 0
    max_size = config.max_upload_size

    for file in files:
        if file.filename == '':
            continue

        # 检查单个文件大小
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        if file_size > max_size:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": f"文件大小超过限制 ({format_file_size(max_size)})"
            })
            error_count += 1
            continue

        filename = get_free_filename(dest_dir, file.filename)
        dest_path = os.path.join(dest_dir, filename)

        try:
            # 使用标准流式写入
            with open(dest_path, 'wb') as f:
                for chunk in file:
                    f.write(chunk)
            relative_path = os.path.relpath(dest_path, config.share_path)
            results.append({
                "filename": filename,
                "path": relative_path,
                "success": True
            })
            success_count += 1
            add_log(user["id"], user["username"], "upload", relative_path, "批量上传", get_client_ip())
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
            error_count += 1

    return jsonify({
        "success": error_count == 0,
        "message": f"上传完成：{success_count} 成功，{error_count} 失败",
        "results": results,
        "success_count": success_count,
        "error_count": error_count
    })


@file_bp.route("/api/files/mkdir", methods=["POST"])
@login_required
def api_mkdir():
    """创建文件夹"""
    user = get_current_user()
    data = request.json
    
    path_param = data.get("path", "/")
    dir_name = data.get("name", "").strip()
    
    if not dir_name:
        return jsonify({"success": False, "message": "请输入文件夹名称"})
    
    if path_param == "/":
        dir_path = config.share_path
    else:
        path_param = path_param.lstrip("/")
        dir_path = os.path.join(config.share_path, path_param)
    
    success, message = create_directory(dir_path, dir_name)
    
    if success:
        relative_path = os.path.join(path_param, dir_name).replace("\\", "/")
        add_log(user["id"], user["username"], "mkdir", relative_path, ip=get_client_ip())
    
    return jsonify({"success": success, "message": message})


@file_bp.route("/api/files/rename", methods=["POST"])
@login_required
def api_rename():
    """重命名文件/文件夹"""
    user = get_current_user()
    data = request.json
    
    old_path = data.get("path", "")
    new_name = data.get("name", "").strip()
    
    if not old_path or not new_name:
        return jsonify({"success": False, "message": "参数不完整"})
    
    old_full_path = os.path.join(config.share_path, old_path.lstrip("/"))
    success, message = rename_path(old_full_path, new_name)
    
    if success:
        add_log(user["id"], user["username"], "rename", old_path, f"重命名为: {new_name}", get_client_ip())
    
    return jsonify({"success": success, "message": message})


@file_bp.route("/api/files/delete", methods=["POST"])
@login_required
def api_delete():
    """删除文件/文件夹"""
    import shutil
    
    user = get_current_user()
    data = request.json
    
    file_path = data.get("path", "").strip()
    if not file_path:
        return jsonify({"success": False, "message": "请指定要删除的文件"})
    
    full_path = os.path.join(config.share_path, file_path.lstrip("/"))
    
    # 获取文件信息用于记录
    info = get_path_info(full_path)
    if not info:
        return jsonify({"success": False, "message": "文件不存在"})
    
    # 创建备份（用于回收站恢复）
    # 获取应用根目录（兼容打包后的exe环境）
    from pathlib import Path
    import sys
    if getattr(sys, 'frozen', False):
        app_root = Path(sys.executable).parent
    else:
        app_root = Path(__file__).parent.parent
    backup_dir = app_root / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup_filename = file_path.replace('/', '_').replace('\\', '_')
    backup_path = backup_dir / backup_filename
    
    try:
        # 复制到备份目录
        if info["is_dir"]:
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(full_path, backup_path)
        else:
            shutil.copy2(full_path, backup_path)
    except Exception as e:
        # 备份失败也继续删除，但记录日志
        print(f"备份文件失败: {e}")
    
    # 记录到回收站
    add_to_trash(
        file_path,
        "dir" if info["is_dir"] else "file",
        info["size"],
        user["id"]
    )
    
    # 删除文件
    success, message = delete_file(full_path)
    
    if success:
        add_log(user["id"], user["username"], "delete", file_path, ip=get_client_ip())
    
    return jsonify({"success": success, "message": message})


@file_bp.route("/api/files/batch-delete", methods=["POST"])
@login_required
def api_batch_delete():
    """批量删除文件/文件夹"""
    import shutil
    
    user = get_current_user()
    data = request.json
    
    paths = data.get("paths", [])
    if not paths or not isinstance(paths, list):
        return jsonify({"success": False, "message": "请选择要删除的文件"})
    
    results = {"success": [], "failed": []}
    
    for file_path in paths:
        file_path = file_path.strip()
        if not file_path:
            continue
        
        full_path = os.path.join(config.share_path, file_path.lstrip("/"))
        
        # 获取文件信息用于记录
        info = get_path_info(full_path)
        if not info:
            results["failed"].append({"path": file_path, "message": "文件不存在"})
            continue
        
        # 创建备份
        from pathlib import Path
        import sys
        if getattr(sys, 'frozen', False):
            app_root = Path(sys.executable).parent
        else:
            app_root = Path(__file__).parent.parent
        backup_dir = app_root / 'backups'
        backup_dir.mkdir(exist_ok=True)
        backup_filename = file_path.replace('/', '_').replace('\\', '_')
        backup_path = backup_dir / backup_filename
        
        try:
            if info["is_dir"]:
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                shutil.copytree(full_path, backup_path)
            else:
                shutil.copy2(full_path, backup_path)
        except Exception as e:
            print(f"备份文件失败: {e}")
        
        # 记录到回收站
        add_to_trash(
            file_path,
            "dir" if info["is_dir"] else "file",
            info["size"],
            user["id"]
        )
        
        # 删除文件
        success, message = delete_file(full_path)
        
        if success:
            results["success"].append(file_path)
            add_log(user["id"], user["username"], "delete", file_path, "批量删除", get_client_ip())
        else:
            results["failed"].append({"path": file_path, "message": message})
    
    total = len(results["success"]) + len(results["failed"])
    msg = f"成功删除 {len(results['success'])}/{total} 个项目"
    if results["failed"]:
        msg += f"，失败 {len(results['failed'])} 个"
    
    return jsonify({
        "success": len(results["failed"]) == 0,
        "message": msg,
        "results": results
    })


def _make_download_response(file_path, filename):
    """生成下载响应，自动处理中文文件名和断点续传"""
    from urllib.parse import quote
    
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range')
    
    # 处理 Range 请求（断点续传）
    if range_header:
        try:
            range_match = range_header.replace('bytes=', '').split('-')
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if range_match[1] else file_size - 1
            
            if start >= file_size:
                return Response(status=416)
            
            end = min(end, file_size - 1)
            content_length = end - start + 1
            
            def generate():
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
            
            response = Response(
                generate(), status=206, mimetype='application/octet-stream',
                direct_passthrough=True
            )
            response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response.headers['Content-Length'] = str(content_length)
        except Exception:
            return Response(status=500)
        
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Disposition'] = f'attachment; filename="{quote(filename)}"; filename*=UTF-8\'\'{quote(filename)}'
        return response
    
    # 普通下载
    response = send_file(file_path, as_attachment=True, download_name=filename)
    response.headers['Content-Disposition'] = f'attachment; filename="{quote(filename)}"; filename*=UTF-8\'\'{quote(filename)}'
    response.headers['Accept-Ranges'] = 'bytes'
    return response


def _make_zip_response(zip_path, zip_filename):
    """生成 ZIP 下载响应"""
    from urllib.parse import quote
    response = send_file(zip_path, as_attachment=True, download_name=zip_filename)
    response.headers['Content-Disposition'] = f'attachment; filename="{quote(zip_filename)}"; filename*=UTF-8\'\'{quote(zip_filename)}'
    return response


def _stream_zip_archive(source_path, arcname=None):
    """流式打包单个文件/文件夹，返回生成器
    
    Args:
        source_path: 要打包的文件或目录路径
        arcname: 在 ZIP 中的名称（默认取 basename）
    """
    import zipstream
    
    zs = zipstream.ZipFile(compression=zipstream.ZIP_DEFLATED)
    
    if os.path.isdir(source_path):
        base_name = arcname or os.path.basename(source_path)
        for root, dirs, files in os.walk(source_path):
            rel_dir = os.path.relpath(root, source_path)
            for file in files:
                file_path = os.path.join(root, file)
                if rel_dir == '.':
                    z_name = os.path.join(base_name, file)
                else:
                    z_name = os.path.join(base_name, rel_dir, file)
                z_name = z_name.replace('\\', '/')
                # 使用生成器读取文件
                def read_chunks(path):
                    with open(path, 'rb') as f:
                        while True:
                            chunk = f.read(65536)
                            if not chunk:
                                break
                            yield chunk
                zs.write_iter(z_name, read_chunks(file_path))
        
        # 空目录
        if not any(os.walk(source_path)):
            zs.writestr(os.path.join(base_name, '.gitkeep').replace('\\', '/'), '')
    else:
        name = arcname or os.path.basename(source_path)
        def read_chunks(path):
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    yield chunk
        zs.write_iter(name, read_chunks(source_path))
    
    return zs


@file_bp.route("/api/files/batch-download", methods=["POST"])
def api_batch_download():
    """批量下载 - 返回文件和文件夹列表，由前端逐个调用下载接口"""
    user = get_current_user()

    # 检查权限：已登录用户（有批量下载权限）或允许匿名批量下载
    if not user and not config.anonymous_batch_download:
        return jsonify({"success": False, "message": "需要登录才能批量下载"})
    
    # 检查用户是否被禁止批量下载（管理员拥有全部权限）
    if user and user.get("role") != 'admin' and user.get("allow_batch_download") == 0:
        return jsonify({"success": False, "message": "您没有批量下载权限"})

    data = request.json
    paths = data.get("paths", [])

    if not paths or not isinstance(paths, list):
        return jsonify({"success": False, "message": "请选择要下载的文件"})

    # 验证路径，区分文件和文件夹
    files_to_download = []  # 单文件列表
    folders_to_zip = []     # 文件夹列表

    for fp in paths:
        fp = fp.strip()
        if not fp:
            continue
        full_path = os.path.join(config.share_path, fp.lstrip("/"))
        if not os.path.exists(full_path) or not is_safe_path(config.share_path, full_path):
            return jsonify({"success": False, "message": f"文件不存在: {fp}"})

        if os.path.isfile(full_path):
            files_to_download.append(fp)
        elif os.path.isdir(full_path):
            folders_to_zip.append(fp)

    if not files_to_download and not folders_to_zip:
        return jsonify({"success": False, "message": "没有有效的文件"})

    # 记录日志
    log_paths = "/".join(files_to_download + folders_to_zip)
    if user:
        add_log(user["id"], user["username"], "download", log_paths,
                f"批量下载（{len(files_to_download)}个文件，{len(folders_to_zip)}个文件夹）", get_client_ip())

    # 返回文件列表和文件夹列表
    return jsonify({
        "success": True,
        "files": files_to_download,
        "folders": folders_to_zip,
        "fileCount": len(files_to_download),
        "folderCount": len(folders_to_zip)
    })


@file_bp.route("/api/files/download")
def api_download():
    """下载文件（支持断点续传）"""
    user = get_current_user()
    
    if not user and not config.anonymous_access:
        return jsonify({"success": False, "message": "需要登录"}), 401
    
    file_path = request.args.get("path", "")
    if not file_path:
        return jsonify({"success": False, "message": "请指定要下载的文件"})
    
    # URL解码处理中文路径
    from urllib.parse import unquote
    file_path = unquote(file_path)
    full_path = os.path.join(config.share_path, file_path.lstrip("/"))
    full_path = os.path.normpath(full_path)
    
    if not is_safe_path(config.share_path, full_path):
        return jsonify({"success": False, "message": "路径不合法"})
    
    if not os.path.exists(full_path):
        return jsonify({"success": False, "message": "文件不存在"})
    
    # 文件夹打包下载（流式）
    if os.path.isdir(full_path):
        from urllib.parse import quote
        import zipstream
        
        zip_filename = os.path.basename(full_path) + ".zip"
        
        if user:
            add_log(user["id"], user["username"], "download", file_path, "ZIP打包下载", get_client_ip())
        
        # 流式打包
        zs = zipstream.ZipFile(compression=zipstream.ZIP_DEFLATED)
        for root, dirs, files in os.walk(full_path):
            rel_dir = os.path.relpath(root, full_path)
            for file in files:
                file_path = os.path.join(root, file)
                z_name = os.path.join(rel_dir, file) if rel_dir != '.' else file
                z_name = z_name.replace('\\', '/')
                zs.write(file_path, z_name)
        
        def generate():
            for chunk in zs:
                yield chunk
        
        response = Response(generate(), mimetype='application/zip')
        response.headers['Content-Disposition'] = f'attachment; filename="{quote(zip_filename)}"; filename*=UTF-8\'\'{quote(zip_filename)}'
        return response
    
    # 单文件下载
    filename = os.path.basename(full_path)
    if user:
        add_log(user["id"], user["username"], "download", file_path, ip=get_client_ip())
    
    return _make_download_response(full_path, filename)


@file_bp.route("/api/files/preview/<path:filepath>")
def api_preview(filepath):
    """在线预览文件"""
    user = get_current_user()
    
    if not user and not config.anonymous_access:
        return jsonify({"success": False, "message": "需要登录"}), 401
    
    full_path = os.path.join(config.share_path, filepath)
    
    if not is_safe_path(config.share_path, full_path):
        return jsonify({"success": False, "message": "路径不合法"})
    
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return jsonify({"success": False, "message": "文件不存在"})
    
    # 根据文件类型返回不同内容
    ext = os.path.splitext(full_path)[1].lower()
    
    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]:
        return send_file(full_path)
    
    if ext in [".svg"]:
        return send_file(full_path, mimetype="image/svg+xml")
    
    if ext in [".mp4", ".webm", ".ogg", ".mov"]:
        # 视频文件
        range_header = request.headers.get('Range')
        
        if range_header:
            # Range 请求处理
            range_match = range_header.replace('bytes=', '').split('-')
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if range_match[1] else None
            
            response = Response(
                _generate_video(full_path, start, end),
                status=206,
                mimetype='video/mp4',
                headers={
                    'Accept-Ranges': 'bytes',
                }
            )
            # 添加 Content-Length 和 Content-Range 头
            def add_range_headers():
                file_size = os.path.getsize(full_path)
                actual_end = min(end, file_size - 1) if end else file_size - 1
                actual_start = min(start, actual_end)
                content_length = actual_end - actual_start + 1
                response.headers['Content-Length'] = str(content_length)
                response.headers['Content-Range'] = f'bytes {actual_start}-{actual_end}/{file_size}'
            
            add_range_headers()
            return response
        else:
            file_size = os.path.getsize(full_path)
            return Response(
                _generate_video(full_path, 0, file_size - 1),
                mimetype='video/mp4',
                headers={
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(file_size)
                }
            )
    
    if ext in [".pdf"]:
        return send_file(full_path, mimetype='application/pdf')
    
    # 文本文件 - 直接返回纯文本（流式读取避免内存问题）
    try:
        # 流式读取，只读取前10万字符
        max_chars = 100000
        chunks = []
        total_chars = 0
        
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            while total_chars < max_chars:
                chunk = f.read(min(8192, max_chars - total_chars))
                if not chunk:
                    break
                chunks.append(chunk)
                total_chars += len(chunk)
        
        content = ''.join(chunks)
        content_bytes = content.encode('utf-8')
        
        response = Response(content_bytes, mimetype='text/plain; charset=utf-8')
        response.headers['Content-Length'] = str(len(content_bytes))
        return response
    except:
        return jsonify({"success": False, "message": "无法预览该文件"}), 400


def _generate_video(path, start=0, end=None):
    """生成视频响应（支持断点续传）- 优化版本，避免重复计算文件大小"""
    def generate():
        with open(path, 'rb') as f:
            f.seek(start)
            if end is not None:
                remaining = end - start + 1
                while remaining > 0:
                    chunk_size = min(65536, remaining)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
            else:
                # 无end限制，读取到文件结束
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    yield chunk
    
    return generate()


@file_bp.route("/api/config/theme", methods=["POST"])
def api_theme():
    """切换主题"""
    theme = request.json.get("theme", "light")
    if theme in ["light", "dark"]:
        return jsonify({"success": True, "theme": theme})
    return jsonify({"success": False, "message": "无效的主题"})


@file_bp.route("/api/files/search")
def api_search():
    """搜索文件"""
    user = get_current_user()

    if not user and not config.anonymous_access:
        return jsonify({"success": False, "message": "需要登录"})

    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"success": False, "message": "请输入搜索关键词"})

    if len(keyword) < 1:
        return jsonify({"success": False, "message": "关键词太短"})

    # 获取筛选条件
    filters = {}
    file_type = request.args.get("type", "all")
    if file_type != "all":
        filters['type'] = file_type

    size_min = request.args.get("size_min", type=int)
    if size_min:
        filters['size_min'] = size_min

    size_max = request.args.get("size_max", type=int)
    if size_max:
        filters['size_max'] = size_max

    date_from = request.args.get("date_from")
    if date_from:
        filters['date_from'] = date_from

    date_to = request.args.get("date_to")
    if date_to:
        filters['date_to'] = date_to

    # 限制搜索结果数量
    max_results = 200

    results = search_files(keyword, filters=filters if filters else None)
    total = len(results)
    results = results[:max_results]

    return jsonify({
        "success": True,
        "keyword": keyword,
        "results": results,
        "total": total,
        "truncated": total > max_results
    })
