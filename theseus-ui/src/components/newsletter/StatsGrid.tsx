import React from 'react';
import { Box, Typography, Grid, Paper } from '@mui/material';
import DescriptionIcon from '@mui/icons-material/Description';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import PendingIcon from '@mui/icons-material/Pending';
import type { TaskMetadata } from './types';

interface StatsGridProps {
    metadata: TaskMetadata;
    taskMessage?: string;
}

const safeNumber = (value: number | undefined | null) =>
    typeof value === 'number' && !Number.isNaN(value) ? value : 0;

const pickDefinedNumber = (...values: (number | undefined | null)[]): number => {
    for (const val of values) {
        if (typeof val === 'number' && !Number.isNaN(val)) {
            return val;
        }
    }
    return 0;
};

const hasPositiveNumber = (...values: (number | undefined | null)[]) =>
    values.some((value) => typeof value === 'number' && !Number.isNaN(value) && value > 0);

const parseRankProgress = (message?: string) => {
    if (!message) return null;

    const match = message.match(/Ranking paper\s+(\d+)\s*\/\s*(\d+)/i);
    if (!match) return null;

    const scored = Number(match[1]);
    const total = Number(match[2]);

    if (Number.isNaN(scored) || Number.isNaN(total) || total <= 0) {
        return null;
    }

    return {
        scored,
        total,
        pending: Math.max(total - scored, 0),
    };
};

export const StatsGrid: React.FC<StatsGridProps> = ({ metadata, taskMessage }) => {
    const summary = metadata.scoring_summary || {};
    const serverStats = metadata.server_stats || [];
    const parsedRank = parseRankProgress(taskMessage);
    const hasUsableSummary = hasPositiveNumber(
        summary.total,
        summary.completed,
        summary.failed,
        summary.pending,
        summary.in_progress,
        summary.pending_plus_in_progress
    );

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

    const normalizedSummary = hasUsableSummary
        ? summary
        : {
            total: pickDefinedNumber(metadata.papers_to_score, parsedRank?.total, serverAggregates.total),
            completed: pickDefinedNumber(metadata.papers_scored, parsedRank?.scored, serverAggregates.completed),
            failed: pickDefinedNumber(metadata.papers_failed, serverAggregates.failed),
            pending: pickDefinedNumber(
                metadata.papers_pending,
                parsedRank?.pending,
                Math.max(serverAggregates.total - (serverAggregates.completed + serverAggregates.failed + serverAggregates.inProgress), 0)
            ),
            in_progress: pickDefinedNumber(metadata.papers_in_progress, serverAggregates.inProgress),
            pending_plus_in_progress: undefined,
        };

    const papersDiscovered = safeNumber(metadata.papers_discovered);
    const totalToScore = pickDefinedNumber(
        normalizedSummary.total,
        metadata.papers_to_score,
        parsedRank?.total,
        papersDiscovered,
        serverAggregates.total
    );

    const papersScored = pickDefinedNumber(
        normalizedSummary.completed,
        metadata.papers_scored,
        parsedRank?.scored,
        serverAggregates.completed
    );

    const papersFailed = pickDefinedNumber(
        normalizedSummary.failed,
        metadata.papers_failed,
        serverAggregates.failed
    );

    const papersInProgress = pickDefinedNumber(
        normalizedSummary.in_progress,
        metadata.papers_in_progress,
        serverAggregates.inProgress
    );

    const pendingRaw = pickDefinedNumber(
        normalizedSummary.pending,
        metadata.papers_pending,
        parsedRank?.pending,
        Math.max(serverAggregates.total - (serverAggregates.completed + serverAggregates.failed + serverAggregates.inProgress), 0)
    );

    const pendingDisplay = pickDefinedNumber(
        normalizedSummary.pending_plus_in_progress,
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
