# Theseus Insight - Research Profiles Feature
## Product Requirements Document (PRD)

**Version:** 1.0  
**Date:** December 2024  
**Status:** Draft  

---

## Executive Summary

This PRD outlines the transformation of Theseus Insight from a single research interest system to a comprehensive multi-profile platform. Currently, users can only maintain one set of research interests, which creates data coherence issues when interests change over time. The proposed Research Profiles feature will allow users to create, manage, and switch between multiple named research profiles, each with distinct interests, while maintaining complete historical data integrity.

### Key Benefits
- **Data Preservation**: Retain ALL papers regardless of profile relevance, eliminating data loss
- **Research Flexibility**: Support multiple concurrent research areas without cross-contamination
- **Enhanced Analytics**: Profile-specific and cross-profile trending analysis
- **Improved Workflows**: Profile-aware newsletters, mind-maps, and content generation
- **Targeted Distribution**: Profile-specific email distribution lists for newsletters
- **Custom Filtering**: Profile-specific ArXiv category filters for focused data collection
- **Future-Proofing**: Architecture designed for eventual multi-user support

---

## Current State Analysis

### Current Architecture Limitations
1. **Single Interest Constraint**: Only one set of research interests supported globally
2. **Data Loss Risk**: Changing research interests makes previously relevant papers irrelevant
3. **Limited Flexibility**: Cannot explore multiple research areas simultaneously
4. **Filtering Inefficiency**: LLM judge filters papers at ingestion, losing potentially valuable data
5. **Context Switching Cost**: Users must manually change interests to explore different research areas

### Current System Dependencies
- **Settings Table**: Stores single research interests text
- **Research Interests Table**: Individual interest records for clustering
- **LLM Judge System**: Scores papers 1-10 against single interest set
- **Trends Analysis**: BERTopic and research interest clustering tied to single profile
- **Content Generation**: Newsletters and mind-maps use single interest context
- **Paper Pipeline**: Filters papers during ingestion based on single interest relevance

---

## Proposed Solution Overview

### Core Concept: Research Profiles
A **Research Profile** is a named collection of research interests, ArXiv filters, and distribution settings that represents a coherent research focus area. Users can create multiple profiles (e.g., "Computer Vision", "NLP Applications", "Robotics Research") and switch between them or analyze them concurrently. Each profile includes:

- **Research Interests**: Text-based interests for LLM judge scoring and clustering (recommended max: 10 per profile)
- **ArXiv Filters**: Category-specific filters for targeted paper harvesting
- **Email Distribution**: Recipient lists for profile-specific newsletter delivery
- **Profile Metadata**: Name, description, color coding, and dynamic tags for organization

### Key Principles
1. **Data Completeness**: Store ALL papers from ArXiv/Kaggle regardless of profile relevance
2. **On-Demand Scoring**: Run LLM judge scoring per profile with user-configurable date ranges
3. **Profile Independence**: Each profile maintains separate metrics, trends, and analytics
4. **Mixed Views**: Support viewing data across multiple profiles simultaneously
5. **Seamless Migration**: Automatic migration of existing interests to "Default" profile

### Dynamic Tag System Design

**User Experience Flow:**
1. **Type-Ahead Interface**: User starts typing in tag input field
2. **Auto-Complete Suggestions**: System shows matching existing tags as dropdown suggestions
3. **Tag Selection**: User can click on suggestion to select existing tag
4. **New Tag Creation**: If user continues typing and presses Enter/Tab, system creates new tag automatically
5. **Immediate Availability**: New tags become immediately available for auto-complete in future use

**Technical Behavior:**
- **Real-Time Search**: API calls trigger after 2+ characters typed with debouncing
- **Case-Insensitive Matching**: Tag matching ignores case differences
- **Fuzzy Matching**: Optional fuzzy matching for typo tolerance
- **Tag Normalization**: Tags stored in lowercase, displayed with proper casing
- **No Duplicates**: System prevents creation of duplicate tags (case-insensitive)

**Example Usage:**
```
User types: "mach"
System shows: ["machine-learning", "machine-vision"] 
User continues: "machine-translation"
User presses Enter: New tag "machine-translation" created and assigned
```

---

## Phased Implementation Plan

### Phase 1: Core Infrastructure (Weeks 1-3)
**Goal**: Establish profile system foundation and migrate existing data

