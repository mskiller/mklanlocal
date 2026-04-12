from __future__ import annotations

import json
import os
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


def _request_json(opener, url: str, *, method: str = "GET", payload: dict | None = None):
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method=method, headers=headers)
    with opener.open(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _assert_page(opener, url: str) -> None:
    request = Request(url, method="GET")
    with opener.open(request) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned {response.status}")


def main() -> None:
    base_url = os.environ.get("FRONTEND_BASE_URL", "http://frontend:3000").rstrip("/")
    credentials = [
        (os.environ.get("SMOKE_USERNAME"), os.environ.get("SMOKE_PASSWORD")),
        (os.environ.get("ADMIN_USERNAME", "admin"), os.environ.get("ADMIN_PASSWORD", "admin")),
        (os.environ.get("CURATOR_USERNAME", "curator"), os.environ.get("CURATOR_PASSWORD", "change-me")),
        (os.environ.get("GUEST_USERNAME", "guest"), os.environ.get("GUEST_PASSWORD", "guest")),
    ]

    opener = None
    for username, password in credentials:
        if not username or not password:
            continue
        candidate = build_opener(HTTPCookieProcessor(CookieJar()))
        try:
            _request_json(
                candidate,
                f"{base_url}/api/auth/login",
                method="POST",
                payload={"username": username, "password": password},
            )
            opener = candidate
            break
        except HTTPError as exc:
            if exc.code != 401:
                raise

    if opener is None:
        raise RuntimeError("Unable to authenticate smoke test with any configured user.")

    sources = _request_json(opener, f"{base_url}/api/sources")
    assets = _request_json(opener, f"{base_url}/api/assets?page=1&page_size=2")
    collections = _request_json(opener, f"{base_url}/api/collections")
    scan_jobs = _request_json(opener, f"{base_url}/api/scan-jobs")

    pages = [
        f"{base_url}/",
        f"{base_url}/sources",
        f"{base_url}/browse-indexed",
        f"{base_url}/search",
        f"{base_url}/collections",
        f"{base_url}/scan-jobs",
        f"{base_url}/upload",
        f"{base_url}/profile",
    ]

    if sources:
        pages.append(f"{base_url}/sources/{sources[0]['id']}")

    if assets.get("items"):
        asset = assets["items"][0]
        pages.extend(
            [
                f"{base_url}/assets/{asset['id']}",
                f"{base_url}/assets/{asset['id']}/similar",
                f"{base_url}/sources/{asset['source_id']}?{urlencode({'path': '/'.join(asset['relative_path'].split('/')[:-1])})}"
                if "/" in asset["relative_path"]
                else f"{base_url}/sources/{asset['source_id']}",
            ]
        )

    if collections:
        pages.append(f"{base_url}/collections/{collections[0]['id']}")

    if scan_jobs:
        pages.append(f"{base_url}/scan-jobs/{scan_jobs[0]['id']}")

    if assets.get("items") and len(assets["items"]) >= 2:
        pages.append(f"{base_url}/compare?a={assets['items'][0]['id']}&b={assets['items'][1]['id']}")

    checked = 0
    for page in pages:
        _assert_page(opener, page)
        checked += 1

    print(f"Smoke check passed for {checked} authenticated frontend routes.")


if __name__ == "__main__":
    main()
