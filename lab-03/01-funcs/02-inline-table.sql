-- выводит компании, основанные в переданном году или позже
create or replace function fn_company_opened_after(p_year int)
returns table(name text, founded_year int)
language sql
stable
as $$
	select name, founded_year
	from company
	where founded_year >= p_year
	order by founded_year
$$;

-- тест
select * from fn_company_opened_after(2015);
select count(*) from fn_company_opened_after(2100);  -- никого: 0