#### Database Schema Changes
- Add `research_profiles` table for profile management
- Update `research_interests` table to be profile-scoped
- Modify all profile-dependent tables (`research_interest_metrics`, `paper_research_interests`)
- Create migration scripts for existing data

#### Core Features
- Profile CRUD operations (Create, Read, Update, Delete)
- Basic profile management API endpoints
- Migration of current research interests to "Default" profile
- Migration of current email recipients and ArXiv filters to "Default" profile
- Update paper ingestion to store ALL papers without LLM filtering

#### Success Criteria
- Existing users can access their data through "Default" profile
- New profiles can be created and managed
- All papers are retained during ingestion
- Zero data loss during migration

### Phase 2: Profile-Aware Paper Management (Weeks 4-6)
**Goal**: Implement profile-specific LLM judge scoring and paper association

#### Core Features
- **Bulk LLM Judge Runner**: New UI page for running judge scoring across profiles
- **Configurable Date Ranges**: User-selectable date ranges for judge runs
- **Profile-Specific Scoring**: Store LLM judge scores per profile per paper
- **Deduplication Logic**: Check existing ArXiv data before re-harvesting
- **Profile Paper Filtering**: Filter papers by profile in Research Library

#### New UI Components
- **Profile Management Page**: Create, edit, delete, and manage profiles including research interests, email distribution lists, ArXiv filters, and tags
- **Bulk Judge Runner Page**: Select profiles, date ranges, and trigger scoring with tag-based profile selection
- **Profile Selector**: Global UI component for switching active profile context with tag-based filtering
- **Paper Filters**: Profile-based and tag-based filtering in paper views
- **Distribution Manager**: Interface for managing email recipients per profile
- **Dynamic Tag Input**: Type-ahead interface that suggests existing tags and allows creation of new tags on-the-fly

#### Success Criteria
- Users can run LLM judge against historical data for any profile
- Profile-specific paper relevance scores are stored and accessible
- ArXiv harvesting avoids duplicate downloads
- Paper views can be filtered by profile

### Phase 3: Profile-Aware Analytics (Weeks 7-9)
**Goal**: Extend trends analysis and analytics to support multiple profiles

#### Core Features
- **Profile-Specific Trends**: BERTopic and research interest clustering per profile
- **Cross-Profile Analytics**: Trending analysis across multiple profiles
- **Mixed View Support**: Display trends from multiple profiles simultaneously
- **Profile Comparison**: Compare trend evolution across different profiles

#### Enhanced Features
- **Profile Metrics Dashboard**: Profile-specific document counts, growth rates
- **Cross-Profile Discovery**: Find papers relevant to multiple profiles
- **Trend Migration**: Historical trend data automatically associated with Default profile

#### Success Criteria
- Trends analysis works independently for each profile
- Users can view cross-profile trend comparisons
- Mixed views display coherent multi-profile data
- Performance remains acceptable with multiple profiles

### Phase 4: Profile-Aware Content Generation (Weeks 10-12)
**Goal**: Enable profile-specific and multi-profile content generation

#### Newsletter Enhancements
- **Profile Selection**: Choose specific profiles for newsletter generation
- **Multi-Profile Newsletters**: Generate newsletters covering multiple profiles
- **Profile-Specific Filtering**: Newsletter content filtered by profile relevance
- **Profile-Specific Distribution**: Newsletters sent to profile-specific email lists
- **Bulk Newsletter Generation**: Create newsletters for multiple profiles simultaneously, each sent to their respective distribution lists

#### Mind-Map Enhancements
- **Profile Context**: Mind-maps seeded from profile-specific papers
- **Cross-Profile Maps**: Explore connections across multiple profiles
- **Profile Filtering**: Filter mind-map exploration by profile relevance

#### Success Criteria
- Newsletters can be generated for specific profiles
- Multi-profile newsletters provide coherent cross-domain insights
- Mind-maps respect profile boundaries while allowing cross-pollination
- Content quality maintains current standards across all profiles

### Phase 5: Advanced Features & Optimization (Weeks 13-15)
**Goal**: Polish user experience and optimize performance

#### Advanced UI Features
- **Profile Templates**: Quick-start templates for common research areas
- **Profile Analytics Dashboard**: Comprehensive profile performance metrics
- **Batch Operations**: Bulk operations across multiple profiles
- **Profile Export/Import**: Share and backup profile configurations

