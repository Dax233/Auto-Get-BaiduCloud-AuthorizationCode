# Auto-Get-BaiduCloud-AuthorizationCode（重构版）

获取百度网盘 OAuth `access_token` 的小工具。

原仓库是一个一次性脚本：`import` 就执行整个授权流程、凭证写成空全局变量、XPATH 硬编码、
`except: pass` 吞异常、`while` + `sleep(1)` 盲轮询。本重构把同样的流程拆成了可安装、
可测试、可脚本调用的命令行工具，行为上仍然只做一件事：**扫码授权，换一个 access_token**。

## 用途

- 通过浏览器完成百度网盘 OAuth 授权（扫码/登录），拿到授权码；
- 用授权码换取 `access_token`，输出到 stdout，方便被其他脚本消费；
- 凭证通过命令行参数或环境变量传入，不再修改源码；缺凭证时直接给清晰报错。

## 安装

需要 Python 3.9+、本机可用的 Chrome（Selenium Manager 会自动匹配/下载驱动）。

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
# 或只装依赖、直接用 python -m baidu_auth 运行
.venv/bin/pip install -r requirements.txt
```

安装后获得 console script：`baidu-auth`。

## 用法

推荐用环境变量传凭证（避免进入 shell 历史）：

```bash
export BAIDU_CLIENT_ID="你的 AppKey"
export BAIDU_CLIENT_SECRET="你的 SecretKey"
baidu-auth
```

或者：

```bash
python -m baidu_auth --client-id "你的 AppKey" --client-secret "你的 SecretKey"
# 等浏览器里完成授权后，stdout 输出 access_token
```

常用参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--client-id` | 环境变量 `BAIDU_CLIENT_ID` | 应用 AppKey |
| `--client-secret` | 环境变量 `BAIDU_CLIENT_SECRET` | 应用 SecretKey（不会打印） |
| `--redirect-uri` | `oob` | OAuth 回调地址 |
| `--scope` | `basic,netdisk` | 申请的权限范围 |
| `--wait-timeout` | `120` | 等待用户在浏览器完成授权的秒数 |
| `--http-timeout` | `15` | 请求 token 接口的超时秒数 |
| `--version` | | 打印版本 |

输出与退出码：

- 成功：stdout 只有一行 `access_token`，退出码 `0`；
- 配置错误（缺 AppKey/SecretKey 等）：stderr 提示，退出码 `2`；
- 授权/网络失败：stderr 提示，退出码 `1`；
- 用户 Ctrl-C：退出码 `130`。

凭证获取：到 <https://pan.baidu.com/union/console/applist> 创建应用（说明见
<https://pan.baidu.com/union/doc/ol0rsap9s>）。

## 原理

1. `baidu_auth.oauth.build_authorize_url()` 用 `urlencode` 构造授权页 URL；
2. `baidu_auth.browser` 启动 Chrome 打开该 URL（`qrcode=1` 的扫码页）；
3. 用 `WebDriverWait` 显式等待授权成功后出现的 `#Verifier` 输入框「有非空值」，取出
   授权码（不再 `sleep` 盲等、不再硬编码 XPath）；浏览器以 context manager 管理，
   异常时也会关闭；
4. `baidu_auth.oauth.request_access_token()` 把 code 以 POST 表单提交到 token 接口，
   解析 JSON；百度返回 `error` 时转成带 `error_description` 的可读异常。

## 目录结构

```
baidu_auth/
├── __init__.py    # 包的公开 API 与版本号
├── __main__.py    # 支持 python -m baidu_auth
├── cli.py         # argparse 入口、凭证解析（参数 > 环境变量）、退出码
├── oauth.py       # 授权页 URL 构造 + token 请求/解析（纯逻辑）
├── browser.py     # Selenium 授权页交互（context manager + WebDriverWait）
└── errors.py      # 自定义异常
tests/             # 纯逻辑单测，mock 掉 selenium / requests
pyproject.toml     # 打包配置与 baidu-auth 入口
授权码.py          # 已弃用的兼容入口，仅提示改用新入口
```

## 开发与测试

```bash
python3 -m venv .venv
.venv/bin/pip install pytest requests selenium
.venv/bin/python -m pytest -q
```

测试不启动浏览器、不发真实网络请求：Selenium 与 requests 都由假对象替代，覆盖
URL 构造、token JSON 解析与错误、参数校验、环境变量回退、浏览器等待/清理逻辑。

## 已知限制

- 仅支持交互式桌面环境：需要能弹出 Chrome 窗口并人工完成扫码/登录，纯 headless
  服务器上不可用；
- 授权页的元素 id 依赖百度页面结构，若百度改版可能失效；
- 只做 `authorization_code` 换 token，不实现 refresh_token 续期、不做 token 持久化；
- 原脚本里的 `device_id` 实际未参与 OAuth 流程，本重构已移除；
- `requirements.txt` 保留原内容（固定版本），与 `pyproject.toml` 的版本范围并存。

## 免责声明

本项目仅供学习与个人自动化使用。使用即表示你自行遵守百度开放平台的服务条款，
并对 AppKey/SecretKey 与 access_token 的保管负责；请勿用于任何违反服务条款、
侵犯他人权益或未经授权的用途。因使用本工具造成的任何后果由使用者自行承担。

## 致谢

原项目：[Dax233/Auto-Get-BaiduCloud-AuthorizationCode](https://github.com/Dax233/Auto-Get-BaiduCloud-AuthorizationCode)。
本分支仅做工程重构，保留原有流程语义；原仓库未附带 LICENSE 文件，本重构不额外附加许可证。
