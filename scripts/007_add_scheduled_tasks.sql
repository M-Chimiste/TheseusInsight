-- Migration: Add scheduled tasks configuration tables
-- Description: Enables user-configurable scheduled tasks with profile support

-- Create enum for task types
CREATE TYPE scheduled_task_type AS ENUM (
    'newsletter',
    'trends_recomputation',
    'database_cleanup',
    'profile_ingestion',
    'bulk_embedding'
);

-- Create enum for schedule frequency
CREATE TYPE schedule_frequency AS ENUM (
    'hourly',
    'daily',
    'weekly',
    'monthly'
);

-- Create the scheduled_tasks table
CREATE TABLE scheduled_tasks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    task_type scheduled_task_type NOT NULL,
    profile_id INTEGER REFERENCES research_profiles(id) ON DELETE CASCADE,
    is_enabled BOOLEAN DEFAULT true,
    frequency schedule_frequency NOT NULL,
    
    -- Schedule configuration
    day_of_week INTEGER CHECK (day_of_week >= 0 AND day_of_week <= 6), -- 0=Monday, 6=Sunday
    day_of_month INTEGER CHECK (day_of_month >= 1 AND day_of_month <= 31),
    hour INTEGER NOT NULL CHECK (hour >= 0 AND hour <= 23),
    minute INTEGER NOT NULL DEFAULT 0 CHECK (minute >= 0 AND minute <= 59),
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Task-specific configuration (JSON)
    config JSONB DEFAULT '{}',
    
    -- Tracking fields
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    last_run_status VARCHAR(50),
    last_run_task_id VARCHAR(255),
    run_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_scheduled_tasks_enabled ON scheduled_tasks(is_enabled);
CREATE INDEX idx_scheduled_tasks_next_run ON scheduled_tasks(next_run_at) WHERE is_enabled = true;
CREATE INDEX idx_scheduled_tasks_profile ON scheduled_tasks(profile_id);
CREATE INDEX idx_scheduled_tasks_type ON scheduled_tasks(task_type);

-- Create scheduled_task_runs table to track execution history
CREATE TABLE scheduled_task_runs (
    id SERIAL PRIMARY KEY,
    scheduled_task_id INTEGER REFERENCES scheduled_tasks(id) ON DELETE CASCADE,
    task_id VARCHAR(255) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    result JSONB,
    
    -- Index for quick lookups
    CONSTRAINT idx_task_runs_unique_task_id UNIQUE (task_id)
);

-- Create indexes for run history
CREATE INDEX idx_scheduled_task_runs_task ON scheduled_task_runs(scheduled_task_id);
CREATE INDEX idx_scheduled_task_runs_started ON scheduled_task_runs(started_at);
CREATE INDEX idx_scheduled_task_runs_status ON scheduled_task_runs(status);

-- Add trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_scheduled_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_scheduled_tasks_updated_at_trigger
BEFORE UPDATE ON scheduled_tasks
FOR EACH ROW
EXECUTE FUNCTION update_scheduled_tasks_updated_at();

-- Insert default scheduled tasks (disabled by default)
INSERT INTO scheduled_tasks (name, task_type, frequency, hour, minute, is_enabled, config) VALUES
('Nightly Trends Recomputation', 'trends_recomputation', 'daily', 2, 0, false, 
 '{"lookback_months": 24, "duration_months": 6, "min_papers": 100}'),
('Weekly Database Cleanup', 'database_cleanup', 'weekly', 3, 0, false, 
 '{"months_to_keep": 24}');

-- Add comment to table
COMMENT ON TABLE scheduled_tasks IS 'Stores user-configurable scheduled tasks with profile support';
COMMENT ON COLUMN scheduled_tasks.day_of_week IS '0=Monday, 1=Tuesday, ..., 6=Sunday';
COMMENT ON COLUMN scheduled_tasks.config IS 'Task-specific configuration as JSON';