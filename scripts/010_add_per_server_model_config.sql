-- Migration 010: Add Per-Server Model Configuration
-- This migration adds support for per-server model name and configuration overrides
-- in the inference_servers table, enabling non-homogeneous multi-server deployments
-- where different servers can use different models (e.g., phi4 on Ollama vs phi4-mlx on LMStudio).

-- Add model_name column for per-server model override
ALTER TABLE inference_servers
ADD COLUMN IF NOT EXISTS model_name VARCHAR(200);

-- Add model_config JSONB for per-server model parameter overrides
ALTER TABLE inference_servers
ADD COLUMN IF NOT EXISTS model_config JSONB DEFAULT '{}';

-- Update existing servers to have empty model_config (not NULL)
UPDATE inference_servers
SET model_config = '{}'
WHERE model_config IS NULL;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_inference_servers_model_name
ON inference_servers(model_name)
WHERE model_name IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN inference_servers.model_name IS
    'Optional model name override for this specific server. '
    'If NULL, uses the global judge_model.model_name from orchestration settings. '
    'Enables per-server model variants (e.g., "phi4" on Ollama, "phi4-mlx" on LMStudio).';

COMMENT ON COLUMN inference_servers.model_config IS
    'Optional per-server model configuration overrides (JSONB). '
    'Valid keys: max_new_tokens, temperature, num_ctx, context_length, gpu_offload, etc. '
    'Values specified here override the global judge_model configuration for this server. '
    'Example: {"max_new_tokens": 1024, "temperature": 0.2, "num_ctx": 32768}';

-- Create a view for monitoring effective model configuration per server
CREATE OR REPLACE VIEW inference_servers_effective_config AS
SELECT
    s.id,
    s.name,
    s.url,
    s.provider,
    s.enabled,
    s.model_name as server_model_name,
    s.model_config as server_model_config,
    s.config_json as server_provider_config,
    CASE
        WHEN s.model_name IS NOT NULL THEN 'overridden'
        ELSE 'global'
    END as model_source,
    s.last_tested_at,
    s.last_test_ok,
    s.notes
FROM inference_servers s
ORDER BY s.provider, s.name;

COMMENT ON VIEW inference_servers_effective_config IS
    'View showing inference servers with their effective model configuration. '
    'The model_source column indicates whether the server uses a per-server model override or global config.';

-- Add trigger to validate model_config JSON structure
CREATE OR REPLACE FUNCTION validate_inference_server_model_config()
RETURNS TRIGGER AS $$
BEGIN
    -- Ensure model_config is valid JSONB
    IF NEW.model_config IS NOT NULL THEN
        -- Validate that model_config is an object (not array or primitive)
        IF jsonb_typeof(NEW.model_config) != 'object' THEN
            RAISE EXCEPTION 'model_config must be a JSON object, got: %', jsonb_typeof(NEW.model_config);
        END IF;

        -- Validate known keys have appropriate types
        IF NEW.model_config ? 'max_new_tokens' AND jsonb_typeof(NEW.model_config->'max_new_tokens') != 'number' THEN
            RAISE EXCEPTION 'model_config.max_new_tokens must be a number';
        END IF;

        IF NEW.model_config ? 'temperature' AND jsonb_typeof(NEW.model_config->'temperature') != 'number' THEN
            RAISE EXCEPTION 'model_config.temperature must be a number';
        END IF;

        IF NEW.model_config ? 'num_ctx' AND jsonb_typeof(NEW.model_config->'num_ctx') != 'number' THEN
            RAISE EXCEPTION 'model_config.num_ctx must be a number';
        END IF;

        IF NEW.model_config ? 'context_length' AND jsonb_typeof(NEW.model_config->'context_length') != 'number' THEN
            RAISE EXCEPTION 'model_config.context_length must be a number';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists (idempotent)
DROP TRIGGER IF EXISTS validate_inference_server_model_config_trigger ON inference_servers;

-- Create trigger
CREATE TRIGGER validate_inference_server_model_config_trigger
    BEFORE INSERT OR UPDATE ON inference_servers
    FOR EACH ROW
    EXECUTE FUNCTION validate_inference_server_model_config();

-- Migration verification: Show current state of inference_servers
DO $$
DECLARE
    server_count INTEGER;
    servers_with_model_override INTEGER;
BEGIN
    SELECT COUNT(*) INTO server_count FROM inference_servers;
    SELECT COUNT(*) INTO servers_with_model_override
    FROM inference_servers
    WHERE model_name IS NOT NULL;

    RAISE NOTICE 'Migration 010 completed successfully';
    RAISE NOTICE 'Total inference servers: %', server_count;
    RAISE NOTICE 'Servers with model override: %', servers_with_model_override;
    RAISE NOTICE 'Servers using global config: %', server_count - servers_with_model_override;
END $$;
