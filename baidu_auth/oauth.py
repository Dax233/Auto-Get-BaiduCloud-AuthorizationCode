"""百度网盘 OAuth 2.0 的纯逻辑部分：授权页 URL 构造、token 交换与解析。

这里刻意不碰浏览器，全部逻辑都可以用假对象单测。
字符串一律走 `urllib.parse.urlencode`，不再手工拼 `?a=1&b=2`；
client_secret 放在 POST 表单里，避免出现在 URL / 代理日志中。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlencode

import requests

from .errors import ConfigurationError, OAuthError

AUTHORIZE_ENDPOINT = "https://openapi.baidu.com/oauth/2.0/authorize"
TOKEN_ENDPOINT = "https://openapi.baidu.com/oauth/2.0/token"

DEFAULT_REDIRECT_URI = "oob"
DEFAULT_SCOPE = "basic,netdisk"


def _require_non_empty(value: object, *, field: str, hint: str) -> str:
    """校验必填字符串，空值直接抛出可读的 ConfigurationError。"""
    text = "" if value is None else str(value).strip()
    if not text:
        raise ConfigurationError(f"缺少 {field}，{hint}")
    return text


def build_authorize_url(
    client_id: object,
    *,
    redirect_uri: object = DEFAULT_REDIRECT_URI,
    scope: object = DEFAULT_SCOPE,
    qrcode: bool = True,
) -> str:
    """构造百度 OAuth 授权页 URL，自动 URL 编码所有查询参数。"""
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": _require_non_empty(
            client_id,
            field="client_id（AppKey）",
            hint="请通过 --client-id 或环境变量 BAIDU_CLIENT_ID 提供",
        ),
        "redirect_uri": _require_non_empty(
            redirect_uri,
            field="redirect_uri",
            hint="默认 oob，可用 --redirect-uri 指定",
        ),
        "scope": _require_non_empty(
            scope,
            field="scope",
            hint="默认 basic,netdisk，可用 --scope 指定",
        ),
    }
    if qrcode:
        params["qrcode"] = "1"
    return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"


def _mask(secret: str | None) -> str:
    """日志/调试里只露出尾巴，避免整串凭证泄露。"""
    if not secret:
        return "<空>"
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"


@dataclass(frozen=True)
class AccessToken:
    """token 接口的成功响应，只保留调用方真正关心的字段。"""

    access_token: str
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None

    def __repr__(self) -> str:  # 防止 print(token) 之类误操作把 token 打全
        return (
            "AccessToken(access_token={}, expires_in={!r}, scope={!r})".format(
                _mask(self.access_token), self.expires_in, self.scope
            )
        )


def _parse_expires_in(raw: object) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def parse_token_response(payload: object, *, status_code: int = 200) -> AccessToken:
    """把 token 接口的 JSON 解析成 AccessToken，错误响应转成 OAuthError。

    百度在失败时返回 `{"error": "...", "error_description": "..."}`，HTTP 状态
    却可能仍是 200，所以必须同时检查 `error` 字段和 `access_token` 是否存在。
    """
    if not isinstance(payload, Mapping):
        raise OAuthError(f"token 接口响应格式异常（HTTP {status_code}）：期望 JSON 对象")

    error = payload.get("error")
    if error:
        description = payload.get("error_description") or payload.get("error_msg") or error
        raise OAuthError(f"获取 access_token 失败（HTTP {status_code}）：{description}")

    raw_token = payload.get("access_token")
    access_token = "" if raw_token is None else str(raw_token).strip()
    if not access_token:
        raise OAuthError(f"token 接口响应缺少 access_token（HTTP {status_code}）")

    refresh_token = payload.get("refresh_token")
    scope = payload.get("scope")
    return AccessToken(
        access_token=access_token,
        expires_in=_parse_expires_in(payload.get("expires_in")),
        refresh_token="" if refresh_token is None else str(refresh_token),
        scope=None if scope is None else str(scope),
    )


def request_access_token(
    code: object,
    client_id: object,
    client_secret: object,
    *,
    redirect_uri: object = DEFAULT_REDIRECT_URI,
    timeout: float = 15.0,
    session: Any | None = None,
    endpoint: str = TOKEN_ENDPOINT,
) -> AccessToken:
    """用授权页拿到的 code 换取 access_token。

    `session` 可注入（测试用假对象，或复用连接池）；默认新建 requests.Session。
    """
    form = {
        "grant_type": "authorization_code",
        "code": _require_non_empty(code, field="authorization code", hint="请先在授权页完成授权"),
        "client_id": _require_non_empty(
            client_id,
            field="client_id（AppKey）",
            hint="请通过 --client-id 或环境变量 BAIDU_CLIENT_ID 提供",
        ),
        "client_secret": _require_non_empty(
            client_secret,
            field="client_secret（SecretKey）",
            hint="请通过 --client-secret 或环境变量 BAIDU_CLIENT_SECRET 提供",
        ),
        "redirect_uri": _require_non_empty(
            redirect_uri,
            field="redirect_uri",
            hint="默认 oob，必须与授权页一致",
        ),
    }
    http = session if session is not None else requests.Session()
    try:
        response = http.post(endpoint, data=form, timeout=timeout)
    except requests.RequestException as exc:  # 网络层错误统一包装，不吞栈
        raise OAuthError(f"请求百度 token 接口失败：{exc}") from exc

    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise OAuthError(
            f"token 接口返回了无法解析的内容（HTTP {response.status_code}）"
        ) from exc

    return parse_token_response(payload, status_code=response.status_code)
