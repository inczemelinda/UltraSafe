DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'uw'
    ) THEN
        CREATE ROLE uw LOGIN PASSWORD 'uw';
    ELSE
        ALTER ROLE uw WITH LOGIN PASSWORD 'uw';
    END IF;
END
$$;

SELECT 'CREATE DATABASE uw_test OWNER uw'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_database
    WHERE datname = 'uw_test'
)\gexec

GRANT ALL PRIVILEGES ON DATABASE uw_test TO uw;
