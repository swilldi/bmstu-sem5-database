#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор тестовых данных для учебной БД об автогонках (ЛР №1).

Источники (регистрация и ключи не нужны):
  * Jolpica F1 API (api.jolpi.ca, преемник Ergast) — все гонки Формулы-1
    с 1950 года: пилоты, конструкторы, трассы, результаты;
  * API Википедии — сопоставление статей из Jolpica с элементами Wikidata;
  * Wikidata (SPARQL) — место рождения пилотов, длина и год открытия трасс,
    год основания и материнские компании команд, а также тысячи гонщиков,
    трасс и команд других серий.

Что реальное, а что досочинено:
  * гонки F1 реальные: дата, трасса, пилот, команда, номер машины, старт,
    финиш, статус, круги. Итоговое время реальное, где оно есть в источнике
    (у отставших на круг в старых гонках его нет — оценивается). Лучший круг
    реальный с 2004 года, раньше оценивается по среднему кругу;
  * машина F1 = «команда + сезон + номер». Названий шасси в открытых данных
    нет, поэтому модель подписана как «Ferrari 2023 #16». Мощность и вес
    генерируются по правилам эпохи;
  * гонки остальных классов (hypercar, gt, touring, stock и младшие формулы)
    вымышленные: придуманные чемпионаты на реальных трассах с реальными
    гонщиками и командами из Wikidata, модели машин — реальные модели класса;
  * класс лицензии генерируется всегда. Недостающие год основания, длина
    трассы, год открытия, город рождения, год дебюта досочиняются так, чтобы
    не противоречить гонкам (команда основана не позже сезона машины и т.п.).

Данные подогнаны под ограничения из lab-01/define_restrictions.sql:
одна гонка в день у пилота, в гонке (трасса + дата) не повторяются машина,
стартовая и финишная позиции, связки статуса со временем, кругами и т.д.
Перед записью всё проверяется тем же набором правил.

Результат: driver.csv, car.csv, team.csv, track.csv, race_entry.csv,
contract.csv в ../data. Колонки идут в порядке create_table.sql, id заданы
явно (после COPY нужно сдвинуть последовательности через setval).
contract — периоды пилота в команде, выведенные из гонок: подряд идущие
гонки за одну команду; пустой end_date — пилот всё ещё в команде.
Порядок загрузки из-за внешних ключей:
team -> track -> driver -> car -> race_entry -> contract.

Запуск:
    python3 generate_racing_data.py
    python3 generate_racing_data.py --no-fake-series   # только реальная F1
    python3 generate_racing_data.py --help
Первый запуск качает данные несколько минут (Jolpica ограничивает частоту
запросов), ответы кэшируются в .cache/racing — повторный запуск мгновенный.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

JOLPICA = "https://api.jolpi.ca/ergast/f1"
WIKI_API = "https://en.wikipedia.org/w/api.php"
WD_ENDPOINT = "https://query.wikidata.org/sparql"
UA = "BMSTU-DB-lab/1.0 (student coursework)"
LABEL = 'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }'

TODAY = datetime.date.today()
CUR_YEAR = TODAY.year
F1_FIRST = 1950

# ---------------------------------------------------------------- границы
# Повторяют CHECK из define_restrictions.sql
BIRTH_MIN = datetime.date(1900, 1, 1)
FOUNDED_MIN, OPENED_MIN, SEASON_MIN = 1894, 1900, 1950
RACE_MIN = datetime.date(1950, 1, 1)
HP = (100, 1500)
WEIGHT = (400, 2000)
LENGTH = (0.4, 26.0)
POS = (1, 70)
LAPS = (0, 1000)
BEST_MS = (10_000, 15 * 60_000)
TOTAL_MS = (60_000, 30 * 3600_000)
CAR_CLASSES = ("formula", "hypercar", "gt", "touring", "stock")
TRACK_TYPES = ("permanent", "street", "oval")
LICENSES = ("super", "A", "B", "C", "D")

# ---------------------------------------------------------------- справочники

# Национальность из Jolpica -> страна (так же, как страны подписаны в Wikidata)
NATIONALITY = {
    "American": "United States", "American-Italian": "United States",
    "Argentine": "Argentina", "Argentinian": "Argentina",
    "Argentine-Italian": "Argentina", "Australian": "Australia",
    "Austrian": "Austria", "Belgian": "Belgium", "Brazilian": "Brazil",
    "British": "United Kingdom", "Canadian": "Canada", "Chilean": "Chile",
    "Chinese": "China", "Colombian": "Colombia", "Czech": "Czech Republic",
    "Danish": "Denmark", "Dutch": "Netherlands", "East German": "East Germany",
    "Finnish": "Finland", "French": "France", "German": "Germany",
    "Hong Kong": "Hong Kong", "Hungarian": "Hungary", "Indian": "India",
    "Indonesian": "Indonesia", "Irish": "Ireland", "Italian": "Italy",
    "Japanese": "Japan", "Liechtensteiner": "Liechtenstein",
    "Malaysian": "Malaysia", "Mexican": "Mexico", "Monegasque": "Monaco",
    "New Zealander": "New Zealand", "New Zealand": "New Zealand",
    "Polish": "Poland", "Portuguese": "Portugal", "Rhodesian": "Rhodesia",
    "Russian": "Russia", "South African": "South Africa", "Spanish": "Spain",
    "Swedish": "Sweden", "Swiss": "Switzerland", "Thai": "Thailand",
    "Uruguayan": "Uruguay", "Venezuelan": "Venezuela", "Saudi": "Saudi Arabia",
    "Emirati": "United Arab Emirates", "Moroccan": "Morocco",
    "Argentinean": "Argentina", "Belarusian": "Belarus", "Estonian": "Estonia",
}

# Разные написания одной страны -> одно
COUNTRY_ALIASES = {
    "UK": "United Kingdom", "USA": "United States",
    "United States of America": "United States",
    "UAE": "United Arab Emirates", "Korea": "South Korea",
    "People's Republic of China": "China",
    "Kingdom of the Netherlands": "Netherlands",
    "Republic of Ireland": "Ireland", "Czechia": "Czech Republic",
    "Ohio": "United States",
    # исторические государства -> современные (кроме тех, что встречаются
    # в самой F1 как отдельная национальность: ГДР, СССР, Чехословакия, Родезия)
    "German Reich": "Germany", "Nazi Germany": "Germany", "Weimar Republic": "Germany",
    "German Empire": "Germany", "Kingdom of Prussia": "Germany",
    "Free State of Prussia": "Germany", "Kingdom of Italy": "Italy",
    "Kingdom of Romania": "Romania", "Socialist Republic of Romania": "Romania",
    "Kingdom of Denmark": "Denmark", "Austria–Hungary": "Austria",
    "Austria-Hungary": "Austria", "First Austrian Republic": "Austria",
    "Federal State of Austria": "Austria", "British Hong Kong": "Hong Kong",
    "French protectorate of Tunisia": "Tunisia", "Ottoman Empire": "Turkey",
    "Polish People's Republic": "Poland", "Second Polish Republic": "Poland",
    "Russian Empire": "Russia", "Kingdom of Hungary": "Hungary",
    "Hungarian People's Republic": "Hungary", "Empire of Japan": "Japan",
    "Union of South Africa": "South Africa", "Kingdom of Greece": "Greece",
    "Kingdom of Bulgaria": "Bulgaria", "People's Republic of Bulgaria": "Bulgaria",
    "Kingdom of Egypt": "Egypt", "Kingdom of Portugal": "Portugal",
    "Francoist Spain": "Spain", "French Third Republic": "France",
    "Kingdom of Serbia": "Serbia", "Kingdom of Yugoslavia": "Yugoslavia",
    "Socialist Federal Republic of Yugoslavia": "Yugoslavia",
    "Czechoslovak Socialist Republic": "Czechoslovakia",
}

# Трассы F1, которые проложены по улицам города
F1_STREET = {"monaco", "baku", "marina_bay", "jeddah", "vegas", "adelaide",
             "detroit", "phoenix", "long_beach", "dallas", "valencia",
             "montjuic", "monsanto", "boavista", "pedralbes", "pescara",
             "miami", "ain-diab", "essarts"}
F1_OVAL = {"indianapolis"}

# Классы трасс в Wikidata: обычная трасса, городская, ралли-кросс.
# Картинг, мотокросс и драг-полосы не берём.
WD_TRACK_CLASSES = {"Q2338524": "permanent", "Q926439": "street",
                    "Q94196270": "permanent"}
# «Speedway» означает овал только в Северной Америке и Океании; в Японии
# или Индии так называют обычные трассы (Fuji Speedway), а стадионы —
# это мотоспидвей, их не берём вовсе
OVAL_NAME = re.compile(r"\b(speedway|superspeedway|oval)\b", re.I)
OVAL_COUNTRIES = {"United States", "Canada", "Australia", "New Zealand"}
NOT_CAR_TRACK = re.compile(r"\b(stadium|stadion)\b", re.I)

