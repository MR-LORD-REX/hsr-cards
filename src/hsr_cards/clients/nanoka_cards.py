"""Nanoka image delegates retaining stable public card signatures."""
from __future__ import annotations

from typing import Literal

from ..core.types import GameMode


class NanokaCardMethods:
    """Delegate non-player cards without touching the HoYoLAB session.

    These async operations load Nanoka catalogs/assets and optionally read/write
    rendered caches. None require a UID/cookies. Explicit proxy arguments override
    the facade proxy; cache roots retain the caller-relative defaults.
    """

    async def get_character_info(
        self,
        identifier: int | str,
        version: str | tuple[str, str] | list[str] | None = None,
        *,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
    ):
        """Render a Nanoka character info card for this client's locale.

        ``version`` follows Nanoka's rules: omit it for the newest published
        build, pass one build for a pinned card, or pass ``(from, to)`` for a
        comparison card. identifier accepts a numeric ID or published name;
        locale selects Nanoka's language (default en), cache_dir overrides provider
        data, and rendered_cache_dir overrides generated images. proxy overrides
        the facade proxy. use_rendered_cache=False disables image-cache IO.

        Return InfoCardResult (image, character, version, cache_path); loading,
        invalid identifiers/versions, and rendering errors propagate. No player
        data or credentials are accessed.
        """
        from ..renderer.nanoka import get_character_info as render_info

        return await render_info(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
        )

    async def get_LC_info(
        self,
        identifier: int | str,
        version: str | tuple[str, str] | list[str] | None = None,
        *,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
    ):
        """Render a level-80 Light Cone card with all S1-S5 values inline.

        Arguments and version comparisons follow get_character_info().
        """
        from ..renderer.nanoka import get_LC_info as render_lc

        return await render_lc(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
        )

    async def get_relic_info(
        self,
        identifier: int | str,
        version: str | tuple[str, str] | list[str] | None = None,
        *,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
    ):
        """Render relic set bonuses and every piece, including planar sets.

        Arguments and version comparisons follow get_character_info().
        """
        from ..renderer.nanoka import get_relic_info as render_relic

        return await render_relic(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
        )

    async def get_item_info(
        self,
        identifier: int | str,
        version: str | tuple[str, str] | list[str] | None = None,
        *,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
    ):
        """Render a Nanoka item card with its description and sources.

        Arguments and version comparisons follow get_character_info().
        """
        from ..renderer.nanoka import get_item_info as render_item

        return await render_item(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
        )

    async def get_character_skills(
        self,
        identifier: int | str,
        version: str | tuple[str, str] | list[str] | None = None,
        *,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
    ):
        """Render a Nanoka skills/eidolon sheet and its rich-message payloads.

        Arguments, cache/locale/proxy rules and exceptions follow
        get_character_info(). Return SkillsCardResult with image/version/character
        plus tables, dropdowns and sections; paired versions compare inline.
        """
        from ..renderer.nanoka import get_character_skills as render_skills

        return await render_skills(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
        )

    async def get_current_endgame_card(
        self,
        game_mode: GameMode = "MOC",
        floors: list[int] | tuple[int, ...] | int | None = None,
        *,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
        force_refresh: bool = False,
    ):
        """Render one Telegram-friendly info card per requested live endgame floor.

        MOC defaults to floors 11 and 12; PF and AS default to 3 and 4.
        AA cards are deferred and raise ``NotImplementedError``. floors accepts
        one number or a sequence. Return EndgameCardResult with ordered floor
        cards; absent live seasons/invalid floors raise ValueError.

        locale/cache/proxy options configure operation-owned clients; an injected
        Nanoka client retains its settings and lifecycle. force_refresh bypasses
        image-cache reads; use_rendered_cache=False disables image-cache IO.
        """
        from ..renderer.nanoka import get_current_endgame_card as render_endgame

        client_options = {}
        if getattr(self, "_nanoka", None) is not None:
            client_options["client"] = self._nanoka

        return await render_endgame(
            game_mode,
            floors,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
            force_refresh=force_refresh,
            **client_options,
        )

    async def get_next_endgame_card(
        self,
        game_mode: GameMode = "MOC",
        floors: list[int] | tuple[int, ...] | int | None = None,
        *,
        look_ahead: int | Literal["max"] = 1,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
        force_refresh: bool = False,
    ):
        """Render upcoming endgame cards after the live season.

        ``look_ahead=1`` returns one result; larger values or ``"max"`` return
        a list ordered by start time. Mode/floor defaults, injected-client
        ownership, and cache/locale/proxy rules match get_current_endgame_card().
        Invalid look-ahead/floors or missing upcoming seasons raise ValueError;
        AA still raises NotImplementedError. force_refresh bypasses cached images.
        """
        from ..renderer.nanoka import get_next_endgame_card as render_next_endgame

        client_options = {}
        if getattr(self, "_nanoka", None) is not None:
            client_options["client"] = self._nanoka

        return await render_next_endgame(
            game_mode,
            floors,
            look_ahead=look_ahead,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
            force_refresh=force_refresh,
            **client_options,
        )

    async def render_all_info(
        self,
        version: str | tuple[str, str] | list[str] | None = None,
        *,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
        concurrency: int = 4,
        include_beta: bool = True,
        identifiers: list[int | str] | tuple[int | str, ...] | None = None,
    ):
        """Render every character's info card concurrently.

        ``version`` uses the same single/comparison rules as
        :meth:`get_character_info`. Failures are collected per character in a
        ``BatchRenderResult`` and never cancel the other renders.
        """
        from ..renderer.nanoka import render_all_info as render_batch

        return await render_batch(
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
            concurrency=concurrency,
            include_beta=include_beta,
            identifiers=identifiers,
        )

    async def render_all_skills(
        self,
        version: str | tuple[str, str] | list[str] | None = None,
        *,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
        concurrency: int = 4,
        include_beta: bool = True,
        identifiers: list[int | str] | tuple[int | str, ...] | None = None,
    ):
        """Render every character's skills sheet concurrently.

        Uses the same failure and comparison semantics as
        :meth:`render_all_info`.
        """
        from ..renderer.nanoka import render_all_skills as render_batch

        return await render_batch(
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy if proxy is not None else getattr(self, "proxy", None),
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
            concurrency=concurrency,
            include_beta=include_beta,
            identifiers=identifiers,
        )
