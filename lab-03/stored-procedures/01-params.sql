-- переносит все релизы одной студии на другую (например, при поглощении студии)
create or replace procedure pr_transfer_games(p_from_studio int, p_to_studio int)
language plpgsql
AS $$
declare
    tr_count int;
    dup_count int;
begin
    if p_from_studio is null or p_to_studio is null then
        raise exception 'Идентификаторы студий не должны быть NULL';
    end if;

    if p_from_studio = p_to_studio then
        raise exception 'Невозможен перенос в себя';
    end if;

    if not exists (select 1 from company c where c.id = p_from_studio) then
        raise exception 'Студия % не найдена', p_from_studio;
    end if;

    if not exists (select 1 from company c where c.id = p_to_studio) then
        raise exception 'Студия % не найдена', p_to_studio;
    end if;

    -- если у новой студии уже есть точно такой же релиз,
    -- после переноса получился бы дубль (uq_game_release), поэтому старую запись удаляем
    delete from game_release gr
    using game_release t
    where gr.company_id = p_from_studio
      and t.company_id = p_to_studio
      and t.game_id = gr.game_id
      and t.platform_id = gr.platform_id
      and t.region = gr.region
      and t.role = gr.role;

    get diagnostics dup_count = ROW_COUNT;

    update game_release gr
        set company_id = p_to_studio
    where company_id = p_from_studio;

    get diagnostics tr_count = ROW_COUNT;
    raise notice 'Перенесено релизов: %, удалено дублей: %', tr_count, dup_count;
end;
$$;


-- тест (в транзакции, чтобы не испортить данные)
begin;

select company_id, count(*) from game_release where company_id in (9, 12) group by company_id;
call pr_transfer_games(9, 12);
select company_id, count(*) from game_release where company_id in (9, 12) group by company_id;

-- у Psikyo и City Connection есть одинаковые релизы — раньше здесь была ошибка uq_game_release
call pr_transfer_games(294, 1415);

rollback;

call pr_transfer_games(9, 9);        -- ошибка: перенос в себя
call pr_transfer_games(null, 9);     -- ошибка: NULL
call pr_transfer_games(9, 999999);   -- ошибка: студия не найдена
