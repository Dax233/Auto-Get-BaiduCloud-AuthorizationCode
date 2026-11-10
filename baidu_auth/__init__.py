"""百度网盘 OAuth 授权码获取工具（原 Auto-Get-BaiduCloud-AuthorizationCode）。

拆成三层：
- :mod:`baidu_auth.oauth`   授权页 URL 构造 + token 交换（纯逻辑，可单测）
- :mod:`baidu_auth.browser` Selenium 授权页交互（context manager + 显式等待）
- :mod:`baidu_auth.cli`     argparse 入口，凭证支持参数或环境变量

浏览器部分延迟导入 selenium，因此 import 本包不会拉起浏览器依赖。()
"""

from __future__ import annotations

from .errors import BaiduAuthError, BrowserError, ConfigurationError, OAuthError
from .oauth import (
    AccessToken,
    build_authorize_url,
    parse_token_response,
    request_access_token,
)

__version__ = "0.2.0"

__all__ = [
    "AccessToken",
    "BaiduAuthError",
    "BrowserError",
    "ConfigurationError",
    "OAuthError",
    "build_authorize_url",
    "parse_token_response",
    "request_access_token",
    "__version__",
]
