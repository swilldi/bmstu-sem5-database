-- Задание 2. Агрегат best_podium_streak
--
-- Самая длинная серия подряд идущих заездов пилота с подиумом
-- (finish_position <= 3). Любой заезд вне подиума обрывает серию,
-- включая сход, где finish_position IS NULL.
--
-- - Состояние — составной тип или jsonb с полями «текущая серия» и
--   «лучшая серия». Сумма или счётчик не подходят.
-- - SFUNC обновляет состояние, FINALFUNC возвращает лучшую серию.
-- - Агрегат зависит от порядка строк, поэтому вызывается с ORDER BY
--   внутри скобок:
--     select driver_id, best_podium_streak(finish_position order by race_date)
--     from race_entry group by driver_id;
-- - Пилот с одними сходами получает 0, а не NULL, и агрегат по пустому
--   набору строк тоже даёт 0. Подумай, нужен ли для этого INITCOND и стоит ли
--   объявлять SFUNC как STRICT: у сходов finish_position IS NULL, и STRICT их
--   просто пропустит.
--
-- Проверка:
-- 1. Топ-10 пилотов по самой длинной серии подиумов.
-- 2. Эталон на чистом SQL по схеме «gaps and islands»
--    (row_number() - row_number() по признаку «подиум»). Запрос
--    select count(*) from (python_vs_sql) where py is distinct from sql_result
--    возвращает 0.
-- 3. Для одного пилота проверь ответ вручную: выведи его заезды по дате и
--    посчитай серию глазами.
-- 4. (*) Покажи, что будет без ORDER BY внутри агрегата, и объясни,
--    почему так нельзя.

drop type if exists podium_streak cascade;
create type podium_streak as (
    len int,
    max_len int
);

create or replace function best_podium_streak_state(state podium_streak, finish_position int)
returns podium_streak
language plpython3u
as $$
    if finish_position is not None and finish_position <= 3:
        state["len"] += 1
    else:
        state["max_len"] = max(state["max_len"], state["len"])
        state["len"] = 0

    return state
$$;

create or replace function best_podium_streak_finish_state(state podium_streak)
returns int
language plpython3u
as $$
    return max(state["max_len"], state["len"])
$$;

create or replace aggregate best_podium_streak(int) (
    sfunc     = best_podium_streak_state,
    stype     = podium_streak,
    finalfunc = best_podium_streak_finish_state,
    initcond = '(0, 0)'
);
