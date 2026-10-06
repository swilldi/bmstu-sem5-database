-- распределение игр по жанрам: топ-N самых популярных жанров
-- (сколько игр и какой процент от всех игр) и итоговая строка "другие" —
-- игры, у которых нет ни одного жанра из топа
create or replace function fn_raspredelenie_genre(p_limit int default 5)
returns table(genre_name text, game_count int, share numeric)
language plpgsql
stable
as $$
declare
    v_total int;
    v_top int[];
begin
    if p_limit is null or p_limit <= 0 then
        raise exception 'Количество жанров должно быть положительным';
    end if;

    select count(*) into v_total from game;

    if v_total = 0 then
        raise notice 'В базе нет игр';
        return;
    end if;

    select array_agg(t.genre_id) into v_top
    from (
        select gg.genre_id
        from game_genre gg
        group by gg.genre_id
        order by count(*) desc, gg.genre_id
        limit p_limit
    ) t;

    return query
        select ge.name, count(*)::int, round(100.0 * count(*) / v_total, 2)
        from game_genre gg
        join genre ge on ge.id = gg.genre_id
        where gg.genre_id = any(v_top)
        group by ge.id, ge.name
        order by count(*) desc, ge.id;

    genre_name := 'другие';
    select count(*) into game_count
    from game g
    where not exists (
        select 1 from game_genre gg
        where gg.game_id = g.id
          and gg.genre_id = any(v_top)
    );
    share := round(100.0 * game_count / v_total, 2);
    return next;
end;
$$;


-- тест
select * from fn_raspredelenie_genre();      -- топ-5 + "другие"
select * from fn_raspredelenie_genre(1);     -- только самый популярный жанр
select * from fn_raspredelenie_genre(1000);  -- больше, чем жанров: в "другие" попадут только игры без жанров
select * from fn_raspredelenie_genre(0);     -- ошибка
