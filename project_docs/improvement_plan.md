# TheseusInsight Multi-Agent Research Architecture Improvement Plan

## Executive Summary

This improvement plan outlines the comprehensive refactoring of TheseusInsight's research agent system from a single LangGraph workflow to a dual-mode architecture supporting both single agent and multi-agent "heavy" orchestration, following the make-it-heavy methodology while preserving existing search infrastructure and research library functionality.

**Target Outcome**: A sophisticated research system that can operate in two modes:
1. **Single Agent Mode**: Current workflow-based approach for focused research
2. **Multi-Agent Mode**: Parallel orchestration of specialized agents for comprehensive, multi-perspective analysis

## Current State Analysis

### Existing Architecture
- **Research Flow**: Sequential LangGraph workflow (query generation → local research → external research → reflection → evaluation → finalize)
- **Frontend**: Single conversation interface with WebSocket progress updates
- **Backend**: ResearchAgentWorkflow with predefined node structure
- **Search Integration**: LocalSearchTool (SQL database) and ExternalSearchTool (arXiv API)
- **Data Storage**: Detailed research results saved to research_runs table

### Limitations Identified
- Single-threaded research approach limits comprehensive analysis
- No multi-perspective evaluation of research questions
- Limited parallel processing capabilities
- Static workflow structure without dynamic question decomposition

## Target Architecture (Make-It-Heavy Inspired)

### Core Principles
1. **Dual-Mode Operation**: Toggle between single and multi-agent approaches
2. **Dynamic Question Generation**: AI creates specialized research questions from user input
3. **Parallel Agent Execution**: Multiple agents work simultaneously with different analytical perspectives
4. **Intelligent Synthesis**: AI combines multiple agent responses into comprehensive answers
5. **Real-Time Orchestration**: Live visual feedback during multi-agent execution
6. **Preserve Existing Tools**: Maintain current search infrastructure and data storage

### Multi-Agent Workflow
```
User Query → Question Generation Agent → Parallel Agent Execution → Synthesis Agent → Final Answer
     ↓                    ↓                         ↓                      ↓             ↓
Single Mode         4-6 Specialized           Research Agent         Response        Comprehensive
Research            Questions                Analysis Agent         Combination      Research Report
                                            Verification Agent
                                            Alternative Agent
```

## Implementation Plan

### Phase 1: Backend Architecture Foundation (Weeks 1-2)

#### 1.1 Multi-Agent Orchestration System
**Location**: `theseus_insight/research_agent/`

**New Components**:
- **`orchestrator.py`**: Main orchestration class managing parallel agent execution
  - Task decomposition and assignment
  - Agent lifecycle management
  - Progress tracking and synchronization
  - Error handling and recovery

- **`agent_manager.py`**: Individual agent management
  - Agent initialization and configuration
  - Resource allocation and cleanup
  - Status monitoring and reporting

- **`question_generator.py`**: AI-powered question decomposition
  - Dynamic question generation from user research topics
  - Question specialization for different analytical perspectives
  - Adaptive question count based on complexity

- **`synthesis_agent.py`**: Response combination engine
  - Multi-perspective analysis integration
  - Conflict resolution between agent responses
  - Comprehensive answer generation with citations

- **`agent_types.py`**: Agent specialization definitions
  - Research Agent: Comprehensive information gathering
  - Analysis Agent: Deep analytical insights
  - Verification Agent: Fact-checking and validation
  - Alternative Agent: Contrarian and alternative perspectives

#### 1.2 Configuration Management System
**Location**: `theseus_insight/data_access/settings.py`

**Database Settings Schema**:
```json
{
  "research_agent_mode": "single|multi",
  "single_agent_config": {
    "model_config": {
      "boss_model": { "model_type": "openai", "model_name": "gpt-4" },
      "query_planner_model": { /* inherits from boss */ },
      "evidence_selector_model": { /* inherits from boss */ },
      "compression_model": { /* inherits from boss */ },
      "answer_generator_model": { /* inherits from boss */ }
    },
    "max_research_loops": 3,
    "max_research_context_tokens": 15000,
    "compress_to_ratio": 0.2,
    "search_config": {
      "local_limit": 20,
      "external_limit": 15
    }
  },
  "multi_agent_config": {
    "parallel_agents": 4,
    "task_timeout": 300,
    "boss_model": { "model_type": "openai", "model_name": "gpt-4" },
    "specialized_models": {
      "question_generator": { /* model config */ },
      "research_agent": { /* model config */ },
      "analysis_agent": { /* model config */ },
      "verification_agent": { /* model config */ },
      "synthesis_agent": { /* model config */ }
    },
    "search_config": {
      "local_limit": 25,
      "external_limit": 20
    },
    "synthesis_config": {
      "conflict_resolution": "weighted_consensus",
      "citation_strategy": "comprehensive"
    }
  }
}
```

