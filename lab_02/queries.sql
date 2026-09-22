-- 1. Пары компаний из одного города
SELECT DISTINCT c1.city, c1.name, c2.name
FROM company AS c1 JOIN company AS c2 ON c1.city = c2.city
WHERE c1.id < c2.id
ORDER BY c1.city;

-- 2. Игры, впервые вышедшие с 2010 по 2014 год
SELECT title, first_release_date FROM game
WHERE first_release_date BETWEEN '2010-01-01' AND '2014-12-31';

-- 3. Инструкция SELECT, использующая предикат LIKE.
SELECT title, first_release_date FROM game
WHERE title ILIKE '%mario%';

-- 4. Релизы, изданные шведскими компаниями
SELECT gr.game_id, gr.company_id
FROM game_release gr
WHERE gr.role = 'publisher'
  AND gr.company_id IN ( SELECT id FROM company WHERE country = 'Sweden' );

-- 5. Движки, на которых не создано ни одной игры
SELECT ge.name, ge.version
FROM game_engine ge
WHERE NOT EXISTS ( SELECT 1 FROM game g WHERE g.game_engine_id = ge.id );

-- 6. Игры жанра role-playing video game (42), оценённые выше любой игры жанра beat 'em up (27)
SELECT g.id, g.title, g.users_score
FROM game g JOIN game_genre gg ON gg.game_id = g.id
WHERE gg.genre_id = 42
  AND g.users_score > ALL ( SELECT g2.users_score
                            FROM game g2 JOIN game_genre gg2 ON gg2.game_id = g2.id
                            WHERE gg2.genre_id = 27
                              AND g2.users_score IS NOT NULL )
ORDER BY g.users_score DESC;

-- 7. Среднее число релизов на одну игру, посчитанное двумя способами
SELECT AVG(releases) AS "Actual AVG",
       SUM(releases) / COUNT(game_id) AS "Calc AVG"
FROM ( SELECT game_id, COUNT(*) AS releases
       FROM game_release
       GROUP BY game_id ) AS tot_games;

-- 8. Для игр жанра role-playing video game — их оценка, средняя и минимальная оценка среди игр на том же движке
SELECT g.id, g.users_score,
       ( SELECT ROUND(AVG(g2.users_score), 1)
         FROM game g2
         WHERE g2.game_engine_id = g.game_engine_id ) AS avg_score,
       ( SELECT MIN(g2.users_score)
         FROM game g2
         WHERE g2.game_engine_id = g.game_engine_id ) AS min_score,
       g.title
FROM game g JOIN game_genre gg ON gg.game_id = g.id
WHERE gg.genre_id = 42
ORDER BY g.id;

-- 9. Отнести каждый релиз к текущему году, прошлому или к «N лет назад»
SELECT c.name AS company, gr.game_id, gr.release_date,
       CASE EXTRACT(YEAR FROM gr.release_date)
           WHEN EXTRACT(YEAR FROM CURRENT_DATE)     THEN 'This year'
           WHEN EXTRACT(YEAR FROM CURRENT_DATE) - 1 THEN 'Last year'
           ELSE (EXTRACT(YEAR FROM CURRENT_DATE)
                 - EXTRACT(YEAR FROM gr.release_date)) || ' years ago'
       END AS "When"
FROM game_release gr JOIN company c ON c.id = gr.company_id
ORDER BY gr.release_date DESC;

-- 10. Инструкция SELECT, использующая поисковое выражение CASE.
SELECT g.title, g.users_score,
       CASE
           WHEN g.users_score < 50 THEN 'мусор'
           WHEN g.users_score < 70 THEN 'проходняк'
           WHEN g.users_score < 85 THEN 'похвально'
           ELSE 'изюмительно'
       END AS score_label
FROM game g;

-- 11. Статистика по каждой игре: сколько релизов и на скольких платформах
CREATE TEMP TABLE game_stats AS
SELECT gr.game_id,
       COUNT(*)                        AS releases,
       COUNT(DISTINCT gr.platform_id)  AS platforms
FROM game_release gr
WHERE gr.game_id IS NOT NULL
GROUP BY gr.game_id;

SELECT * FROM game_stats ORDER BY releases DESC, game_id;

-- 12. Самая издаваемая игра по двум разным критериям
SELECT 'По числу релизов' AS criteria, g.title AS best_game
FROM game g JOIN ( SELECT game_id, COUNT(*) AS cnt
                   FROM game_release
                   GROUP BY game_id
                   ORDER BY cnt DESC LIMIT 1 ) od ON od.game_id = g.id
UNION
SELECT 'По числу платформ', g.title
FROM game g JOIN ( SELECT game_id, COUNT(DISTINCT platform_id) AS cnt
                   FROM game_release
                   GROUP BY game_id
                   ORDER BY cnt DESC LIMIT 1 ) od ON od.game_id = g.id;

-- 13. Игра с максимальным числом релизов
SELECT g.title, g.users_score
FROM game g
WHERE g.id IN ( SELECT gr.game_id
                FROM game_release gr
                GROUP BY gr.game_id
                HAVING COUNT(*) = ( SELECT MAX(cnt)
                                    FROM ( SELECT COUNT(*) AS cnt
                                           FROM game_release
                                           GROUP BY game_id ) AS t ) );

