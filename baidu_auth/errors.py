"""baidu_auth 的自定义异常类型。

全部继承 `BaiduAuthError`，CLI 只需要捕获这一个基类就能给出统一的可读报错，
调用方也可以按需细分处理。()
"""

from __future__ import annotations


class BaiduAuthError(Exception):
    """本工具所有可预期错误的基类。"""


class ConfigurationError(BaiduAuthError):
    """凭证等配置缺失或不合法（例如 client_id 为空）。"""


class OAuthError(BaiduAuthError):
    """百度 OAuth 接口报错，或响应无法按预期解析。"""


class BrowserError(BaiduAuthError):
    """浏览器启动/页面交互失败，或等待用户授权超时。"""
