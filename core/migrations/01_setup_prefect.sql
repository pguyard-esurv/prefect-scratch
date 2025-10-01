-- Setup Prefect Database and User
-- This script creates the necessary database and user for Prefect server

-- Create prefect user
CREATE USER prefect_user WITH PASSWORD 'prefect_dev_password';

-- Create prefect database
CREATE DATABASE prefect_db OWNER prefect_user;

-- Grant all privileges on prefect_db to prefect_user
GRANT ALL PRIVILEGES ON DATABASE prefect_db TO prefect_user;

-- Connect to prefect_db and grant schema privileges
\c prefect_db;
GRANT ALL ON SCHEMA public TO prefect_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO prefect_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO prefect_user;

-- Switch back to main database
\c rpa_db;