-- 14. По каждой платформе: число релизов, самый ранний и самый поздний из них
SELECT p.name, p.type,
       COUNT(gr.game_id)     AS releases,
       MIN(gr.release_date)  AS first_release,
       MAX(gr.release_date)  AS last_release
FROM platform p LEFT OUTER JOIN game_release gr ON gr.platform_id = p.id
GROUP BY p.id, p.name, p.type
ORDER BY releases DESC;

-- 15. Жанры, средняя оценка игр которых выше общей средней оценки
SELECT ge.id, ge.name,
       ROUND(AVG(g.users_score), 2) AS avg_score,
       COUNT(*)                     AS games
FROM game g JOIN game_genre gg ON gg.game_id = g.id
            JOIN genre ge      ON ge.id = gg.genre_id
GROUP BY ge.id, ge.name
HAVING AVG(g.users_score) > ( SELECT AVG(users_score) FROM game )
   AND COUNT(*) >= 20
ORDER BY avg_score DESC;

-- 16. Вставку в таблицу
INSERT INTO company (name, country, city, founded_year)
VALUES ('Test Studio Ltd.', 'Russia', DEFAULT, 2026);

-- 17. вставка в таблицу набора данных вложенного подзапроса.
INSERT INTO game_genre (game_id, genre_id)
SELECT DISTINCT gg.game_id, ge.parent_id
FROM game_genre gg JOIN genre ge ON ge.id = gg.genre_id
WHERE ge.parent_id IS NOT NULL
  AND NOT EXISTS ( SELECT 1
                   FROM game_genre x
                   WHERE x.game_id = gg.game_id
                     AND x.genre_id = ge.parent_id );

-- 18. Поднять оценку игре, но не выше 100 (ограничение chk_users_score)
UPDATE game
SET users_score = LEAST(users_score + 5, 100)
WHERE id = 161;

-- 19. Выставить игре среднюю оценку по жанру role-playing video game (42)
UPDATE game g
SET users_score = ( SELECT ROUND(AVG(g2.users_score))
                    FROM game g2 JOIN game_genre gg2 ON gg2.game_id = g2.id
                    WHERE gg2.genre_id = 42 )
WHERE g.id = 161;

-- 20. Простая инструкция DELETE.
DELETE FROM company
WHERE name = 'Test Studio Ltd.';

-- 21. Удалить движки, на которых не создано ни одной игры
DELETE FROM game_engine ge
WHERE NOT EXISTS ( SELECT 1 FROM game g WHERE g.game_engine_id = ge.id );

-- 22. Инструкция SELECT, использующая простое обобщённое табличное выражение.???
WITH releases_per_game (game_id, releases) AS (
    SELECT gr.game_id, COUNT(*)
    FROM game_release gr
    GROUP BY gr.game_id
)
SELECT ROUND(AVG(releases), 2) AS "Среднее число релизов на игру",
       MAX(releases)           AS "Максимум",
       COUNT(*)                AS "Игр с релизами"
FROM releases_per_game;

-- 23. Развернуть иерархию жанров (genre.parent_id) в дерево с уровнями и путём
WITH RECURSIVE genre_tree (id, name, parent_id, level, path) AS (
    SELECT g.id, g.name, g.parent_id, 0, g.name
    FROM genre g
    WHERE g.parent_id IS NULL
    UNION ALL
    SELECT g.id, g.name, g.parent_id, t.level + 1, t.path || ' / ' || g.name
    FROM genre g JOIN genre_tree t ON g.parent_id = t.id
)
SELECT level, id, name, path
FROM genre_tree
ORDER BY path;

-- 24. Для каждой игры жанра role-playing video game (42) — её оценка и средняя/минимальная/максимальная оценка внутри жанра
SELECT g.id, g.title, ge.name AS genre, g.users_score,
       ROUND(AVG(g.users_score) OVER (PARTITION BY ge.id), 1) AS avg_in_genre,
       MIN(g.users_score) OVER (PARTITION BY ge.id)           AS min_in_genre,
       MAX(g.users_score) OVER (PARTITION BY ge.id)           AS max_in_genre
FROM game g JOIN game_genre gg ON gg.game_id = g.id
            JOIN genre ge      ON ge.id = gg.genre_id
WHERE ge.id = 42
ORDER BY g.users_score DESC;

-- 25. Запрос с полными дублями: одна игра выходит в одном регионе на нескольких платформах, поэтому пара (title, region) повторяется
SELECT g.title, gr.region
FROM game g JOIN game_release gr ON gr.game_id = g.id
ORDER BY g.title, gr.region;

-- Устранение дублей через ROW_NUMBER()
WITH numbered AS (
    SELECT g.title, gr.region,
           ROW_NUMBER() OVER (PARTITION BY g.title, gr.region
                              ORDER BY g.title) AS rn
    FROM game g JOIN game_release gr ON gr.game_id = g.id
)
SELECT title, region
FROM numbered
WHERE rn = 1
ORDER BY title, region;
