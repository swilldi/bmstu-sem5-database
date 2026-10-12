CREATE TABLE IF NOT EXISTS driver (
    driver_id serial,
    full_name text,
    birth_date date,
    birth_city text,
    country text,
    license_class text,
    debut_year smallint
);

CREATE TABLE IF NOT EXISTS car (
    car_id serial,
    model text,
    season_year smallint,
    car_class text,
    horsepower int,
    weight_kg numeric(6, 2),
    team_id int
);

CREATE TABLE IF NOT EXISTS team (
    team_id serial,
    name text,
    country text,
    founded_year smallint,
    is_active boolean,
    team_parent_id int
);

CREATE TABLE IF NOT EXISTS track (
    track_id serial,
    name text,
    country text,
    length_km numeric(6, 2), 
    track_type text,
    opened_year smallint
);

CREATE TABLE IF NOT EXISTS race_entry(

    driver_id int,
    car_id int,
    track_id int, 
    status text,
    grid_position smallint,
    finish_position smallint,
    best_lap interval,
    total_time interval,
    race_date date,
    laps_completed smallint
);

CREATE TABLE IF NOT EXISTS contract (
    driver_id int,
    team_id int,
    start_date date,
    end_date date
);
