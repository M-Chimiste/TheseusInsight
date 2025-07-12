# Set up PostgreSQL extensions for Theseus Insight in Docker or local environment

param(
    [string]$DbUser = $env:POSTGRES_USER,
    [string]$DbPass = $env:POSTGRES_PASSWORD,
    [string]$DbName = $env:POSTGRES_DB
)

# Set defaults if not provided
if (-not $DbUser) { $DbUser = "theseus" }
if (-not $DbPass) { $DbPass = "theseus" }
if (-not $DbName) { $DbName = "theseusdb" }

# Colors for output
$InfoColor = "Cyan"
$SuccessColor = "Green"
$WarningColor = "Yellow"
$ErrorColor = "Red"

function Write-Status {
    param([string]$Message)
    Write-Host $Message -ForegroundColor $InfoColor
}

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor $SuccessColor
}

function Write-Warning {
    param([string]$Message)
    Write-Host $Message -ForegroundColor $WarningColor
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host $Message -ForegroundColor $ErrorColor
}

Write-Host "Setting up pgvector extension for user: $DbUser, database: $DbName"

# Detect environment and set schema file path
$SchemaFile = $null
$Environment = $null

if (Test-Path "C:\app\sql\001_init_schema_postgres.sql") {
    # Running in Docker container
    $SchemaFile = "C:\app\sql\001_init_schema_postgres.sql"
    $Environment = "docker"
    Write-Host "🐳 Detected Docker environment" -ForegroundColor $InfoColor
}
elseif (Test-Path "$PSScriptRoot\001_init_schema_postgres.sql") {
    # Running locally with schema file in same directory as script
    $SchemaFile = "$PSScriptRoot\001_init_schema_postgres.sql"
    $Environment = "local"
    Write-Host "💻 Detected local environment" -ForegroundColor $InfoColor
}
else {
    Write-ErrorMsg "❌ Error: Cannot find 001_init_schema_postgres.sql"
    Write-Host "   Expected locations:"
    Write-Host "   - Docker: C:\app\sql\001_init_schema_postgres.sql"
    Write-Host "   - Local:  $PSScriptRoot\001_init_schema_postgres.sql"
    exit 1
}

