import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { Box, Paper, Typography, List, ListItem, ListItemText, Chip, Link } from '@mui/material';
import * as d3 from 'd3';
import type { TimelineDataResponse, TimelinePeriodData, TimelineKeyPaper } from '../../services/api';

interface TimelineCanvasProps {
  data: TimelineDataResponse;
  zoomLevel: 'year' | 'quarter' | 'month' | 'week';
  isDarkMode: boolean;
  onPeriodClick: (topicId: number, periodStart: string, periodEnd: string) => void;
}

// Color palette for streams - vibrant, futuristic colors
const STREAM_COLORS = [
  '#00d4ff', // Cyan
  '#7c3aed', // Purple
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#ef4444', // Red
  '#ec4899', // Pink
  '#06b6d4', // Teal
  '#8b5cf6', // Violet
  '#22c55e', // Green
  '#f97316', // Orange
];

// Phase colors for legend/chips
const PHASE_COLORS = {
  emerging: '#4caf50',   // Green
  growth: '#2196f3',     // Blue
  stable: '#9e9e9e',     // Gray
  declining: '#f44336',  // Red
};

interface StreamDataPoint {
  date: Date;
  [key: string]: number | Date;
}

const TimelineCanvas: React.FC<TimelineCanvasProps> = ({
  data,
  zoomLevel,
  isDarkMode,
  onPeriodClick,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Tooltip state
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [tooltipData, setTooltipData] = useState<{
    topicId: number;
    topicLabel: string;
    period: TimelinePeriodData;
    color: string;
  } | null>(null);
  const [hoveredTopicId, setHoveredTopicId] = useState<number | null>(null);

  // Topic color mapping
  const topicColors = useMemo(() => {
    const colorMap: Record<number, string> = {};
    data.topics.forEach((topic, idx) => {
      colorMap[topic.topic_id] = STREAM_COLORS[idx % STREAM_COLORS.length];
    });
    return colorMap;
  }, [data.topics]);

  // Clear hide timeout
  const clearHideTimeout = useCallback(() => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  }, []);

  // Hide tooltip immediately
  const hideTooltip = useCallback(() => {
    clearHideTimeout();
    setTooltipPosition(null);
    setTooltipData(null);
    setHoveredTopicId(null);
  }, [clearHideTimeout]);

  // Start hide timeout
  const startHideTimeout = useCallback(() => {
    clearHideTimeout();
    hideTimeoutRef.current = setTimeout(() => {
      setTooltipPosition(null);
      setTooltipData(null);
    }, 300); // Shorter timeout - 300ms
  }, [clearHideTimeout]);

  useEffect(() => {
    return () => clearHideTimeout();
  }, [clearHideTimeout]);

  // Calculate dimensions
  const margin = { top: 60, right: 40, bottom: 60, left: 40 };
  const height = 400;

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || data.topics.length === 0) return;

    const containerWidth = containerRef.current.clientWidth;
    const width = Math.max(800, containerWidth);
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Add gradient definitions
    const defs = svg.append('defs');

    // Add glow filter
    const filter = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-20%')
      .attr('y', '-20%')
      .attr('width', '140%')
      .attr('height', '140%');

    filter.append('feGaussianBlur')
      .attr('stdDeviation', '3')
      .attr('result', 'coloredBlur');

    const feMerge = filter.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Create gradients for each topic
    data.topics.forEach((topic) => {
      const color = topicColors[topic.topic_id];
      const gradient = defs.append('linearGradient')
        .attr('id', `gradient-${topic.topic_id}`)
        .attr('x1', '0%')
        .attr('y1', '0%')
        .attr('x2', '0%')
        .attr('y2', '100%');

      gradient.append('stop')
        .attr('offset', '0%')
        .attr('stop-color', color)
        .attr('stop-opacity', 0.9);

      gradient.append('stop')
        .attr('offset', '100%')
        .attr('stop-color', d3.color(color)?.darker(0.5)?.toString() || color)
        .attr('stop-opacity', 0.7);
    });

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Collect all unique dates across all topics
    const allDates = new Set<string>();
    data.topics.forEach(topic => {
      topic.periods.forEach(period => {
        allDates.add(period.period_start);
      });
    });

    const sortedDates = Array.from(allDates).sort();

    if (sortedDates.length === 0) return;

    // Create stream data structure
    const streamData: StreamDataPoint[] = sortedDates.map(dateStr => {
      const point: StreamDataPoint = { date: new Date(dateStr) };
      data.topics.forEach(topic => {
        const period = topic.periods.find(p => p.period_start === dateStr);
        point[topic.topic_id.toString()] = period ? period.doc_count : 0;
      });
      return point;
    });

    // Topic IDs as keys for stacking
    const topicKeys = data.topics.map(t => t.topic_id.toString());

    // Create stack generator
    const stack = d3.stack<StreamDataPoint>()
      .keys(topicKeys)
      .value((d, key) => (d[key] as number) || 0)
      .order(d3.stackOrderInsideOut)
      .offset(d3.stackOffsetWiggle);

    const stackedData = stack(streamData);

    // X scale (time)
    const xScale = d3.scaleTime()
      .domain(d3.extent(streamData, d => d.date) as [Date, Date])
      .range([0, innerWidth]);

    // Y scale - find the extent of the stacked data
    const yMin = d3.min(stackedData, layer => d3.min(layer, d => d[0])) || 0;
    const yMax = d3.max(stackedData, layer => d3.max(layer, d => d[1])) || 0;

    const yScale = d3.scaleLinear()
      .domain([yMin, yMax])
      .range([innerHeight, 0]);

    // Area generator with smooth curves
    const area = d3.area<d3.SeriesPoint<StreamDataPoint>>()
      .x(d => xScale(d.data.date))
      .y0(d => yScale(d[0]))
      .y1(d => yScale(d[1]))
      .curve(d3.curveBasis);

    // Draw streams
    const streams = g.selectAll('.stream')
      .data(stackedData)
      .join('path')
      .attr('class', 'stream')
      .attr('d', area)
      .attr('fill', d => `url(#gradient-${d.key})`)
      .attr('stroke', d => topicColors[parseInt(d.key)])
      .attr('stroke-width', 0.5)
      .attr('opacity', 0.85)
      .style('cursor', 'pointer')
      .style('transition', 'opacity 0.3s ease, filter 0.3s ease')
      .on('mouseenter', function(event, d) {
        const topicId = parseInt(d.key);
        setHoveredTopicId(topicId);

        // Highlight this stream, dim others using D3
        streams.attr('opacity', (sd) => parseInt(sd.key) === topicId ? 0.85 : 0.2);
        d3.select(this).style('filter', 'url(#glow)');

        // Find the period closest to mouse position
        const [mouseX] = d3.pointer(event, g.node());
        const dateAtMouse = xScale.invert(mouseX);

        // Find the closest period
        const topic = data.topics.find(t => t.topic_id === topicId);
        if (!topic) return;

        let closestPeriod = topic.periods[0];
        let minDist = Infinity;
        topic.periods.forEach(p => {
          const periodDate = new Date(p.period_start);
          const dist = Math.abs(periodDate.getTime() - dateAtMouse.getTime());
          if (dist < minDist) {
            minDist = dist;
            closestPeriod = p;
          }
        });

        clearHideTimeout();
        setTooltipPosition({ x: event.clientX, y: event.clientY });
        setTooltipData({
          topicId: topicId,
          topicLabel: topic.topic_label,
          period: closestPeriod,
          color: topicColors[topicId],
        });
      })
      .on('mousemove', function(event, d) {
        const topicId = parseInt(d.key);
        const [mouseX] = d3.pointer(event, g.node());
        const dateAtMouse = xScale.invert(mouseX);

        const topic = data.topics.find(t => t.topic_id === topicId);
        if (!topic) return;

        let closestPeriod = topic.periods[0];
        let minDist = Infinity;
        topic.periods.forEach(p => {
          const periodDate = new Date(p.period_start);
          const dist = Math.abs(periodDate.getTime() - dateAtMouse.getTime());
          if (dist < minDist) {
            minDist = dist;
            closestPeriod = p;
          }
        });

        setTooltipPosition({ x: event.clientX, y: event.clientY });
        setTooltipData(prev => prev ? {
          ...prev,
          period: closestPeriod,
        } : null);
      })
      .on('mouseleave', function() {
        // Reset all streams to normal opacity
        streams.attr('opacity', 0.85).style('filter', 'none');
        setHoveredTopicId(null);
        startHideTimeout();
      })
      .on('click', function(event, d) {
        const topicId = parseInt(d.key);
        const [mouseX] = d3.pointer(event, g.node());
        const dateAtMouse = xScale.invert(mouseX);

        const topic = data.topics.find(t => t.topic_id === topicId);
        if (!topic) return;

        let closestPeriod = topic.periods[0];
        let minDist = Infinity;
        topic.periods.forEach(p => {
          const periodDate = new Date(p.period_start);
          const dist = Math.abs(periodDate.getTime() - dateAtMouse.getTime());
          if (dist < minDist) {
            minDist = dist;
            closestPeriod = p;
          }
        });

        onPeriodClick(topicId, closestPeriod.period_start, closestPeriod.period_end);
      });

    // Draw X axis
    const xAxis = d3.axisBottom(xScale)
      .ticks(getTickCount(zoomLevel))
      .tickFormat(getTickFormat(zoomLevel) as (domainValue: Date | d3.NumberValue, index: number) => string);

    g.append('g')
      .attr('class', 'x-axis')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis)
      .selectAll('text')
      .style('fill', isDarkMode ? '#e0e0e0' : '#333')
      .style('font-size', '11px');

    g.selectAll('.x-axis path, .x-axis line')
      .style('stroke', isDarkMode ? '#555' : '#ccc');

    // Draw vertical grid lines
    g.selectAll('.grid-line')
      .data(xScale.ticks(getTickCount(zoomLevel)))
      .join('line')
      .attr('class', 'grid-line')
      .attr('x1', d => xScale(d))
      .attr('x2', d => xScale(d))
      .attr('y1', 0)
      .attr('y2', innerHeight)
      .attr('stroke', isDarkMode ? '#333' : '#eee')
      .attr('stroke-dasharray', '3,3');

    // Add title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', 28)
      .attr('text-anchor', 'middle')
      .style('fill', isDarkMode ? '#e0e0e0' : '#333')
      .style('font-size', '16px')
      .style('font-weight', 600)
      .text(`Research Interest Flow (${zoomLevel}ly)`);

    // Legend is now rendered as React component below the SVG for better text handling

  }, [data, zoomLevel, isDarkMode, height, margin, topicColors, clearHideTimeout, startHideTimeout, onPeriodClick]);

  const showTooltip = tooltipPosition !== null && tooltipData !== null;

  return (
    <Box ref={containerRef} sx={{ width: '100%', overflowX: 'auto', position: 'relative' }}>
      {/* Topic Legend */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mb: 2, px: 1 }}>
        {data.topics.map((topic) => (
          <Box
            key={topic.topic_id}
            onClick={() => {
              const firstPeriod = topic.periods[0];
              if (firstPeriod) {
                onPeriodClick(topic.topic_id, firstPeriod.period_start, firstPeriod.period_end);
              }
            }}
            onMouseEnter={() => setHoveredTopicId(topic.topic_id)}
            onMouseLeave={() => setHoveredTopicId(null)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
              cursor: 'pointer',
              px: 1,
              py: 0.5,
              borderRadius: 1,
              bgcolor: hoveredTopicId === topic.topic_id ? 'action.hover' : 'transparent',
              transition: 'background-color 0.2s',
              '&:hover': { bgcolor: 'action.hover' },
            }}
          >
            <Box
              sx={{
                width: 14,
                height: 14,
                borderRadius: 0.5,
                bgcolor: topicColors[topic.topic_id],
                opacity: hoveredTopicId === null || hoveredTopicId === topic.topic_id ? 0.85 : 0.3,
                flexShrink: 0,
              }}
            />
            <Typography
              variant="caption"
              sx={{
                color: hoveredTopicId === null || hoveredTopicId === topic.topic_id ? 'text.primary' : 'text.disabled',
                fontWeight: hoveredTopicId === topic.topic_id ? 600 : 400,
                transition: 'all 0.2s',
              }}
            >
              {topic.topic_label}
            </Typography>
          </Box>
        ))}
      </Box>

      <svg ref={svgRef} />

      {/* Mouse-following tooltip */}
      {showTooltip && tooltipData && tooltipPosition && (
        <Paper
          elevation={8}
          onMouseEnter={clearHideTimeout}
          onMouseLeave={hideTooltip}
          sx={{
            position: 'fixed',
            // Position left of cursor if near right edge (within 400px of right side)
            left: tooltipPosition.x > window.innerWidth - 400
              ? tooltipPosition.x - 365
              : tooltipPosition.x + 15,
            top: tooltipPosition.y - 10,
            p: 2,
            maxWidth: 350,
            zIndex: 9999,
            bgcolor: 'background.paper',
            transform: 'translateY(-100%)',
            // Border on appropriate side based on position
            borderLeft: tooltipPosition.x > window.innerWidth - 400 ? 'none' : `4px solid ${tooltipData.color}`,
            borderRight: tooltipPosition.x > window.innerWidth - 400 ? `4px solid ${tooltipData.color}` : 'none',
          }}
        >
          <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
            {tooltipData.topicLabel}
          </Typography>

          <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap' }}>
            <Chip
              label={tooltipData.period.phase}
              size="small"
              sx={{
                bgcolor: PHASE_COLORS[tooltipData.period.phase as keyof typeof PHASE_COLORS],
                color: 'white',
                textTransform: 'capitalize',
              }}
            />
            <Chip
              label={`${tooltipData.period.doc_count} papers`}
              size="small"
              variant="outlined"
            />
            {tooltipData.period.growth_rate !== null && tooltipData.period.growth_rate !== undefined && (
              <Chip
                label={`${(tooltipData.period.growth_rate * 100).toFixed(0)}% growth`}
                size="small"
                variant="outlined"
                color={tooltipData.period.growth_rate > 0 ? 'success' : 'error'}
              />
            )}
          </Box>

          <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
            {tooltipData.period.period_start} — {tooltipData.period.period_end}
          </Typography>

          {tooltipData.period.key_papers && tooltipData.period.key_papers.length > 0 && (
            <>
              <Typography variant="caption" fontWeight="bold" sx={{ mt: 1 }}>
                Key Papers:
              </Typography>
              <List dense sx={{ py: 0 }}>
                {tooltipData.period.key_papers.slice(0, 3).map((paper: TimelineKeyPaper) => (
                  <ListItem key={paper.id} sx={{ px: 0, py: 0.5 }}>
                    <ListItemText
                      primary={truncateLabel(paper.title, 60)}
                      primaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                ))}
              </List>
            </>
          )}

          <Link
            component="button"
            variant="caption"
            onClick={() => {
              onPeriodClick(tooltipData.topicId, tooltipData.period.period_start, tooltipData.period.period_end);
              hideTooltip();
            }}
            sx={{ mt: 1, display: 'block', cursor: 'pointer' }}
          >
            Click to view all papers →
          </Link>
        </Paper>
      )}
    </Box>
  );
};

// Helper functions
function getTickCount(zoomLevel: string): number {
  switch (zoomLevel) {
    case 'year': return 5;
    case 'quarter': return 8;
    case 'month': return 12;
    case 'week': return 20;
    default: return 10;
  }
}

function getTickFormat(zoomLevel: string): (date: Date) => string {
  switch (zoomLevel) {
    case 'year': return d3.timeFormat('%Y');
    case 'quarter': return d3.timeFormat('Q%q %Y');
    case 'month': return d3.timeFormat('%b %Y');
    case 'week': return d3.timeFormat('%b %d');
    default: return d3.timeFormat('%b %Y');
  }
}

function truncateLabel(label: string, maxLength: number): string {
  if (label.length <= maxLength) return label;
  return label.substring(0, maxLength - 3) + '...';
}

export default TimelineCanvas;
