-- PRIMARY KEY
ALTER TABLE driver ADD CONSTRAINT pk_driver PRIMARY KEY (driver_id);
ALTER TABLE car ADD CONSTRAINT pk_car PRIMARY KEY (car_id);
ALTER TABLE team ADD CONSTRAINT pk_team PRIMARY KEY (team_id);
ALTER TABLE track ADD CONSTRAINT pk_track PRIMARY KEY (track_id);
ALTER TABLE race_entry ADD CONSTRAINT pk_race_entry PRIMARY KEY (driver_id, race_date);
ALTER TABLE contract ADD CONSTRAINT pk_contract PRIMARY KEY (driver_id, start_date);


-- UNIQUE
ALTER TABLE race_entry 
    ADD CONSTRAINT uq_race_entry_car UNIQUE (track_id, race_date, car_id),
    ADD CONSTRAINT uq_race_entry_finish_position UNIQUE (track_id, race_date, finish_position),
    ADD CONSTRAINT uq_race_entry_grid_position UNIQUE (track_id, race_date, grid_position);
ALTER TABLE car 
    ADD CONSTRAINT uq_car UNIQUE (model, season_year, team_id);
ALTER TABLE team  
    ADD CONSTRAINT uq_team UNIQUE (name);
ALTER TABLE track
    ADD CONSTRAINT uq_track UNIQUE (name, country);

-- NOT NULL
ALTER TABLE driver
    ALTER COLUMN full_name set not NULL,
    ALTER COLUMN birth_date set not NULL,
    ALTER COLUMN birth_city set not NULL,
    ALTER COLUMN country set not NULL,
    ALTER COLUMN license_class set not NULL,
    ALTER COLUMN debut_year set not NULL;

ALTER TABLE car
    ALTER COLUMN model set not NULL,
    ALTER COLUMN season_year set not NULL,
    ALTER COLUMN car_class set not NULL,
    ALTER COLUMN horsepower set not NULL,
    ALTER COLUMN weight_kg set not NULL,
    ALTER COLUMN team_id set not NULL;

ALTER TABLE team
    ALTER COLUMN name set not NULL,
    ALTER COLUMN country set not NULL,
    ALTER COLUMN founded_year set not NULL,
    ALTER COLUMN is_active set not NULL,
    ALTER COLUMN is_active set default true;

ALTER TABLE track
    ALTER COLUMN name set not NULL,
    ALTER COLUMN country set not NULL,
    ALTER COLUMN length_km set not NULL,
    ALTER COLUMN track_type set not NULL,
    ALTER COLUMN opened_year set not NULL;

ALTER TABLE race_entry
    ALTER COLUMN car_id set not NULL,
    ALTER COLUMN track_id set not NULL,
    ALTER COLUMN status set not NULL,
    ALTER COLUMN grid_position set not NULL,
    ALTER COLUMN laps_completed set not null;

ALTER TABLE contract
    ALTER COLUMN team_id set not NULL;

-- CHECK
ALTER TABLE driver
    ADD CONSTRAINT chk_birth_date CHECK (birth_date between '1900-01-01' and current_date - interval '15 years'),
    ADD CONSTRAINT chk_debut_year CHECK (debut_year between extract(year from birth_date) + 15 and extract(year from now())),
    ADD CONSTRAINT chk_license_class CHECK (license_class in ('super', 'A', 'B', 'C', 'D'));

ALTER TABLE car
    ADD CONSTRAINT chk_season_year CHECK (season_year between 1950 and extract(year from now()) + 1),
    ADD CONSTRAINT chk_car_class CHECK (car_class in ('formula', 'hypercar', 'gt', 'touring', 'stock')),
    ADD CONSTRAINT chk_horsepower CHECK (horsepower between 100 and 1500),
    ADD CONSTRAINT chk_weight_kg CHECK (weight_kg between 400 and 2000);

ALTER TABLE team
    ADD CONSTRAINT chk_founded_year CHECK (founded_year between 1894 and extract(year from now())),
    ADD CONSTRAINT chk_team_parent_id CHECK (team_parent_id != team_id);

ALTER TABLE track
    ADD CONSTRAINT chk_length_km CHECK (length_km between 0.4 and 26),
    ADD CONSTRAINT chk_track_type CHECK (track_type in ('permanent', 'street', 'oval')),
    ADD CONSTRAINT chk_opened_year CHECK (opened_year between 1900 and extract(year from now()));

ALTER TABLE race_entry
    ADD CONSTRAINT chk_race_date CHECK (race_date between '1950-01-01' and  current_date),
    ADD CONSTRAINT chk_grid_position CHECK (grid_position between 1 and 70),
    ADD CONSTRAINT chk_status CHECK (status in ('finished', 'dnf', 'dsq', 'dns')),
    ADD CONSTRAINT chk_finish_position_range CHECK (finish_position between 1 and 70),
    ADD CONSTRAINT chk_total_time_range CHECK (total_time between '1 minutes' and '30 hours'),
    ADD CONSTRAINT chk_laps_completed_range CHECK (laps_completed between 0 and 1000),
    ADD CONSTRAINT chk_best_lap_range CHECK (best_lap between '10 seconds' and '15 minutes'),

    ADD CONSTRAINT chk_finish_position CHECK ((status = 'finished') = (finish_position is not null)),
    ADD CONSTRAINT chk_total_time CHECK ((status = 'finished') = (total_time is not null)),
    ADD CONSTRAINT chk_laps_completed_finish CHECK (status != 'finished' or laps_completed >= 1),
    ADD CONSTRAINT chk_best_lap CHECK (status != 'finished' or best_lap is not null),
    ADD CONSTRAINT chk_laps_completed_dns CHECK (status != 'dns' or laps_completed = 0),
    ADD CONSTRAINT chk_best_lap_zero_laps CHECK (laps_completed != 0 or best_lap is null),
    ADD CONSTRAINT chk_best_lap_dsq CHECK (status != 'dsq' or  best_lap is null),
    ADD CONSTRAINT chk_best_lap_cmp_total_time CHECK (total_time >= best_lap * laps_completed);

ALTER TABLE contract
    ADD CONSTRAINT chk_contract_start_date CHECK (start_date between '1950-01-01' and current_date),
    ADD CONSTRAINT chk_contract_end_date CHECK (end_date between start_date and current_date);
    

-- FOREIGN KEY
ALTER TABLE race_entry
    ADD CONSTRAINT fk_driver FOREIGN KEY (driver_id) references driver(driver_id),
    ADD CONSTRAINT fk_car FOREIGN KEY (car_id) references car(car_id),
    ADD CONSTRAINT fk_track FOREIGN KEY (track_id) references track(track_id);

ALTER TABLE team
    ADD CONSTRAINT fk_team_parent_id FOREIGN KEY (team_parent_id) references team(team_id);
ALTER TABLE car
    ADD CONSTRAINT fk_team_belong FOREIGN KEY (team_id) references team(team_id);

ALTER TABLE contract
    ADD CONSTRAINT fk_contract_driver FOREIGN KEY (driver_id) references driver(driver_id),
    ADD CONSTRAINT fk_contract_team FOREIGN KEY (team_id) references team(team_id);