"""Command line interface for the integrated Prydwen build pipeline."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .client import PrydwenClient
from .nanoka import DEFAULT_NANOKA_VERSION


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="hsr-prydwen")
    parser.add_argument("--work-dir", default=None, help="working directory (default: root/.hsr_prydwen)")
    parser.add_argument("--build-dir", default=None, help="approved assets directory")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--proxy", default=None)
    parser.add_argument("--settle-ms", type=int, default=5_000)
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--chrome", default=None)
    parser.add_argument("--nanoka-cache", default=None)
    parser.add_argument("--nanoka-version", default=DEFAULT_NANOKA_VERSION)
    parser.add_argument("--transport", choices=["http", "browser"], default="http")
    parser.add_argument("--refresh", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("urls", help="cache the Prydwen roster in .hsr_prydwen/rawUrls.json")
    pull = sub.add_parser("pull", help="cache character HTML")
    pull.add_argument("character", nargs="*")
    pull.add_argument("--concurrency", type=int, default=2)
    parse = sub.add_parser("parse", help="parse cached pages into build JSON drafts")
    parse.add_argument("character", nargs="*")
    validate = sub.add_parser("validate", help="validate JSON and local asset references")
    validate.add_argument("files", nargs="+")
    approve = sub.add_parser("approve", help="approve one build, or a batch with --all")
    approve.add_argument("character", nargs="?")
    approve.add_argument("--file", default=None)
    approve.add_argument("--all", action="store_true", dest="approve_all")
    approve_all = sub.add_parser("approve-all", help="approve every valid build, reporting failures")
    approve_all.add_argument("character", nargs="*")
    for command in (approve, approve_all):
        command.add_argument("--reviewer", default="manual")
        command.add_argument("--note", default=None)
    teams = sub.add_parser("teams", help="derive data/teams.json")
    teams.add_argument("--allow-draft", action="store_true")
    card = sub.add_parser("card", help="render and publish an approved build")
    card.add_argument("character")
    card.add_argument("--data", default=None)
    cards = sub.add_parser("cards", help="render a batch and create review contact sheets")
    cards.add_argument("character", nargs="*")
    for command in (card, cards):
        command.add_argument("--out", default=None)
        command.add_argument("--allow-draft", action="store_true")
        command.add_argument("--exclude-extra", action=argparse.BooleanOptionalAction, default=True,
                             help="hide condition references and overflow labels (default: true)")
        command.add_argument("--detailed", dest="exclude_extra", action="store_false",
                             help="render .detailed.png and its condition pages")
    args = parser.parse_args(argv)
    options = {key: getattr(args, key) for key in (
        "work_dir", "build_dir", "headed", "proxy", "settle_ms", "timeout_ms", "retries",
        "nanoka_cache", "nanoka_version", "transport", "refresh",
    )}
    if args.chrome is not None:
        options["chrome"] = args.chrome
    client = PrydwenClient(**options)
    try:
        if args.command == "urls":
            print(asyncio.run(client.urls()))
        elif args.command == "pull":
            result = asyncio.run(client.pull(args.character, concurrency=args.concurrency))
            print(f"Available {len(result['paths'])}; cached {result['cached']}; downloaded {result['downloaded']}")
            _failures(result["failed"])
        elif args.command == "parse":
            result = client.parse(args.character)
            for path in result["paths"]:
                print(path)
            _failures(result["failed"])
        elif args.command == "validate":
            result = client.validate(args.files)
            for item in result:
                print(json.dumps(item, ensure_ascii=False))
            if any(item["problems"] for item in result):
                raise SystemExit("Some builds are blocked")
        elif args.command in {"approve", "approve-all"}:
            if args.command == "approve-all" or args.approve_all:
                if args.command == "approve" and (args.file or args.character):
                    raise ValueError("Use approve-all with character slugs to approve a subset")
                result = client.approve_all(
                    args.character if args.command == "approve-all" else None,
                    reviewer=args.reviewer, note=args.note,
                )
                for data in result["approved"]:
                    print(f"approved {data.character.slug}")
                _failures(result["failed"])
            else:
                data = client.approve(args.character, file=args.file, reviewer=args.reviewer, note=args.note)
                print(f"approved {data.character.slug}")
        elif args.command == "teams":
            result = client.teams(allow_draft=args.allow_draft)
            print(client.data_dir / "teams.json")
            for item in result.skipped:
                print(f"skipped {item['path']}: {item['reason']}")
        elif args.command == "card":
            print(client.card(args.character, data=args.data, out=args.out,
                              allow_draft=args.allow_draft, exclude_extra=args.exclude_extra))
        elif args.command == "cards":
            result = client.cards(args.character, out=args.out, allow_draft=args.allow_draft,
                                  exclude_extra=args.exclude_extra)
            print(f"Rendered {len(result['cards'])}; skipped {len(result['skipped'])}; failed {len(result['failed'])}")
            _failures(result["failed"])
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


def _failures(items: list[dict]) -> None:
    if items:
        for item in items:
            print(json.dumps(item, ensure_ascii=False))
        raise SystemExit(f"{len(items)} operation(s) failed")


if __name__ == "__main__":
    main()
