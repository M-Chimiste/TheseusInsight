#!/usr/bin/env python3
"""Minimal worker to test the main loop."""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

from ..data_access.worker_heartbeats import WorkerHeartbeatsRepository
from ..data_access.judge_task_queue import JudgeTaskQueueRepository

class MinimalWorker:
    def __init__(self, server_url: str, job_id: UUID):
        self.server_url = server_url
        self.job_id = job_id
        self.worker_id = f"minimal_worker_{server_url.split('//')[1].replace(':', '_').replace('.', '_')}"
        self.running = True
        self.tasks_processed = 0

    async def start(self):
        """Start the minimal worker."""
        print(f"🚀 Starting minimal worker {self.worker_id}")
        
        # Simple loop - just send heartbeats and try to lease tasks
        for i in range(3):  # Run for 3 iterations
            try:
                print(f"📡 Iteration {i+1}: Sending heartbeat...")
                await asyncio.to_thread(
                    WorkerHeartbeatsRepository.upsert_heartbeat,
                    worker_id=self.worker_id,
                    server_url=self.server_url,
                    job_id=self.job_id,
                    status='active',
                    tasks_processed=self.tasks_processed
                )
                print("✅ Heartbeat sent")
                
                print("🔍 Trying to lease a task...")
                task = await asyncio.to_thread(
                    JudgeTaskQueueRepository.lease_next_task,
                    server_url=self.server_url,
                    worker_id=self.worker_id
                )
                
                if task:
                    print(f"✅ Leased task {task.id} (paper {task.paper_id}, profile {task.profile_id})")
                    
                    # Just mark it as completed for testing
                    await asyncio.to_thread(
                        JudgeTaskQueueRepository.mark_task_completed,
                        task.id
                    )
                    self.tasks_processed += 1
                    print(f"✅ Completed task {task.id}")
                else:
                    print("❌ No tasks available")
                
                await asyncio.sleep(5)  # Wait 5 seconds between iterations
                
            except Exception as e:
                print(f"❌ Error in iteration {i+1}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"🏁 Minimal worker {self.worker_id} finished. Processed {self.tasks_processed} tasks.")

async def main():
    job_id = UUID('f9512b12-f93b-4a40-8810-94a46eddd468')
    server_url = 'http://localhost:11434'
    
    worker = MinimalWorker(server_url, job_id)
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())

