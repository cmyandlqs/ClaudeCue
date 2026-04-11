"""Download ccCue source package for CLI install."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DownloadResult:
    ok: bool
    message: str
    source_root: Optional[Path] = None


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "cccue-installer", "Accept": "application/vnd.github+json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_file(url: str, dst: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "cccue-installer"}, method="GET")
    with urllib.request.urlopen(req, timeout=60) as response:
        dst.write_bytes(response.read())


def _find_runtime_root(extract_root: Path) -> Optional[Path]:
    candidates = [p for p in extract_root.iterdir() if p.is_dir()]
    for c in candidates:
        if (c / "hooks").exists() and (c / "cli").exists() and (c / "notifier").exists():
            return c
    return None


def download_and_extract_source(
    workdir: Path,
    repo: Optional[str] = None,
    ref: str = "latest",
    download_url: Optional[str] = None,
) -> DownloadResult:
    """Download source zip and return extracted source root.

    Priority:
    1) download_url when provided
    2) GitHub repo latest release zipball
    3) GitHub repo zipball by ref
    """
    workdir.mkdir(parents=True, exist_ok=True)
    zip_path = workdir / "source.zip"
    extract_dir = workdir / "extracted"

    try:
        if extract_dir.exists():
            for item in extract_dir.iterdir():
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
        else:
            extract_dir.mkdir(parents=True, exist_ok=True)

        if download_url:
            _download_file(download_url, zip_path)
        else:
            if not repo:
                return DownloadResult(False, "missing repo for online install")

            if ref == "latest":
                meta = _http_get_json(f"https://api.github.com/repos/{repo}/releases/latest")
                # Prefer source zipball URL from release metadata.
                zip_url = str(meta.get("zipball_url", "")).strip()
                if not zip_url:
                    return DownloadResult(False, f"cannot resolve latest release zipball for repo: {repo}")
            else:
                zip_url = f"https://api.github.com/repos/{repo}/zipball/{ref}"

            _download_file(zip_url, zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        source_root = _find_runtime_root(extract_dir)
        if not source_root:
            return DownloadResult(False, "downloaded package does not contain ccCue runtime structure")

        return DownloadResult(True, "source downloaded", source_root=source_root)

    except urllib.error.HTTPError as exc:
        return DownloadResult(False, f"download failed: HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return DownloadResult(False, f"download failed: {exc.reason}")
    except zipfile.BadZipFile:
        return DownloadResult(False, "downloaded file is not a valid zip")
    except Exception as exc:
        return DownloadResult(False, f"download failed: {exc}")
