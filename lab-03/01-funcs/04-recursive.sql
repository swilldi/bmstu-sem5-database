-- with recursive t as (
--     -- 1. якорь: выполняется один раз, задаёт начальные строки
--     select ..., 1 as level, name as path
--     from team
--     where team_id = p_team_id

--     union all

--     -- 2. рекурсивная часть: ссылается на t и находит следующий уровень
--     select ..., t.level + 1, t.path || ' → ' || c.name
--     from team c
--     join t on <условие связи родитель → ребёнок>
-- )
-- select * from t;

create or replace function fn_team_tree(p_team_id int)
returns table(team_id int, name text, level int, path text)
language plpgsql
stable
as $$
begin
    if not exists (select 1 from team t where t.team_id = p_team_id) then
        raise exception 'Нет команды с id = %', p_team_id;
    end if;

    return query
    with recursive t as (
        select tt.team_id, tt.name, 1 as level, tt.name as path
        from team tt
        where tt.team_id = p_team_id

        union all

        select c.team_id, c.name, t.level + 1, t.path || ' -> ' || c.name
        from team c
        join t on t.team_id = c.team_parent_id
    )
    select * from t;
end;
$$;

select * from fn_team_tree(6);
