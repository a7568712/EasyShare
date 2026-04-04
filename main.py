# -*- coding: utf-8 -*-
"""
EasyShare - 私有文件共享网盘
主程序入口
"""

import os
import sys
import socket
import argparse
import winreg
import secrets
import tempfile
from pathlib import Path
from ctypes import windll

# 检查是否为GUI模式（无控制台窗口）
def is_gui_mode():
    """检测是否为GUI模式运行"""
    return windll.kernel32.GetConsoleWindow() == 0

# 单实例检查 - 使用Windows命名互斥体
import ctypes

_single_instance_mutex = None

def check_single_instance():
    """检查是否已有实例在运行"""
    global _single_instance_mutex
    try:
        # 创建命名互斥体（系统范围）
        mutex_name = "EasyShare_SingleInstance_Mutex"
        _single_instance_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        
        # ERROR_ALREADY_EXISTS = 183 表示互斥体已存在
        if last_error == 183:
            return False, "EasyShare 已在运行中！"
        return True, None
    except Exception as e:
        return True, None

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, session, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config, APP_NAME, APP_VERSION, init_config
from database import init_database, cleanup_expired_trash


def get_secret_key():
    """获取安全的session密钥"""
    # 优先从环境变量获取
    secret = os.environ.get('EASYSHARE_SECRET_KEY')
    if secret:
        return secret.encode() if isinstance(secret, str) else secret
    
    # 从配置文件获取
    secret = config.get('secret_key')
    if secret:
        return secret.encode() if isinstance(secret, str) else secret
    
    # 生成新的随机密钥
    return secrets.token_hex(32)


# 获取应用根目录（打包后指向exe所在目录）
def get_app_root():
    """获取应用根目录"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

# 获取资源目录（打包后指向临时目录）
def get_resource_path():
    """获取资源文件目录（打包后指向_MEIPASS临时目录）"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

APP_ROOT = get_app_root()
RESOURCE_ROOT = get_resource_path()

# 创建Flask应用
app = Flask(__name__,
            template_folder=str(RESOURCE_ROOT / 'templates'),
            static_folder=str(RESOURCE_ROOT / 'static'))
app.secret_key = get_secret_key()
app.wsgi_app = ProxyFix(app.wsgi_app)

# 配置请求最大大小 (使用配置文件中的 max_upload_size)
app.config['MAX_CONTENT_LENGTH'] = config.max_upload_size

# 注册蓝图
from routes import file_bp, admin_bp
app.register_blueprint(file_bp)
app.register_blueprint(admin_bp)


@app.route('/favicon.ico')
def favicon():
    """网站图标"""
    return send_from_directory(app.static_folder, 'EasyShare.ico', mimetype='image/x-icon')


def get_local_ips():
    """获取本机所有局域网IP地址"""
    ips = []
    try:
        # 创建socket获取本机IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        ips.append(local_ip)

        # 获取主机名
        hostname = socket.gethostname()
        # 获取所有IP（包含IPv6）
        addr_info = socket.getaddrinfo(hostname, None)
        for info in addr_info:
            ip = info[4][0]
            if '.' in ip and ip not in ips:
                ips.append(ip)
    except:
        pass

    # 添加本地回环地址
    if '127.0.0.1' not in ips:
        ips.append('127.0.0.1')

    return list(set(ips))


def print_server_info(port):
    """打印服务器启动信息"""
    ips = get_local_ips()

    print("\n" + "=" * 60)
    print(f"  {APP_NAME} v{APP_VERSION} - 私有文件共享网盘")
    print("=" * 60)
    print(f"\n  [目录] 共享目录: {config.share_path}")
    print(f"\n  [访问] 访问地址:")
    for ip in ips:
        print(f"           http://{ip}:{port}")
    print(f"           http://localhost:{port}")
    print("\n  按 Ctrl+C 停止服务器")
    print("=" * 60 + "\n")


