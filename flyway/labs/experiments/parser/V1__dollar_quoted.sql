CREATE TABLE app.parser_probe (message text NOT NULL);

DO $body$
DECLARE
    message text := 'semicolon; ${word}';
BEGIN
    INSERT INTO app.parser_probe VALUES (message);
END
$body$;

CREATE FUNCTION app.parser_echo(text) RETURNS text
LANGUAGE sql AS $function$
    SELECT $1 || ';${word}'
$function$;

COMMENT ON TABLE app.parser_probe IS 'literal; not a new statement';
