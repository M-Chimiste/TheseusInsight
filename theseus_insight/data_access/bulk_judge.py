"""Bulk LLM Judge operations for scoring papers across multiple profiles."""

from __future__ import annotations

import json
import time
import uuid
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
import json_repair
from tqdm import tqdm
import asyncio

from ..inference.llm import OllamaInference, OpenAIInference, AnthropicInference, GeminiInference
from ..prompt import RESEARCH_INTERESTS_SYSTEM_PROMPT, research_prompt
from .profiles import ProfileRepository, ProfileInterestsRepository, ProfileScoreRepository
from .papers import PaperRepository
from ..api.models import BulkJudgeRunRequest, BulkJudgeRunResponse
from ..data_processing.optimized_ollama_scoring import OptimizedOllamaScorer
from ..data_processing.checkpoint_manager import CheckpointManager


class BulkJudgeRunner:
    """Service for running LLM judge scoring across multiple profiles."""
    
    def __init__(
        self, 
        judge_model_config: dict, 
        verbose: bool = True,
        use_optimized_scorer: bool = True,
        embedding_model=None,
        checkpoint_manager: Optional[CheckpointManager] = None
    ):
        """
        Initialize the bulk judge runner with model configuration.
        
        Args:
            judge_model_config: Configuration for the judge model
            verbose: Whether to show progress information
            use_optimized_scorer: Whether to use the optimized Ollama scorer
            embedding_model: Optional embedding model for similarity-based optimizations
        """
        self.judge_model_config = judge_model_config
        self.verbose = verbose
        self.judge_inference = self._load_judge_model(judge_model_config)
        self.use_optimized_scorer = use_optimized_scorer
        self.embedding_model = embedding_model
        self.checkpoint_manager = checkpoint_manager
        
        # Initialize optimized scorer if requested and using Ollama
        self.optimized_scorer = None
        if use_optimized_scorer and judge_model_config.get('model_type', '').lower() == 'ollama':
            self.optimized_scorer = OptimizedOllamaScorer(
                judge_inference=self.judge_inference,
                embedding_model=embedding_model,
                verbose=verbose
            )
        
    def _load_judge_model(self, model_config: dict):
        """Load the appropriate judge model based on configuration."""
        model_type = model_config.get('model_type', '').lower()
        model_name = model_config.get('model_name', '')
        max_new_tokens = model_config.get('max_new_tokens', 512)
        temperature = model_config.get('temperature', 0.1)
        num_ctx = model_config.get('num_ctx', 4096)
        
        if model_type == 'ollama':
            return OllamaInference(
                model_name=model_name,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                num_ctx=num_ctx
            )
        elif model_type == 'openai':
            return OpenAIInference(
                model_name=model_name,
                max_new_tokens=max_new_tokens,
                temperature=temperature
            )
        elif model_type == 'anthropic':
            return AnthropicInference(
                model_name=model_name,
                max_new_tokens=max_new_tokens,
                temperature=temperature
            )
        elif model_type == 'gemini':
            return GeminiInference(
                model_name=model_name,
                max_new_tokens=max_new_tokens,
                temperature=temperature
            )
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
    
    async def run_bulk_judge(
        self, 
        request: BulkJudgeRunRequest,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        job_id: Optional[str] = None
    ) -> BulkJudgeRunResponse:
        """
        Run LLM judge scoring for multiple profiles.
        
        Args:
            request: Bulk judge run request parameters
            progress_callback: Optional callback for progress updates (stage, current, total)
            
        Returns:
            BulkJudgeRunResponse with job details
        """
        if not job_id:
            job_id = str(uuid.uuid4())
        
        # Initialize checkpoint manager if needed
        if self.checkpoint_manager and not job_id:
            # Create or find resumable job
            config = {
                "profile_ids": request.profile_ids,
                "profile_tags": request.profile_tags,
                "from_date": str(request.from_date) if request.from_date else None,
                "to_date": str(request.to_date) if request.to_date else None,
                "batch_size": request.batch_size,
                "overwrite_existing": request.overwrite_existing
            }
            
            resumable_job_id = await self.checkpoint_manager.find_resumable_job("bulk_judge", config)
            if resumable_job_id:
                job_id = str(resumable_job_id)
                if self.verbose:
                    print(f"🔄 Resuming job {job_id}")
                await self.checkpoint_manager.resume_job(resumable_job_id)
            else:
                new_job_id = await self.checkpoint_manager.create_job("bulk_judge", config)
                job_id = str(new_job_id)
        
        if self.verbose:
            print(f"🚀 STARTING BULK LLM JUDGE RUN - Job ID: {job_id}")
            print("="*60)
        
        # Step 1: Resolve target profiles
        target_profiles = self._resolve_target_profiles(request)
        
        if not target_profiles:
            return BulkJudgeRunResponse(
                job_id=job_id,
                status="failed",
                profile_count=0,
                estimated_papers=0,
                message="No profiles found matching the criteria"
            )
        
        if self.verbose:
            profile_names = [p['name'] for p in target_profiles]
            print(f"📋 Target profiles ({len(target_profiles)}): {', '.join(profile_names)}")
        
        # Step 2: Get papers to score
        papers_to_score = self._get_papers_to_score(target_profiles, request)
        
        if not papers_to_score:
            return BulkJudgeRunResponse(
                job_id=job_id,
                status="completed",
                profile_count=len(target_profiles),
                estimated_papers=0,
                message="No papers found in the specified date range"
            )
        
        total_operations = len(target_profiles) * len(papers_to_score)
        
        if self.verbose:
            print(f"📊 Found {len(papers_to_score)} papers to score across {len(target_profiles)} profiles")
            print(f"🎯 Total scoring operations: {total_operations}")
        
        # Check for previous progress
        start_profile_idx = 0
        total_scored = 0
        total_failed = 0
        
        if self.checkpoint_manager and job_id:
            checkpoint = await self.checkpoint_manager.get_latest_checkpoint(
                uuid.UUID(job_id), "profile_progress"
            )
            if checkpoint:
                checkpoint_data = checkpoint['checkpoint_data']
                start_profile_idx = checkpoint_data.get('last_completed_profile_idx', 0) + 1
                total_scored = checkpoint_data.get('total_scored', 0)
                total_failed = checkpoint_data.get('total_failed', 0)
                if self.verbose:
                    print(f"🔄 Resuming from profile {start_profile_idx + 1}/{len(target_profiles)}")
        
        # Step 3: Run scoring for each profile
        for profile_idx in range(start_profile_idx, len(target_profiles)):
            profile = target_profiles[profile_idx]
            if progress_callback:
                progress_callback(f"Scoring profile: {profile['name']}", profile_idx, len(target_profiles))
            
            if self.verbose:
                print(f"\n⚖️ SCORING PROFILE: {profile['name']} ({profile_idx + 1}/{len(target_profiles)})")
                print("-" * 40)
            
            # Get research interests for this profile
            research_interests = ProfileInterestsRepository.get_interests_text_by_profile(profile['id'])
            
            if not research_interests:
                if self.verbose:
                    print(f"⚠️ No research interests found for profile {profile['name']}, skipping")
                continue
            
            # Score papers for this profile
            scored, failed = await self._score_papers_for_profile(
                profile['id'],
                profile['name'],
                research_interests,
                papers_to_score,
                request.batch_size,
                request.overwrite_existing,
                job_id=job_id if self.checkpoint_manager else None
            )
            
            total_scored += scored
            total_failed += failed
            
            # Save checkpoint after each profile
            if self.checkpoint_manager and job_id:
                await self.checkpoint_manager.save_checkpoint(
                    uuid.UUID(job_id),
                    "profile_progress",
                    {
                        "last_completed_profile_idx": profile_idx,
                        "total_scored": total_scored,
                        "total_failed": total_failed,
                        "profile_id": profile['id'],
                        "profile_name": profile['name']
                    },
                    profile_idx + 1
                )
                await self.checkpoint_manager.update_progress(
                    uuid.UUID(job_id), 
                    profile_idx + 1, 
                    len(target_profiles)
                )
        
        if progress_callback:
            progress_callback("Bulk judge run completed", len(target_profiles), len(target_profiles))
        
        if self.verbose:
            print(f"\n🎉 BULK JUDGE RUN COMPLETE!")
            print("="*60)
            print(f"✅ Successfully scored: {total_scored} paper-profile combinations")
            print(f"❌ Failed operations: {total_failed}")
            print(f"📊 Success rate: {(total_scored / (total_scored + total_failed) * 100):.1f}%" if (total_scored + total_failed) > 0 else "100%")
        
        # Mark job as completed
        if self.checkpoint_manager and job_id:
            await self.checkpoint_manager.complete_job(uuid.UUID(job_id))
        
        return BulkJudgeRunResponse(
            job_id=job_id,
            status="completed",
            profile_count=len(target_profiles),
            estimated_papers=len(papers_to_score),
            message=f"Scored {total_scored} paper-profile combinations with {total_failed} failures"
        )
    
    def _resolve_target_profiles(self, request: BulkJudgeRunRequest) -> List[dict]:
        """Resolve which profiles to target based on request criteria."""
        target_profiles = []
        
        # Get profiles by explicit IDs
        if request.profile_ids:
            for profile_id in request.profile_ids:
                profile = ProfileRepository.get_by_id(profile_id)
                if profile and profile['is_active']:
                    target_profiles.append(profile)
                elif self.verbose:
                    print(f"⚠️ Profile ID {profile_id} not found or inactive")
        
        # Get profiles by tags
        if request.profile_tags:
            tag_profiles = ProfileRepository.get_by_tags(request.profile_tags)
            for profile in tag_profiles:
                if profile['is_active'] and profile not in target_profiles:
                    target_profiles.append(profile)
        
        # If no specific criteria, get all active profiles
        if not request.profile_ids and not request.profile_tags:
            target_profiles = ProfileRepository.get_all_active()
        
        return target_profiles
    
    def _get_papers_to_score(
        self, 
        target_profiles: List[dict], 
        request: BulkJudgeRunRequest
    ) -> List[dict]:
        """Get papers that need to be scored based on date range or specific IDs."""
        
        # If specific paper IDs are provided, use those
        if request.paper_ids:
            papers = []
            for paper_id in request.paper_ids:
                paper = PaperRepository.get_by_id(paper_id)
                if paper:
                    papers.append(paper)
            if self.verbose:
                print(f"📋 Using {len(papers)} specific papers from provided IDs")
        else:
            # Otherwise, get all papers in date range
            papers = PaperRepository.get_papers_in_date_range(
                start_date=request.from_date,
                end_date=request.to_date
            )
            if self.verbose:
                print(f"📋 Found {len(papers)} papers in date range")
        
        if not request.overwrite_existing:
            # Filter out papers that already have scores for target profiles
            profile_ids = [p['id'] for p in target_profiles]
            original_count = len(papers)
            papers = [
                paper for paper in papers
                if not ProfileScoreRepository.has_scores_for_profiles(paper['id'], profile_ids)
            ]
            if self.verbose and original_count != len(papers):
                print(f"📝 Filtered to {len(papers)} papers that need scoring (skipped {original_count - len(papers)} already scored)")
        
        return papers
    
    async def _score_papers_for_profile(
        self,
        profile_id: int,
        profile_name: str,
        research_interests: str,
        papers: List[dict],
        batch_size: int,
        overwrite_existing: bool,
        job_id: Optional[str] = None
    ) -> Tuple[int, int]:
        """Score papers for a specific profile."""
        
        # Check for existing progress for this profile
        start_paper_idx = 0
        if self.checkpoint_manager and job_id:
            checkpoint = await self.checkpoint_manager.get_latest_checkpoint(
                uuid.UUID(job_id), f"profile_{profile_id}_progress"
            )
            if checkpoint:
                start_paper_idx = checkpoint['checkpoint_data'].get('last_completed_idx', 0) + 1
                if self.verbose:
                    print(f"🔄 Resuming profile {profile_name} from paper {start_paper_idx + 1}")
        
        # Use optimized scorer if available (TODO: add checkpoint support to optimized scorer)
        if self.optimized_scorer and start_paper_idx == 0:
            scored, failed, stats = self.optimized_scorer.score_papers_for_profile(
                profile_id=profile_id,
                profile_name=profile_name,
                research_interests=research_interests,
                papers=papers,
                overwrite_existing=overwrite_existing,
                use_prefiltering=bool(self.embedding_model),
                prefilter_threshold=0.3
            )
            return scored, failed
        
        # Fall back to original implementation
        scored_count = 0
        failed_count = 0
        consecutive_failures = 0
        
        # Filter papers that already have scores for this profile if not overwriting
        if not overwrite_existing:
            papers_to_score = []
            for paper in papers:
                if not ProfileScoreRepository.has_score_for_profile(paper['id'], profile_id):
                    papers_to_score.append(paper)
            
            if self.verbose and len(papers_to_score) != len(papers):
                skipped = len(papers) - len(papers_to_score)
                print(f"📝 Skipping {skipped} papers that already have scores for this profile")
        else:
            papers_to_score = papers
        
        if not papers_to_score:
            if self.verbose:
                print(f"✅ All papers already scored for profile {profile_name}")
            return 0, 0
        
        if self.verbose:
            print(f"🎯 Scoring {len(papers_to_score)} papers for profile {profile_name}")
            if batch_size > 1:
                print(f"⚡ Using batch database writes with batch size: {batch_size}")
        
        # Collect scores for batch processing
        scores_batch = []
        
        # Process papers in batches with progress tracking
        papers_to_process = papers_to_score[start_paper_idx:]
        with tqdm(papers_to_process, desc=f"Scoring {profile_name}", 
                  initial=start_paper_idx, total=len(papers_to_score),
                  disable=not self.verbose) as pbar:
            for paper in pbar:
                success = False
                attempts = 0
                max_attempts = 3
                
                while not success and attempts < max_attempts:
                    attempts += 1
                    try:
                        # Clear cache on retry if using Ollama and we have consecutive failures
                        if attempts == 2 and consecutive_failures > 2:
                            self._clear_judge_cache()
                        
                        # Score the paper
                        score_data = self._score_single_paper(paper, research_interests)
                        
                        if score_data:
                            # Add to batch instead of immediate write
                            scores_batch.append({
                                'paper_id': paper['id'],
                                'profile_id': profile_id,
                                'score': score_data['score'],
                                'related': score_data['related'],
                                'rationale': score_data['rationale'],
                                'judge_model': self.judge_model_config.get('model_name', 'unknown')
                            })
                            
                            consecutive_failures = 0
                            success = True
                            
                            pbar.set_postfix({
                                'score': score_data['score'],
                                'related': score_data['related'],
                                'failed': failed_count,
                                'batch': len(scores_batch)
                            })
                            
                            # Write batch when it reaches the configured size
                            if len(scores_batch) >= batch_size:
                                successful, failed = ProfileScoreRepository.bulk_create_or_update_scores(scores_batch)
                                scored_count += successful
                                failed_count += failed
                                scores_batch = []  # Clear batch
                                
                                # Save checkpoint periodically
                                if self.checkpoint_manager and job_id and scored_count % 100 == 0:
                                    current_idx = start_paper_idx + papers_to_score.index(paper)
                                    await self.checkpoint_manager.save_checkpoint(
                                        uuid.UUID(job_id),
                                        f"profile_{profile_id}_progress",
                                        {
                                            "last_completed_idx": current_idx,
                                            "scored_count": scored_count,
                                            "failed_count": failed_count
                                        },
                                        current_idx + 1
                                    )
                                
                        else:
                            if attempts >= max_attempts:
                                raise ValueError("Failed to get valid score data")
                        
                    except Exception as e:
                        if attempts >= max_attempts:
                            if self.verbose:
                                pbar.write(f"❌ Failed to score paper '{paper['title'][:50]}...': {str(e)[:50]}")
                            failed_count += 1
                            consecutive_failures += 1
                            success = True  # Exit the retry loop
                        else:
                            time.sleep(1)  # Brief delay before retry
        
        # Write any remaining scores in the batch
        if scores_batch:
            successful, failed = ProfileScoreRepository.bulk_create_or_update_scores(scores_batch)
            scored_count += successful
            failed_count += failed
        
        if self.verbose:
            success_rate = (scored_count / (scored_count + failed_count) * 100) if (scored_count + failed_count) > 0 else 100
            print(f"✅ Profile {profile_name}: {scored_count} scored, {failed_count} failed ({success_rate:.1f}% success)")
        
        return scored_count, failed_count
    
    def _score_single_paper(self, paper: dict, research_interests: str) -> Optional[dict]:
        """Score a single paper against research interests."""
        
        try:
            messages = [
                {"role": "user", "content": research_prompt(research_interests, paper['abstract'])}
            ]
            
            if getattr(self.judge_inference, "provider", "") == "ollama":
                response = self.judge_inference.invoke(
                    messages=messages,
                    system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT,
                    schema=None
                )
            else:
                response = self.judge_inference.invoke(
                    messages=messages,
                    system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT
                )
            
            # Parse JSON response
            try:
                response_json = json_repair.loads(response)
                
                # Ensure response_json is a dictionary
                if not isinstance(response_json, dict):
                    if self.verbose:
                        print(f"⚠️ Expected dict from JSON parsing, got {type(response_json)}")
                        print(f"Raw response: {response[:200]}...")
                    return None
                    
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ JSON parsing failed: {e}")
                    print(f"Raw response: {response[:200]}...")
                return None
            
            # Validate required fields
            required_keys = ['score', 'related', 'rationale']
            if not all(key in response_json for key in required_keys):
                if self.verbose:
                    print(f"⚠️ Missing required keys in response: {response_json}")
                return None
            
            # Validate and convert values
            score_val = int(response_json['score'])
            related_val = bool(response_json['related'])
            rationale_val = str(response_json['rationale'])
            
            # Validate score range
            if not (1 <= score_val <= 10):
                score_val = max(1, min(10, score_val))  # Clamp to valid range
            
            return {
                'score': score_val,
                'related': related_val,
                'rationale': rationale_val
            }
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error scoring paper: {e}")
            return None
    
    def _clear_judge_cache(self):
        """Clear Ollama cache if using Ollama judge model."""
        try:
            if (hasattr(self.judge_inference, 'provider') and 
                self.judge_inference.provider == "ollama"):
                from ..utils import purge_ollama_cache
                import os
                ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
                model_name = self.judge_model_config.get('model_name')
                if model_name:
                    if self.verbose:
                        print(f"🧹 Clearing Ollama cache for {model_name}")
                    purge_ollama_cache(ollama_url, model_name)
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Failed to clear judge cache: {e}")


async def create_bulk_judge_runner(
    orchestration_config: dict, 
    verbose: bool = True,
    checkpoint_manager: Optional[CheckpointManager] = None
) -> BulkJudgeRunner:
    """Factory function to create a BulkJudgeRunner from orchestration config."""
    judge_config = orchestration_config.get('judge_model', {})
    
    # Initialize checkpoint manager if not provided
    if checkpoint_manager is None:
        checkpoint_manager = CheckpointManager()
        await checkpoint_manager.initialize()
    
    return BulkJudgeRunner(judge_config, verbose, checkpoint_manager=checkpoint_manager) 