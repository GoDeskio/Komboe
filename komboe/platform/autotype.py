"""Desktop auto-type. Matching and typing happen on the device; nothing is sent to a server."""
from __future__ import annotations

import subprocess


def sequence_for(items: list[dict], window_title: str) -> list[str] | None:
    title = window_title.lower()
    for item in items:
        name = (item.get("name") or "").lower()
        uri = (item.get("uri") or "").lower()
        if name and name in title or (uri and uri in title):
            return [item.get("username") or "", "tab", item.get("password") or "", "enter"]
    return None


def type_into(window_id: str, steps: list[str]) -> None:
    subprocess.run(["xdotool", "windowactivate", "--sync", str(window_id)], check=True, capture_output=True)
    for step in steps:
        if step == "tab":
            subprocess.run(["xdotool", "key", "--window", str(window_id), "Tab"], check=True, capture_output=True)
        elif step == "enter":
            subprocess.run(["xdotool", "key", "--window", str(window_id), "Return"], check=True, capture_output=True)
        else:
            subprocess.run(["xdotool", "type", "--window", str(window_id), "--", step], check=True, capture_output=True)
