"""Python API for every operation exposed by the ``hsr-prydwen`` CLI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..builds import default_build_dir
from ..providers.prydwen.api import PrydwenAPIClient
from ..providers.prydwen.models import GameMode, RedeemCode, TierListData
from ..providers.prydwen.fetch import DEFAULT_CHROME, FetchConfig, PrydwenFetcher
from ..providers.prydwen.models import BuildCardData, ReviewStatus, TeamIndex
from ..providers.prydwen.assets import DEFAULT_NANOKA_VERSION, NanokaIndex
from ..providers.prydwen.paths import default_nanoka_cache, default_work_dir
from ..prydwen.builds.registry import approve_build, load_build, validate_build, write_build
from ..providers.prydwen.parsing.roster import load_raw_urls


class PrydwenClient:
    """Independent Prydwen queries and a cache-first build pipeline.

    Queries, ``urls`` and ``pull`` are async; parsing, validation, and rendering
    use local files synchronously.

    Parsing and rendering are local. Drafts, reports and contact sheets stay in
    ``work_dir``; approved renders are also published to ``build_dir/<slug>/``.
    Render once with each ``exclude_extra`` value to keep both variants.
    """

    def __init__(
        self, *, work_dir: str | Path | None = None, build_dir: str | Path | None = None,
        nanoka_cache: str | Path | None = None, nanoka_version: str = DEFAULT_NANOKA_VERSION,
        headed: bool = False, proxy: str | None = None, settle_ms: int = 5_000,
        transport: str = "http", refresh: bool = False, timeout_ms: int = 30_000,
        retries: int = 2, chrome: str | Path = DEFAULT_CHROME,
        api: PrydwenAPIClient | None = None,
    ):
        """Configure independent build and query access with an optional caller-owned API.

        work_dir contains drafts/reports; build_dir contains approved artifacts.
        Reads existing Nanoka catalogs for nanoka_version, but creates no directories.
        transport selects HTTP or explicit browser collection; timeouts are milliseconds
        for builds. Injected api objects are never closed by this client."""
        self.api = api if api is not None else PrydwenAPIClient(proxy=proxy)
        self._owns_api = api is None
        self._closed = False
        self.work_dir = Path(work_dir).expanduser().resolve() if work_dir is not None else default_work_dir()
        self.build_dir = Path(build_dir).expanduser().resolve() if build_dir is not None else default_build_dir()
        self.raw_dir = self.work_dir / "raw"
        self.data_dir = self.work_dir / "data"
        self.cards_dir = self.work_dir / "cards"
        self.urls_path = self.work_dir / "rawUrls.json"
        self.nanoka = NanokaIndex(
            cache_dir=Path(nanoka_cache).expanduser() if nanoka_cache is not None else default_nanoka_cache(),
            version=nanoka_version,
        )
        self.fetch_config = FetchConfig(
            raw_dir=self.raw_dir, chrome=Path(chrome), headless=not headed,
            proxy=proxy, settle_ms=settle_ms, transport=transport, refresh=refresh,
            timeout_ms=timeout_ms, retries=retries,
        )


    def _fetcher(self) -> PrydwenFetcher:
        return self.api.build_fetcher(self.fetch_config, nanoka=self.nanoka)

    @staticmethod
    def _characters(character: str | Iterable[str] | None) -> list[str]:
        if character is None:
            return []
        return [character] if isinstance(character, str) else list(character)

    def _paths(self, directory: Path, suffix: str, character=None) -> list[Path]:
        names = self._characters(character)
        if names:
            paths = [directory / f"{self._slug(name)}{suffix}" for name in names]
            missing = [str(path) for path in paths if not path.is_file()]
            if missing:
                raise FileNotFoundError("Missing builds: " + ", ".join(missing))
            return paths
        return sorted(path for path in directory.glob(f"*{suffix}")
                      if path.stem not in {"teams", "characters-index"} and "." not in path.stem)

    def _slug(self, value: str) -> str:
        from ..builds import _filename
        value = _filename(value)
        if self.urls_path.is_file():
            for entry in load_raw_urls(self.urls_path):
                if value.casefold() in {entry.slug.casefold(), entry.name.casefold(), str(entry.nanoka_id)}:
                    return _filename(entry.slug)
        return value

    async def urls(self) -> Path:
        """Fetch the character roster and write rawUrls.json under work_dir.

        Uses the configured cache/transport and closes the operation-owned fetcher.
        Network, parsing, and filesystem failures propagate."""
        async with self._fetcher() as fetcher:
            return await fetcher.raw_urls()

    async def pull(self, character: str | Iterable[str] | None = None, *, concurrency: int = 2) -> dict:
        """Cache selected character HTML with bounded concurrent fetches.

        character accepts one name/slug, an iterable, or None for the saved roster.
        Returns paths plus cached/downloaded counts and per-character failures.
        Unknown selections or an empty roster raise ValueError; missing manifests raise."""
        entries = load_raw_urls(self.urls_path)
        wanted = {self._slug(value) for value in self._characters(character)}
        if wanted:
            matched = [entry for entry in entries if entry.slug in wanted]
            missing = wanted - {entry.slug for entry in matched}
            if missing:
                raise ValueError(f"Unknown characters: {sorted(missing)}")
            entries = matched
        if not entries:
            raise ValueError("No matching characters in rawUrls.json")
        async with self._fetcher() as fetcher:
            paths = await fetcher.all(entries, concurrency=concurrency)
        return {"paths": paths, "cached": fetcher.cached, "downloaded": fetcher.downloaded,
                "failed": fetcher.failures}

    def parse(self, character: str | Iterable[str] | None = None) -> dict:
        """Parse selected cached HTML into draft build JSON without network access.

        character accepts one name/slug, an iterable, or None for all raw snapshots.
        Returns written paths and per-file failures. Missing snapshots raise
        FileNotFoundError and unavailable Nanoka catalogs raise ValueError."""
        from ..providers.prydwen.parsing.builds import parse_html
        paths = self._paths(self.raw_dir, ".html", character)
        if not paths:
            raise FileNotFoundError(f"No raw character HTML found in {self.raw_dir}")
        if not self.nanoka.available:
            raise ValueError(f"Nanoka catalog unavailable at {self.nanoka.cache_dir}")
        result = {"paths": [], "failed": []}
        for path in paths:
            try:
                meta_path = path.with_suffix(".meta.json")
                meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
                source = meta.get("url") or f"https://www.prydwen.gg/star-rail/characters/{path.stem}"
                data = parse_html(path.read_bytes().decode("utf-8"), source_url=source,
                                  nanoka=self.nanoka, raw_path=path)
                result["paths"].append(write_build(data, self.data_dir / f"{path.stem}.json"))
            except Exception as exc:
                result["failed"].append({"file": str(path), "error": str(exc)})
        return result

    def validate(self, files: str | Path | Iterable[str | Path]) -> list[dict]:
        """Read one or several build JSON files and return review status and validation problems.

        Performs local catalog/file checks without changing approval state. Missing
        files and malformed build JSON raise instead of becoming per-file failures."""
        paths = [files] if isinstance(files, (str, Path)) else list(files)
        results = []
        for path in paths:
            data = load_build(Path(path))
            results.append({"file": str(path), "status": data.review.status.value,
                            "problems": validate_build(data, self.nanoka)})
        return results

    def approve(
        self, character: str | None = None, *, file: str | Path | None = None,
        reviewer: str = "manual", note: str | None = None,
    ) -> BuildCardData:
        """Validate and explicitly approve one character or file, recording reviewer and note.

        Updates the selected draft JSON and returns BuildCardData. Missing selection
        or failed validation raises ValueError; missing files propagate filesystem errors."""
        if file is None and character is None:
            raise ValueError("Supply a character or file")
        path = Path(file) if file is not None else self.data_dir / f"{self._slug(character)}.json"
        return approve_build(path, reviewer=reviewer, note=note, nanoka=self.nanoka)

    def approve_all(
        self, character: str | Iterable[str] | None = None, *, reviewer: str = "manual",
        note: str | None = None,
    ) -> dict:
        """Approve selected valid drafts, retaining and reporting individual failed entries.

        character is a name/slug, iterable, or None for every draft. Returns approved
        models and per-file failures; missing requested files or an empty data tree raises."""
        paths = self._paths(self.data_dir, ".json", character)
        if not paths:
            raise FileNotFoundError(f"No character JSON found in {self.data_dir}")
        result = {"approved": [], "failed": []}
        for path in paths:
            try:
                result["approved"].append(self.approve(file=path, reviewer=reviewer, note=note))
            except Exception as exc:
                result["failed"].append({"file": str(path), "error": str(exc)})
        return result

    def teams(self, *, allow_draft: bool = False) -> TeamIndex:
        """Write and return the cross-character team index from local build JSON.

        Drafts are excluded unless allow_draft=True. Writes data_dir/teams.json;
        no requests or approvals occur."""
        from ..prydwen.builds.teams import build_team_index
        index = build_team_index(self.data_dir, nanoka=self.nanoka, include_drafts=allow_draft)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "teams.json").write_text(index.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return index

    def card(
        self, character: str | None = None, *, data: str | Path | None = None,
        out: str | Path | None = None, allow_draft: bool = False, exclude_extra: bool = True,
    ) -> Path:
        """Render one local build and publish approved artifacts, returning the PNG path.

        Supply character or data. Drafts require allow_draft=True. exclude_extra=True
        produces the clean card; False adds detailed conditions. out and working
        reports must remain outside build_dir. Invalid approved builds raise ValueError.
        Writes local images/reports and, for approved builds, published asset metadata."""
        from ..prydwen.builds.publish import publish_build
        from ..renderer.prydwen.builds.card import render_card
        if data is None and character is None:
            raise ValueError("Supply a character or data file")
        source = Path(data) if data is not None else self.data_dir / f"{self._slug(character)}.json"
        model = load_build(source)
        approved = model.review.status == ReviewStatus.APPROVED
        if not approved and not allow_draft:
            raise ValueError(f"{source} is a draft; approve it or use allow_draft=True")
        problems = validate_build(model, self.nanoka)
        if approved and problems:
            raise ValueError("Approved build no longer validates:\n- " + "\n- ".join(problems))
        slug = self._slug(model.character.slug)
        destination = Path(out) if out is not None else self.cards_dir / f"{slug}.png"
        if destination.resolve().is_relative_to(self.build_dir.resolve()):
            raise ValueError("Render working files outside build_dir; approved PNGs are published automatically")
        report_dir = self.work_dir / "reports"
        image = render_card(model, destination, nanoka=self.nanoka,
                            exclude_extra=exclude_extra, report_dir=report_dir)
        if approved:
            return publish_build(model, image, report_dir / f"{image.stem}.render.json", self.build_dir)
        return image

    def cards(
        self, character: str | Iterable[str] | None = None, *, out: str | Path | None = None,
        allow_draft: bool = False, exclude_extra: bool = True,
    ) -> dict:
        """Render selected local builds and return cards, contact sheets, and per-file failures.

        character is a name/slug, iterable, or None for all JSON builds. Draft handling
        and exclude_extra match card(). Writes working outputs outside build_dir and
        publishes approved images. Empty input or output inside build_dir raises."""
        from ..prydwen.builds.batch import render_batch
        paths = self._paths(self.data_dir, ".json", character)
        if not paths:
            raise FileNotFoundError(f"No character JSON found in {self.data_dir}")
        output = Path(out) if out is not None else self.cards_dir
        if output.resolve().is_relative_to(self.build_dir.resolve()):
            raise ValueError("Batch working files must be outside build_dir")
        return render_batch(paths, output,
                            nanoka=self.nanoka, allow_draft=allow_draft,
                            exclude_extra=exclude_extra, client=self)

    async def get_redeem_codes(self, *, timeout: float = 30.0) -> list[RedeemCode]:
        """Fetch active codes and reward models; timeout is measured in seconds.

        Performs HTTP in a worker; dependency and HTTP failures propagate.
        """
        return await self.api.get_redeem_codes(timeout=timeout)

    async def get_tier_list(
        self, *, game_mode: GameMode = "MOC", timeout: float = 30.0,
        proxy: str | None = None,
    ) -> TierListData:
        """Fetch MOC/PF/AS ranking data with case-insensitive mode aliases.

        A per-call proxy overrides the API default. Invalid modes, nonpositive
        timeouts, missing rankings, and HTTP errors raise before returning data.
        """
        return await self.api.get_tier_list(game_mode=game_mode, timeout=timeout, proxy=proxy)

    async def close(self) -> None:
        """Close an internally constructed API client, leaving injected APIs open."""
        if self._owns_api and not self._closed:
            await self.api.close()
            self._closed = True

    async def __aenter__(self) -> "PrydwenClient":
        """Return the client; transports open only during explicit fetch operations."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Close owned API resources when leaving an async context."""
        await self.close()