# Мощность и вес машин F1 по эпохам: (до года, л.с., кг)
F1_ERAS = [
    (1953, (170, 400), (560, 760)),
    (1960, (240, 400), (550, 720)),
    (1965, (150, 220), (450, 520)),
    (1976, (380, 520), (550, 600)),
    (1986, (480, 900), (540, 600)),
    (1988, (600, 950), (500, 560)),
    (1994, (620, 800), (500, 530)),
    (2005, (700, 950), (595, 610)),
    (2013, (740, 800), (605, 645)),
    (2021, (850, 1000), (691, 755)),
    (9999, (950, 1020), (798, 805)),
]
INDY_ROADSTER = ((330, 420), (700, 850))   # Инди-500 в зачёте F1, 1950–1960

# Реальные модели по классам: (модель, первый сезон, последний сезон)
MODELS = {
    "formula": [
        ("Dallara F300", 2000, 2001), ("Dallara F302", 2002, 2007),
        ("Dallara F308", 2008, 2011), ("Dallara F312", 2012, 2018),
        ("Dallara GP2/05", 2005, 2007), ("Dallara GP2/08", 2008, 2010),
        ("Dallara GP2/11", 2011, 2017), ("Dallara F2 2018", 2018, 2023),
        ("Dallara F2 2024", 2024, 9999), ("Dallara GP3/10", 2010, 2012),
        ("Dallara GP3/13", 2013, 2015), ("Dallara GP3/16", 2016, 2018),
        ("Dallara F3 2019", 2019, 2024), ("Dallara F3 2025", 2025, 9999),
        ("Lola B02/50", 2002, 2004), ("Lola B05/52", 2005, 2008),
        ("Tatuus F.4-T014", 2014, 2021), ("Tatuus F4-T421", 2022, 9999),
        ("Dallara IR-05", 2003, 2011), ("Dallara DW12", 2012, 9999),
        ("Reynard 2KI", 2000, 2002),
    ],
    "hypercar": [
        ("Toyota GR010 Hybrid", 2021, 9999),
        ("Glickenhaus SCG 007 LMH", 2021, 2023), ("Alpine A480", 2021, 2022),
        ("Peugeot 9X8", 2022, 9999), ("Ferrari 499P", 2023, 9999),
        ("Porsche 963", 2023, 9999), ("Cadillac V-Series.R", 2023, 9999),
        ("Vanwall Vandervell 680", 2023, 2023), ("BMW M Hybrid V8", 2024, 9999),
        ("Alpine A424", 2024, 9999), ("Lamborghini SC63", 2024, 2024),
        ("Isotta Fraschini Tipo 6", 2024, 2024),
        ("Aston Martin Valkyrie AMR-LMH", 2025, 9999),
    ],
    "gt": [
        ("Porsche 911 GT3-RS", 2000, 2005), ("Ferrari 360 Modena GT", 2000, 2004),
        ("Chrysler Viper GTS-R", 2000, 2005), ("Chevrolet Corvette C5-R", 2000, 2004),
        ("Saleen S7-R", 2001, 2007), ("Lister Storm", 2000, 2003),
        ("Maserati MC12 GT1", 2004, 2009), ("Aston Martin DBR9", 2005, 2009),
        ("Porsche 911 GT3 R", 2006, 9999), ("Ferrari F430 GT3", 2006, 2010),
        ("Ferrari 458 Italia GT3", 2011, 2015), ("Ferrari 488 GT3", 2016, 2022),
        ("Ferrari 296 GT3", 2023, 9999), ("Audi R8 LMS", 2009, 9999),
        ("Mercedes-Benz SLS AMG GT3", 2011, 2015), ("Mercedes-AMG GT3", 2016, 9999),
        ("BMW Z4 GT3", 2010, 2015), ("BMW M6 GT3", 2016, 2021),
        ("BMW M4 GT3", 2022, 9999), ("Lamborghini Gallardo GT3", 2006, 2014),
        ("Lamborghini Huracán GT3", 2015, 9999), ("McLaren MP4-12C GT3", 2012, 2014),
        ("McLaren 650S GT3", 2015, 2018), ("McLaren 720S GT3", 2019, 9999),
        ("Aston Martin V12 Vantage GT3", 2012, 2018),
        ("Aston Martin Vantage AMR GT3", 2019, 9999),
        ("Bentley Continental GT3", 2014, 9999), ("Nissan GT-R Nismo GT3", 2012, 9999),
        ("Lexus RC F GT3", 2017, 9999), ("Honda NSX GT3", 2017, 9999),
        ("Ford Mustang GT3", 2024, 9999), ("Chevrolet Corvette Z06 GT3.R", 2024, 9999),
    ],
    "touring": [
        ("BMW 320i (E36)", 1995, 1999), ("BMW 320i (E46)", 2000, 2005),
        ("Alfa Romeo 155", 1995, 1997), ("Alfa Romeo 156", 1998, 2005),
        ("Audi A4 Quattro", 1995, 1999), ("Vauxhall Vectra", 1996, 2008),
        ("Honda Accord", 1996, 2002), ("Ford Mondeo", 1995, 2000),
        ("Volvo S40", 1997, 2000), ("Nissan Primera", 1995, 2000),
        ("Peugeot 406", 1996, 1999), ("SEAT Toledo", 1998, 2004),
        ("SEAT León", 2005, 2016), ("Chevrolet Cruze", 2009, 2015),
        ("Honda Civic", 2004, 2016), ("BMW 320si", 2006, 2011),
        ("Volvo S60", 2012, 2017), ("Citroën C-Elysée", 2014, 2017),
        ("Lada Granta", 2012, 2015), ("Lada Vesta", 2015, 2017),
        ("Hyundai i30 N TCR", 2017, 9999), ("Honda Civic Type R TCR", 2018, 9999),
        ("Audi RS 3 LMS", 2017, 9999), ("Cupra León Competición", 2021, 9999),
        ("Lynk & Co 03 TCR", 2019, 9999), ("Peugeot 308 TCR", 2018, 2021),
        ("Alfa Romeo Giulietta TCR", 2018, 2022),
        ("Volkswagen Golf GTI TCR", 2017, 2022), ("Toyota Corolla GR Sport", 2019, 9999),
        ("BMW 330i M Sport", 2019, 2022), ("Ford Focus ST", 2017, 9999),
    ],
    "stock": [
        ("Chevrolet Lumina", 1990, 1994), ("Chevrolet Monte Carlo", 1995, 2007),
        ("Ford Thunderbird", 1990, 1997), ("Ford Taurus", 1998, 2005),
        ("Ford Fusion", 2006, 2018), ("Pontiac Grand Prix", 1990, 2004),
        ("Dodge Intrepid", 2001, 2004), ("Dodge Charger", 2005, 2012),
        ("Toyota Camry", 2007, 9999), ("Chevrolet Impala SS", 2007, 2012),
        ("Chevrolet SS", 2013, 2017), ("Chevrolet Camaro ZL1", 2018, 9999),
        ("Ford Mustang", 2019, 9999),
    ],
}

# Вымышленные чемпионаты. dist — дистанция в км, hours — длительность гонки,
# speed — средняя скорость на круге (для stock считается по типу трассы)
SERIES = [
    dict(cls="formula", years=(2000, CUR_YEAR), races=10, teams=11, cars=(2, 2),
         dist=(130, 170), speed=180, hp=(250, 620), kg=(550, 760),
         types=("permanent", "street"), min_len=2.5, age=(16, 30)),
    dict(cls="hypercar", years=(2021, CUR_YEAR), races=8, teams=8, cars=(2, 2),
         hours=(6, 6), long_race=24, speed=200, hp=(670, 700), kg=(1030, 1100),
         types=("permanent",), min_len=4.0, age=(20, 45)),
    dict(cls="gt", years=(2000, CUR_YEAR), races=8, teams=12, cars=(1, 3),
         hours=(1, 3), long_race=24, speed=165, hp=(450, 600), kg=(1150, 1350),
         types=("permanent", "street"), min_len=3.0, age=(18, 55)),
    dict(cls="touring", years=(1995, CUR_YEAR), races=10, teams=10, cars=(2, 2),
         dist=(45, 70), speed=145, hp=(280, 380), kg=(1100, 1300),
         types=("permanent", "street"), min_len=1.8, age=(17, 50)),
    dict(cls="stock", years=(1990, CUR_YEAR), races=10, teams=14, cars=(1, 3),
         dist=(400, 800), speed=None, hp=(550, 850), kg=(1450, 1600),
         types=("oval", "permanent"), min_len=0.8, age=(18, 52)),
]

STATUS_WEIGHTS = {  # finished / dnf / dsq / dns
    "formula": (0.84, 0.13, 0.01, 0.02), "hypercar": (0.80, 0.17, 0.01, 0.02),
    "gt": (0.82, 0.15, 0.01, 0.02), "touring": (0.86, 0.11, 0.01, 0.02),
    "stock": (0.80, 0.17, 0.01, 0.02),
}

