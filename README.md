# EasyShare - 局域网文件共享软件

一个简洁、安全、易用的局域网文件共享工具，支持文件拖拽上传、下载，文件预览、回收站等功能。

## 预览图片
![文件管理界面](https://github.com/a7568712/EasyShare/blob/main/EasyShare%20-%20%E6%96%87%E4%BB%B6%E7%AE%A1%E7%90%86.png)

![管理后台界面](https://github.com/a7568712/EasyShare/blob/main/EasyShare%20-%20%E7%AE%A1%E7%90%86%E5%90%8E%E5%8F%B0.png)

### 文件管理
- 📁 文件夹创建、重命名、删除
- 📤 文件上传（支持拖拽上传）
- 📥 文件下载（支持断点续传）
- 📦 批量下载（文件夹自动打包为ZIP）
- 🔍 文件搜索（支持筛选条件）
- 🖼️ 在线预览（图片、视频、PDF、文本）
- 🗑️ 回收站（支持恢复和永久删除）

### 上传功能
- 单文件上传
- 多文件批量上传
- **文件夹上传**（保持目录结构）
- **拖拽上传**（支持文件和文件夹）
- 大文件支持（默认最大100GB）

### 用户管理
- 多用户支持
- 角色权限控制（管理员/读写/只读）
- 登录失败锁定保护
- 操作日志记录

### 访问控制
- 匿名访问开关
- 匿名上传开关
- 匿名批量下载开关
- 文件夹隐藏功能

### 界面特性
- 明暗主题切换
- 响应式设计
- 拖拽交互
- 进度显示

## 系统要求

- Windows 7/10/11
- 无需安装 Python（已打包为exe）
- 局域网内设备可访问

## 快速开始

### 方式一：使用打包版（推荐）

1. 下载 `EasyShare.exe`
2. 双击运行
3. 手动访问显示的地址
4. 默认管理员账号：`admin` / `admin`

### 方式二：源码运行

```bash
# 安装依赖
pip install flask zipstream

# 运行
python main.py

# 指定端口和目录
python main.py -p 8080 -d D:\共享文件夹
```

## 使用说明

### 文件上传

#### 方式1：点击上传
1. 点击"上传文件"按钮
2. 选择要上传的文件
3. 等待上传完成

#### 方式2：拖拽上传
1. 将文件或文件夹拖拽到页面任意位置
2. 松开鼠标自动开始上传

#### 方式3：文件夹上传
1. 点击"上传文件夹"按钮
2. 选择要上传的文件夹
3. 文件夹结构会被完整保留

**注意**：
- Chrome/Edge 浏览器支持直接拖拽文件夹上传
- 其他浏览器请使用"选择文件夹"按钮

### 文件下载

- **单文件下载**：点击文件右侧的下载按钮
- **批量下载**：勾选多个文件，点击"批量下载"
- **文件夹下载**：点击文件夹右侧的下载按钮（自动打包为ZIP）

### 回收站

- 删除的文件会进入回收站
- 支持从回收站恢复文件
- 支持永久删除
- 自动清理（默认保留30天）

### 用户管理（管理员）

1. 登录管理员账号
2. 进入"管理后台"
3. 可以：
   - 创建/编辑/删除用户
   - 查看操作日志
   - 管理回收站
   - 修改系统配置

## 配置说明

配置文件位于程序目录下的 `config.json`：

```json
{
    "share_path": "C:\\Users\\xxx\\Desktop\\EasyShare",
    "port": 8081,
    "host": "0.0.0.0",
    "theme": "light",
    "site_title": "EasyShare",
    "page_title": "EasyShare",
    "anonymous_access": true,
    "anonymous_readonly": true,
    "anonymous_upload": false,
    "anonymous_batch_download": false,
    "max_upload_size": 107374182400,
    "password_min_length": 6,
    "password_require_uppercase": false,
    "password_require_number": false,
    "password_require_special": false,
    "login_max_attempts": 5,
    "login_lock_minutes": 15,
    "trash_retention_days": 30
}
```

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `share_path` | 共享文件夹路径 | 程序所在目录 |
| `port` | 服务端口 | 8081 |
| `host` | 监听地址 | 0.0.0.0 |
| `theme` | 主题（light/dark） | light |
| `site_title` | 网站标题 | EasyShare |
| `page_title` | 浏览器标签标题 | EasyShare |
| `anonymous_access` | 允许匿名访问 | true |
| `anonymous_readonly` | 匿名用户只读 | true |
| `anonymous_upload` | 允许匿名上传 | false |
| `anonymous_batch_download` | 允许匿名批量下载 | false |
| `max_upload_size` | 最大上传文件大小（字节） | 100GB |
| `password_min_length` | 密码最小长度 | 6 |
| `login_max_attempts` | 登录最大失败次数 | 5 |
| `login_lock_minutes` | 登录锁定时间（分钟） | 15 |
| `trash_retention_days` | 回收站保留天数 | 30 |

## 安全特性

- 路径安全检查（防止目录遍历攻击）
- 密码加密存储（PBKDF2）
- 登录失败锁定保护
- Session 安全机制
- 操作日志记录

## 浏览器兼容性

| 浏览器 | 支持情况 |
|--------|----------|
| Chrome 86+ | ✅ 完整支持（含文件夹拖拽） |
| Edge 86+ | ✅ 完整支持（含文件夹拖拽） |
| Firefox | ✅ 支持（文件夹请使用按钮选择） |
| Safari | ✅ 支持（文件夹请使用按钮选择） |
| IE11 | ⚠️ 基本功能支持 |

## 技术栈

- 后端：Python + Flask
- 前端：原生 JavaScript + HTML5
- 数据库：SQLite
- 打包：PyInstaller

## 目录结构

```
EasyShare/
├── main.py              # 主程序入口
├── config.py            # 配置文件
├── database.py          # 数据库操作
├── routes/              # 路由模块
│   ├── __init__.py
│   ├── file_ops.py      # 文件操作
│   └── admin.py         # 管理后台
├── utils/               # 工具模块
│   ├── file_utils.py    # 文件工具
│   └── security.py      # 安全工具
├── templates/           # HTML模板
│   ├── index.html       # 主页
│   ├── login.html       # 登录页
│   └── admin.html       # 管理后台
├── static/              # 静态资源
│   └── EasyShare.ico    # 图标
├── data/                # 数据目录
│   └── easyshare.db     # 数据库
├── backups/             # 回收站备份
└── config.json          # 配置文件
```

## 命令行参数

```bash
python main.py [选项]

选项:
  -p, --port          监听端口（默认：8081）
  -a, --host          监听地址（默认：0.0.0.0）
  -d, --dir           共享目录路径
  --autostart         配置开机自启动
  --remove-autostart  移除开机自启动
  --version           显示版本信息
```

## 常见问题

### Q: 如何修改共享目录？
A: 编辑 `config.json` 文件，修改 `share_path` 项，或启动时指定 `-d` 参数。

### Q: 如何添加新用户？
A: 使用管理员账号登录，进入"管理后台"-"用户管理"，点击"添加用户"。

### Q: 文件夹拖拽上传没反应？
A: 请使用 Chrome 或 Edge 浏览器，其他浏览器请使用"选择文件夹"按钮。

### Q: 如何备份数据？
A: 备份以下文件即可：
- `data/easyshare.db` - 数据库
- `config.json` - 配置文件
- `backups/` - 回收站备份

## 更新日志

### v1.0
- 初始版本发布
- 文件上传下载功能
- 用户管理系统
- 回收站功能
- 拖拽上传支持
- 文件夹上传支持

## 许可证

MIT License

## 致谢

感谢使用 EasyShare！
