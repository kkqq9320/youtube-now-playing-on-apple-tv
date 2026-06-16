from __future__ import annotations

import json
import os
import re
from http.cookiejar import MozillaCookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

HISTORY_URL = "https://www.youtube.com/feed/history"
WAITING_FOR_TRIGGER_ERROR = "waiting for selected Apple TV to start playing YouTube"
WAITING_FOR_HISTORY_ERROR = "waiting for YouTube history refresh"
DEFAULT_COOKIE_FILES = (
    "/config/.youtube_cookies.txt",
    "/config/.youtube_cookies.txt.",
)


def empty_payload(error: str, cookies: bool = False) -> dict[str, Any]:
    """Build an empty payload with a diagnostic error."""
    return {
        "channel": "",
        "title": "",
        "video_id": "",
        "duration_string": "",
        "thumbnail": "",
        "original_url": "",
        "cookies": cookies,
        "error": error,
    }


def waiting_payload() -> dict[str, Any]:
    """Build the initial payload before any Apple TV playback trigger matches."""
    return empty_payload(WAITING_FOR_TRIGGER_ERROR)


def standalone_waiting_payload() -> dict[str, Any]:
    """Build the initial payload before a standalone history refresh runs."""
    return empty_payload(WAITING_FOR_HISTORY_ERROR)


def resolve_cookie_file(cookie_file: str | None) -> str:
    """Resolve an explicitly configured or legacy default cookie file path."""
    if cookie_file:
        return cookie_file

    for candidate in DEFAULT_COOKIE_FILES:
        if os.path.exists(candidate):
            return candidate

    return DEFAULT_COOKIE_FILES[0]


def load_cookies(cookie_file: str) -> MozillaCookieJar:
    """Load a Netscape-format YouTube cookie file."""
    cookie_jar = MozillaCookieJar(cookie_file)
    cookie_jar.load(ignore_discard=True, ignore_expires=True)
    return cookie_jar


