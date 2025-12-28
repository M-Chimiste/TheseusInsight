import React, { useEffect, useRef, useState } from 'react';
import { Box, Typography, Paper, Chip, Tooltip, Grid } from '@mui/material';
import ComputerIcon from '@mui/icons-material/Computer';
import SpeedIcon from '@mui/icons-material/Speed';
import type { ServerStats } from './types';

interface ServerActivityIndicatorProps {
    servers: ServerStats[];
}

export const ServerActivityIndicator: React.FC<ServerActivityIndicatorProps> = ({ servers }) => {
    // State for client-side throughput calculation
    const [now, setNow] = useState(Date.now());
    const metricsRef = useRef<Record<string, { startTime: number, baseCount: number }>>({});

    // Update timer every second to refresh throughput calculations
    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(timer);
    }, []);

    // Calculate throughput (papers per minute)
    const calculateThroughput = (server: ServerStats): number => {
        // Prefer backend value if available and non-zero
        if (server.throughput && server.throughput > 0) {
            return server.throughput;
        }

        // Initialize start time for new busy servers
        if (server.status === 'busy' && !metricsRef.current[server.server_id]) {
            metricsRef.current[server.server_id] = {
                startTime: Date.now(),
                baseCount: server.completed
            };
        }

        const metrics = metricsRef.current[server.server_id];
        if (!metrics) return 0;

        const durationMin = (now - metrics.startTime) / 60000;
        // Show 0 for first 5 seconds to stabilize
        if (durationMin < 0.08) return 0;

        const delta = server.completed - metrics.baseCount;
        // If delta is 0, throughput drops over time (correct behavior)
        return Math.max(0, delta / durationMin);
    };

    // Get server status color
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'busy': return 'success';
            case 'idle': return 'warning';
            case 'offline': return 'default';
            default: return 'default';
        }
    };

    return (
        <Paper elevation={2} sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ComputerIcon />
                Multi-Server Activity
            </Typography>
            
            <Grid container spacing={2} sx={{ mt: 1 }}>
                {servers.map((server) => {
                    const isBusy = server.status === 'busy';
                    return (
                        <Grid size={{ xs: 12, sm: 6, md: 4 }} key={server.server_id}>
                            <Box sx={{ 
                                border: '1px solid',
                                borderColor: isBusy ? 'success.main' : 'divider',
                                borderRadius: 1,
                                p: 2,
                                height: '100%',
                                position: 'relative',
                                transition: 'all 0.3s ease',
                                boxShadow: isBusy ? '0 0 0 1px rgba(46, 125, 50, 0.2)' : 'none',
                                animation: isBusy ? 'pulse 2s infinite' : 'none',
                                '@keyframes pulse': {
                                    '0%': { boxShadow: '0 0 0 0 rgba(46, 125, 50, 0.4)' },
                                    '70%': { boxShadow: '0 0 0 6px rgba(46, 125, 50, 0)' },
                                    '100%': { boxShadow: '0 0 0 0 rgba(46, 125, 50, 0)' }
                                }
                            }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                                    <Tooltip title={server.server_url}>
                                        <Typography variant="subtitle1" fontWeight="bold" noWrap sx={{ maxWidth: '70%' }}>
                                            {server.server_name || 'Unknown Server'}
                                        </Typography>
                                    </Tooltip>
                                    <Chip
                                        label={server.status || 'unknown'}
                                        size="small"
                                        color={getStatusColor(server.status || 'offline')}
                                        variant={isBusy ? "filled" : "outlined"}
                                    />
                                </Box>
                                
                                {/* Stats Grid */}
                                <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mb: 2 }}>
                                    <Tooltip title="Completed">
                                        <Chip
                                            label={`✓ ${server.completed}`}
                                            size="small"
                                            color="success"
                                            variant="outlined"
                                            sx={{ width: '100%', justifyContent: 'flex-start', pl: 1 }}
                                        />
                                    </Tooltip>
                                    <Tooltip title="Failed">
                                        <Chip
                                            label={`✗ ${server.failed}`}
                                            size="small"
                                            color="error"
                                            variant="outlined"
                                            sx={{ width: '100%', justifyContent: 'flex-start', pl: 1 }}
                                        />
                                    </Tooltip>
                                </Box>

                                {/* Throughput */}
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 'auto' }}>
                                    <SpeedIcon color="action" fontSize="small" />
                                    <Typography variant="h5" fontWeight="medium" color="text.primary">
                                        {calculateThroughput(server).toFixed(1)}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                                        papers/min
                                    </Typography>
                                </Box>
                                
                                <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 1 }}>
                                    {server.last_completed_at ? 
                                        `Last: ${new Date(server.last_completed_at).toLocaleTimeString()}` : 
                                        'No activity yet'
                                    }
                                </Typography>
                            </Box>
                        </Grid>
                    );
                })}
            </Grid>

            {/* Summary stats */}
            {servers.length > 0 && (
                <Box sx={{ 
                    mt: 2, 
                    pt: 2, 
                    borderTop: '1px solid',
                    borderColor: 'divider',
                    display: 'flex',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 1
                }}>
                    <Typography variant="body2" color="text.secondary">
                        <strong>Total Throughput:</strong> {
                            servers.reduce((sum, server) => sum + calculateThroughput(server), 0).toFixed(1)
                        } papers/min
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        <strong>Active Servers:</strong> {
                            servers.filter(s => s.status === 'busy').length
                        }/{servers.length}
                    </Typography>
                </Box>
            )}
        </Paper>
    );
};