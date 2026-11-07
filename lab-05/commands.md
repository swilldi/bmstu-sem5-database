# ЛР5 — основные команды JSON в PostgreSQL

Формат: **команда** — описание, ниже общий пример.
В примерах `t` — таблица, `doc` — столбец `jsonb`.

---

## 1. Выгрузка данных таблицы в JSON

- **`to_jsonb(row)` / `row_to_json(row)`** — превращает строку таблицы в JSON-объект (ключи = имена столбцов).
  ```sql
  SELECT to_jsonb(t) FROM t;
  ```
- **`jsonb_build_object(k1, v1, k2, v2, ...)`** — собирает объект из пар ключ–значение (свои имена ключей, выбор полей).
  ```sql
  SELECT jsonb_build_object('id', id, 'name', name) FROM t;
  ```
- **`jsonb_build_array(v1, v2, ...)`** — собирает массив из значений.
  ```sql
  SELECT jsonb_build_array(id, name) FROM t;
  ```
- **`jsonb_agg(expr ORDER BY ...)`** — агрегат: собирает значения из многих строк в один массив.
  ```sql
  SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM t;
  ```
- **`jsonb_object_agg(key, value)`** — агрегат: собирает строки в один объект `{key: value}`.
  ```sql
  SELECT jsonb_object_agg(id, name) FROM t;
  ```
- **`jsonb_pretty(doc)`** — форматирует JSON с отступами (для чтения).
  ```sql
  SELECT jsonb_pretty(jsonb_agg(t)) FROM t;
  ```
- **`json_strip_nulls(doc)` / `jsonb_strip_nulls(doc)`** — убирает из объекта ключи со значением `null`.
  ```sql
  SELECT jsonb_strip_nulls(to_jsonb(t)) FROM t;
  ```

## 2. Сохранение в файл и загрузка из файла

- **`\o файл` … `\o`** (psql) — перенаправляет вывод запроса в файл; `\t on` убирает заголовки, `\a` — выравнивание.
  ```sql
  \t on
  \a
  \o t.json
  SELECT jsonb_agg(t) FROM t;
  \o
  ```
- **`COPY (запрос) TO 'файл'`** — выгрузка результата на стороне сервера (`\copy` — на стороне клиента).
  ```sql
  \copy (SELECT jsonb_agg(t) FROM t) TO 't.json'
  ```
- **`pg_read_file('путь')`** — читает файл на сервере как текст; приводим к `jsonb`.
  ```sql
  SELECT pg_read_file('/workspace/data/t.json')::jsonb;
  ```
- **``\set var `cat файл` ``** (psql) — читает файл на клиенте в переменную, далее `:'var'`.
  ```sql
  \set content `cat t.json`
  SELECT :'content'::jsonb;
  ```
- **`CREATE TABLE ... (LIKE t INCLUDING ALL)`** — таблица-копия той же структуры, куда грузим данные.
  ```sql
  CREATE TABLE t_copy (LIKE t INCLUDING ALL);
  ```
- **`jsonb_populate_recordset(NULL::t, arr)`** — разворачивает массив объектов в строки типа таблицы `t`.
  ```sql
  INSERT INTO t_copy
  SELECT * FROM jsonb_populate_recordset(NULL::t, pg_read_file('/workspace/data/t.json')::jsonb);
  ```
- **`jsonb_to_recordset(arr) AS x(col type, ...)`** — то же, но столбцы и типы задаются вручную.
  ```sql
  SELECT * FROM jsonb_to_recordset('[{"id":1,"name":"a"}]') AS x(id int, name text);
  ```
- **`EXCEPT`** — проверка, что копия совпадает с оригиналом (оба запроса должны дать 0 строк).
  ```sql
  SELECT * FROM t EXCEPT SELECT * FROM t_copy;
  SELECT * FROM t_copy EXCEPT SELECT * FROM t;
  ```
- **`setval(pg_get_serial_sequence(...), max)`** — выравнивает serial-счётчик после вставки с явными id.
  ```sql
  SELECT setval(pg_get_serial_sequence('t_copy', 'id'), (SELECT max(id) FROM t_copy));
  ```

## 2а. Выгрузка всей БД в JSON

- **`json_build_object('t1', (SELECT json_agg(...)), ...)`** — вся БД одним документом `{таблица: [строки]}`, таблицы перечислены вручную. Берём `json`, а не `jsonb`: `json` сохраняет порядок ключей, `jsonb` сортирует их (сначала короткие).
  ```sql
  SELECT json_build_object(
    'team',       (SELECT json_agg(t ORDER BY team_id) FROM team t),
    'car',        (SELECT json_agg(t ORDER BY car_id)  FROM car t),
    'race_entry', (SELECT json_agg(t ORDER BY race_date, track_id, driver_id) FROM race_entry t)
  );
  ```
