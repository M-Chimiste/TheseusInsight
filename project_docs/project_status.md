# Project Status - Theseus Insight

## Recently Completed (Latest Session)

### Mind-Map Progress Tracking & Async/Sync Deadlock Resolution (CRITICAL FIX)
- **Issue Identified**: Mind-map generation was freezing due to async/sync race conditions and deadlocks
- **Root Cause**: Mixed async/sync contexts in LangGraph workflow causing event loop conflicts
- **Solution**: Restored fully synchronous workflow for local LLM resource management
- **Hardware Consideration**: Local LLM models require synchronous calls to prevent hardware overload

#### Key Fixes Implemented:
1. **Synchronous Workflow Architecture**:
   - Restored `generate_mindmap_sync` with proper sync workflow
   - All progress callbacks are purely synchronous (no async/await mixing)
   - LangGraph sync workflow with `sync_app.invoke()` instead of `async_app.ainvoke()`

2. **Frontend Race Condition Fix**:
   - Removed `settings` dependency from useEffect to prevent duplicate API calls
   - Fixed parameter flow from UI settings to backend (expansion_order issue)
   - Added comprehensive debug logging for parameter tracking

3. **Progress Callback Architecture**:
   - Synchronous progress callbacks throughout the workflow
   - Granular progress updates during summarization phase
   - Proper timeout handling (increased to 30 seconds)

4. **Local Hardware Optimization**:
   - **Synchronous LLM calls prevent concurrent resource conflicts**
   - Sequential processing protects local GPU/CPU from overload
   - Batch processing with progress tracking for large paper sets

#### Technical Details:
- **LLM Inference**: Already synchronous (`invoke()` methods, not async)
- **Workflow Nodes**: All sync progress wrappers (`_*_with_sync_progress`)
- **State Management**: LangGraph StateGraph with sync compilation
- **Progress Updates**: Direct sync callback execution without event loop scheduling

### Mind-Map Progress Tracking Investigation & Enhancement (Previous)
- **Progress Callback Issue Analysis**: Investigated why percentage callbacks weren't registering in the UI during mind-map generation
- **Root Cause Identified**: Progress callbacks were working correctly for workflow steps but lacked granular tracking during summary generation
- **Enhanced Summary Progress**: Added fine-grained progress updates during the summarization phase
- **Improved UX**: Users now see real-time progress updates throughout the entire mind-map generation process

#### Key Findings & Fixes:
1. **Progress Flow Analysis**:
   - Frontend (`useMindMap.ts`): Correctly handles WebSocket messages with `message.overallStatus` and `message.progress`
   - Backend WebSocket (`websockets.py`): Properly forwards `RunStatus` objects from TaskManager
   - TaskManager (`tasks.py`): Uses correct `asyncio.run_coroutine_threadsafe()` approach for sync callbacks
   - Workflow (`workflow.py`): Has comprehensive progress tracking at each major step

2. **Summarization Enhancement**:
   - Added granular progress callbacks within `SummariserNode._generate_batch_summaries()`
   - Progress now updates for each individual paper summary (within 60-75% range)
   - Enhanced logging to track individual summary generation steps
   - Passed sync progress callback from workflow to summariser node

3. **Technical Implementation**:
   - Fixed potential async/sync context issues with proper coroutine scheduling
   - Added detailed progress messages showing paper titles during summarization
   - Enhanced error handling for progress callback failures
   - Maintained backwards compatibility with existing progress tracking

#### Progress Tracking Flow:
```
Frontend UI → WebSocket → TaskManager → Workflow → Individual Nodes
    ↑                                                      ↓
Progress Bar ← RunStatus ← update_task_status ← sync_progress_callback
```

#### Detailed Progress Phases:
- **10-20%**: Select seed paper from database
- **20-35%**: Embed seed paper for similarity search
- **35-50%**: Find similar papers (single or multi-order expansion)
- **60-75%**: Generate LLM summaries (now with granular per-paper progress)
- **75-90%**: Build mind-map with layout positioning
- **90-100%**: Finalize and send results

### Database Migration System Update (New)
- **Comprehensive Migration Overhaul**: Extended DB migration system to support all new MindMap and Research Agent tables
- **Backwards Compatibility**: Maintained full backwards compatibility with older database exports
- **New Table Support**: Added export/import for 5 new table types:
  - `research_runs` - Research Agent execution history
  - `research_agent_state` - Research Agent state snapshots
  - `paper_fulltext` - Full-text content for papers (MindMap feature)
  - `mindmap_reports` - Saved MindMap reports
  - `model_catalog` - Model configuration catalog
- **Enhanced CLI**: Updated command-line interface with `--exclude-new-tables` option for backwards compatibility
- **Automatic Detection**: Import system automatically detects and handles new table data when present
- **Comprehensive Verification**: Enhanced migration verification to check all table types

