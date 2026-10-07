#!/usr/bin/env python3
"""Call Perplexity Agent API once per day (Asia/Bangkok) and publish the
result as a static page under docs/ so the phuong-tho-xauusd skill can
WebFetch it directly, without needing an MCP connector.

Skips the API call (and any cost) if docs/perplexity-latest.md already
reflects today's date in Asia/Bangkok time -- this enforces the "max
1 call per day" requirement even though the workflow may run several
times a day.

Uses the Agent API (/v1/agent, preset "fast" = Sonar Pro equivalent),
which replaced the old /chat/completions endpoint in 2026.
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
    "24 gio qua co kha nang anh huong den gia vang XAUUSD, kem nguon trich dan. "
    "Tra loi ngan gon, chinh xac, bang tieng Viet."
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
    url = "https://api.perplexity.ai/v1/agent"
    payload = {
        "preset": "fast",
        "input": QUERY,
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
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_answer_and_sources(data: dict):
    answer = None
    sources = []
    for item in data.get("output", []):
        item_type = item.get("type")
        if item_type == "message":
            content = item.get("content") or []
            for c in content:
                text = c.get("text")
                if text:
                    answer = text
        elif item_type == "search_results":
            for r in item.get("results", []):
                u = r.get("url")
                t = r.get("title") or u
                if u:
                    sources.append((t, u))
    return answer, sources


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

    answer, sources = extract_answer_and_sources(data)
    if not answer:
        print(f"Perplexity: phan hoi khong co noi dung: {data}", file=sys.stderr)
        return 0

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
        answer,
        "",
    ]
    if sources:
        lines.append("### Nguon trich dan")
        for i, (title, u) in enumerate(sources, start=1):
            lines.append(f"{i}. [{title}]({u})")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Perplexity: da ghi {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