- **`EXECUTE format('... %I.%I ...')` по `information_schema.tables`** — то же, но список таблиц берётся из каталога. Имя таблицы нельзя передать параметром, поэтому нужен динамический SQL; `%I` экранирует идентификатор, `coalesce(..., '[]')` даёт `[]` для пустой таблицы.
  ```sql
  CREATE OR REPLACE FUNCTION db_to_jsonb(p_schema text DEFAULT 'public')
  RETURNS jsonb LANGUAGE plpgsql AS $$
  DECLARE r record; res jsonb := '{}'; part jsonb;
  BEGIN
    FOR r IN SELECT table_name FROM information_schema.tables
             WHERE table_schema = p_schema AND table_type = 'BASE TABLE'
    LOOP
      EXECUTE format('SELECT coalesce(jsonb_agg(to_jsonb(t)), ''[]'') FROM %I.%I t',
                     p_schema, r.table_name)
      INTO part;
      res := res || jsonb_build_object(r.table_name, part);
    END LOOP;
    RETURN res;
  END $$;

  SELECT db_to_jsonb();
  ```
- **`psql -At -c "..." -o файл`** — сохранить результат в файл с хоста; `-A` убирает выравнивание, `-t` — заголовки, в файле остаётся только JSON.
  ```bash
  PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d study -At -c "SELECT db_to_jsonb()" -o db.json
  ```
- **Цикл в shell** — отдельный файл на каждую таблицу (удобнее смотреть и грузить по одной).
  ```bash
  for t in team track driver car race_entry contract; do
    PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d study -At -c "SELECT json_agg(x) FROM $t x" -o "$t.json"
  done
  ```
- **`jsonb_populate_recordset(NULL::t, doc -> 't')`** — обратная загрузка: каждый ключ документа разворачивается в свою таблицу. Порядок — по внешним ключам: `team`, `track`, `driver` → `car` → `race_entry`, `contract`. Ссылка `team` на саму себя не мешает: внешний ключ проверяется в конце `INSERT`.
  ```sql
  INSERT INTO team_copy
  SELECT * FROM jsonb_populate_recordset(NULL::team, (SELECT doc -> 'team' FROM json_import WHERE id = 1));
  ```
- **`information_schema.columns` → JSON** — описание структуры (столбцы, типы, `NULL`), которое можно приложить к выгрузке.
  ```sql
  SELECT jsonb_object_agg(table_name, cols) FROM (
    SELECT table_name,
           jsonb_agg(jsonb_build_object('column', column_name, 'type', data_type,
                                        'nullable', is_nullable = 'YES') ORDER BY ordinal_position) AS cols
    FROM information_schema.columns
    WHERE table_schema = 'public'
    GROUP BY table_name
  ) s;
  ```

Что важно:
- В JSON попадают только данные. Ограничения, ключи, индексы и последовательности не сохраняются; для полной копии структуры есть `pg_dump -s`.
- `date` и `interval` превращаются в строки (`"best_lap": "00:01:51.792"`), а при загрузке через `jsonb_populate_recordset` восстанавливаются точно. `NULL` сохраняется как `null`, столбцы `jsonb` вкладываются как есть.
- Документ собирается в памяти целиком. Вся учебная БД — около 18 MB; для очень больших баз лучше файл на таблицу или `COPY`.
- Вложенный документ («команда → машины → заезды») — это уже не копия БД, а отчёт: связи видны сразу, но восстановить таблицы из него сложнее.

## 3. Столбец JSON/JSONB и его заполнение

- **`json` vs `jsonb`** — `json` хранит текст как есть; `jsonb` — бинарный, без дублей ключей, поддерживает индексы и операторы `?`, `@>`. В работе используем `jsonb`.
- **`ALTER TABLE ... ADD COLUMN ... jsonb`** — добавляет JSON-столбец в существующую таблицу.
  ```sql
  ALTER TABLE t ADD COLUMN doc jsonb;
  ```
- **`CREATE TABLE` со столбцом `jsonb`** — новая таблица с JSON-атрибутом.
  ```sql
  CREATE TABLE t (id serial PRIMARY KEY, doc jsonb NOT NULL DEFAULT '{}');
  ```
- **`INSERT ... '{...}'::jsonb`** — вставка JSON-литерала.
  ```sql
  INSERT INTO t (doc) VALUES ('{"a": 1, "tags": ["x", "y"]}');
  ```
- **`UPDATE ... SET doc = ...`** — заполнение столбца для существующих строк.
  ```sql
  UPDATE t SET doc = jsonb_build_object('a', 1, 'b', true) WHERE id = 1;
  ```
