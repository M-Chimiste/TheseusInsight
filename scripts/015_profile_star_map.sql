-- Migration: Profile Star Map cached points
-- Stores precomputed 2D coordinates (x,y) for up to ~10k papers per profile.
-- This enables fast interactive rendering in the frontend without shipping raw embeddings.

CREATE TABLE IF NOT EXISTS profile_star_map_points (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    x DOUBLE PRECISION NOT NULL,
    y DOUBLE PRECISION NOT NULL,
    dominant_interest_id INTEGER REFERENCES profile_research_interests(id) ON DELETE SET NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, paper_id)
);

-- Fast retrieval per profile / most recent compute
CREATE INDEX IF NOT EXISTS idx_profile_star_map_points_profile
    ON profile_star_map_points(profile_id);

CREATE INDEX IF NOT EXISTS idx_profile_star_map_points_profile_computed_at
    ON profile_star_map_points(profile_id, computed_at DESC);

