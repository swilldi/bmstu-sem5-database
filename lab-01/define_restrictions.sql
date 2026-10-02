-- PRIMARY KEY
ALTER TABLE company
    ADD CONSTRAINT pk_company PRIMARY KEY (id);

ALTER TABLE game
    ADD CONSTRAINT pk_game PRIMARY KEY (id);

ALTER TABLE platform
    ADD CONSTRAINT pk_platform PRIMARY KEY (id);

ALTER TABLE game_engine
    ADD CONSTRAINT pk_game_engine PRIMARY KEY (id);

ALTER TABLE genre
    ADD CONSTRAINT pk_genre PRIMARY KEY (id);

ALTER TABLE game_genre
    ADD CONSTRAINT pk_game_genre PRIMARY KEY (game_id, genre_id);


-- UNIQUE
ALTER TABLE company
    ADD CONSTRAINT uq_company_name UNIQUE (name);

ALTER TABLE game_release
    ADD CONSTRAINT uq_game_release UNIQUE (game_id, company_id, platform_id, region, role);


-- FOREIGN KEY
ALTER TABLE game_genre
    ADD CONSTRAINT fk_game FOREIGN KEY (game_id) REFERENCES game(id),
    ADD CONSTRAINT fk_genre FOREIGN KEY (genre_id) REFERENCES genre(id);

ALTER TABLE game_release
    ADD CONSTRAINT fk_release_game FOREIGN KEY (game_id) REFERENCES game(id),
    ADD CONSTRAINT fk_release_platform FOREIGN KEY (platform_id) REFERENCES platform(id),
    ADD CONSTRAINT fk_release_company FOREIGN KEY (company_id) REFERENCES company(id);

ALTER TABLE game
    ADD CONSTRAINT fk_game_engine FOREIGN KEY (game_engine_id) REFERENCES game_engine(id);

ALTER TABLE game_engine
    ADD CONSTRAINT fk_engine_company FOREIGN KEY (company_id) REFERENCES company(id);

ALTER TABLE genre
    ADD CONSTRAINT fk_genre_parent FOREIGN KEY (parent_id) REFERENCES genre(id);

ALTER TABLE platform
    ADD CONSTRAINT fk_platform_company FOREIGN KEY (company_id) REFERENCES company(id);


-- NOT NULL
ALTER TABLE company 
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN country SET NOT NULL,
    ALTER COLUMN founded_year SET NOT NULL;

ALTER TABLE platform
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN short_name SET NOT NULL,
    ALTER COLUMN type SET NOT NULL,
    ALTER COLUMN release_date SET NOT NULL;

ALTER TABLE game
    ALTER COLUMN title SET NOT NULL;

ALTER TABLE game_engine
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN version SET NOT NULL,
    ALTER COLUMN company_id SET NOT NULL,
    ALTER COLUMN release_date SET NOT NULL,
    ALTER COLUMN is_active SET NOT NULL;

ALTER TABLE game_release
    ALTER COLUMN game_id SET NOT NULL,
    ALTER COLUMN platform_id SET NOT NULL,
    ALTER COLUMN company_id SET NOT NULL,
    ALTER COLUMN release_date SET NOT NULL,
    ALTER COLUMN region SET NOT NULL,
    ALTER COLUMN role SET NOT NULL;

ALTER TABLE genre
    ALTER COLUMN name SET NOT NULL;


-- CHECK
ALTER TABLE game
    ADD CONSTRAINT chk_users_score CHECK (users_score BETWEEN 0 AND 100),
    ADD CONSTRAINT chk_first_release_date CHECK (first_release_date >= DATE '1958-10-01'),
    ADD CONSTRAINT chk_age_rating CHECK (age_rating in (0, 3, 7, 12, 16, 18));

ALTER TABLE platform
    ADD CONSTRAINT chk_platform_type CHECK (type IN ('console', 'handheld', 'computer',
                                                     'mobile', 'vr', 'cloud', 'arcade'));

ALTER TABLE game_release
    ADD CONSTRAINT chk_release_region CHECK (region IN ('NA', 'EU', 'JP', 'WW')),
    ADD CONSTRAINT chk_release_role CHECK (role IN ('developer', 'publisher', 'porting_studio'));
