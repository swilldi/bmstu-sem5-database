create or replace procedure pr_table_links(p_table text)
language plpgsql
as $$
declare
    v_table regclass;
    r record;
begin
    v_table := to_regclass(p_table);
    if v_table is null then
        raise exception 'Таблица "%" не найдена', p_table;
    end if;

    raise notice '=== Связи таблицы % ===', v_table;

    raise notice '-- Ссылается на:';
    for r in
        select con.conname, pg_get_constraintdef(con.oid) as def
        from pg_constraint con
        where con.contype = 'f'
          and con.conrelid = v_table
    loop
        raise notice '   %: %', r.conname, r.def;
    end loop;

    raise notice '-- На неё ссылаются:';
    for r in
        select con.conrelid::regclass as from_table, pg_get_constraintdef(con.oid) as def
        from pg_constraint con
        where con.contype = 'f'
          and con.confrelid = v_table
    loop
        raise notice '   из %: %', r.from_table, r.def;
    end loop;
end;
$$;
