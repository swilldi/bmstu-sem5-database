-- Гонки пилота по порядку: старт -> финиш, сколько позиций отыграл, самая длинная серия финишей
drop procedure if exists pr_driver_form(int);

create or replace procedure pr_driver_form(p_driver_id int)
language plpgsql
as $$
declare
    cur cursor for
        select re.race_date, t.name as track_name, re.grid_position, re.finish_position, re.status
        from race_entry re
        join track t using (track_id)
        where re.driver_id = p_driver_id
        order by re.race_date;
    r record;
    v_races int := 0;
    v_gained int;
    v_total_gained int := 0;
    v_streak int := 0;
    v_max_streak int := 0;
begin
    if not exists (select 1 from driver d where d.driver_id = p_driver_id) then
        raise exception 'Пилот не найден';
    end if;

    open cur;
    loop
        fetch cur into r;
        exit when not found;

        v_races := v_races + 1;

        if r.status = 'finished' then
            v_gained := r.grid_position - r.finish_position;
            v_total_gained := v_total_gained + v_gained;

            v_streak := v_streak + 1;
            if v_streak > v_max_streak then
                v_max_streak := v_streak;
            end if;

            raise notice '% | % | % -> % | %', r.race_date, r.track_name, r.grid_position, r.finish_position,
                case when v_gained > 0 then '+' || v_gained else v_gained::text end;
        else
            v_streak := 0;
            raise notice '% | % | % -> %', r.race_date, r.track_name, r.grid_position, r.status;
        end if;
    end loop;
    close cur;

    if v_races = 0 then
        raise notice 'Нет гонок';
        return;
    end if;

    raise notice 'Гонок: %, самая длинная серия финишей: %, всего отыграно позиций: %', v_races, v_max_streak, v_total_gained;
end;
$$;


call pr_driver_form(108);

-- call pr_driver_form(29);

-- call pr_driver_form(28);

-- call pr_driver_form(999999);