#### Key Migration Features:
1. **Export System Enhancements**:
   - Export version bumped to 2.0 with backwards compatibility metadata
   - Selective table inclusion/exclusion via `include_new_tables` parameter
   - Proper handling of binary embedding data (numpy array to bytes conversion)
   - Enhanced progress tracking for new table exports
   - Graceful error handling for missing tables

2. **Import System Enhancements**:
   - Auto-detection of export version and available features
   - Intelligent handling of missing tables (optional vs required)
   - Proper embedding reconstruction from binary data
   - Enhanced duplicate detection for all table types
   - Comprehensive import statistics and error reporting

3. **Migration Orchestration**:
   - Updated `DatabaseMigrator` class to support new table parameters
   - Enhanced verification system checking all available tables
   - Improved error messages and progress reporting
   - Command-line interface for export/import/migrate operations

4. **Documentation & Examples**:
   - Updated migration example script with comprehensive demonstrations
   - Clear documentation of backwards compatibility features
   - Usage examples for all new migration capabilities

### Multi-Order Mind-Map Expansion & Saving Functionality
- **Frontend Complete**: Implemented comprehensive multi-order mind-map expansion with saving capability
- **Settings Integration**: Added multi-order parameters to Settings.tsx mind-map configuration
- **New Page**: Created MindMapReports.tsx page for managing saved mind-map reports
- **Enhanced UI**: Updated MindMapExplorer with save dialog, multi-order settings, and improved controls
- **API Layer**: Extended all mind-map APIs and interfaces to support new parameters and report management
- **Navigation**: Added Mind-Map Reports to main navigation menu

#### Key Features Implemented:
1. **Multi-Order Expansion**:
   - Expansion Order setting (1-5 levels)
   - Max Nodes per Order setting (5-50 nodes)
   - Exponential growth control to prevent overwhelming graphs
   - Both global settings and per-generation overrides

2. **Mind-Map Report Saving**:
   - Required title with optional description
   - Complete mind-map data persistence
   - Generation parameters tracking
   - Statistics and metadata storage

3. **Report Management Page**:
   - Card-based layout showing all saved reports
   - View, edit titles, and delete functionality
   - Metadata display (nodes, edges, expansion order)
   - Direct loading of saved mind-maps

4. **Enhanced User Experience**:
   - Save button in mind-map explorer
   - Validation for required fields
   - Success/error feedback
   - Consistent design patterns

#### Backend Status:
- ✅ **Database schema**: mindmap_reports table created with complete schema
- ✅ **Database CRUD methods**: All report management methods implemented
- ✅ **Multi-order expansion workflow logic**: Implemented with conditional routing
- ✅ **Progress tracking for iterative generation**: Implemented with specialized progress callbacks

## Previously Completed Features

### Core Infrastructure
- **Database Integration**: SQLite with comprehensive paper storage and metadata
- **API Architecture**: FastAPI backend with RESTful endpoints and WebSocket support
- **Frontend Framework**: React with TypeScript, Material-UI, and React Query
- **Authentication**: API key management for multiple LLM providers

### Research & Analysis Pipeline
- **ArXiv Integration**: Automated paper harvesting with taxonomy filtering
- **Embedding System**: Vector similarity search with multiple embedding models
- **LLM Integration**: Multi-provider support (OpenAI, Anthropic, Ollama, Gemini)
- **Research Agent**: Automated literature review with multi-step reasoning
- **Hybrid Search**: Combined keyword and semantic search capabilities

### Content Generation
- **Newsletter Builder**: Automated newsletter generation with email distribution
- **Podcast Creator**: Text-to-speech podcast generation with multiple voices
- **Visualizer**: Matrix-style video generation for podcast content

### User Interface
- **Papers Management**: Advanced filtering, pagination, and similarity search
- **Model Catalog**: Centralized model configuration and management
- **Research Library**: Literature review results management
- **Run History**: Task tracking and status monitoring
- **Settings**: Comprehensive configuration management

### Mind-Map Explorer (Core)
- **Interactive Visualization**: React Flow-based mind-map rendering
- **Smart Layouts**: Force-directed positioning with collision detection
- **Paper Summarization**: LLM-generated summaries for each node
- **Similarity Connections**: Edge weights based on semantic similarity
- **Real-time Generation**: WebSocket progress tracking

### Database Migration & Data Management
- **Comprehensive Migration System**: Full export/import of all table types
- **Backwards Compatibility**: Support for older database formats
- **Verification System**: Migration integrity checking
- **Command-Line Tools**: CLI interface for database operations
- **Data Preservation**: Safe handling of binary data and embeddings

## Current Architecture

