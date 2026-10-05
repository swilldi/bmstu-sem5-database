create or replace procedure pr_delete_genre(p_genre int, p_new_genre int, p_level int default 0)
language plpgsql
as $$
declare
    r record;
    v_name text;
    v_moved int;
begin
    if p_level > 50 then
        raise exception 'Слишком глубокая рекурсия: возможен цикл в иерархии жанров';
    end if;

    if p_level = 0 then
        if p_genre is null or p_new_genre is null then
            raise exception 'Идентификаторы жанров не должны быть NULL';
        end if;

        if not exists (select 1 from genre g where g.id = p_genre) then
            raise exception 'Удаляемый жанр % не найден', p_genre;
        end if;

        if not exists (select 1 from genre g where g.id = p_new_genre) then
            raise exception 'Жанр % (куда переносить игры) не найден', p_new_genre;
        end if;

        if exists (select 1 from fn_tree_genre(p_genre) t where t.genre_id = p_new_genre) then
            raise exception 'Жанр % входит в удаляемое поддерево', p_new_genre;
        end if;
    end if;

    select g.name into v_name from genre g where g.id = p_genre;

    for r in select g.id from genre g where g.parent_id = p_genre loop
        call pr_delete_genre(r.id, p_new_genre, p_level + 1);
    end loop;

    insert into game_genre (game_id, genre_id)
    select gg.game_id, p_new_genre
    from game_genre gg
    where gg.genre_id = p_genre
    on conflict do nothing;

    get diagnostics v_moved = row_count;

    delete from game_genre gg where gg.genre_id = p_genre;

    delete from genre g where g.id = p_genre;

    raise notice '%', repeat('    ', p_level) || 'Удалён жанр "' || v_name || '", перенесено игр: ' || v_moved;
end;
$$;
