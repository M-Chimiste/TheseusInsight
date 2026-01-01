-- Migration: Add Z coordinate to Profile Star Map cached points
-- Enables 3D visualization (x,y,z) in the frontend.

ALTER TABLE profile_star_map_points
ADD COLUMN IF NOT EXISTS z DOUBLE PRECISION NOT NULL DEFAULT 0;

