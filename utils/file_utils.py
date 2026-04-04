# -*- coding: utf-8 -*-
"""
EasyShare 文件操作工具
提供文件/文件夹的各种操作功能
"""

import os
import shutil
import zipfile
import hashlib
import html
from datetime import datetime
from pathlib import Path

from config import config, PREVIEWABLE_TYPES, IGNORED_PATTERNS
from utils.security import is_safe_path, is_hidden_folder


def format_file_size(size):
    """格式化文件大小显示"""
    if size < 0:
        return "-"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def get_file_icon(filename, is_dir=False):
    """根据文件名或类型获取图标"""
    if is_dir:
        return "📁"
    
    ext = os.path.splitext(filename)[1].lower()
    
    icons = {
        # 图片
        ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".webp": "🖼️", ".bmp": "🖼️", ".svg": "🖼️",
        # 视频
        ".mp4": "🎬", ".avi": "🎬", ".mkv": "🎬", ".mov": "🎬", ".wmv": "🎬", ".flv": "🎬", ".webm": "🎬",
        # 音频
        ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵", ".aac": "🎵", ".ogg": "🎵",
        # 文档
        ".pdf": "📕", ".doc": "📘", ".docx": "📘", ".xls": "📗", ".xlsx": "📗",
        ".ppt": "📙", ".pptx": "📙", ".txt": "📄", ".md": "📝",
        # 压缩
        ".zip": "🗜️", ".rar": "🗜️", ".7z": "🗜️", ".tar": "🗜️", ".gz": "🗜️",
        # 代码
        ".py": "🐍", ".js": "📜", ".ts": "📜", ".html": "🌐", ".css": "🎨", ".json": "📋",
        ".java": "☕", ".c": "⚙️", ".cpp": "⚙️", ".h": "⚙️", ".go": "🔵", ".rs": "🦀",
        # 其他
        ".exe": "⚙️", ".dll": "⚙️", ".iso": "💿", ".dmg": "💿",
    }
    
    return icons.get(ext, "📄")


def get_preview_type(filename):
    """获取文件预览类型"""
    ext = os.path.splitext(filename)[1].lower()
    
    for ptype, extensions in PREVIEWABLE_TYPES.items():
        if ext in extensions:
            return ptype
    
    return None


def is_ignored(name):
    """检查文件/文件夹是否应该忽略"""
    return name in IGNORED_PATTERNS


def list_directory(dir_path):
    """
    列出目录内容
    
    Args:
        dir_path: 目录路径
        
    Returns:
        list: 文件/文件夹信息列表
    """
    share_path = config.share_path
    
    if not is_safe_path(share_path, dir_path):
        return None
    
    if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
        return None
    
    items = []
    
    try:
        for name in sorted(os.listdir(dir_path)):
            if is_ignored(name):
                continue
            if is_hidden_folder(name):
                continue
            
            full_path = os.path.join(dir_path, name)
            is_dir = os.path.isdir(full_path)
            
            try:
                stat = os.stat(full_path)
                size = stat.st_size if not is_dir else 0
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except:
                size = 0
                mtime = "-"
            
            items.append({
                "name": html.escape(name),  # XSS防护：HTML转义文件名
                "path": full_path,
                # 统一使用正斜杠，便于前端URL编码
                "relative_path": html.escape(os.path.relpath(full_path, share_path).replace('\\', '/')),  # XSS防护
                "is_dir": is_dir,
                "size": size,
                "size_display": format_file_size(size) if not is_dir else "-",
                "mtime": mtime,
                "icon": get_file_icon(name, is_dir),
                "preview_type": None if is_dir else get_preview_type(name)
            })
    except PermissionError:
        return None
    
    # 目录排在前面
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    
    return items


