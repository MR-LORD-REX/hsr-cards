from pathlib import Path
from typing import Any, Literal
from .renderer.hoyolab.anomaly import AnomalyRenderer
from .renderer.hoyolab.moc import MOCRenderer
from .renderer.hoyolab.finction import PFRenderer
from .renderer.hoyolab.shadow import ASRenderer
from .renderer.hoyolab.banners import BannerRenderer
from .renderer.hoyolab.events import EventsRenderer
from .renderer.hoyolab.endgame import EndgameRenderer
from .renderer.hoyolab.notes import NotesRenderer
from .renderer.hoyolab.currencywar import CurrencyWarRenderer, CurrencyWarResult
from .api.base_api import BaseAPI
from .utils.errors import HSR_Error
from .models.auth import Cookies
from .models.events import CalendarData, CalendarResponse
from .models.notes import NotesResponse, NotesData
from .models.currencywar import CurrencyWarData, CurrencyWarResponse 
from .builds import BUILD_METADATA_URL, update_build_assets
from .prydwen.codes import RedeemCode, fetch_redeem_codes
from .prydwen.tier_list import TierListData, fetch_tier_list
from .renderer.prydwen import TierListRenderer
from PIL import Image

class HonkaiStarrail:
    def __init__(
        self, uid: int | str, 
        cookie: Cookies | None = None,
        proxy: str | None = None
        ):
        self.uid = str(uid)
        self.cookie = cookie
        self.proxy = proxy
        cookie_dict = cookie.model_dump() if cookie is not None else None
        self.api = BaseAPI(
            self.uid, 
            cookie=cookie_dict,
            proxy=proxy
        )
        
    def _check_server(self):
        if self.uid.startswith("1") or self.uid.startswith("8"):
            return 'prod_official_asia'
        elif self.uid.startswith("6"):
            return 'prod_official_usa'
        elif self.uid.startswith("7"):
            return 'prod_official_eur'
        elif self.uid.startswith("5"):
            raise ValueError("HK,TW server is not supported yet.")
        else:
            raise ValueError("Invalid UID")
        
    async def __aenter__(self):
        await self.api.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.api.__aexit__(exc_type, exc_val, exc_tb)
    
    async def anomaly(self)-> Image.Image:
        try:
            server=self._check_server()
            if not server:
                raise ValueError("Invalid UID")
            data= await self.api._fetch_anomaly(server=server)
            async with AnomalyRenderer() as renderer:
                img=await renderer.render_anomaly(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render anomaly: {e}")
        
    async def MOC(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        try:
            server=self._check_server()
            if not server:
                raise ValueError("Invalid UID")
            data= await self.api._fetch_moc(schedule_type,server=server, need_all="true")
            async with MOCRenderer() as renderer:
                img=await renderer.render_moc(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render MOC: {e}")
    
    async def PF(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        try:
            server=self._check_server()
            if not server:
                raise ValueError("Invalid UID")
            data= await self.api._fetch_pf(schedule_type,server=server, need_all="true")
            async with PFRenderer() as renderer:
                img=await renderer.render_pf(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render PF: {e}")
        
    async def shadow(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        try:
            server=self._check_server()
            if not server:
                raise ValueError("Invalid UID")
            data= await self.api._fetch_as(schedule_type,server=server, need_all="true")
            async with ASRenderer() as renderer:
                img=await renderer.render_AS(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render shadow: {e}")

    async def _calendar(self) -> CalendarData:
        try:
            server = self._check_server()
            raw = await self.api._fetch_calendar(server=server)
            parsed = CalendarResponse.model_validate(raw)
            if parsed.retcode != 0 or parsed.data is None:
                raise HSR_Error(f"API error {parsed.retcode}: {parsed.message}")
            return parsed.data
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to fetch calendar: {e}")

    async def banners(self) -> Image.Image:
        try:
            cal = await self._calendar()
            async with BannerRenderer() as renderer:
                return await renderer.render_banners(cal)
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render banners: {e}")

    async def events(self) -> Image.Image:
        try:
            cal = await self._calendar()
            personalised = self.cookie is not None
            async with EventsRenderer() as renderer:
                return await renderer.render_events(
                    cal.act_list,
                    personalised=personalised,
                    now_ts=cal.now,
                )
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render events: {e}")

    async def endgame(self) -> Image.Image:
        try:
            cal = await self._calendar()
            personalised = self.cookie is not None
            async with EndgameRenderer() as renderer:
                return await renderer.render_endgame(
                    cal.challenge_list,
                    personalised=personalised,
                    now_ts=cal.now,
                )
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render endgame: {e}")

    async def notes(self, raw: bool = False) -> Image.Image | tuple[Image.Image, NotesData]:
        if self.cookie is None:
            raise HSR_Error("notes() requires user cookies — pass a Cookies object when creating HonkaiStarrail.")
        try:
            server   = self._check_server()
            raw_data = await self.api._fetch_notes(server=server)
            parsed   = NotesResponse.model_validate(raw_data)
            if parsed.retcode != 0 or parsed.data is None:
                raise HSR_Error(f"API error {parsed.retcode}: {parsed.message}")
            async with NotesRenderer() as renderer:
                img = renderer.render_notes(parsed.data)
            if raw:
                return img, parsed.data
            return img
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render notes: {e}")

    async def currency_war(
        self,
        index: int = 0,
        raw: bool = False,
    ) -> "CurrencyWarResult | tuple[CurrencyWarResult, CurrencyWarData]":
        """Render one Currency Wars run.

        ``index`` follows the API order (0 is the most recent run) and accepts
        negative values. The result exposes ``image``, ``current``, ``next()``,
        ``prev()`` and ``all`` for paging through the recent runs.
        """
        try:
            server = self._check_server()
            raw_data = await self.api._fetch_currency_war(server=server)
            parsed = CurrencyWarResponse.model_validate(raw_data)
            if parsed.retcode != 0 or parsed.data is None:
                raise HSR_Error(f"API error {parsed.retcode}: {parsed.message}")
            async with CurrencyWarRenderer() as renderer:
                result = await renderer.render_currency_war(parsed.data, index)
            if raw:
                return result, parsed.data
            return result
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render currency war: {e}")

    async def verify_cookies(self) -> bool:
        if self.cookie is None:
            return False
        try:
            server = self._check_server()
            raw    = await self.api._fetch_notes(server=server)
            return raw.get("retcode", -1) == 0
        except Exception:
            return False

    async def redeem_codes(self) -> list[RedeemCode]:
        """Fetch active HSR redeem codes and their rewards from Prydwen."""
        try:
            return await fetch_redeem_codes()
        except Exception as e:
            raise HSR_Error(f"Failed to fetch redeem codes: {e}")

    async def tier_list(
        self,
        game_mode: Literal["MOC", "PF", "AS"] = "MOC",
        raw: bool = False,
        *,
        timeout: float = 30.0,
    ) -> Image.Image | tuple[Image.Image, TierListData]:
        """Render Prydwen's MOC, PF, or AS list; optionally return parsed data.

        Defaults to Memory of Chaos. No player record is requested.
        This client's proxy also applies to Prydwen.
        """
        try:
            data = await fetch_tier_list(game_mode=game_mode, timeout=timeout, proxy=self.proxy)
            async with TierListRenderer(
                session=self.api.session, proxy=self.proxy, timeout=timeout
            ) as renderer:
                image = await renderer.render_tier_list(data)
            return (image, data) if raw else image
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render tier list: {e}") from e

    async def update_nanoka_assets(
        self,
        *,
        version: str | None = None,
        force: bool = False,
    ) -> None:
        """Refresh the Nanoka cache with the same rules as ``update_assets``.

        ``version`` switches to and refreshes one published build; ``force``
        revalidates the active build even when its manifest looks complete.
        """
        from .nanoka import NanokaClient

        async with NanokaClient() as nanoka:
            await nanoka.update_assets(version=version, force=force)

    async def character_build(
        self,
        identifier: int | str | None = None,
        url: bool = False,
        *,
        detailed: bool = False,
        name: str | None = None,
        element: str | None = None,
        path: str | None = None,
        rarity: int | None = None,
        released: bool | None = None,
        include_beta: bool = True,
        search: str | None = None,
        build_dir: str | Path | None = None,
        **filters: Any,
    ) -> Image.Image | str | list[Image.Image] | list[str] | None:
        """Return one clean image/link, or a list of detailed images/links.

        Detailed results contain the summary first, then its condition pages.
        Missing variants return `None`. Identifiers follow Nanoka's rules.
        """
        from .nanoka import NanokaClient


        async with NanokaClient(include_assets=False) as nanoka:
            return await nanoka.character_build(
                identifier,
                name=name,
                element=element,
                path=path,
                rarity=rarity,
                released=released,
                include_beta=include_beta,
                search=search,
                url=url,
                detailed=detailed,
                build_dir=build_dir,
                **filters,
            )

    async def update_builds(
        self,
        *,
        metadata_url: str = BUILD_METADATA_URL,
        build_dir: str | Path | None = None,
    ) -> int:
        """Refresh local community build images from the repository metadata."""
        return await update_build_assets(
            self.api.session,
            metadata_url=metadata_url,
            build_dir=build_dir,
        )

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
        comparison card.
        """
        from .renderer.nanoka import get_character_info as render_info

        return await render_info(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
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
        from .renderer.nanoka import get_LC_info as render_lc

        return await render_lc(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
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
        from .renderer.nanoka import get_relic_info as render_relic

        return await render_relic(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
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
        from .renderer.nanoka import get_item_info as render_item

        return await render_item(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
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
        """Render a Nanoka skills/eidolon sheet and its rich-message payloads."""
        from .renderer.nanoka import get_character_skills as render_skills

        return await render_skills(
            identifier,
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
        )

    async def get_current_endgame_card(
        self,
        game_mode: str = "MOC",
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

        MOC is supported first. Its default floors are 11 and 12; PF and AS
        default to 3 and 4, while AA uses every published floor.
        """
        from .renderer.nanoka import get_current_endgame_card as render_endgame

        return await render_endgame(
            game_mode,
            floors,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
            force_refresh=force_refresh,
        )

    async def get_next_endgame_card(
        self,
        game_mode: str = "MOC",
        floors: list[int] | tuple[int, ...] | int | None = None,
        *,
        look_ahead: int | str = 1,
        locale: str = "en",
        cache_dir: str | None = None,
        proxy: str | None = None,
        rendered_cache_dir: str | None = None,
        use_rendered_cache: bool = True,
        force_refresh: bool = False,
    ):
        """Render upcoming endgame cards after the live season.

        ``look_ahead=1`` returns one result; larger values or ``"max"`` return
        a list ordered by start time.
        """
        from .renderer.nanoka import get_next_endgame_card as render_next_endgame

        return await render_next_endgame(
            game_mode,
            floors,
            look_ahead=look_ahead,  # type: ignore[arg-type]
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
            force_refresh=force_refresh,
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
        from .renderer.nanoka import render_all_info as render_batch

        return await render_batch(
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
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
        from .renderer.nanoka import render_all_skills as render_batch

        return await render_batch(
            version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
            rendered_cache_dir=rendered_cache_dir,
            use_rendered_cache=use_rendered_cache,
            concurrency=concurrency,
            include_beta=include_beta,
            identifiers=identifiers,
        )