# For local installations, check if database and user exist, create if needed
if ($Environment -eq "local") {
    Write-Status "🔧 Checking local PostgreSQL setup..."
    
    # Try to detect available superuser
    $SuperUser = $null
    $CurrentUser = $env:USERNAME
    
    # Test different potential superusers
    $testUsers = @($CurrentUser, "postgres", $env:USER)
    foreach ($testUser in $testUsers) {
        if ($testUser -and -not $SuperUser) {
            try {
                $result = & psql -U $testUser -d postgres -c "SELECT 1;" 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $SuperUser = $testUser
                    Write-Success "✅ Found PostgreSQL superuser: $SuperUser"
                    break
                }
            }
            catch {
                # Continue to next user
            }
        }
    }
    
    if (-not $SuperUser) {
        Write-ErrorMsg "❌ Error: Cannot find a working PostgreSQL superuser"
        Write-Host "   Tried users: $CurrentUser, postgres, $($env:USER)"
        Write-Host "   Please ensure PostgreSQL is running and you have superuser access"
        Write-Host ""
        Write-Host "💡 Common solutions:" -ForegroundColor Yellow
        Write-Host "   - Windows: Make sure PostgreSQL service is running"
        Write-Host "   - Check if you can connect with: psql -U postgres -d postgres"
        Write-Host "   - Verify PostgreSQL is in your PATH"
        exit 1
    }
    
    # Check if target user already exists
    Write-Status "👤 Checking if user '$DbUser' exists..."
    try {
        $userExists = & psql -U $SuperUser -d postgres -tAc "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$DbUser';" 2>$null
        
        if ($userExists -eq "1") {
            Write-Success "✅ User '$DbUser' already exists"
        }
        else {
            Write-Status "➕ Creating user '$DbUser'..."
            & psql -U $SuperUser -d postgres -c "CREATE USER $DbUser WITH PASSWORD '$DbPass'; ALTER USER $DbUser CREATEDB;" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-ErrorMsg "❌ Error: Failed to create user '$DbUser'"
                exit 1
            }
            Write-Success "✅ User '$DbUser' created successfully"
        }
    }
    catch {
        Write-ErrorMsg "❌ Error checking user existence"
        exit 1
    }
    
    # Check if database already exists
    Write-Status "🗄️  Checking if database '$DbName' exists..."
    try {
        $dbExists = & psql -U $SuperUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DbName';" 2>$null
        
        if ($dbExists -eq "1") {
            Write-Success "✅ Database '$DbName' already exists"
        }
        else {
            Write-Status "➕ Creating database '$DbName'..."
            & psql -U $SuperUser -d postgres -c "CREATE DATABASE $DbName OWNER $DbUser;" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-ErrorMsg "❌ Error: Failed to create database '$DbName'"
                exit 1
            }
            Write-Success "✅ Database '$DbName' created successfully"
        }
    }
    catch {
        Write-ErrorMsg "❌ Error checking database existence"
        exit 1
    }
    
    # Grant necessary privileges
    Write-Status "🔐 Ensuring user '$DbUser' has proper privileges..."
    try {
        & psql -U $SuperUser -d $DbName -c @"
GRANT ALL PRIVILEGES ON DATABASE $DbName TO $DbUser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DbUser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DbUser;
GRANT CREATE ON SCHEMA public TO $DbUser;
ALTER SCHEMA public OWNER TO $DbUser;
"@ 2>$null
    }
    catch {
        Write-Warning "⚠️  Warning: Some privilege grants may have failed, but continuing..."
    }
    
    # Test connection as target user
    Write-Status "🔍 Testing connection as user '$DbUser'..."
    try {
        & psql -U $DbUser -d $DbName -c "SELECT 1;" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Successfully connected as user '$DbUser'"
        }
        else {
            Write-Warning "⚠️  Warning: Could not connect as user '$DbUser', but continuing..."
            Write-Host "   You may need to update pg_hba.conf or check password authentication"
        }
    }
    catch {
        Write-Warning "⚠️  Warning: Could not test connection as user '$DbUser', but continuing..."
    }
}

# Enable pgvector extension on the database
Write-Status "🔌 Enabling pgvector extension..."
try {
    & psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "❌ Error: Failed to create pgvector extension"
        Write-Host "   Make sure pgvector is installed on your PostgreSQL instance"
        Write-Host "   See: https://github.com/pgvector/pgvector#installation"
        exit 1
    }
}
catch {
    Write-ErrorMsg "❌ Error: Failed to create pgvector extension"
    exit 1
}

