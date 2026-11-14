"""Offline regression tests; no credentials or external services are needed."""

import asyncio
import json
import os
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import get_args, get_type_hints
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from PIL import Image

from hsr_cards import TierListData, fetch_tier_list, parse_tier_list, tier_list
from hsr_cards.prydwen.tier_list import _parse_dom
from hsr_cards.renderer.prydwen import TierListRenderer

HTML = (Path(__file__).parent / "fixtures" / "prydwen_tier_list.html").read_text(encoding="utf-8")


def _hydrated_html():
    """A small copy of the public payload schema, split across script tags."""
    characters = [
        {"slug": "acheron", "name": "Acheron", "rarity": "5", "element": "Lightning",
         "smallImage": "/images/acheron.webp", "isSpecialRating": False},
        {"slug": "arlan", "name": "Arlan", "rarity": "4", "element": "Lightning",
         "smallImage": "/images/arlan.webp", "isSpecialRating": False},
        {"slug": "trailblazer-harmony", "name": "Trailblazer - Harmony", "rarity": "5",
         "element": "Imaginary", "smallImage": "/images/trailblazer.webp", "isSpecialRating": True},
    ]
    ratings = [
        {"slug": "acheron", "category": "DPS", "moc_rating": 11, "pure_rating": 6, "apo_rating": 7,
         "moc_tags": "Debuff", "pure_tags": "Advance, Buff", "apo_tags": "Break",
         "moc_marks": "up, watch", "pure_marks": "down", "apo_marks": "new", "show": True},
        {"slug": "acheron", "category": "Specialist", "moc_rating": 10, "pure_rating": 9, "apo_rating": 8,
         "moc_tags": "Buff", "pure_tags": "Energy", "apo_tags": "Debuff", "show": True},
        {"slug": "arlan", "category": "DPS", "moc_rating": 4, "pure_rating": 4, "apo_rating": 4,
         "moc_special_rating": 1, "pure_special_rating": 1, "apo_special_rating": 1, "show": True},
        {"slug": "trailblazer-harmony", "category": "Amplifier", "moc_rating": 9, "pure_rating": 8,
         "apo_rating": 9, "moc_tags": "Break, Buff", "pure_tags": "Buff", "apo_tags": "Buff", "show": True},
        {"slug": "hidden", "category": "DPS", "moc_rating": 11, "pure_rating": 11, "apo_rating": 11,
         "show": False},
        {"slug": "unranked", "category": "DPS", "moc_rating": 0, "pure_rating": None, "apo_rating": 0},
    ]
    payload = json.dumps({"characters": characters, "ratings": ratings, "tierListConfig": {}})
    cut = len(payload) // 2
    scripts = '<script>self.__next_f.push(not_json)</script>'
    for chunk in (payload[:cut], payload[cut:]):
        scripts += '<script>self.__next_f.push(' + json.dumps([1, chunk]) + ')</script>'
    return HTML + scripts


HYDRATED_HTML = _hydrated_html()


def _find_character(data, slug, role_key="dps"):
    return next(
        (tier.name, character)
        for tier in data.tiers for role in tier.roles for character in role.characters
        if character.slug == slug and role.key == role_key
    )


