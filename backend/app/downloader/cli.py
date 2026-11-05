"""Command line interface for the downloader adapter.

Examples:
    uv run python -m app.downloader resolve https://www.instagram.com/p/XXXX/
    uv run python -m app.downloader download https://www.instagram.com/reel/XXXX/ -o downloads
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from .engines.iqsaved import IqSavedEngine
from .errors import DownloaderError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ins-downloader",
        description="Resolve and download Instagram media through the iqsaved adapter.",
    )
    parser.add_argument(
        "command",
        choices=("resolve", "download"),
        help="resolve metadata only, or also download the media files",
    )
    parser.add_argument("urls", nargs="+", help="Instagram post, reel or TV URLs")
    parser.add_argument(
        "-o",
        "--output",
        default="downloads",
        help="directory for downloaded files (default: downloads)",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=3.0,
        help="minimum seconds between upstream requests (default: 3.0)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="per-request timeout in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="maximum attempts per URL (default: 3)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON instead of human-readable text",
    )
    return parser


async def run(args: argparse.Namespace) -> int:
    engine = IqSavedEngine(
        min_interval=args.min_interval,
        timeout=args.timeout,
        max_attempts=args.attempts,
    )
    results: list[dict[str, Any]] = []

    try:
        for url in args.urls:
            entry: dict[str, Any] = {"url": url}
            try:
                post = await engine.resolve(url)
                entry["status"] = "success"
                entry["post"] = post.model_dump(mode="json")

                if args.command == "download":
                    destination = Path(args.output) / post.shortcode
                    files = []
                    for item in post.items:
                        path = _unique_path(destination / item.filename)
                        downloaded = await engine.download(item, path)
                        files.append(downloaded.model_dump(mode="json"))
                    entry["files"] = files
            except DownloaderError as exc:
                entry["status"] = "error"
                entry["error"] = type(exc).__name__
                entry["message"] = str(exc)
            except OSError as exc:
                entry["status"] = "error"
                entry["error"] = type(exc).__name__
                entry["message"] = str(exc)

            results.append(entry)
            if not args.json:
                _print_human(entry)
    finally:
        await engine.close()

    if args.json:
        payload: Any = results[0] if len(results) == 1 else results
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    return 0 if all(entry["status"] == "success" for entry in results) else 1


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _print_human(entry: dict[str, Any]) -> None:
    print(f"\n{entry['url']}")
    if entry["status"] != "success":
        print(f"  ERROR {entry['error']}: {entry['message']}")
        return

    post = entry["post"]
    author = post.get("author") or "unknown"
    caption = (post.get("caption") or "").replace("\n", " ")[:100]
    print(f"  author: {author}")
    print(f"  shortcode: {post['shortcode']} | items: {len(post['items'])}")
    if caption:
        print(f"  caption: {caption}")

    files = entry.get("files")
    if files:
        for downloaded in files:
            size = downloaded["size"]
            print(f"  saved: {downloaded['path']} ({size} bytes)")
    else:
        for item in post["items"]:
            print(f"  {item['kind']}: {item['filename']}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
