# PL/Python в PostgreSQL

Методичка для ЛР №4 «SQL CLR». В SQL Server расширения пишут на C# и подгружают в сервер через CLR. В PostgreSQL то же самое делают процедурные языки, и один из них — PL/Python: функции, агрегаты, процедуры и триггеры пишутся на Python и выполняются **внутри сервера БД**, рядом с данными.

Все примеры работают на твоей схеме автогонок: `team`, `car`, `track`, `driver`, `race_entry`, `contract`. Примеры в уроках — это **не** готовые объекты для сдачи. Шесть объектов лабы ты пишешь сам в практике и финальном задании, а уроки показывают приёмы на соседних задачах.

Как проходить: по порядку, код набирать руками в `psql` или в своём клиенте, практику делать сразу после урока. Всё, что меняет данные, запускай внутри `BEGIN; ... ROLLBACK;`, чтобы не портить сгенерированную базу (подробнее в уроке 7).

**Содержание**

- Часть I. Основы
  - [Урок 0. Окружение](#урок-0-окружение)
  - [Урок 1. Как SQL CLR ложится на PostgreSQL](#урок-1-как-sql-clr-ложится-на-postgresql)
  - [Урок 2. Скалярная функция](#урок-2-скалярная-функция)
  - [Урок 3. Типы на границе SQL и Python](#урок-3-типы-на-границе-sql-и-python)
  - [Урок 4. Запросы к базе изнутри функции](#урок-4-запросы-к-базе-изнутри-функции)
- Часть II. Шесть объектов
  - [Урок 5. Табличная функция](#урок-5-табличная-функция)
  - [Урок 6. Агрегатная функция](#урок-6-агрегатная-функция)
  - [Урок 7. Хранимая процедура](#урок-7-хранимая-процедура)
  - [Урок 8. Триггер](#урок-8-триггер)
  - [Урок 9. Пользовательский тип](#урок-9-пользовательский-тип)
- Часть III. Надёжность
  - [Урок 10. Ошибки и подтранзакции](#урок-10-ошибки-и-подтранзакции)
  - [Урок 11. Тестирование, развёртывание, производительность](#урок-11-тестирование-развёртывание-производительность)
- [Итог: структура лабораторной](#итог-структура-лабораторной)
- [Финальное задание](#финальное-задание)
- [Шпаргалка](#шпаргалка)
- [Источники](#источники-и-что-почитать-дальше)

---

# Часть I. Основы

## Урок 0. Окружение

PL/Python — расширение `plpython3u`. Оно есть не в каждой сборке PostgreSQL, поэтому сначала проверь, доступно ли оно.

```sql
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name = 'plpython3u';
```

Если строка есть, включи расширение в своей базе (один раз на базу):

```sql
CREATE EXTENSION IF NOT EXISTS plpython3u;
```

И проверь, какой Python внутри сервера:

```sql
DO $$
import sys
plpy.notice(sys.version)
$$ LANGUAGE plpython3u;
```

`DO` — анонимный блок кода: выполнился и исчез. Удобен для экспериментов. `plpy.notice` печатает сообщение клиенту, это твой `print`.

### Если строки нет

Зависит от того, как установлен PostgreSQL:

| Установка | Что делать |
|---|---|
| Postgres.app | Поставить Python **с python.org** (не через brew) нужной версии: для PostgreSQL 17 — 3.13.x, для 18 — любой ≥ 3.9. Затем `CREATE EXTENSION`. |
| Homebrew (`postgresql@NN`) | Стандартная формула может собираться без PL/Python. Проще перейти на Postgres.app или Docker. |
| Docker | Официальный образ без PL/Python, но пакет доставляется одной строкой (см. ниже). |
| Linux / учебная ВМ | Пакет `postgresql-plpython3-NN`, где `NN` — версия сервера. |

Вариант с Docker (подставь свою версию вместо 17):

```dockerfile
FROM postgres:17
RUN apt-get update \
 && apt-get install -y postgresql-plpython3-17 \
 && rm -rf /var/lib/apt/lists/*
```

```bash
docker build -t pg-py:17 .
docker run -d --name pgpy -e POSTGRES_PASSWORD=pass -p 5433:5432 pg-py:17
psql -h localhost -p 5433 -U postgres
```

Потом прогони в этом контейнере свои `create_table.sql`, `define_restrictions.sql` и скрипт загрузки.

> **Буква `u` в `plpython3u` значит untrusted.** Код внутри может делать всё, что может процесс сервера: читать файлы, ходить в сеть. Поэтому создавать такие функции может только суперпользователь. В Postgres.app и Docker ты и так суперпользователь, а на чужом сервере (например, университетском) может не получиться — уточни заранее.

### Практика

1. Включи расширение в базе с автогонками и выведи через `DO` версию Python и текущее время сервера (`datetime.datetime.now()`).
2. Выведи через `DO` число строк в `race_entry`. Подсказка: `plpy.execute("SELECT count(*) AS n FROM race_entry")[0]["n"]` — подробно разберём в уроке 4, пока просто убедись, что работает.

Подробнее: [PL/Python — Python Procedural Language](https://www.postgresql.org/docs/current/plpython.html), [PL/Python в Postgres.app](https://postgresapp.com/documentation/plpython.html)

---

## Урок 1. Как SQL CLR ложится на PostgreSQL

Задание сформулировано под SQL Server, поэтому сначала переведём термины. Логика одна: обычная функция на «внешнем» языке, а SQL-командой ты говоришь серверу, какую роль она играет.

| Объект в ЛР | SQL Server + CLR | PostgreSQL + PL/Python |
|---|---|---|
| Скалярная функция | `[SqlFunction]`, `CREATE FUNCTION ... EXTERNAL NAME` | `CREATE FUNCTION ... RETURNS <тип> LANGUAGE plpython3u` |
| Табличная функция | `[SqlFunction(FillRowMethodName=...)]` | `RETURNS TABLE (...)` или `RETURNS SETOF ...` |
| Агрегат | класс с `Init / Accumulate / Merge / Terminate` | `CREATE AGGREGATE` из функций `SFUNC` (≈ Accumulate), `FINALFUNC` (≈ Terminate), `COMBINEFUNC` (≈ Merge), `INITCOND` (≈ Init) |
| Хранимая процедура | `[SqlProcedure]` | `CREATE PROCEDURE ... LANGUAGE plpython3u`, вызов через `CALL` |
| Триггер | `[SqlTrigger]` | функция `RETURNS trigger` + `CREATE TRIGGER ... EXECUTE FUNCTION` |
| Пользовательский тип | `[SqlUserDefinedType]` со своим `Parse/ToString` | составной тип `CREATE TYPE ... AS (...)` + функции и операторы на Python (почему не «настоящий» базовый тип — в уроке 9) |

Главное отличие: в SQL Server сборку компилируют отдельно и регистрируют DLL. В PostgreSQL исходник на Python лежит прямо в теле `CREATE FUNCTION` между `$$ ... $$`. Сервер хранит его в каталоге и при первом вызове в сессии компилирует.

Минимальная функция:

```sql
CREATE OR REPLACE FUNCTION hello(who text)
RETURNS text
LANGUAGE plpython3u
AS $$
return f"Привет, {who}!"
$$;

SELECT hello('пилот');
```

Что тут происходит:
- тело между `$$` — это тело Python-функции; PostgreSQL сам оборачивает его в `def`;
- аргументы доступны по именам (`who`) и списком `args`;
- `return` отдаёт значение, оно конвертируется в объявленный тип `text`;
- `return None` или конец функции без `return` дают SQL `NULL`.

> **Ловушка: не присваивай параметру.** Строка `who = who.strip()` упадёт с `UnboundLocalError`: присваивание делает `who` локальной переменной всего тела. Заводи новую переменную: `name = who.strip()`.

> **Где ловятся ошибки.** Синтаксические ошибки Python всплывают уже на `CREATE FUNCTION`. Ошибки выполнения (`KeyError`, деление на ноль) — только при вызове, вместе с Python-трейсбеком в тексте ошибки.

### Практика

1. Напиши `fmt_driver(full_name text, country text) RETURNS text`, возвращающую строку вида `Иванов И. (RUS)`. Возьми фамилию и инициал имени, страну обрежь до трёх заглавных букв. Проверь на `SELECT fmt_driver(full_name, country) FROM driver LIMIT 10;`.
2. Сломай: присвой параметру новое значение в теле, вызови, прочитай трейсбек. Почини.

---

## Урок 2. Скалярная функция

Скалярная функция принимает значения одной строки и возвращает одно значение. Её можно использовать везде, где допустимо выражение: в `SELECT`, `WHERE`, `ORDER BY`, в индексах.

Пример: средняя скорость на лучшем круге, км/ч. Длина трассы — `track.length_km`, время круга — `race_entry.best_lap`.

```sql
CREATE OR REPLACE FUNCTION lap_speed_kmh(length_km numeric, lap_seconds double precision)
RETURNS numeric
LANGUAGE plpython3u
IMMUTABLE STRICT
AS $$
if lap_seconds <= 0:
    return None
return round(float(length_km) / lap_seconds * 3600, 2)
$$;
```

Вызов на твоих данных:

```sql
SELECT d.full_name, t.name AS track, r.best_lap,
       lap_speed_kmh(t.length_km, extract(epoch FROM r.best_lap)) AS kmh
FROM race_entry r
JOIN driver d USING (driver_id)
JOIN track  t USING (track_id)
WHERE r.best_lap IS NOT NULL
ORDER BY kmh DESC
LIMIT 10;
```

Разберём новые слова.

**`STRICT`.** Если хоть один аргумент `NULL`, функция даже не вызывается, сразу возвращается `NULL`. Для `race_entry` это удобно: у сошедших и не стартовавших `best_lap` пустой. Без `STRICT` в Python пришёл бы `None`, и `None <= 0` упал бы с `TypeError`.

> Нужно знать: **категории изменчивости.** `IMMUTABLE` — результат зависит только от аргументов (можно кэшировать и использовать в индексах). `STABLE` — может читать таблицы, но в пределах одного запроса возвращает одно и то же. `VOLATILE` (по умолчанию) — может всё, включая запись. Если функция ходит в таблицы, она **не** `IMMUTABLE`, даже если тебе так хочется: планировщик поверит и может вернуть устаревший результат.

**`float(length_km)`.** `numeric` приходит в Python как `Decimal`, а `Decimal / float` — `TypeError`. Подробно о типах в следующем уроке.

**`extract(epoch FROM r.best_lap)`.** Интервал переведён в секунды ещё в SQL. Почему не передать `interval` прямо — тоже в уроке 3.

Проверь, как работает `STRICT`:

```sql
SELECT lap_speed_kmh(5.0, NULL);   -- NULL, функция не вызывалась
SELECT lap_speed_kmh(5.0, 100);    -- 180.00
```

### Практика

1. Напиши `driver_age_at(birth_date date, on_date date) RETURNS int` — возраст в полных годах на дату. Выведи пилотов, которые были моложе 18 лет хотя бы в одном заезде. Даты в Python придут строками, распарсь их через `datetime.date.fromisoformat`.
2. Напиши `power_per_ton(horsepower int, weight_kg numeric) RETURNS numeric` и найди 5 самых «злых» машин каждого `car_class`. (*) Сделай это одним запросом с оконной функцией.

<details><summary>Подсказка к (*)</summary>

`row_number() OVER (PARTITION BY car_class ORDER BY ... DESC)` в подзапросе, снаружи фильтр по номеру.

</details>

Подробнее: [PL/Python Functions](https://www.postgresql.org/docs/current/plpython-funcs.html)

---

## Урок 3. Типы на границе SQL и Python

Половина ошибок в PL/Python — не в логике, а в том, во что превратилось значение на входе и выходе. Запомни таблицу.

**На входе (SQL → Python):**

| PostgreSQL | Python | Твои колонки |
|---|---|---|
| `boolean` | `bool` | `team.is_active` |
| `smallint`, `int`, `bigint` | `int` | годы, позиции, круги, `horsepower` |
| `real`, `double precision` | `float` | результат `extract(epoch ...)` |
| `numeric` | `decimal.Decimal` | `length_km`, `weight_kg` |
| массив | `list` | — |
| составной тип / строка таблицы | `dict` | урок 9 |
| `NULL` | `None` | |
| **всё остальное**: `text`, `date`, `interval`, `timestamp` | **`str`** | `race_date`, `birth_date`, `best_lap`, `total_time` |

**На выходе (Python → SQL):**
- `None` → `NULL`;
- для большинства типов значение превращается в строку через `str()` и разбирается так же, как литерал в SQL;
- `list` → массив, `dict` / `tuple` → составной тип.

Отсюда три ловушки.

> **Ловушка 1. `Decimal` и `float` не смешиваются.** `Decimal("5.0") / 2.5` даёт `TypeError`. Либо приводи к `float(...)`, либо работай целиком в `Decimal`.

> **Ловушка 2. Даты и интервалы — строки.** `race_date` придёт как `'2019-06-15'`, `best_lap` — как `'00:01:23.456'`. Сравнивать интервалы строками нельзя: `'00:10:00' < '00:9:59'` по символам — неверно. А при большой длительности формат меняется (например, может появиться `1 day ...`), и самописный парсер сломается.

Надёжный приём: **переводи интервалы в секунды на стороне SQL**, через `extract(epoch FROM ...)`, а в Python работай с `float`. Даты разбирай `datetime.date.fromisoformat(s)`.

> **Ловушка 3. Возврат интервала.** Если функция `RETURNS interval`, верни строку, которую PostgreSQL точно поймёт: `f"{seconds} seconds"`. Возвращать `datetime.timedelta` рискованно: её `str()` не обязательно совпадает с форматом литерала интервала в PostgreSQL.

Посмотри на это сам:

```sql
DO $$
r = plpy.execute("""
    SELECT best_lap, total_time, race_date, extract(epoch FROM best_lap) AS lap_s
    FROM race_entry WHERE status = 'finished' LIMIT 1
""")[0]
for k, v in r.items():
    plpy.notice(f"{k}: {v!r} ({type(v).__name__})")
$$ LANGUAGE plpython3u;
```

### Практика

1. Напиши `pace_gap(lap_seconds float8, best_seconds float8) RETURNS interval` — насколько круг медленнее эталонного, в виде интервала. Проверь, что результат можно сравнивать с `interval '1 second'`.
2. Сломай: передай в `lap_speed_kmh` из урока 2 `length_km` без `float(...)` и посмотри на ошибку. Затем перепиши функцию полностью на `Decimal` без `float` и сравни результаты на одних данных.

Подробнее: [Data Values in PL/Python](https://www.postgresql.org/docs/current/plpython-data.html)

---

## Урок 4. Запросы к базе изнутри функции

Python-код внутри сервера может выполнять SQL через модуль `plpy` (его не надо импортировать). Это то, ради чего вообще пишут серверные функции: логика рядом с данными, без передачи по сети.

### `plpy.execute`

```python
rows = plpy.execute("SELECT team_id, name FROM team WHERE is_active LIMIT 5")
rows.nrows()        # число строк
rows[0]["name"]     # строка — это dict
for r in rows: ...
```

### Параметры: только через `plpy.prepare`

Пример: путь команды по родителям, от команды до самого верхнего владельца. Это рекурсия по самоссылке `team_parent_id`.

```sql
CREATE OR REPLACE FUNCTION team_lineage(start_id int)
RETURNS text
LANGUAGE plpython3u
STABLE STRICT
AS $$
if "plan" not in SD:
    SD["plan"] = plpy.prepare(
        "SELECT name, team_parent_id FROM team WHERE team_id = $1",
        ["int"])
plan = SD["plan"]

names, seen, cur = [], set(), start_id
while cur is not None:
    if cur in seen:
        plpy.error(f"цикл в иерархии команд на team_id={cur}")
    seen.add(cur)
    rows = plpy.execute(plan, [cur])
    if rows.nrows() == 0:
        return None
    names.append(rows[0]["name"])
    cur = rows[0]["team_parent_id"]
return " → ".join(names)
$$;

SELECT team_id, team_lineage(team_id)
FROM team WHERE team_parent_id IS NOT NULL LIMIT 10;
```

Новое:

- **`plpy.prepare(sql, [типы])`** готовит план с параметрами `$1, $2, ...`, а **`plpy.execute(plan, [значения])`** выполняет его. Значения передаются отдельно от текста запроса, поэтому SQL-инъекция невозможна.
- **`SD`** — словарь, который живёт между вызовами этой функции в пределах сессии. В нём кэшируют подготовленные планы, чтобы не разбирать запрос при каждом вызове. Есть ещё **`GD`** — общий для всех PL/Python-функций сессии.
- **`plpy.error(...)`** бросает ошибку SQL и прерывает запрос (подробно в уроке 10).

> **Так делать нельзя:** `plpy.execute(f"SELECT ... WHERE name = '{name}'")`. Это SQL-инъекция и заодно ошибка на любом названии с апострофом. Если без подстановки в текст не обойтись (например, имя таблицы — параметр), используй `plpy.quote_ident(...)` и `plpy.quote_literal(...)`.

> **Не тащи в Python то, что умеет SQL.** Тот же путь по родителям делается одним `WITH RECURSIVE`. В лабе цель — показать механизм, но в отчёте полезно написать, почему ты выбрал Python (сложная логика, библиотеки Python, наглядность), а не делать вид, что так быстрее.

### Практика

1. Напиши `driver_team_on(driver_id int, on_date date) RETURNS text` — название команды, с которой у пилота был контракт на дату (по таблице `contract`; `end_date IS NULL` считай действующим контрактом). Используй `prepare` и кэш в `SD`.
2. (*) Перепиши `team_lineage` через один `WITH RECURSIVE`-запрос внутри Python-функции и убедись, что результаты совпадают на всех командах:
   `SELECT count(*) FROM team WHERE team_lineage(team_id) IS DISTINCT FROM team_lineage_v2(team_id);` должно дать 0.

Подробнее: [Database Access](https://www.postgresql.org/docs/current/plpython-database.html)

---

# Часть II. Шесть объектов

## Урок 5. Табличная функция

Табличная функция возвращает набор строк, и её используют в `FROM`, как таблицу. Аналог CLR-функции с `FillRow`.

Объявить результат можно двумя способами:

| Способ | Когда |
|---|---|
| `RETURNS TABLE (col1 type, col2 type, ...)` | столбцы нужны только этой функции |
| `RETURNS SETOF some_type` | тип уже есть (таблица или `CREATE TYPE`), его переиспользуют |

Вернуть строки из Python можно тоже двумя способами: собрать список и вернуть его целиком или отдавать по одной через `yield`.

Пример: карьера пилота — его заезды со скоростью лучшего круга.

```sql
CREATE OR REPLACE FUNCTION driver_career(p_driver_id int)
RETURNS TABLE (
    race_date       date,
    track           text,
    status          text,
    finish_position smallint,
    lap_kmh         numeric
)
LANGUAGE plpython3u
STABLE STRICT
AS $$
plan = plpy.prepare("""
    SELECT r.race_date, t.name AS track, r.status, r.finish_position,
           t.length_km, extract(epoch FROM r.best_lap) AS lap_s
    FROM race_entry r JOIN track t USING (track_id)
    WHERE r.driver_id = $1
    ORDER BY r.race_date
""", ["int"])

for r in plpy.execute(plan, [p_driver_id]):
    kmh = None
    if r["lap_s"]:
        kmh = round(float(r["length_km"]) / r["lap_s"] * 3600, 2)
    yield {
        "race_date": r["race_date"],
        "track": r["track"],
        "status": r["status"],
        "finish_position": r["finish_position"],
        "lap_kmh": kmh,
    }
$$;

SELECT * FROM driver_career(1);
SELECT status, count(*) FROM driver_career(1) GROUP BY status;
```

Строку результата можно отдать как `dict` (ключи — имена столбцов), как `tuple`/`list` (порядок столбцов) или как объект с атрибутами. `dict` надёжнее: перестановка столбцов в `RETURNS TABLE` его не ломает.

> **`yield` не делает функцию «потоковой» целиком.** Здесь `plpy.execute` всё равно загружает весь результат запроса в память. Для огромных выборок есть `plpy.cursor(plan, [args])`, который читает порциями. На твоих объёмах (тысячи строк) это неважно, но знать стоит.

> **Имя параметра и столбцов.** Параметр назван `p_driver_id`, а не `driver_id`: так он не путается с колонкой результата и колонками запроса. В PL/Python конфликта бы не было (запрос — просто строка), но если позже перепишешь функцию на PL/pgSQL, конфликт появится.

Табличную функцию можно вызвать «для каждой строки» другой таблицы через `LATERAL`:

```sql
SELECT d.full_name, c.*
FROM driver d
CROSS JOIN LATERAL driver_career(d.driver_id) c
WHERE d.license_class = 'super'
LIMIT 20;
```

### Практика

1. Напиши `race_results(p_track_id int, p_date date)` — протокол гонки: место, пилот, машина, команда, отставание от победителя в секундах (`total_time` победителя минус свой). У сошедших отставание `NULL`, и они идут в конце.
2. Напиши табличную функцию **без обращения к таблицам**: `lap_splits(total_seconds float8, laps int)` возвращает `(lap int, cumulative_seconds float8)` при равномерном темпе. Используй `yield`. Проверь `SELECT * FROM lap_splits(5400, 60) WHERE lap % 10 = 0;`.
3. (*) Сделай вариант `race_results`, возвращающий `SETOF` своего составного типа (создай его через `CREATE TYPE ... AS (...)`), и сравни, что изменилось в объявлении.

Подробнее: [Data Values: Set-Returning Functions](https://www.postgresql.org/docs/current/plpython-data.html)

---

## Урок 6. Агрегатная функция

Агрегат сворачивает много строк в одно значение, как `sum` или `avg`. Сам агрегат на Python не пишется: пишутся обычные функции, а `CREATE AGGREGATE` собирает из них агрегат.

Схема работы:

```
state = INITCOND
для каждой строки группы:
    state = SFUNC(state, значение)
результат = FINALFUNC(state)          (если FINALFUNC нет — результатом будет state)
```

Это прямой аналог CLR: `Init` → `INITCOND`, `Accumulate` → `SFUNC`, `Terminate` → `FINALFUNC`.

### Пример 1: доля финишей

Состояние — массив из двух чисел `{финиши, всего}`.

```sql
CREATE OR REPLACE FUNCTION finish_rate_step(state int[], status text)
RETURNS int[]
LANGUAGE plpython3u
IMMUTABLE
AS $$
finished, total = state
if status is None:
    return state
return [finished + (1 if status == "finished" else 0), total + 1]
$$;

CREATE OR REPLACE FUNCTION finish_rate_final(state int[])
RETURNS numeric
LANGUAGE plpython3u
IMMUTABLE
AS $$
finished, total = state
return None if total == 0 else round(finished / total, 3)
$$;

CREATE OR REPLACE AGGREGATE finish_rate(text) (
    SFUNC     = finish_rate_step,
    STYPE     = int[],
    FINALFUNC = finish_rate_final,
    INITCOND  = '{0,0}'
);
```

Используется как любой агрегат:

```sql
SELECT d.full_name, count(*) AS races, finish_rate(r.status) AS rate
FROM race_entry r JOIN driver d USING (driver_id)
GROUP BY d.driver_id, d.full_name
HAVING count(*) >= 5
ORDER BY rate DESC
LIMIT 10;
```

Проверка правильности — сравни со встроенными средствами:

```sql
SELECT finish_rate(status),
       round(avg((status = 'finished')::int), 3)
FROM race_entry;
```

Два числа должны совпасть.

### Пример 2: медиана, где нужен весь набор

Не всё считается «на лету» с маленьким состоянием. Для медианы нужны все значения, поэтому состояние — массив.

```sql
CREATE OR REPLACE FUNCTION collect_step(state float8[], x float8)
RETURNS float8[]
LANGUAGE plpython3u IMMUTABLE STRICT
AS $$
return state + [x]
$$;

CREATE OR REPLACE FUNCTION median_final(state float8[])
RETURNS float8
LANGUAGE plpython3u IMMUTABLE
AS $$
import statistics
return statistics.median(state) if state else None
$$;

CREATE OR REPLACE AGGREGATE py_median(float8) (
    SFUNC     = collect_step,
    STYPE     = float8[],
    FINALFUNC = median_final,
    INITCOND  = '{}'
);

SELECT t.name,
       py_median(extract(epoch FROM r.best_lap)) AS median_lap_s,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM r.best_lap)) AS check_s
FROM race_entry r JOIN track t USING (track_id)
GROUP BY t.name
LIMIT 10;
```

Колонки `median_lap_s` и `check_s` должны совпасть: `percentile_cont(0.5)` — встроенная медиана, удобный эталон для теста.

Тонкости:

| Что | Как работает |
|---|---|
| `STRICT` у `SFUNC` | строки с `NULL` пропускаются, состояние не меняется. У `collect_step` это и отбрасывает пустые `best_lap` |
| `INITCOND` | строка-литерал начального состояния. Без него состояние начинается с `NULL` |
| Пустая группа | вызывается только `FINALFUNC` от `INITCOND`, поэтому там нужна проверка на 0 / пустой массив |
| `STYPE internal` | доступен только для функций на C, из Python нельзя |

> **Цена массива в состоянии.** `state + [x]` на каждой строке копирует весь массив, это O(n²) по группе. На тысячах строк незаметно, на миллионах — заметно. Для «потоковых» статистик (среднее, дисперсия) держи в состоянии несколько чисел, а не все значения.

> **Аналог `Merge` — `COMBINEFUNC`.** Он нужен для параллельной агрегации: две частичные свёртки объединяются в одну. Требует `PARALLEL SAFE` у функций. Для лабы необязательно, но упомянуть в отчёте — плюс.

### Практика

1. Напиши агрегат `lap_consistency(float8)` — стандартное отклонение времени круга в секундах, **без хранения всех значений**: в состоянии держи `{n, сумма, сумма квадратов}`. Сверь с встроенным `stddev_samp`.
2. Напиши агрегат `best_track(text, float8)` с **двумя аргументами**: название трассы и скорость; возвращает трассу с максимальной скоростью. Состояние — составной тип или массив `text[]` (подумай, что удобнее).
3. (*) Добавь к `finish_rate` `COMBINEFUNC` и пометь функции `PARALLEL SAFE`.

<details><summary>Подсказка к 2</summary>

`CREATE AGGREGATE best_track(text, float8) (...)`, а `SFUNC` получает `(state, name, speed)`. Если состояние — составной тип, в Python оно придёт `dict`ом, а возвращать его можно тоже `dict`ом.

</details>

Подробнее: [CREATE AGGREGATE](https://www.postgresql.org/docs/current/sql-createaggregate.html), [User-Defined Aggregates](https://www.postgresql.org/docs/current/xaggr.html)

---

## Урок 7. Хранимая процедура

Процедура, в отличие от функции, ничего не возвращает в выражение, вызывается отдельной командой `CALL` и может управлять транзакциями. Это аналог `[SqlProcedure]`.

Пример: деактивировать команду и всё её «потомство» по `team_parent_id`.

```sql
CREATE OR REPLACE PROCEDURE deactivate_team_tree(root_id int)
LANGUAGE plpython3u
AS $$
exists = plpy.prepare("SELECT 1 FROM team WHERE team_id = $1", ["int"])
if plpy.execute(exists, [root_id]).nrows() == 0:
    plpy.error(f"команда {root_id} не найдена")

children   = plpy.prepare("SELECT team_id FROM team WHERE team_parent_id = $1", ["int"])
deactivate = plpy.prepare("UPDATE team SET is_active = false WHERE team_id = $1", ["int"])

queue, seen = [root_id], set()
while queue:
    tid = queue.pop()
    if tid in seen:
        continue
    seen.add(tid)
    plpy.execute(deactivate, [tid])
    queue.extend(r["team_id"] for r in plpy.execute(children, [tid]))

plpy.notice(f"деактивировано команд: {len(seen)}")
$$;
```

Тестируй так, чтобы не испортить данные:

```sql
BEGIN;
SELECT team_id, is_active FROM team WHERE team_id = 1 OR team_parent_id = 1;
CALL deactivate_team_tree(1);
SELECT team_id, is_active FROM team WHERE team_id = 1 OR team_parent_id = 1;
ROLLBACK;
```

### Управление транзакциями

В процедуре можно фиксировать работу частями: `plpy.commit()` и `plpy.rollback()`. Обычные `COMMIT` и `ROLLBACK` через `plpy.execute` выполнить нельзя. После завершения транзакции новая начинается автоматически.

```python
for i, batch in enumerate(batches):
    for row in batch:
        plpy.execute(insert_plan, row)
    plpy.commit()           # каждая пачка фиксируется отдельно
```

> **Ловушка.** `plpy.commit()` работает, только если `CALL` выполнен на верхнем уровне, а не внутри твоего `BEGIN ... ROLLBACK`. Внутри блока получишь ошибку `invalid transaction termination`. Поэтому процедуру с коммитами тестируют на копии базы, а не через `ROLLBACK`.

| | Функция | Процедура |
|---|---|---|
| Вызов | в выражении: `SELECT f(...)` | `CALL p(...)` |
| Возвращает значение | да | нет (только через `INOUT`/`OUT`-параметры) |
| `COMMIT` / `ROLLBACK` внутри | нельзя | можно (`plpy.commit()`) |
| Типичное применение | вычисление, выборка | изменение данных, пакетные операции |

### Практика

1. Напиши процедуру `close_contracts(p_team_id int, p_on date)`: всем открытым контрактам команды (`end_date IS NULL`) ставит `end_date = p_on` и печатает через `notice`, сколько контрактов закрыто. Учти `CHECK` на `end_date` — подумай, какие даты допустимы, и проверь это в Python **до** `UPDATE`, с понятным сообщением.
2. (*) Процедура `generate_race(p_track_id int, p_date date, p_size int)`: случайно выбирает `p_size` пилотов и машин и вставляет заезды в `race_entry` так, чтобы прошли **все** твои `CHECK` и `UNIQUE`. Хорошая проверка, что ты понимаешь собственные ограничения.

Подробнее: [Transaction Management](https://www.postgresql.org/docs/current/plpython-transactions.html), [CREATE PROCEDURE](https://www.postgresql.org/docs/current/sql-createprocedure.html)

---

## Урок 8. Триггер

Триггер — функция, которую сервер вызывает сам при `INSERT`/`UPDATE`/`DELETE`. Делается в два шага: функция `RETURNS trigger` (без аргументов) и команда `CREATE TRIGGER`, привязывающая её к таблице.

Всё о событии лежит в словаре `TD`:

| Ключ | Что внутри |
|---|---|
| `TD["event"]` | `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` |
| `TD["when"]` | `BEFORE`, `AFTER`, `INSTEAD OF` |
| `TD["level"]` | `ROW` или `STATEMENT` |
| `TD["new"]`, `TD["old"]` | новая и старая строка (`dict`); для `INSERT` нет старой, для `DELETE` — новой |
| `TD["table_name"]` | имя таблицы |
| `TD["args"]` | аргументы из `CREATE TRIGGER ... EXECUTE FUNCTION f('a', 'b')` |

Что вернуть из `BEFORE ... FOR EACH ROW`:

| Возврат | Эффект |
|---|---|
| `None` или `"OK"` | строка идёт как есть |
| `"MODIFY"` | применить изменения, которые ты внёс в `TD["new"]` (только `INSERT`/`UPDATE`) |
| `"SKIP"` | молча пропустить эту строку |
| `plpy.error(...)` | отменить всю команду с ошибкой |

В `AFTER`-триггерах возврат игнорируется: строка уже записана, остаётся только реагировать (логировать, менять другие таблицы) или бросить ошибку.

### Пример 1: нормализация данных (`MODIFY`)

```sql
CREATE OR REPLACE FUNCTION trg_driver_normalize()
RETURNS trigger
LANGUAGE plpython3u
AS $$
new = TD["new"]
if new["full_name"] is not None:
    new["full_name"] = " ".join(new["full_name"].split()).title()
if new["country"] is not None:
    new["country"] = new["country"].strip()
return "MODIFY"
$$;

CREATE TRIGGER driver_normalize
BEFORE INSERT OR UPDATE ON driver
FOR EACH ROW EXECUTE FUNCTION trg_driver_normalize();
```

> **Почему проверка на `None`?** `BEFORE`-триггер срабатывает **раньше** проверки `NOT NULL`. Если вставить `NULL` в `full_name`, без проверки ты получишь непонятный `AttributeError` из Python вместо нормальной ошибки ограничения.

### Пример 2: правило между строками (`plpy.error`)

`CHECK` видит только одну строку. А правило «контракты одного пилота не пересекаются по времени» затрагивает несколько строк. Это работа для триггера.

```sql
CREATE OR REPLACE FUNCTION trg_contract_no_overlap()
RETURNS trigger
LANGUAGE plpython3u
AS $$
if "plan" not in SD:
    SD["plan"] = plpy.prepare("""
        SELECT team_id, start_date, end_date
        FROM contract
        WHERE driver_id = $1
          AND daterange(start_date, end_date, '[]') && daterange($2, $3, '[]')
          AND (driver_id, start_date) IS DISTINCT FROM ($4, $5)
    """, ["int", "date", "date", "int", "date"])

new = TD["new"]
old = TD["old"] or {}
rows = plpy.execute(SD["plan"], [
    new["driver_id"], new["start_date"], new["end_date"],
    old.get("driver_id"), old.get("start_date"),
])
if rows.nrows() > 0:
    r = rows[0]
    plpy.error(
        f"контракт пилота {new['driver_id']} пересекается с контрактом "
        f"в команде {r['team_id']} ({r['start_date']} – {r['end_date'] or 'н.в.'})")
return None
$$;

CREATE TRIGGER contract_no_overlap
BEFORE INSERT OR UPDATE ON contract
FOR EACH ROW EXECUTE FUNCTION trg_contract_no_overlap();
```

Разбор:
- `daterange(start, end, '[]')` — диапазон дат включительно; `NULL` в конце означает «без конца», то есть действующий контракт. `&&` — «пересекаются».
- Условие с `old` исключает **саму себя** при `UPDATE`, иначе строка конфликтовала бы со своей старой версией.
- `IS DISTINCT FROM`, а не `NOT (... = ...)`: при `INSERT` старой строки нет, `$4` и `$5` равны `NULL`, и обычное сравнение дало бы `NULL`, то есть отфильтровало бы **все** строки. Та же ловушка с `NULL`, что и в `CHECK` из ЛР №1.

Проверка:

```sql
BEGIN;
INSERT INTO contract VALUES (1, 1, '2015-01-01', '2016-12-31');
INSERT INTO contract VALUES (1, 2, '2016-06-01', NULL);   -- должна быть ошибка
ROLLBACK;
```

> Для такого правила в PostgreSQL есть и декларативный способ: `EXCLUDE USING gist` с расширением `btree_gist`. Триггер здесь — учебный пример, и в отчёте честно стоит упомянуть, что ограничение-исключение было бы надёжнее (триггер не видит незакоммиченные строки параллельных транзакций).

### Практика

1. Триггер на `race_entry`, проверяющий межтабличные правила, которые не смог выразить `CHECK` в ЛР №1: дата заезда не раньше года открытия трассы, не раньше рождения пилота + 15 лет, и сезон машины не позже года заезда. Сообщение об ошибке должно говорить, **какое** правило нарушено.
2. `AFTER`-триггер журнала: создай таблицу `race_entry_log(changed_at timestamptz, op text, driver_id int, race_date date, old_status text, new_status text)` и пиши туда каждое изменение статуса заезда. Обычные `UPDATE` без смены статуса не логируй.
3. (*) `INSTEAD OF`-триггер на представлении: создай `VIEW driver_team_now` (пилот + текущая команда по `contract`) и сделай так, чтобы `UPDATE driver_team_now SET team = 'X'` закрывал текущий контракт и открывал новый.

Подробнее: [Trigger Functions](https://www.postgresql.org/docs/current/plpython-trigger.html)

---

## Урок 9. Пользовательский тип

В SQL Server CLR-тип — это класс с методами `Parse` (из строки) и `ToString` (в строку), и сервер хранит его как полноценный тип. В PostgreSQL «настоящий» базовый тип (`CREATE TYPE name (INPUT = ..., OUTPUT = ...)`) требует функций ввода/вывода, написанных на C. На Python их не сделать.

Поэтому в PL/Python тип собирают из трёх частей:

1. **Составной тип** — структура данных: `CREATE TYPE ... AS (...)`.
2. **Функции на Python** — «методы» и конструктор с проверками.
3. **Операторы** (`CREATE OPERATOR`) — чтобы тип было удобно использовать в выражениях.

Пример: характеристики машины.

```sql
CREATE TYPE car_spec AS (
    horsepower int,
    weight_kg  numeric(6, 2)
);
```

Конструктор с валидацией (те же диапазоны, что в твоих `CHECK`):

```sql
CREATE OR REPLACE FUNCTION make_car_spec(hp int, kg numeric)
RETURNS car_spec
LANGUAGE plpython3u
IMMUTABLE STRICT
AS $$
if not 100 <= hp <= 1500:
    plpy.error(f"мощность вне диапазона: {hp}")
if not 400 <= kg <= 2000:
    plpy.error(f"масса вне диапазона: {kg}")
return {"horsepower": hp, "weight_kg": kg}
$$;
```

«Методы» — функции, принимающие значение типа. Составной тип приходит в Python как `dict`:

```sql
CREATE OR REPLACE FUNCTION hp_per_ton(spec car_spec)
RETURNS numeric
LANGUAGE plpython3u
IMMUTABLE STRICT
AS $$
return round(spec["horsepower"] / float(spec["weight_kg"]) * 1000, 1)
$$;

CREATE OR REPLACE FUNCTION car_spec_label(spec car_spec)
RETURNS text
LANGUAGE plpython3u
IMMUTABLE STRICT
AS $$
return f"{spec['horsepower']} л.с. / {spec['weight_kg']} кг"
$$;
```

Оператор «мощнее по удельной мощности»:

```sql
CREATE OR REPLACE FUNCTION car_spec_stronger(a car_spec, b car_spec)
RETURNS boolean
LANGUAGE plpython3u
IMMUTABLE STRICT
AS $$
pa = a["horsepower"] / float(a["weight_kg"])
pb = b["horsepower"] / float(b["weight_kg"])
return pa > pb
$$;

CREATE OPERATOR >> (
    LEFTARG  = car_spec,
    RIGHTARG = car_spec,
    FUNCTION = car_spec_stronger
);
```

Использование на твоей таблице `car`:

```sql
SELECT model, season_year,
       car_spec_label(make_car_spec(horsepower, weight_kg)) AS spec,
       hp_per_ton(make_car_spec(horsepower, weight_kg))      AS hp_t
FROM car
ORDER BY hp_t DESC
LIMIT 10;

SELECT make_car_spec(1000, 800) >> make_car_spec(700, 1200);   -- true
```

Тип можно использовать как тип колонки:

```sql
CREATE TABLE car_upgrade (
    car_id  int REFERENCES car(car_id),
    before  car_spec,
    after   car_spec
);
```

> **Почему `>>`, а не `>`.** Для составных типов PostgreSQL уже умеет сравнивать значения поэлементно (`ROW(1,2) < ROW(1,3)`). Свой `>` для `car_spec` вступил бы в конкуренцию с этим поведением и запутал бы читателя. Отдельное имя оператора однозначно.

> **Что ещё бывает.** Если тип — это просто «число с правилами» (например, время круга от 10 до 900 секунд), подходит `CREATE DOMAIN lap_seconds AS float8 CHECK (VALUE BETWEEN 10 AND 900)`. Но домен ограничения задаёт на SQL, а не на Python, поэтому для лабы «CLR-тип» его одного мало.

| Подход | Плюсы | Минусы |
|---|---|---|
| Составной тип + Python-функции | пишется на Python, есть поля и методы | нет своего текстового формата, проверки — только через конструктор |
| Домен | проверки встроены в тип | только одно значение, логика на SQL |
| Базовый тип на C | полноценный тип со своим вводом/выводом | нужен C и сборка расширения |

### Практика

1. Сделай свой тип для лабы, отличный от `car_spec`. Требования: минимум два поля, конструктор с проверками, минимум два «метода» и один оператор. Покажи его использование в запросе к твоим таблицам.
2. Сломай: вставь в колонку типа `car_spec` значение в обход конструктора, через литерал `'(5000,10)'::car_spec`. Объясни в двух предложениях, почему так получилось и как это закрыть (подумай про домен над составным типом или `CHECK` на колонке).

Подробнее: [CREATE TYPE](https://www.postgresql.org/docs/current/sql-createtype.html), [CREATE OPERATOR](https://www.postgresql.org/docs/current/sql-createoperator.html)

---

# Часть III. Надёжность

## Урок 10. Ошибки и подтранзакции

Ошибки возникают в двух мирах: в Python (`KeyError`, `ZeroDivisionError`) и в SQL (нарушение ограничения внутри `plpy.execute`). Оба приводят к ошибке запроса, но обрабатываются по-разному.

### Сообщения и ошибки

| Вызов | Что делает |
|---|---|
| `plpy.notice(msg)`, `plpy.warning(msg)`, `plpy.info(msg)` | сообщение клиенту, выполнение продолжается |
| `plpy.error(msg)` | ошибка SQL, функция прерывается |
| необработанное Python-исключение | тоже ошибка SQL, в тексте будет трейсбек |

### Перехват ошибок SQL

Ошибка внутри `plpy.execute` превращается в Python-исключение `plpy.SPIError`. У частых ошибок есть свои подклассы в `plpy.spiexceptions`:

```python
from plpy import spiexceptions

try:
    plpy.execute(insert_plan, [ ... ])
except spiexceptions.UniqueViolation:
    plpy.notice("уже есть, пропускаю")
except spiexceptions.CheckViolation as e:
    plpy.notice(f"нарушен CHECK: {e}")
```

Каждый `plpy.execute` сам по себе выполняется атомарно: если он упал и ты поймал исключение, его частичные изменения откатятся, а функция продолжит работу.

### Подтранзакции: несколько команд атомарно

Иногда нужно «всё или ничего» для **группы** команд. Например, добавить пилота и сразу его контракт: если контракт не вставился, пилот тоже не нужен.

```python
from plpy import spiexceptions

ins_driver = plpy.prepare("""
    INSERT INTO driver (full_name, birth_date, birth_city, country, license_class, debut_year)
    VALUES ($1, $2, $3, $4, $5, $6) RETURNING driver_id
""", ["text", "date", "text", "text", "text", "smallint"])
ins_contract = plpy.prepare(
    "INSERT INTO contract VALUES ($1, $2, $3, $4)",
    ["int", "int", "date", "date"])

try:
    with plpy.subtransaction():
        d_id = plpy.execute(ins_driver, [ ... ])[0]["driver_id"]
        plpy.execute(ins_contract, [d_id, team_id, start, None])
except plpy.SPIError as e:
    plpy.notice(f"пилот не добавлен: {e}")
```

Внутри `with plpy.subtransaction():` любая ошибка откатывает **оба** `INSERT`.

> **Не глотай ошибки молча.** `except Exception: pass` скроет и баг в твоём коде, и нарушение ограничения. Лови конкретные исключения и хотя бы пиши `notice`.

> Внутри активной подтранзакции нельзя вызывать `plpy.commit()` — сначала выйди из блока `with`.

### Практика

1. Добавь в процедуру из урока 7 (`close_contracts`) обработку: если `UPDATE` нарушил `CHECK`, процедура не падает, а пишет `warning` с id контракта и продолжает с остальными.
2. Напиши процедуру `add_driver_with_contract(...)` по образцу выше. Проверь три случая: всё корректно; пилот с неверным `license_class` (ничего не добавилось); корректный пилот, но контракт пересекается (сработал триггер из урока 8, и пилот тоже не добавился).

Подробнее: [Explicit Subtransactions](https://www.postgresql.org/docs/current/plpython-subtransaction.html), [Utility Functions](https://www.postgresql.org/docs/current/plpython-util.html)

---

## Урок 11. Тестирование, развёртывание, производительность

В задании три глагола: создать, **развернуть** и **протестировать**. Развёртывание — это скрипт, который на чистой базе создаёт все объекты. Тесты — скрипт, который их проверяет и громко падает при ошибке.

### Развёртывание

Каждый скрипт должен запускаться повторно без ошибок:

```sql
CREATE EXTENSION IF NOT EXISTS plpython3u;

DROP AGGREGATE IF EXISTS finish_rate(text);
CREATE OR REPLACE FUNCTION finish_rate_step(...) ...;
CREATE OR REPLACE FUNCTION finish_rate_final(...) ...;
CREATE AGGREGATE finish_rate(text) (...);

DROP TRIGGER IF EXISTS contract_no_overlap ON contract;
CREATE TRIGGER contract_no_overlap ...;
```

> `CREATE OR REPLACE FUNCTION` не может сменить тип возвращаемого значения. Если поменял `RETURNS`, нужен `DROP FUNCTION` перед созданием. А тип (`CREATE TYPE`) нельзя удалить, пока от него зависят функции, — тогда `DROP TYPE ... CASCADE` удалит и их.

Запуск, как в ЛР №1, с остановкой на первой ошибке:

```bash
psql -v ON_ERROR_STOP=1 -d racing -f lab4_deploy.sql
psql -v ON_ERROR_STOP=1 -d racing -f lab4_tests.sql
```

### Тесты

Тест — `DO`-блок с `assert`. Упавший `assert` — это Python-исключение, то есть ошибка SQL, и `ON_ERROR_STOP` остановит скрипт.

```sql
DO $$
v = plpy.execute("SELECT lap_speed_kmh(5.0, 100.0) AS v")[0]["v"]
assert abs(float(v) - 180.0) < 0.01, f"ожидали 180, получили {v}"

v = plpy.execute("SELECT lap_speed_kmh(5.0, NULL) AS v")[0]["v"]
assert v is None, "STRICT не сработал"

a, b = plpy.execute("""
    SELECT finish_rate(status) AS a, round(avg((status = 'finished')::int), 3) AS b
    FROM race_entry
""")[0].values()
assert a == b, f"finish_rate {a} != эталон {b}"

plpy.notice("все тесты пройдены")
$$ LANGUAGE plpython3u;
```

Хорошие тесты для каждого объекта:
- **эталон**: сравнение со встроенным средством (`avg`, `percentile_cont`, `stddev_samp`, `WITH RECURSIVE`);
- **граничные случаи**: `NULL`, пустая группа, ноль кругов;
- **ожидаемая ошибка**: триггер и конструктор типа **должны** падать на плохих данных. Проверяется через `try/except plpy.SPIError` внутри теста: если исключения не было — `assert False`.
- **изменения данных** — внутри подтранзакции, которую ты откатываешь, бросив своё исключение, или в `BEGIN ... ROLLBACK` вокруг теста.

### Отладка

- `plpy.notice(repr(x))` — главный инструмент: печатай значение **и** тип.
- Ошибка Python приходит с трейсбеком, номер строки считается от начала тела функции.
- Модули импортируются один раз на сессию. Если ты поменял что-то на уровне `GD`, переподключись, чтобы начать с чистого состояния.

### Производительность

В задании говорится о «высокопроизводительных языках» — для SQL Server это C# против T-SQL. В PostgreSQL ситуация другая: интерпретатор Python медленнее встроенных функций на C, и каждый вызов добавляет накладные расходы на конвертацию типов. Проверь сам:

```sql
EXPLAIN ANALYZE SELECT finish_rate(status) FROM race_entry;
EXPLAIN ANALYZE SELECT avg((status = 'finished')::int) FROM race_entry;
```

Скорее всего, Python-версия будет заметно медленнее. Это нормальный вывод для отчёта: PL/Python выигрывает не скоростью, а выразительностью (сложная логика, стандартная библиотека Python, пакеты вроде `statistics`). Реальная «высокая производительность» в PostgreSQL — это расширения на C.

### Практика

1. Собери `lab4_tests.sql`: минимум два теста на каждый объект из уроков 2–9, один из них — на ожидаемую ошибку.
2. Замерь через `EXPLAIN ANALYZE` свою скалярную функцию против того же выражения на чистом SQL. Запиши числа: пригодятся в отчёте.

Подробнее: [Utility Functions](https://www.postgresql.org/docs/current/plpython-util.html)

---

# Итог: структура лабораторной

Удобно разложить лабу так:

```
lab4/
├── 00_extension.sql      CREATE EXTENSION plpython3u
├── 01_scalar.sql         скалярная функция
├── 02_aggregate.sql      функции шага/финала + CREATE AGGREGATE
├── 03_table_func.sql     табличная функция
├── 04_procedure.sql      процедура
├── 05_trigger.sql        функция-триггер + CREATE TRIGGER
├── 06_type.sql           CREATE TYPE + конструктор, методы, оператор
├── deploy.sql            \i 00_... \i 06_... по порядку
└── tests.sql             DO-блоки с assert
```

`deploy.sql` собирает всё через `\i`:

```sql
\set ON_ERROR_STOP on
\i 00_extension.sql
\i 01_scalar.sql
-- ...
```

Порядок важен: тип из `06` нужно создать раньше, чем функции, которые его используют. Если твоя табличная функция возвращает `SETOF` своего типа, вынеси `CREATE TYPE` выше.

---

# Финальное задание

Сама лабораторная. Создай, разверни и протестируй на своей базе шесть объектов на PL/Python:

- **Скалярная функция**, использующая данные минимум двух колонок, с осознанно выбранными `STRICT` и категорией изменчивости.
- **Агрегат** со своим состоянием (не просто сумма) и `FINALFUNC`; результат сверяется с эталоном на встроенных средствах или с ручным подсчётом.
- **Табличная функция** с параметром, обращающаяся к таблицам через `plpy.prepare`.
- **Хранимая процедура**, изменяющая данные, с проверкой входных параметров и понятными сообщениями.
- **Триггер**, реализующий правило, которое нельзя выразить через `CHECK`, `UNIQUE` или `FOREIGN KEY`.
- **Пользовательский тип**: составной тип + конструктор с проверками + методы + оператор.

Общие требования:
- ни одного SQL-запроса, собранного подстановкой значений в строку;
- все объекты создаются одним скриптом через `psql -v ON_ERROR_STOP=1`, повторный запуск не падает;
- тестовый скрипт проверяет нормальные случаи, `NULL` и хотя бы одну ожидаемую ошибку для каждого объекта;
- в отчёте для каждого объекта: зачем он нужен в предметной области, почему он на Python, а не на SQL, и замер производительности хотя бы для одного объекта.

Идеи для твоей предметной области, если не хватает своих:
- триггер межтабличных дат из практики урока 8 (то, что не сделал `CHECK` в ЛР №1);
- агрегат «стабильность пилота» по времени кругов или «самая частая причина схода» по статусу;
- табличная функция «протокол гонки» или «история команды по сезонам»;
- процедура генерации гонки, проходящей все ограничения;
- тип «результат заезда» или «отставание» с оператором сравнения.

---

# Шпаргалка

```sql
-- расширение
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- скалярная
CREATE OR REPLACE FUNCTION f(a int, b text) RETURNS numeric
LANGUAGE plpython3u IMMUTABLE STRICT AS $$ return ... $$;

-- табличная
CREATE OR REPLACE FUNCTION tf(p int) RETURNS TABLE (x int, y text)
LANGUAGE plpython3u STABLE AS $$ yield {"x": 1, "y": "a"} $$;

-- агрегат
CREATE AGGREGATE agg(text) (SFUNC = step, STYPE = int[], FINALFUNC = fin, INITCOND = '{0,0}');

-- процедура
CREATE OR REPLACE PROCEDURE p(a int) LANGUAGE plpython3u AS $$ ... $$;
CALL p(1);

-- триггер
CREATE OR REPLACE FUNCTION trg() RETURNS trigger LANGUAGE plpython3u AS $$ ... return "MODIFY" $$;
CREATE TRIGGER t BEFORE INSERT OR UPDATE ON tbl FOR EACH ROW EXECUTE FUNCTION trg();

-- тип
CREATE TYPE t AS (a int, b numeric);
CREATE OPERATOR >> (LEFTARG = t, RIGHTARG = t, FUNCTION = t_gt);
```

```python
# запросы
rows = plpy.execute("SELECT ...")                       # без параметров
plan = plpy.prepare("SELECT ... WHERE id = $1", ["int"])
rows = plpy.execute(plan, [42])
rows.nrows(); rows[0]["col"]

# кэш
SD["plan"]   # на функцию, на сессию
GD["x"]      # на все функции сессии

# сообщения и ошибки
plpy.notice(...); plpy.warning(...); plpy.error(...)
try: ...
except plpy.spiexceptions.UniqueViolation: ...
with plpy.subtransaction(): ...

# транзакции (только в процедуре, CALL на верхнем уровне)
plpy.commit(); plpy.rollback()

# триггер
TD["event"], TD["when"], TD["new"], TD["old"], TD["args"]
return None | "OK" | "MODIFY" | "SKIP"
```

| SQL-тип | В Python |
|---|---|
| `int`, `smallint` | `int` |
| `numeric` | `Decimal` |
| `float8` | `float` |
| `date`, `interval`, `text` | `str` |
| массив | `list` |
| составной | `dict` |
| `NULL` | `None` |

---

# Источники и что почитать дальше

**Официальная документация PostgreSQL**
- [PL/Python — Python Procedural Language](https://www.postgresql.org/docs/current/plpython.html) — оглавление главы, с него удобно ходить по разделам.
- [PL/Python Functions](https://www.postgresql.org/docs/current/plpython-funcs.html) — объявление функций, аргументы, ловушка с присваиванием параметру.
- [Data Values](https://www.postgresql.org/docs/current/plpython-data.html) — полная таблица конвертации типов, составные типы, возврат наборов.
- [Database Access](https://www.postgresql.org/docs/current/plpython-database.html) — `execute`, `prepare`, курсоры.
- [Trigger Functions](https://www.postgresql.org/docs/current/plpython-trigger.html) — словарь `TD` и коды возврата.
- [Explicit Subtransactions](https://www.postgresql.org/docs/current/plpython-subtransaction.html) и [Transaction Management](https://www.postgresql.org/docs/current/plpython-transactions.html) — урок 10 и коммиты в процедурах.
- [CREATE AGGREGATE](https://www.postgresql.org/docs/current/sql-createaggregate.html) и [User-Defined Aggregates](https://www.postgresql.org/docs/current/xaggr.html) — все параметры агрегатов, включая `COMBINEFUNC` и moving-aggregate.
- [CREATE TYPE](https://www.postgresql.org/docs/current/sql-createtype.html) — почему базовые типы требуют C, и какие ещё бывают типы.

**Установка**
- [PL/Python в Postgres.app](https://postgresapp.com/documentation/plpython.html) — какая версия Python нужна под твою версию PostgreSQL.
- [How to install Postgres with plpython3u](https://postgres.ai/docs/postgres-howtos/advanced-topics/misc/how-to-install-postgres-16-with-plpython3u) — рецепты для macOS, Ubuntu и Docker.
