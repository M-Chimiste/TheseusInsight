# Topic Evolution & Trend-Forecast Dashboard User Guide

## Overview

The Topic Evolution & Trend-Forecast Dashboard is an automated analytics platform that helps machine learning researchers identify emerging topics, track their evolution over time, and make strategic research decisions based on predictive forecasts.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Understanding the Dashboard](#understanding-the-dashboard)
3. [Topic Discovery Modes](#topic-discovery-modes)
4. [Interactive Features](#interactive-features)
5. [Recomputation and Administration](#recomputation-and-administration)
6. [Integration with Other Features](#integration-with-other-features)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

Before using the trends dashboard, ensure you have:

1. **Papers in Your Database**: The system analyzes papers already in your Theseus Insight database
2. **LLM Configuration**: A configured "judge" model for label summarization (in Settings → Orchestration)
3. **Sufficient Data**: At least 100+ papers for meaningful trend analysis

### First Time Setup

1. **Navigate to Trends**: Click "Trends" in the sidebar navigation
2. **Initial Computation**: If no trends data exists, you'll see a "Recompute Trends" button
3. **Start Analysis**: Click the button to begin your first trends computation
4. **Wait for Processing**: Initial computation may take 5-15 minutes depending on your paper collection size

### Quick Start Workflow

```
1. Access Trends page → 2. Trigger computation → 3. Explore results → 4. Generate content
```

---

## Understanding the Dashboard

### Main Dashboard View

The trends dashboard provides multiple visualization modes:

#### **Topic Heatmap View**
- **Visual Overview**: Color-coded grid showing topic popularity and growth
- **Growth Indicators**: Green = growing, red = declining, gray = stable
- **Interactive**: Click any topic to view detailed timeline and papers

#### **Topic List View**
- **Detailed Metrics**: Shows document counts, growth rates, and forecasts
- **Sortable Columns**: Sort by growth rate, document count, or forecast values
- **Search Functionality**: Find specific topics by keywords

### Key Metrics Explained

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **Doc Count** | Number of papers in this topic for the current period | Higher = more active research area |
| **Growth Rate** | Percentage change from previous period | Positive = growing, negative = declining |
| **Forecast 1M/3M/6M** | Predicted paper counts for 1, 3, 6 months ahead | Trend trajectory prediction |
| **Total Papers** | All-time papers associated with this topic | Overall topic significance |

### Timeline Visualizations

**Interactive Charts**: 
- **Line Charts**: Show topic evolution over time
- **Forecast Overlay**: Dotted lines show predicted future values
- **Period Selection**: Toggle between weekly, monthly, quarterly views
- **Zoom and Pan**: Explore specific time ranges in detail

---

## Topic Discovery Modes

The system offers two complementary approaches to topic analysis:

### 1. Automatic Topic Discovery (Default)

**How it Works**:
- Uses BERTopic with HDBSCAN clustering
- Automatically identifies emerging topics from paper embeddings
- Generates descriptive labels based on topic keywords

**Best For**:
- Discovering unexpected research directions
- Identifying emerging trends you might not have considered
- Broad exploration of the research landscape

**Configuration**:
- **Lookback Months**: How far back to analyze (1-36 months)
- **Duration Months**: Analysis window (1-24 months)
- **Min Papers**: Minimum papers required per topic (prevents noise)

### 2. Research Interest Analysis

**How it Works**:
- Clusters papers against your configured research interests
- Uses semantic similarity to match papers to interests
- Tracks evolution of your specific research areas

**Best For**:
- Monitoring your specific research domains
- Tracking progress in areas you care about
- Focused analysis on predetermined interests

**Setup**:
1. Go to Settings → Research Interests
2. Add your research interests (one per line)
3. Use "Research Interests" mode in trends dashboard

---

## Interactive Features

### Topic Detail Modal

Click any topic to open detailed information:

**Timeline Tab**:
- Historical evolution chart
- Forecast visualization
- Period-by-period metrics

**Papers Tab**:
- Representative papers for this topic
- Relevance scores and sorting options
- Direct links to paper details

**Actions Tab**:
- Generate mind-map from topic
- Create newsletter focused on topic
- Export topic data

### Search and Filtering

**Smart Search**:
- Search topics by keywords or phrases
- Real-time filtering as you type
- Highlights matching terms in results

**Advanced Filters**:
- **Period Type**: Week/Month/Quarter granularity
- **Duration**: Analysis time window
- **Min Papers**: Filter out small topics
- **Sort Options**: Growth rate, document count, forecasts

### Label Summarization

**AI-Generated Labels**:
- Long topic labels are automatically summarized
- Uses your configured LLM model
- Cached for performance (no re-generation)

**Customization**:
- Labels update when you change LLM models
- Cache management in admin settings
- Manual cache clearing available

---

## Recomputation and Administration

### When to Recompute

**Automatic Schedule**: 
- Runs nightly at 2 AM (configurable)
- Incremental processing (only new data)
- Minimal performance impact

**Manual Triggers**:
- New papers added to database
- Changed research interests
- Different analysis parameters needed
- Troubleshooting data issues

### Recomputation Options

#### **Incremental Processing** (Recommended)
```
✅ Fast execution (2-5 minutes)
✅ Preserves existing topics
✅ Only processes new papers
✅ Updates recent time periods
```

#### **Full Recalculation**
```
⚠️ Longer execution (8-15 minutes)
✅ Recalculates all metrics
✅ Preserves topic structure
✅ Fixes data inconsistencies
```

#### **Nuclear Option** (Troubleshooting)
```
🚨 Longest execution (10-20 minutes)
⚠️ Clears ALL trend data
✅ Complete fresh start
✅ Fixes major issues
```

### Performance Configuration

**System Optimization**:
- Automatic hardware detection
- Recommended settings based on your system
- Configurable processing parameters

**Key Settings**:
- **Max Cores**: CPU utilization limit
- **Memory Allocation**: RAM usage for processing
- **Batch Sizes**: Processing chunk sizes
- **Caching Options**: Performance vs memory trade-offs

### Monitoring and Validation

**Forecast Accuracy**:
- Automatic accuracy tracking
- Alerts when accuracy drops below 70%
- Historical performance metrics

**Processing Logs**:
- Detailed execution logs
- Error reporting and diagnostics
- Performance timing information

---

## Integration with Other Features

### Mind-Map Generation

**From Trending Topics**:
1. Open topic detail modal
2. Click "Generate Mind-Map"
3. System seeds mind-map with topic's most relevant papers
4. Explore intellectual neighborhood of the topic

**Benefits**:
- Discover related research areas
- Understand topic's intellectual structure
- Find influential papers in the field

### Newsletter Creation

**Topic-Focused Newsletters**:
1. Select interesting trending topic
2. Click "Generate Newsletter"
3. System creates newsletter from topic's recent papers
4. Overrides general research interests

**Use Cases**:
- Share trending research with team
- Create focused summaries for specific areas
- Track developments in hot topics

### Paper Filtering

**Topic-Based Navigation**:
- Click topic tags on paper cards
- Filter entire paper library by topic
- Maintain other filters (date, score, search)

**Research Workflow**:
```
Trends → Interesting Topic → Filter Papers → Deep Dive → Generate Content
```

---

## Best Practices

### Optimal Configuration

**For Small Collections** (< 1,000 papers):
- Use 12-month lookback
- Set min_papers to 10-20
- Focus on quarterly analysis
- Use research interest mode

**For Large Collections** (> 10,000 papers):
- Use 24-month lookback
- Set min_papers to 50-100
- Weekly/monthly analysis
- Automatic topic discovery

### Interpretation Guidelines

**Growth Rate Analysis**:
- **> 50%**: Explosive growth (investigate immediately)
- **20-50%**: Strong growth (promising area)
- **5-20%**: Steady growth (established field)
- **< 5%**: Stable or declining

**Document Count Context**:
- Consider absolute numbers vs growth rates
- Small topics with high growth may be early signals
- Large topics with modest growth are still significant

**Forecast Reliability**:
- 1-month forecasts: High accuracy
- 3-month forecasts: Good accuracy
- 6-month forecasts: Moderate accuracy (use with caution)

### Research Strategy

**Discovery Workflow**:
1. **Broad Exploration**: Use automatic topic discovery
2. **Trend Identification**: Sort by growth rate
3. **Deep Dive**: Examine top growing topics
4. **Content Generation**: Create mind-maps and newsletters
5. **Research Planning**: Use forecasts for strategic decisions

**Monitoring Workflow**:
1. **Interest Tracking**: Use research interest mode
2. **Regular Review**: Weekly dashboard checks
3. **Comparative Analysis**: Track relative growth vs other topics
4. **Opportunity Assessment**: Identify under-explored growing areas

---

## Troubleshooting

### Common Issues

#### **No Topics Appearing**

**Symptoms**: Empty dashboard or very few topics
**Causes**: 
- Insufficient papers in database
- Min papers threshold too high
- Recent database or configuration changes

**Solutions**:
1. Check paper count in Research Library
2. Lower min_papers threshold (try 10-20)
3. Trigger manual recomputation
4. Verify research interests are configured

#### **Slow Performance**

**Symptoms**: Long loading times, timeouts
**Causes**:
- Large paper collection
- Insufficient system resources
- Suboptimal configuration

**Solutions**:
1. Check system info and optimize configuration
2. Use incremental processing instead of full recalculation
3. Increase processing timeouts
4. Consider development mode for testing

#### **Inaccurate Forecasts**

**Symptoms**: Forecast accuracy alerts, unrealistic predictions
**Causes**:
- Insufficient historical data
- Rapid changes in research patterns
- Data quality issues

**Solutions**:
1. Increase lookback period for more historical data
2. Validate forecast accuracy manually
3. Consider shorter forecast horizons
4. Check for data anomalies or outliers

#### **Label Summarization Errors**

**Symptoms**: Failed label generation, poor summaries
**Causes**:
- LLM configuration issues
- Rate limiting
- Network connectivity

**Solutions**:
1. Verify judge model configuration in Settings
2. Check API keys and connectivity
3. Clear label cache and retry
4. Use different LLM model

### Advanced Diagnostics

#### **Database Issues**

**Check Data Integrity**:
```sql
-- Count papers with embeddings
SELECT COUNT(*) FROM papers WHERE embedding IS NOT NULL;

-- Check topic distribution
SELECT COUNT(*) as topic_count, AVG(total_papers) as avg_papers 
FROM topics;

-- Verify recent metrics
SELECT period_type, COUNT(*) as metric_count 
FROM topic_metrics 
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY period_type;
```

#### **Performance Analysis**

**Monitor Resource Usage**:
- Check CPU and memory utilization during processing
- Monitor database connection counts
- Review processing logs for bottlenecks

**Optimization Steps**:
1. Adjust batch sizes based on available memory
2. Enable memory mapping for large datasets
3. Use development mode for testing configurations
4. Consider incremental processing for regular updates

#### **Accuracy Validation**

**Manual Validation Process**:
1. Compare forecasts to actual paper counts
2. Check for systematic biases in predictions
3. Validate topic assignments manually
4. Review clustering quality and topic coherence

### Getting Help

**Log Information**:
- Check browser console for frontend errors
- Review backend logs for processing issues
- Use task status tracking for background operations

**Community Support**:
- GitHub issues for bug reports
- Documentation updates for unclear procedures
- Feature requests for enhancements

---

## Advanced Usage

### Custom Analysis Workflows

**Competitive Research Analysis**:
1. Set up research interests for your field and competitors' areas
2. Monitor relative growth rates
3. Identify emerging areas before competitors
4. Use forecasts for strategic research planning

**Conference Preparation**:
1. Analyze trends 3-6 months before major conferences
2. Identify hot topics for paper submissions
3. Generate newsletters for team briefings
4. Create mind-maps for presentation planning

**Grant Application Support**:
1. Use growth forecasts to justify research directions
2. Export trend data for proposal graphics
3. Identify emerging areas with funding potential
4. Track field evolution for background sections

### API Integration

For advanced users, the trends system provides comprehensive APIs for:
- Custom dashboard creation
- Automated reporting
- Integration with external tools
- Programmatic analysis workflows

See the [API Documentation](trends_api_spec.md) for detailed technical information.

---

This user guide provides comprehensive information for effectively using the Topic Evolution & Trend-Forecast Dashboard. For technical implementation details, see the [API Specification](trends_api_spec.md) and [PRD](../project_docs/prd.md). 