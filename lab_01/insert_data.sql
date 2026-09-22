COPY company FROM '/workspace/data/company.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY platform FROM '/workspace/data/platform.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY genre FROM '/workspace/data/genre.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY game_engine FROM '/workspace/data/game_engine.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY game FROM '/workspace/data/game.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY game_genre FROM '/workspace/data/game_genre.csv' WITH (FORMAT csv, HEADER true, Null '');
COPY game_release FROM '/workspace/data/game_release.csv' WITH (FORMAT csv, HEADER true, NULL '');

SELECT setval('company_id_seq', (SELECT MAX(id) FROM company));
SELECT setval('game_engine_id_seq', (SELECT MAX(id) FROM game_engine));
SELECT setval('platform_id_seq', (SELECT MAX(id) FROM platform));
SELECT setval('genre_id_seq', (SELECT MAX(id) FROM genre));
SELECT setval('game_id_seq', (SELECT MAX(id) FROM game));


