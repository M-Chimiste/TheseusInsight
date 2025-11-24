import React from 'react';
import { Box, Typography, Grid, Paper } from '@mui/material';
import DescriptionIcon from '@mui/icons-material/Description';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import PendingIcon from '@mui/icons-material/Pending';
import type { TaskMetadata } from './types';

interface StatsGridProps {
    metadata: TaskMetadata;
}

const safeNumber = (value: number | undefined | null) =>
    typeof value === 'number' && !Number.isNaN(value) ? value : 0;

const pickValue = (...values: (number | undefined)[]): number => {
    for (const val of values) {
        if (val !== undefined && val !== null) {
            return val;
        }
    }
    return 0;
};

export const StatsGrid: React.FC<StatsGridProps> = ({ metadata }) => {
    const summary = metadata.scoring_summary || {};
    const serverStats = metadata.server_stats || [];

    const serverAggregates = serverStats.reduce(
        (acc, stat) => {
            const completed = safeNumber(stat.completed);
            const failed = safeNumber(stat.failed);
            const inProgress = safeNumber(stat.in_progress);
            const total = safeNumber(stat.total);
            return {
                completed: acc.completed + completed,
                failed: acc.failed + failed,
                inProgress: acc.inProgress + inProgress,
                total: acc.total + total,
            };
        },
        { completed: 0, failed: 0, inProgress: 0, total: 0 }
    );

    const papersDiscovered = safeNumber(metadata.papers_discovered);
    const totalToScore = pickValue(
        safeNumber(summary.total),
        safeNumber(metadata.papers_to_score),
        papersDiscovered,
        serverAggregates.total
    );

    const papersScored = pickValue(
        safeNumber(summary.completed),
        safeNumber(metadata.papers_scored),
        serverAggregates.completed
    );

    const papersFailed = pickValue(
        safeNumber(summary.failed),
        safeNumber(metadata.papers_failed),
        serverAggregates.failed
    );

    const papersInProgress = pickValue(
        safeNumber(summary.in_progress),
        safeNumber(metadata.papers_in_progress),
        serverAggregates.inProgress
    );

    const pendingRaw = pickValue(
        safeNumber(summary.pending),
        safeNumber(metadata.papers_pending),
        Math.max(serverAggregates.total - (serverAggregates.completed + serverAggregates.failed + serverAggregates.inProgress), 0)
    );

    const pendingDisplay = pickValue(
        safeNumber(summary.pending_plus_in_progress),
        pendingRaw + papersInProgress,
        Math.max(totalToScore - (papersScored + papersFailed), 0)
    );

    const stats = [
        {
            label: 'Papers Discovered',
            value: Math.max(papersDiscovered, totalToScore),
            icon: <DescriptionIcon />
        },
        {
            label: 'Scored',
            value: papersScored,
            icon: <CheckCircleIcon color="success" />
        },
        {
            label: 'Failed',
            value: papersFailed,
            icon: <CancelIcon color="error" />
        },
        {
            label: 'Pending',
            value: Math.max(pendingDisplay, 0),
            icon: <PendingIcon color="warning" />
        }
    ];

    return (
        <Grid container spacing={2}>
            {stats.map((stat) => (
                <Grid size={{ xs: 6, sm: 3 }} key={stat.label}>
                    <Paper elevation={2} sx={{ p: 2, textAlign: 'center' }}>
                        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
                            {stat.icon}
                        </Box>
                        <Typography variant="h4" fontWeight="bold">
                            {stat.value.toLocaleString()}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            {stat.label}
                        </Typography>
                    </Paper>
                </Grid>
            ))}
        </Grid>
    );
};