- **`CHECK (jsonb_typeof(doc) = 'object')`** — ограничение на тип документа. `jsonb_typeof` возвращает `object`, `array`, `string`, `number`, `boolean`, `null`.
  ```sql
  ALTER TABLE t ADD CONSTRAINT doc_is_object CHECK (jsonb_typeof(doc) = 'object');
  ```

## 4.1. Извлечение фрагмента JSON

- **`doc -> 'key'`** — значение по ключу как `jsonb` (фрагмент).
  ```sql
  SELECT doc -> 'engine' FROM t;
  ```
- **`doc -> n`** — элемент массива по индексу (с 0; `-1` — последний).
  ```sql
  SELECT doc -> 'tags' -> 0 FROM t;
  ```
- **`doc #> '{a,b,0}'`** — фрагмент по пути (ключи и индексы).
  ```sql
  SELECT doc #> '{engine,hybrid}' FROM t;
  ```
- **`jsonb_path_query(doc, 'jsonpath')`** — все фрагменты по JSONPath (каждый — отдельной строкой).
  ```sql
  SELECT jsonb_path_query(doc, '$.items[*] ? (@.x > 10)') FROM t;
  ```
- **`jsonb_path_query_array` / `jsonb_path_query_first`** — то же, но результат одним массивом / только первый.
  ```sql
  SELECT jsonb_path_query_array(doc, '$.items[*].name') FROM t;
  ```
- **`JSON_QUERY(doc, 'path')`** (PG 17+, стандарт SQL) — возвращает фрагмент по пути.
  ```sql
  SELECT JSON_QUERY(doc, '$.items') FROM t;
  ```

## 4.2. Извлечение значений узлов

- **`doc ->> 'key'`** — значение по ключу как `text` (скаляр). Для чисел — приведение типа.
  ```sql
  SELECT (doc ->> 'speed')::int FROM t;
  ```
- **`doc #>> '{a,b}'`** — значение по пути как `text`.
  ```sql
  SELECT doc #>> '{engine,layout}' FROM t;
  ```
- **`JSON_VALUE(doc, 'path' RETURNING type)`** (PG 17+) — скалярное значение сразу нужного типа.
  ```sql
  SELECT JSON_VALUE(doc, '$.engine.cylinders' RETURNING int) FROM t;
  ```
- **`jsonb_array_length(arr)`** — длина массива.
  ```sql
  SELECT jsonb_array_length(doc -> 'tags') FROM t;
  ```
- **Использование в `WHERE` / `ORDER BY` / `GROUP BY`** — значения узлов работают как обычные столбцы.
  ```sql
  SELECT doc ->> 'type', count(*) FROM t GROUP BY doc ->> 'type';
  ```

## 4.3. Проверка существования узла

- **`doc ? 'key'`** — есть ли ключ верхнего уровня (или строка в массиве).
  ```sql
  SELECT * FROM t WHERE doc ? 'aero';
  ```
- **`doc ?| ARRAY['a','b']`** — есть хотя бы один из ключей.
  ```sql
  SELECT * FROM t WHERE doc ?| ARRAY['aero', 'sponsors'];
  ```
- **`doc ?& ARRAY['a','b']`** — есть все ключи.
  ```sql
  SELECT * FROM t WHERE doc ?& ARRAY['aero', 'sponsors'];
  ```
- **`doc @> '{...}'`** — документ содержит указанный фрагмент (вложенность учитывается).
  ```sql
  SELECT * FROM t WHERE doc @> '{"engine": {"turbo": true}}';
  ```
- **`doc <@ '{...}'`** — документ содержится в указанном.
  ```sql
  SELECT * FROM t WHERE doc <@ '{"a": 1, "b": 2}';
  ```
- **`doc @? 'jsonpath'` / `jsonb_path_exists(doc, 'jsonpath')`** — есть ли что-то по JSONPath (в т. ч. с условием).
  ```sql
  SELECT * FROM t WHERE doc @? '$.engine.hybrid';
  SELECT * FROM t WHERE jsonb_path_exists(doc, '$.items[*] ? (@.x > 30)');
  ```
- **`doc @@ 'jsonpath-предикат'`** — истинно ли условие JSONPath.
  ```sql
  SELECT * FROM t WHERE doc @@ '$.speed > 300';
  ```
- **`JSON_EXISTS(doc, 'path')`** (PG 17+) — стандартная проверка существования пути.
  ```sql
  SELECT JSON_EXISTS(doc, '$.aero.drs') FROM t;
  ```
- **`doc -> 'key' IS NULL`** — простая проверка через извлечение (учтите: ключ со значением `null` даст не SQL NULL, а `'null'::jsonb`).
  ```sql
  SELECT * FROM t WHERE doc -> 'aero' IS NULL;
  ```

## 4.4. Изменение JSON-документа

- **`jsonb_set(doc, '{path}', new_value, create_missing)`** — заменяет (или создаёт) значение по пути.
  ```sql
  UPDATE t SET doc = jsonb_set(doc, '{engine,turbo}', 'true') WHERE id = 1;
  ```
