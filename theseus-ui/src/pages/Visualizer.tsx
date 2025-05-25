import React, { useState, useEffect } from 'react';
import {
  Typography,
  Card,
  CardContent,
  Box,
  Button,
  Chip,
  TextField,
  CircularProgress,
  Container,
} from '@mui/material';
import { taskApi } from '../services/api'; // Assuming api.ts will be updated
import { useWebSocket, type RunStatusPayload as WS_RunStatusPayload } from '../hooks/useWebSocket';

// Aliases for WebSocket payload types
interface RunStatusPayload extends WS_RunStatusPayload {}

interface VisualizerParamsType {
  matrix_count: number;
  matrix_head_color: string;
  matrix_tail_color: string;
  matrix_char_size: number;
  head_step_time: number;
  random_x_jitter: number;
  fade_time: number;
  head_glow_passes: number;
  head_glow_alpha_decay: number;
  head_spawn_delay_range_min: number;
  head_spawn_delay_range_max: number;
  head_saw_period: number;
  line_width: number;
  wave_color: string;
  trail_color_1: string;
  trail_color_2: string;
  trail_color_3: string;
  glow_passes: number;
  glow_alpha_decay: number;
  font_path: string;
  resolution_width: number;
  resolution_height: number;
  fps: number;
}

const Visualizer: React.FC = () => {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [visualizerParams, setVisualizerParams] = useState<VisualizerParamsType>({
    matrix_count: 150,
    matrix_head_color: "#e0ffe7",
    matrix_tail_color: "#00b000",
    matrix_char_size: 24,
    head_step_time: 0.3,
    random_x_jitter: 3.0,
    fade_time: 3.0,
    head_glow_passes: 3,
    head_glow_alpha_decay: 50,
    head_spawn_delay_range_min: 1.0,
    head_spawn_delay_range_max: 3.0,
    head_saw_period: 1.5,
    line_width: 3,
    wave_color: "#d703fc",
    trail_color_1: "#fc03b6",
    trail_color_2: "#ba03fc",
    trail_color_3: "#ce6bf2",
    glow_passes: 3,
    glow_alpha_decay: 40,
    font_path: "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", // Default, consider making this configurable or removing if problematic
    resolution_width: 1920,
    resolution_height: 1080,
    fps: 30
  });

  const [generating, setGenerating] = useState<boolean>(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState({
    stage: '',
    progress: 0,
    message: "No active visualization task. Upload an audio file and click 'Generate Visualization' to start.",
  });
  const [downloadInfo, setDownloadInfo] = useState<{ url: string | null, filename: string }>({ url: null, filename: 'visualization.mp4' });

  const handleAudioFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setAudioFile(event.target.files[0]);
    } else {
      setAudioFile(null);
    }
  };
  
  const handleGenerateVisualization = async () => {
    if (!audioFile) {
      setError('Please upload an audio file first.');
      return;
    }
    setGenerating(true);
    setError(null);
    setStatusMessages([]);
    setPipelineStatus({
        stage: 'Initiating...',
        progress: 5,
        message: 'Preparing to generate visualization...',
    });
    setDownloadInfo({ url: null, filename: 'visualization.mp4' });


    try {
      // This will be defined in services/api.ts later
      // For now, assuming a function like visualizerApi.generateVisualization exists
      const response = await (taskApi as any).runVisualizerPipeline(audioFile, visualizerParams); 
      setTaskId(response.data.task_id);
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to start visualization generation';
      setError(errMsg);
      setPipelineStatus(prev => ({ ...prev, stage: 'Failed to Start', message: `Error: ${errMsg}`}));
      setGenerating(false);
    }
  };

  // WebSocket integration
  const placeholderTaskId = 'dummy-visualizer-task-id';
  const wsHookState = useWebSocket(taskId || placeholderTaskId, "visualizer" as any); // Cast 'visualizer' if not in hook's type yet

  const handleParsedRunStatus = (payload: RunStatusPayload) => {
    const mainNode = payload.nodes && payload.nodes.length > 0 ? payload.nodes[0] : null;
    const logMessage = `[${payload.overallStatus?.toUpperCase()}] ${new Date().toLocaleTimeString()}: ${mainNode?.message || payload.error || 'Status update'}`;
    setStatusMessages(prev => [...prev, logMessage].slice(-100));

    setPipelineStatus({
      stage: mainNode?.message || (payload.overallStatus === 'failed' ? 'Failed' : pipelineStatus.stage),
      progress: mainNode?.progress ?? (payload.overallStatus === 'completed' ? 100 : (payload.overallStatus === 'failed' ? 0 : pipelineStatus.progress)),
      message: mainNode?.message || payload.error || (payload.overallStatus === 'completed' ? 'Completed successfully' : 'Processing...'),
    });
    setError(payload.error || null);
    
    if (payload.overallStatus === 'completed' || payload.overallStatus === 'failed') {
      setGenerating(false);
    }
  };

  useEffect(() => {
    if (taskId && taskId !== placeholderTaskId && wsHookState.lastMessage) {
      handleParsedRunStatus(wsHookState.lastMessage as RunStatusPayload);
    }
    if (taskId && wsHookState.error) {
      const errorMessage = wsHookState.error?.toString() || 'WebSocket connection error';
      if (taskId !== placeholderTaskId) {
        setError(errorMessage);
        setPipelineStatus(prev => ({ ...prev, stage: 'WebSocket Error', message: `Error: ${errorMessage}`}));
        setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: ${errorMessage}`].slice(-100));
        setGenerating(false);
      }
    }
  }, [taskId, wsHookState.lastMessage, wsHookState.error]);

  useEffect(() => {
    if (wsHookState.lastMessage?.overallStatus === 'completed' && taskId && (wsHookState.lastMessage as any).result) {
        taskApi.downloadTaskArtifact(taskId, 'video') // Assuming 'video' is the artifact type
            .then(downloadRes => {
                const blob = new Blob([downloadRes.data], { type: 'video/mp4' });
                setDownloadInfo({ url: URL.createObjectURL(blob), filename: 'visualization.mp4' });
            })
            .catch(err => {
                console.error("Failed to download artifact:", err);
                setError("Failed to prepare download link for the visualization.");
            });
    }
  }, [wsHookState.lastMessage, taskId]);

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
        🎬 Audio Visualizer
      </Typography>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Audio File Upload Card */}
        <Card>
          <CardContent>
            <Typography variant="h5" gutterBottom sx={{ mb: 2 }}>Upload Audio File</Typography>
            <Button
              variant="contained"
              component="label"
            >
              Select Audio File
              <input
                type="file"
                accept="audio/*"
                hidden
                onChange={handleAudioFileUpload}
              />
            </Button>
            {audioFile && (
              <Chip label={audioFile.name} onDelete={() => setAudioFile(null)} sx={{ mt: 2, ml:1 }} />
            )}
          </CardContent>
        </Card>

        {/* Visualization Settings Card */}
        <Card>
          <CardContent>
            <Typography variant="h5" gutterBottom sx={{ mb: 2 }}>Visualization Settings</Typography>
            <Box sx={{ display: 'flex', gap: 3 }}> {/* Two-column layout */}
              {/* Column 1 */}
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField label="Matrix Head Color" type="color" value={visualizerParams.matrix_head_color} onChange={e => setVisualizerParams(prev => ({ ...prev, matrix_head_color: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }} />
                <TextField label="Matrix Char Size" type="number" value={visualizerParams.matrix_char_size} onChange={e => setVisualizerParams(prev => ({ ...prev, matrix_char_size: parseInt(e.target.value) }))} fullWidth />
                <TextField label="Head Step Time (s)" type="number" inputProps={{ step: 0.01 }} value={visualizerParams.head_step_time} onChange={e => setVisualizerParams(prev => ({ ...prev, head_step_time: parseFloat(e.target.value) }))} fullWidth />
                <TextField label="Fade Time (s)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.fade_time} onChange={e => setVisualizerParams(prev => ({ ...prev, fade_time: parseFloat(e.target.value) }))} fullWidth />
                <TextField label="Head Glow Alpha Decay" type="number" value={visualizerParams.head_glow_alpha_decay} onChange={e => setVisualizerParams(prev => ({ ...prev, head_glow_alpha_decay: parseInt(e.target.value) }))} fullWidth />
                <TextField label="Head Saw Period (s)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.head_saw_period} onChange={e => setVisualizerParams(prev => ({ ...prev, head_saw_period: parseFloat(e.target.value) }))} fullWidth />
                <TextField label="Wave Color" type="color" value={visualizerParams.wave_color} onChange={e => setVisualizerParams(prev => ({ ...prev, wave_color: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }} />
                <TextField label="Glow Alpha Decay" type="number" value={visualizerParams.glow_alpha_decay} onChange={e => setVisualizerParams(prev => ({ ...prev, glow_alpha_decay: parseInt(e.target.value) }))} fullWidth />
                <TextField label="FPS" type="number" value={visualizerParams.fps} onChange={e => setVisualizerParams(prev => ({ ...prev, fps: parseInt(e.target.value) }))} fullWidth />
                <TextField label="Resolution Width (px)" type="number" value={visualizerParams.resolution_width} onChange={e => setVisualizerParams(prev => ({ ...prev, resolution_width: parseInt(e.target.value) }))} fullWidth />
                <TextField label="Resolution Height (px)" type="number" value={visualizerParams.resolution_height} onChange={e => setVisualizerParams(prev => ({ ...prev, resolution_height: parseInt(e.target.value) }))} fullWidth />
              </Box>
              {/* Column 2 */}
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField label="Matrix Tail Color" type="color" value={visualizerParams.matrix_tail_color} onChange={e => setVisualizerParams(prev => ({ ...prev, matrix_tail_color: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }} />
                <TextField label="Matrix Count" type="number" value={visualizerParams.matrix_count} onChange={e => setVisualizerParams(prev => ({ ...prev, matrix_count: parseInt(e.target.value) }))} fullWidth />
                <TextField label="Random X Jitter (px)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.random_x_jitter} onChange={e => setVisualizerParams(prev => ({ ...prev, random_x_jitter: parseFloat(e.target.value) }))} fullWidth />
                <TextField label="Head Glow Passes" type="number" value={visualizerParams.head_glow_passes} onChange={e => setVisualizerParams(prev => ({ ...prev, head_glow_passes: parseInt(e.target.value) }))} fullWidth />
                <TextField label="Head Spawn Delay Min (s)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.head_spawn_delay_range_min} onChange={e => setVisualizerParams(prev => ({ ...prev, head_spawn_delay_range_min: parseFloat(e.target.value) }))} fullWidth />
                <TextField label="Head Spawn Delay Max (s)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.head_spawn_delay_range_max} onChange={e => setVisualizerParams(prev => ({ ...prev, head_spawn_delay_range_max: parseFloat(e.target.value) }))} fullWidth />
                <TextField label="Line Width (px)" type="number" value={visualizerParams.line_width} onChange={e => setVisualizerParams(prev => ({ ...prev, line_width: parseInt(e.target.value) }))} fullWidth />
                <TextField label="Trail Color 1" type="color" value={visualizerParams.trail_color_1} onChange={e => setVisualizerParams(prev => ({ ...prev, trail_color_1: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }}/>
                <TextField label="Trail Color 2" type="color" value={visualizerParams.trail_color_2} onChange={e => setVisualizerParams(prev => ({ ...prev, trail_color_2: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }}/>
                <TextField label="Trail Color 3" type="color" value={visualizerParams.trail_color_3} onChange={e => setVisualizerParams(prev => ({ ...prev, trail_color_3: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }}/>
                <TextField label="Glow Passes" type="number" value={visualizerParams.glow_passes} onChange={e => setVisualizerParams(prev => ({ ...prev, glow_passes: parseInt(e.target.value) }))} fullWidth />
                <TextField label="Font Path" type="text" value={visualizerParams.font_path} onChange={e => setVisualizerParams(prev => ({ ...prev, font_path: e.target.value }))} fullWidth />
              </Box>
            </Box>
          </CardContent>
        </Card>

        {/* Generate Button and Status Card */}
        <Card>
          <CardContent>
            <Typography variant="h5" gutterBottom>Generate</Typography>
            <Button
              variant="contained"
              color="primary"
              fullWidth
              disabled={!audioFile || generating}
              onClick={handleGenerateVisualization}
              sx={{ py: 1.5, fontSize: '1.1rem' }}
            >
              {generating ? `Generating... (${pipelineStatus.stage} ${pipelineStatus.progress.toFixed(0)}%)` : 'Generate Visualization'}
            </Button>
            {generating && <CircularProgress sx={{ mt: 2, display: 'block', marginLeft: 'auto', marginRight: 'auto' }} />}
            {error && (
              <Typography color="error" sx={{ mt: 2, textAlign: 'center' }}>
                {error}
              </Typography>
            )}
            {taskId && !generating && wsHookState.readyState === 1 && wsHookState.lastMessage?.overallStatus !== 'completed' && wsHookState.lastMessage?.overallStatus !== 'failed' && (
              <Typography sx={{ mt: 2, textAlign: 'center' }}>
                Visualization generation in progress. Task ID: {taskId}
                <br />
                Status: {pipelineStatus.message} ({pipelineStatus.progress.toFixed(0)}%)
              </Typography>
            )}
            {wsHookState.lastMessage?.overallStatus === 'completed' && (
               <Typography sx={{ mt: 2, textAlign: 'center' }} color="success.main">
                 Visualization Ready! Task ID: {taskId}
               </Typography>
            )}
            {downloadInfo.url && (
              <Button component="a" href={downloadInfo.url} download={downloadInfo.filename} variant="contained" fullWidth sx={{ mt: 2 }}>
                Download Visualization
              </Button>
            )}

            {/* Live Log Display */}
            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>Live Log:</Typography>
            <Box
              sx={{
                height: 200,
                overflowY: 'auto',
                border: '1px solid',
                borderColor: 'divider',
                p: 1,
                borderRadius: 1,
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
                backgroundColor: 'action.hover'
              }}
            >
              {statusMessages.length > 0 ? statusMessages.map((msg, index) => (
                <div key={index}>{msg}</div>
              )) : "No log messages yet."}
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default Visualizer; 