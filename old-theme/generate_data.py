#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор тестовых данных для учебной БД по видеоиграм.

Источники:
  * Wikidata (SPARQL, без ключа) — игры, компании, платформы, жанры, движки,
    связи между ними и реальные даты релизов по платформам;
  * RAWG (нужен API-ключ) — пользовательские оценки игр.

Результат: семь CSV-файлов под схему лабораторной работы.

Запуск:
    python3 generate_data.py --games 4000
    python3 generate_data.py --games 4000 --no-rawg
    python3 generate_data.py --help
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

WD_ENDPOINT = "https://query.wikidata.org/sparql"
RAWG_ENDPOINT = "https://api.rawg.io/api/games"
UA = "BMSTU-DB-lab/1.0 (student coursework)"
LABEL = 'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }'

YEARS = range(1996, 2025)

# студии Nintendo — их игры берём целиком, независимо от года
NINTENDO = ["Q8093", "Q56283842", "Q1132576", "Q1571787",
            "Q1478832", "Q1662225", "Q1341356", "Q1948967"]

REGIONS = ["WW", "NA", "EU", "JP"]
# Минимальный возраст. В Wikidata четыре независимых системы рейтингов;
# берём их по приоритету PEGI -> USK -> ESRB -> CERO и приводим к шкале
# 0 / 3 / 7 / 12 / 16 / 18, которую разрешает CHECK в схеме.
AGE_BY_QID = {
    # PEGI — совпадает со шкалой один в один
    "Q14915512": 3, "Q14915514": 7, "Q14915515": 12,
    "Q14915516": 16, "Q14915517": 18,
    # USK (Германия): 0 / 6 / 12 / 16 / 18
    "Q14920387": 0, "Q14920391": 7, "Q14920392": 12,
    "Q14920393": 16, "Q14920394": 18,
    # ESRB (США): EC / E / E10+ / T / M17+ / AO18+
    "Q14864327": 0, "Q14864328": 3, "Q14864334": 3, "Q14864329": 7,
    "Q14864330": 12, "Q14864331": 18, "Q14864332": 18,
    # CERO (Япония): A / B12 / C15 / D17 / Z18
    "Q11389850": 0, "Q127986181": 0, "Q14870286": 12, "Q127985696": 12,
    "Q14870289": 16, "Q127985009": 16, "Q14870298": 18,
    "Q14870299": 18, "Q125714350": 18,
}
AGE_PROPS = (("age_pegi", "wdt:P908"), ("age_usk", "wdt:P914"),
             ("age_esrb", "wdt:P852"), ("age_cero", "wdt:P853"))

# ---------------------------------------------------------------- утилиты

def qid(url):
    return url.rsplit("/", 1)[-1]


def qnum(q):
    return int(q[1:]) if q[1:].isdigit() else 10 ** 9


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield i, seq[i:i + size]


