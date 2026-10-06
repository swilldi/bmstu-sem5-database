-- средняя оценка игр в переданном жанре
create or replace function avg_score_by_genre(p_genre_id INT)
returns numeric
language sql
stable
as $$
	select round(avg(g.users_score), 2)
	from game_genre gg join game g on gg.game_id = g.id
	where gg.genre_id = p_genre_id; 
$$;

-- тест
select avg_score_by_genre(167);
select avg_score_by_genre(999999);  -- нет такого жанра: NULL
