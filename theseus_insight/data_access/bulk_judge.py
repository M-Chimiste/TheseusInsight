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

from ..inference.llm import OllamaInference, OpenAIInference, AnthropicInference, GeminiInference
from ..prompt import RESEARCH_INTERESTS_SYSTEM_PROMPT, research_prompt
from .profiles import ProfileRepository, ProfileInterestsRepository, ProfileScoreRepository
from .papers import PaperRepository
from ..api.models import BulkJudgeRunRequest, BulkJudgeRunResponse


class BulkJudgeRunner:
    """Service for running LLM judge scoring across multiple profiles."""
    
    def __init__(self, judge_model_config: dict, verbose: bool = True):
        """Initialize the bulk judge runner with model configuration."""
        self.judge_model_config = judge_model_config
        self.verbose = verbose
        self.judge_inference = self._load_judge_model(judge_model_config)
        
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
    
    def run_bulk_judge(
        self, 
        request: BulkJudgeRunRequest,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> BulkJudgeRunResponse:
        """
        Run LLM judge scoring for multiple profiles.
        
        Args:
            request: Bulk judge run request parameters
            progress_callback: Optional callback for progress updates (stage, current, total)
            
        Returns:
            BulkJudgeRunResponse with job details
        """
        job_id = str(uuid.uuid4())
        
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
        
        # Step 3: Run scoring for each profile
        total_scored = 0
        total_failed = 0
        
        for profile_idx, profile in enumerate(target_profiles):
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
            scored, failed = self._score_papers_for_profile(
                profile['id'],
                profile['name'],
                research_interests,
                papers_to_score,
                request.batch_size,
                request.overwrite_existing
            )
            
            total_scored += scored
            total_failed += failed
        
        if progress_callback:
            progress_callback("Bulk judge run completed", len(target_profiles), len(target_profiles))
        
        if self.verbose:
            print(f"\n🎉 BULK JUDGE RUN COMPLETE!")
            print("="*60)
            print(f"✅ Successfully scored: {total_scored} paper-profile combinations")
            print(f"❌ Failed operations: {total_failed}")
            print(f"📊 Success rate: {(total_scored / (total_scored + total_failed) * 100):.1f}%" if (total_scored + total_failed) > 0 else "100%")
        
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
        """Get papers that need to be scored based on date range and existing scores."""
        
        # Get all papers in date range
        papers = PaperRepository.get_papers_in_date_range(
            start_date=request.from_date,
            end_date=request.to_date
        )
        
        if not request.overwrite_existing:
            # Filter out papers that already have scores for target profiles
            profile_ids = [p['id'] for p in target_profiles]
            papers = [
                paper for paper in papers
                if not ProfileScoreRepository.has_scores_for_profiles(paper['id'], profile_ids)
            ]
        
        return papers
    
    def _score_papers_for_profile(
        self,
        profile_id: int,
        profile_name: str,
        research_interests: str,
        papers: List[dict],
        batch_size: int,
        overwrite_existing: bool
    ) -> Tuple[int, int]:
        """Score papers for a specific profile."""
        
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
        
        # Process papers in batches with progress tracking
        with tqdm(papers_to_score, desc=f"Scoring {profile_name}", disable=not self.verbose) as pbar:
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
                            # Store the score
                            ProfileScoreRepository.create_or_update_score(
                                paper_id=paper['id'],
                                profile_id=profile_id,
                                score=score_data['score'],
                                related=score_data['related'],
                                rationale=score_data['rationale'],
                                judge_model=self.judge_model_config.get('model_name', 'unknown')
                            )
                            
                            scored_count += 1
                            consecutive_failures = 0
                            success = True
                            
                            pbar.set_postfix({
                                'score': score_data['score'],
                                'related': score_data['related'],
                                'failed': failed_count
                            })
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
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ JSON parsing failed: {e}")
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


def create_bulk_judge_runner(orchestration_config: dict, verbose: bool = True) -> BulkJudgeRunner:
    """Factory function to create a BulkJudgeRunner from orchestration config."""
    judge_config = orchestration_config.get('judge_model', {})
    return BulkJudgeRunner(judge_config, verbose) 