#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор синтетических данных для схемы видеоигр.

Ничего не качает из сети: все значения выдумываются локально.
Формат CSV, порядок колонок и папка вывода совпадают с generate_data.py,
поэтому insert_data.sql работает без изменений.

Соблюдаются ограничения из define_restrictions.sql:
  * company.name уникально, NOT NULL поля заполнены;
  * game.users_score 0..100, age_rating in (0,3,7,12,16,18),
    first_release_date >= 1958-10-01;
  * platform.type из допустимого списка;
  * game_release.region in (NA, EU, JP, WW), role in (developer,
    publisher, porting_studio), пара (game, company, platform, region, role)
    уникальна;
  * все внешние ключи ссылаются на существующие строки, даты потомков
    не раньше дат родителей.

Пример: python3 generate_fake_data.py --companies 1200 --games 6000
"""

import argparse
import csv
import datetime
import os
import random

MIN_DATE = datetime.date(1958, 10, 1)
MAX_DATE = datetime.date(2025, 6, 30)

COLUMNS = {
    "company": ["id", "name", "country", "city", "founded_year"],
    "game_engine": ["id", "name", "version", "company_id", "release_date", "is_active"],
    "platform": ["id", "name", "short_name", "type", "generation", "release_date", "company_id"],
    "genre": ["id", "name", "parent_id"],
    "game": ["id", "title", "users_score", "age_rating", "first_release_date", "game_engine_id"],
    "game_genre": ["game_id", "genre_id"],
    "game_release": ["game_id", "platform_id", "company_id", "release_date", "region", "role"],
}
ORDER = ["company", "game_engine", "platform", "genre", "game", "game_genre", "game_release"]

REGIONS = ["NA", "EU", "JP", "WW"]
ROLES = ["developer", "publisher", "porting_studio"]
PLATFORM_TYPES = ["console", "handheld", "computer", "mobile", "vr", "cloud", "arcade"]
AGE_RATINGS = [0, 3, 7, 12, 16, 18]

CITIES = {
    "Japan": ["Tokyo", "Kyoto", "Osaka", "Sapporo", "Nagoya", "Fukuoka", "Yokohama"],
    "USA": ["San Francisco", "Seattle", "Austin", "Los Angeles", "Boston", "Chicago", "Irvine"],
    "Canada": ["Montreal", "Vancouver", "Toronto", "Quebec", "Edmonton"],
    "United Kingdom": ["London", "Guildford", "Brighton", "Manchester", "Edinburgh", "Leeds"],
    "France": ["Paris", "Lyon", "Montpellier", "Bordeaux", "Annecy"],
    "Germany": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt"],
    "Sweden": ["Stockholm", "Malmo", "Gothenburg", "Skovde"],
    "Poland": ["Warsaw", "Krakow", "Wroclaw", "Gdansk"],
    "Russia": ["Moscow", "Saint Petersburg", "Novosibirsk", "Kazan"],
    "South Korea": ["Seoul", "Busan", "Daegu"],
    "China": ["Shanghai", "Beijing", "Shenzhen", "Chengdu"],
    "Finland": ["Helsinki", "Tampere", "Espoo"],
    "Netherlands": ["Amsterdam", "Utrecht", "Eindhoven"],
    "Spain": ["Madrid", "Barcelona", "Valencia"],
    "Italy": ["Milan", "Rome", "Turin"],
    "Australia": ["Melbourne", "Sydney", "Brisbane"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Curitiba"],
    "Czech Republic": ["Prague", "Brno", "Ostrava"],
    "Ukraine": ["Kyiv", "Lviv", "Kharkiv"],
    "Denmark": ["Copenhagen", "Aarhus"],
}

COMPANY_FIRST = [
    "Nova", "Pixel", "Iron", "Crimson", "Silver", "Vector", "Lunar", "Quantum", "Ember",
    "Frost", "Hollow", "Bright", "Granite", "Neon", "Onyx", "Phoenix", "Radiant", "Shadow",
    "Storm", "Titan", "Vivid", "Wild", "Zenith", "Amber", "Basalt", "Cobalt", "Delta",
    "Echo", "Falcon", "Golden", "Harbor", "Indigo", "Jade", "Kestrel", "Lantern", "Mirage",
    "North", "Orbit", "Prism", "Quartz", "Raven", "Solar", "Thunder", "Umbra", "Velvet",
    "Willow", "Xenon", "Yonder", "Zephyr", "Anvil", "Beacon", "Cinder", "Drift", "Elder",
    "Fable", "Glimmer", "Hyper", "Ivory", "Junction", "Kinetic", "Lucid", "Meridian",
    "Nimbus", "Obsidian", "Paragon", "Quiet", "Ridge", "Summit", "Tundra", "Union",
]
COMPANY_SECOND = [
    "Wolf", "Fox", "Bear", "Dragon", "Hawk", "Lion", "Owl", "Whale", "Serpent", "Tiger",
    "Anchor", "Bridge", "Canyon", "Forest", "Garden", "Harbor", "Island", "Lake", "Mountain",
    "River", "Valley", "Field", "Tower", "Gate", "Road", "Star", "Moon", "Sun", "Comet",
    "Machine", "Engine", "Circuit", "Signal", "Cipher", "Pixel", "Byte", "Code", "Logic",
]
COMPANY_SUFFIX = [
    "Studios", "Interactive", "Games", "Entertainment", "Soft", "Digital", "Works",
    "Labs", "Team", "Collective", "Media", "Productions", "Systems", "House", "Arts",
    "Technologies", "Group", "Workshop", "Forge",
]
COMPANY_LEGAL = ["", "", "", "", " Inc.", " Ltd.", " GmbH", " S.A.", " Co.", " AB", " LLC"]

ENGINE_SUFFIX = [
    "Engine", "Forge", "Core", "Frame", "Nexus", "Works", "Runtime", "Foundry", "Matrix",
    "Kernel", "Studio", "Toolkit", "Pipeline", "Canvas", "Render", "Sandbox",
]
ENGINE_ROOT = [
    "Aether", "Bolt", "Cascade", "Dusk", "Ether", "Flux", "Glow", "Helix", "Ignis",
    "Juno", "Kilo", "Lumen", "Mesa", "Nimble", "Orion", "Pulse", "Quasar", "Rift",
    "Spire", "Tempest", "Ultra", "Vortex", "Warp", "Xeno", "Yield", "Zodiac", "Apex",
    "Blaze", "Chroma", "Dynamo", "Element", "Fusion", "Gravity", "Horizon", "Impulse",
    "Vanta", "Stratus", "Cinder", "Torrent", "Prime",
]

PLATFORM_MODEL = [
    "Vision", "Master", "Arcade", "Fusion", "Prime", "Turbo", "Micro", "Mega", "Ultra",
    "Nova", "Delta", "Sigma", "Orbit", "Vertex", "Pocket", "Cube", "Wave", "Pulse",
    "Core", "Edge", "Vista", "Halo", "Nexus", "Zen", "Flux", "Astro", "Quantum",
]
PLATFORM_LINE = [
    "Station", "System", "Box", "Deck", "Pad", "Player", "Console", "Portable", "Terminal",
    "Machine", "Drive", "Cabinet", "Gear", "Link", "Screen", "Cloud", "Stream",
]

GENRE_TREE = {
    "Action": ["Platformer", "Beat 'em up", "Hack and slash", "Stealth", "Fighting",
               "Battle royale", "Character action"],
    "Shooter": ["First-person shooter", "Third-person shooter", "Tactical shooter",
                "Arena shooter", "Shoot 'em up", "Hero shooter"],
    "Adventure": ["Point-and-click", "Visual novel", "Interactive fiction",
                  "Survival horror", "Walking simulator", "Text adventure"],
    "Role-playing": ["Action RPG", "JRPG", "Tactical RPG", "MMORPG", "Roguelike",
                     "Roguelite", "Dungeon crawler", "CRPG"],
    "Strategy": ["Real-time strategy", "Turn-based strategy", "4X", "Tower defense",
                 "Grand strategy", "Auto battler", "MOBA"],
    "Simulation": ["Life simulation", "Vehicle simulation", "Flight simulator",
                   "Farming simulation", "Business simulation", "Colony simulation"],
    "Sports": ["Football", "Basketball", "Hockey", "Tennis", "Golf", "Extreme sports",
               "Wrestling"],
    "Racing": ["Arcade racing", "Simulation racing", "Kart racing", "Rally", "Combat racing"],
    "Puzzle": ["Match three", "Physics puzzle", "Logic puzzle", "Hidden object",
               "Puzzle-platformer", "Sokoban"],
    "Music": ["Rhythm", "Music creation", "Dance"],
    "Sandbox": ["Survival", "Crafting", "City builder", "Open world"],
    "Casual": ["Party", "Board game", "Card game", "Educational", "Idle"],
    "Horror": ["Psychological horror", "Action horror", "Cosmic horror"],
    "Indie": ["Art game", "Experimental", "Metroidvania"],
}

TITLE_ADJ = [
    "Broken", "Eternal", "Silent", "Crimson", "Frozen", "Hidden", "Last", "Lost", "Rising",
    "Savage", "Twisted", "Ancient", "Burning", "Dark", "Distant", "Endless", "Fallen",
    "Forgotten", "Golden", "Hollow", "Infinite", "Iron", "Midnight", "Northern", "Pale",
    "Sacred", "Scarlet", "Shattered", "Silver", "Sunken", "Wandering", "Wild", "Deep",
    "Neon", "Quiet", "Restless", "Velvet", "Feral", "Solar", "Hungry",
]
TITLE_NOUN = [
    "Empire", "Legacy", "Kingdom", "Odyssey", "Chronicles", "Frontier", "Horizon", "Legion",
    "Requiem", "Sanctuary", "Tempest", "Uprising", "Vanguard", "Voyage", "Citadel", "Covenant",
    "Descent", "Dominion", "Echoes", "Exodus", "Genesis", "Harvest", "Inferno", "Journey",
    "Labyrinth", "Machine", "Nomad", "Oracle", "Paradox", "Protocol", "Reckoning", "Rebellion",
    "Sentinel", "Spiral", "Sunrise", "Threshold", "Tides", "Tower", "Warden", "Wasteland",
    "Garden", "Compass", "Lantern", "Signal", "Circuit", "Mirage", "Anthem", "Verdict",
]
TITLE_PLACE = [
    "Arcadia", "Valoria", "Kessar", "Norhaven", "Ashfall", "Ironvale", "Duskmere", "Solara",
    "Kyros", "Veridia", "Zephyros", "Marrow", "Halcyon", "Thornwick", "Emberfall", "Nyxara",
    "Caldera", "Wintermoor", "Sablefen", "Aureon",
]
TITLE_SUB = [
    "Director's Cut", "Definitive Edition", "Remastered", "Redux", "Reborn", "Awakening",
    "Origins", "Revelations", "Uprising", "Aftermath", "Homecoming", "Second Wind",
    "The Long Night", "Cold Iron", "Broken Chains", "New Dawn",
]
ROMAN = ["II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def random_date(rnd, start, end):
    """Случайная дата в отрезке [start, end]."""
    if end < start:
        start, end = end, start
    delta = (end - start).days
    return start + datetime.timedelta(days=rnd.randint(0, delta))


def year_start(year):
    return datetime.date(year, 1, 1)


def clamp_date(d):
    if d < MIN_DATE:
        return MIN_DATE
    if d > MAX_DATE:
        return MAX_DATE
    return d


def unique_name(rnd, used, make):
    """Дергает make() пока имя не окажется новым, потом добавляет уточнение."""
    for _ in range(40):
        name = make()
        if name not in used:
            used.add(name)
            return name
    n = 2
    base = make()
    while "%s %d" % (base, n) in used:
        n += 1
    name = "%s %d" % (base, n)
    used.add(name)
    return name


def gen_companies(rnd, count):
    rows = []
    used = set()
    countries = list(CITIES)

    def make():
        style = rnd.random()
        if style < 0.45:
            base = "%s %s" % (rnd.choice(COMPANY_FIRST), rnd.choice(COMPANY_SUFFIX))
        elif style < 0.8:
            base = "%s %s %s" % (rnd.choice(COMPANY_FIRST), rnd.choice(COMPANY_SECOND),
                                 rnd.choice(COMPANY_SUFFIX))
        else:
            base = "%s%s %s" % (rnd.choice(COMPANY_FIRST), rnd.choice(COMPANY_SECOND).lower(),
                                rnd.choice(COMPANY_SUFFIX))
        return base + rnd.choice(COMPANY_LEGAL)

    for i in range(1, count + 1):
        country = rnd.choice(countries)
        city = rnd.choice(CITIES[country])
        # город иногда неизвестен - колонка nullable
        if rnd.random() < 0.05:
            city = None
        founded = rnd.randint(1958, 2022)
        rows.append([i, unique_name(rnd, used, make), country, city, founded])
    return rows


def gen_engines(rnd, count, companies):
    rows = []
    used = set()

    def make():
        if rnd.random() < 0.55:
            return "%s %s" % (rnd.choice(ENGINE_ROOT), rnd.choice(ENGINE_SUFFIX))
        return "%s%s" % (rnd.choice(ENGINE_ROOT), rnd.choice(ENGINE_SUFFIX))

    for i in range(1, count + 1):
        comp = rnd.choice(companies)
        # движок не может выйти раньше основания компании
        low = max(comp[4], 1975)
        released = random_date(rnd, year_start(low), MAX_DATE)
        version = "%d.%d" % (rnd.randint(1, 9), rnd.randint(0, 20))
        if rnd.random() < 0.2:
            version += ".%d" % rnd.randint(0, 40)
        is_active = released.year >= 2012 or rnd.random() < 0.2
        rows.append([i, unique_name(rnd, used, make), version, comp[0],
                     released.isoformat(), "true" if is_active else "false"])
    return rows


def short_of(rnd, name, used):
    """Аббревиатура вида PSX / NVS-2 из слов названия."""
    letters = "".join(w[0] for w in name.split() if w[:1].isalnum()).upper()
    base = (letters or name[:3].upper())[:5]
    cand = base
    n = 2
    while cand in used:
        cand = "%s-%d" % (base, n)
        n += 1
    used.add(cand)
    return cand


def gen_platforms(rnd, count, companies):
    rows = []
    used_names = set()
    used_short = set()
    vendors = rnd.sample(companies, min(len(companies), max(30, count // 6)))

    for i in range(1, count + 1):
        comp = rnd.choice(vendors)
        ptype = rnd.choices(
            PLATFORM_TYPES,
            weights=[30, 18, 20, 12, 8, 5, 7],
        )[0]

        def make():
            head = comp[1].split()[0]
            style = rnd.random()
            if style < 0.4:
                return "%s %s" % (head, rnd.choice(PLATFORM_LINE))
            if style < 0.75:
                return "%s %s %s" % (head, rnd.choice(PLATFORM_LINE), rnd.choice(PLATFORM_MODEL))
            return "%s %s %d" % (head, rnd.choice(PLATFORM_MODEL), rnd.randint(1, 9))

        name = unique_name(rnd, used_names, make)

        # у молодых типов платформ не бывает ранних дат
        low = max(comp[4], 1972)
        if ptype == "mobile":
            low = max(low, 1997)
        elif ptype == "cloud":
            low = max(low, 2009)
        elif ptype == "vr":
            low = max(low, 1991)
        released = random_date(rnd, year_start(low), MAX_DATE)

        if ptype in ("console", "handheld"):
            generation = min(9, max(1, (released.year - 1972) // 6 + 1))
        else:
            generation = None
        rows.append([i, name, short_of(rnd, name, used_short), ptype, generation,
                     released.isoformat(), comp[0]])
    return rows


def gen_genres():
    """Двухуровневое дерево жанров: корневые + поджанры."""
    rows = []
    next_id = 1
    for root, children in GENRE_TREE.items():
        root_id = next_id
        next_id += 1
        rows.append([root_id, root, None])
        for child in children:
            rows.append([next_id, child, root_id])
            next_id += 1
    return rows


def gen_games(rnd, count, engines):
    rows = []
    used = set()
    engine_date = {e[0]: datetime.date.fromisoformat(e[4]) for e in engines}
    engine_ids = list(engine_date)

    def make():
        style = rnd.random()
        if style < 0.3:
            title = "%s %s" % (rnd.choice(TITLE_ADJ), rnd.choice(TITLE_NOUN))
        elif style < 0.5:
            title = "%s of %s" % (rnd.choice(TITLE_NOUN), rnd.choice(TITLE_PLACE))
        elif style < 0.65:
            title = "%s: %s" % (rnd.choice(TITLE_PLACE), rnd.choice(TITLE_NOUN))
        elif style < 0.8:
            title = "The %s %s" % (rnd.choice(TITLE_ADJ), rnd.choice(TITLE_NOUN))
        else:
            title = "%s %s" % (rnd.choice(TITLE_NOUN), rnd.choice(TITLE_PLACE))
        if rnd.random() < 0.12:
            title += " " + rnd.choice(ROMAN)
        if rnd.random() < 0.1:
            title += ": " + rnd.choice(TITLE_SUB)
        return title

    for i in range(1, count + 1):
        engine_id = None
        low = datetime.date(1975, 1, 1)
        if rnd.random() < 0.85:
            engine_id = rnd.choice(engine_ids)
            # игра не выходит раньше своего движка
            low = max(low, engine_date[engine_id])
        released = random_date(rnd, clamp_date(low), MAX_DATE)

        # оценка: колокол вокруг 72, редкие пропуски
        score = None
        if rnd.random() < 0.92:
            score = int(min(100, max(0, rnd.gauss(72, 14))))
        age = rnd.choices(AGE_RATINGS, weights=[8, 12, 16, 22, 22, 20])[0]
        if rnd.random() < 0.06:
            age = None

        rows.append([i, unique_name(rnd, used, make), score, age,
                     released.isoformat(), engine_id])
    return rows


def gen_game_genre(rnd, games, genres):
    roots = [g[0] for g in genres if g[2] is None]
    children = {}
    for g in genres:
        if g[2] is not None:
            children.setdefault(g[2], []).append(g[0])

    pairs = set()
    for game in games:
        root = rnd.choice(roots)
        pairs.add((game[0], root))
        kids = children.get(root, [])
        for _ in range(rnd.randint(0, 2)):
            if kids:
                pairs.add((game[0], rnd.choice(kids)))
        if rnd.random() < 0.35:
            other = rnd.choice(roots)
            pairs.add((game[0], other))
    return sorted(pairs)


def gen_game_release(rnd, games, platforms, companies, max_per_game):
    """Раскладывает каждую игру по платформам, регионам и ролям компаний."""
    plat_date = {p[0]: datetime.date.fromisoformat(p[5]) for p in platforms}
    plat_ids = list(plat_date)
    comp_ids = [c[0] for c in companies]

    seen = set()
    rows = []
    for game in games:
        game_id = game[0]
        first = datetime.date.fromisoformat(game[4])
        developer = rnd.choice(comp_ids)
        publisher = developer if rnd.random() < 0.25 else rnd.choice(comp_ids)
        porter = rnd.choice(comp_ids) if rnd.random() < 0.2 else None

        # платформы, которые уже существовали к выходу игры
        ok = [p for p in rnd.sample(plat_ids, min(len(plat_ids), 60))
              if plat_date[p] <= first]
        if not ok:
            ok = [min(plat_ids, key=lambda p: plat_date[p])]
        chosen = ok[:rnd.randint(1, max_per_game)]

        for plat in chosen:
            base = max(first, plat_date[plat])
            regions = rnd.choice([["WW"], ["NA", "EU"], ["JP"], ["NA", "EU", "JP"],
                                  ["NA"], ["EU"], ["WW"]])
            for region in regions:
                date = clamp_date(base + datetime.timedelta(days=rnd.randint(0, 540)))
                for company, role in ((developer, "developer"),
                                      (publisher, "publisher"),
                                      (porter, "porting_studio")):
                    if company is None:
                        continue
                    key = (game_id, company, plat, region, role)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append([game_id, plat, company, date.isoformat(), region, role])
    return rows


def write_csv(tables, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name in ORDER:
        path = os.path.join(out_dir, name + ".csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLUMNS[name])
            for row in tables[name]:
                w.writerow(["" if v is None else v for v in row])


def main():
    p = argparse.ArgumentParser(
        description="Генератор случайных тестовых данных (без обращений к сети)")
    p.add_argument("--companies", type=int, default=1200)
    p.add_argument("--engines", type=int, default=1100)
    p.add_argument("--platforms", type=int, default=1000)
    p.add_argument("--games", type=int, default=6000)
    p.add_argument("--platforms-per-game", type=int, default=4,
                   help="максимум платформ на одну игру")
    p.add_argument("--seed", type=int, default=20250915,
                   help="зерно ГСЧ, одинаковое зерно дает одинаковые файлы")
    p.add_argument("--out", default=None, help="куда положить CSV")
    args = p.parse_args()

    rnd = random.Random(args.seed)
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out or os.path.join(os.path.dirname(here), "data")

    companies = gen_companies(rnd, args.companies)
    engines = gen_engines(rnd, args.engines, companies)
    platforms = gen_platforms(rnd, args.platforms, companies)
    genres = gen_genres()
    games = gen_games(rnd, args.games, engines)
    game_genre = gen_game_genre(rnd, games, genres)
    game_release = gen_game_release(rnd, games, platforms, companies,
                                    args.platforms_per_game)

    tables = {
        "company": companies,
        "game_engine": engines,
        "platform": platforms,
        "genre": genres,
        "game": games,
        "game_genre": game_genre,
        "game_release": game_release,
    }
    write_csv(tables, out_dir)

    print("Готово. Файлы в %s\n" % out_dir)
    for name in ORDER:
        print("  %-14s %7d строк" % (name, len(tables[name])))


if __name__ == "__main__":
    main()
