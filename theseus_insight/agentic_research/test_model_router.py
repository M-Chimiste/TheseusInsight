import json
from .model_router import (
    AgentModelRouter, 
    ResearchAgentModelConfig, 
    ModelRole, 
    load_research_agent_model_config
)
from ..data_model.data_handling import PaperDatabase


def test_model_router():
    """Test the model router functionality."""
    
    # Initialize database
    db = PaperDatabase("data/theseus.db")
    
    print("🔧 Testing Research Agent Model Router")
    print("=" * 50)
    
    # Test 1: Load default configuration
    print("\n1. Loading default model configuration...")
    config = load_research_agent_model_config(db)
    print(f"   ✓ Boss model: {config.boss_model.model_name} ({config.boss_model.model_type})")
    print(f"   ✓ Worker models: {list(config.worker_models.keys())}")
    print(f"   ✓ Default worker: {config.default_worker}")
    
    # Test 2: Initialize router
    print("\n2. Initializing model router...")
    router = AgentModelRouter(db, config)
    print(f"   ✓ Router initialized with {len(router.get_available_models())} models")
    
    # Test 3: Test model selection
    print("\n3. Testing dynamic model selection...")
    test_tasks = ["summary", "analysis", "search", "unknown_task"]
    for task in test_tasks:
        selected_role = router.select_worker_model(task)
        model_config = config.get_model_for_role(selected_role)
        print(f"   ✓ Task '{task}' -> {selected_role.value} -> {model_config.model_name}")
    
    # Test 4: Test configuration serialization
    print("\n4. Testing configuration serialization...")
    config_dict = config.to_dict()
    print(f"   ✓ Config serialized: {len(json.dumps(config_dict))} bytes")
    
    # Recreate from dict
    config2 = ResearchAgentModelConfig(config_dict)
    print(f"   ✓ Config recreated: boss={config2.boss_model.model_name}")
    
    # Test 5: Test trace logging (without actual model invocation)
    print("\n5. Testing trace logging...")
    print(f"   ✓ Current trace entries: {len(router.get_trace_log())}")
    
    # Test mock invocation logging
    router._log_invocation(
        config.boss_model, 
        ModelRole.BOSS, 
        "test_task", 
        duration_ms=123.45, 
        success=True
    )
    
    trace_log = router.get_trace_log()
    print(f"   ✓ After mock invocation: {len(trace_log)} entries")
    if trace_log:
        latest = trace_log[-1]
        print(f"      - Model: {latest['model_name']}")
        print(f"      - Role: {latest['model_role']}")  
        print(f"      - Duration: {latest['duration_ms']}ms")
    
    print("\n✅ All model router tests passed!")
    print("\nModel Router Configuration:")
    print(json.dumps(config.to_dict(), indent=2))


if __name__ == "__main__":
    test_model_router() 