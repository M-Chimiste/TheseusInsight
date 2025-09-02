-- Migration 008: Add Multi-Ollama Server Support for Bulk Judge Operations
-- This migration adds support for multiple Ollama servers and a durable task queue
-- for distributed LLM judge processing across multiple servers

-- Drop existing tables to start fresh (as requested for dev environment)
DROP TABLE IF EXISTS worker_heartbeats CASCADE;
DROP TABLE IF EXISTS judge_task_queue CASCADE;
DROP TABLE IF EXISTS ollama_servers CASCADE;

-- Create Ollama servers configuration table
CREATE TABLE ollama_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(500) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    notes TEXT,
    last_tested_at TIMESTAMP WITH TIME ZONE,
    last_test_latency_ms INTEGER,
    last_test_ok BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create judge task queue table for durable processing
CREATE TABLE judge_task_queue (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'leased', 'in_progress', 'completed', 'failed', 'canceled')),
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    assigned_server_url VARCHAR(500),
    leased_until TIMESTAMP WITH TIME ZONE,
    leased_by_worker VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, paper_id, profile_id)
);

-- Create worker heartbeats table for monitoring
CREATE TABLE worker_heartbeats (
    id SERIAL PRIMARY KEY,
    worker_id VARCHAR(100) NOT NULL,
    server_url VARCHAR(500) NOT NULL,
    job_id UUID REFERENCES processing_jobs(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    tasks_processed INTEGER DEFAULT 0,
    current_task_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(worker_id, server_url, job_id)
);

-- Create error logs table for monitoring and debugging
CREATE TABLE error_logs (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL,
    task_id INTEGER,
    server_url VARCHAR(500),
    worker_id VARCHAR(100),
    error_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for error logs
CREATE INDEX idx_error_logs_job_id ON error_logs(job_id);
CREATE INDEX idx_error_logs_type ON error_logs(error_type);
CREATE INDEX idx_error_logs_severity ON error_logs(severity);
CREATE INDEX idx_error_logs_created_at ON error_logs(created_at);

-- Add indexes for performance (only create if tables exist and indexes don't exist)
DO $$
BEGIN
    -- Ollama servers indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ollama_servers') THEN
        CREATE INDEX IF NOT EXISTS idx_ollama_servers_enabled ON ollama_servers(enabled);
        CREATE INDEX IF NOT EXISTS idx_ollama_servers_url ON ollama_servers(url);
    END IF;

    -- Judge task queue indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'judge_task_queue') THEN
        CREATE INDEX IF NOT EXISTS idx_judge_queue_status ON judge_task_queue(status);
        CREATE INDEX IF NOT EXISTS idx_judge_queue_job_status ON judge_task_queue(job_id, status);
        CREATE INDEX IF NOT EXISTS idx_judge_queue_lease ON judge_task_queue(status, leased_until)
            WHERE leased_until IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_judge_queue_server ON judge_task_queue(assigned_server_url, status);
    END IF;

    -- Worker heartbeats indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'worker_heartbeats') THEN
        CREATE INDEX IF NOT EXISTS idx_worker_heartbeats_job ON worker_heartbeats(job_id);
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'worker_heartbeats' AND column_name = 'last_heartbeat') THEN
            CREATE INDEX IF NOT EXISTS idx_worker_heartbeats_heartbeat ON worker_heartbeats(last_heartbeat);
        END IF;
    END IF;
END $$;

-- Extend processing_jobs table with bulk judge specific fields
ALTER TABLE processing_jobs
ADD COLUMN IF NOT EXISTS job_type VARCHAR(50) DEFAULT 'bulk_judge',
ADD COLUMN IF NOT EXISTS cancel_requested BOOLEAN DEFAULT FALSE;

-- Create or replace the update function (safe to run multiple times)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers conditionally (only if tables exist)
DO $$
BEGIN
    -- Add triggers only if tables exist
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ollama_servers') THEN
        DROP TRIGGER IF EXISTS update_ollama_servers_updated_at ON ollama_servers;
        CREATE TRIGGER update_ollama_servers_updated_at
            BEFORE UPDATE ON ollama_servers
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'judge_task_queue') THEN
        DROP TRIGGER IF EXISTS update_judge_task_queue_updated_at ON judge_task_queue;
        CREATE TRIGGER update_judge_task_queue_updated_at
            BEFORE UPDATE ON judge_task_queue
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'worker_heartbeats') THEN
        DROP TRIGGER IF EXISTS update_worker_heartbeats_updated_at ON worker_heartbeats;
        CREATE TRIGGER update_worker_heartbeats_updated_at
            BEFORE UPDATE ON worker_heartbeats
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Insert some sample Ollama servers for development (optional)
-- These can be removed in production or customized as needed
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ollama_servers') THEN
        INSERT INTO ollama_servers (name, url, notes) VALUES
            ('Local Ollama', 'http://localhost:11434', 'Default local Ollama installation'),
            ('Server 1', 'http://server1:11434', 'Remote Ollama server 1'),
            ('Server 2', 'http://server2:11434', 'Remote Ollama server 2')
        ON CONFLICT (url) DO NOTHING;
    END IF;
END $$;

-- Add comments for documentation
COMMENT ON TABLE ollama_servers IS 'Configuration for multiple Ollama servers used in bulk judge operations';
COMMENT ON TABLE judge_task_queue IS 'Durable task queue for distributed bulk judge processing';
COMMENT ON TABLE worker_heartbeats IS 'Heartbeat monitoring for worker processes';

COMMENT ON COLUMN judge_task_queue.status IS 'Task status: pending, leased, in_progress, completed, failed, canceled';
COMMENT ON COLUMN judge_task_queue.assigned_server_url IS 'URL of the Ollama server assigned to process this task';
COMMENT ON COLUMN judge_task_queue.leased_until IS 'Timestamp until which the task is leased to a worker';
COMMENT ON COLUMN judge_task_queue.leased_by_worker IS 'Identifier of the worker that leased this task';

-- Create a view for monitoring active tasks
CREATE OR REPLACE VIEW active_judge_tasks AS
SELECT
    jt.*,
    pj.job_type,
    pj.status as job_status,
    pj.progress_current,
    pj.progress_total,
    pj.started_at as job_started_at,
    os.name as server_name
FROM judge_task_queue jt
JOIN processing_jobs pj ON jt.job_id = pj.id
LEFT JOIN ollama_servers os ON jt.assigned_server_url = os.url
WHERE jt.status IN ('leased', 'in_progress')
ORDER BY jt.created_at DESC;

-- Grant necessary permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ollama_servers TO theseus_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON judge_task_queue TO theseus_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON worker_heartbeats TO theseus_user;