def get_path_info(path):
    """获取路径信息"""
    share_path = config.share_path
    
    if not is_safe_path(share_path, path):
        return None
    
    if not os.path.exists(path):
        return None
    
    is_dir = os.path.isdir(path)
    
    try:
        stat = os.stat(path)
        size = stat.st_size if not is_dir else 0
        mtime = datetime.fromtimestamp(stat.st_mtime)
    except:
        return None
    
    return {
        "name": os.path.basename(path),
        "path": path,
        "relative_path": os.path.relpath(path, share_path).replace('\\', '/'),
        "is_dir": is_dir,
        "size": size,
        "size_display": format_file_size(size) if not is_dir else "-",
        "mtime": mtime.strftime("%Y-%m-%d %H:%M:%S"),
        "mtime_ts": stat.st_mtime
    }


def create_directory(dir_path, dir_name):
    """创建目录"""
    share_path = config.share_path
    new_path = os.path.join(dir_path, dir_name)
    
    if not is_safe_path(share_path, new_path):
        return False, "路径不安全"
    
    if os.path.exists(new_path):
        return False, "目录已存在"
    
    try:
        os.makedirs(new_path, exist_ok=True)
        return True, "创建成功"
    except Exception as e:
        return False, str(e)


def rename_path(old_path, new_name):
    """重命名文件或目录"""
    share_path = config.share_path
    parent_dir = os.path.dirname(old_path)
    new_path = os.path.join(parent_dir, new_name)
    
    if not is_safe_path(share_path, old_path):
        return False, "路径不安全"
    
    if not is_safe_path(share_path, new_path):
        return False, "路径不安全"
    
    if os.path.exists(new_path):
        return False, "目标名称已存在"
    
    try:
        os.rename(old_path, new_path)
        return True, "重命名成功"
    except Exception as e:
        return False, str(e)


def delete_file(file_path):
    """删除文件或目录"""
    share_path = config.share_path
    
    if not is_safe_path(share_path, file_path):
        return False, "路径不安全"
    
    if not os.path.exists(file_path):
        return False, "文件不存在"
    
    try:
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
        return True, "删除成功"
    except Exception as e:
        return False, str(e)


def move_file(src_path, dest_dir):
    """移动文件或目录"""
    share_path = config.share_path
    filename = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, filename)
    
    if not is_safe_path(share_path, src_path):
        return False, "路径不安全"
    
    if not is_safe_path(share_path, dest_path):
        return False, "路径不安全"
    
    if os.path.exists(dest_path):
        return False, "目标位置已存在同名文件"
    
    try:
        shutil.move(src_path, dest_path)
        return True, "移动成功"
    except Exception as e:
        return False, str(e)


def copy_file(src_path, dest_dir):
    """复制文件或目录"""
    share_path = config.share_path
    filename = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, filename)
    
    if not is_safe_path(share_path, src_path):
        return False, "路径不安全"
    
    if not is_safe_path(share_path, dest_path):
        return False, "路径不安全"
    
    if os.path.exists(dest_path):
        return False, "目标位置已存在同名文件"
    
    try:
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path)
        else:
            shutil.copy2(src_path, dest_path)
        return True, "复制成功"
    except Exception as e:
        return False, str(e)


def get_dir_size(dir_path):
    """计算目录大小（递归计算所有子目录）"""
    total_size = 0
    try:
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                fp = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(fp)
                except:
                    pass
    except:
        pass
    return total_size


def create_zip_archive(dir_path, output_path, check_safe=True):
    """创建ZIP压缩包 - 流式写入，支持大文件
    
    Args:
        dir_path: 要压缩的目录/文件路径
        output_path: ZIP输出路径
        check_safe: 是否检查安全路径（临时目录应设为False）
    """
    import traceback
    
    # 安全检查
    if check_safe:
        share_path = config.share_path
        if not is_safe_path(share_path, dir_path):
            return False
    
    try:
        dir_path = os.path.abspath(dir_path)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isdir(dir_path):
                for root, dirs, files in os.walk(dir_path):
                    rel_dir = os.path.relpath(root, dir_path)
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(rel_dir, file) if rel_dir != '.' else file
                        arcname = arcname.replace('\\', '/')
                        # 直接写入，流式处理大文件
                        zipf.write(file_path, arcname)
                    
                    # 空目录处理
                    if not dirs and not files and rel_dir != '.':
                        zip_info = zipfile.ZipInfo(os.path.join(rel_dir, '.gitkeep').replace('\\', '/'))
                        zipf.writestr(zip_info, '')
            else:
                basename = os.path.basename(dir_path)
                zipf.write(dir_path, basename)
        
        return True
    except Exception as e:
        print(f"创建压缩包失败: {e}")
        traceback.print_exc()
        return False


