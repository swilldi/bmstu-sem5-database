COPY team FROM '/workspace/data/team.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY track FROM '/workspace/data/track.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY driver FROM '/workspace/data/driver.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY car FROM '/workspace/data/car.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY race_entry FROM '/workspace/data/race_entry.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY contract FROM '/workspace/data/contract.csv' WITH (FORMAT csv, HEADER true, NULL '');

SELECT setval('driver_driver_id_seq', (SELECT MAX(driver_id) FROM driver));
SELECT setval('car_car_id_seq', (SELECT MAX(car_id) FROM car));
SELECT setval('team_team_id_seq', (SELECT MAX(team_id) FROM team));
SELECT setval('track_track_id_seq', (SELECT MAX(track_id) FROM track));


