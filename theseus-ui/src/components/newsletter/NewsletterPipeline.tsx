import React, { useEffect, useState } from 'react';
import { Box, Typography, Grid } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import PsychologyIcon from '@mui/icons-material/Psychology';
import ArticleIcon from '@mui/icons-material/Article';
import SendIcon from '@mui/icons-material/Send';
import type { TaskState } from '../../hooks/useTaskState';
import { StageCard } from './StageCard';
import { StatsGrid } from './StatsGrid';
import { ServerActivityIndicator } from './ServerActivityIndicator';
import { SmartLogViewer } from './SmartLogViewer';
import { SuccessCelebration } from './SuccessCelebration';

interface NewsletterPipelineProps {
    taskState: TaskState;
}

export const NewsletterPipeline: React.FC<NewsletterPipelineProps> = ({ taskState }) => {
    const [logs, setLogs] = useState<string[]>([]);
    const [showCelebration, setShowCelebration] = useState(false);

    // Update logs when message changes
    useEffect(() => {
        if (taskState.message && taskState.isRunning) {
            setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${taskState.message}`]);
        }
    }, [taskState.message, taskState.isRunning]);

    // Handle completion
    useEffect(() => {
        if (taskState.status === 'completed' && !showCelebration) {
            setShowCelebration(true);
            setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Pipeline completed successfully!`]);
        }
    }, [taskState.status, showCelebration]);

    const metadata = taskState.metadata || {};

    // Determine stage status
    const getStageStatus = (stageId: string) => {
        const rawStage = taskState.currentStep?.toLowerCase() || '';
        const currentStage = rawStage.includes('scoring') ? 'rank' : rawStage;

        // Mapping backend stages to UI stages
        const stageOrder = ['download', 'embed', 'rank', 'newsletter', 'email', 'podcast', 'completed'];
        const currentStageIndex = stageOrder.findIndex(s => currentStage.includes(s));
        const targetStageIndex = stageOrder.indexOf(stageId);

        if (taskState.error) return 'failed';
        if (taskState.status === 'completed') return 'completed';

        if (currentStage.includes(stageId)) return 'active';
        if (currentStageIndex > targetStageIndex) return 'completed';
        return 'pending';
    };

    // Calculate progress for active stage
    const getStageProgress = (stageId: string) => {
        const status = getStageStatus(stageId);
        if (status === 'completed') return 1;
        if (status === 'pending') return 0;
        return taskState.progress / 100; // Assuming progress is 0-100
    };

    if (!taskState.isRunning && taskState.status !== 'completed' && taskState.status !== 'failed') {
        return null; // Or return a placeholder/empty state
    }

    return (
        <Box>
            <SuccessCelebration show={showCelebration} />

            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box>
                    <Typography variant="h5" fontWeight="bold">
                        Newsletter Generation
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        {taskState.isRunning ? 'Pipeline in progress...' : 'Pipeline status'}
                    </Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                    <Typography variant="h3" fontWeight="bold" color="primary">
                        {Math.round(taskState.progress)}%
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 1 }}>
                        Total Progress
                    </Typography>
                </Box>
            </Box>

            {/* Stats Grid */}
            <Box sx={{ mb: 3 }}>
                <StatsGrid metadata={metadata} taskMessage={taskState.message} />
            </Box>

            {/* Multi-Server Activity */}
            {metadata.server_stats && metadata.server_stats.length > 0 && (
                <Box sx={{ mb: 3 }}>
                    <ServerActivityIndicator servers={metadata.server_stats} />
                </Box>
            )}

            {/* Pipeline Stages */}
            <Box sx={{ mb: 3 }}>
                <Grid container spacing={2}>
                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <StageCard
                            label="Harvest"
                            status={getStageStatus('download')}
                            progress={getStageProgress('download')}
                            icon={<DownloadIcon />}
                            description="Downloading papers from ArXiv"
                        />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <StageCard
                            label="Rank"
                            status={getStageStatus('rank') === 'pending' && getStageStatus('embed') === 'active' ? 'active' : getStageStatus('rank')}
                            progress={getStageProgress('rank')}
                            icon={<PsychologyIcon />}
                            description="Embedding & Scoring papers"
                        />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <StageCard
                            label="Generate"
                            status={getStageStatus('newsletter')}
                            progress={getStageProgress('newsletter')}
                            icon={<ArticleIcon />}
                            description="Writing newsletter sections"
                        />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <StageCard
                            label="Send Email"
                            status={getStageStatus('email') === 'pending' && getStageStatus('podcast') === 'active' ? 'active' : getStageStatus('email')}
                            progress={getStageProgress('email')}
                            icon={<SendIcon />}
                            description="Sending newsletter email"
                        />
                    </Grid>
                </Grid>
            </Box>

            {/* Logs */}
            <SmartLogViewer logs={logs} />
        </Box>
    );
};
