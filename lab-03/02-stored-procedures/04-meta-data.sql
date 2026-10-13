-- Информация о таблице: столбцы, ограничения, триггеры, размер
drop procedure if exists pr_table_info(text);

create or replace procedure pr_table_info(p_table text)
language plpgsql
as $$
declare
    v_oid regclass;
    r record;
begin
    -- to_regclass возвращает null, если таблицы нет
    v_oid := to_regclass(p_table);

    if v_oid is null then
        raise exception 'Таблица % не найдена', p_table;
    end if;

    raise notice 'Столбцы:';
    for r in (select c.column_name, c.data_type, c.is_nullable, c.column_default
              from information_schema.columns c
              where c.table_name = p_table
              order by c.ordinal_position)
    loop
        raise notice '  % % % %', r.column_name, r.data_type,
            case when r.is_nullable = 'NO' then 'not null' else '' end,
            coalesce('default ' || r.column_default, '');
    end loop;

    raise notice 'Ограничения:';
    for r in (select con.conname, con.contype, pg_get_constraintdef(con.oid) as def
              from pg_constraint con
              where con.conrelid = v_oid
              order by con.contype, con.conname)
    loop
        raise notice '  % (%) %', r.conname, r.contype, r.def;
    end loop;

    raise notice 'Триггеры:';
    for r in (select tg.tgname
              from pg_trigger tg
              where tg.tgrelid = v_oid and not tg.tgisinternal)
    loop
        raise notice '  %', r.tgname;
    end loop;

    raise notice 'Размер: %', pg_size_pretty(pg_total_relation_size(v_oid));
end;
$$;


call pr_table_info('race_entry');

call pr_table_info('team');

call pr_table_info('abc');
