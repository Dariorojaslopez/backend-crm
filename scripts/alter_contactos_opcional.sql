-- Hace opcionales los campos de contactos (PostgreSQL).
-- Ejecutar una vez si la tabla ya existía con NOT NULL.

ALTER TABLE contactos ALTER COLUMN nombre DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN apellidos DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN municipio_id DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN provincia_id DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN cargo_id DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN partido_id DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN tipo_id DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN relacion_id DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN afinidad DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN influencia DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN prioridad DROP NOT NULL;
ALTER TABLE contactos ALTER COLUMN periodo DROP NOT NULL;