- **`jsonb_insert(doc, '{path}', value, insert_after)`** — вставляет элемент в массив (или новый ключ).
  ```sql
  UPDATE t SET doc = jsonb_insert(doc, '{tags,-1}', '"z"', true) WHERE id = 1;
  ```
- **`doc || '{...}'`** — слияние: добавляет/перезаписывает ключи верхнего уровня; для массивов — конкатенация.
  ```sql
  UPDATE t SET doc = doc || '{"homologated": false}' WHERE id = 1;
  ```
- **`doc - 'key'`** — удаляет ключ верхнего уровня.
  ```sql
  UPDATE t SET doc = doc - 'aero' WHERE id = 1;
  ```
- **`doc - n`** — удаляет элемент массива по индексу.
  ```sql
  UPDATE t SET doc = doc - 0 WHERE id = 1;   -- если doc — массив
  ```
- **`doc #- '{path}'`** — удаляет узел по вложенному пути.
  ```sql
  UPDATE t SET doc = doc #- '{engine,hybrid}' WHERE id = 1;
  ```
- **`jsonb_set_lax(doc, path, value, ..., 'delete_key')`** — как `jsonb_set`, но задаёт поведение при `NULL` значении.
  ```sql
  SELECT jsonb_set_lax(doc, '{aero}', NULL, true, 'delete_key') FROM t;
  ```

## 4.5. Разбиение документа на строки

- **`jsonb_array_elements(arr)`** — каждый элемент массива → отдельная строка (`jsonb`).
  ```sql
  SELECT t.id, e FROM t, jsonb_array_elements(t.doc -> 'items') AS e;
  ```
- **`jsonb_array_elements_text(arr)`** — то же, но элементы как `text`.
  ```sql
  SELECT t.id, tag FROM t, jsonb_array_elements_text(t.doc -> 'tags') AS tag;
  ```
- **`jsonb_each(obj)` / `jsonb_each_text(obj)`** — каждая пара ключ–значение объекта → строка `(key, value)`.
  ```sql
  SELECT t.id, kv.key, kv.value FROM t, jsonb_each(t.doc -> 'engine') AS kv;
  ```
- **`jsonb_object_keys(obj)`** — список ключей объекта строками.
  ```sql
  SELECT DISTINCT jsonb_object_keys(doc) FROM t;
  ```
- **`jsonb_to_recordset(arr) AS x(col type, ...)`** — массив объектов → таблица с типизированными столбцами.
  ```sql
  SELECT t.id, x.* FROM t, jsonb_to_recordset(t.doc -> 'items') AS x(name text, x numeric);
  ```
- **`WITH ORDINALITY`** — добавляет к развёрнутым строкам порядковый номер элемента.
  ```sql
  SELECT t.id, e.n, e.val FROM t, jsonb_array_elements(t.doc -> 'items') WITH ORDINALITY AS e(val, n);
  ```
- **`LEFT JOIN LATERAL ... ON true`** — разворачивает, не теряя строки с пустым массивом / без ключа.
  ```sql
  SELECT t.id, e FROM t LEFT JOIN LATERAL jsonb_array_elements(t.doc -> 'items') AS e ON true;
  ```
- **`JSON_TABLE(doc, 'path' COLUMNS (...))`** (PG 17+) — стандартный способ превратить JSON в таблицу.
  ```sql
  SELECT t.id, jt.*
  FROM t, JSON_TABLE(t.doc, '$.items[*]' COLUMNS (name text PATH '$.name', x numeric PATH '$.x')) AS jt;
  ```

## Дополнительно: индексы

- **`CREATE INDEX ... USING gin (doc)`** — ускоряет `?`, `?|`, `?&`, `@>`, `@?`, `@@`.
  ```sql
  CREATE INDEX t_doc_gin ON t USING gin (doc);
  ```
- **`USING gin (doc jsonb_path_ops)`** — индекс меньше и быстрее, но только для `@>`, `@?`, `@@`.
  ```sql
  CREATE INDEX t_doc_path ON t USING gin (doc jsonb_path_ops);
  ```
- **Индекс по выражению** — для частого поиска по одному полю.
  ```sql
  CREATE INDEX t_doc_type ON t ((doc ->> 'type'));
  ```

## Краткий синтаксис JSONPath

| Элемент | Значение |
|---|---|
| `$` | корень документа |
| `.key` | ключ объекта |
| `[0]`, `[*]`, `[last]` | элемент массива / все / последний |
| `? (@.x > 1)` | фильтр, `@` — текущий элемент |
| `.size()`, `.type()`, `.double()` | методы |
| `&&`, `\|\|`, `!`, `like_regex`, `exists(...)` | логика в фильтрах |
