-- Дисквалификация пилота и сдвиг мест тех, кто финишировал ниже
create or replace procedure pr_disqualify(p_driver_id int, p_race_date date)
language plpgsql
as $$
declare
    v_finish_position int;
    v_track_id int;
    v_row_moved int := 0;
    r record;
begin
    if not exists (select 1 from race_entry re where re.driver_id = p_driver_id and re.race_date = p_race_date and re.status = 'finished') then
        raise exception ' Пилот не найден или он не финишировал';
    end if;

    select re.finish_position, re.track_id
    into v_finish_position, v_track_id
    from race_entry re
    where re.driver_id = p_driver_id and re.race_date = p_race_date;

    update race_entry re
    set status = 'dsq',
        finish_position = null,
        best_lap = null,
        total_time = null
    where re.driver_id = p_driver_id and re.race_date = p_race_date;

    for r in (select finish_position 
    from race_entry re 
    where re.track_id = v_track_id and re.race_date = p_race_date and re.finish_position > v_finish_position 
    order by finish_position) 
    loop
        update race_entry re
            set finish_position = re.finish_position - 1
        where re.track_id = v_track_id and re.race_date = p_race_date and re.finish_position = r.finish_position;
        
        v_row_moved := v_row_moved + 1;
    end loop;

    raise notice 'Перемещено % значений', v_row_moved;
end;
$$;
