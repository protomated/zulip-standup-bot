-- PostgreSQL initialization script for Zulip Standup Bot
-- This script is run automatically when the database container starts

-- Create the main database user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'standup_user') THEN
        CREATE USER standup_user;
    END IF;
END
$$;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE standup TO standup_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO standup_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO standup_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO standup_user;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create a simple health check function
CREATE OR REPLACE FUNCTION health_check()
RETURNS TEXT AS $$
BEGIN
    RETURN 'OK';
END;
$$ LANGUAGE plpgsql;

-- Add a comment to identify this database
COMMENT ON DATABASE standup IS 'Zulip Standup Bot Database';