#### Performance Optimizations
- **Intelligent Caching**: Cache profile-specific computations
- **Batch Processing**: Optimize multi-profile operations
- **Index Optimization**: Database indexes for multi-profile queries
- **Background Processing**: Async processing for heavy profile operations

#### Success Criteria
- System performance scales well with multiple profiles
- User experience is intuitive and efficient
- Advanced features enhance research productivity
- System remains stable under heavy multi-profile usage

---

## Database Schema Changes

### New Tables

#### `research_profiles` 
```sql
CREATE TABLE research_profiles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT, -- UI color coding
    tags JSONB, -- Array of tags for profile organization
    email_recipients JSONB, -- Array of email addresses for newsletter distribution
    arxiv_filters JSONB, -- ArXiv category filters specific to this profile
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

#### `profile_research_interests`
```sql
CREATE TABLE profile_research_interests (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    interest_text TEXT NOT NULL,
    embedding vector(768),
    embedding_model TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(profile_id, interest_text)
);
```

### Modified Tables

#### `paper_profile_scores`
```sql
CREATE TABLE paper_profile_scores (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    score REAL, -- LLM judge score 1-10
    rationale TEXT, -- LLM judge rationale
    related BOOLEAN DEFAULT FALSE,
    similarity_score REAL, -- Embedding similarity score
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(paper_id, profile_id)
);
```

### Index Strategy
```sql
-- Performance indexes for multi-profile queries
CREATE INDEX idx_paper_profile_scores_profile_id ON paper_profile_scores(profile_id);
CREATE INDEX idx_paper_profile_scores_score ON paper_profile_scores(score DESC);
CREATE INDEX idx_paper_profile_scores_similarity ON paper_profile_scores(similarity_score DESC);
CREATE INDEX idx_profile_research_interests_profile_id ON profile_research_interests(profile_id);

-- Tag-based queries optimization (GIN index for JSONB array operations)
CREATE INDEX idx_research_profiles_tags ON research_profiles USING GIN (tags);
CREATE INDEX idx_research_profiles_active ON research_profiles (is_active);

-- Note: Tags are stored as JSONB arrays on profiles, no separate tags table needed
-- Unique tag list generated via: SELECT DISTINCT jsonb_array_elements_text(tags) FROM research_profiles;
```

---

## Migration Strategy

### Automatic Migration Process
1. **Create Default Profile**: Create "Default" profile with current research interests
2. **Migrate Research Interests**: Move existing interests to Default profile
3. **Associate Historical Data**: Link all existing paper scores/metrics to Default profile
4. **Preserve Settings**: Maintain current system behavior through Default profile
5. **Update References**: Update all API calls to use profile-scoped endpoints

### Migration Script Outline
```python
def migrate_to_profiles():
    # 1. Create Default profile with current settings
    email_recipients = get_current_email_recipients()
    arxiv_config = get_current_arxiv_config()
    default_profile = create_profile(
        name="Default", 
        email_recipients=email_recipients,
        arxiv_filters=arxiv_config,
        is_default=True
    )
    
    # 2. Migrate research interests
    current_interests = get_current_research_interests()
    migrate_interests_to_profile(current_interests, default_profile.id)
    
    # 3. Associate existing paper scores
    migrate_paper_scores_to_profile(default_profile.id)
    
    # 4. Update research interest metrics
    migrate_research_metrics_to_profile(default_profile.id)
    
    # 5. Validate data integrity
    validate_migration_completeness()