class ParserTests(unittest.TestCase):
    def test_metadata_roles_and_group_order(self):
        data = parse_tier_list(HTML)
        self.assertIsInstance(data, TierListData)
        self.assertEqual((data.mode, data.mode_key), ("Memory of Chaos", "moc"))
        self.assertEqual(data.updated, "11/November/2026")
        self.assertEqual([r.key for r in data.roles], ["dps", "debuffer", "support", "sustain"])
        self.assertEqual([g.key for g in data.groups], ["apex", "forgotten"])
        self.assertEqual([(t.name, t.key) for t in data.tiers], [("T0", "t0"), ("T5", "t5")])
        self.assertEqual([len(r.characters) for r in data.tiers[0].roles], [1, 1, 0, 0])

    def test_character_details_and_relative_urls(self):
        data = parse_tier_list(HTML, source="https://example.test/star-rail/tier-list")
        character = data.tiers[0].roles[0].characters[0]
        self.assertEqual((character.name, character.slug), ("Acheron", "acheron"))
        self.assertEqual(character.icon_url, "https://example.test/images/acheron.webp")
        self.assertEqual((character.element, character.rarity, character.eidolon), ("Lightning", 5, "E0"))
        self.assertEqual(character.tags, ["Debuff", "Buff"])
        self.assertEqual(character.marks, ["up", "watchlist"])
        self.assertTrue(character.url.endswith("/characters/acheron"))

    def test_lazy_images_srcset_and_element_alt(self):
        data = parse_tier_list(HTML)
        self.assertEqual(data.tiers[0].roles[0].characters[0].icon_url,
                         data.tiers[0].roles[1].characters[0].icon_url)
        arlan = data.tiers[1].roles[0].characters[0]
        self.assertTrue(arlan.icon_url.endswith("/images/arlan.webp"))
        self.assertEqual((arlan.element, arlan.rarity, arlan.eidolon), ("Lightning", 4, "E6"))

    def test_missing_image_url_does_not_become_page_url(self):
        data = parse_tier_list(HTML.replace('src="/images/acheron.webp"', 'alt-other="none"'))
        self.assertEqual(data.tiers[0].roles[0].characters[0].icon_url, "")

    def test_mixed_text_remains_in_document_order(self):
        self.assertEqual(_parse_dom("Before <b>middle &amp; </b>after").text(), "Before middle & after")

    def test_tiers_before_any_group_are_preserved(self):
        html = HTML.replace('<div class="meta-line"><h5 class="meta-header apex">Apex characters</h5></div>', '')
        self.assertEqual(parse_tier_list(html).groups[0].key, "meta")
        self.assertEqual(len(parse_tier_list(html).tiers), 2)

    def test_blocked_and_empty_pages_raise(self):
        for html in ("<h1>Challenge</h1>", '<div class="custom-tier-list-hsr"></div>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_tier_list(html)


    def test_each_mode_uses_its_own_rankings_tags_and_marks(self):
        for mode, title, key, expected_tier, tags, marks in [
            ("MOC", "Memory of Chaos", "moc", "T0", ["Debuff"], ["up", "watchlist"]),
            ("PF", "Pure Fiction", "pure", "T3", ["Advance", "Buff"], ["down"]),
            ("AS", "Apocalyptic Shadow", "apo", "T2", ["Break"], ["new"]),
        ]:
            with self.subTest(mode=mode):
                data = parse_tier_list(HYDRATED_HTML, game_mode=mode)
                self.assertEqual((data.mode, data.mode_key), (title, key))
                tier, character = _find_character(data, "acheron")
                self.assertEqual(tier, expected_tier)
                self.assertEqual(character.tags, tags)
                self.assertEqual(character.marks, marks)
                self.assertEqual(sum(len(r.characters) for t in data.tiers for r in t.roles), 4)
                self.assertEqual(_find_character(data, "arlan")[1].eidolon, "E6")
                self.assertEqual(_find_character(data, "trailblazer-harmony", "support")[1].eidolon, "E6")
                self.assertEqual(_find_character(data, "arlan")[0], "T5")

    def test_multiple_roles_for_one_character_are_retained_per_mode(self):
        data = parse_tier_list(HYDRATED_HTML, game_mode="AS")
        self.assertEqual(_find_character(data, "acheron", "debuffer")[0], "T1.5")
        self.assertEqual(_find_character(data, "acheron", "dps")[0], "T2")

    def test_default_mode_and_case_insensitive_input(self):
        self.assertEqual(parse_tier_list(HYDRATED_HTML), parse_tier_list(HYDRATED_HTML, game_mode="MOC"))
        self.assertEqual(parse_tier_list(HYDRATED_HTML, game_mode="pf").mode_key, "pure")

    def test_missing_mode_data_never_substitutes_visible_moc(self):
        for mode in ("PF", "AS"):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "no embedded ratings"):
                parse_tier_list(HTML, game_mode=mode)

    def test_visible_selected_mode_without_hydration_is_supported(self):
        html = HTML.replace('option moc selected', 'option moc').replace('option pure', 'option pure selected')
        self.assertEqual(parse_tier_list(html, game_mode="PF").mode_key, "pure")

    def test_invalid_mode_rejected(self):
        for mode in ("SU", "", None):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "game_mode"):
                parse_tier_list(HYDRATED_HTML, game_mode=mode)


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.data = parse_tier_list(HTML)

    async def test_fetch_runs_parser_and_forwards_network_options(self):
        with patch("hsr_cards.prydwen.tier_list._fetch_html", return_value=HTML) as fetch:
            data = await fetch_tier_list(timeout=7, proxy="http://proxy.test")
        self.assertEqual(data.mode_key, "moc")
        fetch.assert_called_once_with(data.source, 7, "http://proxy.test")

    async def test_invalid_timeout_rejected(self):
        with self.assertRaises(ValueError):
            await fetch_tier_list(timeout=0)
        with self.assertRaises(ValueError):
            TierListRenderer(timeout=-1)

    async def test_render_deduplicates_portraits_and_draws_full_grid(self):
        renderer = TierListRenderer()
        portrait = Image.new("RGBA", (60, 80), (10, 90, 140, 255))
        with patch.object(renderer, "_fetch_image", AsyncMock(return_value=portrait)) as fetch:
            image = await renderer.render_tier_list(self.data)
        self.assertEqual(fetch.await_count, 2)  # Acheron appears in two roles.
        self.assertEqual(image.width, 1280)
        self.assertGreater(image.height, 600)  # Includes the second tier's wrapped tags.
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(image.getpixel((120, 250)), (10, 90, 140))
        self.assertEqual(image.getpixel((424, 250)), (10, 90, 140))
        self.assertEqual(image.getpixel((5, 250)), (244, 79, 79))
        self.assertEqual(image.getpixel((5, image.height - 70)), (114, 241, 243))
        stream = BytesIO()
        image.save(stream, format="PNG")
        stream.seek(0)
        with Image.open(stream) as reopened:
            self.assertEqual(reopened.size, image.size)

    async def test_missing_portraits_still_render_named_tiles(self):
        renderer = TierListRenderer()
        with patch.object(renderer, "_fetch_image", AsyncMock(return_value=None)):
            image = await renderer.render_tier_list(self.data)
        self.assertEqual(image.width, 1280)
        tile = image.crop((94, 214, 206, 326))
        self.assertGreater(len(tile.getcolors(20000)), 100)  # Text and badges on the gradient.

    async def test_network_and_invalid_images_use_placeholder(self):
        for fail in (aiohttp.ClientError("offline"), asyncio.TimeoutError(), None):
            response = MagicMock()
            response.raise_for_status.side_effect = fail
            response.read = AsyncMock(return_value=b"not an image")
            request = MagicMock()
            request.__aenter__ = AsyncMock(return_value=response)
            request.__aexit__ = AsyncMock(return_value=False)
            session = MagicMock()
            session.get.return_value = request
            async with TierListRenderer(session=session) as renderer:
                self.assertIsNone(await renderer._fetch_image("https://example.test/icon.webp"))
            session.close.assert_not_called()

    async def test_owned_session_closes(self):
        async with TierListRenderer() as renderer:
            session = renderer.session
            self.assertFalse(session.closed)
        self.assertTrue(session.closed)

    async def test_cancellation_is_not_swallowed(self):
        renderer = TierListRenderer()
        with patch.object(renderer, "_fetch_image", AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                await renderer.render_tier_list(self.data)

    async def test_standalone_returns_image_or_image_and_data(self):
        with patch("hsr_cards.renderer.prydwen.tier_list.fetch_tier_list", AsyncMock(return_value=self.data)), \
             patch.object(TierListRenderer, "_fetch_image", AsyncMock(return_value=None)):
            image = await tier_list()
            raw_image, data = await tier_list(raw=True)
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(raw_image.size, image.size)
        self.assertIs(data, self.data)

    async def test_main_client_forwards_proxy_and_preserves_session(self):
        # The existing player client imports cookie checks. Disable dotenv and
        # provide dummy values so this test never reads a .env or uses credentials.
        with patch("dotenv.load_dotenv", return_value=False), patch.dict(os.environ, {
            "ltoken_v2": "test", "ltuid_v2": "test", "default_uid": "800000000"
        }):
            from hsr_cards import HonkaiStarrail
        client = object.__new__(HonkaiStarrail)
        client.proxy = "http://proxy.test"
        client.api = SimpleNamespace(session=MagicMock())
        image = Image.new("RGB", (1, 1))
        with patch("hsr_cards.client.fetch_tier_list", AsyncMock(return_value=self.data)) as fetch, \
             patch.object(TierListRenderer, "render_tier_list", AsyncMock(return_value=image)):
            self.assertIs(await client.tier_list(), image)
            self.assertEqual(await client.tier_list(raw=True, timeout=9), (image, self.data))
        fetch.assert_awaited_with(game_mode="MOC", timeout=9, proxy="http://proxy.test")
        client.api.session.close.assert_not_called()
        self.assertEqual(get_args(get_type_hints(HonkaiStarrail.tier_list)["game_mode"]), ("MOC", "PF", "AS"))
        for mode in ("MOC", "PF", "AS"):
            data = parse_tier_list(HYDRATED_HTML, game_mode=mode)
            with patch("hsr_cards.client.fetch_tier_list", AsyncMock(return_value=data)) as fetch, \
                 patch.object(TierListRenderer, "render_tier_list", AsyncMock(return_value=image)) as render:
                self.assertEqual(await client.tier_list(mode, raw=True), (image, data))
                fetch.assert_awaited_once_with(game_mode=mode, timeout=30.0, proxy="http://proxy.test")
                render.assert_awaited_once_with(data)
        with patch("hsr_cards.client.fetch_tier_list", AsyncMock(side_effect=ValueError("bad HTML"))):
            from hsr_cards.utils.errors import HSR_Error
            with self.assertRaisesRegex(HSR_Error, "Failed to render tier list: bad HTML"):
                await client.tier_list()


    async def test_fetch_selects_requested_mode_from_one_page(self):
        for mode, key in (("MOC", "moc"), ("PF", "pure"), ("AS", "apo")):
            with patch("hsr_cards.prydwen.tier_list._fetch_html", return_value=HYDRATED_HTML):
                self.assertEqual((await fetch_tier_list(game_mode=mode)).mode_key, key)
        with patch("hsr_cards.prydwen.tier_list._fetch_html") as fetch:
            with self.assertRaisesRegex(ValueError, "game_mode"):
                await fetch_tier_list(game_mode="SU")
            fetch.assert_not_called()

    async def test_standalone_forwards_selected_mode(self):
        data = parse_tier_list(HYDRATED_HTML, game_mode="PF")
        image = Image.new("RGB", (1, 1))
        with patch("hsr_cards.renderer.prydwen.tier_list.fetch_tier_list", AsyncMock(return_value=data)) as fetch, \
             patch.object(TierListRenderer, "render_tier_list", AsyncMock(return_value=image)) as render:
            self.assertEqual(await tier_list("PF", raw=True), (image, data))
            fetch.assert_awaited_once_with(game_mode="PF", timeout=30.0, proxy=None)
            render.assert_awaited_once_with(data)


if __name__ == "__main__":
    unittest.main()
