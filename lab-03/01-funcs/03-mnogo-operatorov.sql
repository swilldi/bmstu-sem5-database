drop function if exists fn_driver_career(int);

create or replace function fn_driver_career(p_driver_id int)
returns table(metric text, value text)
language plpgsql
stable
as $$
declare
    v_starts int;
    v_wins int;
    v_podiums int;
    v_dnf int;
    v_drops_percent numeric(5, 2);
    v_best_start_position smallint;
    v_teams int;
    v_first_race date;
    v_last_race date;
begin
    if p_driver_id is null then
        raise exception 'Не передан id пилота';
    end if;

    if not exists (select 1 from driver d where d.driver_id = p_driver_id) then
        raise exception 'Пилот % не найден', p_driver_id;
    end if;

    select count(distinct team_id)
    into v_teams
    from contract
    where driver_id = p_driver_id;

    select  count(*) filter (where status != 'dns'),
            count(*) filter (where finish_position = 1),
            count(*) filter (where finish_position <= 3),
            count(*) filter (where status = 'dnf'),
            min(grid_position),
            min(race_date),
            max(race_date)
    into v_starts, v_wins, v_podiums, v_dnf, v_best_start_position, v_first_race, v_last_race
    from race_entry re
    where driver_id = p_driver_id;

    v_drops_percent := round(v_dnf::numeric / nullif(v_starts, 0) * 100, 2);

    return query values
        ('Стартов', v_starts::text),
        ('Побед', v_wins::text),
        ('Подиумов', v_podiums::text),
        ('Сходов', v_drops_percent::text || '%'),
        ('Лучшая позиция на старте', v_best_start_position::text),
        ('Команд', v_teams::text),
        ('Первая гонка', v_first_race::text),
        ('Последняя гонка', v_last_race::text);
end;
$$;

-- пилот с самой длинной карьерой
select * from fn_driver_career(736);

-- все заезды со статусом dns: стартов 0, процент сходов пустой
select * from fn_driver_career(7);

-- пилот без гонок и контрактов: нули
select * from fn_driver_career(28);

-- ошибки
select * from fn_driver_career(999999);
select * from fn_driver_career(null);
