"""Fictional, nonpersonal data and cached artwork for documentation renders.

Only image-loading boundaries are replaced. The public facade, validated
response models, layout code, typography and compositing all run normally.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from hsr_cards.providers.hoyolab.models import CalendarData, NotesData, CurrencyWarData

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / ".nanoka_cache" / "4.7.51" / "en" / "assets"
NOW = int(datetime(2026, 11, 15, 6, tzinfo=timezone.utc).timestamp())
TIME = {"year": 2026, "month": 11, "day": 15, "hour": 12, "minute": 30}


def art(relative):
    """Resolve a real cached image or fail instead of silently making a placeholder."""
    path = ASSETS / relative
    if not path.is_file():
        raise FileNotFoundError(f"Missing showcase artwork: {path}")
    return str(path)


def first_art(directory):
    paths = sorted((ASSETS / directory).rglob("*.webp"))
    if not paths:
        raise FileNotFoundError(f"Missing showcase artwork directory: {directory}")
    return str(paths[0])


def open_local(url):
    """Load local-only public artwork; no network request is allowed in these samples."""
    path = Path(url)
    if not path.is_file():
        raise FileNotFoundError(f"Sample artwork is not a cached local file: {url}")
    with Image.open(path) as image:
        return image.convert("RGBA")


@contextmanager
def local_artwork():
    """Patch renderer fetch boundaries while retaining all real rendering code."""
    from hsr_cards.renderer.hoyolab.anomaly import AnomalyRenderer
    from hsr_cards.renderer.hoyolab.finction import PFRenderer
    from hsr_cards.renderer.hoyolab.shadow import ASRenderer
    from hsr_cards.renderer.hoyolab.currencywar import CurrencyWarRenderer

    async def team_icon(url):
        return open_local(url)

    async def renderer_icon(self, url):
        return open_local(url) if url else None

    async def session_icon(session, url):
        return open_local(url) if url else None

    async def banner_icon(session, url, size=(72, 72)):
        return open_local(url).resize(size, Image.Resampling.LANCZOS)

    with ExitStack() as stack:
        stack.enter_context(patch("hsr_cards.renderer.common.team.get_icon", team_icon))
        for renderer in (AnomalyRenderer, PFRenderer, ASRenderer):
            stack.enter_context(patch.object(renderer, "get_icon", renderer_icon))
        stack.enter_context(patch.object(CurrencyWarRenderer, "_icon", renderer_icon))
        stack.enter_context(patch("hsr_cards.renderer.hoyolab.banners._fetch_image", banner_icon))
        for module in ("events", "endgame"):
            stack.enter_context(patch(f"hsr_cards.renderer.hoyolab.{module}._fetch", session_icon))
        yield


CHARACTERS = (
    (1308, "Acheron", "lightning"), (1307, "Black Swan", "wind"),
    (1209, "Yanqing", "ice"), (1212, "Jingliu", "ice"),
    (1309, "Robin", "physical"), (1008, "Arlan", "lightning"),
)


def avatars(offset=0):
    """Return a four-character sample team with cached public portraits."""
    return [{"element": element, "level": 80, "rank": 0, "icon": art(f"avatarshopicon/{identifier}.webp")}
            for identifier, _, element in (CHARACTERS * 2)[offset:offset + 4]]


def timed(start_days=-7, end_days=14):
    start, end = NOW + start_days * 86400, NOW + end_days * 86400
    return {"start_ts": str(start), "end_ts": str(end), "now": str(NOW),
            "start_time": datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.fromtimestamp(end, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}


def calendar():
    """Construct a validated example calendar; all dates and progress are fictional."""
    jade = {"item_id": 1, "name": "Stellar Jade", "icon": art("itemfigures/900001.webp"),
            "wiki_url": "", "num": 120, "rarity": "5"}
    credits = {**jade, "item_id": 2, "name": "Credit", "icon": art("itemfigures/2.webp"), "num": 20000, "rarity": "3"}
    pool_avatars = [
        {"item_id": str(identifier), "item_name": name, "icon_url": art(f"avatarshopicon/{identifier}.webp"),
         "damage_type": "1", "rarity": "5" if identifier != 1008 else "4", "avatar_base_type": "1",
         "is_forward": False, "wiki_url": "", "item_avatar_icon_path": art(f"avatarshopicon/{identifier}.webp"),
         "damage_type_name": element}
        for identifier, name, element in CHARACTERS[:4]
    ]
    avatar_pool = {"name": "Sample Character Warp", "type": "CardPoolRole", "avatar_list": pool_avatars,
                   "equip_list": [], "is_after_version": False, "time_info": timed(), "version": "4.7",
                   "id": "demo-character", "gacha_time_type": "GachaTimeTypeLimited"}
    equip = {"item_id": "23034", "item_name": "Along the Passing Shore", "item_url": art("lightconemediumicon/23034.webp"),
             "avatar_base_type": "1", "rarity": "5", "is_forward": False, "wiki_url": ""}
    equip_pool = {**avatar_pool, "name": "Sample Light Cone Warp", "type": "CardPoolEquipment", "avatar_list": [],
                  "equip_list": [equip], "id": "demo-equipment"}
    activities = []
    for index, (name, kind, progress, maximum) in enumerate((
        ("Sample Exploration Event", "ActivityTypeOther", 4, 8),
        ("Sample Double Rewards", "ActivityTypeDouble", 3, 12),
        ("Sample Login Rewards", "ActivityTypeSign", 3, 7),
    )):
        activities.append({"id": 100 + index, "version": "4.7", "name": name, "act_type": kind,
                           "act_status": "OtherActStatusUnFinish", "reward_list": [jade, credits],
                           "total_progress": maximum, "current_progress": progress, "time_info": timed(end_days=8 + index * 3),
                           "panel_id": index, "panel_desc": "Illustrative event", "strategy": "", "multiple_drop_type": 0,
                           "multiple_drop_type_list": [], "count_refresh_type": 0, "count_value": maximum,
                           "drop_multiple": 2 if index == 1 else 1, "is_after_version": False, "sort_weight": index,
                           "all_finished": False, "show_text": "Incomplete", "act_time_type": "ActivityTimeTypeLimited"})
    challenges = []
    for index, (name, kind, progress, maximum) in enumerate((
        ("Sample MOC Cycle", "ChallengeTypeChasm", 12, 12),
        ("Sample PF Cycle", "ChallengeTypeStory", 4, 4),
        ("Sample AS Cycle", "ChallengeTypeBoss", 3, 4),
        ("Sample AA Cycle", "ChallengeTypePeak", 3, 4),
    )):
        challenges.append({"group_id": 1000 + index, "name_mi18n": name, "challenge_type": kind,
                           "total_progress": maximum, "current_progress": progress, "status": "challengeStatusInProgress",
                           "time_info": timed(end_days=7 + index * 7), "reward_list": [{**jade, "num": 800}],
                           "show_text": f"{progress}/{maximum}", "challenge_peak_rank_icon_type": "",
                           "challenge_peak_rank_icon": "", "challenge_peak_start_version": "4.7", "extra_progress": 0})
    return CalendarData.model_validate({"avatar_card_pool_list": [avatar_pool], "equip_card_pool_list": [equip_pool],
                                        "act_list": activities, "challenge_list": challenges, "now": str(NOW), "cur_game_version": "4.7"})


def battle(mode):
    count = 12 if mode == "MOC" else 4
    floors = []
    buff = {"name_mi18n": "Sample blessing", "icon": art("skillicons/IconCriticalChance.webp")}
    # Fixed-height MOC and AS templates fit three complete records.
    floor_numbers = range(10, 13) if mode == "MOC" else range(2, 5) if mode == "AS" else range(1, count + 1)
    for floor in floor_numbers:
        nodes = [{"avatars": avatars(offset), "challenge_time": TIME, "score": 35000 if mode == "PF" else 3500, "buff": buff}
                 for offset in (0, 2)]
        floors.append({"name": f"{'Memory of Chaos' if mode == 'MOC' else 'Pure Fiction' if mode == 'PF' else 'Apocalyptic Shadow'} {floor:02d}",
                       "is_fast": False, "is_chaos": True, "round_num": 5, "star_num": 3,
                       "node_1": nodes[0], "node_2": nodes[1]})
    data = {"has_data": True, "star_num": count * 3, "battle_num": count + 2, "max_floor": str(count), "all_floor_detail": floors}
    if mode == "AS":
        data["groups"] = [{"upper_boss": {"name_mi18n": "Sample boss · first half", "icon": art("monstermiddleicon/Monster_3025010.webp")},
                           "lower_boss": {"name_mi18n": "Sample boss · second half", "icon": art("monstermiddleicon/Monster_4014030.webp")}}]
    return {"retcode": 0, "data": data}


def anomaly():
    icon = art("monstermiddleicon/Monster_3025010.webp")
    records = [{"has_challenge_record": True, "avatars": avatars(index), "star_num": 3,
                "challenge_time": TIME, "round_num": 4 + index} for index in range(3)]
    return {"retcode": 0, "data": {
        "challenge_peak_records": [{"group": {"begin_time": {**TIME, "day": 8}, "end_time": {**TIME, "day": 29}},
                                    "boss_info": {"name_mi18n": "Sample boss", "icon": icon},
                                    "mob_infos": [{"monster_name": f"Sample encounter {index + 1}", "monster_icon": art(f"monstermiddleicon/Monster_{identifier}.webp")}
                                                  for index, identifier in enumerate((2033010, 3013010, 4014030))],
                                    "boss_record": {"has_challenge_record": True, "round_num": 6, "star_num": 3,
                                                    "buff": {"name_mi18n": "Sample blessing", "icon": art("skillicons/IconCriticalChance.webp")},
                                                    "avatars": avatars()}, "mob_records": records}],
        "challenge_peak_best_record_brief": {"total_battle_num": 8, "mob_stars": 9, "boss_stars": 3, "challenge_peak_rank_icon": ""}
    }}


def notes():
    return NotesData.model_validate({
        "current_stamina": 180, "max_stamina": 300, "stamina_recover_time": 21600,
        "stamina_full_ts": NOW + 21600, "accepted_epedition_num": 4, "total_expedition_num": 4,
        "current_train_score": 300, "max_train_score": 500, "current_rogue_score": 10000,
        "max_rogue_score": 14000, "weekly_cocoon_cnt": 1, "weekly_cocoon_limit": 3,
        "current_reserve_stamina": 80, "is_reserve_stamina_full": False,
        "rogue_tourn_weekly_unlocked": True, "rogue_tourn_weekly_max": 1000, "rogue_tourn_weekly_cur": 600,
        "current_ts": NOW, "rogue_tourn_exp_is_full": False, "grid_fight_weekly_cur": 3000,
        "grid_fight_weekly_max": 6000, "period_score": 1200, "period_max_score": 2400,
    })


def currency_war():
    roles = [{"role_id": str(identifier), "avatar_id": str(identifier), "icon": art(f"avatarshopicon/{identifier}.webp"),
              "star": "3" if index == 0 else "2", "rarity": "5", "is_trial": False, "is_upgrade": False,
              "equip_list": [{"equip_id": "sample-equipment", "icon": first_art("gridfight/equipment"),
                              "category": "Equipment", "name": "Sample equipment"}],
              "pos": str(index), "role_type": "RoleTypeAvatar", "name": name, "is_projection": False}
             for index, (identifier, name, _) in enumerate(CHARACTERS)]
    icon = art("skillicons/IconAttack.webp")
    lineup = {"front_roles": roles[:4], "back_roles": roles[4:],
              "portal_list": [{"portal_id": "sample-portal", "name": "Sample environment", "icon": first_art("gridfight/portal")}],
              "augment_list": [{"augment_id": str(i), "name": f"Sample strategy {i + 1}", "quality": "3", "icon": first_art("gridfight/augmentbig")} for i in range(2)],
              "trait_list": [{"trait_id": "demo-trait", "icon": icon, "trait_count": "4", "trait_name": "Sample bond", "quality": "3", "trait_type": "TraitTypeRole"}],
              "damage_list": [{"damage_type": "DamageTypeRole", "id": role["role_id"], "damage": str(3600000 // (index + 1))} for index, role in enumerate(roles)],
              "spot_light_list": [{"spot_light_id": "sample-spotlight", "role_id": roles[0]["role_id"], "icon": icon,
                                   "name": "Sample plot armor", "role_icon": roles[0]["icon"]}]}
    brief = {"archive_time": "2026/11/15 12:30", "archive_time_ts": str(NOW), "archive_rank": "GridFightArchiveRankSSS",
             "remain_hp": "80", "total_coin": "248", "lineup_coin": "92",
             "division": {"icon": icon, "level": "5", "name_with_num": "Sample Division V", "name": "Sample Division"}}
    return CurrencyWarData.model_validate({"grid_fight_archive_list": [{"archive_type": "GridFightArchiveTypeNormal", "brief": brief, "lineup": lineup}]})


class SampleHoYoLAB:
    """Borrowed query client that supplies only explicit, fictional sample payloads."""
    uid = "documentation-sample"
    cookie = None

    async def get_anomaly(self):
        return anomaly()

    async def get_moc(self, schedule_type="1"):
        return battle("MOC")

    async def get_pf(self, schedule_type="1"):
        return battle("PF")

    async def get_shadow(self, schedule_type="1"):
        return battle("AS")

    async def get_calendar(self):
        return calendar()

    async def get_notes(self):
        return notes()

    async def get_currency_war(self):
        return currency_war()
