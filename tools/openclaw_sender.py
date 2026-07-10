"""Read an existing Markdown report and send it to an OpenClaw webhook."""

from datetime import datetime
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = BASE_DIR / "logs" / "openclaw.log"


def _safe_message(error):
    """Return a short, single-line error without configuration values."""
    return str(error or "").replace("\n", " ").replace("\r", " ")[:240]


def _write_log(report_name, enabled, group_configured, ok, status_code=None, error=""):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = [
        timestamp,
        Path(report_name).name or "-",
        f"enabled={str(enabled).lower()}",
        f"group_configured={str(group_configured).lower()}",
        f"result={'success' if ok else 'failed'}",
        f"status_code={status_code if status_code is not None else '-'}",
        f"message={_safe_message(error) or '-'}",
    ]
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write("\t".join(fields) + "\n")


def _result(ok, enabled, message, status_code=None):
    return {
        "ok": ok,
        "enabled": enabled,
        "message": message,
        "status_code": status_code,
    }


def send_report(report_path: str) -> dict:
    """Read and send the complete Markdown report at ``report_path``."""
    path = Path(report_path)
    report_name = path.name
    enabled = os.environ.get("OPENCLAW_WECHAT_ENABLED") == "1"
    group = os.environ.get("OPENCLAW_WECHAT_GROUP", "").strip()
    group_configured = bool(group)

    if not enabled:
        message = "OpenClaw 推送未开启"
        print(message)
        _write_log(report_name, False, group_configured, False, error=message)
        return _result(False, False, message)

    webhook_url = os.environ.get("OPENCLAW_WEBHOOK_URL", "").strip()
    if not webhook_url:
        message = "缺少 OpenClaw webhook 配置"
        _write_log(report_name, True, group_configured, False, error=message)
        return _result(False, True, message)
    if not group_configured:
        message = "缺少 OpenClaw 微信群标识"
        _write_log(report_name, True, False, False, error=message)
        return _result(False, True, message)

    mode = os.environ.get("OPENCLAW_PAYLOAD_MODE", "text").strip().lower()
    if mode not in {"text", "content"}:
        message = "OPENCLAW_PAYLOAD_MODE 只支持 text 或 content"
        _write_log(report_name, True, True, False, error=message)
        return _result(False, True, message)

    try:
        markdown = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        message = f"日报读取失败：{exc.__class__.__name__}"
        _write_log(report_name, True, True, False, error=message)
        return _result(False, True, message)

    payload = {"group": group, mode: markdown}
    try:
        request = Request(
            webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            status_code = response.status
        if 200 <= status_code < 300:
            message = "OpenClaw 推送成功"
            _write_log(report_name, True, True, True, status_code, message)
            return _result(True, True, message, status_code)
        message = f"OpenClaw 返回非 2xx 状态：{status_code}"
        _write_log(report_name, True, True, False, status_code, message)
        return _result(False, True, message, status_code)
    except HTTPError as exc:
        message = f"OpenClaw 返回非 2xx 状态：{exc.code}"
        _write_log(report_name, True, True, False, exc.code, message)
        return _result(False, True, message, exc.code)
    except (URLError, TimeoutError, OSError) as exc:
        message = f"OpenClaw 网络请求失败：{exc.__class__.__name__}"
        _write_log(report_name, True, True, False, error=message)
        return _result(False, True, message)