def fetch_history_html(cookie_jar: MozillaCookieJar) -> str:
    """Fetch the signed-in YouTube history page."""
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    request = Request(
        HISTORY_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Sec-Fetch-Mode": "navigate",
        },
    )

    with opener.open(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_yt_initial_data(html: str) -> dict[str, Any]:
    """Extract the ytInitialData object from a YouTube HTML page."""
    match = re.search(r"var\s+ytInitialData\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not match:
        match = re.search(r"ytInitialData\"\]\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not match:
        raise ValueError("ytInitialData was not found")
    return json.loads(match.group(1))


def iter_nodes(value: Any):
    """Yield a nested JSON node and all of its descendants."""
    yield value

    if isinstance(value, dict):
        for item in value.values():
            yield from iter_nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_nodes(item)


def text_content(value: Any) -> str:
    """Extract text from common YouTube text model shapes."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("content"), str):
            return value["content"]
        if isinstance(value.get("simpleText"), str):
            return value["simpleText"]
        runs = value.get("runs")
        if isinstance(runs, list):
            return "".join(run.get("text", "") for run in runs if isinstance(run, dict))
    return ""


def find_first_video_item(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Find the first video-like item in YouTube history data."""
    for value in iter_nodes(data):
        if not isinstance(value, dict):
            continue

        lockup = value.get("lockupViewModel")
        if isinstance(lockup, dict) and lockup.get("contentId"):
            return "lockup", lockup

        for key in ("videoRenderer", "compactVideoRenderer", "gridVideoRenderer"):
            renderer = value.get(key)
            if isinstance(renderer, dict) and renderer.get("videoId"):
                return "renderer", renderer

        reel = value.get("reelItemRenderer")
        if isinstance(reel, dict) and reel.get("videoId"):
            return "reel", reel

    raise ValueError(
        "video item was not found; refresh YouTube cookies if history is empty or logged out"
    )


def first_thumbnail(video_id: str, fallback: str = "") -> str:
    """Prefer maxresdefault when it exists, otherwise fall back safely."""
    base = f"https://i.ytimg.com/vi/{video_id}"
    maxres = f"{base}/maxresdefault.jpg"
    fallback = fallback or f"{base}/hqdefault.jpg"

    try:
        request = Request(maxres, method="HEAD")
        with urlopen(request, timeout=1) as response:
            if response.status == 200:
                return maxres
    except (HTTPError, URLError, TimeoutError, ValueError):
        pass

    return fallback


def thumbnail_from_renderer(renderer: dict[str, Any], video_id: str) -> str:
    """Extract the best thumbnail already present in a renderer."""
    thumbnails = renderer.get("thumbnail", {}).get("thumbnails", [])
    if thumbnails:
        return first_thumbnail(video_id, thumbnails[-1].get("url", ""))
    return first_thumbnail(video_id)


def parse_lockup(lockup: dict[str, Any]) -> dict[str, Any]:
    """Parse a lockupViewModel item."""
    video_id = lockup.get("contentId", "")
    metadata = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
    rows = (
        metadata.get("metadata", {})
        .get("contentMetadataViewModel", {})
        .get("metadataRows", [])
    )

    channel = ""
    if rows:
        parts = rows[0].get("metadataParts", [])
        if parts:
            channel = text_content(parts[0].get("text", {}))

    duration_string = ""
    overlays = (
        lockup.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", [])
    )
    for value in iter_nodes(overlays):
        if isinstance(value, dict) and "thumbnailBadgeViewModel" in value:
            duration_string = text_content(
                value["thumbnailBadgeViewModel"].get("text", {})
            )
            if duration_string:
                break

    return {
        "channel": channel,
        "title": text_content(metadata.get("title", {})),
        "video_id": video_id,
        "duration_string": duration_string,
        "thumbnail": first_thumbnail(video_id) if video_id else "",
        "original_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "cookies": bool(video_id),
        "error": "",
    }


def parse_renderer(renderer: dict[str, Any]) -> dict[str, Any]:
    """Parse a classic videoRenderer item."""
    video_id = renderer.get("videoId", "")
    channel = text_content(renderer.get("ownerText", {}))
    if not channel:
        channel = text_content(renderer.get("shortBylineText", {}))
    if not channel:
        channel = text_content(renderer.get("longBylineText", {}))

    return {
        "channel": channel,
        "title": text_content(renderer.get("title", {})),
        "video_id": video_id,
        "duration_string": text_content(renderer.get("lengthText", {})),
        "thumbnail": thumbnail_from_renderer(renderer, video_id) if video_id else "",
        "original_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "cookies": bool(video_id),
        "error": "",
    }


def parse_reel(reel: dict[str, Any]) -> dict[str, Any]:
    """Parse a Shorts reel item."""
    video_id = reel.get("videoId", "")
    return {
        "channel": text_content(reel.get("accessibility", {})),
        "title": text_content(reel.get("headline", {})),
        "video_id": video_id,
        "duration_string": "",
        "thumbnail": thumbnail_from_renderer(reel, video_id) if video_id else "",
        "original_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "cookies": bool(video_id),
        "error": "",
    }


def parse_video_item(item_type: str, item: dict[str, Any]) -> dict[str, Any]:
    """Parse a YouTube video item by detected shape."""
    if item_type == "lockup":
        return parse_lockup(item)
    if item_type == "reel":
        return parse_reel(item)
    return parse_renderer(item)


def fetch_latest_thumbnail(cookie_file: str | None) -> dict[str, Any]:
    """Fetch the latest YouTube history item using a cookie file."""
    resolved_cookie_file = resolve_cookie_file(cookie_file)

    try:
        cookie_jar = load_cookies(resolved_cookie_file)
    except OSError as error:
        return empty_payload(f"cookie file not found: {error}")
    except Exception as error:
        return empty_payload(f"cookie load failed: {error}")

    try:
        html = fetch_history_html(cookie_jar)
        cookie_jar.save(ignore_discard=True, ignore_expires=True)
        data = extract_yt_initial_data(html)
        return parse_video_item(*find_first_video_item(data))
    except Exception as error:
        return empty_payload(str(error))
