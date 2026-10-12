-- представление "игра — жанр" с названиями вместо id
create or replace view v_game_genre as
select g.id as game_id, g.title, ge.name as genre_name
from game_genre gg
join game g on g.id = gg.game_id
join genre ge on ge.id = gg.genre_id;

-- вставка в представление: жанр ищется по названию (если его нет — создаётся),
-- затем добавляется связь в game_genre; удаление — убирает связь
create or replace function tr_fn_v_game_genre()
returns trigger
language plpgsql
as $$
declare
    v_genre_id int;
begin
    if tg_op = 'INSERT' then
        if not exists (select 1 from game g where g.id = new.game_id) then
            raise exception 'Игра % не найдена', new.game_id;
        end if;

        select ge.id into v_genre_id from genre ge where ge.name = new.genre_name;

        if v_genre_id is null then
            insert into genre (name) values (new.genre_name)
            returning id into v_genre_id;
            raise notice 'Создан новый жанр "%" (id = %)', new.genre_name, v_genre_id;
        end if;

        insert into game_genre (game_id, genre_id)
        values (new.game_id, v_genre_id)
        on conflict do nothing;

        return new;

    elsif tg_op = 'DELETE' then
        delete from game_genre gg
        using genre ge
        where gg.genre_id = ge.id
          and gg.game_id = old.game_id
          and ge.name = old.genre_name;

        return old;
    end if;
end;
$$;

create or replace trigger tr_v_game_genre
instead of insert or delete on v_game_genre
for each row
execute function tr_fn_v_game_genre();


-- тест (в транзакции, чтобы не испортить данные)
begin;

select * from v_game_genre where game_id = 11;

-- существующий жанр
insert into v_game_genre (game_id, genre_name) values (11, 'adventure video game');
-- несуществующий жанр — будет создан
insert into v_game_genre (game_id, genre_name) values (11, 'тестовый жанр');

select * from v_game_genre where game_id = 11;

delete from v_game_genre where game_id = 11 and genre_name = 'first-person shooter';

select * from v_game_genre where game_id = 11;

rollback;
