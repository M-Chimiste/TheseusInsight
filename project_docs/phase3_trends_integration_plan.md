# Phase 3: Research Profiles ↔ Trends Integration Plan

## Overview
Integrate the Research Profiles system with Theseus Insight's trends analysis to enable profile-scoped topic discovery, metrics, and forecasting.

## Current Trends System Architecture

### Two Analysis Modes
1. **BERTopic Mode** - Automatic topic discovery using BERTopic clustering on paper embeddings
2. **Research Interest Mode** - Analysis based on user-configured research interests in `research_interests` table

### Key Components
- `TrendsProcessor` - Main processing pipeline with BERTopic
- `ResearchInterestProcessor` - Research interest-based analysis  
- `TopicsRepository` / `ResearchInterestsRepository` - Data access layers
- Weekly → Monthly → Quarterly metric aggregation
- Prophet-based forecasting

---

## 🎯 Integration Strategy

### Phase 3A: Profile-Scoped BERTopic Analysis
**Goal:** Run BERTopic topic discovery separately for each research profile using only papers relevant to that profile.

#### Implementation Steps

1. **Modify TrendsProcessor for Profile Context**
   ```python
   # New method in TrendsProcessor
   def extract_topics_for_profile(self, profile_id: int, papers: List[Dict], min_topic_size: int = 10):
       """Run BERTopic on papers filtered for a specific profile."""
       # Filter papers by profile scores/relevance
       # Run BERTopic clustering
       # Return profile-specific topics
   ```

2. **Profile-Specific Topics Tables**
   ```sql
   -- Extend existing topics table
   ALTER TABLE topics ADD COLUMN profile_id INTEGER REFERENCES research_profiles(id);
   ALTER TABLE topic_metrics ADD COLUMN profile_id INTEGER REFERENCES research_profiles(id);
   
   -- Update indexes
   CREATE INDEX idx_topics_profile ON topics(profile_id);
   CREATE INDEX idx_topic_metrics_profile ON topic_metrics(profile_id);
   ```

3. **Enhanced API Endpoints**
   ```
   GET /api/trends/profiles/{profile_id}/topics
   GET /api/trends/profiles/{profile_id}/dashboard  
   POST /api/trends/profiles/{profile_id}/recompute
   ```

#### Benefits
- **Profile-specific topic discovery** - Each profile gets its own topic clusters
- **Better topic relevance** - Topics are specific to profile interests
- **Comparative analysis** - Compare topic trends across profiles

### Phase 3B: Profile-Aware Research Interest Analysis
**Goal:** Replace the current single `research_interests` table with profile-scoped interests from `profile_research_interests`.

#### Implementation Steps

1. **Update ResearchInterestProcessor**
   ```python
   # Modify existing ResearchInterestProcessor
   def calculate_metrics_for_profile(self, profile_id: int):
       """Calculate research interest metrics for a specific profile."""
       # Use profile_research_interests instead of research_interests
       # Filter papers by profile relevance scores
   ```

2. **API Integration**
   ```
   GET /api/trends/profiles/{profile_id}/interests
   GET /api/trends/interests/compare?profile_ids=1,2,3
   ```

#### Benefits
- **Profile-specific interest tracking** - Each profile tracks its own interests
- **Cross-profile comparison** - Compare interest performance across profiles
- **Interest evolution** - Track how interests perform in different profile contexts

### Phase 3C: Multi-Profile Analytics Dashboard
**Goal:** Create comprehensive analytics comparing profiles and enabling multi-profile workflows.

#### Features
- **Profile Performance Comparison** - Side-by-side metrics
- **Cross-Profile Topic Discovery** - Find overlapping topics
- **Interest Migration Analysis** - See how topics move between profiles
- **Unified Timeline Views** - Multi-profile trending

---

## 🚀 Implementation Plan

### Week 1: Database & Core Integration
- [ ] Add `profile_id` columns to topics and metrics tables
- [ ] Update existing topics to belong to Default profile
- [ ] Modify `TrendsProcessor` to accept profile context
- [ ] Create profile-specific data access methods

### Week 2: Profile-Scoped BERTopic
- [ ] Implement `extract_topics_for_profile()` method
- [ ] Create profile-filtered paper selection logic
- [ ] Add profile-aware topic saving and retrieval
- [ ] Test topic discovery on individual profiles

### Week 3: Enhanced API & Research Interests
- [ ] Add profile trends API endpoints
- [ ] Update `ResearchInterestProcessor` for profiles
- [ ] Implement cross-profile comparison endpoints
- [ ] Create unified dashboard data aggregation

### Week 4: Testing & Optimization
- [ ] Comprehensive testing with multiple profiles
- [ ] Performance optimization for multi-profile queries
- [ ] Documentation updates
- [ ] UI integration planning

---

## 📊 Expected Outcomes

### Technical Achievements
- **Profile-scoped analytics** - Each profile gets its own topic and interest tracking
- **Comparative insights** - Cross-profile analysis and comparison
- **Better relevance** - Topics and metrics specific to profile context
- **Scalable architecture** - Ready for unlimited number of profiles

### User Benefits
- **Focused insights** - See trends specific to each research area
- **Profile optimization** - Understand which profiles are most productive
- **Interest validation** - See which interests are generating the best content
- **Strategic planning** - Make data-driven decisions about research focus

### API Capabilities
```
# Profile-specific trends
GET /api/trends/profiles/1/topics
GET /api/trends/profiles/1/interests
GET /api/trends/profiles/1/dashboard

# Cross-profile analysis  
GET /api/trends/profiles/compare?ids=1,2,3
GET /api/trends/topics/overlap?profile_ids=1,2
GET /api/trends/interests/performance-comparison

# Multi-profile workflows
POST /api/trends/profiles/bulk-recompute
GET /api/trends/profiles/unified-timeline
```

---

## 🔧 Technical Considerations

### Database Schema Changes
```sql
-- Add profile context to existing tables
ALTER TABLE topics ADD COLUMN profile_id INTEGER REFERENCES research_profiles(id);
ALTER TABLE topic_metrics ADD COLUMN profile_id INTEGER REFERENCES research_profiles(id);

-- Update existing data to Default profile
UPDATE topics SET profile_id = 1 WHERE profile_id IS NULL;
UPDATE topic_metrics SET profile_id = 1 WHERE profile_id IS NULL;

-- Add constraints
ALTER TABLE topics ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE topic_metrics ALTER COLUMN profile_id SET NOT NULL;
```

### Performance Optimizations
- **Selective paper filtering** - Only process papers relevant to each profile
- **Parallel processing** - Run profile analysis in parallel where possible
- **Caching strategies** - Cache profile-specific computations
- **Incremental updates** - Only recompute changed profiles

### Backward Compatibility
- **Default profile fallback** - All existing functionality works through Default profile
- **API versioning** - New endpoints don't break existing ones
- **Gradual migration** - Existing topics remain accessible

---

## 🎮 Next Action Items

### Immediate (This Week)
1. **Start database schema updates** - Add profile_id columns
2. **Create profile-aware TrendsProcessor methods** 
3. **Test basic profile-scoped topic discovery**

### Short-term (Next 2 Weeks)
1. **Complete API endpoint implementation**
2. **Update ResearchInterestProcessor for profiles**
3. **Add cross-profile comparison capabilities**

### Medium-term (Next Month)
1. **Frontend UI integration**
2. **Comprehensive testing and optimization**
3. **Documentation and user guides**

---

This integration will transform the trends system from single-context to multi-profile, enabling sophisticated research analytics while maintaining full backward compatibility with existing functionality. 