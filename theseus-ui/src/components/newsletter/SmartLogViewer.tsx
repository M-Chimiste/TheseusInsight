import React, { useEffect, useRef, useState } from 'react';
import { Box, Typography, Paper, List, ListItem, ListItemText, Accordion, AccordionSummary, AccordionDetails, FormControlLabel, Switch } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

interface SmartLogViewerProps {
    logs: string[];
}

export const SmartLogViewer: React.FC<SmartLogViewerProps> = ({ logs }) => {
    const logEndRef = useRef<HTMLDivElement>(null);
    const [autoScroll, setAutoScroll] = useState(false);
    const [expanded, setExpanded] = useState(false);

    useEffect(() => {
        if (autoScroll && expanded) {
            logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs, autoScroll, expanded]);

    if (logs.length === 0) return null;

    return (
        <Paper elevation={2} sx={{ mt: 2 }}>
            <Accordion expanded={expanded} onChange={(_, isExpanded) => setExpanded(isExpanded)}>
                <AccordionSummary
                    expandIcon={<ExpandMoreIcon />}
                    aria-controls="logs-content"
                    id="logs-header"
                >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', pr: 2 }}>
                        <Typography variant="h6">
                            Pipeline Logs ({logs.length})
                        </Typography>
                        {expanded && (
                            <FormControlLabel
                                control={
                                    <Switch
                                        size="small"
                                        checked={autoScroll}
                                        onChange={(e) => setAutoScroll(e.target.checked)}
                                        onClick={(e) => e.stopPropagation()}
                                    />
                                }
                                label="Auto-scroll"
                            />
                        )}
                    </Box>
                </AccordionSummary>
                <AccordionDetails>
                    <Box
                        sx={{
                            maxHeight: 300,
                            overflow: 'auto',
                            bgcolor: 'background.default',
                            border: 1,
                            borderColor: 'divider',
                            p: 2,
                            borderRadius: 1,
                            fontFamily: 'monospace'
                        }}
                    >
                        <List dense>
                            {logs.slice(-50).map((log, index) => (
                                <ListItem key={index} sx={{ py: 0.5 }}>
                                    <ListItemText
                                        primary={log}
                                        primaryTypographyProps={{
                                            variant: 'body2',
                                            sx: { color: 'text.primary', fontFamily: 'monospace', fontSize: '0.85rem' }
                                        }}
                                    />
                                </ListItem>
                            ))}
                        </List>
                        <div ref={logEndRef} />
                    </Box>
                </AccordionDetails>
            </Accordion>
        </Paper>
    );
};
