# ЛР6 — теория по заданиям

Короткая теория к каждому файлу `01.py` … `10.py`. Примеры специально построены на других таблицах, чем задания, чтобы их не копировать, а переносить.

- [0. Основа: подключение и курсор](#0-основа-подключение-и-курсор)
- [1. Скалярный запрос](#1-скалярный-запрос)
- [2. Несколько JOIN](#2-несколько-join)
- [3. CTE и оконные функции](#3-cte-и-оконные-функции)
- [4. Метаданные](#4-метаданные)
- [5. Скалярная функция](#5-скалярная-функция)
- [6. Табличная функция](#6-табличная-функция)
- [7. Хранимая процедура и транзакции](#7-хранимая-процедура-и-транзакции)
- [8. Системные функции](#8-системные-функции)
- [9. Создание таблицы](#9-создание-таблицы)
- [10. INSERT и COPY](#10-insert-и-copy)
- [Сборка в меню](#сборка-в-меню)

---

## 0. Основа: подключение и курсор

Драйвер — **psycopg 3** (`pip install "psycopg[binary]"`). Подключение уже есть в `database.py`.

```python
from database import connect

with connect() as db:
    cur = db.execute("SELECT count(*) FROM team WHERE is_active")
    print(cur.fetchone())      # (684,)
```

| Вызов | Что делает |
|---|---|
| `db.execute(sql, params)` | создаёт курсор, выполняет запрос, возвращает курсор |
| `cur.fetchone()` | следующая строка кортежем или `None`, если строк нет |
| `cur.fetchall()` | все строки списком кортежей |
| `cur.description` | описание столбцов результата, `[c.name for c in cur.description]` |
| `cur.rowcount` | сколько строк затронул `INSERT/UPDATE/DELETE` |

**Параметры.** Значения от пользователя передаются только через `%s`, а не через f-строку:

```python
db.execute("SELECT name FROM team WHERE country = %s AND founded_year > %s", (country, year))
```

Драйвер сам экранирует значение и правильно передаёт тип. Если склеивать строку, ввод `' OR 1=1 --` превращается в часть SQL (это и есть SQL-инъекция). Важно: `%s` подставляет **значение**. Имя таблицы или столбца так передать нельзя, для этого есть модуль `psycopg.sql` (см. п. 9).

Даже один параметр передаётся кортежем: `(x,)`, а не `(x)`.

**Типы PostgreSQL → Python.**

| PostgreSQL | Python |
|---|---|
| `int`, `smallint` | `int` |
| `numeric` | `decimal.Decimal` |
| `text` | `str` |
| `date` | `datetime.date` |
| `interval` | `datetime.timedelta` |
| `boolean` | `bool` |
| `NULL` | `None` |

**`with connect() as db`** при выходе из блока делает `commit` (или `rollback`, если вылетело исключение) и закрывает соединение.

**Ошибки** базы приходят как исключения `psycopg.Error` и его подклассы из `psycopg.errors`: `ForeignKeyViolation`, `CheckViolation`, `UniqueViolation`, `RaiseException` (от `RAISE EXCEPTION` в PL/pgSQL) и т. д. Подробности лежат в `e.diag`: `e.diag.message_primary`, `e.diag.constraint_name`.

> После любой ошибки текущая транзакция «сломана»: все следующие запросы падают с `InFailedSqlTransaction`, пока не сделаешь `db.rollback()`.

---

## 1. Скалярный запрос

**Скалярный запрос** возвращает ровно одно значение: одна строка, один столбец. Обычно это агрегат (`count`, `min`, `max`, `avg`) или `ORDER BY ... LIMIT 1`.

```python
(n,) = db.execute("SELECT count(*) FROM track WHERE track_type = 'oval'").fetchone()
```

Распаковка `(n,) = ...` сразу проверяет, что пришёл ровно один столбец.

**Сортировка и NULL.** При `ORDER BY x` (по возрастанию) значения `NULL` идут **в конце**, при `DESC` — в начале. Управляется явно: `ORDER BY x DESC NULLS LAST`. Надёжнее всего отфильтровать `WHERE x IS NOT NULL`.

**Ничьи.** `LIMIT 1` при равенстве вернёт случайного из лидеров. Чтобы получить всех лидеров, используй `FETCH FIRST 1 ROW WITH TIES` (нужен `ORDER BY`).

**Формат интервала.** `interval` приходит как `timedelta` и печатается как `0:00:14.961000`. Два способа это исправить:

- в SQL: `to_char(best_lap, 'FMMI:SS.MS')` → `0:14.961` (`FM` убирает ведущий ноль у минут);
- в Python: `td.total_seconds()`, затем `divmod(sec, 60)` и `f"{m}:{s:06.3f}"`.

---

## 2. Несколько JOIN

`JOIN` склеивает строки таблиц по условию. Цепочка соединений читается слева направо: каждое следующее соединение добавляет столбцы к уже собранному результату.

```sql
SELECT t.name AS team, c.model, c.season_year, c.horsepower
FROM car c
JOIN team t ON t.team_id = c.team_id
WHERE t.country = %s
ORDER BY c.season_year;
```

| Вид | Что остаётся |
|---|---|
| `JOIN` (`INNER`) | только строки, у которых есть пара |
| `LEFT JOIN` | все строки слева, справа `NULL`, если пары нет |
| `FULL JOIN` | все строки с обеих сторон |

**`USING (col)` против `ON a.col = b.col`.** `USING` короче и годится, когда столбец называется одинаково в обеих таблицах. Есть подвох: в схеме один и тот же столбец может означать разное. Например, `country` есть и у `driver`, и у `track`, и `USING (country)` соединит их по совпадению стран, а не по смыслу.

**Псевдонимы** (`car c`) обязательны, когда в двух таблицах есть столбцы с одинаковыми именами (`name` у `team` и у `track`).

**Поиск по части строки** без учёта регистра:

```python
db.execute("SELECT name FROM track WHERE name ILIKE %s", (f"%{part}%",))
```

Символы `%` добавляются к **значению** параметра, а не вписываются в SQL.

**Составной ключ.** Заезд в `race_entry` определяется парой `(driver_id, race_date)`, а гонка — парой `(track_id, race_date)`. Это пригодится при группировке и соединениях.

---

## 3. CTE и оконные функции

**CTE** (Common Table Expression, `WITH`) — именованный подзапрос. Сложный запрос раскладывается на шаги, которые читаются сверху вниз:

```sql
WITH team_cars AS (
    SELECT team_id, count(*) AS cars, max(horsepower) AS max_hp
    FROM car
    GROUP BY team_id
)
SELECT t.name, tc.cars, tc.max_hp
FROM team_cars tc
JOIN team t USING (team_id);
```

Можно объявить несколько CTE через запятую, и каждый следующий видит предыдущие.

**Оконная функция** считает значение по группе строк («окну»), но, в отличие от `GROUP BY`, **не схлопывает** строки: у каждой строки остаётся свой результат.

```sql
функция() OVER (PARTITION BY ... ORDER BY ...)
```

- `PARTITION BY` — на какие группы делить (без него всё окно — весь результат);
- `ORDER BY` — порядок внутри группы (нужен для рангов и нарастающих итогов).

| Функция | Что даёт |
|---|---|
| `row_number()` | 1, 2, 3, 4 — всегда разные |
| `rank()` | 1, 2, 2, 4 — при равенстве одинаковое место, потом пропуск |
| `dense_rank()` | 1, 2, 2, 3 — без пропусков |
| `lag(x)` / `lead(x)` | значение из предыдущей / следующей строки |
| `sum(x) OVER (ORDER BY ...)` | нарастающий итог |
| `max(x) OVER ()` | максимум по всему результату в каждой строке |

Пример: машины каждой команды по мощности и отставание от самой мощной машины команды.

```sql
SELECT team_id, model, horsepower,
       rank() OVER (PARTITION BY team_id ORDER BY horsepower DESC) AS place,
       max(horsepower) OVER (PARTITION BY team_id) - horsepower       AS gap
FROM car;
```

**Оконные функции нельзя использовать в `WHERE`**: они считаются после него. Чтобы отфильтровать по рангу, оберни запрос в CTE и фильтруй во внешнем `SELECT`.

**Значение по таблице соответствия** (например, очки за место) удобно брать из массива. Индексы в PostgreSQL начинаются с 1, а выход за границу даёт `NULL`:

```sql
SELECT (ARRAY[10, 6, 4, 3, 2, 1])[2];   -- 6
SELECT (ARRAY[10, 6, 4, 3, 2, 1])[9];   -- NULL → оберни в coalesce(..., 0)
```

**Фильтр по году** из `date`: `extract(year FROM race_date) = %s`. Вариант, который может использовать индекс: `race_date >= make_date(%s, 1, 1) AND race_date < make_date(%s + 1, 1, 1)`.

---

## 4. Метаданные

Описание самой базы (таблицы, столбцы, ограничения, функции) тоже хранится в таблицах, и его можно читать обычным `SELECT`. Есть два источника.

**`information_schema`** — стандарт SQL, одинаковый в разных СУБД:

| Представление | Что внутри |
|---|---|
| `information_schema.tables` | таблицы и представления |
| `information_schema.columns` | столбцы: `column_name`, `data_type`, `is_nullable`, `column_default`, `ordinal_position` |
| `information_schema.table_constraints` | ограничения: имя и тип (`PRIMARY KEY`, `FOREIGN KEY`, `CHECK`, `UNIQUE`) |

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
```

**`pg_catalog`** — системный каталог PostgreSQL. Он подробнее, но относится только к этой СУБД:

| Таблица | Что внутри |
|---|---|
| `pg_class` | таблицы, индексы (`relname`, `relkind`) |
| `pg_constraint` | ограничения: `conname`, `contype` (`p`, `f`, `c`, `u`), `conrelid` — oid таблицы |
| `pg_proc` | функции и процедуры: `proname`, `prokind` (`f` — функция, `p` — процедура, `a` — агрегат) |
| `pg_namespace` | схемы, связь через `pronamespace` / `relnamespace` |

Полезные функции, которые превращают внутреннее представление в текст:

| Функция | Результат |
|---|---|
| `pg_get_constraintdef(oid)` | текст ограничения, например `CHECK (horsepower >= 100 ...)` |
| `pg_get_function_arguments(oid)` | `p_driver_id integer, p_year integer` |
| `pg_get_function_result(oid)` | `numeric`, `TABLE(metric text, value text)` |
| `pg_get_functiondef(oid)` | полный `CREATE FUNCTION` |

**Имя таблицы → oid** через приведение к `regclass`, и его можно передавать параметром:

```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = %s::regclass;
```

Если таблицы нет, приведение упадёт с `UndefinedTable`. Эту ошибку нужно поймать и показать понятное сообщение.

Шпаргалка: в `psql` команда `\set ECHO_HIDDEN on` показывает, какие запросы к каталогу выполняют `\d`, `\df` и т. п. Это хороший источник примеров.

---

## 5. Скалярная функция

Функции из ЛР3 нужно сначала создать в базе (сейчас их там нет):

```bash
psql -h localhost -p 5433 -U postgres -d study -f ../lab-03/01-funcs/01-scalar.sql
```

> В файлах ЛР3 есть тестовые вызовы внутри `begin; ... rollback;`. Сама функция создаётся до `begin`, так что откат её не удаляет. Перед запуском всё равно проверь, что файл не меняет данные.

Скалярная функция вызывается внутри `SELECT`, как встроенная:

```python
(value,) = db.execute("SELECT fn_avg_speed(%s, %s)", (driver_id, race_date)).fetchone()
```

- Дату удобно передавать объектом `datetime.date`: `date.fromisoformat("1950-05-13")`. Строка тоже сработает, PostgreSQL приведёт её сам.
- Если внутри функции `SELECT` ничего не нашёл, функция на `language sql` вернёт `NULL`, а в Python придёт `None`. Проверь это явно, а не печатай `None км/ч`.
- `numeric` приходит как `Decimal`, он печатается без хвоста двоичной погрешности.

**`STABLE` / `IMMUTABLE` / `VOLATILE`** — обещание оптимизатору о поведении функции: не меняет данные и одинаково отвечает в рамках запроса, всегда одинаково отвечает, или может что угодно. На вызов из Python это не влияет.

---

## 6. Табличная функция

Функция с `RETURNS TABLE(...)` или `RETURNS SETOF` возвращает набор строк. Её ставят во `FROM`, как таблицу:

```python
cur = db.execute("SELECT * FROM fn_team_tree(%s)", (team_id,))
cols = [c.name for c in cur.description]
rows = cur.fetchall()
```

Поскольку это обычный источник строк, к нему применимо всё: `WHERE`, `ORDER BY`, `JOIN`, `LIMIT`.

| Вид в ЛР3 | Как устроена |
|---|---|
| inline (`language sql`, один `SELECT`) | оптимизатор встраивает тело в запрос |
| многооператорная (`plpgsql`, `RETURN QUERY` / `RETURN NEXT`) | выполняется целиком, результат копится и отдаётся |

**Вывод таблицей.** Ширину столбца можно взять как максимум длины `str()` по заголовку и всем значениям, а печатать через `str.ljust(width)`. Стоит один раз написать функцию `print_table(cols, rows)`: она понадобится в пунктах 2, 3, 4, 6 и 8.

Если функция делает `RAISE EXCEPTION` (например, «Пилот не найден»), в Python прилетит `psycopg.errors.RaiseException`. Текст лежит в `e.diag.message_primary`.

---

## 7. Хранимая процедура и транзакции

**Процедура** вызывается через `CALL`, а не через `SELECT`, и ничего не возвращает (кроме `INOUT`-параметров). Обычно она меняет данные.

```python
db.execute("CALL pr_close_team(%s)", (team_id,))
```

**NOTICE.** Сообщения `RAISE NOTICE` в Python по умолчанию теряются. Их нужно перехватить обработчиком:

```python
def on_notice(diag):
    print(f"[{diag.severity}] {diag.message_primary}")

db.add_notice_handler(on_notice)
```

**Транзакции в psycopg 3.**

| Режим | Поведение |
|---|---|
| по умолчанию | первый запрос открывает транзакцию, изменения видны другим только после `db.commit()` |
| `db.rollback()` | отменяет всё с начала транзакции |
| `with db.transaction():` | блок, который сам делает `commit` или `rollback` |
| `connect(autocommit=True)` | каждый запрос фиксируется сразу |

Схема «показать результат → спросить → зафиксировать или откатить»:

```python
try:
    db.execute("CALL ...", params)
except psycopg.Error as e:
    db.rollback()
    print("Ошибка:", e.diag.message_primary)
else:
    if input("Зафиксировать? (y/n): ").strip().lower() == "y":
        db.commit()
    else:
        db.rollback()
```

> Ловушка: если соединение не в autocommit и транзакция уже открыта предыдущим запросом, `with db.transaction():` создаёт только `SAVEPOINT` и при выходе ничего не фиксирует. Для этого пункта используй явные `commit()` и `rollback()`.

> Пока программа ждёт ответа «y/n», транзакция открыта и держит блокировки на изменённых строках. Из второго окна `psql` изменения не видны, а `pg_stat_activity` показывает состояние `idle in transaction`.

Триггеры работают в той же транзакции, поэтому `rollback` отменяет и то, что они записали (например, строки аудита из ЛР3).

---

## 8. Системные функции

Встроенные функции PostgreSQL вызываются так же, как свои: `SELECT f(...)`.

| Функция | Что возвращает |
|---|---|
| `version()` | строка версии сервера |
| `current_database()`, `current_user`, `current_schema()` | где и под кем ты работаешь (у `current_user` скобок нет) |
| `now()`, `current_date` | время начала транзакции, текущая дата |
| `pg_backend_pid()` | pid серверного процесса твоего соединения |
| `pg_postmaster_start_time()` | когда запущен сервер |
| `pg_database_size(name)` | размер базы в байтах |
| `pg_relation_size(t)` | размер только данных таблицы |
| `pg_total_relation_size(t)` | данные + индексы + TOAST |
| `pg_size_pretty(bytes)` | байты в виде `14 MB` |
| `inet_server_addr()`, `inet_server_port()` | адрес и порт сервера |

Статистика по таблицам есть в представлении `pg_stat_user_tables`: `relname`, `n_live_tup` (примерное число строк), `seq_scan`, `idx_scan`. Активные соединения показывает `pg_stat_activity`.

```sql
SELECT relname, pg_size_pretty(pg_relation_size(relid))
FROM pg_stat_user_tables
ORDER BY pg_relation_size(relid) DESC;
```

> Сортируй по числу байт, а не по строке `pg_size_pretty`, иначе `9 MB` окажется больше `14 MB`.

---

## 9. Создание таблицы

`CREATE TABLE` — команда DDL. В PostgreSQL DDL **транзакционный**: без `commit` таблица не появится для других соединений и пропадёт после закрытия программы.

```sql
CREATE TABLE IF NOT EXISTS sponsor (
    sponsor_id  int GENERATED ALWAYS AS IDENTITY,
    team_id     int  NOT NULL,
    name        text NOT NULL,
    amount_usd  numeric(12, 2) NOT NULL,
    kind        text NOT NULL,
    CONSTRAINT pk_sponsor PRIMARY KEY (sponsor_id),
    CONSTRAINT fk_sponsor_team FOREIGN KEY (team_id) REFERENCES team (team_id),
    CONSTRAINT chk_sponsor_amount CHECK (amount_usd > 0),
    CONSTRAINT chk_sponsor_kind CHECK (kind IN ('title', 'technical', 'partner'))
);
```

- `IF NOT EXISTS` — повторный запуск не падает (но и не изменит уже существующую таблицу).
- `GENERATED ALWAYS AS IDENTITY` — современная замена `serial`.
- Именованные ограничения (`CONSTRAINT имя`) дают понятные сообщения об ошибках и видны в пункте 4.

**Составной внешний ключ** ссылается на составной первичный ключ целиком, и порядок столбцов совпадает:

```sql
FOREIGN KEY (a, b) REFERENCES parent (a, b)
```

`ON DELETE CASCADE` удаляет дочерние строки вместе с родителем. Без него удалить родителя, у которого есть дети, не получится.

**Динамическое имя таблицы** нельзя передать через `%s`. Безопасный способ — `psycopg.sql`:

```python
from psycopg import sql
db.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(name)))
```

---

## 10. INSERT и COPY

**Одна строка:**

```python
cur = db.execute(
    "INSERT INTO sponsor (team_id, name, amount_usd, kind) VALUES (%s, %s, %s, %s) RETURNING sponsor_id",
    (team_id, name, amount, kind),
)
(new_id,) = cur.fetchone()
db.commit()
```

`RETURNING` сразу возвращает вставленные значения (сгенерированный id и т. п.).

**Пакет строк:** `cur.executemany(sql, list_of_tuples)`. Это быстрее цикла с `execute`, но медленнее `COPY`.

**Понятные ошибки ограничений.** Лови конкретные классы:

```python
from psycopg import errors

try:
    ...
except errors.ForeignKeyViolation:
    db.rollback(); print("Такой команды нет")
except errors.CheckViolation as e:
    db.rollback(); print("Нарушено условие", e.diag.constraint_name)
```

**COPY** — самый быстрый способ загрузки: данные идут потоком, без разбора отдельных `INSERT`.

```python
with db.cursor() as cur:
    with cur.copy("COPY sponsor (team_id, name, amount_usd, kind) FROM STDIN WITH (FORMAT csv, HEADER)") as copy:
        with open("sponsors.csv", "rb") as f:
            while chunk := f.read(8192):
                copy.write(chunk)
db.commit()
```

- `FROM STDIN` — данные шлёт клиент (твоя программа). `COPY ... FROM '/path'` читал бы файл на **сервере**, то есть внутри контейнера.
- Вместо сырых байтов можно отправлять кортежи: `copy.write_row((1, "Shell", 1000, "title"))`.
- Список столбцов в `COPY` должен совпадать с порядком столбцов в CSV. Столбец `IDENTITY` в него не включают.
- **`COPY` атомарен**: одна плохая строка (нет такого внешнего ключа, нарушен `CHECK`) отменяет загрузку **целиком**, и в ошибке будет указан номер строки (`CONTEXT: COPY sponsor, line 5`).

Есть и обратное направление: `COPY (SELECT ...) TO STDOUT WITH (FORMAT csv, HEADER)` и `copy.read()` / `for row in copy.rows()`.

---

## Сборка в меню

Итоговое приложение — цикл: показать пункты, прочитать номер, вызвать функцию, поймать ошибку, повторить.

```python
ACTIONS = {
    "1": ("Скалярный запрос", task_scalar),
    "2": ("Несколько JOIN", task_join),
    # ...
}

def main():
    with connect() as db:
        db.add_notice_handler(on_notice)
        while True:
            for key, (title, _) in ACTIONS.items():
                print(f"{key}. {title}")
            choice = input("> ").strip()
            if choice == "0":
                break
            if choice not in ACTIONS:
                continue
            try:
                ACTIONS[choice][1](db)
            except psycopg.Error as e:
                db.rollback()
                print("Ошибка БД:", e.diag.message_primary or e)
            except ValueError:
                print("Неверный ввод")
```

- Одно соединение на всё приложение, оно передаётся в каждую функцию.
- Пункты, которые только читают, тоже открывают транзакцию. После них стоит сделать `db.rollback()` (или `commit()`), чтобы соединение не висело в `idle in transaction`.
- Ввод чисел и дат проверяй в Python (`int(...)`, `date.fromisoformat(...)`) до отправки в базу.

Подробнее: [psycopg 3 docs](https://www.psycopg.org/psycopg3/docs/), [PostgreSQL: Window Functions](https://www.postgresql.org/docs/current/tutorial-window.html), [System Information Functions](https://www.postgresql.org/docs/current/functions-info.html), [COPY](https://www.postgresql.org/docs/current/sql-copy.html).
