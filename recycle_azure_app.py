"""Recycle the Azure App Service worker after a zip deployment.

Azure's zip deploy can update /home/site/wwwroot without replacing a long-lived
Python process. This helper uses the existing publish-profile credentials only
inside GitHub Actions, asks Kudu to stop the bot worker, and waits for App
Service to start a fresh process that reports a new health-check uptime.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def _request(url: str, *, auth: str | None = None, method: str = "GET"):
    headers = {"Accept": "application/json"}
    if auth:
        headers["Authorization"] = f"Basic {auth}"
    request = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
        return response.status, json.loads(body) if body else None


def _publish_profile() -> tuple[str, str]:
    root = ET.fromstring(os.environ["AZURE_PUBLISH_PROFILE"])
    profiles = root.findall(".//publishProfile")
    profile = next(
        (
            item
            for item in profiles
            if "scm." in item.attrib.get("publishUrl", "")
            and item.attrib.get("userName")
            and item.attrib.get("userPWD")
        ),
        None,
    )
    if profile is None:
        raise RuntimeError("Publish profile does not contain Kudu credentials")

    host = profile.attrib["publishUrl"].split(":", 1)[0]
    credentials = (
        f'{profile.attrib["userName"]}:{profile.attrib["userPWD"]}'.encode()
    )
    auth = base64.b64encode(credentials).decode()
    return f"https://{host}", auth


def _process_details(kudu_url: str, auth: str) -> list[dict]:
    _, processes = _request(f"{kudu_url}/api/processes", auth=auth)
    details = []
    for process in processes or []:
        process_id = process.get("id")
        if process_id is None:
            continue
        try:
            _, detail = _request(
                f"{kudu_url}/api/processes/{process_id}", auth=auth
            )
            details.append(detail or process)
        except urllib.error.HTTPError:
            details.append(process)
    return details


def _is_bot_process(process: dict) -> bool:
    command = str(process.get("command_line") or "").lower()
    name = str(process.get("name") or "").lower()
    is_scm = bool(process.get("is_scm_site"))
    return not is_scm and "main.py" in command and "python" in (command + name)


def _health(app_url: str) -> dict | None:
    try:
        _, payload = _request(f'{app_url.rstrip("/")}/health')
        return payload
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError):
        return None


def main() -> None:
    app_url = os.environ["APP_URL"].rstrip("/")
    kudu_url, auth = _publish_profile()
    before = _health(app_url) or {}
    before_uptime = int(before.get("uptime_seconds", 0))

    candidates = [
        process
        for process in _process_details(kudu_url, auth)
        if _is_bot_process(process)
    ]
    if len(candidates) != 1:
        safe_processes = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "is_scm_site": item.get("is_scm_site"),
            }
            for item in _process_details(kudu_url, auth)
        ]
        raise RuntimeError(
            f"Expected exactly one bot process, found {len(candidates)}; "
            f"processes={safe_processes}"
        )

    process_id = candidates[0]["id"]
    print(f"Recycling bot worker pid={process_id}")
    _request(f"{kudu_url}/api/processes/{process_id}", auth=auth, method="DELETE")

    for _ in range(60):
        time.sleep(5)
        health = _health(app_url)
        if not health or not health.get("bot_connected"):
            continue
        uptime = int(health.get("uptime_seconds", before_uptime))
        if uptime < before_uptime and uptime < 300:
            print(f"Fresh bot worker healthy; uptime_seconds={uptime}")
            return

    raise RuntimeError("Fresh bot worker did not become healthy within 5 minutes")


if __name__ == "__main__":
    main()
