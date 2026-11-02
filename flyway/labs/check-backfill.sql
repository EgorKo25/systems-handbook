-- Gate after v1 drain and v2 dual writes; before v3/title-only writers.
SELECT count(*) FILTER (WHERE title IS NULL) AS missing_title,
       count(*) FILTER (WHERE title IS DISTINCT FROM body) AS changed_value
FROM app.notes;
DO $gate$
BEGIN
    IF EXISTS (SELECT 1 FROM app.notes WHERE title IS NULL OR title IS DISTINCT FROM body) THEN
        RAISE EXCEPTION 'Backfill gate refused: NULL or unequal body/title; inspect writers and rows';
    END IF;
END
$gate$;