# ---------------------------------------------------------------- утилиты


def qid(url):
    return url.rsplit("/", 1)[-1]


def qnum(q):
    return int(q[1:]) if q[1:].isdigit() else 10 ** 9


def val(row, key):
    v = row.get(key)
    return v["value"] if v else None


def digest(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def is_label(s):
    """Без английской подписи сервис меток возвращает сам QID."""
    return bool(s) and not re.fullmatch(r"Q\d+", s) and not s.startswith("http")


def wd_date(s):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})T", s or "")
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return datetime.date(y, max(mo, 1), max(d, 1))
    except ValueError:
        return None


def wd_year(s):
    d = wd_date(s)
    return d.year if d else None


def years_ago(n):
    try:
        return TODAY.replace(year=TODAY.year - n)
    except ValueError:          # 29 февраля
        return TODAY.replace(year=TODAY.year - n, day=28)


def wiki_title(url):
    t = url.split("/wiki/", 1)[-1].split("#", 1)[0]
    return urllib.parse.unquote(t).replace("_", " ")


def laptime_ms(s):
    sec = 0.0
    for part in s.split(":"):
        sec = sec * 60 + float(part)
    return int(round(sec * 1000))


def fmt_interval(ms):
    if ms is None:
        return None
    s, ms = divmod(int(ms), 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return "%02d:%02d:%02d.%03d" % (h, m, s, ms)


def norm_country(name):
    if not name:
        return None
    return COUNTRY_ALIASES.get(name, name)


def pick_country(cands):
    """cands — пары (страна, упразднена ли). Существующие государства важнее."""
    cur = sorted({norm_country(c) for c, gone in cands if not gone and is_label(c)})
    old = sorted({norm_country(c) for c, gone in cands if gone and is_label(c)})
    return (cur or old or [None])[0]


def sundays(year, n, rnd):
    """n воскресений с марта по ноябрь, примерно равномерно."""
    start, end = datetime.date(year, 3, 1), datetime.date(year, 11, 30)
    span = (end - start).days
    out = []
    for i in range(n):
        d = start + datetime.timedelta(days=int(span * (i + rnd.uniform(0.1, 0.9)) / n))
        d += datetime.timedelta(days=(6 - d.weekday()) % 7)
        out.append(d)
    return sorted(set(out))


class Progress:
    def __init__(self, title, total):
        self.title, self.total, self.done = title, max(total, 1), 0
        self.draw()

    def step(self, n=1):
        self.done += n
        self.draw()

    def draw(self):
        pct = min(100, self.done * 100 // self.total)
        bar = "#" * (pct // 4) + "." * (25 - pct // 4)
        sys.stdout.write("\r  %-24s [%s] %3d%%  %d/%d" %
                         (self.title, bar, pct, self.done, self.total))
        sys.stdout.flush()

    def close(self):
        sys.stdout.write("\n")


# ------------------------------------------------------------- обращения


class Fetcher:
    """HTTP с кэшем на диске. Ошибки не кэшируются."""

    def __init__(self, cache_dir):
        self.cache = cache_dir
        self.last = {}
        os.makedirs(cache_dir, exist_ok=True)

    def cached(self, name, load):
        path = os.path.join(self.cache, name + ".json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        data = load()
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(path + ".tmp", path)
        return data

    def http(self, url, data=None, headers=None, pause=0.5, retries=7):
        host = urllib.parse.urlsplit(url).netloc
        hdrs = {"User-Agent": UA}
        hdrs.update(headers or {})
        for attempt in range(retries):
            wait = self.last.get(host, 0) + pause - time.time()
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(url, data=data, headers=hdrs)
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    res = json.load(r)
                self.last[host] = time.time()
                return res
            except urllib.error.HTTPError as e:
                self.last[host] = time.time()
                if e.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                    raise
                delay = int(e.headers.get("Retry-After") or 0) or 20 * (attempt + 1)
                sys.stdout.write("\n    %s ответил %d, жду %d с\n" % (host, e.code, delay))
                time.sleep(delay)
            except OSError:
                if attempt == retries - 1:
                    raise
                time.sleep(5 * (attempt + 1))

    def sparql(self, name, query):
        def load():
            body = urllib.parse.urlencode({"query": query}).encode()
            res = self.http(WD_ENDPOINT, body, {
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded"}, pause=1.0)
            return res["results"]["bindings"]
        return self.cached("wd_" + name, load)

    def sparql_values(self, name, qids, body, size=150):
        """Запрос с VALUES ?item { ... } пачками."""
        qids = sorted(set(qids), key=qnum)
        rows = []
        for i in range(0, len(qids), size):
            values = " ".join("wd:" + q for q in qids[i:i + size])
            rows += self.sparql("%s_%s" % (name, digest(values)), body % values)
        return rows

    def f1_season(self, year):
        races, offset, total = {}, 0, None
        while total is None or offset < total:
            url = "%s/%d/results.json?limit=100&offset=%d" % (JOLPICA, year, offset)
            data = self.cached("f1_%d_%04d" % (year, offset),
                               lambda: self.http(url, pause=0.35)["MRData"])
            total = int(data["total"])
            for race in data["RaceTable"]["Races"]:
                rnd = int(race["round"])
                if rnd in races:
                    races[rnd]["Results"].extend(race["Results"])
                else:
                    races[rnd] = race
            offset += 100
        return [races[k] for k in sorted(races)]

    def wiki_qids(self, titles):
        """Заголовки статей английской Википедии -> QID (с учётом редиректов)."""
        titles = sorted(set(titles))
        out = {}
        for i in range(0, len(titles), 50):
            batch = titles[i:i + 50]
            query = urllib.parse.urlencode({
                "action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
                "redirects": 1, "format": "json", "titles": "|".join(batch)})
            q = self.cached("wiki_" + digest("|".join(batch)),
                            lambda: self.http(WIKI_API + "?" + query, pause=0.3)["query"])
            norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
            redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
            pages = {p["title"]: p.get("pageprops", {}).get("wikibase_item")
                     for p in q.get("pages", {}).values()}
            for t in batch:
                x = norm.get(t, t)
                x = redir.get(x, x)
                if pages.get(x):
                    out[t] = pages[x]
        return out


# ------------------------------------------------------------- запросы

Q_F1_DRIVER = """SELECT ?item ?placeLabel WHERE {
  VALUES ?item { %s }
  ?item wdt:P19 ?place .
  """ + LABEL + "}"

Q_F1_TEAM = """SELECT ?item ?inception ?dissolved ?parent WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item wdt:P571 ?inception }
  OPTIONAL { ?item wdt:P576 ?dissolved }
  OPTIONAL { ?item wdt:P749 ?parent }
}"""

Q_F1_TRACK = """SELECT ?item ?cls ?len ?inception ?opening WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item wdt:P31 ?cls }
  OPTIONAL { ?item p:P2043/psn:P2043/wikibase:quantityAmount ?len }
  OPTIONAL { ?item wdt:P571 ?inception }
  OPTIONAL { ?item wdt:P1619 ?opening }
}"""

Q_DRIVERS = """SELECT ?p ?pLabel ?birth ?death ?start WHERE {
  ?p wdt:P106 wd:Q10349745 ; wdt:P31 wd:Q5 ; wdt:P569 ?birth .
  OPTIONAL { ?p wdt:P570 ?death }
  OPTIONAL { ?p wdt:P2031 ?start }
  """ + LABEL + "}"

Q_DRIVER_CITIZEN = """SELECT ?p ?cLabel ?gone WHERE {
  ?p wdt:P106 wd:Q10349745 ; wdt:P27 ?c .
  OPTIONAL { ?c wdt:P576 ?gone }
  """ + LABEL + "}"

Q_DRIVER_PLACE = """SELECT ?p ?placeLabel WHERE {
  ?p wdt:P106 wd:Q10349745 ; wdt:P19 ?place .
  """ + LABEL + "}"

Q_TEAMS = """SELECT ?t ?tLabel ?cLabel ?cgone ?inception ?dissolved ?parent WHERE {
  ?t wdt:P31/wdt:P279* wd:Q20074337 ; wdt:P17 ?c .
  OPTIONAL { ?c wdt:P576 ?cgone }
  OPTIONAL { ?t wdt:P571 ?inception }
  OPTIONAL { ?t wdt:P576 ?dissolved }
  OPTIONAL { ?t wdt:P749 ?parent }
  """ + LABEL + "}"

Q_TRACKS = """SELECT ?t ?tLabel ?cls ?cLabel ?cgone ?len ?inception ?opening WHERE {
  VALUES ?cls { %s }
  ?t wdt:P31 ?cls ; wdt:P17 ?c .
  OPTIONAL { ?c wdt:P576 ?cgone }
  OPTIONAL { ?t p:P2043/psn:P2043/wikibase:quantityAmount ?len }
  OPTIONAL { ?t wdt:P571 ?inception }
  OPTIONAL { ?t wdt:P1619 ?opening }
  """ % " ".join("wd:" + c for c in WD_TRACK_CLASSES) + LABEL + "}"

# ------------------------------------------------------------- F1


def map_status(r):
    """Статус Jolpica -> finished / dnf / dsq / dns; None — не прошёл квалификацию."""
    pt, status = r.get("positionText", ""), r.get("status", "")
    if pt == "F" or status.startswith(("Did not qualify", "Did not prequalify")):
        return None
    if pt == "W" or status in ("Did not start", "Withdrew"):
        return "dns"
    if pt in ("D", "E") or status in ("Disqualified", "Excluded"):
        return "dsq"
    if pt.isdigit():
        return "finished"
    return "dnf"


def collect_f1(f):
    years = list(range(F1_FIRST, CUR_YEAR + 1))
    bar = Progress("сезоны F1", len(years))
    races = []
    for y in years:
        races += f.f1_season(y)
        bar.step()
    bar.close()
    return races


def parse_f1(races, log):
    """Сырые гонки -> справочники и очищенные заезды."""
    drivers, teams, tracks, events = {}, {}, {}, []
    for race in races:
        date = datetime.date.fromisoformat(race["date"])
        if date > TODAY:
            continue
        c = race["Circuit"]
        cid = c["circuitId"]
        tracks.setdefault(cid, {
            "name": c["circuitName"], "country": norm_country(c["Location"]["country"]),
            "city": c["Location"].get("locality"), "url": c.get("url"),
            "first": date.year})
        rows = []
        for r in race["Results"]:
            status = map_status(r)
            if status is None:
                log["F1: не прошли квалификацию (не заезд)"] += 1
                continue
            d, k = r["Driver"], r["Constructor"]
            if d["driverId"] not in drivers:
                nat = d.get("nationality", "")
                if nat not in NATIONALITY:
                    log["F1: неизвестная национальность " + nat] += 1
                dob = d.get("dateOfBirth")
                drivers[d["driverId"]] = {
                    "name": ("%s %s" % (d.get("givenName", ""), d["familyName"])).strip(),
                    "birth": datetime.date.fromisoformat(dob) if dob else None,
                    "country": NATIONALITY.get(nat, nat), "url": d.get("url")}
            if k["constructorId"] not in teams:
                nat = k.get("nationality", "")
                teams[k["constructorId"]] = {
                    "name": k["name"], "country": NATIONALITY.get(nat, nat),
                    "url": k.get("url")}
            fl = r.get("FastestLap", {}).get("Time", {}).get("time")
            rows.append({
                "driver": d["driverId"], "team": k["constructorId"],
                "number": r.get("number") or "?" + d["driverId"],
                "status": status, "raw": r.get("status", ""),
                "pos": int(r["positionText"]) if status == "finished" else None,
                "grid": int(r.get("grid") or 0),
                "laps": int(r.get("laps") or 0) if status != "dns" else 0,
                "total": (int(r["Time"]["millis"]) if status == "finished"
                          and r.get("Time", {}).get("millis") else None),
                "best": laptime_ms(fl) if fl and status in ("finished", "dnf") else None,
            })
        events.append({"date": date, "season": int(race["season"]),
                       "circuit": cid, "rows": rows})
    return drivers, teams, tracks, events


def dedupe_f1(events, drivers, log):
    """Одна строка на пилота, на машину и на финишное место в гонке."""
    for ev in events:
        rows = [e for e in ev["rows"]
                if drivers[e["driver"]]["birth"] and drivers[e["driver"]]["birth"] >= BIRTH_MIN]
        log["F1: заезды пилотов без даты рождения или родившихся до 1900"] += \
            len(ev["rows"]) - len(rows)
        rows.sort(key=lambda e: (e["pos"] is None, e["pos"] or 0, -e["laps"]))
        seen_d, seen_car, seen_pos, kept = set(), set(), set(), []
        for e in rows:
            car = (e["team"], e["number"])
            if e["driver"] in seen_d or car in seen_car or (e["pos"] and e["pos"] in seen_pos):
                log["F1: совместные заезды на одной машине (оставлена одна строка)"] += 1
                continue
            seen_d.add(e["driver"])
            seen_car.add(car)
            if e["pos"]:
                seen_pos.add(e["pos"])
            kept.append(e)
        ev["rows"] = kept
    return [ev for ev in events if ev["rows"]]


def fix_grid(rows, log, tag):
    """Стартовые места 1..n без повторов; 0 (старт с пит-лейна) — в конец."""
    used, rest = set(), []
    for e in sorted(rows, key=lambda e: (e["grid"] <= 0, e["grid"])):
        if POS[0] <= e["grid"] <= POS[1] and e["grid"] not in used:
            used.add(e["grid"])
        else:
            rest.append(e)
    nxt = max(used, default=0)
    for e in rest:
        nxt += 1
        e["grid"] = nxt
        log[tag + ": стартовое место назначено (пит-лейн, повтор или пусто)"] += 1


def fill_f1_times(ev, track_len, rnd, log):
    rows = ev["rows"]
    fin = sorted((e for e in rows if e["status"] == "finished"), key=lambda e: e["pos"])
    lead = fin[0] if fin else None
    lead_laps = lead["laps"] if lead else max([e["laps"] for e in rows] + [1])
    lead_ms = lead["total"] if lead else None
    if not lead_ms:
        bests = sorted(e["best"] for e in rows if e["best"])
        if bests:
            avg = bests[len(bests) // 2] * 1.04
        elif track_len:
            avg = track_len / 150 * 3600_000
        else:
            avg = 120_000
        lead_ms = int(avg * max(lead_laps, 1))
        if lead:
            lead["total"] = lead_ms
            log["F1: время победителя оценено"] += 1
    avg = lead_ms / max(lead_laps, 1)
    prev = 0
    for e in fin:
        if e["total"] is None:
            if e["laps"] >= lead_laps:
                est = max(prev, lead_ms) + rnd.uniform(1, 30) * 1000
            elif "Lap" in e["raw"] or e["raw"] == "Finished":
                est = max(prev + rnd.uniform(1, 4) * 1000,
                          lead_ms + avg * rnd.uniform(0.05, 0.3))
            else:                       # классифицирован, хотя сошёл
                est = avg * e["laps"] * rnd.uniform(1.01, 1.05)
            e["total"] = int(est)
            log["F1: итоговое время оценено (в источнике нет)"] += 1
        prev = max(prev, e["total"])
    for e in rows:
        if e["status"] not in ("finished", "dnf") or e["laps"] == 0:
            e["best"] = None
            continue
        own = e["total"] / e["laps"] if e["status"] == "finished" else avg * rnd.uniform(1.0, 1.04)
        if e["best"] is None:
            e["best"] = int(own * rnd.uniform(0.955, 0.99))
            log["F1: лучший круг оценён (в источнике нет)"] += 1
        if e["status"] == "finished" and e["best"] * e["laps"] > e["total"]:
            e["best"] = int(e["total"] / e["laps"] * 0.99)
            log["F1: лучший круг уменьшен до согласия с итоговым временем"] += 1
        e["best"] = min(max(e["best"], BEST_MS[0]), BEST_MS[1])


def f1_car_specs(season, indy, rnd):
    if indy and season <= 1960:
        hp, kg = INDY_ROADSTER
    else:
        hp, kg = next((h, k) for until, h, k in F1_ERAS if season <= until)
    return rnd.randint(*hp), rnd.randint(*kg)


# ------------------------------------------------------------- Wikidata


def enrich_f1(f, drivers, teams, tracks):
    print("Шаг 2/4. Сопоставление F1 с Wikidata")
    for kind, items in (("пилоты", drivers), ("команды", teams), ("трассы", tracks)):
        urls = {k: wiki_title(v["url"]) for k, v in items.items() if v.get("url")}
        found = f.wiki_qids(urls.values())
        for k, t in urls.items():
            items[k]["qid"] = found.get(t)
        print("  %-8s найдено в Wikidata %d из %d" %
              (kind, sum(1 for v in items.values() if v.get("qid")), len(items)))

    by_q = {v["qid"]: v for v in drivers.values() if v.get("qid")}
    for r in f.sparql_values("f1_driver", by_q, Q_F1_DRIVER):
        place = val(r, "placeLabel")
        if is_label(place):
            by_q[qid(val(r, "item"))].setdefault("city", place)

    by_q = {v["qid"]: v for v in teams.values() if v.get("qid")}
    for r in f.sparql_values("f1_team", by_q, Q_F1_TEAM):
        t = by_q[qid(val(r, "item"))]
        y = wd_year(val(r, "inception"))
        if y and (t.get("founded") is None or y < t["founded"]):
            t["founded"] = y
        if val(r, "dissolved"):
            t["dissolved"] = wd_year(val(r, "dissolved"))
        if val(r, "parent"):
            t["parent_qid"] = qid(val(r, "parent"))

    by_q = {v["qid"]: v for v in tracks.values() if v.get("qid")}
    for r in f.sparql_values("f1_track", by_q, Q_F1_TRACK):
        t = by_q[qid(val(r, "item"))]
        if val(r, "cls") and qid(val(r, "cls")) == "Q926439":
            t["street"] = True
        if val(r, "len"):
            km = float(val(r, "len")) / 1000
            if LENGTH[0] <= km <= LENGTH[1]:
                t["len"] = max(t.get("len") or 0, km)
        for key in ("opening", "inception"):
            y = wd_year(val(r, key))
            if y and (t.get("opened") is None or y < t["opened"]):
                t["opened"] = y


def collect_pools(f):
    print("Шаг 3/4. Гонщики, трассы и команды других серий (Wikidata)")
    drivers = {}
    for r in f.sparql("drivers", Q_DRIVERS):
        q = qid(val(r, "p"))
        if q in drivers:
            continue
        drivers[q] = {"qid": q, "name": val(r, "pLabel"), "birth": wd_date(val(r, "birth")),
                      "death": wd_date(val(r, "death")), "start": wd_year(val(r, "start")),
                      "cands": []}
    for r in f.sparql("driver_citizen", Q_DRIVER_CITIZEN):
        d = drivers.get(qid(val(r, "p")))
        if d:
            d["cands"].append((val(r, "cLabel"), bool(val(r, "gone"))))
    for r in f.sparql("driver_place", Q_DRIVER_PLACE):
        d = drivers.get(qid(val(r, "p")))
        if d and is_label(val(r, "placeLabel")):
            d.setdefault("city", val(r, "placeLabel"))
    for d in drivers.values():
        d["country"] = pick_country(d.pop("cands"))
    print("  гонщиков   %d" % len(drivers))

    teams = {}
    for r in f.sparql("teams", Q_TEAMS):
        q = qid(val(r, "t"))
        t = teams.setdefault(q, {"qid": q, "name": val(r, "tLabel"), "cands": [],
                                 "founded": None, "dissolved": None})
        t["cands"].append((val(r, "cLabel"), bool(val(r, "cgone"))))
        y = wd_year(val(r, "inception"))
        if y and (t["founded"] is None or y < t["founded"]):
            t["founded"] = y
        if val(r, "dissolved"):
            t["dissolved"] = wd_year(val(r, "dissolved"))
        if val(r, "parent"):
            t["parent_qid"] = qid(val(r, "parent"))
    for t in teams.values():
        t["country"] = pick_country(t.pop("cands"))
    print("  команд     %d" % len(teams))

    tracks = {}
    for r in f.sparql("tracks", Q_TRACKS):
        q = qid(val(r, "t"))
        t = tracks.setdefault(q, {"qid": q, "name": val(r, "tLabel"), "cands": [],
                                  "classes": set(), "len": None, "opened": None})
        t["cands"].append((val(r, "cLabel"), bool(val(r, "cgone"))))
        t["classes"].add(qid(val(r, "cls")))
        if val(r, "len"):
            km = float(val(r, "len")) / 1000
            if LENGTH[0] <= km <= LENGTH[1]:
                t["len"] = max(t["len"] or 0, km)
        for key in ("opening", "inception"):
            y = wd_year(val(r, key))
            if y and (t["opened"] is None or y < t["opened"]):
                t["opened"] = y
    for q in [q for q, t in tracks.items() if NOT_CAR_TRACK.search(t["name"] or "")]:
        del tracks[q]
    for t in tracks.values():
        t["country"] = pick_country(t.pop("cands"))
        if "Q926439" in t["classes"]:
            t["type"] = "street"
        elif OVAL_NAME.search(t["name"] or "") and t["country"] in OVAL_COUNTRIES:
            t["type"] = "oval"
        else:
            t["type"] = "permanent"
    print("  трасс      %d" % len(tracks))
    return drivers, teams, tracks


# ------------------------------------------------------------- сборка


class Builder:
    def __init__(self, rnd, log):
        self.rnd, self.log = rnd, log
        self.teams, self.tracks, self.drivers, self.cars = [], [], [], []
        self.entries = []
        self.race_keys = set()            # (track, date) — уже занятые гонки
        self.busy = defaultdict(set)      # пилот -> даты гонок
        self.city_pool = defaultdict(list)

    # --- справочники

    def add_team(self, t):
        t["seasons"] = []
        self.teams.append(t)
        return t

    def add_track(self, t):
        t["seasons"] = []
        self.tracks.append(t)
        return t

    def add_driver(self, d):
        d["seasons"] = []
        d.setdefault("classes", set())
        self.drivers.append(d)
        return d

    def add_car(self, team, season, model, cls, hp, kg):
        car = {"team": team, "season": season, "model": model, "cls": cls,
               "hp": hp, "kg": kg}
        team["seasons"].append(season)
        self.cars.append(car)
        return car

    def add_entry(self, driver, car, track, date, e):
        driver["seasons"].append(date.year)
        driver["classes"].add(car["cls"])
        track["seasons"].append(date.year)
        self.busy[id(driver)].add(date)
        e.update(driver=driver, car=car, track=track, date=date)
        self.entries.append(e)

    # --- реальная F1

    def load_f1(self, drivers, teams, tracks, events, by_qid):
        rnd, log = self.rnd, self.log
        names = Counter(t["name"] for t in teams.values())
        tmap, trmap, dmap, cars = {}, {}, {}, {}
        for cid, t in teams.items():
            name = t["name"] if names[t["name"]] == 1 else "%s (%s)" % (t["name"], cid)
            row = self.add_team({"name": name, "country": t["country"], "qid": t.get("qid"),
                                 "founded": t.get("founded"), "dissolved": t.get("dissolved"),
                                 "parent_qid": t.get("parent_qid"), "f1": True})
            tmap[cid] = row
            if row["qid"]:
                by_qid[row["qid"]] = row
        for cid, t in tracks.items():
            if cid in F1_STREET or t.get("street"):
                kind = "street"
            elif cid in F1_OVAL:
                kind = "oval"
            else:
                kind = "permanent"
            row = self.add_track({"name": t["name"], "country": t["country"], "qid": t.get("qid"),
                                  "len": t.get("len"), "opened": t.get("opened"), "type": kind,
                                  "f1": cid})
            trmap[cid] = row
            if t.get("city"):
                self.city_pool[t["country"]].append(t["city"])
            if row["qid"]:
                by_qid[row["qid"]] = row
        for did, d in drivers.items():
            if not d["birth"] or d["birth"] < BIRTH_MIN:
                log["F1: пилоты без даты рождения или родившиеся до 1900 (не проходят CHECK)"] += 1
                continue
            dmap[did] = self.add_driver({"name": d["name"], "birth": d["birth"],
                                         "country": d["country"], "city": d.get("city"),
                                         "qid": d.get("qid"), "license": "super", "f1": True})
            if d.get("city"):
                self.city_pool[d["country"]].append(d["city"])
            if d.get("qid"):
                by_qid[d["qid"]] = dmap[did]

        for ev in events:
            track = trmap[ev["circuit"]]
            fix_grid(ev["rows"], log, "F1")
            fill_f1_times(ev, track.get("len"), rnd, log)
            self.race_keys.add((id(track), ev["date"]))
            for e in ev["rows"]:
                key = (e["team"], ev["season"], e["number"])
                if key not in cars:
                    team = tmap[e["team"]]
                    num = e["number"] if not e["number"].startswith("?") else str(len(cars) % 90 + 1)
                    hp, kg = f1_car_specs(ev["season"], ev["circuit"] == "indianapolis", rnd)
                    cars[key] = self.add_car(team, ev["season"], "%s %d #%s" %
                                             (team["name"], ev["season"], num),
                                             "formula", hp, kg)
                self.add_entry(dmap[e["driver"]], cars[key], track, ev["date"], {
                    "status": e["status"], "grid": e["grid"], "pos": e["pos"],
                    "laps": e["laps"], "best": e["best"], "total": e["total"]})
        last = max(ev["season"] for ev in events)
        for t in tmap.values():
            t["active"] = max(t["seasons"], default=0) >= last - 1

    # --- справочники из Wikidata

    def load_pools(self, drivers, teams, tracks, by_qid):
        log = self.log
        f1_names = {(d["name"].lower(), d["birth"]) for d in self.drivers}
        team_names = {t["name"].lower() for t in self.teams}
        track_names = {(t["name"].lower(), t["country"]) for t in self.tracks}
        born_max = years_ago(15)
        for d in sorted(drivers.values(), key=lambda d: qnum(d["qid"])):
            if d["qid"] in by_qid:
                continue
            if not is_label(d["name"]) or not d["birth"] or not d["country"]:
                log["Wikidata: гонщики без имени, даты рождения или страны"] += 1
                continue
            if not (BIRTH_MIN <= d["birth"] <= born_max):
                log["Wikidata: гонщики вне диапазона дат рождения"] += 1
                continue
            if (d["name"].lower(), d["birth"]) in f1_names:
                continue
            if d.get("city"):
                self.city_pool[d["country"]].append(d["city"])
            d["pool"] = True
            by_qid[d["qid"]] = self.add_driver(d)
        for t in sorted(teams.values(), key=lambda t: qnum(t["qid"])):
            if t["qid"] in by_qid or not is_label(t["name"]) or not t["country"]:
                continue
            if t["name"].lower() in team_names:
                continue
            team_names.add(t["name"].lower())
            t["pool"] = True
            by_qid[t["qid"]] = self.add_team(t)
        for t in sorted(tracks.values(), key=lambda t: qnum(t["qid"])):
            if t["qid"] in by_qid or not is_label(t["name"]) or not t["country"]:
                continue
            key = (t["name"].lower(), t["country"])
            if key in track_names:
                continue
            track_names.add(key)
            t["pool"] = True
            by_qid[t["qid"]] = self.add_track(t)

    # --- вымышленные чемпионаты

    def gen_length(self, kind):
        rnd = self.rnd
        if kind == "oval":
            return round(rnd.choice([0.85, 0.85, 1.0, 1.5, 1.5, 2.0, 2.4, 2.5, 4.0]) *
                         rnd.uniform(0.97, 1.03), 2)
        if kind == "street":
            return round(rnd.uniform(1.8, 5.5), 2)
        return round(rnd.triangular(2.0, 7.0, 4.2), 2)

    def track_len(self, t):
        if t.get("len") is None:
            t["len"] = self.gen_length(t["type"])
            t["len_fake"] = True
            self.log["досочинено: длина трассы"] += 1
        return t["len"]

    def lap_base_ms(self, s, t):
        km = self.track_len(t)
        if s["cls"] == "stock":
            speed = 145 if t["type"] != "oval" else (190 if km < 1.4 else 240 if km < 3.5 else 280)
        else:
            speed = s["speed"]
        return km / speed * 3600_000

    def eligible_team(self, t, season):
        if t.get("f1") and not t.get("pool"):
            return False
        if t.get("dissolved") and t["dissolved"] < season:
            return False
        return t.get("founded") is None or FOUNDED_MIN <= t["founded"] <= season

    def eligible_driver(self, d, season, ages):
        if not d.get("pool") or d.get("taken") == season:
            return False
        age = season - d["birth"].year
        if not ages[0] <= age <= ages[1]:
            return False
        if d.get("death") and d["death"].year <= season:
            return False
        if d.get("debut") and d["debut"] > season:
            return False
        if d.get("start") and d["start"] > season:
            return False
        return True

    def fake_driver(self, season, ages):
        """Если реальных гонщиков подходящего возраста не хватило."""
        rnd = self.rnd
        donors = [d for d in self.drivers if d.get("pool") and d.get("city")] or self.drivers
        first = rnd.choice(donors)["name"].split()[0]
        last = rnd.choice(donors)["name"].split()[-1]
        donor = rnd.choice(donors)
        birth = datetime.date(season - rnd.randint(ages[0] + 2, min(ages[1], ages[0] + 12)),
                              rnd.randint(1, 12), rnd.randint(1, 28))
        self.log["досочинено: гонщики (реальных не хватило)"] += 1
        return self.add_driver({"name": "%s %s" % (first, last), "birth": birth,
                                "country": donor["country"], "city": donor.get("city"),
                                "pool": True, "fake": True})

    def run_series(self, s):
        rnd, log = self.rnd, self.log
        cls = s["cls"]
        teams = [t for t in self.teams if t.get("pool")]
        drivers = [d for d in self.drivers if d.get("pool")]
        calendar, roster, prev_seats = [], [], {}
        y0, y1 = s["years"]
        for season in range(y0, y1 + 1):
            # команды: большая часть переходит в следующий сезон
            keep = [t for t in roster if rnd.random() < 0.85 and self.eligible_team(t, season)]
            kept = {id(t) for t in keep}
            pool = [t for t in teams if id(t) not in kept and self.eligible_team(t, season)]
            roster = keep + rnd.sample(pool, min(len(pool), max(0, s["teams"] - len(keep))))
            for t in roster:
                if t.get("founded") is None:
                    t["founded"] = max(FOUNDED_MIN, season - rnd.randint(0, 8))
                    t["founded_fake"] = True
            # трассы: календарь тоже частично сохраняется
            ok = [t for t in self.tracks if t["type"] in s["types"]
                  and (t["len"] is None or t["len"] >= s["min_len"])
                  and (t.get("opened") is None or t["opened"] <= season)
                  and (cls != "stock" or t["country"] == "United States")]
            if cls == "stock":
                ovals = [t for t in ok if t["type"] == "oval"]
                roads = [t for t in ok if t["type"] != "oval"]
                ok = ovals + rnd.sample(roads, min(4, len(roads)))
            ok_ids = {id(t) for t in ok}
            calendar = [t for t in calendar if id(t) in ok_ids and rnd.random() < 0.8]
            in_cal = {id(t) for t in calendar}
            extra = [t for t in ok if id(t) not in in_cal]
            rnd.shuffle(extra)
            calendar += extra[:max(0, s["races"] - len(calendar))]
            if not calendar:
                continue
            # машины и пилоты на сезон
            models = [m for m, a, b in MODELS[cls] if a <= season <= b]
            free = [d for d in drivers if self.eligible_driver(d, season, s["age"])]
            rnd.shuffle(free)
            seats, number = [], 1
            for t in roster:
                model = rnd.choice(models)
                for _ in range(rnd.randint(*s["cars"])):
                    car = self.add_car(t, season, "%s #%d" % (model, number), cls,
                                       rnd.randint(*s["hp"]), rnd.randint(*s["kg"]))
                    number += rnd.randint(1, 3)
                    old = prev_seats.get(id(t), [])
                    d = old.pop(0) if old else None
                    if d is None or rnd.random() > 0.75 or not self.eligible_driver(d, season, s["age"]):
                        d = None
                        while free and d is None:
                            x = free.pop()
                            if self.eligible_driver(x, season, s["age"]):
                                d = x
                        if d is None:
                            d = self.fake_driver(season, s["age"])
                            drivers.append(d)
                    d["taken"] = season
                    if d.get("debut") is None:
                        start, lo = d.get("start"), d["birth"].year + 15
                        if start and lo <= start <= season:
                            d["debut"] = start
                        else:
                            lo = max(lo + 1, season - 5)
                            d["debut"] = rnd.randint(min(lo, season), season)
                            d["debut_fake"] = True
                    seats.append((car, d, rnd.gauss(1, 0.004) * rnd.gauss(1, 0.003)))
            prev_seats = defaultdict(list)
            for car, d, _ in seats:
                prev_seats[id(car["team"])].append(d)
            for t in calendar:
                if t.get("opened") is None:
                    t["opened"] = max(OPENED_MIN, season - rnd.randint(0, 30))
                    t["opened_fake"] = True
            dates = sundays(season, len(calendar), rnd)
            for t, date in zip(calendar, dates):
                if date > TODAY:
                    continue
                for shift in (0, -1, 7, 6, 14):
                    dd = date + datetime.timedelta(days=shift)
                    if (id(t), dd) not in self.race_keys and dd.year == season:
                        self.race_keys.add((id(t), dd))
                        self.fake_race(s, t, dd, seats)
                        break
                else:
                    log["вымышленные гонки: не нашлось свободной даты"] += 1

    def fake_race(self, s, track, date, seats):
        rnd = self.rnd
        base = self.lap_base_ms(s, track)
        if not 12_000 <= base <= 14 * 60_000:
            self.log["вымышленные гонки: пропущены (круг вне 10 с–15 мин)"] += 1
            return
        if "dist" in s:
            laps = max(5, round(rnd.uniform(*s["dist"]) / track["len"]))
        else:
            hours = s["long_race"] if (s.get("long_race") and track["len"] >= 7
                                       and rnd.random() < 0.5) else rnd.uniform(*s["hours"])
            laps = max(5, int(hours * 3600_000 / (base * 1.02)))
        laps = min(laps, 950)
        while base * 1.02 * laps < 3 * 60_000:
            laps += 5
        cars = [x for x in seats if date not in self.busy[id(x[1])]]
        pace = {id(c): p * rnd.uniform(0.997, 1.003) for c, d, p in cars}
        w = STATUS_WEIGHTS[s["cls"]]
        res = []
        for car, d, _ in cars:
            avg = base * 1.02 * pace[id(car)]
            st = rnd.choices(("finished", "dnf", "dsq", "dns"), w)[0]
            res.append({"car": car, "driver": d, "status": st, "avg": avg})
        lead = min((r["avg"] for r in res if r["status"] == "finished"), default=base)
        t_lead = lead * laps
        for r in res:
            if r["status"] == "finished":
                r["laps"] = min(laps, -(-int(t_lead) // int(r["avg"])))
                r["total"] = int(r["laps"] * r["avg"])
                r["best"] = int(r["avg"] / 1.02 * rnd.uniform(0.985, 1.0))
            elif r["status"] == "dnf":
                r["laps"] = int(laps * rnd.random() ** 1.5)
                r["best"] = (int(r["avg"] / 1.02 * rnd.uniform(0.985, 1.01))
                             if r["laps"] and rnd.random() < 0.9 else None)
            elif r["status"] == "dsq":
                r["laps"] = rnd.choice([laps, int(laps * rnd.uniform(0.5, 1))])
            else:
                r["laps"] = 0
        order = sorted((r for r in res if r["status"] == "finished"),
                       key=lambda r: (-r["laps"], r["total"]))
        for i, r in enumerate(order, 1):
            r["pos"] = i
        for i, r in enumerate(sorted(res, key=lambda r: r["avg"] * rnd.uniform(0.99, 1.01)), 1):
            r["grid"] = i
        for r in res:
            self.add_entry(r["driver"], r["car"], track, date, {
                "status": r["status"], "grid": r["grid"], "pos": r.get("pos"),
                "laps": r["laps"], "best": r.get("best"), "total": r.get("total")})

    # --- согласование и досочинение остального

    def finalize(self):
        rnd, log = self.rnd, self.log
        born_max = years_ago(15)
        for t in self.teams:
            first = min(t["seasons"], default=None)
            f = t.get("founded")
            if f is not None and not FOUNDED_MIN <= f <= CUR_YEAR:
                f = None
            if f is None:
                f = (max(FOUNDED_MIN, first - rnd.randint(0, 8)) if first
                     else rnd.randint(1950, 2020))
                log["досочинено: год основания команды"] += 1
            elif first and f > first:
                f = first
                log["Wikidata: год основания команды позже первого сезона (сдвинут)"] += 1
            t["founded"] = f
            if "active" not in t:
                last = max(t["seasons"], default=None)
                t["active"] = not t.get("dissolved") and (last is None or last >= CUR_YEAR - 2)
        for t in self.tracks:
            self.track_len(t)
            first = min(t["seasons"], default=None)
            o = t.get("opened")
            if o is not None and not OPENED_MIN <= o <= CUR_YEAR:
                o = None
            if o is None:
                o = (max(OPENED_MIN, first - rnd.randint(0, 15)) if first
                     else rnd.randint(1925, 2020))
                log["досочинено: год открытия трассы"] += 1
            elif first and o > first:
                o = first
                log["Wikidata: трасса открыта позже первой гонки (год сдвинут)"] += 1
            t["opened"] = o
        # в Wikidata местом рождения иногда указана сама страна — это не город
        countries = {x["country"] for x in self.drivers + self.teams + self.tracks}
        countries |= set(NATIONALITY.values()) | set(COUNTRY_ALIASES)
        pools = {c: [x for x in p if x not in countries] for c, p in self.city_pool.items()}
        kept = []
        for d in self.drivers:
            if not d.get("city") or d["city"] in countries:
                pool = pools.get(d["country"])
                if not pool and not d["seasons"]:
                    log["Wikidata: гонщики без города и без городов их страны (убраны)"] += 1
                    continue
                d["city"] = rnd.choice(pool) if pool else d["country"]
                log["досочинено: город рождения (город той же страны)"] += 1
            kept.append(d)
        self.drivers = kept
        for d in self.drivers:
            if d.get("f1") and d["seasons"]:
                d["debut"] = min(d["seasons"])
            elif d.get("debut") is None:
                lo = d["birth"].year + 15
                start = d.get("start")
                if start and lo <= start <= CUR_YEAR:
                    d["debut"] = start
                else:
                    d["debut"] = min(CUR_YEAR, lo + rnd.randint(1, 9))
                    log["досочинено: год дебюта"] += 1
            d["debut"] = max(d["debut"], d["birth"].year + 15)
            if not d.get("license"):
                d["license"] = self.license_for(d)
            assert d["birth"] <= born_max
        self.link_parents()

    def license_for(self, d):
        rnd = self.rnd
        top = d["classes"]
        if "hypercar" in top:
            return rnd.choice(["super", "A", "A"])
        if "gt" in top or "formula" in top:
            return rnd.choice(["A", "A", "B"])
        if top:
            return rnd.choice(["B", "B", "C"])
        return rnd.choices(LICENSES, (0.03, 0.15, 0.27, 0.30, 0.25))[0]

    def link_parents(self):
        """Реальные связи «материнская компания» из Wikidata + немного вымышленных.
        Команды упорядочены так, что у родителя id меньше, чем у дочерней."""
        rnd, log = self.rnd, self.log
        by_qid = {t["qid"]: t for t in self.teams if t.get("qid")}
        for t in self.teams:
            p = by_qid.get(t.get("parent_qid"))
            t["parent"] = p if p is not None and p is not t else None
        # разрываем циклы и считаем глубину
        for t in self.teams:
            seen, x = set(), t
            while x["parent"] is not None:
                if id(x) in seen:
                    x["parent"] = None
                    break
                seen.add(id(x))
                x = x["parent"]
        log["Wikidata: реальные связи команд с материнскими"] += sum(
            1 for t in self.teams if t["parent"] is not None)

        def depth(t):
            n = 0
            while t["parent"] is not None:
                t, n = t["parent"], n + 1
            return n
        self.teams.sort(key=lambda t: (depth(t), not t.get("f1"), t["founded"], t["name"]))
        by_country = defaultdict(list)
        for t in self.teams:
            older = [p for p in by_country[t["country"]] if p["founded"] <= t["founded"]]
            if t["parent"] is None and older and rnd.random() < 0.07:
                t["parent"] = rnd.choice(older)
                log["досочинено: связь команды с материнской"] += 1
            by_country[t["country"]].append(t)
        # родитель должен идти раньше: при вымышленных связях это так по построению
        pos = {id(t): i for i, t in enumerate(self.teams)}
        for t in self.teams:
            if t["parent"] is not None and pos[id(t["parent"])] > pos[id(t)]:
                t["parent"] = None
                log["связь с материнской отброшена (порядок id)"] += 1

    # --- таблицы

    def tables(self):
        for i, t in enumerate(self.teams, 1):
            t["id"] = i
        for i, t in enumerate(sorted(self.tracks, key=lambda t: (not t.get("f1"), t["opened"], t["name"])), 1):
            t["id"] = i
        drivers = sorted(self.drivers, key=lambda d: (not d.get("f1"), d["birth"], d["name"]))
        for i, d in enumerate(drivers, 1):
            d["id"] = i
        cars = sorted(self.cars, key=lambda c: (c["season"], c["cls"], c["team"]["id"], c["model"]))
        for i, c in enumerate(cars, 1):
            c["id"] = i
        entries = sorted(self.entries, key=lambda e: (e["date"], e["track"]["id"], e["grid"]))
        contracts = self.contracts(entries)
        return {
            "team": [(t["id"], t["name"], t["country"], t["founded"],
                      "true" if t["active"] else "false",
                      t["parent"]["id"] if t["parent"] else None) for t in self.teams],
            "track": [(t["id"], t["name"], t["country"], "%.2f" % t["len"], t["type"], t["opened"])
                      for t in sorted(self.tracks, key=lambda t: t["id"])],
            "driver": [(d["id"], d["name"], d["birth"].isoformat(), d["city"], d["country"],
                        d["license"], d["debut"]) for d in drivers],
            "car": [(c["id"], c["model"], c["season"], c["cls"], c["hp"], c["kg"], c["team"]["id"])
                    for c in cars],
            "race_entry": [(e["driver"]["id"], e["car"]["id"], e["track"]["id"], e["status"],
                            e["grid"], e["pos"], fmt_interval(e["best"]), fmt_interval(e["total"]),
                            e["date"].isoformat(), e["laps"]) for e in entries],
            "contract": [(c["driver"]["id"], c["team"]["id"], c["start"].isoformat(),
                          c["end"].isoformat() if c["end"] else None) for c in contracts],
        }, entries, contracts

    @staticmethod
    def contracts(entries):
        """Периоды пилота в команде: подряд идущие гонки за одну команду.
        Если пилот ушёл и вернулся — это новый период. Последний период
        открыт (без даты конца), если пилот ехал в этом или прошлом сезоне
        и команда активна."""
        by_driver = defaultdict(list)
        for e in entries:                     # уже по возрастанию даты
            by_driver[id(e["driver"])].append(e)
        out = []
        for races in by_driver.values():
            cur = None
            for e in races:
                team = e["car"]["team"]
                if cur is not None and cur["team"] is team:
                    cur["end"] = e["date"]
                else:
                    cur = {"driver": e["driver"], "team": team,
                           "start": e["date"], "end": e["date"]}
                    out.append(cur)
            if cur["end"].year >= CUR_YEAR - 1 and cur["team"]["active"]:
                cur["end"] = None
        out.sort(key=lambda c: (c["driver"]["id"], c["start"]))
        return out


# ------------------------------------------------------------- проверка


def validate(b, entries, contracts):
    """Те же правила, что в define_restrictions.sql, плюс согласованность таблиц."""
    errors = Counter()
    born_max = years_ago(15)

    def check(cond, msg):
        if not cond:
            errors[msg] += 1

    names = Counter(t["name"] for t in b.teams)
    check(all(v == 1 for v in names.values()), "team: повтор имени")
    for t in b.teams:
        check(FOUNDED_MIN <= t["founded"] <= CUR_YEAR, "team: founded_year")
        check(t["parent"] is None or t["parent"]["id"] < t["id"], "team: родитель после дочерней")
        check(t["country"], "team: country")
    keys = Counter((t["name"], t["country"]) for t in b.tracks)
    check(all(v == 1 for v in keys.values()), "track: повтор (name, country)")
    for t in b.tracks:
        check(LENGTH[0] <= t["len"] <= LENGTH[1], "track: length_km")
        check(t["type"] in TRACK_TYPES, "track: track_type")
        check(OPENED_MIN <= t["opened"] <= CUR_YEAR, "track: opened_year")
    for d in b.drivers:
        check(BIRTH_MIN <= d["birth"] <= born_max, "driver: birth_date")
        check(d["birth"].year + 15 <= d["debut"] <= CUR_YEAR, "driver: debut_year")
        check(d["license"] in LICENSES, "driver: license_class")
        check(d["city"] and d["country"] and d["name"], "driver: пустые поля")
    cars = Counter((c["model"], c["season"], c["team"]["id"]) for c in b.cars)
    check(all(v == 1 for v in cars.values()), "car: повтор (model, season, team)")
    for c in b.cars:
        check(SEASON_MIN <= c["season"] <= CUR_YEAR + 1, "car: season_year")
        check(c["cls"] in CAR_CLASSES, "car: car_class")
        check(HP[0] <= c["hp"] <= HP[1], "car: horsepower")
        check(WEIGHT[0] <= c["kg"] <= WEIGHT[1], "car: weight_kg")
        check(c["team"]["founded"] <= c["season"], "согласованность: команда основана позже сезона")
    pk, car_k, grid_k, fin_k = Counter(), Counter(), Counter(), Counter()
    for e in entries:
        race = (e["track"]["id"], e["date"])
        pk[(e["driver"]["id"], e["date"])] += 1
        car_k[race + (e["car"]["id"],)] += 1
        grid_k[race + (e["grid"],)] += 1
        if e["pos"] is not None:
            fin_k[race + (e["pos"],)] += 1
        st, laps, best, total = e["status"], e["laps"], e["best"], e["total"]
        check(RACE_MIN <= e["date"] <= TODAY, "race_entry: race_date")
        check(POS[0] <= e["grid"] <= POS[1], "race_entry: grid_position")
        check(e["pos"] is None or POS[0] <= e["pos"] <= POS[1], "race_entry: finish_position")
        check(total is None or TOTAL_MS[0] <= total <= TOTAL_MS[1], "race_entry: total_time")
        check(LAPS[0] <= laps <= LAPS[1], "race_entry: laps_completed")
        check(best is None or BEST_MS[0] <= best <= BEST_MS[1], "race_entry: best_lap")
        check((st == "finished") == (e["pos"] is not None), "race_entry: finished ⇔ позиция")
        check((st == "finished") == (total is not None), "race_entry: finished ⇔ время")
        check(st != "finished" or laps >= 1, "race_entry: finished → круги ≥ 1")
        check(st != "finished" or best is not None, "race_entry: finished → лучший круг")
        check(st != "dns" or laps == 0, "race_entry: dns → 0 кругов")
        check(laps != 0 or best is None, "race_entry: 0 кругов → нет лучшего круга")
        check(st != "dsq" or best is None, "race_entry: dsq → нет лучшего круга")
        check(total is None or best is None or total >= best * laps, "race_entry: время ≥ круг × круги")
        check(e["car"]["season"] == e["date"].year, "согласованность: сезон машины ≠ год гонки")
        check(e["driver"]["debut"] <= e["date"].year, "согласованность: гонка раньше дебюта")
        check(e["track"]["opened"] <= e["date"].year, "согласованность: гонка до открытия трассы")
    for name, cnt in (("PK (driver_id, race_date)", pk), ("машина в гонке", car_k),
                      ("стартовое место в гонке", grid_k), ("финишное место в гонке", fin_k)):
        dup = sum(1 for v in cnt.values() if v > 1)
        if dup:
            errors["race_entry: повтор — " + name] += dup

    by_driver = defaultdict(list)
    for c in contracts:
        by_driver[id(c["driver"])].append(c)
        check(RACE_MIN <= c["start"] <= TODAY, "contract: start_date")
        check(c["end"] is None or c["start"] <= c["end"] <= TODAY, "contract: end_date")
        check(c["team"]["founded"] <= c["start"].year,
              "согласованность: контракт раньше основания команды")
        check(c["driver"]["debut"] <= c["start"].year, "согласованность: контракт раньше дебюта")
    for periods in by_driver.values():
        periods.sort(key=lambda c: c["start"])
        for a, nxt in zip(periods, periods[1:]):
            check(a["end"] is not None and a["end"] < nxt["start"],
                  "contract: периоды пилота пересекаются или повторяют начало")
    for e in entries:
        inside = any(c["team"] is e["car"]["team"] and c["start"] <= e["date"]
                     and (c["end"] is None or e["date"] <= c["end"])
                     for c in by_driver[id(e["driver"])])
        check(inside, "согласованность: гонка вне контракта с командой машины")
    return errors


# ------------------------------------------------------------- вывод

COLUMNS = {
    "driver": ["driver_id", "full_name", "birth_date", "birth_city", "country",
               "license_class", "debut_year"],
    "car": ["car_id", "model", "season_year", "car_class", "horsepower", "weight_kg", "team_id"],
    "team": ["team_id", "name", "country", "founded_year", "is_active", "team_parent_id"],
    "track": ["track_id", "name", "country", "length_km", "track_type", "opened_year"],
    "race_entry": ["driver_id", "car_id", "track_id", "status", "grid_position",
                   "finish_position", "best_lap", "total_time", "race_date", "laps_completed"],
}
COLUMNS["contract"] = ["driver_id", "team_id", "start_date", "end_date"]
ORDER = ["team", "track", "driver", "car", "race_entry", "contract"]


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
    p = argparse.ArgumentParser(description="Генератор данных об автогонках")
    p.add_argument("--out", default=None, help="куда положить CSV (по умолчанию ../data)")
    p.add_argument("--cache", default=None, help="папка кэша ответов API")
    p.add_argument("--seed", type=int, default=42, help="зерно случайных чисел")
    p.add_argument("--no-fake-series", action="store_true",
                   help="без вымышленных чемпионатов: только реальная F1 и справочники")
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out or os.path.join(os.path.dirname(here), "data")
    f = Fetcher(args.cache or os.path.join(here, ".cache", "racing"))
    rnd = random.Random(args.seed)
    log = Counter()

    print("Шаг 1/4. Гонки Формулы-1 (Jolpica)")
    races = collect_f1(f)
    drivers, teams, tracks, events = parse_f1(races, log)
    events = dedupe_f1(events, drivers, log)
    enrich_f1(f, drivers, teams, tracks)
    pool_d, pool_t, pool_tr = collect_pools(f)

    print("Шаг 4/4. Сборка и проверка")
    b = Builder(rnd, log)
    by_qid = {}
    b.load_f1(drivers, teams, tracks, events, by_qid)
    b.load_pools(pool_d, pool_t, pool_tr, by_qid)
    if not args.no_fake_series:
        for s in SERIES:
            b.run_series(s)
    b.finalize()
    tables, entries, contracts = b.tables()
    errors = validate(b, entries, contracts)
    if errors:
        print("\nДанные не проходят ограничения, CSV не записаны:")
        for k, v in sorted(errors.items()):
            print("  %-60s %d" % (k, v))
        sys.exit(1)
    write_csv(tables, out_dir)

    real = sum(1 for e in entries if e["car"]["cls"] == "formula" and e["car"]["team"].get("f1"))
    print("\nГотово. Файлы в %s\n" % out_dir)
    for name in ORDER:
        print("  %-11s %6d строк" % (name, len(tables[name])))
    print("\n  из них реальных заездов F1: %d, вымышленных: %d" % (real, len(entries) - real))
    print("\nЧто подправлено или досочинено:")
    for k, v in sorted(log.items()):
        print("  %-66s %d" % (k, v))


if __name__ == "__main__":
    main()
