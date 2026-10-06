-- при добавлении/изменении релиза игры обновляет game.first_release_date,
-- если новый релиз вышел раньше, чем записанная дата первого выхода
create or replace function tr_fn_update_first_release()
returns trigger
language plpgsql
as $$
begin
    update game g
        set first_release_date = new.release_date
    where g.id = new.game_id
      and (g.first_release_date is null or g.first_release_date > new.release_date);

    if found then
        raise notice 'Игра %: дата первого выхода изменена на %', new.game_id, new.release_date;
    end if;

    return null;
end;
$$;

create or replace trigger tr_update_first_release
after insert or update of release_date, game_id on game_release
for each row
execute function tr_fn_update_first_release();


-- тест (в транзакции, чтобы не испортить данные)
begin;

select id, title, first_release_date from game where id = 11;

insert into game_release (game_id, platform_id, company_id, release_date, region, role)
values (11, 1, 1, date '2000-01-01', 'WW', 'publisher');

select id, title, first_release_date from game where id = 11;

rollback;
