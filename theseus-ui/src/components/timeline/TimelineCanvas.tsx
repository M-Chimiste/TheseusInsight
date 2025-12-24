import React, { useRef, useEffect, useState } from 'react';
import { Box, Popover, Typography, List, ListItem, ListItemText, Button, Chip } from '@mui/material';
import * as d3 from 'd3';
import type { TimelineDataResponse, TimelinePeriodData, TimelineKeyPaper } from '../../services/api';

interface TimelineCanvasProps {
  data: TimelineDataResponse;
  zoomLevel: 'year' | 'quarter' | 'month' | 'week';
  isDarkMode: boolean;
  onPeriodClick: (topicId: number, periodStart: string, periodEnd: string) => void;
}

// Phase colors
const PHASE_COLORS = {
  emerging: '#4caf50',   // Green
  growth: '#2196f3',     // Blue
  stable: '#9e9e9e',     // Gray
  declining: '#f44336',  // Red
  forecast: '#ff9800',   // Orange
};

const TimelineCanvas: React.FC<TimelineCanvasProps> = ({
  data,
  zoomLevel,
  isDarkMode,
  onPeriodClick,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Popover state
  const [anchorEl, setAnchorEl] = useState<SVGElement | null>(null);
  const [popoverData, setPopoverData] = useState<{
    topicId: number;
    topicLabel: string;
    period: TimelinePeriodData;
  } | null>(null);

  // Calculate dimensions
  const margin = { top: 40, right: 40, bottom: 60, left: 200 };
  const rowHeight = 60;
  const height = margin.top + margin.bottom + data.topics.length * rowHeight;

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

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Collect all dates for x-scale
    const allDates: Date[] = [];
    data.topics.forEach(topic => {
      topic.periods.forEach(period => {
        allDates.push(new Date(period.period_start));
        allDates.push(new Date(period.period_end));
      });
    });

    if (allDates.length === 0) return;

    // X scale (time)
    const xScale = d3.scaleTime()
      .domain([d3.min(allDates)!, d3.max(allDates)!])
      .range([0, innerWidth]);

    // Y scale (topics)
    const yScale = d3.scaleBand()
      .domain(data.topics.map(t => t.topic_id.toString()))
      .range([0, innerHeight])
      .padding(0.2);

    // Get max doc count for radius scaling
    const maxDocCount = d3.max(data.topics.flatMap(t => t.periods.map(p => p.doc_count))) || 1;

    // Radius scale
    const radiusScale = d3.scaleSqrt()
      .domain([0, maxDocCount])
      .range([4, Math.min(yScale.bandwidth() / 2 - 2, 25)]);

    // Draw grid lines
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

    // Draw topic labels on the left
    g.selectAll('.topic-label')
      .data(data.topics)
      .join('text')
      .attr('class', 'topic-label')
      .attr('x', -10)
      .attr('y', d => (yScale(d.topic_id.toString()) || 0) + yScale.bandwidth() / 2)
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'middle')
      .style('fill', isDarkMode ? '#e0e0e0' : '#333')
      .style('font-size', '12px')
      .style('font-weight', 500)
      .text(d => truncateLabel(d.topic_label, 25));

    // Draw horizontal swim lanes
    g.selectAll('.swim-lane')
      .data(data.topics)
      .join('rect')
      .attr('class', 'swim-lane')
      .attr('x', 0)
      .attr('y', d => yScale(d.topic_id.toString()) || 0)
      .attr('width', innerWidth)
      .attr('height', yScale.bandwidth())
      .attr('fill', (_, i) => isDarkMode
        ? (i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent')
        : (i % 2 === 0 ? 'rgba(0,0,0,0.02)' : 'transparent'));

    // Draw period nodes
    data.topics.forEach(topic => {
      const topicG = g.append('g')
        .attr('class', `topic-${topic.topic_id}`);

      // Draw connecting line
      const sortedPeriods = [...topic.periods].sort(
        (a, b) => new Date(a.period_start).getTime() - new Date(b.period_start).getTime()
      );

      if (sortedPeriods.length > 1) {
        topicG.append('path')
          .datum(sortedPeriods)
          .attr('fill', 'none')
          .attr('stroke', isDarkMode ? '#555' : '#ccc')
          .attr('stroke-width', 2)
          .attr('d', d3.line<TimelinePeriodData>()
            .x(d => xScale(new Date(d.period_start)))
            .y(() => (yScale(topic.topic_id.toString()) || 0) + yScale.bandwidth() / 2)
            .curve(d3.curveMonotoneX)
          );
      }

      // Draw period circles
      topicG.selectAll('.period-node')
        .data(topic.periods)
        .join('circle')
        .attr('class', 'period-node')
        .attr('cx', d => xScale(new Date(d.period_start)))
        .attr('cy', (yScale(topic.topic_id.toString()) || 0) + yScale.bandwidth() / 2)
        .attr('r', d => radiusScale(d.doc_count))
        .attr('fill', d => d.is_forecast
          ? 'transparent'
          : PHASE_COLORS[d.phase as keyof typeof PHASE_COLORS] || PHASE_COLORS.stable
        )
        .attr('stroke', d => d.is_forecast
          ? PHASE_COLORS.forecast
          : PHASE_COLORS[d.phase as keyof typeof PHASE_COLORS] || PHASE_COLORS.stable
        )
        .attr('stroke-width', d => d.is_forecast ? 2 : 1)
        .attr('stroke-dasharray', d => d.is_forecast ? '4,2' : 'none')
        .attr('opacity', 0.85)
        .style('cursor', 'pointer')
        .on('mouseenter', function(event, d) {
          d3.select(this)
            .transition()
            .duration(150)
            .attr('r', radiusScale(d.doc_count) * 1.2)
            .attr('opacity', 1);

          setAnchorEl(this as unknown as SVGElement);
          setPopoverData({
            topicId: topic.topic_id,
            topicLabel: topic.topic_label,
            period: d,
          });
        })
        .on('mouseleave', function(_, d) {
          d3.select(this)
            .transition()
            .duration(150)
            .attr('r', radiusScale(d.doc_count))
            .attr('opacity', 0.85);

          // Don't close popover immediately - let it close on its own
        })
        .on('click', (_, d) => {
          onPeriodClick(topic.topic_id, d.period_start, d.period_end);
        });
    });

    // Add title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', 24)
      .attr('text-anchor', 'middle')
      .style('fill', isDarkMode ? '#e0e0e0' : '#333')
      .style('font-size', '16px')
      .style('font-weight', 600)
      .text(`Topic Evolution Timeline (${zoomLevel}ly)`);

  }, [data, zoomLevel, isDarkMode, height, margin]);

  // Handle popover close
  const handlePopoverClose = () => {
    setAnchorEl(null);
    setPopoverData(null);
  };

  const open = Boolean(anchorEl) && Boolean(popoverData);

  return (
    <Box ref={containerRef} sx={{ width: '100%', overflowX: 'auto' }}>
      <svg ref={svgRef} />

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handlePopoverClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        disableRestoreFocus
        sx={{ pointerEvents: 'auto' }}
      >
        {popoverData && (
          <Box sx={{ p: 2, maxWidth: 350 }}>
            <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
              {popoverData.topicLabel}
            </Typography>

            <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap' }}>
              <Chip
                label={popoverData.period.phase}
                size="small"
                sx={{
                  bgcolor: PHASE_COLORS[popoverData.period.phase as keyof typeof PHASE_COLORS],
                  color: 'white',
                  textTransform: 'capitalize',
                }}
              />
              <Chip
                label={`${popoverData.period.doc_count} papers`}
                size="small"
                variant="outlined"
              />
              {popoverData.period.growth_rate !== null && popoverData.period.growth_rate !== undefined && (
                <Chip
                  label={`${(popoverData.period.growth_rate * 100).toFixed(0)}% growth`}
                  size="small"
                  variant="outlined"
                  color={popoverData.period.growth_rate > 0 ? 'success' : 'error'}
                />
              )}
            </Box>

            <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
              {popoverData.period.period_start} — {popoverData.period.period_end}
            </Typography>

            {popoverData.period.key_papers && popoverData.period.key_papers.length > 0 && (
              <>
                <Typography variant="caption" fontWeight="bold" sx={{ mt: 1 }}>
                  Key Papers:
                </Typography>
                <List dense sx={{ py: 0 }}>
                  {popoverData.period.key_papers.slice(0, 3).map((paper: TimelineKeyPaper) => (
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

            <Button
              size="small"
              variant="text"
              onClick={() => {
                onPeriodClick(
                  popoverData.topicId,
                  popoverData.period.period_start,
                  popoverData.period.period_end
                );
                handlePopoverClose();
              }}
              sx={{ mt: 1 }}
            >
              View All Papers →
            </Button>
          </Box>
        )}
      </Popover>
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