Write-Success "✅ pgvector extension enabled for database `"$DbName`"."

# Apply initial schema
Write-Status "📋 Applying initial schema from: $SchemaFile"
try {
    & psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName -f $SchemaFile 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "❌ Error: Failed to apply schema from $SchemaFile"
        exit 1
    }
}
catch {
    Write-ErrorMsg "❌ Error: Failed to apply schema from $SchemaFile"
    exit 1
}

# Apply profile migrations
Write-Status "🔄 Applying profile migrations..."

# Determine migration file paths based on environment
if ($Environment -eq "docker") {
    $MigrateToProfilesFile = "C:\app\sql\002_migrate_to_profiles.sql"
    $ProfilesTrendsFile = "C:\app\sql\003_profiles_trends_integration.sql"
    $StagingTablesFile = "C:\app\sql\004_add_staging_tables.sql"
    $OptimizeIndexesFile = "C:\app\sql\005_optimize_indexes.sql"
}
else {
    $MigrateToProfilesFile = "$PSScriptRoot\002_migrate_to_profiles.sql"
    $ProfilesTrendsFile = "$PSScriptRoot\003_profiles_trends_integration.sql"
    $StagingTablesFile = "$PSScriptRoot\004_add_staging_tables.sql"
    $OptimizeIndexesFile = "$PSScriptRoot\005_optimize_indexes.sql"
}

# Apply profile migration
if (Test-Path $MigrateToProfilesFile) {
    Write-Status "📋 Applying profile migration from: $MigrateToProfilesFile"
    try {
        & psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName -f $MigrateToProfilesFile 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-ErrorMsg "❌ Error: Failed to apply profile migration from $MigrateToProfilesFile"
            exit 1
        }
        Write-Success "✅ Profile migration completed successfully"
    }
    catch {
        Write-ErrorMsg "❌ Error: Failed to apply profile migration from $MigrateToProfilesFile"
        exit 1
    }
}
else {
    Write-Warning "⚠️  Warning: Profile migration file not found at $MigrateToProfilesFile"
    Write-Host "   The system will work but profile features may not be available"
}

# Apply profiles-trends integration
if (Test-Path $ProfilesTrendsFile) {
    Write-Status "📋 Applying profiles-trends integration from: $ProfilesTrendsFile"
    try {
        & psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName -f $ProfilesTrendsFile 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-ErrorMsg "❌ Error: Failed to apply profiles-trends integration from $ProfilesTrendsFile"
            exit 1
        }
        Write-Success "✅ Profiles-trends integration completed successfully"
    }
    catch {
        Write-ErrorMsg "❌ Error: Failed to apply profiles-trends integration from $ProfilesTrendsFile"
        exit 1
    }
}
else {
    Write-Warning "⚠️  Warning: Profiles-trends integration file not found at $ProfilesTrendsFile"
    Write-Host "   Trends features may not work properly with profiles"
}

# Apply staging tables migration
if (Test-Path $StagingTablesFile) {
    Write-Status "📋 Applying staging tables migration from: $StagingTablesFile"
    try {
        & psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName -f $StagingTablesFile 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-ErrorMsg "❌ Error: Failed to apply staging tables migration from $StagingTablesFile"
            exit 1
        }
        Write-Success "✅ Staging tables migration completed successfully"
    }
    catch {
        Write-ErrorMsg "❌ Error: Failed to apply staging tables migration from $StagingTablesFile"
        exit 1
    }
}
else {
    Write-Warning "⚠️  Warning: Staging tables migration file not found at $StagingTablesFile"
    Write-Host "   Bulk import features may not be available"
}

# Apply index optimization
if (Test-Path $OptimizeIndexesFile) {
    Write-Status "📋 Applying index optimization from: $OptimizeIndexesFile"
    try {
        & psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName -f $OptimizeIndexesFile 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-ErrorMsg "❌ Error: Failed to apply index optimization from $OptimizeIndexesFile"
            exit 1
        }
        Write-Success "✅ Index optimization completed successfully"
    }
    catch {
        Write-ErrorMsg "❌ Error: Failed to apply index optimization from $OptimizeIndexesFile"
        exit 1
    }
}
else {
    Write-Warning "⚠️  Warning: Index optimization file not found at $OptimizeIndexesFile"
    Write-Host "   Database performance may not be optimal"
}

Write-Host ""
Write-Success "🎉 Database setup with profile features completed successfully!"
Write-Host ""
Write-Host "📋 Connection details:" -ForegroundColor $InfoColor
Write-Host "   Database: $DbName"
Write-Host "   User: $DbUser"
Write-Host "   Environment: $Environment"
Write-Host ""

if ($Environment -eq "local") {
    Write-Host "🔗 Connection string example:" -ForegroundColor $InfoColor
    Write-Host "   postgresql://$DbUser`:$DbPass@localhost:5432/$DbName"
    Write-Host ""
    Write-Host "💻 Test connection:" -ForegroundColor $InfoColor
    Write-Host "   psql -U $DbUser -d $DbName -h localhost"
} 