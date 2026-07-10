"""Resend the newest generated daily report."""

from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tools.openclaw_sender import send_report


def main():
    reports = list((BASE_DIR / "reports").glob("*.md"))
    if not reports:
        print("未找到可发送的日报")
        return 1
    latest = max(reports, key=lambda path: path.stat().st_mtime)
    try:
        result = send_report(latest)
    except Exception as exc:
        print(f"OpenClaw 推送失败：{exc.__class__.__name__}")
        return 1
    if result["enabled"]:
        print(result["message"])
    return 0 if result["ok"] or not result["enabled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
