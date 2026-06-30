"""Post run results to Discord via webhook.

Requires DISCORD_WEBHOOK_URL in the environment. No-op when unset.
Sends a stats embed with profile photos attached.
"""

import json
import os
import time
from pathlib import Path
from urllib import request as urllib_request

import config


_USER_AGENT = "BumbleAuto/1.0"


def _send_multipart_payload(webhook_url: str, payload: dict,
                             files: list[tuple[str, bytes]]) -> None:
    """Send a Discord webhook payload with optional file attachments.

    Uses multipart/form-data so files appear as message attachments in
    the same message as the embed. Requires User-Agent header — Discord
    blocks Python's default urllib user-agent.
    """
    import uuid
    boundary = uuid.uuid4().hex

    body_parts = []

    # payload_json field (the embed and attachment metadata)
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="payload_json"\r\n'
        f"Content-Type: application/json\r\n\r\n"
        f"{json.dumps(payload)}\r\n"
    )

    # File fields — one per profile photo
    for i, (filename, data) in enumerate(files):
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files[{i}]"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n\r\n".encode()
            + data
            + b"\r\n"
        )

    body_parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(
        p.encode() if isinstance(p, str) else p for p in body_parts
    )

    req = urllib_request.Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        urllib_request.urlopen(req)
    except urllib_request.HTTPError as e:
        print(f"[report] webhook failed: {e.code} {e.read().decode()[:200]}")


def post_run(likes_sent: int, profiles_seen: int, skips: int,
             total_cost: float, total_duration_s: float,
             liked_profiles: list[dict] | None = None) -> None:
    """Post a stats embed + profile photos to the configured webhook.

    Only uploads photos for profiles swiped right in this run (from
    *liked_profiles*). Uses exact folder names to avoid mismatches when
    two profiles share a name.

    Reads DISCORD_WEBHOOK_URL from the environment. No-op when unset.
    """
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return  # silent no-op — webhook is optional

    liked_profiles = liked_profiles or []

    # Collect profile photos from this run
    liked_dir = config.DEBUG_DIR / "liked"
    files: list[tuple[str, bytes]] = []
    profile_texts: list[str] = []

    for i, profile in enumerate(liked_profiles):
        name = profile.get("name", "unknown").capitalize()
        profile_texts.append(f"{i + 1}. **{name}**")

        # Find & read the first photo using exact folder name
        folder_name = profile.get("folder")
        photo = None
        if folder_name and liked_dir.is_dir():
            exact_folder = liked_dir / folder_name
            candidate = exact_folder / "imgs" / "frame_00.png"
            if candidate.is_file():
                photo = candidate
        if photo is None:
            # Fallback: scan by name (pre-timestamp format compatibility)
            safe = "".join(c for c in profile.get("name", "unknown").lower() if c.isalnum()) or "unknown"
            if liked_dir.is_dir():
                for folder in sorted(liked_dir.iterdir()):
                    if folder.is_dir() and f"_{safe}" in folder.name:
                        candidate = folder / "imgs" / "frame_00.png"
                        if candidate.is_file():
                            photo = candidate
                            break
        if photo:
            files.append((f"{profile.get('name', 'unknown')}_frame_00.png", photo.read_bytes()))

    embed = {
        "title": "Bumble Auto — Run Complete",
        "color": 0x57F287,
        "fields": [
            {"name": "👀 Seen",  "value": str(profiles_seen), "inline": True},
            {"name": "❤️ Likes", "value": str(likes_sent),    "inline": True},
            {"name": "⏭️ Skip",  "value": str(skips),         "inline": True},
            {
                "name": "Swiped Right",
                "value": "\n".join(profile_texts) if profile_texts else "None",
                "inline": False,
            },
        ],
        "footer": {"text": f"${total_cost:.2f} · {total_duration_s:.0f}s"},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }

    payload = {"embeds": [embed]}
    if files:
        payload["attachments"] = [
            {"id": i, "filename": fn, "description": f"Photo {i + 1}"}
            for i, (fn, _) in enumerate(files)
        ]

    _send_multipart_payload(webhook_url, payload, files)