def show_startup_notification(port):
    """显示启动通知窗口（GUI模式）"""
    if not is_gui_mode():
        return
    
    try:
        import tkinter as tk
        from tkinter import messagebox
        
        ips = get_local_ips()
        # 分离本地和局域网IP
        local_ip = '127.0.0.1'
        network_ip = None
        for ip in ips:
            if ip != '127.0.0.1' and not ip.startswith('::'):
                network_ip = ip
                break
        
        urls = f"http://{local_ip}:{port}"
        if network_ip:
            urls += f"\nhttp://{network_ip}:{port}"
        
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        root.attributes('-topmost', True)  # 置顶
        
        messagebox.showinfo(
            f"{APP_NAME} 已启动",
            f"访问地址：\n{urls}\n\n点击确定关闭此提示",
            master=root
        )
        root.destroy()
    except Exception as e:
        print(f"[提示] 启动通知失败: {e}")


def setup_auto_start(enable=True):
    """
    配置开机自启动（Windows）

    Args:
        enable: True启用，False禁用
    """
    try:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)

        if enable:
            exe_path = sys.executable
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
            print(f"[自启动] 已添加到开机启动项")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                print(f"[自启动] 已从开机启动项移除")
            except FileNotFoundError:
                pass

        winreg.CloseKey(key)
        return True
    except PermissionError:
        print("[自启动] 需要管理员权限才能配置")
        return False
    except Exception as e:
        print(f"[自启动] 配置失败: {e}")
        return False


def run_server(host=None, port=None, share_path=None):
    """
    运行服务器

    Args:
        host: 监听地址
        port: 监听端口
        share_path: 共享目录
    """
    # 单实例检查
    can_run, msg = check_single_instance()
    if not can_run:
        print(f"[错误] {msg}")
        if is_gui_mode():
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                messagebox.showerror(f"{APP_NAME} 错误", msg, master=root)
                root.destroy()
            except:
                pass
        return
    
    # 应用配置覆盖
    if host:
        config.set("host", host)
    if port:
        config.set("port", port)
    if share_path:
        config.set("share_path", os.path.abspath(share_path))

    # 确保共享目录存在
    share_path = config.share_path
    if not os.path.exists(share_path):
        print(f"[警告] 共享目录不存在，将自动创建: {share_path}")
        os.makedirs(share_path, exist_ok=True)

    # 初始化数据库
    init_database()
    
    # 清理过期的回收站记录
    retention_days = config.trash_retention_days
    cleaned_count = cleanup_expired_trash(retention_days)
    if cleaned_count > 0:
        print(f"[回收站] 已自动清理 {cleaned_count} 条过期记录（保留 {retention_days} 天）")

    # 获取监听参数
    listen_host = config.host
    listen_port = config.port

    # 打印服务器信息（控制台模式）
    if not is_gui_mode():
        print_server_info(listen_port)
    else:
        # GUI模式显示通知
        show_startup_notification(listen_port)

    # Waitress 对大文件上传支持有问题，强制使用 Flask 内置服务器
    if not is_gui_mode():
        print(f"[服务器] 使用 Flask 内置服务器")
    app.run(host=listen_host, port=listen_port, debug=False, threaded=True)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - 私有文件共享网盘 v{APP_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py                           # 使用默认配置启动
  python main.py -p 9000                   # 指定端口
  python main.py -d D:\\files                # 指定共享目录
  python main.py -h 0.0.0.0 -p 8080         # 指定地址和端口
  python main.py --autostart               # 配置开机自启动

更多信息请访问: https://github.com/easyshare
        """
    )

    parser.add_argument("-p", "--port", type=int, help="监听端口 (默认: 8080)")
    parser.add_argument("-a", "--host", dest="host", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("-d", "--dir", "--share-path", dest="share_path", help="共享目录 (默认: 用户主目录)")
    parser.add_argument("--autostart", action="store_true", help="配置开机自启动")
    parser.add_argument("--remove-autostart", dest="remove_autostart", action="store_true", help="移除开机自启动")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")

    args = parser.parse_args()

    # 处理开机自启动
    if args.autostart:
        setup_auto_start(True)
        return

    if args.remove_autostart:
        setup_auto_start(False)
        return

    # 运行服务器
    run_server(
        host=args.host,
        port=args.port,
        share_path=args.share_path
    )


if __name__ == "__main__":
    main()
