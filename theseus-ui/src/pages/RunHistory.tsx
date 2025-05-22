import React, { useState, useEffect, useCallback } from 'react';
import { 
    Box, 
    Typography, 
    CircularProgress, 
    Alert, 
    Table, 
    TableBody, 
    TableCell, 
    TableContainer, 
    TableHead, 
    TableRow, 
    Paper, 
    TablePagination, 
    Grid
} from '@mui/material';
import { DatePicker, LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format } from 'date-fns'; // Correct import for date-fns v3
import { getLogs } from '../services/api';
import type { LogEntry } from '../services/api';

const RunHistory: React.FC = () => {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [fromDate, setFromDate] = useState<Date | null>(null);
    const [toDate, setToDate] = useState<Date | null>(null);

    const fetchLogs = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const fromDateStr = fromDate ? format(fromDate, 'yyyy-MM-dd') : undefined;
            const toDateStr = toDate ? format(toDate, 'yyyy-MM-dd') : undefined;
            const fetchedLogs = await getLogs(100, fromDateStr, toDateStr); // Fetch up to 100 logs for now
            setLogs(fetchedLogs);
        } catch (err) {
            console.error("Error fetching logs:", err);
            setError('Failed to fetch run history. Please try again.');
        }
        setLoading(false);
    }, [fromDate, toDate]);

    useEffect(() => {
        fetchLogs();
    }, [fetchLogs]);

    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage);
    };

    const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
        setRowsPerPage(parseInt(event.target.value, 10));
        setPage(0);
    };

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns}>
            <Box sx={{ p: 3 }}>
                <Typography variant="h4" gutterBottom>
                    Run History
                </Typography>

                <Paper sx={{ mb: 2, p: 2 }}>
                    <Grid container spacing={2} alignItems="center" justifyContent="center">
                        <Grid size={{ xs: 12, sm: 4 }}>
                            <DatePicker
                                label="From Date"
                                value={fromDate}
                                onChange={(newValue) => {
                                    setFromDate(newValue);
                                    setPage(0); // Reset page when date changes
                                }}
                                slotProps={{ textField: { fullWidth: true } }}
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 4 }}>
                            <DatePicker
                                label="To Date"
                                value={toDate}
                                onChange={(newValue) => {
                                    setToDate(newValue);
                                    setPage(0); // Reset page when date changes
                                }}
                                slotProps={{ textField: { fullWidth: true } }}
                                minDate={fromDate || undefined} // Prevent selecting toDate before fromDate
                            />
                        </Grid>
                        {/* Future: Add filter by status dropdown */}
                    </Grid>
                </Paper>

                {loading && <CircularProgress sx={{ display: 'block', margin: 'auto', mt: 3 }} />}
                {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
                {!loading && !error && (
                    <Paper sx={{ width: '100%', overflow: 'hidden' }}>
                        <TableContainer sx={{ maxHeight: 600 }}>
                            <Table stickyHeader aria-label="run history table">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Task ID</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Date Time Run</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {logs.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage).map((log) => (
                                        <TableRow hover role="checkbox" tabIndex={-1} key={log.task_id + log.datetime_run}>
                                            <TableCell>{log.task_id}</TableCell>
                                            <TableCell>{log.status}</TableCell>
                                            <TableCell>{log.datetime_run}</TableCell>
                                        </TableRow>
                                    ))}
                                    {logs.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={3} align="center">
                                                No logs found for the selected criteria.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                        <TablePagination
                            rowsPerPageOptions={[10, 25, 50, 100]}
                            component="div"
                            count={logs.length}
                            rowsPerPage={rowsPerPage}
                            page={page}
                            onPageChange={handleChangePage}
                            onRowsPerPageChange={handleChangeRowsPerPage}
                        />
                    </Paper>
                )}
            </Box>
        </LocalizationProvider>
    );
};

export default RunHistory; 