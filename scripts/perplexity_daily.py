#!/usr/bin/env python3
"""Call Perplexity Sonar Pro once per day (Asia/Bangkok) and publish the
result as a static page under docs/ so the phuong-tho-xauusd skill can
WebFetch it directly, without needing an MCP connector.

Skips the API call (and any cost) if docs/perplexity-latest.md already
reflects today's date in Asia/Bangkok time -- this enforces the "max
1 call per day" requirement even though the workflow may run several
times a day.
"""
import os
import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.error

BANGKOK = timezone(timedelta(hours=7))
OUT_PATH = Path("docs/perplexity-latest.md")
QUERY = (
    "Tom tat tin tuc vi mo/dia chinh tri/Fed/loi suat quan trong nhat trong "
    "24 gio qua co kha nang anh huong den gia vang XAUUSD, kem nguon trich dan."
)


def today_bangkok() -> str:
    return datetime.now(BANGKOK).strftime("%Y-%m-%d")


def already_done_today() -> bool:
    if not OUT_PATH.exists():
        return False
    text = OUT_PATH.read_text(encoding="utf-8")
    marker = f"date: {today_bangkok()}"
    return marker in text


def call_perplexity(api_key: str) -> dict:
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": "Tra loi ngan gon, chinh xac, bang tieng Viet, luon kem nguon trich dan.",
            },
            {"role": "user", "content": QUERY},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    if already_done_today():
        print(f"Perplexity: da goi hom nay ({today_bangkok()}), bo qua.")
        return 0

    api_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        print("Perplexity: khong co PERPLEXITY_API_KEY, bo qua.")
        return 0

    try:
        data = call_perplexity(api_key)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        print(f"Perplexity: loi HTTP {e.code}: {body}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Perplexity: loi goi API: {e}", file=sys.stderr)
        return 0

    try:
        message = data["choices"][0]["message"]["content"]
    except Exception:
        print(f"Perplexity: phan hoi khong dung dinh dang: {data}", file=sys.stderr)
        return 0

    citations = data.get("citations") or []

    now_bkk = datetime.now(BANGKOK)
    lines = [
        "---",
        "layout: default",
        'title: "Perplexity: tin vi mo anh huong gia vang (cap nhat hang ngay)"',
        f"date: {now_bkk.strftime('%Y-%m-%d')}",
        "---",
        "",
        f"> Cap nhat luc {now_bkk.strftime('%Y-%m-%d %H:%M')} (gio Bangkok, UTC+7)",
        "",
        message,
        "",
    ]
    if citations:
        lines.append("### Nguon trich dan")
        for i, c in enumerate(citations, start=1):
            lines.append(f"{i}. {c}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Perplexity: da ghi {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
