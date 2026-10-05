create or replace procedure pr_studio_gaps(p_company int)
language plpgsql
as $$
declare
    cur_game cursor (c_company int) for
        select g.title as name, g.first_release_date as release_date
        from game_release gr
        join game g on gr.game_id = g.id
        where gr.company_id = c_company
          and gr.role = 'developer'
          and g.first_release_date is not null
        order by g.first_release_date, g.id;

    rec record;
    prev_name text;
    prev_date date;
    gap int;
    max_gap int := -1;
    from_name text;
    to_name text;
    cnt int := 0;
begin
    if p_company is null then
        raise exception 'Идентификатор студии не должен быть NULL';
    end if;

    if not exists (select 1 from company c where c.id = p_company) then
        raise exception 'Студия % не найдена', p_company;
    end if;

    open cur_game(p_company);
    loop
        fetch cur_game into rec;
        exit when not found;

        cnt := cnt + 1;

        if prev_date is not null then
            gap := rec.release_date - prev_date;
            raise notice '"%" -> "%": % дн.', prev_name, rec.name, gap;

            if gap > max_gap then
                max_gap := gap;
                from_name := prev_name;
                to_name := rec.name;
            end if;
        end if;

        prev_name := rec.name;
        prev_date := rec.release_date;
    end loop;
    close cur_game;

    if cnt < 2 then
        raise notice 'У студии % меньше двух игр с датой выхода', p_company;
    else
        raise notice 'Игр: %. Самая долгая пауза: % дн. — между "%" и "%"', cnt, max_gap, from_name, to_name;
    end if;
end;
$$;
