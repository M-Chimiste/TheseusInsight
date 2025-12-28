import React from 'react';
import { Box, Typography } from '@mui/material';
import Confetti from 'react-confetti';
import { useWindowSize } from 'react-use';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

interface SuccessCelebrationProps {
    show: boolean;
}

export const SuccessCelebration: React.FC<SuccessCelebrationProps> = ({ show }) => {
    const { width, height } = useWindowSize();

    if (!show) return null;

    return (
        <>
            <Confetti
                width={width}
                height={height}
                recycle={false}
                numberOfPieces={200}
            />
            <Box
                sx={{
                    textAlign: 'center',
                    py: 4,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 2
                }}
            >
                <CheckCircleIcon sx={{ fontSize: 80, color: 'success.main' }} />
                <Typography variant="h4" fontWeight="bold" color="success.main">
                    Newsletter Generated Successfully!
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Your newsletter has been created and sent to recipients.
                </Typography>
            </Box>
        </>
    );
};
