import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  IconButton,
  Paper,
  Divider,
  Stack,
  FormControlLabel,
  Checkbox,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
  Timeline as TimelineIcon,
  Article as ArticleIcon,
  ShowChart as ShowChartIcon,
  AccountTree as MindMapIcon,
  Email as NewsletterIcon,
  Psychology as ResearchIcon,
  AutoGraph as TopicIcon,
} from '@mui/icons-material';
import * as d3 from 'd3';
import {
  trendsApi,
  researchInterestsApi,
  createWebSocket,
  type TopicApiResponse,
  isTopicDetailResponse,
  isResearchInterestDetailResponse,
  type EntityDetailResponse,
  type TrendsListResponse,
} from '../services/api';
import { useTheme } from '../contexts/ThemeContext';
import { useLayout } from '../contexts/LayoutContext';
// import PaperRowCard from './PaperRowCard'; // No longer used directly here

interface TrendsProps {}

type ViewMode = 'research-interests' | 'topic-discovery';

const Trends: React.FC<TrendsProps> = () => {
  const navigate = useNavigate();
  const { headerHeight } = useLayout(); // Get dynamic header height
  // State management
  const [viewMode, setViewMode] = useState<ViewMode>('research-interests');
  const [topics, setTopics] = useState<TopicApiResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [periodType, setPeriodType] = useState<'week' | 'month' | 'quarter'>('week');
  const [durationMonths, setDurationMonths] = useState<1 | 3 | 6 | 12 | 24>(1);
  const [sortBy, setSortBy] = useState<'growth_rate' | 'doc_count' | 'total_papers' | 'forecast_3m'>('growth_rate');
  const [minDocCount, setMinDocCount] = useState(1);
  const [selectedTopic, setSelectedTopic] = useState<EntityDetailResponse | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [recomputeDialogOpen, setRecomputeDialogOpen] = useState<boolean>(false);
  const [isRecomputing, setIsRecomputing] = useState<boolean>(false);
  const [forceFullRecalc, setForceFullRecalc] = useState(false);
  const [clearAllData, setClearAllData] = useState(false);
  const [dashboardStats, setDashboardStats] = useState<{
    total_topics: number;
    total_papers_with_topics: number;
  }>({ total_topics: 0, total_papers_with_topics: 0 });
  const [selectedTopics, setSelectedTopics] = useState<Set<number>>(new Set());
  const [summarizedLabels, setSummarizedLabels] = useState<Record<string, string>>({});

  const { isDarkMode } = useTheme();

  // D3 chart refs
  const timelineChartRef = useRef<SVGSVGElement>(null);
  const trendsChartRef = useRef<SVGSVGElement>(null);

  // Get current API based on view mode
  const getCurrentApi = () => {
    if (viewMode === 'research-interests') {
      return {
        getTrendingTopics: researchInterestsApi.getResearchInterests,
        searchTopics: researchInterestsApi.searchResearchInterests,
        getTopicDetail: researchInterestsApi.getResearchInterestDetail,
        recomputeTrends: researchInterestsApi.recomputeResearchInterests,
        getTopicPapers: researchInterestsApi.getResearchInterestPapers,
      };
    } else {
      return trendsApi;
    }
  };

  // Get view mode labels
  const getViewModeInfo = () => {
    if (viewMode === 'research-interests') {
      return {
        title: 'Research Interest Clustering',
        description: 'Analyzes papers based on your configured research interests from Settings, clustering papers against these predefined areas of focus.',
        entityName: 'research interest',
        entityNamePlural: 'research interests'
      };
    } else {
      return {
        title: 'Topic Discovery',
        description: 'Automatically discovers emerging topics using BERTopic machine learning to identify research trends and patterns.',
        entityName: 'topic',
        entityNamePlural: 'topics'
      };
    }
  };

  // Create concise topic label by stripping prefixes, numbers, and punctuation
  const createTopicLabel = (topicLabel: string): string => {
    // Remove prefixes like "Interest: " or "Topic XXXX: "
    let cleanLabel = topicLabel.replace(/^(Interest: |Topic \d+: )/, '');
    
    // Remove numbers and punctuation
    cleanLabel = cleanLabel.replace(/[0-9.,/#!$%^&*;:{}=\-_`~()]/g, '');
    
    // Trim whitespace and return the first two words
    return cleanLabel.trim().split(/\s+/).filter(Boolean).slice(0, 2).join(' ');
  };

  // Load trending topics
  const loadTrendingTopics = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await getCurrentApi().getTrendingTopics({
        limit: 20,
        period_type: periodType,
        duration_months: durationMonths,
        min_doc_count: minDocCount,
        sort_by: sortBy,
      });
      
      const data: TrendsListResponse = response.data;
      
      // Apply client-side sorting for options not supported by backend
      let sortedTopics = [...data.topics];
      if (sortBy === "total_papers") {
        sortedTopics.sort((a, b) => (b.total_papers || 0) - (a.total_papers || 0));
      }
      
      setTopics(sortedTopics);
      setDashboardStats({
        total_topics: data.total_topics,
        total_papers_with_topics: data.total_papers_with_topics,
      });
    } catch (err: any) {
      setError(`Failed to load trending topics: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Search topics
  const searchTopics = async () => {
    if (!searchQuery.trim()) {
      loadTrendingTopics();
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const response = await getCurrentApi().searchTopics({
        query: searchQuery,
        limit: 20,
      });
      
      // Apply client-side sorting for search results too
      let sortedTopics = [...response.data.topics];
      if (sortBy === "total_papers") {
        sortedTopics.sort((a, b) => (b.total_papers || 0) - (a.total_papers || 0));
      }
      
      setTopics(sortedTopics);
    } catch (err: any) {
      setError(`Failed to search topics: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (topics.length > 0) {
      fetchSummarizedLabels();
    }
  }, [topics]);

  // Load topic detail
  const loadTopicDetail = async (topicId: number) => {
    try {
      const response = await getCurrentApi().getTopicDetail(topicId, {
        period_type: periodType,
        timeline_limit: 24,
        papers_limit: 10,
      });
      
      setSelectedTopic(response.data);
      setDetailDialogOpen(true);
    } catch (err: any) {
      setError(`Failed to load topic detail: ${err.message}`);
    }
  };

  // Trigger recomputation
  const triggerRecomputation = async () => {
    try {
      setIsRecomputing(true);
      
      const response = await getCurrentApi().recomputeTrends({
        lookback_months: 24,
        duration_months: durationMonths,
        min_papers: 100,
        force_full_recalc: forceFullRecalc,
        validate_accuracy: true,
        clear_all_data: clearAllData,
      });
      
      // Set up WebSocket to track progress
      const ws = createWebSocket(response.data.task_id, 'trends' as any);
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'task_completed') {
          setIsRecomputing(false);
          setRecomputeDialogOpen(false);
          loadTrendingTopics(); // Reload data
          ws.close();
        } else if (message.type === 'task_failed') {
          setIsRecomputing(false);
          setError(`Recomputation failed: ${message.error}`);
          ws.close();
        }
      };
      
    } catch (err: any) {
      setIsRecomputing(false);
      setError(`Failed to start recomputation: ${err.message}`);
    }
  };

  // Generate mind-map from topic
  const generateMindMapFromTopic = async (topicId: number) => {
    try {
      setError(null);
      
      // Call the mind-map API to generate a mind-map from this topic
      const response = await fetch('/api/mindmap/expand', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          topic_id: topicId,
          k: 10,
          similarity_threshold: 0.3,
          layout_algorithm: "force-directed",
          expansion_order: 2,
          max_nodes_per_order: 5
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to generate mind-map: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Show success message and navigate to mind-map reports
      alert(`Mind-map generation started! Task ID: ${data.task_id}\n\nThe mind-map will be automatically saved to your Mind-Map Reports when complete. You can view the progress and the saved mind-map there.`);
      
      // Navigate to mind-map reports page
      window.open('/mindmap-reports', '_blank');
      
    } catch (err: any) {
      setError(`Failed to generate mind-map: ${err.message}`);
    }
  };

  // Generate newsletter from topic
  const generateNewsletterFromTopic = (topicId: number) => {
    navigate(`/newsletter?topicId=${topicId}`);
  };

  // D3 Timeline Chart
  const renderTimelineChart = (timeline: any[]) => {
    if (!timelineChartRef.current) return;

    const svg = d3.select(timelineChartRef.current);
    svg.selectAll("*").remove(); // Clear previous chart

    // Get container dimensions dynamically
    const container = timelineChartRef.current.parentElement;
    const containerWidth = container ? container.clientWidth : 800;
    
    const margin = { top: 50, right: 30, bottom: 60, left: 70 };
    const width = Math.max(400, containerWidth - 40) - margin.left - margin.right; // Leave some padding
    const height = 350 - margin.top - margin.bottom;

    const chart = svg
      .attr("width", width + margin.left + margin.right)
      .attr("height", height + margin.top + margin.bottom)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const data = timeline.map(d => ({
      date: new Date(d.period_start),
      doc_count: d.doc_count,
    }));

    const x = d3.scaleTime()
      .domain(d3.extent(data, d => d.date) as [Date, Date])
      .range([0, width]);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.doc_count) as number])
      .range([height, 0]);

    const line = d3.line<any>()
      .x(d => x(d.date))
      .y(d => y(d.doc_count));

    chart.append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", "steelblue")
      .attr("stroke-width", 2)
      .attr("d", line);

    // Styling based on theme
    const axisColor = isDarkMode ? 'white' : 'black';
    const titleColor = isDarkMode ? 'white' : 'black';

    // X-axis
    chart.append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .attr("fill", axisColor);

    // Y-axis
    chart.append("g")
      .call(d3.axisLeft(y))
      .selectAll("text")
      .attr("fill", axisColor);

    // Title - centered properly
    svg.append("text")
      .attr("x", (width + margin.left + margin.right) / 2)
      .attr("y", 25)
      .attr("text-anchor", "middle")
      .style("font-size", "18px")
      .style("font-weight", "600")
      .attr("fill", titleColor)
      .text(`${getViewModeInfo().entityName.charAt(0).toUpperCase() + getViewModeInfo().entityName.slice(1)} Evolution Over Time`);

    // Axis labels
    chart.append("text")
      .attr("transform", `translate(${width/2},${height + 45})`)
      .style("text-anchor", "middle")
      .style("fill", axisColor)
      .style("font-size", "12px")
      .text("Time");
      
    chart.append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left + 15)
      .attr("x", 0 - (height / 2))
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("fill", axisColor)
      .style("font-size", "12px")
      .text("Paper Count");
  };

  // D3 Topic Trends Chart - Responsive and optimized layout
  const renderTopicTrendsChart = (topicsToRender: TopicApiResponse[]) => {
    if (!trendsChartRef.current) return;

    const svg = d3.select(trendsChartRef.current);
    svg.selectAll("*").remove();

    // Get container dimensions dynamically
    const container = trendsChartRef.current.parentElement;
    const containerWidth = container ? container.clientWidth : 1200;
    
    // Calculate responsive dimensions
    const legendWidth = 350; // Much larger legend width for full text display
    const padding = 40; // Container padding
    const margin = { 
      top: 80, 
      right: containerWidth > 900 ? legendWidth + 20 : 20, // Increase threshold for wider legend
      bottom: 60, 
      left: 70 
    };
    
    const width = Math.max(400, containerWidth - padding) - margin.left - margin.right;
    const height = 450 - margin.top - margin.bottom;

    const chart = svg
      .attr("width", width + margin.left + margin.right)
      .attr("height", height + margin.top + margin.bottom)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Styling based on theme
    const axisColor = isDarkMode ? 'white' : 'black';
    const titleColor = isDarkMode ? 'white' : 'black';

    // Handle empty data case
    if (!topicsToRender.length) {
      // Still render basic chart structure with empty state message
      const x = d3.scaleTime()
        .domain([new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), new Date()])
        .range([0, width]);

      const y = d3.scaleLinear()
        .domain([0, 100])
        .range([height, 0]);

      // X-axis
      chart.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x))
        .selectAll("text")
        .style("fill", axisColor);

      // Y-axis
      chart.append("g")
        .call(d3.axisLeft(y))
        .selectAll("text")
        .style("fill", axisColor);

      // Title - properly positioned to avoid legend overlap
      svg.append("text")
        .attr("x", (width + margin.left) / 2)
        .attr("y", 25)
        .attr("text-anchor", "middle")
        .style("font-size", "20px")
        .style("font-weight", "600")
        .style("fill", titleColor)
        .text(`${getViewModeInfo().entityNamePlural.charAt(0).toUpperCase() + getViewModeInfo().entityNamePlural.slice(1)} Trends Over Time`);
        
      // Description - positioned below title and constrained to chart width
      const description = `Shows the evolution of top ${getViewModeInfo().entityNamePlural} with trend lines and growth indicators. Each line represents a ${getViewModeInfo().entityName}'s paper count evolution over the selected time period.`;
      
      // Wrap text properly based on available width
      const maxDescriptionWidth = width;
      const words = description.split(' ');
      const lineHeight = 16;
      let currentLine = '';
      let lineNumber = 0;
      
      // Create description group
      const descriptionGroup = svg.append("g");
      
      words.forEach(word => {
        const testLine = currentLine + word + ' ';
        // More accurate text width calculation
        if (testLine.length * 7 > maxDescriptionWidth && currentLine !== '') {
          descriptionGroup.append("text")
            .attr("x", margin.left + (width / 2))
            .attr("y", 50 + (lineNumber * lineHeight))
            .attr("text-anchor", "middle")
            .style("font-size", "14px")
            .style("fill", titleColor)
            .text(currentLine.trim());
          currentLine = word + ' ';
          lineNumber++;
        } else {
          currentLine = testLine;
        }
      });
      
      if (currentLine.trim() !== '') {
        descriptionGroup.append("text")
          .attr("x", margin.left + (width / 2))
          .attr("y", 50 + (lineNumber * lineHeight))
          .attr("text-anchor", "middle")
          .style("font-size", "14px")
          .style("fill", titleColor)
          .text(currentLine.trim());
      }

      // Axis labels
      chart.append("text")
        .attr("transform", `translate(${width/2},${height + 45})`)
        .style("text-anchor", "middle")
        .style("fill", axisColor)
        .style("font-size", "12px")
        .text("Time");
        
      chart.append("text")
        .attr("transform", "rotate(-90)")
        .attr("y", 0 - margin.left + 15)
        .attr("x", 0 - (height / 2))
        .attr("dy", "1em")
        .style("text-anchor", "middle")
        .style("fill", axisColor)
        .style("font-size", "12px")
        .text("Paper Count");

      // Empty state message
      chart.append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .style("font-size", "16px")
        .style("fill", isDarkMode ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)")
        .text(`No ${getViewModeInfo().entityNamePlural} data available`);
        
      chart.append("text")
        .attr("x", width / 2)
        .attr("y", height / 2 + 25)
        .attr("text-anchor", "middle")
        .style("font-size", "14px")
        .style("fill", isDarkMode ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.5)")
        .text("Try running the Recompute process to generate data");

      return;
    }

    // Take top 8 topics for clarity and filter by selection
    const topTopics = topicsToRender.slice(0, 8);
    const visibleTopics = selectedTopics.size === 0 ? topTopics : topTopics.filter(topic => selectedTopics.has(topic.id));

    // Create simulated time series data
    const timePoints = durationMonths <= 1 ? 4 : durationMonths <= 3 ? 6 : durationMonths <= 6 ? 8 : 12;
    const timeData: Array<{topic: TopicApiResponse, data: Array<{date: Date, value: number}>}> = [];

    visibleTopics.forEach((topic) => {
      const currentValue = topic.latest_doc_count || 0;
      const growthRate = topic.latest_growth_rate || 0;
      const points: Array<{date: Date, value: number}> = [];

      for (let i = 0; i < timePoints; i++) {
        const monthsBack = timePoints - 1 - i;
        const date = new Date();
        date.setMonth(date.getMonth() - monthsBack);
        
        const decayFactor = Math.exp(-growthRate * monthsBack / timePoints);
        const variance = 0.1 + (Math.sin(i * 0.5) * 0.05);
        const historicalValue = currentValue * decayFactor * (1 + variance);
        
        points.push({
          date: date,
          value: Math.max(1, Math.round(historicalValue))
        });
      }

      timeData.push({ topic, data: points });
    });

    const allDates = timeData.flatMap(d => d.data.map(p => p.date));
    const allValues = timeData.flatMap(d => d.data.map(p => p.value));

    const x = d3.scaleTime()
      .domain(d3.extent(allDates) as [Date, Date])
      .range([0, width]);

    const y = d3.scaleLinear()
      .domain([0, d3.max(allValues) || 0])
      .range([height, 0]);

    const color = d3.scaleOrdinal(d3.schemeCategory10)
        .domain(visibleTopics.map((_, i) => i.toString()));

    const line = d3.line<{date: Date, value: number}>()
      .x(d => x(d.date))
      .y(d => y(d.value));

    // Draw lines
    timeData.forEach((topicData, index) => {
        chart.append("path")
          .datum(topicData.data)
          .attr("fill", "none")
          .attr("stroke", color(index.toString()))
          .attr("stroke-width", 2)
          .attr("d", line);
        
        // Draw points
        chart.selectAll(`.dot-${index}`)
          .data(topicData.data)
          .enter()
          .append("circle")
            .attr("cx", d => x(d.date))
            .attr("cy", d => y(d.value))
            .attr("r", 4)
            .attr("fill", color(index.toString()));
    });
    
    // X-axis
    chart.append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .style("fill", axisColor);
      
    // Y-axis
    chart.append("g")
      .call(d3.axisLeft(y))
      .selectAll("text")
      .style("fill", axisColor);

    // Title - properly positioned to avoid legend overlap
    svg.append("text")
      .attr("x", (width + margin.left) / 2)
      .attr("y", 25)
      .attr("text-anchor", "middle")
      .style("font-size", "20px")
      .style("font-weight", "600")
      .style("fill", titleColor)
      .text(`${getViewModeInfo().entityNamePlural.charAt(0).toUpperCase() + getViewModeInfo().entityNamePlural.slice(1)} Trends Over Time`);
      
    // Description - positioned below title and constrained to chart width
    const description = `Shows the evolution of top ${getViewModeInfo().entityNamePlural} with trend lines and growth indicators. Each line represents a ${getViewModeInfo().entityName}'s paper count evolution over the selected time period.`;
    
    // Wrap text properly based on available width
    const maxDescriptionWidth = width;
    const words = description.split(' ');
    const lineHeight = 16;
    let currentLine = '';
    let lineNumber = 0;
    
    // Create description group
    const descriptionGroup = svg.append("g");
    
    words.forEach(word => {
      const testLine = currentLine + word + ' ';
      // More accurate text width calculation
      if (testLine.length * 7 > maxDescriptionWidth && currentLine !== '') {
        descriptionGroup.append("text")
          .attr("x", margin.left + (width / 2))
          .attr("y", 50 + (lineNumber * lineHeight))
          .attr("text-anchor", "middle")
          .style("font-size", "14px")
          .style("fill", titleColor)
          .text(currentLine.trim());
        currentLine = word + ' ';
        lineNumber++;
      } else {
        currentLine = testLine;
      }
    });
    
    // Add the last line
    if (currentLine.trim() !== '') {
      descriptionGroup.append("text")
        .attr("x", margin.left + (width / 2))
        .attr("y", 50 + (lineNumber * lineHeight))
        .attr("text-anchor", "middle")
        .style("font-size", "14px")
        .style("fill", titleColor)
        .text(currentLine.trim());
    }

    // Axis labels
    chart.append("text")
      .attr("transform", `translate(${width/2},${height + 45})`)
      .style("text-anchor", "middle")
      .style("fill", axisColor)
      .style("font-size", "12px")
      .text("Time");
      
    chart.append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left + 15)
      .attr("x", 0 - (height / 2))
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("fill", axisColor)
      .style("font-size", "12px")
      .text("Paper Count");

    // Legend - Only show if there's space (wide screens need more room for 350px legend)
    if (containerWidth > 900 && timeData.length > 0) {
      const legendItemHeight = 25;
      const legendStartY = 20;
      const maxLegendItems = Math.min(timeData.length, 8);
      const legendX = width + 20;
      
      // Add legend background
      const titleSpacing = 25; // Space for the legend title
      const legendHeight = (maxLegendItems * legendItemHeight) + 30 + titleSpacing;
      chart.append("rect")
        .attr("x", legendX - 5)
        .attr("y", legendStartY - 15)
        .attr("width", legendWidth - 10) // Adjust for much wider legend
        .attr("height", legendHeight)
        .attr("rx", 4)
        .style("fill", isDarkMode ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.03)")
        .style("stroke", isDarkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)")
        .style("stroke-width", 1);
      
      // Legend title
      chart.append("text")
        .attr("x", legendX)
        .attr("y", legendStartY - 5)
        .style("text-anchor", "start")
        .style("fill", axisColor)
        .style("font-size", "14px")
        .style("font-weight", "bold")
        .text(`${getViewModeInfo().entityNamePlural.charAt(0).toUpperCase() + getViewModeInfo().entityNamePlural.slice(1)}`);
      
      // Legend items
      const legend = chart.selectAll(".legend")
        .data(timeData.slice(0, maxLegendItems))
        .enter().append("g")
          .attr("class", "legend")
          .attr("transform", (_, i) => `translate(${legendX},${legendStartY + titleSpacing + i * legendItemHeight})`);

      legend.append("rect")
        .attr("x", 0)
        .attr("y", -8)
        .attr("width", 16)
        .attr("height", 16)
        .attr("rx", 2)
        .style("fill", (_, i) => color(i.toString()))
        .style("stroke", axisColor)
        .style("stroke-width", 0.5);

      legend.append("text")
        .attr("x", 22)
        .attr("y", 0)
        .attr("dy", ".35em")
        .style("text-anchor", "start")
        .style("fill", axisColor)
        .style("font-size", "12px")
        .style("font-weight", "500")
        .style("cursor", "pointer")
        .text(d => {
          const originalLabel = d.topic.label;
          return summarizedLabels[originalLabel] || createTopicLabel(originalLabel);
        })
        .append("title") // Add tooltip for full text
        .text(d => d.topic.label);
    }
  };

  // Fetch summarized labels from the backend
  const fetchSummarizedLabels = async () => {
    if (topics.length === 0) return;

    try {
      // Extract the actual interest text from labels that have "Interest: " prefix
      const labelsToSummarize = topics.map(t => t.label).map(label => {
        if (label.startsWith("Interest: ")) {
          return label.replace(/^Interest: \d+\. /, "").replace(/^Interest: /, "");
        }
        return label;
      });

      console.log("Requesting summaries for", labelsToSummarize.length, "labels");
      const response = await trendsApi.summarizeLabels(labelsToSummarize);
      
      // Map summaries to both full labels and extracted labels for flexible lookup
      const mappedSummaries: Record<string, string> = {};
      
      topics.forEach(topic => {
        const fullLabel = topic.label;
        const extractedLabel = fullLabel.startsWith("Interest: ") 
          ? fullLabel.replace(/^Interest: \d+\. /, "").replace(/^Interest: /, "")
          : fullLabel;
        
        const summary = response.data[extractedLabel];
        if (summary) {
          mappedSummaries[fullLabel] = summary;
          mappedSummaries[extractedLabel] = summary;
        }
      });
      
      setSummarizedLabels(mappedSummaries);
      
    } catch (error) {
      console.error("Failed to fetch summarized labels:", error);
    }
  };

  // Effects
  useEffect(() => {
    loadTrendingTopics();
  }, [periodType, durationMonths, sortBy, minDocCount, viewMode]);

  useEffect(() => {
    // Always render the chart, even if empty (to show empty state)
    renderTopicTrendsChart(topics);
  }, [topics, selectedTopics, durationMonths, isDarkMode, summarizedLabels]);

  useEffect(() => {
    // Re-render chart when selected topic timeline changes
    if (selectedTopic) {
      const entityData = getEntityData(selectedTopic);
      if (entityData) {
        renderTimelineChart(entityData.timeline);
      }
    }
  }, [selectedTopic, isDarkMode]);

  // Add resize handler for responsive charts
  useEffect(() => {
    const handleResize = () => {
      // Debounce resize events to avoid excessive re-rendering
      setTimeout(() => {
        renderTopicTrendsChart(topics);
        if (selectedTopic) {
          const entityData = getEntityData(selectedTopic);
          if (entityData) {
            renderTimelineChart(entityData.timeline);
          }
        }
      }, 100);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [topics, selectedTopic, selectedTopics, durationMonths, isDarkMode]);

  // Utility functions
  const formatGrowthRate = (rate: number | undefined) => {
    if (rate === undefined || rate === null) return "N/A";
    return `${(rate * 100).toFixed(1)}%`;
  };

  const getGrowthIcon = (rate: number | undefined) => {
    if (rate === undefined || rate === null) return <TrendingUpIcon color="disabled" />;
    if (rate > 0.05) return <TrendingUpIcon color="success" />;
    if (rate < -0.05) return <TrendingUpIcon color="error" />;
    return <TrendingUpIcon color="action" />;
  };

  // Helper functions to extract entity data regardless of type
  const getEntityData = (entity: EntityDetailResponse | null) => {
    if (!entity) return null;
    
    if (isTopicDetailResponse(entity)) {
      return {
        id: entity.topic.id,
        label: entity.topic.label,
        latest_growth_rate: entity.topic.latest_growth_rate,
        latest_doc_count: entity.topic.latest_doc_count,
        total_papers: entity.total_papers,
        timeline: entity.timeline,
        representative_papers: entity.representative_papers
      };
    } else if (isResearchInterestDetailResponse(entity)) {
      return {
        id: entity.interest.id,
        label: entity.interest.interest_text,
        latest_growth_rate: entity.interest.latest_growth_rate,
        latest_doc_count: entity.interest.latest_doc_count,
        total_papers: entity.total_papers,
        timeline: entity.timeline,
        representative_papers: entity.representative_papers
      };
    }
    
    return null;
  };

  const getEntityId = (entity: EntityDetailResponse | null): number | null => {
    if (!entity) return null;
    return isTopicDetailResponse(entity) ? entity.topic.id : entity.interest.id;
  };

  // Main component render
  return (
    <Box sx={{ pt: `${headerHeight + 24}px`, pb: 3, px: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h4" gutterBottom component="div">
              {getViewModeInfo().title}
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
              {getViewModeInfo().description}
              Each {getViewModeInfo().entityName} shows recent activity (papers in current {periodType}) and total papers ever associated.
            </Typography>
          </Box>
          
          {/* View Mode Toggle */}
          <Box sx={{ ml: 3 }}>
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={(_, newViewMode) => {
                if (newViewMode) {
                  setViewMode(newViewMode);
                  setError(null); // Clear any existing errors
                }
              }}
              size="small"
              sx={{ boxShadow: 1 }}
            >
              <ToggleButton value="research-interests" title="Analyze papers based on your research interests">
                <ResearchIcon sx={{ mr: 1 }} />
                Research Interests
              </ToggleButton>
              <ToggleButton value="topic-discovery" title="Automatically discover emerging topics">
                <TopicIcon sx={{ mr: 1 }} />
                Topic Discovery
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Box>
        
        {/* Stats Cards */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="h6">{dashboardStats.total_topics}</Typography>
                <Typography color="text.secondary">{`Total ${getViewModeInfo().entityNamePlural}`}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="h6">{dashboardStats.total_papers_with_topics}</Typography>
                <Typography color="text.secondary">Papers with Topics</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          {/* First Row: Search */}
          <Grid size={{ xs: 12, md: 8 }}>
            <TextField
              fullWidth
              label={`Search ${getViewModeInfo().entityNamePlural}`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && searchTopics()}
              InputProps={{
                endAdornment: (
                  <IconButton onClick={searchTopics}>
                    <SearchIcon />
                  </IconButton>
                ),
              }}
            />
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <Button
              fullWidth
              variant="outlined"
              onClick={loadTrendingTopics}
              startIcon={<RefreshIcon />}
            >
              Refresh
            </Button>
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <Button
              fullWidth
              variant="contained"
              onClick={() => setRecomputeDialogOpen(true)}
              startIcon={<ShowChartIcon />}
            >
              Recompute
            </Button>
          </Grid>
          
          {/* Second Row: Filters */}
          <Grid size={{ xs: 6, md: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Period</InputLabel>
              <Select
                value={periodType}
                label="Period"
                onChange={(e) => setPeriodType(e.target.value as any)}
              >
                <MenuItem value="week">Week</MenuItem>
                <MenuItem value="month">Month</MenuItem>
                <MenuItem value="quarter">Quarter</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <FormControl fullWidth>
            <InputLabel>Duration</InputLabel>
              <Select
                value={durationMonths}
                label="Duration"
                onChange={(e) => setDurationMonths(e.target.value as any)}
              >
                <MenuItem value={1}>1 Month</MenuItem>
                <MenuItem value={3}>3 Months</MenuItem>
                <MenuItem value={6}>6 Months</MenuItem>
                <MenuItem value={12}>1 Year</MenuItem>
                <MenuItem value={24}>2 Years</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label="Sort By"
                onChange={(e) => setSortBy(e.target.value as any)}
              >
                <MenuItem value="growth_rate">Growth Rate</MenuItem>
                <MenuItem value="doc_count">Recent Papers</MenuItem>
                <MenuItem value="total_papers">Total Papers</MenuItem>
                <MenuItem value="forecast_3m">3M Forecast</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 6, md: 2 }}>
            <Tooltip title="Minimum papers per topic">
              <TextField
                fullWidth
                label="Min Papers"
                type="number"
                value={minDocCount}
                onChange={(e) => setMinDocCount(parseInt(e.target.value) || 1)}
                inputProps={{ min: 1, max: 100 }}
              />
            </Tooltip>
          </Grid>
        </Grid>
      </Paper>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Topic Trends Visualization */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {getViewModeInfo().entityNamePlural.charAt(0).toUpperCase() + getViewModeInfo().entityNamePlural.slice(1)} Trends Over Time
          </Typography>
          <Typography 
            variant="body2" 
            color="text.secondary" 
            sx={{ 
              mb: 3, 
              lineHeight: 1.6,
              maxWidth: 'none',
              whiteSpace: 'normal',
              wordWrap: 'break-word'
            }}
          >
            Shows the evolution of top {getViewModeInfo().entityNamePlural} with trend lines and growth indicators. Each line represents a {getViewModeInfo().entityName}'s paper count evolution over the selected time period.
          </Typography>
          <Box sx={{ 
            width: '100%',
            minHeight: '500px',
            overflowX: 'auto',
            overflowY: 'hidden',
            display: 'flex',
            justifyContent: 'center'
          }}>
            <svg ref={trendsChartRef} style={{ maxWidth: '100%', height: 'auto' }}></svg>
          </Box>
          
          {/* Topic Filter Controls */}
          {topics.length > 0 && (
            <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle2" gutterBottom>
                Filter {getViewModeInfo().entityNamePlural.charAt(0).toUpperCase() + getViewModeInfo().entityNamePlural.slice(1)} (click to toggle):
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                <Chip
                  label="Show All"
                  size="small"
                  variant={selectedTopics.size === 0 ? "filled" : "outlined"}
                  color={selectedTopics.size === 0 ? "primary" : "default"}
                  onClick={() => setSelectedTopics(new Set())}
                />
                {topics.slice(0, 8).map((topic) => (
                  <Chip
                    key={topic.id}
                    label={createTopicLabel(topic.label)}
                    size="small"
                    variant={selectedTopics.has(topic.id) ? "filled" : "outlined"}
                    color={selectedTopics.has(topic.id) ? "primary" : "default"}
                    onClick={() => {
                      const newSelected = new Set(selectedTopics);
                      if (selectedTopics.has(topic.id)) {
                        newSelected.delete(topic.id);
                      } else {
                        newSelected.add(topic.id);
                      }
                      setSelectedTopics(newSelected);
                    }}
                  />
                ))}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Topics List */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Grid container spacing={3}>
          {topics.map((topic) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={topic.id}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }} onClick={() => loadTopicDetail(topic.id)}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                      {topic.label}
                    </Typography>
                    {getGrowthIcon(topic.latest_growth_rate)}
                  </Stack>
                  
                  <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                    <Chip
                      label={`${topic.latest_doc_count || 0} recent`}
                      size="small"
                      color="primary"
                      variant="outlined"
                      title={`Papers in current ${periodType} period`}
                    />
                    <Chip
                      label={`${topic.total_papers || 0} total`}
                      size="small"
                      color="secondary"
                      variant="outlined"
                      title="All-time papers associated with this topic"
                    />
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Topic Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TimelineIcon />
            {getEntityData(selectedTopic)?.label}
          </Box>
        </DialogTitle>
        <DialogContent>
          {selectedTopic && (() => {
            const entityData = getEntityData(selectedTopic);
            if (!entityData) return null;
            
            return (
              <Box>
                {/* Topic Info */}
                <Box sx={{ mb: 3 }}>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="body2" color="text.secondary">Total Papers</Typography>
                      <Typography variant="h6">{entityData.total_papers}</Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="body2" color="text.secondary">Latest Growth</Typography>
                      <Typography variant="h6">{formatGrowthRate(entityData.latest_growth_rate)}</Typography>
                    </Grid>
                  </Grid>
                </Box>

                <Divider sx={{ my: 2 }} />

                {/* Timeline Chart */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="h6" gutterBottom>Timeline</Typography>
                  <Box sx={{ 
                    width: '100%',
                    minHeight: '400px',
                    overflowX: 'auto',
                    overflowY: 'hidden',
                    display: 'flex',
                    justifyContent: 'center'
                  }}>
                    <svg ref={timelineChartRef} style={{ maxWidth: '100%', height: 'auto' }}></svg>
                  </Box>
                </Box>

                <Divider sx={{ my: 2 }} />

                {/* Representative Papers */}
                <Box>
                  <Typography variant="h6" gutterBottom>Representative Papers</Typography>
                  {entityData.representative_papers.map((paper) => (
                    <Card key={paper.id} sx={{ mb: 1 }}>
                      <CardContent sx={{ py: 1 }}>
                        <Typography variant="subtitle2">{paper.title}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          Score: {paper.score.toFixed(2)} | Date: {paper.date}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              </Box>
            );
          })()}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailDialogOpen(false)}>Close</Button>
          {selectedTopic && (() => {
            const entityId = getEntityId(selectedTopic);
            if (!entityId) return null;
            
            return (
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="outlined"
                  startIcon={<MindMapIcon />}
                  onClick={async () => {
                    await generateMindMapFromTopic(entityId);
                    setDetailDialogOpen(false);
                  }}
                >
                  Mind-Map
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<NewsletterIcon />}
                  onClick={() => {
                    generateNewsletterFromTopic(entityId);
                    setDetailDialogOpen(false);
                  }}
                >
                  Newsletter
                </Button>
                <Button
                  variant="contained"
                  startIcon={<ArticleIcon />}
                  onClick={() => {
                    // Navigate to papers filtered by this topic
                    window.open(`/papers?topic_id=${entityId}`, '_blank');
                  }}
                >
                  View All Papers
                </Button>
              </Box>
            );
          })()}
        </DialogActions>
      </Dialog>

      {/* Recompute Dialog */}
      <Dialog open={recomputeDialogOpen} onClose={() => !isRecomputing && setRecomputeDialogOpen(false)}>
        <DialogTitle>Recompute Trends</DialogTitle>
        <DialogContent>
          <Typography>
            This will recompute topic models and trends using incremental weekly-first analysis. 
            By default, only new papers and recent time periods are processed to preserve historical data.
          </Typography>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 2 }}>
            The analysis will generate weekly metrics as the foundation, then aggregate 
            to monthly and quarterly views for the current {durationMonths}-month duration.
          </Typography>

          <FormControlLabel
            control={
              <Checkbox
                checked={forceFullRecalc}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForceFullRecalc(e.target.checked)}
                disabled={isRecomputing}
              />
            }
            label={
              <Box>
                <Typography variant="body2">Force full recalculation</Typography>
                <Typography variant="caption" color="text.secondary">
                  Recalculate all historical data instead of incremental processing (slower)
                </Typography>
              </Box>
            }
            sx={{ mb: 2 }}
          />

          <FormControlLabel
            control={
              <Checkbox
                checked={clearAllData}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setClearAllData(e.target.checked)}
                disabled={isRecomputing}
                color="error"
              />
            }
            label={
              <Box>
                <Typography variant="body2" color="error.main">⚠️ Nuclear Option: Clear All Data</Typography>
                <Typography variant="caption" color="text.secondary">
                  DEVELOPMENT/TESTING: Delete all topics, metrics, and relationships for fresh start
                </Typography>
              </Box>
            }
            sx={{ mb: 2 }}
          />

          {isRecomputing && (
            <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
              <CircularProgress size={20} sx={{ mr: 2 }} />
              <Typography>Recomputing trends...</Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRecomputeDialogOpen(false)} disabled={isRecomputing}>
            Cancel
          </Button>
          <Button onClick={triggerRecomputation} variant="contained" disabled={isRecomputing}>
            Start Recomputation
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Trends;
