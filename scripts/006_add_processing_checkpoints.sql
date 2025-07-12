-- Migration 006: Add processing checkpoints for resumable operations
-- This adds tables to track processing state and enable resume functionality

-- Create processing jobs table
CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(100) NOT NULL, -- 'harvest_judge', 'bulk_judge', 'embedding_backfill', etc.
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    configuration JSONB NOT NULL, -- Job configuration (dates, thresholds, etc.)
    state JSONB, -- Current processing state for resume
    progress_current INTEGER DEFAULT 0,
    progress_total INTEGER,
    progress_percent NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN progress_total > 0 THEN (progress_current::NUMERIC / progress_total * 100)::NUMERIC(5,2)
            ELSE 0
        END
    ) STORED,
    error_message TEXT,
    error_count INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_checkpoint_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create checkpoints table for detailed progress tracking
CREATE TABLE IF NOT EXISTS processing_checkpoints (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    checkpoint_type VARCHAR(50) NOT NULL, -- 'papers_processed', 'embeddings_generated', etc.
    checkpoint_data JSONB NOT NULL, -- Checkpoint-specific data
    item_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX idx_processing_jobs_job_type ON processing_jobs(job_type);
CREATE INDEX idx_processing_jobs_created_at ON processing_jobs(created_at DESC);
CREATE INDEX idx_processing_checkpoints_job_id ON processing_checkpoints(job_id);
CREATE INDEX idx_processing_checkpoints_created_at ON processing_checkpoints(created_at DESC);

-- Function to update job progress
CREATE OR REPLACE FUNCTION update_job_progress(
    p_job_id UUID,
    p_current INTEGER,
    p_total INTEGER DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    UPDATE processing_jobs
    SET 
        progress_current = p_current,
        progress_total = COALESCE(p_total, progress_total),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to save checkpoint
CREATE OR REPLACE FUNCTION save_checkpoint(
    p_job_id UUID,
    p_checkpoint_type VARCHAR(50),
    p_checkpoint_data JSONB,
    p_item_count INTEGER DEFAULT 0
) RETURNS VOID AS $$
BEGIN
    -- Insert checkpoint
    INSERT INTO processing_checkpoints (job_id, checkpoint_type, checkpoint_data, item_count)
    VALUES (p_job_id, p_checkpoint_type, p_checkpoint_data, p_item_count);
    
    -- Update job last checkpoint time
    UPDATE processing_jobs
    SET 
        last_checkpoint_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get latest checkpoint for a job
CREATE OR REPLACE FUNCTION get_latest_checkpoint(
    p_job_id UUID,
    p_checkpoint_type VARCHAR(50) DEFAULT NULL
) RETURNS TABLE (
    checkpoint_data JSONB,
    item_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pc.checkpoint_data,
        pc.item_count,
        pc.created_at
    FROM processing_checkpoints pc
    WHERE pc.job_id = p_job_id
        AND (p_checkpoint_type IS NULL OR pc.checkpoint_type = p_checkpoint_type)
    ORDER BY pc.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_processing_jobs_updated_at
    BEFORE UPDATE ON processing_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add some useful views
CREATE OR REPLACE VIEW active_jobs AS
SELECT 
    id,
    job_type,
    status,
    progress_current,
    progress_total,
    progress_percent,
    started_at,
    last_checkpoint_at,
    CASE 
        WHEN status = 'running' AND started_at IS NOT NULL THEN
            EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))::INTEGER
        ELSE NULL
    END as runtime_seconds
FROM processing_jobs
WHERE status IN ('pending', 'running')
ORDER BY created_at DESC;

CREATE OR REPLACE VIEW job_statistics AS
SELECT 
    job_type,
    COUNT(*) as total_jobs,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_jobs,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs,
    COUNT(*) FILTER (WHERE status = 'running') as running_jobs,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) FILTER (WHERE status = 'completed') as avg_runtime_seconds,
    MAX(created_at) as last_job_created
FROM processing_jobs
GROUP BY job_type;

-- Comments
COMMENT ON TABLE processing_jobs IS 'Tracks all processing jobs for resume capability';
COMMENT ON TABLE processing_checkpoints IS 'Stores checkpoints for resuming interrupted jobs';
COMMENT ON FUNCTION update_job_progress IS 'Updates job progress counters';
COMMENT ON FUNCTION save_checkpoint IS 'Saves a checkpoint for a processing job';
COMMENT ON FUNCTION get_latest_checkpoint IS 'Retrieves the most recent checkpoint for a job';