### Phase 2: API and Database Updates (Week 3)

#### 2.1 Research Agent API Modifications
**Location**: `theseus_insight/api/routers/research_agent.py`

**API Changes**:
- **Request Model Updates**:
  ```python
  class ResearchTaskRequest(BaseModel):
      research_question: str
      mode: Literal["single", "multi"] = "single"
      config: Optional[Dict[str, Any]] = None
      save_to_library: bool = True
  ```

- **New Endpoints**:
  - `GET /api/research-agent/modes` - Available modes and configurations
  - `PUT /api/research-agent/mode` - Switch between single and multi-agent mode
  - `GET /api/research-agent/config/{mode}` - Get mode-specific configuration

- **Enhanced Progress Tracking**:
  ```python
  class MultiAgentProgress(BaseModel):
      agents: List[AgentStatus]
      synthesis_status: Optional[str]
      overall_progress: float
      estimated_completion: Optional[datetime]
  ```

#### 2.2 Database Schema Evolution
**Location**: `scripts/` (new migration: `007_multi_agent_support.sql`)

**Research Runs Table Updates**:
```sql
ALTER TABLE research_runs ADD COLUMN agent_mode VARCHAR(10) DEFAULT 'single';
ALTER TABLE research_runs ADD COLUMN agent_questions JSONB; -- Generated questions per agent
ALTER TABLE research_runs ADD COLUMN agent_results JSONB; -- Individual agent responses
ALTER TABLE research_runs ADD COLUMN synthesis_process JSONB; -- Synthesis methodology and conflicts
ALTER TABLE research_runs ADD COLUMN parallel_execution_stats JSONB; -- Performance metrics
ALTER TABLE research_runs ADD COLUMN agent_specializations JSONB; -- Agent type assignments
```

**Export/Import Updates**:
- **`db_export.py`**: Enhanced to handle multi-agent results
- **`db_import.py`**: Version checking to ignore incompatible legacy data
- **Migration Utility**: Convert single-agent historical data where possible

### Phase 3: Frontend Transformation (Week 4)

#### 3.1 Settings UI Enhancement
**Location**: `theseus-ui/src/pages/Settings.tsx`

**New Configuration Sections**:
- **Research Agent Mode Toggle**: 
  - Radio buttons for Single/Multi mode selection
  - Mode-specific configuration panels that show/hide based on selection

- **Single Agent Configuration Panel** (existing, reorganized):
  - Model assignments for each workflow node
  - Search limits and research parameters
  - Context and compression settings

- **Multi-Agent Configuration Panel** (new):
  - Number of parallel agents (2-6 slider)
  - Task timeout configuration
  - Boss model selection (inherits to all agents unless overridden)
  - Specialized agent model assignments
  - Search limits per agent
  - Synthesis strategy selection

#### 3.2 Research Agent UI Redesign
**Location**: `theseus-ui/src/pages/ResearchAgent.tsx`

**UI Transformation**:
Replace chat interface with orchestration dashboard:

**New Components**:
- **`AgentProgressBar.tsx`**: Individual agent status with animated progress
  ```typescript
  interface AgentProgressProps {
    agentId: number;
    agentType: string;
    status: 'queued' | 'initializing' | 'processing' | 'completed' | 'failed';
    currentQuestion: string;
    progress: number;
    executionTime?: number;
  }
  ```

- **`OrchestrationDashboard.tsx`**: Overall multi-agent coordination view
  - Real-time agent status grid
  - Overall progress indicator
  - Time elapsed and estimated completion
  - Cancel/pause controls

- **`QuestionDecomposition.tsx`**: Show generated research questions
  - Visual mapping of questions to agents
  - Question complexity indicators
  - Agent specialization assignments

- **`SynthesisView.tsx`**: Final answer assembly process
  - Response combination visualization
  - Conflict identification and resolution
  - Citation mapping and verification

**Progress Monitoring Interface**:
```typescript
interface MultiAgentUI {
  header: {
    title: "RESEARCH HEAVY" | "SINGLE AGENT";
    elapsed_time: string;
    status: "RUNNING" | "COMPLETED" | "FAILED";
  };
  agents: Array<{
    id: number;
    type: string;
    progress_bar: React.Component;
    current_task: string;
  }>;
  synthesis: {
    status: "PENDING" | "PROCESSING" | "COMPLETED";
    progress: number;
  };
}
```

### Phase 4: Integration and Validation (Week 5)

