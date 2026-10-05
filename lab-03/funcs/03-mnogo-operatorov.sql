/*create or replace function fn_raspredelenie_genre()
returns table(name text, game_count int, percent )
language plpgsql
stable
as $$
declare
	select avg(count(version))
	from game_engine
	group by name
begin
	 
	
end
$$;*/

insert ("") into game_engine 
select name, count(name)
	from game_engine
	--group by name, version
	