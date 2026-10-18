-- Задание 6. Пользовательский тип race_result
--
-- Составной тип «результат заезда», который умеет сравнивать два результата
-- между собой.
--
-- Конструктор make_race_result(status, finish_position, laps, total_time)
-- проверяет те же правила, что CHECK на race_entry:
-- - status входит в finished, dnf, dsq или dns;
-- - finished <=> finish_position IS NOT NULL <=> total_time IS NOT NULL;
-- - для dns выполняется laps = 0;
-- - total_time лежит в диапазоне 1 мин ... 30 ч.
-- Интервал переводится в секунды (total_s). Ошибки называют нарушенное правило.
--
-- Методы, минимум три:
-- - rr_is_classified(race_result) — финишировал ли пилот;
-- - rr_format(race_result) — "P3 · 58 laps · 1:32:15.124" для финишёров
--   и "DNF (lap 23)", "DSQ", "DNS" для остальных;
-- - rr_gap(a, b) — насколько a позади b: "+12.345 s" или "+2 laps".
--   Если оба не финишировали, NULL.
--
-- Оператор a >> b означает «результат a лучше b». Функция под ним —
-- rr_better(race_result, race_result). Правила по порядку:
-- 1. finished лучше любого нефинишировавшего;
-- 2. оба finished — лучше тот, у кого меньше finish_position;
-- 3. оба не финишировали — лучше тот, у кого больше laps;
-- 4. dns хуже всех, dsq хуже dnf при равных кругах.
-- Объяви у оператора COMMUTATOR или NEGATOR, если они уместны,
-- и обоснуй выбор.
--
-- Проверка:
-- 1. Дуэли напарников. Напарники — это два пилота в одной гонке, чьи машины
--    принадлежат одной команде. Для каждой команды и сезона посчитай, сколько
--    раз каждый пилот был лучше напарника. Сравнивай только через >> по
--    make_race_result(...).
-- 2. В каждой гонке победитель лучше (>>) всех остальных участников. Запрос,
--    ищущий нарушения, возвращает 0 строк.
-- 3. Ошибки конструктора, минимум три разных: finished без времени, dns
--    с кругами, неизвестный статус.
-- 4. Литерал '(finished,,10,100)'::race_result обходит конструктор. Покажи это
--    и закрой дыру доменом race_result_d с проверкой rr_valid(VALUE).

drop type if exists race_result cascade;

create type race_result as (
    status          text,
    finish_position int,
    laps            int,
    total_s         float8
);

-- Конструктор

create or replace function make_race_result(status text, finish_position int, laps int, total_time interval)
returns race_result
language plpython3u
as $$
    pass
$$;

-- Методы

create or replace function rr_is_classified(r race_result)
returns boolean
language plpython3u
as $$
    pass
$$;

create or replace function rr_format(r race_result)
returns text
language plpython3u
as $$
    pass
$$;

create or replace function rr_gap(a race_result, b race_result)
returns text
language plpython3u
as $$
    pass
$$;

-- Оператор

create or replace function rr_better(a race_result, b race_result)
returns boolean
language plpython3u
as $$
    pass
$$;

create operator >> (
    leftarg  = race_result,
    rightarg = race_result,
    function = rr_better
);

-- Домен, закрывающий обход конструктора

create or replace function rr_valid(r race_result)
returns boolean
language plpython3u
as $$
    pass
$$;

create domain race_result_d as race_result
    check (rr_valid(value));