```

---

## API Changes

### New Endpoints

#### Profile Management
```
GET    /api/profiles                    # List all profiles
POST   /api/profiles                    # Create new profile
GET    /api/profiles/{id}               # Get profile details
PUT    /api/profiles/{id}               # Update profile
DELETE /api/profiles/{id}               # Delete profile
POST   /api/profiles/{id}/clone         # Clone profile
PUT    /api/profiles/{id}/distribution  # Update email distribution list
PUT    /api/profiles/{id}/arxiv-filters # Update ArXiv category filters
PUT    /api/profiles/{id}/tags          # Update profile tags
GET    /api/profiles/tags               # Get all unique tags across profiles
GET    /api/profiles/tags/search?q={query} # Search/auto-complete existing tags
GET    /api/profiles/by-tag/{tag}       # Get profiles with specific tag
```

#### Profile-Scoped Operations
```
GET    /api/profiles/{id}/papers        # Get papers for profile
POST   /api/profiles/{id}/judge-run     # Run LLM judge for profile
GET    /api/profiles/{id}/trends        # Get trends for profile
POST   /api/profiles/{id}/newsletter    # Generate profile newsletter
POST   /api/profiles/{id}/mindmap       # Generate profile mind-map
```

#### Bulk Operations
```
POST   /api/profiles/bulk/judge-run     # Run judge across multiple profiles
POST   /api/profiles/bulk/newsletter    # Generate newsletters for multiple profiles
GET    /api/profiles/bulk/trends        # Cross-profile trend analysis
```

#### Tag Auto-Complete API Specification
```
GET /api/profiles/tags/search?q={query}&limit=10

Response:
{
  "query": "mach",
  "suggestions": [
    {"tag": "machine-learning", "usage_count": 5},
    {"tag": "machine-vision", "usage_count": 2}
  ],
  "exact_match": false
}

