import React from 'react';
import { Box, Typography, LinearProgress, Paper } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';

interface StageCardProps {
    label: string;
    status: 'pending' | 'active' | 'completed' | 'failed';
    progress: number;
    icon?: React.ReactNode;
    description?: string;
}

export const StageCard: React.FC<StageCardProps> = ({
    label,
    status,
    progress,
    icon,
    description
}) => {
    const getStatusIcon = () => {
        switch (status) {
            case 'completed': return <CheckCircleIcon sx={{ fontSize: 40 }} />;
            case 'failed': return <ErrorIcon sx={{ fontSize: 40 }} />;
            case 'pending': return <HourglassEmptyIcon sx={{ fontSize: 40 }} />;
            default: return icon;
        }
    };

    const getCardStyles = () => {
        switch (status) {
            case 'completed':
                return {
                    bgcolor: 'success.main',
                    color: 'success.contrastText',
                    elevation: 2
                };
            case 'active':
                return {
                    bgcolor: 'primary.main',
                    color: 'primary.contrastText',
                    elevation: 4
                };
            case 'failed':
                return {
                    bgcolor: 'error.main',
                    color: 'error.contrastText',
                    elevation: 2
                };
            default: // pending
                return {
                    bgcolor: 'action.disabledBackground',
                    color: 'text.disabled',
                    elevation: 1
                };
        }
    };

    const cardStyles = getCardStyles();

    return (
        <Paper
            elevation={cardStyles.elevation}
            sx={{
                p: 2,
                position: 'relative',
                bgcolor: cardStyles.bgcolor,
                color: cardStyles.color,
                border: status === 'active' ? 2 : 0,
                borderColor: 'primary.dark',
                transition: 'all 0.3s ease',
                ...(status === 'active' && {
                    animation: 'pulse-glow 2s ease-in-out infinite',
                    '@keyframes pulse-glow': {
                        '0%': {
                            boxShadow: '0 0 0 0 rgba(144, 202, 249, 0.7)',
                            transform: 'scale(1)'
                        },
                        '50%': {
                            boxShadow: '0 0 20px 10px rgba(144, 202, 249, 0)',
                            transform: 'scale(1.02)'
                        },
                        '100%': {
                            boxShadow: '0 0 0 0 rgba(144, 202, 249, 0)',
                            transform: 'scale(1)'
                        }
                    }
                })
            }}
        >
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
                <Box sx={{ color: 'inherit', display: 'flex', justifyContent: 'center' }}>
                    {icon && status === 'active' ? icon : getStatusIcon()}
                </Box>
                <Typography variant="subtitle2" fontWeight="bold" color="inherit">
                    {label}
                </Typography>
                {description && (
                    <Typography
                        variant="caption"
                        sx={{
                            color: 'inherit',
                            opacity: 0.8,
                            textAlign: 'center'
                        }}
                    >
                        {description}
                    </Typography>
                )}
                {status === 'active' && (
                    <Box sx={{ width: '100%', mt: 1 }}>
                        <LinearProgress
                            variant="determinate"
                            value={progress * 100}
                            sx={{
                                height: 6,
                                borderRadius: 3,
                                bgcolor: 'rgba(255, 255, 255, 0.3)',
                                '& .MuiLinearProgress-bar': {
                                    bgcolor: 'rgba(255, 255, 255, 0.9)'
                                }
                            }}
                        />
                        <Typography
                            variant="caption"
                            sx={{
                                mt: 0.5,
                                display: 'block',
                                textAlign: 'center',
                                color: 'inherit',
                                opacity: 0.9
                            }}
                        >
                            {Math.round(progress * 100)}%
                        </Typography>
                    </Box>
                )}
            </Box>
        </Paper>
    );
};
