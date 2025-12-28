#!/usr/bin/env python3
"""Debug script to test worker functionality step by step."""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from theseus_insight.data_access.worker_heartbeats import WorkerHeartbeatsRepository
from theseus_insight.data_access.judge_task_queue import JudgeTaskQueueRepository

async def test_worker_operations():
    """Test worker operations step by step."""
    print("🔧 Testing worker operations...")
    
    job_id = UUID('f9512b12-f93b-4a40-8810-94a46eddd468')
    server_url = 'http://localhost:11434'
    worker_id = 'debug-worker-test'
    
    try:
        print("1. Testing heartbeat with asyncio.to_thread...")
        await asyncio.to_thread(
            WorkerHeartbeatsRepository.upsert_heartbeat,
            worker_id=worker_id,
            server_url=server_url,
            job_id=job_id,
            status='active',
            tasks_processed=0
        )
        print("✅ Heartbeat successful")
        
        print("2. Testing task lease with asyncio.to_thread...")
        task = await asyncio.to_thread(
            JudgeTaskQueueRepository.lease_next_task,
            server_url=server_url,
            worker_id=worker_id
        )
        
        if task:
            print(f"✅ Task leased: {task.id} (paper {task.paper_id}, profile {task.profile_id})")
            
            print("3. Testing task completion...")
            await asyncio.to_thread(
                JudgeTaskQueueRepository.mark_task_completed,
                task.id
            )
            print("✅ Task marked as completed")
        else:
            print("❌ No task available to lease")
            
        print("4. Testing worker cleanup...")
        await asyncio.to_thread(
            WorkerHeartbeatsRepository.mark_worker_inactive,
            worker_id=worker_id,
            server_url=server_url,
            job_id=job_id
        )
        print("✅ Worker marked as inactive")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_worker_operations())
