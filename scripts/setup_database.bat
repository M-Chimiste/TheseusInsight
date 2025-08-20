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
if exist "C:\app\sql\001_init_schema_postgres.sql" (
    REM Running in Docker container
    set SCHEMA_FILE=C:\app\sql\001_init_schema_postgres.sql
    set ENVIRONMENT=docker
    echo 🐳 Detected Docker environment
) else if exist "%~dp0001_init_schema_postgres.sql" (
    REM Running locally with schema file in same directory as script
    set SCHEMA_FILE=%~dp0001_init_schema_postgres.sql
    set ENVIRONMENT=local
    echo 💻 Detected local environment
) else (
    echo ❌ Error: Cannot find 001_init_schema_postgres.sql
    echo    Expected locations:
    echo    - Docker: C:\app\sql\001_init_schema_postgres.sql
    echo    - Local:  %~dp0001_init_schema_postgres.sql
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

REM Create migration tracking table
if exist "%CREATE_MIGRATION_TRACKING_FILE%" (
    echo 📊 Creating migration tracking table...
    psql -U "%DB_USER%" -d "%DB_NAME%" -f "%CREATE_MIGRATION_TRACKING_FILE%" >nul 2>&1
)

REM Apply migration compatibility functions
if exist "%MIGRATION_COMPAT_FILE%" (
    echo 🔧 Setting up migration compatibility functions...
    psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%MIGRATION_COMPAT_FILE%"
    if %errorlevel% neq 0 (
        echo ❌ Error: Failed to apply migration compatibility from %MIGRATION_COMPAT_FILE%
        exit /b 1
    )
    echo ✅ Migration compatibility functions created
)

REM Apply initial schema
echo 📋 Applying initial schema from: %SCHEMA_FILE%
psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%SCHEMA_FILE%"
if %errorlevel% neq 0 (
    echo ❌ Error: Failed to apply schema from %SCHEMA_FILE%
    exit /b 1
)

REM Apply profile migrations
echo 🔄 Applying database migrations...

REM Determine migration file paths based on environment
if "%ENVIRONMENT%"=="docker" (
    set MIGRATION_COMPAT_FILE=C:\app\sql\000_migration_compatibility.sql
    set MIGRATE_TO_PROFILES_FILE=C:\app\sql\002_migrate_to_profiles.sql
    set PROFILES_TRENDS_FILE=C:\app\sql\003_profiles_trends_integration.sql
    set STAGING_TABLES_FILE=C:\app\sql\004_add_staging_tables.sql
    set OPTIMIZE_INDEXES_FILE=C:\app\sql\005_optimize_indexes.sql
    set PROCESSING_CHECKPOINTS_FILE=C:\app\sql\006_add_processing_checkpoints.sql
    set SCHEDULED_TASKS_FILE=C:\app\sql\007_add_scheduled_tasks.sql
    set CREATE_MIGRATION_TRACKING_FILE=C:\app\sql\create_migration_tracking.sql
) else (
    set MIGRATION_COMPAT_FILE=%~dp0000_migration_compatibility.sql
    set MIGRATE_TO_PROFILES_FILE=%~dp0002_migrate_to_profiles.sql
    set PROFILES_TRENDS_FILE=%~dp0003_profiles_trends_integration.sql
    set STAGING_TABLES_FILE=%~dp0004_add_staging_tables.sql
    set OPTIMIZE_INDEXES_FILE=%~dp0005_optimize_indexes.sql
    set PROCESSING_CHECKPOINTS_FILE=%~dp0006_add_processing_checkpoints.sql
    set SCHEDULED_TASKS_FILE=%~dp0007_add_scheduled_tasks.sql
    set CREATE_MIGRATION_TRACKING_FILE=%~dp0create_migration_tracking.sql
)

REM Apply profile migration
if exist "%MIGRATE_TO_PROFILES_FILE%" (
    echo 📋 Applying profile migration from: %MIGRATE_TO_PROFILES_FILE%
    psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%MIGRATE_TO_PROFILES_FILE%"
    if %errorlevel% neq 0 (
        echo ❌ Error: Failed to apply profile migration from %MIGRATE_TO_PROFILES_FILE%
        exit /b 1
    )
    echo ✅ Profile migration completed successfully
) else (
    echo ⚠️  Warning: Profile migration file not found at %MIGRATE_TO_PROFILES_FILE%
    echo    The system will work but profile features may not be available
)

REM Apply profiles-trends integration
if exist "%PROFILES_TRENDS_FILE%" (
    echo 📋 Applying profiles-trends integration from: %PROFILES_TRENDS_FILE%
    psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%PROFILES_TRENDS_FILE%"
    if %errorlevel% neq 0 (
        echo ❌ Error: Failed to apply profiles-trends integration from %PROFILES_TRENDS_FILE%
        exit /b 1
    )
    echo ✅ Profiles-trends integration completed successfully
) else (
    echo ⚠️  Warning: Profiles-trends integration file not found at %PROFILES_TRENDS_FILE%
    echo    Trends features may not work properly with profiles
)

REM Apply staging tables migration
if exist "%STAGING_TABLES_FILE%" (
    echo 📋 Applying staging tables migration from: %STAGING_TABLES_FILE%
    psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%STAGING_TABLES_FILE%"
    if %errorlevel% neq 0 (
        echo ❌ Error: Failed to apply staging tables migration from %STAGING_TABLES_FILE%
        exit /b 1
    )
    echo ✅ Staging tables migration completed successfully
) else (
    echo ⚠️  Warning: Staging tables migration file not found at %STAGING_TABLES_FILE%
    echo    Bulk import features may not be available
)

REM Apply index optimization
if exist "%OPTIMIZE_INDEXES_FILE%" (
    echo 📋 Applying index optimization from: %OPTIMIZE_INDEXES_FILE%
    psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%OPTIMIZE_INDEXES_FILE%"
    if %errorlevel% neq 0 (
        echo ❌ Error: Failed to apply index optimization from %OPTIMIZE_INDEXES_FILE%
        exit /b 1
    )
    echo ✅ Index optimization completed successfully
) else (
    echo ⚠️  Warning: Index optimization file not found at %OPTIMIZE_INDEXES_FILE%
    echo    Database performance may not be optimal
)

REM Apply processing checkpoints migration
if exist "%PROCESSING_CHECKPOINTS_FILE%" (
    echo 📋 Applying processing checkpoints migration from: %PROCESSING_CHECKPOINTS_FILE%
    psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%PROCESSING_CHECKPOINTS_FILE%"
    if %errorlevel% neq 0 (
        echo ❌ Error: Failed to apply processing checkpoints migration from %PROCESSING_CHECKPOINTS_FILE%
        exit /b 1
    )
    echo ✅ Processing checkpoints migration completed successfully
) else (
    echo ⚠️  Warning: Processing checkpoints migration file not found at %PROCESSING_CHECKPOINTS_FILE%
    echo    Processing tracking features may not be available
)

REM Apply scheduled tasks migration
if exist "%SCHEDULED_TASKS_FILE%" (
    echo 📋 Applying scheduled tasks migration from: %SCHEDULED_TASKS_FILE%
    psql -v ON_ERROR_STOP=1 -U "%DB_USER%" -d "%DB_NAME%" -f "%SCHEDULED_TASKS_FILE%"
    if %errorlevel% neq 0 (
        echo ❌ Error: Failed to apply scheduled tasks migration from %SCHEDULED_TASKS_FILE%
        exit /b 1
    )
    echo ✅ Scheduled tasks migration completed successfully
) else (
    echo ⚠️  Warning: Scheduled tasks migration file not found at %SCHEDULED_TASKS_FILE%
    echo    Scheduled task features may not be available
)

echo.
echo 🎉 Database setup with profile features completed successfully!
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