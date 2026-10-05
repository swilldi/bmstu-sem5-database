-- выводит компании которые основаны после переданного года
create or replace function fn_compant_opened_after(p_year int)
returns table(name text, founded_year int)
language sql
stable
as $$
	select name, founded_year
	from company
	where founded_year >= p_year
	order by founded_year
$$;

select * from fn_compant_opened_after(2000)
