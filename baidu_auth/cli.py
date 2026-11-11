"""命令行入口：`python -m baidu_auth` 或安装后的 `baidu-auth`。

凭证优先级：命令行参数 > 环境变量（BAIDU_CLIENT_ID / BAIDU_CLIENT_SECRET）。
缺凭证时给清晰报错，而不是拼出一个必然失败的授权 URL。
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Mapping, Sequence

from .browser import DEFAULT_WAIT_TIMEOUT, wait_for_authorization_code
from .errors import BaiduAuthError, ConfigurationError
from .oauth import (
    DEFAULT_REDIRECT_URI,
    DEFAULT_SCOPE,
    build_authorize_url,
    request_access_token,
)
from . import __version__

ENV_CLIENT_ID = "BAIDU_CLIENT_ID"
ENV_CLIENT_SECRET = "BAIDU_CLIENT_SECRET"

_PROG = "baidu-auth"


def build_parser() -> argparse.ArgumentParser:
    """构造参数解析器（单独暴露出来便于测试）。"""
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description="获取百度网盘 OAuth access_token：打开授权页扫码授权后用 code 换取 token。",
        epilog=(
            "凭证也可以通过环境变量传入：BAIDU_CLIENT_ID / BAIDU_CLIENT_SECRET。"
        ),
    )
    parser.add_argument(
        "--client-id",
        metavar="APP_KEY",
        help=f"应用的 AppKey；未指定时读取环境变量 {ENV_CLIENT_ID}",
    )
    parser.add_argument(
        "--client-secret",
        metavar="SECRET_KEY",
        help=f"应用的 SecretKey；未指定时读取环境变量 {ENV_CLIENT_SECRET}（不会打印到输出）",
    )
    parser.add_argument(
        "--redirect-uri",
        default=DEFAULT_REDIRECT_URI,
        help=f"OAuth 回调地址，默认 {DEFAULT_REDIRECT_URI}",
    )
    parser.add_argument(
        "--scope",
        default=DEFAULT_SCOPE,
        help=f"申请的权限范围，默认 {DEFAULT_SCOPE}",
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=DEFAULT_WAIT_TIMEOUT,
        metavar="SECONDS",
        help=f"等待用户完成授权的秒数，默认 {DEFAULT_WAIT_TIMEOUT:.0f}",
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=15.0,
        metavar="SECONDS",
        help="请求 token 接口的超时秒数，默认 15",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _pick(value: str | None, env: Mapping[str, str], name: str) -> str:
    """参数优先，参数为空则回退到环境变量（含首尾空白的参数视为未提供）。"""
    if value is not None and value.strip():
        return value.strip()
    return (env.get(name) or "").strip()


def resolve_credentials(
    args: argparse.Namespace, environ: Mapping[str, str] | None = None
) -> tuple[str, str]:
    """从参数/环境变量解析 client_id 与 client_secret，缺失时抛 ConfigurationError。"""
    env = os.environ if environ is None else environ
    client_id = _pick(getattr(args, "client_id", None), env, ENV_CLIENT_ID)
    client_secret = _pick(getattr(args, "client_secret", None), env, ENV_CLIENT_SECRET)
    if not client_id:
        raise ConfigurationError(
            "缺少 client_id（AppKey）：请用 --client-id 传入，"
            f"或设置环境变量 {ENV_CLIENT_ID}"
        )
    if not client_secret:
        raise ConfigurationError(
            "缺少 client_secret（SecretKey）：请用 --client-secret 传入，"
            f"或设置环境变量 {ENV_CLIENT_SECRET}"
        )
    return client_id, client_secret


def run(args: argparse.Namespace, *, environ: Mapping[str, str] | None = None) -> str:
    """执行完整授权流程，返回 access_token（仅返回，不打印，便于测试）。"""
    client_id, client_secret = resolve_credentials(args, environ)
    authorize_url = build_authorize_url(
        client_id,
        redirect_uri=args.redirect_uri,
        scope=args.scope,
    )
    code = wait_for_authorization_code(authorize_url, timeout=args.wait_timeout)
    token = request_access_token(
        code,
        client_id,
        client_secret,
        redirect_uri=args.redirect_uri,
        timeout=args.http_timeout,
    )
    return token.access_token


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 主函数，返回进程退出码。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        access_token = run(args)
    except ConfigurationError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2
    except BaiduAuthError as exc:
        print(f"授权失败：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130
    # token 本身就是本工具的产出，写到 stdout 便于管道/脚本使用
    print(access_token)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
