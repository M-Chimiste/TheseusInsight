"""Queue producer service for bulk judge operations."""

from typing import List, Tuple, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import logging
import json

from ..data_access.judge_task_queue import JudgeTaskQueueRepository
from ..data_access.papers import PaperRepository
from ..data_access.profiles import ProfileRepository, ProfileScoreRepository

logger = logging.getLogger(__name__)


class JudgeQueueProducer:
    """Service for producing judge tasks to the durable queue."""

    def __init__(self):
        self.task_queue_repo = JudgeTaskQueueRepository()

    def enqueue_bulk_judge_job(
        self,
        job_id: UUID,
        profile_ids: Optional[List[int]] = None,
        paper_ids: Optional[List[int]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        overwrite_existing: bool = False,
        create_processing_job: bool = True,
        server_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Enqueue a bulk judge job by creating tasks for paper-profile combinations.

        Args:
            job_id: UUID for the job
            profile_ids: List of profile IDs to judge (None = all active profiles)
            paper_ids: List of specific paper IDs (None = all papers in date range)
            date_from: Start date filter (None = no start filter)
            date_to: End date filter (None = no end filter)
            overwrite_existing: Whether to overwrite existing scores

        Returns:
            Dict with statistics about enqueued tasks
        """
        start_time = datetime.now()
        logger.info(f"Starting bulk judge job enqueue for job {job_id}")

        # Step 1: Create processing job if requested
        if create_processing_job:
            self._create_processing_job(
                job_id,
                profile_ids,
                paper_ids,
                date_from,
                date_to,
                overwrite_existing
            )

        # Step 2: Resolve target profiles
        target_profiles = self._resolve_target_profiles(profile_ids)
        if not target_profiles:
            return {
                'success': False,
                'error': 'No active profiles found',
                'profile_count': 0,
                'paper_count': 0,
                'tasks_enqueued': 0
            }

        logger.info(f"Resolved {len(target_profiles)} target profiles")

        # Step 3: Get papers to process
        logger.info(f"Getting papers with criteria: paper_ids={paper_ids}, date_from={date_from}, date_to={date_to}")
        papers = self._get_papers_to_process(paper_ids, date_from, date_to)
        logger.info(f"Retrieved {len(papers)} papers from repository")

        if not papers:
            logger.warning(f"No papers found matching criteria: paper_ids={paper_ids}, date_from={date_from}, date_to={date_to}")
            return {
                'success': False,
                'error': 'No papers found matching criteria',
                'profile_count': len(target_profiles),
                'paper_count': 0,
                'tasks_enqueued': 0
            }

        logger.info(f"Found {len(papers)} papers to process")
        if len(papers) > 0:
            logger.info(f"Sample paper: ID={papers[0].get('id')}, Date={papers[0].get('date')}, Title={papers[0].get('title')[:50]}...")

        # Step 4: Filter out already scored combinations if not overwriting
        paper_profile_combinations = self._generate_combinations(
            papers, target_profiles, overwrite_existing
        )

        if not paper_profile_combinations:
            logger.info("No paper-profile combinations need processing")
            return {
                'success': True,
                'profile_count': len(target_profiles),
                'paper_count': len(papers),
                'tasks_enqueued': 0,
                'skipped_existing': True
            }

        # Step 5: Enqueue tasks in batches
        batch_size = 1000  # Adjust based on performance needs
        total_enqueued = 0

        for i in range(0, len(paper_profile_combinations), batch_size):
            batch = paper_profile_combinations[i:i + batch_size]
            # Do not pre-assign servers; enable dynamic pooling across workers
            batch_enqueued = self.task_queue_repo.enqueue_tasks(job_id, batch, server_urls=None)

            if batch_enqueued > 0:
                total_enqueued += batch_enqueued
                logger.info(f"Enqueued batch {i//batch_size + 1}: {batch_enqueued} tasks")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(
            f"Bulk judge job {job_id} enqueue completed: "
            f"{total_enqueued} tasks enqueued in {duration:.2f}s"
        )
        
        if server_urls:
            logger.info(f"Tasks distributed across {len(server_urls)} servers: {', '.join(server_urls)}")

        return {
            'success': True,
            'job_id': str(job_id),
            'profile_count': len(target_profiles),
            'paper_count': len(papers),
            'tasks_enqueued': total_enqueued,
            'duration_seconds': duration,
            'profiles': [p['name'] for p in target_profiles],
            'overwrite_existing': overwrite_existing
        }

    def _resolve_target_profiles(self, profile_ids: Optional[List[int]]) -> List[Dict[str, Any]]:
        """Resolve which profiles to target."""
        if profile_ids:
            profiles = []
            for profile_id in profile_ids:
                profile = ProfileRepository.get_by_id(profile_id)
                if profile and profile.get('is_active', True):
                    profiles.append(profile)
                else:
                    logger.warning(f"Profile {profile_id} not found or inactive")
            return profiles
        else:
            # Get all active profiles
            return ProfileRepository.get_all_active()

    def _get_papers_to_process(
        self,
        paper_ids: Optional[List[int]],
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get papers to process based on criteria."""
        if paper_ids:
            # Specific paper IDs provided
            papers = []
            for paper_id in paper_ids:
                paper = PaperRepository.get_by_id(paper_id)
                if paper:
                    papers.append(paper)
                else:
                    logger.warning(f"Paper {paper_id} not found")
            return papers
        else:
            # Date range query
            return PaperRepository.get_papers_in_date_range(
                start_date=date_from,
                end_date=date_to
            )

    def _generate_combinations(
        self,
        papers: List[Dict[str, Any]],
        profiles: List[Dict[str, Any]],
        overwrite_existing: bool
    ) -> List[Tuple[int, int]]:
        """Generate paper-profile combinations that need processing."""
        combinations = []

        for paper in papers:
            paper_id = paper['id']

            if overwrite_existing:
                # Include all combinations if overwriting
                for profile in profiles:
                    combinations.append((paper_id, profile['id']))
            else:
                # Filter out already scored combinations
                for profile in profiles:
                    profile_id = profile['id']
                    # Check if this specific paper-profile combination already has a score
                    if not ProfileScoreRepository.has_score_for_profile(paper_id, profile_id):
                        combinations.append((paper_id, profile_id))

        logger.info(
            f"Generated {len(combinations)} paper-profile combinations "
            f"({'overwriting' if overwrite_existing else 'skipping existing'})"
        )

        return combinations

    def _create_processing_job(
        self,
        job_id: UUID,
        profile_ids: Optional[List[int]],
        paper_ids: Optional[List[int]],
        date_from: Optional[str],
        date_to: Optional[str],
        overwrite_existing: bool
    ):
        """Create a processing job record for tracking."""
        from ..db import get_cursor

        configuration = {
            'profile_ids': profile_ids,
            'paper_ids': paper_ids,
            'date_from': date_from,
            'date_to': date_to,
            'overwrite_existing': overwrite_existing,
            'created_by': 'queue_producer'
        }

        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO processing_jobs (
                    id, job_type, configuration, status, created_at
                ) VALUES (%s, 'bulk_judge_queue', %s, 'pending', CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO NOTHING
            """, (str(job_id), json.dumps(configuration)))

        logger.info(f"Created/ensured processing job {job_id}")

    def get_job_enqueue_status(self, job_id: UUID) -> Dict[str, Any]:
        """Get the current enqueue status for a job."""
        queue_stats = self.task_queue_repo.get_job_progress(job_id)

        return {
            'job_id': str(job_id),
            'total_tasks': queue_stats.get('total_tasks', 0),
            'completed_tasks': queue_stats.get('completed_tasks', 0),
            'failed_tasks': queue_stats.get('failed_tasks', 0),
            'pending_tasks': queue_stats.get('pending_tasks', 0),
            'leased_tasks': queue_stats.get('leased_tasks', 0),
            'in_progress_tasks': queue_stats.get('in_progress_tasks', 0),
            'canceled_tasks': queue_stats.get('canceled_tasks', 0),
            'completion_percentage': (
                queue_stats.get('completed_tasks', 0) / queue_stats.get('total_tasks', 1) * 100
                if queue_stats.get('total_tasks', 0) > 0 else 0
            ),
            'avg_attempts': queue_stats.get('avg_attempts', 0),
            'max_attempts': queue_stats.get('max_attempts', 0)
        }

    def cancel_job_enqueue(self, job_id: UUID) -> int:
        """Cancel all pending tasks for a job. Returns count of canceled tasks."""
        canceled_count = self.task_queue_repo.cancel_job_tasks(job_id)
        logger.info(f"Canceled {canceled_count} pending tasks for job {job_id}")
        return canceled_count
