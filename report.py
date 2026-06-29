"""Post run results to Discord via webhook.

Requires DISCORD_WEBHOOK_URL in the environment. No-op when unset.
"""

import json
import os
import time
from pathlib import Path
from urllib import request as urllib_request

import config


def _send_embed(webhook_url: str, embed: dict) -> None:
    """Send a single embed payload to the Discord webhook."""
    body = json.dumps({"embeds": [embed]}).encode("utf-8")
    req = urllib_request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib_request.urlopen(req)
    except urllib_request.HTTPError as e:
        print(f"[report] webhook embed failed: {e.code} {e.read().decode()[:200]}")


def _send_file(webhook_url: str, filepath: Path) -> None:
    """Upload a single file to the Discord webhook."""
    if not filepath.is_file():
        return

    import uuid
    boundary = uuid.uuid4().hex
    filename = filepath.name
    data = filepath.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n".encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib_request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        urllib_request.urlopen(req)
    except urllib_request.HTTPError as e:
        print(f"[report] webhook file upload failed: {e.code} {e.read().decode()[:200]}")


def post_run(likes_sent: int, profiles_seen: int, skips: int,
             total_cost: float, total_duration_s: float,
             liked_profiles: list[dict] | None = None) -> None:
    """Post a summary embed + liked profile photos to the configured webhook.

    Only uploads photos for profiles liked in this run (from *liked_profiles*).
    Reads DISCORD_WEBHOOK_URL from the environment. No-op when unset.
    """
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return  # silent no-op — webhook is optional

    liked_profiles = liked_profiles or []

    color = 0x57F287

    embed = {
        "title": "Hinge Auto — Run Complete",
        "color": color,
        "fields": [
            {"name": "👀 Profiles Seen", "value": str(profiles_seen), "inline": True},
            {"name": "❤️ Likes Sent",    "value": str(likes_sent),    "inline": True},
            {"name": "⏭️ Skipped",       "value": str(skips),         "inline": True},
        ],
        "footer": {"text": f"${total_cost:.2f} · {total_duration_s:.0f}s"},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }

    _send_embed(webhook_url, embed)

    # Upload first photo of each liked profile from this run
    liked_dir = config.DEBUG_DIR / "liked"
    if not liked_dir.is_dir():
        return

    for profile in liked_profiles:
        idx = profile.get("index", 0)
        name = profile.get("name", "unknown")
        safe = "".join(c for c in name.lower() if c.isalnum()) or "unknown"
        # Walk debug/liked/ folders to find matching one
        for folder in sorted(liked_dir.iterdir()):
            if not folder.is_dir():
                continue
            if folder.name.endswith(f"_{safe}"):
                first_photo = folder / "imgs" / "frame_00.png"
                if first_photo.is_file():
                    time.sleep(0.5)  # avoid rate-limit bursts
                    _send_file(webhook_url, first_photo)
                break
