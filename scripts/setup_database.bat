@echo off
REM Set up PostgreSQL extensions for Theseus Insight in Docker or local environment

setlocal enabledelayedexpansion

set DB_USER=%POSTGRES_USER%
set DB_PASS=%POSTGRES_PASSWORD%
set DB_NAME=%POSTGRES_DB%

REM Set defaults if not provided
if "%DB_USER%"=="" set DB_USER=theseus
if "%DB_PASS%"=="" set DB_PASS=theseus
if "%DB_NAME%"=="" set DB_NAME=theseusdb

echo Setting up pgvector extension for user: %DB_USER%, database: %DB_NAME%

REM Detect environment and set schema file path
if exist "C:\docker-entrypoint-initdb.d\init_schema_postgres.sql" (
    REM Running in Docker container
    set SCHEMA_FILE=C:\docker-entrypoint-initdb.d\init_schema_postgres.sql
    set ENVIRONMENT=docker
    echo 🐳 Detected Docker environment
) else if exist "%~dp0init_schema_postgres.sql" (
    REM Running locally with schema file in same directory as script
    set SCHEMA_FILE=%~dp0init_schema_postgres.sql
    set ENVIRONMENT=local
    echo 💻 Detected local environment
) else (
    echo ❌ Error: Cannot find init_schema_postgres.sql
    echo    Expected locations:
    echo    - Docker: C:\docker-entrypoint-initdb.d\init_schema_postgres.sql
    echo    - Local:  %~dp0init_schema_postgres.sql
    exit /b 1
)

REM For local installations, check if database and user exist, create if needed
if "%ENVIRONMENT%"=="local" (
    echo 🔧 Checking local PostgreSQL setup...
    
    REM Try to detect available superuser
    set SUPERUSER=
    set CURRENT_USER=%USERNAME%
    
    REM Test different potential superusers
    for %%u in ("%CURRENT_USER%" "postgres" "%USERNAME%") do (
        if "!SUPERUSER!"=="" (
            psql -U "%%~u" -d postgres -c "SELECT 1;" >nul 2>&1
            if !errorlevel! equ 0 (
                set SUPERUSER=%%~u
                echo ✅ Found PostgreSQL superuser: !SUPERUSER!
            )
        )
    )
    
    if "!SUPERUSER!"=="" (
        echo ❌ Error: Cannot find a working PostgreSQL superuser
        echo    Tried users: %CURRENT_USER%, postgres, %USERNAME%
        echo    Please ensure PostgreSQL is running and you have superuser access
        echo.
        echo 💡 Common solutions:
        echo    - Windows: Make sure PostgreSQL service is running
        echo    - Check if you can connect with: psql -U postgres -d postgres
        echo    - Verify PostgreSQL is in your PATH
        exit /b 1
    )
    
    REM Check if target user already exists
    echo 👤 Checking if user '%DB_USER%' exists...
    for /f %%i in ('psql -U "!SUPERUSER!" -d postgres -tAc "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '%DB_USER%';" 2^>nul') do set USER_EXISTS=%%i
    
    if "!USER_EXISTS!"=="1" (
        echo ✅ User '%DB_USER%' already exists
    ) else (
        echo ➕ Creating user '%DB_USER%'...
        psql -U "!SUPERUSER!" -d postgres -c "CREATE USER %DB_USER% WITH PASSWORD '%DB_PASS%'; ALTER USER %DB_USER% CREATEDB;"
        if !errorlevel! neq 0 (
            echo ❌ Error: Failed to create user '%DB_USER%'
            exit /b 1
        )
        echo ✅ User '%DB_USER%' created successfully
    )
    
    REM Check if database already exists
    echo 🗄️  Checking if database '%DB_NAME%' exists...
    for /f %%i in ('psql -U "!SUPERUSER!" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '%DB_NAME%';" 2^>nul') do set DB_EXISTS=%%i
    
    if "!DB_EXISTS!"=="1" (
        echo ✅ Database '%DB_NAME%' already exists
    ) else (
        echo ➕ Creating database '%DB_NAME%'...
        psql -U "!SUPERUSER!" -d postgres -c "CREATE DATABASE %DB_NAME% OWNER %DB_USER%;"
        if !errorlevel! neq 0 (
            echo ❌ Error: Failed to create database '%DB_NAME%'
            exit /b 1
        )
        echo ✅ Database '%DB_NAME%' created successfully
    )
    
    REM Grant necessary privileges
    echo 🔐 Ensuring user '%DB_USER%' has proper privileges...
    psql -U "!SUPERUSER!" -d "%DB_NAME%" -c "GRANT ALL PRIVILEGES ON DATABASE %DB_NAME% TO %DB_USER%; GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO %DB_USER%; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO %DB_USER%; GRANT CREATE ON SCHEMA public TO %DB_USER%; ALTER SCHEMA public OWNER TO %DB_USER%;" >nul 2>&1
    
    REM Test connection as target user
    echo 🔍 Testing connection as user '%DB_USER%'...
    psql -U "%DB_USER%" -d "%DB_NAME%" -c "SELECT 1;" >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Successfully connected as user '%DB_USER%'
    ) else (
        echo ⚠️  Warning: Could not connect as user '%DB_USER%', but continuing...
        echo    You may need to update pg_hba.conf or check password authentication
    )
)

REM Enable pgvector extension on the database
echo 🔌 Enabling pgvector extension...
psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -c "CREATE EXTENSION IF NOT EXISTS vector;"
if %errorlevel% neq 0 (
    echo ❌ Error: Failed to create pgvector extension
    echo    Make sure pgvector is installed on your PostgreSQL instance
    echo    See: https://github.com/pgvector/pgvector#installation
    exit /b 1
)

echo ✅ pgvector extension enabled for database "%DB_NAME%".

REM Apply initial schema
echo 📋 Applying initial schema from: %SCHEMA_FILE%
psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%SCHEMA_FILE%"
if %errorlevel% neq 0 (
    echo ❌ Error: Failed to apply schema from %SCHEMA_FILE%
    exit /b 1
)

echo.
echo 🎉 Database setup completed successfully!
echo.
echo 📋 Connection details:
echo    Database: %DB_NAME%
echo    User: %DB_USER%
echo    Environment: %ENVIRONMENT%
echo.
if "%ENVIRONMENT%"=="local" (
    echo 🔗 Connection string example:
    echo    postgresql://%DB_USER%:%DB_PASS%@localhost:5432/%DB_NAME%
    echo.
    echo 💻 Test connection:
    echo    psql -U %DB_USER% -d %DB_NAME% -h localhost
) 