### Backend Stack
- **Framework**: FastAPI with async/await support
- **Database**: SQLite with custom ORM layer and comprehensive migration support
- **Task Management**: Background task system with WebSocket notifications
- **LLM Integration**: Provider-agnostic model configuration
- **Vector Search**: Embedding-based similarity computation
- **Migration System**: Full database export/import with backwards compatibility

### Frontend Stack
- **Framework**: React 18 with TypeScript
- **UI Library**: Material-UI (MUI) v5
- **State Management**: React Query for server state, Context for UI state
- **Routing**: React Router v6
- **Visualization**: React Flow for mind-maps, custom components for other visualizations

### Key Dependencies
- **LangGraph**: Workflow orchestration for complex AI tasks
- **Sentence Transformers**: Embedding generation
- **OpenAI/Anthropic SDKs**: LLM API integration
- **React Flow**: Interactive graph visualization
- **TanStack Query**: Data fetching and caching
- **NumPy**: Binary data handling for embeddings

## Development Notes

### Code Quality Practices
- TypeScript for type safety across frontend and backend
- Comprehensive error handling with user-friendly messages
- Responsive design with mobile-first approach
- Performance optimizations with lazy loading and infinite scroll
- Consistent naming conventions and code organization

### Scalability Considerations
- Modular architecture allowing easy feature additions
- Provider-agnostic LLM integration for flexibility
- Efficient database queries with proper indexing
- Background task processing to avoid UI blocking
- Component reusability across different pages
- Robust migration system for database evolution

### Recent Technical Decisions
- Multi-order expansion with configurable limits to balance utility and performance
- Report saving system for persistent mind-map exploration
- Enhanced settings organization for better user experience
- Consistent UI patterns across all management pages
- Backwards-compatible migration system for seamless upgrades

## Next Priorities

### Immediate Focus
1. **Testing**: Comprehensive testing of new migration system with real data
2. **Documentation**: Update user documentation for migration capabilities
3. **Performance**: Optimization for large database migrations
4. **Integration Testing**: Verify all new table types work correctly in production

### Future Enhancements
1. **Collaboration**: Multi-user mind-map sharing and commenting
2. **Export Capabilities**: PDF, PNG, and data export for mind-maps
3. **Advanced Analytics**: Usage patterns and effectiveness metrics
4. **Integration**: Connect with external reference managers
5. **Performance**: Optimization for large-scale mind-map generation
6. **Cloud Migration**: Support for cloud database backends

## Debug Log

### Current Session: Database Migration System Complete ✅
- ✅ **Migration Export System**: Updated `db_export.py` to support all 5 new table types
  - Added `export_research_runs()`, `export_research_agent_state()`, `export_paper_fulltext()`, `export_mindmap_reports()`, `export_model_catalog()` methods
  - Implemented proper binary embedding handling for `paper_fulltext` table
  - Added `include_new_tables` parameter for backwards compatibility
  - Enhanced metadata with version 2.0 and feature detection
  - Comprehensive error handling with graceful degradation
  
- ✅ **Migration Import System**: Updated `db_import.py` to support all new table types
  - Added corresponding import methods for all 5 new tables
  - Implemented automatic table detection and optional import handling
  - Added proper embedding reconstruction from binary data
  - Enhanced duplicate detection for all table types
  - Improved progress tracking and error reporting
  
- ✅ **Migration Orchestration**: Updated `db_migrate.py` for enhanced coordination
  - Added `include_new_tables` parameter to all migration methods
  - Enhanced verification system to check all available tables
  - Updated CLI with `--exclude-new-tables` option
  - Improved verification output with table-by-table status
  
- ✅ **Documentation & Examples**: Updated migration example with comprehensive demonstrations
  - Created new `migration_example.py` showing all new capabilities
  - Added examples for backwards compatibility mode
  - Demonstrated auto-detection and selective migration
  - Added cleanup and comprehensive testing examples

### Previous Session: Multi-Order Expansion Implementation Complete ✅
- ✅ **Mind-Map Reports Database**: Implemented complete database layer for mind-map reports
- ✅ **Multi-Order Expansion Backend Logic**: Implemented complete multi-order retrieval workflow
- ✅ **Frontend Integration**: All UI components updated with proper TypeScript interfaces

### Latest Session Issues Resolved
- Proper handling of binary embedding data in migration system
- Backwards compatibility maintained for older export formats
- Enhanced error handling for missing tables during migration
- Comprehensive CLI interface for all migration operations
- Automated table detection and validation in import system

### Known Issues
- Large database migrations may require performance optimization
- Binary embedding data handling needs thorough testing across platforms
- CLI help text could be more detailed for complex migration scenarios

### Technical Debt
- Consider implementing database schema versioning for automatic migrations
- Evaluate compressed archive formats for large database exports
- Review error handling patterns across all migration modules
- Consider adding migration progress persistence for very large operations
