-- переход пилота в другую команду

create or replace procedure transfer_driver(p_driver_id int, p_new_team_id int, p_on date)
language plpython3u
as $$
    -- проверки проверочки

    close_contract_plan = plpy.prepare("""
        update contract
        set end_date = $1 - 1
        where driver_id = $2 and end_date is null
    """, ["date", "int"])

    plpy.execute(close_contract_plan, [p_on, p_driver_id])

    add_contract_plan = plpy.prepare("""
        insert into contract (driver_id, team_id, start_date, end_date)
        values ($1, $2, $3, null)
    """, ["int", "int", "date"])

    plpy.execute(add_contract_plan, [p_driver_id, p_new_team_id, p_on])
$$;
