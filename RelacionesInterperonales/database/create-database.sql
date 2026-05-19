-- Crea la base de datos solo si no existe y luego se conecta.

SELECT 'CREATE DATABASE interpersonalrelation'
WHERE NOT EXISTS (
	SELECT FROM pg_database WHERE datname = 'interpersonalrelation'
)\gexec

\connect interpersonalrelation

SET client_encoding = 'UTF8';