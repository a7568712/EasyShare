# -*- coding: utf-8 -*-
"""
EasyShare 路由模块
"""

from flask import Blueprint

# 创建蓝图
file_bp = Blueprint('file', __name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# 导入路由
from . import file_ops, admin
