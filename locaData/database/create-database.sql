-- Crea la base de datos solo si no existe y luego se conecta.

SELECT 'CREATE DATABASE locadata'
WHERE NOT EXISTS (
	SELECT FROM pg_database WHERE datname = 'locadata'
)\gexec

\connect locadata

SET client_encoding = 'UTF8';