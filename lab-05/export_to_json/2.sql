\t on
\a

\o 'teams_array.json'
select jsonb_pretty(jsonb_agg(t order by t.team_id, founded_year))
from team t;

\o 'count_track_by_country.json'
select jsonb_pretty(
    jsonb_object_agg(country, cnt)
)
from (
    select country, count(*) as cnt 
    from track t
    group by country
    order by country
) c;