class Progress:
    """Однострочный прогресс-бар."""

    def __init__(self, title, total):
        self.title, self.total, self.done = title, max(total, 1), 0
        self.draw()

    def step(self, n=1):
        self.done += n
        self.draw()

    def draw(self):
        pct = min(100, self.done * 100 // self.total)
        fill = pct // 4
        bar = "#" * fill + "." * (25 - fill)
        sys.stdout.write("\r  %-22s [%s] %3d%%  %d/%d" %
                         (self.title, bar, pct, self.done, self.total))
        sys.stdout.flush()

    def close(self):
        sys.stdout.write("\n")
        sys.stdout.flush()


# ------------------------------------------------------------- обращения

class Fetcher:
    def __init__(self, cache_dir, delay=0.4):
        self.cache = cache_dir
        self.delay = delay
        os.makedirs(cache_dir, exist_ok=True)

    def _get(self, url, data=None, headers=None, retries=4):
        req = urllib.request.Request(url, data=data,
                                     headers=headers or {"User-Agent": UA})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.load(r)
            except Exception:
                if attempt == retries - 1:
                    return None
                time.sleep(4 * (attempt + 1))

    def sparql(self, name, query):
        path = os.path.join(self.cache, name + ".json")
        if os.path.exists(path):
            cached = json.load(open(path, encoding="utf-8"))
            if isinstance(cached, list):
                return cached
            # в кэше лежит полный ответ SPARQL, а не список строк — достаём
            if isinstance(cached, dict) and "results" in cached:
                return cached["results"]["bindings"]
        body = urllib.parse.urlencode({"query": query}).encode()
        res = self._get(WD_ENDPOINT, body, {
            "Accept": "application/sparql-results+json", "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded"})
        rows = res["results"]["bindings"] if res else []
        json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(self.delay)
        return rows

    def rawg(self, name, params):
        path = os.path.join(self.cache, name + ".json")
        if os.path.exists(path):
            return json.load(open(path, encoding="utf-8"))
        url = RAWG_ENDPOINT + "?" + urllib.parse.urlencode(params)
        res = self._get(url) or {}
        json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(self.delay)
        return res


def val(row, key):
    return row[key]["value"] if key in row else None


# ------------------------------------------------------------ шаг 1: игры

def collect_games(f, target, nintendo_limit):
    """Топ Nintendo по известности + все Minecraft + добор по годам."""
    games = {}

    # «Самые известные» = те, о которых написали на наибольшем числе языков.
    # wikibase:sitelinks — количество языковых версий статьи в Википедии.
    nin_values = " ".join("wd:" + q for q in NINTENDO)
    rows = f.sparql("wd_nintendo_top%d" % nintendo_limit, f"""
SELECT DISTINCT ?game ?gameLabel ?sitelinks (MIN(?d) AS ?date) WHERE {{
  VALUES ?nin {{ {nin_values} }}
  ?game wdt:P31 wd:Q7889 ; wdt:P577 ?d ; wdt:P400 ?pf ; wikibase:sitelinks ?sitelinks .
  {{ ?game wdt:P178 ?nin }} UNION {{ ?game wdt:P123 ?nin }}
  {LABEL}
}}
GROUP BY ?game ?gameLabel ?sitelinks
ORDER BY DESC(?sitelinks)
LIMIT {int(nintendo_limit * 1.6)}""")
    for r in rows:
        if len(games) >= nintendo_limit:
            break
        q, lab = qid(val(r, "game")), val(r, "gameLabel")
        if lab and lab != q and len(lab) <= 140:
            games[q] = (lab, val(r, "date")[:10])
    nintendo_count = len(games)

    for r in f.sparql("wd_minecraft", """
SELECT DISTINCT ?game ?l (MIN(?d) AS ?date) WHERE {
  ?game wdt:P31 wd:Q7889 ; wdt:P577 ?d ; rdfs:label ?l .
  FILTER(LANG(?l) = "en" && CONTAINS(LCASE(?l), "minecraft"))
}
GROUP BY ?game ?l"""):
        lab = val(r, "l")
        if len(lab) <= 140:
            games[qid(val(r, "game"))] = (lab, val(r, "date")[:10])

    pool = {}
    bar = Progress("игры по годам", len(YEARS))
    for year in YEARS:
        for r in f.sparql("wd_games_%d" % year, f"""
SELECT ?game ?gameLabel (MIN(?d) AS ?date) WHERE {{
  ?game wdt:P31 wd:Q7889 ; wdt:P577 ?d ; wdt:P178 ?dev ; wdt:P123 ?pub ; wdt:P400 ?pf .
  FILTER(YEAR(?d) = {year})
  {LABEL}
}}
GROUP BY ?game ?gameLabel"""):
            q, lab = qid(val(r, "game")), val(r, "gameLabel")
            if q.startswith("Q") and lab and lab != q and len(lab) <= 140:
                pool[q] = (lab, val(r, "date")[:10])
        bar.step()
    bar.close()

    # добираем до цели: самые заметные игры каждого года (меньше QID — раньше
    # заведена статья, а это неплохо коррелирует с известностью)
    by_year = {}
    for q, (lab, d) in pool.items():
        by_year.setdefault(d[:4], []).append(q)
    per_year = max(1, (target - len(games)) // max(len(by_year), 1) + 1)
    for year in sorted(by_year):
        for q in sorted(by_year[year], key=qnum)[:per_year]:
            if len(games) >= target:
                break
            games.setdefault(q, pool[q])

    print("  игр отобрано: %d (из них Nintendo: %d, пул был %d)"
          % (len(games), nintendo_count, len(pool)))
    return games


# --------------------------------------------------------- шаг 2: связи

def collect_links(f, ids):
    """dev / pub / genre / engine / platform(+дата) / возрастной рейтинг."""
    props = (("dev", "wdt:P178"), ("pub", "wdt:P123"),
             ("genre", "wdt:P136"), ("engine", "wdt:P408")) + AGE_PROPS
    links = {k: [] for k, _ in props}
    links["platform"] = []
    total = (len(props) + 1) * (len(ids) // 140 + 1)
    bar = Progress("связи игр", total)
    for key, prop in props:
        for i, ch in chunks(ids, 140):
            vals = " ".join("wd:" + q for q in ch)
            for r in f.sparql("wd_%s_%05d" % (key, i),
                              f"SELECT ?game ?v WHERE {{ VALUES ?game {{ {vals} }} ?game {prop} ?v . }}"):
                links[key].append((qid(val(r, "game")), qid(val(r, "v"))))
            bar.step()
    for i, ch in chunks(ids, 140):
        vals = " ".join("wd:" + q for q in ch)
        for r in f.sparql("wd_platform_%05d" % i, f"""
SELECT ?game ?v ?pdate WHERE {{
  VALUES ?game {{ {vals} }}
  ?game p:P400 ?st . ?st ps:P400 ?v .
  OPTIONAL {{ ?st pq:P577 ?pdate }} }}"""):
            d = val(r, "pdate")
            links["platform"].append((qid(val(r, "game")), qid(val(r, "v")),
                                      d[:10] if d else None))
        bar.step()
    bar.close()
    return links


# ------------------------------------------------- шаг 3: детали сущностей

def collect_entities(f, name, ids, query_tpl, size=120):
    out = {}
    bar = Progress(name, len(ids) // size + 1)
    for i, ch in chunks(sorted(ids, key=qnum), size):
        vals = " ".join("wd:" + q for q in ch)
        for r in f.sparql("wd_%s_%05d" % (name, i), query_tpl.format(values=vals)):
            out.setdefault(qid(val(r, "x")), []).append(r)
        bar.step()
    bar.close()
    return out


Q_COMPANY = """
SELECT ?x ?xLabel ?countryLabel ?hqCountryLabel ?hqLabel ?inception WHERE {{
  VALUES ?x {{ {values} }}
  OPTIONAL {{ ?x wdt:P17 ?country }}
  OPTIONAL {{ ?x wdt:P159 ?hq . OPTIONAL {{ ?hq wdt:P17 ?hqCountry }} }}
  OPTIONAL {{ ?x wdt:P571 ?inception }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""

Q_PLATFORM = """
SELECT ?x ?xLabel ?manufacturer ?date ?inception WHERE {{
  VALUES ?x {{ {values} }}
  OPTIONAL {{ ?x wdt:P176 ?manufacturer }}
  OPTIONAL {{ ?x wdt:P577 ?date }}
  OPTIONAL {{ ?x wdt:P571 ?inception }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""

Q_GENRE = """
SELECT ?x ?xLabel ?parent WHERE {{
  VALUES ?x {{ {values} }}
  OPTIONAL {{ ?x wdt:P279 ?parent }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""

# P408 в Wikidata ссылается на что попало: сами игры, Java, Windows, Adobe Flash,
# студии-разработчики. Настоящие движки отбираем по классу (P31):
#   Q193564   — game engine
#   Q63533016 — game engine version (Unreal Engine 4 и подобные)
#   Q5519929  — game creation system (GameMaker, RPG Maker)
#   Q2622299  — software engine
Q_ENGINE = """
SELECT ?x ?xLabel ?dev ?ver ?inception ?pub ?disc WHERE {{
  VALUES ?x {{ {values} }}
  ?x wdt:P31 ?cls .
  VALUES ?cls {{ wd:Q193564 wd:Q63533016 wd:Q5519929 wd:Q2622299 }}
  OPTIONAL {{ ?x wdt:P178 ?dev }}
  OPTIONAL {{ ?x wdt:P348 ?ver }}
  OPTIONAL {{ ?x wdt:P571 ?inception }}
  OPTIONAL {{ ?x wdt:P577 ?pub }}
  OPTIONAL {{ ?x wdt:P2669 ?disc }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""

# ------------------------------------------------------- шаг 4: оценки RAWG

def collect_scores(f, key, pages=150):
    """Каталог RAWG по убыванию популярности -> отображение название -> оценка.

    Тянуть карточку каждой игры по отдельности было бы 4000 запросов, поэтому
    выкачиваем список страницами по 40 и сопоставляем по нормализованному имени.
    """
    scores = {}
    bar = Progress("оценки RAWG", pages)
    for page in range(1, pages + 1):
        data = f.rawg("rawg_%04d" % page,
                      {"key": key, "page_size": 40, "page": page,
                       "ordering": "-added"})
        for g in (data or {}).get("results", []):
            rating = g.get("rating") or 0
            if rating:
                scores[normalize(g["name"])] = int(round(rating * 20))
        bar.step()
        if not (data or {}).get("next"):
            break
    bar.close()
    print("  оценок собрано: %d" % len(scores))
    return scores


def normalize(name):
    s = name.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


# ------------------------------------------------- досочинение данных игр
# Часть игр в источниках без оценки и без возрастного рейтинга. Чтобы колонки
# не были наполовину пустыми, недостающее достраиваем правдоподобно.
# Генератор детерминированный: ключ — идентификатор игры, поэтому при повторном
# запуске у той же игры будет то же значение.

HIGH_AGE_WORDS = ("horror", "shooter", "fighting", "war", "stealth",
                  "hack and slash", "survival", "crime", "beat")
LOW_AGE_WORDS = ("puzzle", "platform", "educational", "party", "sports",
                 "racing", "music", "kart", "simulation", "board")


def synth_score(key):
    """Оценки игроков кучкуются в районе 70 из 100 — повторяем это распределение."""
    rnd = random.Random("score:" + key)
    return max(20, min(97, int(round(rnd.gauss(72, 11)))))


def synth_age(key, genre_names):
    """Возраст выводим из жанров: хоррор и шутеры взрослее головоломок."""
    rnd = random.Random("age:" + key)
    text = " ".join(genre_names).lower()
    if any(w in text for w in HIGH_AGE_WORDS):
        return rnd.choice([16, 18, 18])
    if any(w in text for w in LOW_AGE_WORDS):
        return rnd.choice([0, 3, 7, 7])
    return rnd.choice([7, 12, 12, 16])


# ------------------------------------------------ вспомогательные эвристики

HANDHELD = ("game boy", "nintendo ds", "nintendo 3ds", "psp", "playstation portable",
            "vita", "switch lite", "game gear", "neo geo pocket", "wonderswan",
            "lynx", "n-gage", "steam deck")
COMPUTER = ("windows", "macos", "mac os", "linux", "dos", "amiga", "atari st",
            "commodore", "zx spectrum", "msx", "personal computer", "pc")
MOBILE = ("ios", "android", "iphone", "ipad", "mobile", "windows phone", "j2me")
VR = ("vr", "oculus", "quest", "vive", "index", "psvr")
CLOUD = ("stadia", "cloud", "geforce now", "onlive", "luna")
ARCADE = ("arcade", "naomi", "cps", "neo geo mvs", "system 16")

GENERATIONS = ((1983, 3), (1987, 4), (1993, 5), (1998, 6), (2005, 7), (2012, 8), (2020, 9))


def platform_type(name):
    low = name.lower()
    for words, kind in ((ARCADE, "arcade"), (VR, "vr"), (CLOUD, "cloud"),
                        (MOBILE, "mobile"), (HANDHELD, "handheld"), (COMPUTER, "computer")):
        if any(w in low for w in words):
            return kind
    return "console"


def platform_generation(kind, year):
    """Поколение консолей выводим из года выхода — в Wikidata его почти нет."""
    if kind not in ("console", "handheld") or not year:
        return None
    gen = 2
    for since, g in GENERATIONS:
        if year >= since:
            gen = g
    return gen


def short_name(name):
    """Аббревиатура платформы: инициалы слов либо первые символы."""
    words = [w for w in re.split(r"[\s\-/]+", name) if w]
    initials = "".join(w[0] for w in words if w[0].isalnum()).upper()
    if 2 <= len(initials) <= 12:
        return initials
    return (name[:12] or "N/A").strip()


# ------------------------------------------------------- шаг 5: сборка CSV

def year_of(date):
    try:
        return int(date[:4])
    except (TypeError, ValueError):
        return None


def build(games, links, comp_raw, plat_raw, genre_raw, eng_raw, scores, fill=True):
    first = lambda rows, k: next((val(r, k) for r in rows if val(r, k)), None)

    # ---- компании -------------------------------------------------------
    earliest = {}
    for gq, cq in links["dev"] + links["pub"]:
        y = year_of(games.get(gq, (None, ""))[1])
        if y and (cq not in earliest or y < earliest[cq]):
            earliest[cq] = y

    company, comp_id, used_names = [], {}, set()
    for cq, rows in comp_raw.items():
        name = first(rows, "xLabel")
        if not name or name == cq or name in used_names:
            continue
        country = first(rows, "countryLabel") or first(rows, "hqCountryLabel")
        if not country:
            continue                      # без страны запись не берём: NOT NULL
        founded = year_of(first(rows, "inception")) or earliest.get(cq)
        if not founded or not (1800 <= founded <= 2024):
            continue
        used_names.add(name)
        comp_id[cq] = len(company) + 1
        company.append((comp_id[cq], name[:200], country[:100],
                        (first(rows, "hqLabel") or "")[:100] or None, founded))

    # ---- платформы ------------------------------------------------------
    platform, plat_id, seen = [], {}, set()
    for pq, rows in plat_raw.items():
        name = first(rows, "xLabel")
        date = first(rows, "date") or first(rows, "inception")
        if not name or name == pq or not date or name in seen:
            continue
        seen.add(name)
        kind = platform_type(name)
        manuf = first(rows, "manufacturer")
        plat_id[pq] = len(platform) + 1
        platform.append((plat_id[pq], name[:200], short_name(name), kind,
                         platform_generation(kind, year_of(date)), date[:10],
                         comp_id.get(qid(manuf)) if manuf else None))

    # ---- жанры ----------------------------------------------------------
    genre, genre_id, seen = [], {}, set()
    for gq, rows in genre_raw.items():
        name = first(rows, "xLabel")
        if not name or name == gq or name in seen:
            continue
        seen.add(name)
        genre_id[gq] = len(genre) + 1
        genre.append([genre_id[gq], name[:120], None, gq, first(rows, "parent")])
    for row in genre:
        parent = row.pop()
        row.pop()
        row[2] = genre_id.get(qid(parent)) if parent else None
    genre = [tuple(r) for r in genre]

    # ---- движки ---------------------------------------------------------
    # даты игр на движке: нужны как запасная дата выхода и как признак того,
    # что движок ещё живой
    first_game, last_game = {}, {}
    for gq, eq in links["engine"]:
        d = games.get(gq, (None, ""))[1]
        if not d:
            continue
        if eq not in first_game or d < first_game[eq]:
            first_game[eq] = d
        if eq not in last_game or d > last_game[eq]:
            last_game[eq] = d

    engine, eng_id, seen = [], {}, set()
    for eq, rows in eng_raw.items():
        name = first(rows, "xLabel")
        dev = first(rows, "dev")
        if not name or name == eq or name in seen or not dev:
            continue
        cid = comp_id.get(qid(dev))
        if not cid:
            continue
        # своей даты у движка часто нет — тогда берём выход первой игры на нём
        date = first(rows, "inception") or first(rows, "pub") or first_game.get(eq)
        if not date:
            continue
        # снят с поддержки явно либо на нём давно ничего не выходило
        active = "false" if first(rows, "disc") else \
            ("true" if last_game.get(eq, "") >= "2016" else "false")
        seen.add(name)
        eng_id[eq] = len(engine) + 1
        engine.append((eng_id[eq], name[:150], (first(rows, "ver") or "1.0")[:40],
                       cid, date[:10], active))

    # ---- игры -----------------------------------------------------------
    game_engine_of = {}
    for gq, eq in links["engine"]:
        if eq in eng_id:
            game_engine_of.setdefault(gq, eng_id[eq])
    # рейтинги разных систем противоречат друг другу, поэтому берём первую
    # попавшуюся по приоритету: PEGI ближе всего к нашей шкале
    age_of = {}
    for key, _ in AGE_PROPS:
        for gq, aq in links[key]:
            if aq in AGE_BY_QID:
                age_of.setdefault(gq, AGE_BY_QID[aq])

    genres_of = {}
    genre_name = {row[0]: row[1] for row in genre}
    for gq, gnq in links["genre"]:
        if gnq in genre_id:
            genres_of.setdefault(gq, []).append(genre_name[genre_id[gnq]])

    game, game_id = [], {}
    matched = aged = synth_scores = synth_ages = 0
    for gq in sorted(games, key=qnum):
        title, date = games[gq]
        score = scores.get(normalize(title))
        if score:
            matched += 1
        elif fill:
            score = synth_score(gq)
            synth_scores += 1
        age = age_of.get(gq)
        if age is not None:
            aged += 1
        elif fill:
            age = synth_age(gq, genres_of.get(gq, []))
            synth_ages += 1
        game_id[gq] = len(game) + 1
        game.append((game_id[gq], title[:200], score, age,
                     date, game_engine_of.get(gq)))

    # ---- игра-жанр ------------------------------------------------------
    game_genre, seen = [], set()
    for gq, gnq in links["genre"]:
        if gq in game_id and gnq in genre_id:
            pair = (game_id[gq], genre_id[gnq])
            if pair not in seen:
                seen.add(pair)
                game_genre.append(pair)

    # ---- релизы (тернарная связь) --------------------------------------
    devs, pubs = {}, {}
    for gq, cq in links["dev"]:
        if cq in comp_id:
            devs.setdefault(gq, []).append(comp_id[cq])
    for gq, cq in links["pub"]:
        if cq in comp_id:
            pubs.setdefault(gq, []).append(comp_id[cq])
    country_of = {row[0]: row[2] for row in company}
    region_by_country = {"Japan": "JP", "United States of America": "NA",
                         "United States": "NA", "Canada": "NA"}

    game_release, seen = [], set()
    for gq, pq, pdate in links["platform"]:
        if gq not in game_id or pq not in plat_id:
            continue
        gid, pid = game_id[gq], plat_id[pq]
        date = (pdate or games[gq][1])[:10]
        for role, companies in (("developer", devs.get(gq, [])),
                                ("publisher", pubs.get(gq, []))):
            for cid in companies[:3]:
                region = "WW" if role == "developer" else \
                    region_by_country.get(country_of.get(cid), "EU")
                key = (gid, cid, pid, region, role)
                if key in seen:
                    continue
                seen.add(key)
                game_release.append((gid, pid, cid, date, region, role))

    print("  оценка: %d из источника, %d досочинено" % (matched, synth_scores))
    print("  возраст: %d из источника, %d досочинено" % (aged, synth_ages))
    print("  движок: %d из источника, остальные пустые" % len(game_engine_of))
    return {"company": company, "game_engine": engine, "platform": platform,
            "genre": genre, "game": game, "game_genre": game_genre,
            "game_release": game_release}


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
    p = argparse.ArgumentParser(description="Генератор тестовых данных о видеоиграх")
    p.add_argument("--games", type=int, default=4000, help="сколько игр отобрать")
    p.add_argument("--nintendo", type=int, default=200,
                   help="сколько игр Nintendo взять (по известности)")
    p.add_argument("--out", default=None, help="куда положить CSV")
    p.add_argument("--cache", default=None, help="папка кэша ответов API")
    p.add_argument("--rawg-key-file", default=os.path.expanduser("~/.rawg_key"))
    p.add_argument("--no-rawg", action="store_true", help="без оценок RAWG")
    p.add_argument("--no-fill", action="store_true",
                   help="не досочинять недостающие оценки и возраст")
    p.add_argument("--rawg-pages", type=int, default=150)
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out or os.path.join(os.path.dirname(here), "data")
    cache = args.cache or os.path.join(here, ".cache")
    f = Fetcher(cache)

    print("Шаг 1/5. Отбор игр")
    games = collect_games(f, args.games, args.nintendo)
    ids = sorted(games, key=qnum)

    print("Шаг 2/5. Связи игр")
    links = collect_links(f, ids)

    print("Шаг 3/5. Детали сущностей")
    comp_ids = {c for _, c in links["dev"] + links["pub"]}
    plat_ids = {p for _, p, _ in links["platform"]}
    genre_ids = {g for _, g in links["genre"]}
    eng_ids = {e for _, e in links["engine"]}
    plat_raw = collect_entities(f, "platform_info", plat_ids, Q_PLATFORM)
    eng_raw = collect_entities(f, "engine_info2", eng_ids, Q_ENGINE)
    genre_raw = collect_entities(f, "genre_info", genre_ids, Q_GENRE)
    for rows in plat_raw.values():
        for r in rows:
            if val(r, "manufacturer"):
                comp_ids.add(qid(val(r, "manufacturer")))
    for rows in eng_raw.values():
        for r in rows:
            if val(r, "dev"):
                comp_ids.add(qid(val(r, "dev")))
    comp_raw = collect_entities(f, "company_info", comp_ids, Q_COMPANY)

    print("Шаг 4/5. Оценки игроков")
    scores = {}
    if args.no_rawg:
        print("  пропущено (--no-rawg)")
    elif os.path.exists(args.rawg_key_file):
        key = open(args.rawg_key_file).read().strip()
        scores = collect_scores(f, key, args.rawg_pages)
    else:
        print("  ключ %s не найден, оценки будут пустыми" % args.rawg_key_file)

    print("Шаг 5/5. Сборка CSV")
    tables = build(games, links, comp_raw, plat_raw, genre_raw, eng_raw, scores,
                   fill=not args.no_fill)
    write_csv(tables, out_dir)

    print("\nГотово. Файлы в %s\n" % out_dir)
    for name in ORDER:
        print("  %-14s %6d строк" % (name, len(tables[name])))


if __name__ == "__main__":
    main()