def get_breadcrumbs(current_path):
    """获取面包屑导航"""
    share_path = config.share_path
    relative = os.path.relpath(current_path, share_path)
    
    if relative == '.':
        return [{"name": "根目录", "path": "/"}]
    
    parts = relative.replace('\\', '/').split('/')
    breadcrumbs = [{"name": "根目录", "path": "/"}]
    cum_path = ""
    
    for part in parts:
        cum_path += "/" + part
        breadcrumbs.append({
            "name": html.escape(part),  # XSS防护：HTML转义
            "path": cum_path
        })
    
    return breadcrumbs


def get_parent_path(current_path):
    """获取上级目录路径"""
    share_path = config.share_path
    parent = os.path.dirname(current_path)
    
    if not is_safe_path(share_path, parent):
        return share_path
    
    return parent


def save_upload_file(file, dest_path):
    """保存上传的文件"""
    share_path = config.share_path
    
    if not is_safe_path(share_path, dest_path):
        return False, "路径不安全"
    
    try:
        file.save(dest_path)
        return True, "上传成功"
    except Exception as e:
        return False, str(e)


def get_free_filename(dir_path, filename):
    """获取可用的文件名（处理重名）"""
    if not os.path.exists(os.path.join(dir_path, filename)):
        return filename
    
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{name} ({counter}){ext}"
        if not os.path.exists(os.path.join(dir_path, new_filename)):
            return new_filename
        counter += 1


