-- Migration 009: Add LMStudio Multi-Server Support
-- This migration extends the ollama_servers table to support multiple inference providers
-- including LMStudio, and renames it to inference_servers for clarity.

-- Rename ollama_servers to inference_servers for generality
ALTER TABLE ollama_servers RENAME TO inference_servers;

-- Add provider column to distinguish between Ollama and LMStudio
ALTER TABLE inference_servers
ADD COLUMN provider VARCHAR(20) NOT NULL DEFAULT 'ollama'
    CHECK (provider IN ('ollama', 'lmstudio'));

-- Add additional config for provider-specific parameters (e.g., LMStudio context_length, gpu_offload)
ALTER TABLE inference_servers
ADD COLUMN config_json JSONB DEFAULT '{}';

-- Update existing servers to have provider='ollama' (for safety, though DEFAULT handles this)
UPDATE inference_servers SET provider = 'ollama' WHERE provider IS NULL OR provider = '';

-- Drop old indexes
DROP INDEX IF EXISTS idx_ollama_servers_enabled;

-- Create new indexes
CREATE INDEX idx_inference_servers_enabled ON inference_servers(enabled) WHERE enabled = TRUE;
CREATE INDEX idx_inference_servers_provider ON inference_servers(provider);
CREATE INDEX idx_inference_servers_provider_enabled ON inference_servers(provider, enabled) WHERE enabled = TRUE;

-- Add comments for documentation
COMMENT ON TABLE inference_servers IS 'Multi-server configuration for local inference providers (Ollama, LMStudio)';
COMMENT ON COLUMN inference_servers.provider IS 'Provider type: ollama or lmstudio';
COMMENT ON COLUMN inference_servers.config_json IS 'Provider-specific configuration JSON. For LMStudio: {context_length, gpu_offload}. For Ollama: {}';

-- Example LMStudio server configuration (commented out, for reference):
-- INSERT INTO inference_servers (name, url, provider, enabled, config_json, notes)
-- VALUES (
--     'Local LMStudio',
--     'localhost:1234',
--     'lmstudio',
--     true,
--     '{"context_length": 32768, "gpu_offload": "max"}',
--     'LMStudio server on local workstation'
-- );
