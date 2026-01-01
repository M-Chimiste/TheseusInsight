"""Data access + computation for Profile Star Map cached points."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from ..db import get_cursor


ProgressCallback = Callable[[str, float, str], None]


@dataclass(frozen=True)
class StarMapPointRow:
    paper_id: int
    x: float
    y: float
    z: float
    dominant_interest_id: Optional[int]


def _parse_pgvector(v: Any) -> Optional[np.ndarray]:
    """Parse a pgvector value into a numpy vector.

    In this codebase, pgvector values typically come back as strings like:
      '[0.1,0.2,...]'
    """
    if v is None:
        return None
    if isinstance(v, np.ndarray):
        return v.astype(np.float32, copy=False)
    if isinstance(v, (list, tuple)):
        return np.asarray(v, dtype=np.float32)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # Fast parse using numpy.
        s = s.strip("[]")
        arr = np.fromstring(s, sep=",", dtype=np.float32)
        if arr.size == 0:
            return None
        return arr
    return None


def _make_projection_matrix(dim: int, *, out_dim: int = 2, seed: int = 42) -> np.ndarray:
    """Create a deterministic orthonormal projection matrix of shape (dim, out_dim)."""
    rng = np.random.default_rng(seed)
    m = rng.normal(size=(dim, out_dim)).astype(np.float32)
    # Orthonormalize columns via QR.
    q, _ = np.linalg.qr(m)
    return q.astype(np.float32, copy=False)


class ProfileStarMapRepository:
    """Repository for cached star map points + computation pipeline."""

    @staticmethod
    def get_status(profile_id: int) -> Dict[str, Any]:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    %s::int AS profile_id,
                    MAX(computed_at) AS computed_at,
                    COUNT(*)::int AS total_points
                FROM profile_star_map_points
                WHERE profile_id = %s
                """,
                (profile_id, profile_id),
            )
            row = cur.fetchone() or {}
            computed_at = row.get("computed_at")
            return {
                "profile_id": profile_id,
                "computed_at": computed_at.isoformat() if computed_at else None,
                "total_points": row.get("total_points", 0),
            }

    @staticmethod
    def get_points(profile_id: int, *, limit: int = 10000) -> Dict[str, Any]:
        """Return cached points + lightweight metadata for rendering/tooltips."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT MAX(computed_at) AS computed_at
                FROM profile_star_map_points
                WHERE profile_id = %s
                """,
                (profile_id,),
            )
            computed_at = (cur.fetchone() or {}).get("computed_at")

            if not computed_at:
                return {
                    "profile_id": profile_id,
                    "total_points": 0,
                    "computed_at": None,
                    "points": [],
                }

            cur.execute(
                """
                SELECT
                    sp.paper_id,
                    sp.x,
                    sp.y,
                    sp.z,
                    sp.dominant_interest_id,
                    pri.interest_text AS dominant_label,
                    pri.short_label AS dominant_short_label,
                    p.title,
                    p.date,
                    p.score AS paper_score,
                    pps.score AS profile_score
                FROM profile_star_map_points sp
                JOIN papers p ON p.id = sp.paper_id
                LEFT JOIN paper_profile_scores pps
                    ON pps.paper_id = sp.paper_id AND pps.profile_id = sp.profile_id
                LEFT JOIN profile_research_interests pri
                    ON pri.id = sp.dominant_interest_id
                WHERE sp.profile_id = %s AND sp.computed_at = %s
                ORDER BY p.date DESC NULLS LAST, sp.paper_id DESC
                LIMIT %s
                """,
                (profile_id, computed_at, limit),
            )
            rows = cur.fetchall() or []

        points_list = [
            {
                "paper_id": r["paper_id"],
                "x": float(r["x"]),
                "y": float(r["y"]),
                "z": float(r.get("z") or 0.0),
                "dominant_interest_id": r.get("dominant_interest_id"),
                "dominant_label": r.get("dominant_label"),
                "dominant_short_label": r.get("dominant_short_label"),
                "title": r.get("title"),
                "date": r.get("date").isoformat() if r.get("date") else None,
                "paper_score": r.get("paper_score"),
                "profile_score": r.get("profile_score"),
            }
            for r in rows
        ]

        # Compute centroids for each constellation.
        from collections import defaultdict
        groups: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for p in points_list:
            interest_id = p.get("dominant_interest_id")
            if interest_id is not None:
                groups[interest_id].append(p)

        centroids = []
        for interest_id, pts in groups.items():
            if not pts:
                continue
            cx = sum(p["x"] for p in pts) / len(pts)
            cy = sum(p["y"] for p in pts) / len(pts)
            cz = sum(p["z"] for p in pts) / len(pts)
            # Get label from first point.
            label = pts[0].get("dominant_label") or ""
            short_label = pts[0].get("dominant_short_label") or label
            centroids.append({
                "interest_id": interest_id,
                "x": cx,
                "y": cy,
                "z": cz,
                "label": label,
                "short_label": short_label,
                "count": len(pts),
            })

        return {
            "profile_id": profile_id,
            "total_points": len(rows),
            "computed_at": computed_at.isoformat() if computed_at else None,
            "points": points_list,
            "centroids": centroids,
        }

    @staticmethod
    def _delete_points(profile_id: int) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM profile_star_map_points WHERE profile_id = %s", (profile_id,))

    @staticmethod
    def _insert_points(profile_id: int, computed_at: datetime, points: List[StarMapPointRow]) -> None:
        if not points:
            return
        computed_at_str = computed_at.isoformat()

        # Chunk inserts to avoid very large executemany payloads.
        chunk_size = 1000
        with get_cursor() as cur:
            for i in range(0, len(points), chunk_size):
                batch = points[i : i + chunk_size]
                cur.executemany(
                    """
                    INSERT INTO profile_star_map_points
                      (profile_id, paper_id, x, y, z, dominant_interest_id, computed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (profile_id, paper_id) DO UPDATE SET
                      x = EXCLUDED.x,
                      y = EXCLUDED.y,
                      z = EXCLUDED.z,
                      dominant_interest_id = EXCLUDED.dominant_interest_id,
                      computed_at = EXCLUDED.computed_at
                    """,
                    [
                        (
                            profile_id,
                            p.paper_id,
                            float(p.x),
                            float(p.y),
                            float(p.z),
                            p.dominant_interest_id,
                            computed_at_str,
                        )
                        for p in batch
                    ],
                )

    @staticmethod
    def _fetch_profile_papers_with_embeddings(profile_id: int, *, limit: int) -> List[Dict[str, Any]]:
        """Fetch the most recent profile-scored papers that have embeddings."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id AS paper_id,
                    p.embedding AS embedding
                FROM papers p
                JOIN paper_profile_scores pps
                    ON pps.paper_id = p.id AND pps.profile_id = %s
                WHERE p.embedding IS NOT NULL
                ORDER BY p.date DESC NULLS LAST, p.id DESC
                LIMIT %s
                """,
                (profile_id, limit),
            )
            return cur.fetchall() or []

    @staticmethod
    def _fetch_dominant_interests(profile_id: int, paper_ids: List[int]) -> Dict[int, Tuple[int, str]]:
        """Return mapping paper_id -> (interest_id, interest_text) based on best similarity."""
        if not paper_ids:
            return {}
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (ppi.paper_id)
                    ppi.paper_id,
                    pri.id AS profile_interest_id,
                    pri.interest_text
                FROM profile_paper_interests ppi
                JOIN profile_research_interests pri
                    ON pri.id = ppi.profile_interest_id
                WHERE pri.profile_id = %s
                  AND ppi.paper_id = ANY(%s)
                ORDER BY ppi.paper_id, ppi.similarity_score DESC
                """,
                (profile_id, paper_ids),
            )
            rows = cur.fetchall() or []
        return {int(r["paper_id"]): (int(r["profile_interest_id"]), r["interest_text"]) for r in rows}

    @staticmethod
    def recompute_profile_star_map(
        profile_id: int,
        *,
        limit: int = 10000,
        progress_cb: ProgressCallback | None = None,
    ) -> Dict[str, Any]:
        """Compute and cache a new star map for a profile (sync, blocking).

        Papers are organized by constellation (dominant interest) so that
        papers with the same interest are grouped together in distinct regions.
        """
        computed_at = datetime.utcnow()

        def progress(step: str, pct: float, msg: str):
            if progress_cb:
                progress_cb(step, pct, msg)

        progress("fetching", 5, f"Fetching up to {limit} papers with embeddings")
        rows = ProfileStarMapRepository._fetch_profile_papers_with_embeddings(profile_id, limit=limit)
        paper_ids = [int(r["paper_id"]) for r in rows]

        if not rows:
            ProfileStarMapRepository._delete_points(profile_id)
            return {
                "profile_id": profile_id,
                "computed_at": computed_at.isoformat(),
                "total_points": 0,
                "message": "No papers with embeddings found for this profile",
            }

        progress("parsing_embeddings", 15, f"Parsing embeddings for {len(rows)} papers")
        vecs: List[np.ndarray] = []
        valid_paper_ids: List[int] = []
        dropped_nonfinite = 0
        dropped_extreme = 0
        for r in rows:
            emb = _parse_pgvector(r["embedding"])
            if emb is None:
                continue
            # Defensive sanitization: skip any vectors with NaN/Inf or absurd magnitudes.
            if not np.isfinite(emb).all():
                dropped_nonfinite += 1
                continue
            if float(np.max(np.abs(emb))) > 1e3:
                dropped_extreme += 1
                continue
            vecs.append(emb)
            valid_paper_ids.append(int(r["paper_id"]))

        if not vecs:
            ProfileStarMapRepository._delete_points(profile_id)
            return {
                "profile_id": profile_id,
                "computed_at": computed_at.isoformat(),
                "total_points": 0,
                "message": "Embeddings could not be parsed for this profile",
            }

        if dropped_nonfinite or dropped_extreme:
            progress(
                "sanitizing",
                25,
                f"Skipped {dropped_nonfinite} non-finite and {dropped_extreme} extreme embeddings",
            )

        progress("dominant_interests", 30, "Computing dominant interest labels")
        dom = ProfileStarMapRepository._fetch_dominant_interests(profile_id, valid_paper_ids)

        # Group papers by dominant interest for constellation-based layout.
        groups: Dict[Optional[int], List[int]] = {}  # interest_id -> list of indices
        for idx, paper_id in enumerate(valid_paper_ids):
            interest_id = dom.get(paper_id, (None, ""))[0] if paper_id in dom else None
            groups.setdefault(interest_id, []).append(idx)

        # Sort groups by size (largest first) for consistent layout.
        sorted_groups = sorted(groups.items(), key=lambda kv: -len(kv[1]))
        num_groups = len(sorted_groups)

        progress("projecting", 40, f"Projecting {len(vecs)} vectors to 3D with {num_groups} constellations")

        dim = int(vecs[0].shape[0])
        X_all = np.stack(vecs, axis=0).astype(np.float32, copy=False)

        # Normalize vectors to unit length for numerical stability.
        norms = np.linalg.norm(X_all.astype(np.float64), axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        X_all = (X_all / norms).astype(np.float32, copy=False)

        P = _make_projection_matrix(dim, out_dim=3, seed=42)

        # Final coordinates for all points.
        final_coords = np.zeros((len(valid_paper_ids), 3), dtype=np.float32)

        # Project all points to 3D (embedding-based positions).
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            Y_initial = X_all @ P

        # Filter non-finite and normalize to [-1, 1].
        finite_mask = np.isfinite(Y_initial).all(axis=1)
        Y_initial = np.where(finite_mask[:, None], Y_initial, 0.0)
        y_min = Y_initial.min(axis=0)
        y_max = Y_initial.max(axis=0)
        y_span = np.where((y_max - y_min) == 0, 1.0, (y_max - y_min))
        positions = ((Y_initial - y_min) / y_span) * 2.0 - 1.0  # [-1, 1]

        progress("constellation_gravity", 50, f"Applying constellation gravity to {num_groups} groups")

        # Compute constellation centroids from initial positions.
        centroids = {}
        for interest_id, indices in sorted_groups:
            if indices:
                centroids[interest_id] = positions[indices].mean(axis=0)

        # Apply gentle gravity: blend each point toward its constellation centroid.
        # gravity_strength=0 means pure embedding layout, 1.0 means all points at centroid.
        gravity_strength = 0.4  # 40% pull toward centroid, 60% original position

        for interest_id, indices in sorted_groups:
            if not indices or interest_id not in centroids:
                continue
            centroid = centroids[interest_id]
            for idx in indices:
                original = positions[idx]
                # Blend: move toward centroid while preserving local structure.
                positions[idx] = original * (1 - gravity_strength) + centroid * gravity_strength

        # Re-normalize to use full [-1, 1] space after gravity adjustment.
        p_min = positions.min(axis=0)
        p_max = positions.max(axis=0)
        p_span = np.where((p_max - p_min) == 0, 1.0, (p_max - p_min))
        positions = ((positions - p_min) / p_span) * 2.0 - 1.0

        final_coords = positions.copy()

        progress("normalizing", 70, "Normalizing final coordinates")

        # Final normalization to [-1, 1] range.
        min_xyz = final_coords.min(axis=0)
        max_xyz = final_coords.max(axis=0)
        span = np.where((max_xyz - min_xyz) == 0, 1.0, (max_xyz - min_xyz))
        Yn = ((final_coords - min_xyz) / span) * 2.0 - 1.0

        # Build points list.
        points: List[StarMapPointRow] = []
        for idx, paper_id in enumerate(valid_paper_ids):
            if not np.isfinite(Yn[idx]).all():
                continue
            interest_id = dom.get(paper_id, (None, ""))[0] if paper_id in dom else None
            points.append(
                StarMapPointRow(
                    paper_id=paper_id,
                    x=float(Yn[idx, 0]),
                    y=float(Yn[idx, 1]),
                    z=float(Yn[idx, 2]),
                    dominant_interest_id=interest_id,
                )
            )

        progress("writing_cache", 88, f"Writing {len(points)} cached points")
        ProfileStarMapRepository._delete_points(profile_id)
        ProfileStarMapRepository._insert_points(profile_id, computed_at, points)

        progress("complete", 100, "Star map recompute complete")
        return {
            "profile_id": profile_id,
            "computed_at": computed_at.isoformat(),
            "total_points": len(points),
            "message": f"Computed star map for {len(points)} papers in {num_groups} constellations",
        }

