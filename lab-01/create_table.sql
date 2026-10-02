CREATE TABLE IF NOT EXISTS company (
    id serial,
    name text,
    country text,
    city text,
    founded_year int
);

CREATE TABLE IF NOT EXISTS game (
    id serial,
    title text,
    users_score int,
    age_rating int,
    first_release_date date,
    game_engine_id int

);

CREATE TABLE IF NOT EXISTS platform (
    id serial,
    name text,
    short_name text,
    type text,
    generation int,
    release_date date,
    company_id int
);

CREATE TABLE IF NOT EXISTS genre (
    id serial,
    name text,
    parent_id int
);

CREATE TABLE IF NOT EXISTS game_engine (
    id serial,
    name text,
    version text,
    company_id int,
    release_date date,
    is_active boolean
);

CREATE TABLE IF NOT EXISTS game_genre (
    game_id int,
    genre_id int
);

CREATE TABLE IF NOT EXISTS game_release (
    game_id int,
    platform_id int,
    company_id int,
    release_date date,
    region text,
    role text
);


