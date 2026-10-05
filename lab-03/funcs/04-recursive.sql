create or replace function fn_tree_genre(p_genre_id int)
returns table(genre_id int, name text, level int, path text)
language sql
stable
as $$
    with recursive sub as(
        select id, name, 1 as level, name as path
        from genre
        where id = p_genre_id

        union all

        select g.id, g.name, s.level + 1, s.path || ' -> ' || g.name
        from genre g
        join sub s on g.parent_id = s.id
    )
    select id, name, level, path
    from sub;
$$;
