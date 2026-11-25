#!/usr/bin/env python3
"""反爬 / 防刷 接口冒烟测试。

对着一个**正在运行**的 RepoPress 实例发请求，验证反爬策略是否生效：
  - 搜索蜘蛛 / 脚本 UA 被拦（403），健康检查与 robots 豁免
  - 浏览器 UA 不被误拦
  - /api/* 按 IP 限流会触发 429
  - 安全响应头存在

用法（在 server/ 目录下）：
    python test.py                      # 默认 http://127.0.0.1:8099
    python test.py http://127.0.0.1:8097
    REPOPRESS_BASE_URL=http://... python test.py

需要服务已在运行，例如： python -m cli start
只用标准库（urllib），不依赖 pytest / requests / httpx。
"""

import os
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("REPOPRESS_BASE_URL", "http://quant.md.lawyer5.cn/")).rstrip("/")

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
BAIDU_UA = "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)"


def call(path, ua=BROWSER_UA, xff=None, method="GET", timeout=10):
    """Send a request and return (status, headers-dict, body-bytes). Never raises on 4xx/5xx."""
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("User-Agent", ua)
    if xff:
        req.add_header("X-Forwarded-For", xff)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, exc.read()


# ── 反爬用例 ──────────────────────────────────────────────────────────

def test_health_is_exempt_even_for_bot_ua():
    """健康检查是豁免路径，即使爬虫 UA 也应放行。"""
    status, _, _ = call("/api/health", ua="curl/8.0.0")
    assert status == 200, f"expected 200, got {status}"


def test_googlebot_blocked():
    status, _, _ = call("/api/admin/users", ua=GOOGLEBOT_UA)
    assert status == 403, f"expected 403 for Googlebot, got {status}"


def test_baiduspider_blocked():
    status, _, _ = call("/api/admin/users", ua=BAIDU_UA)
    assert status == 403, f"expected 403 for Baiduspider, got {status}"


def test_script_ua_blocked():
    status, _, _ = call("/api/admin/users", ua="python-requests/2.31.0")
    assert status == 403, f"expected 403 for python-requests, got {status}"


def test_nonbrowser_ua_blocked():
    """无浏览器特征的 UA（空 UA / curl 等）应被拦。"""
    status, _, _ = call("/api/admin/users", ua="")
    assert status == 403, f"expected 403 for empty UA, got {status}"


def test_browser_ua_not_blocked():
    """浏览器 UA 不应被反爬误拦：通过 bot 检查后，因无 token 返回 401。"""
    status, _, _ = call("/api/admin/users", ua=BROWSER_UA, xff="10.0.0.1")
    assert status == 401, f"expected 401 (auth required, not bot-blocked), got {status}"


def test_security_headers_present():
    status, headers, _ = call("/api/health")
    assert status == 200, f"expected 200, got {status}"
    assert headers.get("x-content-type-options") == "nosniff", headers
    assert headers.get("x-frame-options") == "DENY", headers
    assert "referrer-policy" in headers, headers


def test_robots_disallow_all():
    status, _, body = call("/robots.txt")
    assert status == 200, f"expected 200, got {status}"
    assert b"Disallow: /" in body, f"unexpected robots body: {body!r}"


def test_rate_limit_triggers_429():
    """同一 IP 高频请求 /api/* 应触发 429（用独立 XFF 隔离限流桶）。"""
    xff = "203.0.113.7"
    for _ in range(300):
        status, _, _ = call("/api/admin/users", ua=BROWSER_UA, xff=xff)
        if status == 429:
            return
    raise AssertionError("rate limit did not trigger within 300 requests")


def main():
    # 连通性检查
    try:
        call("/api/health")
    except Exception as exc:  # noqa: BLE001
        print(f"无法连接 {BASE}: {exc}")
        print("请先启动服务，例如： python -m cli start")
        sys.exit(2)

    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    print(f"测试目标: {BASE}\n")
    passed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL  {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR {fn.__name__}: {exc}")

    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)


if __name__ == "__main__":
    main()
