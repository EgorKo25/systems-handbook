INSERT INTO app.notes(body)
SELECT 'Записка ' || n FROM generate_series(1,1000) AS n;
