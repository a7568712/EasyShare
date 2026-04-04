# -*- coding: utf-8 -*-
"""
EasyShare 配置文件
管理应用程序的所有配置项
"""

import os
import sys
import json
import secrets
from pathlib import Path

# 应用基础配置
APP_NAME = "EasyShare"
APP_VERSION = "1.0"

# 默认配置
# 获取应用根目录（兼容打包后的exe环境）
def _get_default_share_path():
    """获取默认共享路径"""
    if getattr(sys, 'frozen', False):
        # 打包后：使用exe所在目录
        return str(Path(sys.executable).parent)
    else:
        # 开发环境：使用脚本所在目录
        return str(Path(__file__).parent)

DEFAULT_CONFIG = {
    "share_path": _get_default_share_path(),  # 默认共享运行文件所在目录
    "port": 8081,
    "host": "0.0.0.0",
    "theme": "light",  # light/dark
    "site_title": "EasyShare",  # 网站标题
    "page_title": "EasyShare",  # 浏览器标签标题
    "anonymous_access": True,  # 是否允许匿名访问（默认允许）
    "anonymous_readonly": True,  # 匿名用户是否只读
    "anonymous_upload": False,  # 是否允许匿名上传
    "hidden_folders": [],  # 隐藏的文件夹列表
    "max_upload_size": 100 * 1024 * 1024 * 1024,  # 100GB
    "log_level": "info",  # info/warning/error
    "auto_start": False,  # 开机自启动
    # 安全策略配置
    "password_min_length": 6,  # 密码最小长度
    "password_require_uppercase": False,  # 是否需要大写字母
    "password_require_number": False,  # 是否需要数字
    "password_require_special": False,  # 是否需要特殊字符
    "login_max_attempts": 5,  # 登录最大失败次数
    "login_lock_minutes": 15,  # 登录锁定时间（分钟）
    "trash_retention_days": 30,  # 回收站保留天数
}

# 允许的文件预览类型
PREVIEWABLE_TYPES = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"],
    "text": [".txt", ".md", ".json", ".xml", ".html", ".css", ".js", ".py", ".c", ".cpp", ".h", ".java", ".go", ".rs", ".sql", ".sh", ".bat", ".yml", ".yaml", ".toml", ".ini", ".conf"],
    "video": [".mp4", ".webm", ".ogg", ".mov"],
    "pdf": [".pdf"],
}

# 忽略的文件/文件夹
IGNORED_PATTERNS = [
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".git",
    ".gitignore",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".env",
]


class Config:
    """配置管理类"""
    
    def __init__(self, config_file=None):
        self.config_file = config_file or self._get_default_config_file()
        self._config = DEFAULT_CONFIG.copy()
        self.load()
        # 如果配置文件不存在，自动创建
        if not os.path.exists(self.config_file):
            self.save()
    
    def _get_default_config_file(self):
        """获取默认配置文件路径"""
        # 获取exe所在目录（打包后指向exe目录，开发环境指向脚本目录）
        if getattr(sys, 'frozen', False):
            # 打包后运行环境
            base_dir = Path(sys.executable).parent
        else:
            # 开发环境
            base_dir = Path(__file__).parent
        return base_dir / "config.json"
    
    def load(self):
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                self._config.update(user_config)
            except Exception as e:
                print(f"配置加载失败: {e}")
    
    def save(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"配置保存失败: {e}")
            return False
    
    def get(self, key, default=None):
        """获取配置项"""
        return self._config.get(key, default)
    
    def set(self, key, value):
        """设置配置项"""
        self._config[key] = value
    
    def get_all(self):
        """获取所有配置"""
        return self._config.copy()
    
    def update(self, config_dict):
        """批量更新配置"""
        self._config.update(config_dict)
    
    @property
    def share_path(self):
        """获取共享目录"""
        return self._config.get("share_path", DEFAULT_CONFIG["share_path"])
    
    @property
    def port(self):
        """获取端口"""
        return self._config.get("port", DEFAULT_CONFIG["port"])
    
    @property
    def host(self):
        """获取监听地址"""
        return self._config.get("host", DEFAULT_CONFIG["host"])
    
    @property
    def theme(self):
        """获取主题"""
        return self._config.get("theme", "light")
    
    @property
    def anonymous_access(self):
        """是否允许匿名访问"""
        return self._config.get("anonymous_access", True)
    
    @property
    def anonymous_readonly(self):
        """匿名用户是否只读"""
        return self._config.get("anonymous_readonly", True)
    
    @property
    def hidden_folders(self):
        """获取隐藏文件夹列表"""
        return self._config.get("hidden_folders", [])
    
    @property
    def max_upload_size(self):
        """获取最大上传大小"""
        return self._config.get("max_upload_size", 100 * 1024 * 1024 * 1024)
    
    @property
    def anonymous_upload(self):
        """是否允许匿名上传"""
        return self._config.get("anonymous_upload", False)
    
    @property
    def site_title(self):
        """获取网站标题"""
        val = self._config.get("site_title")
        return val if val else "EasyShare"
    
    @property
    def page_title(self):
        """获取浏览器标签标题"""
        val = self._config.get("page_title")
        return val if val else "EasyShare"
    
    @property
    def anonymous_batch_download(self):
        """是否允许匿名批量下载"""
        return self._config.get("anonymous_batch_download", False)
    
    @property
    def password_min_length(self):
        """密码最小长度"""
        return self._config.get("password_min_length", 6)
    
    @property
    def password_require_uppercase(self):
        """是否需要大写字母"""
        return self._config.get("password_require_uppercase", False)
    
    @property
    def password_require_number(self):
        """是否需要数字"""
        return self._config.get("password_require_number", False)
    
    @property
    def password_require_special(self):
        """是否需要特殊字符"""
        return self._config.get("password_require_special", False)
    
    @property
    def login_max_attempts(self):
        """登录最大失败次数"""
        return self._config.get("login_max_attempts", 5)
    
    @property
    def login_lock_minutes(self):
        """登录锁定时间（分钟）"""
        return self._config.get("login_lock_minutes", 15)
    
    @property
    def trash_retention_days(self):
        """回收站保留天数"""
        return self._config.get("trash_retention_days", 30)


# 全局配置实例
config = Config()


def init_config(share_path=None, port=None, host=None, theme=None):
    """初始化配置（用于命令行参数覆盖）"""
    if share_path:
        config.set("share_path", os.path.abspath(share_path))
    if port:
        config.set("port", port)
    if host:
        config.set("host", host)
    if theme:
        config.set("theme", theme)
