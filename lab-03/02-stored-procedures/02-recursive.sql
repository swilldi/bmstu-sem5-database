-- Закрыть команду и все дочерние, закрыть их контракты
create or replace procedure pr_close_team(p_team_id int, p_level int default 0)
language plpgsql
as $$
declare 
    r record;
begin
    if p_level = 0 and not exists (select 1 from team where team_id = p_team_id) then
        raise exception 'Команды с id = % не существует', p_team_id;
    end if;

    update team
    set is_active = false
    where team_id = p_team_id;

    update contract
    set end_date = current_date
    where end_date is null and team_id = p_team_id;

    raise notice '%Команда % закрыта', repeat('  ', p_level), p_team_id;
    for r in select team_id from team where team_parent_id = p_team_id
    loop
        call pr_close_team(r.team_id, p_level + 1);
    end loop;

end;
$$;

begin;
call pr_close_team(3);
select count(*) from contract where end_date is null;  -- должно стать 188 - 4 = 184, а не 0
rollback;
