"""已弃用：请改用 `python -m baidu_auth` 或安装后的 `baidu-auth` 命令。"""

import sys

print("授权码.py 已弃用，逻辑已重构到 baidu_auth 包；请运行 python -m baidu_auth 或 baidu-auth。", file=sys.stderr)
raise SystemExit(2)