def search_files(keyword, search_path=None, filters=None):
    """
    搜索文件（支持模糊搜索）

    Args:
        keyword: 搜索关键词
        search_path: 搜索路径，默认为共享目录
        filters: 筛选条件 {'type': 'image|video|doc|zip|code|all', 'size_min': bytes, 'size_max': bytes, 'date_from': 'YYYY-MM-DD', 'date_to': 'YYYY-MM-DD'}

    Returns:
        list: 匹配的文件列表，按相关性排序
    """
    import fnmatch
    from difflib import SequenceMatcher

    share_path = config.share_path
    if search_path is None:
        search_path = share_path

    if not is_safe_path(share_path, search_path):
        return []

    if not os.path.exists(search_path):
        return []

    results = []
    filters = filters or {}

    # 文件类型映射
    type_extensions = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'],
        'video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
        'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg'],
        'doc': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md'],
        'zip': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'code': ['.py', '.js', '.ts', '.html', '.css', '.json', '.java', '.c', '.cpp', '.go', '.rs', '.php', '.rb', '.swift', '.kt']
    }

    def fuzzy_match_score(filename, keyword):
        """计算模糊匹配分数 - 优化版本"""
        filename_lower = filename.lower()
        keyword_lower = keyword.lower()
        
        # 1. 完全匹配（最高分）
        if filename_lower == keyword_lower:
            return 100
        
        # 2. 开头匹配（高分）
        if filename_lower.startswith(keyword_lower):
            return 95
        
        # 3. 结尾匹配（中高分）
        if filename_lower.endswith(keyword_lower):
            return 85
        
        # 4. 完全包含（中等分）
        if keyword_lower in filename_lower:
            # 根据位置给分：越靠前分数越高
            pos = filename_lower.find(keyword_lower)
            return 75 - (pos // 10) * 5  # 位置越前分数越高，最低70分
        
        # 5. 通配符匹配
        if '*' in keyword:
            if fnmatch.fnmatch(filename_lower, keyword_lower):
                return 80
        
        # 6. 子串连续匹配检查 - 确保关键词的字符在文件名中是连续出现的
        def has_contiguous_match(s, sub):
            """检查sub中的字符是否在s中连续出现"""
            sub_idx = 0
            for i, char in enumerate(s):
                if sub_idx < len(sub) and char == sub[sub_idx]:
                    sub_idx += 1
                    if sub_idx == len(sub):
                        return True
            return sub_idx == len(sub)
        
        # 如果关键词字符在文件名中不是连续出现的，惩罚分数
        if not has_contiguous_match(filename_lower, keyword_lower):
            # 字符不连续，说明相关性很低
            return 0
        
        # 7. 真正的模糊匹配（编辑距离）- 仅用于短关键词
        if len(keyword) <= 3:
            # 短关键词需要更高的相似度才显示
            ratio = SequenceMatcher(None, keyword_lower, filename_lower).ratio()
            return int(ratio * 50)  # 最高50分
        
        # 8. 长关键词模糊匹配（更严格的匹配）
        ratio = SequenceMatcher(None, keyword_lower, filename_lower).ratio()
        # 只有当相似度超过50%才考虑
        if ratio >= 0.5:
            return int(ratio * 40)
        
        return 0

    def matches_type(ext):
        """检查文件类型是否匹配"""
        if 'type' not in filters or filters['type'] == 'all':
            return True
        return ext.lower() in type_extensions.get(filters['type'], [])

    def matches_size(size):
        """检查文件大小是否匹配"""
        size_min = filters.get('size_min', 0)
        size_max = filters.get('size_max', float('inf'))
        return size_min <= size <= size_max

    def matches_date(mtime):
        """检查修改时间是否匹配"""
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        if not date_from and not date_to:
            return True
        mtime_str = mtime.strftime("%Y-%m-%d") if isinstance(mtime, datetime) else mtime
        if date_from and mtime_str < date_from:
            return False
        if date_to and mtime_str > date_to:
            return False
        return True

    # 递归搜索
    keyword_lower = keyword.lower()
    all_matches = []

    for root, dirs, files in os.walk(search_path):
        # 跳过隐藏目录
        dirs[:] = [d for d in dirs if not is_hidden_folder(d) and not is_ignored(d)]

        for file in files:
            if is_ignored(file):
                continue

            # 计算模糊匹配分数
            score = fuzzy_match_score(file, keyword)
            if score < 30:  # 低于30分不显示
                continue

            full_path = os.path.join(root, file)
            try:
                stat = os.stat(full_path)
                ext = os.path.splitext(file)[1].lower()

                if matches_type(ext) and matches_size(stat.st_size) and matches_date(datetime.fromtimestamp(stat.st_mtime)):
                    all_matches.append({
                        "name": html.escape(file),  # XSS防护：HTML转义文件名
                        "path": full_path,
                        "relative_path": html.escape(os.path.relpath(full_path, share_path).replace('\\', '/')),  # XSS防护
                        "is_dir": False,
                        "size": stat.st_size,
                        "size_display": format_file_size(stat.st_size),
                        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "icon": get_file_icon(file, False),
                        "preview_type": get_preview_type(file),
                        "score": score
                    })
            except:
                pass

        # 搜索目录（也支持模糊匹配）
        for dir_name in dirs:
            if is_hidden_folder(dir_name) or is_ignored(dir_name):
                continue

            score = fuzzy_match_score(dir_name, keyword)
            if score < 30:
                continue

            full_path = os.path.join(root, dir_name)
            try:
                stat = os.stat(full_path)
                all_matches.append({
                    "name": html.escape(dir_name),  # XSS防护：HTML转义目录名
                    "path": full_path,
                    "relative_path": html.escape(os.path.relpath(full_path, share_path).replace('\\', '/')),  # XSS防护
                    "is_dir": True,
                    "size": 0,
                    "size_display": "-",
                    "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "icon": "📁",
                    "preview_type": None,
                    "score": score
                })
            except:
                    pass

    # 按相关性排序（分数高的在前，文件夹优先）
    all_matches.sort(key=lambda x: (x["score"], not x["is_dir"]), reverse=True)

    # 移除score字段后返回
    for item in all_matches:
        del item["score"]

    return all_matches