#### 4.1 WebSocket Protocol Updates
**Location**: `theseus_insight/api/routers/websockets.py`

**Enhanced Message Types**:
```typescript
interface MultiAgentProgressMessage {
  type: 'multi_agent_progress';
  task_id: string;
  mode: 'single' | 'multi';
  agents: Array<{
    agent_id: number;
    agent_type: string;
    status: 'queued' | 'initializing' | 'processing' | 'completed' | 'failed';
    current_question: string;
    progress: number;
    execution_time?: number;
    sources_found?: number;
  }>;
  synthesis_status?: 'pending' | 'processing' | 'completed';
  overall_progress: number;
  estimated_completion?: string;
}

interface QuestionGenerationMessage {
  type: 'questions_generated';
  task_id: string;
  questions: Array<{
    agent_id: number;
    question: string;
    specialization: string;
  }>;
}

interface SynthesisMessage {
  type: 'synthesis_progress';
  task_id: string;
  phase: 'conflict_detection' | 'resolution' | 'integration' | 'citation';
  progress: number;
  conflicts_found?: number;
}
```

#### 4.2 Testing and Validation Strategy

**Unit Testing**:
- Multi-agent orchestration logic
- Question generation quality and diversity
- Synthesis algorithm accuracy
- Configuration management

**Integration Testing**:
- End-to-end single mode workflow
- End-to-end multi-agent orchestration
- WebSocket message flow
- Database migration and export/import

**Performance Testing**:
- Parallel agent execution efficiency
- Resource utilization during multi-agent mode
- WebSocket message throughput
- Database query optimization

**User Acceptance Testing**:
- Mode switching functionality
- Configuration UI usability
- Progress monitoring clarity
- Result quality comparison (single vs multi)

## Success Criteria

### Functional Requirements ✅
- [x] Toggle between single and multi-agent modes
- [x] Multi-agent orchestration with 2-6 parallel agents
- [x] Dynamic question generation based on research topic
- [x] Real-time progress monitoring with visual feedback
- [x] Comprehensive result synthesis from multiple perspectives
- [x] Maintained research library functionality with enhanced detail capture
- [x] Backward compatibility for existing search infrastructure

### Technical Requirements ✅
- [x] Efficient parallel execution without resource conflicts
- [x] Robust error handling and recovery mechanisms
- [x] Clean data migration with legacy data handling
- [x] WebSocket protocol supporting real-time multi-agent updates
- [x] Configuration system supporting both modes with model routing

### User Experience Requirements ✅
- [x] Intuitive mode selection and configuration in Settings
- [x] Clear visualization of multi-agent progress with make-it-heavy style interface
- [x] Enhanced research quality through multi-perspective analysis
- [x] Maintained or improved performance standards
- [x] Seamless transition between single and multi-agent modes

## Risk Assessment and Mitigation

### Technical Risks
1. **Parallel Execution Complexity**: Risk of race conditions and resource conflicts
   - *Mitigation*: Careful agent isolation and resource management
   
2. **WebSocket Message Volume**: High message frequency during multi-agent execution
   - *Mitigation*: Message batching and intelligent update throttling
   
3. **Model Cost Scaling**: Multiple agents may increase LLM API costs
   - *Mitigation*: Configurable timeouts and agent limits

### Data Migration Risks
1. **Schema Compatibility**: New columns may conflict with existing data
   - *Mitigation*: Careful migration testing and rollback procedures
   
2. **Export/Import Breaking Changes**: Historical exports may become incompatible
   - *Mitigation*: Version checking and graceful degradation

## Implementation Timeline

| Week | Phase | Key Deliverables |
|------|-------|------------------|
| 1-2 | Backend Foundation | Multi-agent orchestration system, Configuration management |
| 3 | API/Database | Enhanced endpoints, Database migration, Export/import updates |
| 4 | Frontend | Settings UI updates, Research agent redesign, New components |
| 5 | Integration | WebSocket updates, Testing, Performance optimization |

## Conclusion

This improvement plan transforms TheseusInsight into a cutting-edge research platform capable of both focused single-agent research and comprehensive multi-agent analysis. By adopting the make-it-heavy methodology while preserving our existing infrastructure, we achieve:

1. **Enhanced Research Quality**: Multi-perspective analysis provides more comprehensive and nuanced research results
2. **Flexible Operation**: Users can choose the appropriate mode based on their research complexity needs
3. **Scalable Architecture**: Framework supports future expansion with additional agent types and specializations
4. **Preserved Investment**: Existing search tools, data storage, and user research libraries remain fully functional

The implementation prioritizes incremental delivery, thorough testing, and user experience continuity throughout the transformation process.
