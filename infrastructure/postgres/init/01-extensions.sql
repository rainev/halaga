-- Extensions the app relies on.
-- Runs automatically the first time the database is created (empty data volume).

-- pgvector: available for future semantic search over filings. Harmless if unused.
CREATE EXTENSION IF NOT EXISTS vector;
