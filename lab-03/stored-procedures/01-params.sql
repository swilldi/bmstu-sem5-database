create or replace procedure pr_transfer_games(p_from_studio int, p_to_studio int)
language plpgsql
AS $$
declare
    tr_count int;
begin
    if p_from_studio = p_to_studio then
        raise exception 'Невозможен перенос в себя';
    end if;

    update game_release gr
        set company_id = p_to_studio
    where company_id = p_from_studio;

    get diagnostics tr_count = ROW_COUNT;
    raise notice 'Перенесено % игр', tr_count;
end;
$$;