# When user creates new tag, it's automatically added to the database
# No separate tag creation endpoint needed - happens during profile update
```

### Enhanced Existing Endpoints

#### Papers API
```
GET /api/papers?profile_id={id}         # Filter by profile
GET /api/papers?profile_ids={id1,id2}   # Filter by multiple profiles
GET /api/papers?profile_tag={tag}       # Filter by profiles with specific tag
GET /api/papers?profile_tags={tag1,tag2} # Filter by profiles with any of the tags
```

#### Trends API
```
GET /api/trends?profile_id={id}         # Profile-specific trends
GET /api/trends?profile_ids={id1,id2}   # Multi-profile trends
GET /api/trends?profile_tag={tag}       # Trends for profiles with specific tag
GET /api/trends?profile_tags={tag1,tag2} # Trends for profiles with any of the tags
```

---

## UI/UX Changes

### Global UI Components

#### Profile Selector
- **Location**: Top navigation bar
- **Features**: Dropdown with all profiles, quick switch, "All Profiles" option
- **Visual Cues**: Color coding, active profile indication

#### Profile Management Panel
- **Location**: Settings page
- **Features**: Create, edit, delete profiles; manage research interests (max 10 recommended), email distribution lists, ArXiv filters, and tags per profile
- **Dynamic Tag System**: Type-ahead interface with auto-complete from existing tags; new tags automatically created when user types novel tag names
- **Email Management**: Add/remove email recipients using current validation approach
- **Filter Configuration**: Select ArXiv categories and subcategories for profile-specific harvesting
- **Bulk Operations**: Mass import/export, profile cloning, tag-based bulk operations

### New Pages

#### Profile Dashboard
- **Overview**: Profile-specific metrics and recent activity
- **Quick Actions**: Run judge, generate content, view trends
- **Analytics**: Profile performance over time
- **Tag-Based Views**: Group and filter profiles by tags, tag-based performance comparison

#### Bulk Operations Page
- **Judge Runner**: Select profiles by name or tags, date ranges, trigger scoring
- **Tag-Based Selection**: Dynamic tag input for selecting multiple profiles via tags
- **Content Generator**: Multi-profile newsletters, cross-profile analysis
- **System Status**: Monitor background operations

### Enhanced Existing Pages

#### Research Library
- **Profile Filtering**: Filter papers by one or multiple profiles
- **Score Display**: Show profile-specific relevance scores
- **Cross-Profile View**: See which profiles find a paper relevant

#### Trends Dashboard
- **Profile Selector**: View trends for specific or multiple profiles
- **Comparison Mode**: Side-by-side profile trend comparison
- **Mixed View**: Overlay trends from multiple profiles

#### Newsletter Generation
- **Profile-Specific Recipients**: Each newsletter sent to the profile's configured distribution list
- **Multi-Profile Coordination**: Option to send coordinated newsletters to different audiences
- **Distribution Preview**: Preview recipient lists before sending newsletters
- **Send History**: Track which profiles received which newsletters

---

## Performance Considerations

### Database Optimization
- **Partitioning**: Consider partitioning large tables by profile_id
- **Indexing Strategy**: Comprehensive indexes for multi-profile queries
- **Query Optimization**: Efficient joins across profile-scoped tables

### Caching Strategy
- **Profile-Specific Caching**: Cache computations per profile
- **Cross-Profile Caching**: Cache multi-profile aggregations
- **Intelligent Invalidation**: Update caches when profiles change

### Background Processing
- **Async Operations**: LLM judge runs, trend computations
- **Queue Management**: Priority queues for different operation types
- **Progress Tracking**: Real-time progress updates for long operations

---

## Risk Assessment

### Technical Risks
- **Database Migration Complexity**: Risk of data loss during migration
- **Performance Degradation**: Multi-profile queries may be slower
- **Storage Growth**: Storing scores for all profiles per paper increases storage
- **API Complexity**: More complex API surface area

### Mitigation Strategies
- **Comprehensive Testing**: Extensive testing of migration scripts
- **Performance Monitoring**: Benchmark multi-profile operations
- **Gradual Rollout**: Phase-based rollout allows for issue detection
- **Rollback Plan**: Clear rollback procedures for each phase

### User Experience Risks
- **Complexity Overload**: Multiple profiles may confuse users
- **Migration Disruption**: Users may lose familiarity with new interface
- **Learning Curve**: New concepts require user education

### Mitigation Strategies
- **Progressive Disclosure**: Hide complexity behind intuitive defaults
- **Guided Migration**: Onboarding flow for existing users
- **Documentation**: Comprehensive user guides and tutorials

---

## Success Metrics

### Technical Metrics
- **Migration Success Rate**: 100% successful data migration with zero data loss
- **Performance Benchmarks**: Multi-profile operations within 2x single-profile latency
- **System Stability**: <0.1% error rate for profile operations
- **Storage Efficiency**: <50% storage increase for multi-profile data

### User Experience Metrics
- **Feature Adoption**: >80% of users create additional profiles within 30 days
- **Profile Usage**: >60% of operations use non-default profiles within 60 days
- **Tag Usage**: >50% of profiles have at least one tag within 60 days
- **Profile Organization**: >70% of users with 5+ profiles use tags for organization
- **User Satisfaction**: >4.5/5 user satisfaction score for profile management
- **Support Requests**: <10% increase in support requests during rollout

### Business Metrics
- **Research Productivity**: Measurable increase in content generation frequency
- **Data Utilization**: Higher percentage of papers marked as relevant across profiles
- **User Retention**: No decrease in user retention during transition
- **Feature Completeness**: All existing features work with profile system

---

## Open Questions & Future Considerations

### Phase 1 Questions
1. Should profiles have access control settings for future multi-user support? - For now, no. I ultimately will think we just keep a user segregated to their profiles.
2. What should be the maximum recommended number of research interests per profile? - We should recommend no more than 10, but it's really up to them.
3. Should we support profile hierarchies or tags for organization? - Yes, if we can. I like the idea of tags.
4. Should there be validation/verification for email addresses in distribution lists? - Do whatever we are currently doing, it works fine.
5. How should we handle email delivery failures and bounce management per profile? - We should handle them the same way we are doing so with the newsletter feature. We shouldn't need to change this.
6. Should profiles support different newsletter templates or formats? - No, keep it as the current default. We can consider this is a future release.

### Future Enhancements
- **Collaborative Profiles**: Shared profiles for research teams
- **Profile Templates**: Pre-built profiles for common research areas
- **Cross-Instance Sync**: Sync profiles across different Theseus Insight instances
- **Machine Learning Optimization**: ML-powered profile suggestion and optimization
- **Advanced Distribution**: Contact list integration, subscription management, delivery analytics
- **Newsletter Customization**: Profile-specific newsletter templates and branding
- **Delivery Scheduling**: Profile-specific delivery schedules and time zones

### Long-term Vision
The Research Profiles feature positions Theseus Insight as a comprehensive research intelligence platform capable of supporting complex, multi-domain research workflows. This foundation enables future features like research team collaboration, institutional knowledge management, and advanced AI-powered research assistance.

---

## Conclusion

The Research Profiles feature represents a fundamental evolution of Theseus Insight from a single-context research tool to a multi-faceted research intelligence platform. The phased implementation approach balances user value delivery with technical risk management, ensuring a smooth transition while opening new possibilities for research productivity and insight generation.

The success of this feature will significantly enhance Theseus Insight's value proposition and establish a foundation for future advanced features in the research intelligence domain.
