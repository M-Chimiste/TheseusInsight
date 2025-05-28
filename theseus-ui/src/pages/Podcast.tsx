import React, { useState, useEffect } from 'react';
import {
  Typography,
  Card,
  CardContent,
  Box,
  Button,
  Chip,
  TextField,
  Tooltip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Container,
  FormControlLabel,
  Switch,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, podcastApi, taskApi } from '../services/api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useTaskState } from '../hooks/useTaskState';

// Interface for podcast generation state

const Podcast: React.FC = () => {
  const queryClient = useQueryClient();
  // Fetch orchestration and model providers for config
  const { data: orchestrationConfig, isLoading: isLoadingOrchestration } = useQuery({
    queryKey: ['orchestrationConfig'],
    queryFn: () => settingsApi.getOrchestrationConfig().then(res => res.data),
  });
  const { data: modelProviders, isLoading: isLoadingProviders } = useQuery({
    queryKey: ['modelProviders'],
    queryFn: () => settingsApi.getModelProviders().then(res => res.data),
  });

  // Local state for model settings and intro music
  const [podcastModelConfig, setPodcastModelConfig] = useState<any>({});
  const [ttsModelConfig, setTtsModelConfig] = useState<any>({});
  const [introMusicFile, setIntroMusicFile] = useState<File | null>(null);

  // Initialize local config when loaded
  React.useEffect(() => {
    if (orchestrationConfig) {
      setPodcastModelConfig(orchestrationConfig.podcast_model || {});
      setTtsModelConfig(orchestrationConfig.tts_model || {});
    }
  }, [orchestrationConfig]);
  
  // Mutation to save config
  const saveConfigMutation = useMutation({
    mutationFn: (newConfig: any) => settingsApi.updateOrchestrationConfig(newConfig),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orchestrationConfig'] }),
  });

  // PDF files state
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);

  // URLs state
  const [urlInput, setUrlInput] = useState<string>('');
  const [urls, setUrls] = useState<string[]>([]);

  // Podcast generation state
  const [statusMessages, setStatusMessages] = useState<string[]>([]); // For live log
  
  // Use the new task state hook
  const { taskState, setTaskId, isCheckingForActiveTasks } = useTaskState('podcast');

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

  const [createVisualization, setCreateVisualization] = useState<boolean>(false);
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
    font_path: "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    resolution_width: 1920,
    resolution_height: 1080,
    fps: 30
  });

  // Handler to call generatePodcast API
  const handleGeneratePodcast = async () => {
    setStatusMessages([]); // Clear previous logs

    try {
      const params = {
        // Determine input_type based on whether URLs or PDFs are provided, PDFs take precedence if both exist
        input_type: pdfFiles.length > 0 ? 'pdfs' : (urls.length > 0 ? 'URLs' : 'none'), // Changed to uppercase 'URLs' to match the backend expectations
        urls: urls.length > 0 ? urls : undefined,
        podcast_model_config: podcastModelConfig,
        tts_model_config: ttsModelConfig,
        create_visualization: createVisualization, 
        visualizer_params: createVisualization ? visualizerParams : null,
      };

      if (params.input_type === 'none') {
        setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: Please provide PDF files or URLs.`]);
        return;
      }

      const response = await podcastApi.generatePodcast(
        params,
        introMusicFile || undefined,
        pdfFiles.length > 0 ? pdfFiles : undefined
      );
      setTaskId(response.data.task_id);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to start podcast generation';
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: ${errorMessage}`]);
    }
  };

  // Handle PDF uploads
  const handlePdfUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files) return;
    const newFiles = Array.from(event.target.files);
    setPdfFiles(prev => [...prev, ...newFiles]);
    // Reset input value to allow re-upload of same file if removed
    event.target.value = '';
  };

  // Remove a PDF file by index
  const handleRemovePdf = (index: number) => {
    setPdfFiles(prev => prev.filter((_file, i) => i !== index));
  };

  // Handle URL input change
  const handleUrlInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setUrlInput(event.target.value);
  };

  // Add URL when pressing Enter or clicking Add button
  const addUrl = () => {
    const trimmed = urlInput.trim();
    if (trimmed && !urls.includes(trimmed)) {
      setUrls(prev => [...prev, trimmed]);
    }
    setUrlInput('');
  };

  const handleUrlKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addUrl();
    }
  };

  // Remove a URL by index
  const handleRemoveUrl = (index: number) => {
    setUrls(prev => prev.filter((_u, i) => i !== index));
  };

  // Update status messages when task state changes
  useEffect(() => {
    if (taskState.taskId && taskState.message) {
      const logMessage = `[${taskState.stage.toUpperCase()}] ${new Date().toLocaleTimeString()}: ${taskState.message}`;
      setStatusMessages(prev => [...prev, logMessage].slice(-100)); // Keep last 100 messages
    }
  }, [taskState.message, taskState.stage, taskState.taskId]);

  // Download button state and logic
  const [downloadInfo, setDownloadInfo] = useState<{ url: string | null, filename: string, type: 'audio' | 'video' | null, isLoading: boolean }>({ 
    url: null, 
    filename: 'podcast', 
    type: null, 
    isLoading: false 
  });

  // Check if task is completed (not running and has taskId, with or without explicit result)
  const isTaskCompleted = taskState.taskId && !taskState.isRunning && !taskState.error;

  useEffect(() => {
    // Try to download artifact when task completes, regardless of result field
    if (isTaskCompleted && taskState.taskId) {
        const artifactType = createVisualization ? 'video' : 'audio';
        const filename = artifactType === 'video' ? 'podcast_visualization.mp4' : 'podcast_audio.mp3';
        const blobType = artifactType === 'video' ? 'video/mp4' : 'audio/mpeg';

        // Set loading state
        setDownloadInfo({ url: null, filename, type: null, isLoading: true });

        taskApi.downloadTaskArtifact(taskState.taskId, artifactType)
            .then(downloadRes => {
                const blob = new Blob([downloadRes.data], { type: blobType });
                setDownloadInfo({ url: URL.createObjectURL(blob), filename, type: artifactType, isLoading: false });
            })
            .catch(err => {
                console.error("Failed to download artifact:", err);
                setDownloadInfo({ url: null, filename, type: null, isLoading: false });
                setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: Failed to prepare download link for the artifact.`]);
            });
    }
  }, [isTaskCompleted, taskState.taskId, createVisualization]);

  // Function to reset task state and allow new generation
  const handleResetTask = () => {
    setTaskId(null);
    setDownloadInfo({ url: null, filename: 'podcast', type: null, isLoading: false });
    setStatusMessages([]);
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
        🎙️ Podcast Creator
      </Typography>

      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
        }}
      >
        {/* Content Sources Card - Combined */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h5" gutterBottom sx={{ mb: 2 }}>Content Sources</Typography>
            
            {/* PDF Upload Section */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom>Upload PDFs</Typography>
              <Button
                variant="contained"
                color="primary"
                component="label"
              >
                Select PDF Files
                <input
                  type="file"
                  accept="application/pdf"
                  multiple
                  hidden
                  onChange={handlePdfUpload}
                />
              </Button>
              <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {pdfFiles.map((file, index) => (
                  <Chip
                    key={index}
                    label={file.name}
                    onDelete={() => handleRemovePdf(index)}
                    color="primary"
                    deleteIcon={<DeleteIcon />}
                  />
                ))}
              </Box>
            </Box>

            {/* URL Input Section */}
            <Box>
              <Typography variant="h6" gutterBottom>Add URLs</Typography>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <TextField
                  label="Enter URL"
                  value={urlInput}
                  onChange={handleUrlInputChange}
                  onKeyDown={handleUrlKeyDown}
                  fullWidth
                />
                <Button variant="contained" onClick={addUrl}>
                  Add
                </Button>
              </Box>
              <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {urls.map((u, index) => (
                  <Chip
                    key={index}
                    label={u}
                    onDelete={() => handleRemoveUrl(index)}
                    color="secondary"
                    deleteIcon={<DeleteIcon />}
                  />
                ))}
              </Box>
            </Box>
          </CardContent>
        </Card>

        {/* Podcast Model Settings Card */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Typography variant="h5" sx={{ flexGrow: 1 }}>Podcast Model Settings</Typography>
              <Tooltip title="Configure the model used for podcast generation."><InfoOutlinedIcon /></Tooltip>
            </Box>
            {isLoadingOrchestration || isLoadingProviders ? (
              <CircularProgress />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FormControl fullWidth>
                  <InputLabel>Model Type (Provider)</InputLabel>
                  <Select
                    value={podcastModelConfig?.model_type || ''}
                    label="Model Type (Provider)"
                    onChange={(e) => setPodcastModelConfig((prev: any) => ({ ...prev, model_type: e.target.value }))}
                  >
                    {(modelProviders || []).map((p: any) => (
                      <MenuItem key={p.id} value={p.name}>{p.name}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField
                  fullWidth
                  label="Model Name"
                  value={podcastModelConfig?.model_name || ''}
                  onChange={(e) => setPodcastModelConfig((prev: any) => ({ ...prev, model_name: e.target.value }))}
                />
                <TextField
                  fullWidth
                  label="Max New Tokens"
                  type="number"
                  value={podcastModelConfig?.max_new_tokens || ''}
                  onChange={(e) => setPodcastModelConfig((prev: any) => ({ ...prev, max_new_tokens: e.target.value ? Number(e.target.value) : null }))}
                />
                <TextField
                  fullWidth
                  label="Temperature"
                  type="number"
                  inputProps={{ step: 0.1 }}
                  value={podcastModelConfig?.temperature || ''}
                  onChange={(e) => setPodcastModelConfig((prev: any) => ({ ...prev, temperature: e.target.value ? parseFloat(e.target.value) : null }))}
                />
                <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <Button
                    variant="contained"
                    onClick={() => saveConfigMutation.mutate({
                      ...orchestrationConfig,
                      podcast_model: podcastModelConfig,
                    })}
                    disabled={saveConfigMutation.status === 'pending'}
                  >Save Podcast Model Settings</Button>
                </Box>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* TTS Model Settings Card */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Typography variant="h5" sx={{ flexGrow: 1 }}>TTS Model Settings</Typography>
              <Tooltip title="Configure the Text-to-Speech (TTS) model and parameters."><InfoOutlinedIcon /></Tooltip>
            </Box>
            {isLoadingOrchestration || isLoadingProviders ? (
              <CircularProgress />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FormControl fullWidth>
                  <InputLabel>TTS Provider</InputLabel>
                  <Select
                    value={ttsModelConfig?.tts_provider || ''}
                    label="TTS Provider"
                    onChange={(e) => setTtsModelConfig((prev: any) => ({ ...prev, tts_provider: e.target.value }))}
                  >
                    {(modelProviders || []).map((p: any) => (
                      <MenuItem key={p.id} value={p.name}>{p.name}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField
                  fullWidth
                  label="TTS Model Name"
                  value={ttsModelConfig?.tts_model_name || ''}
                  onChange={(e) => setTtsModelConfig((prev: any) => ({ ...prev, tts_model_name: e.target.value }))}
                />
                <TextField
                  fullWidth
                  label="Speaker 1 Voice"
                  value={ttsModelConfig?.speaker_1_voice || ''}
                  onChange={(e) => setTtsModelConfig((prev: any) => ({ ...prev, speaker_1_voice: e.target.value }))}
                />
                <TextField
                  fullWidth
                  label="Speaker 1 Speed"
                  type="number"
                  inputProps={{ step: 0.1 }}
                  value={ttsModelConfig?.speaker_1_speed || 1.0}
                  onChange={(e) => setTtsModelConfig((prev: any) => ({ ...prev, speaker_1_speed: parseFloat(e.target.value) }))}
                />
                <TextField
                  fullWidth
                  label="Speaker 2 Voice"
                  value={ttsModelConfig?.speaker_2_voice || ''}
                  onChange={(e) => setTtsModelConfig((prev: any) => ({ ...prev, speaker_2_voice: e.target.value }))}
                />
                <TextField
                  fullWidth
                  label="Speaker 2 Speed"
                  type="number"
                  inputProps={{ step: 0.1 }}
                  value={ttsModelConfig?.speaker_2_speed || 1.0}
                  onChange={(e) => setTtsModelConfig((prev: any) => ({ ...prev, speaker_2_speed: parseFloat(e.target.value) }))}
                />
                <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <Button
                    variant="contained"
                    onClick={() => saveConfigMutation.mutate({
                      ...orchestrationConfig,
                      tts_model: ttsModelConfig,
                    })}
                    disabled={saveConfigMutation.status === 'pending'}
                  >Save TTS Model Settings</Button>
                </Box>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* Intro Music Upload */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h5" gutterBottom>Intro Music (Optional)</Typography>
            <Button variant="contained" color="primary" component="label">
              Upload Intro Music
              <input
                type="file"
                accept="audio/*"
                hidden
                onChange={e => e.target.files && setIntroMusicFile(e.target.files[0])}
              />
            </Button>
            {introMusicFile && (
              <Chip label={introMusicFile.name} onDelete={() => setIntroMusicFile(null)} sx={{ mt: 2 }} />
            )}
          </CardContent>
        </Card>

        {/* Visualization Settings Section (Conditional) */}
        <Card sx={{ width: '100%' }}>
          <CardContent>
            <FormControlLabel
              control={<Switch checked={createVisualization} onChange={(e) => setCreateVisualization(e.target.checked)} />}
              label="Create Video Visualization?"
              sx={{ mb: 2 }}
            />
            {createVisualization && (
              <>
                <Typography variant="h5" gutterBottom sx={{ mb: 2 }}>Visualization Settings</Typography>
                <Box sx={{ display: 'flex', gap: 3 }}> {/* Two-column layout */}
                  {/* Column 1 */}
                  <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <TextField label="Matrix Head Color" type="color" value={visualizerParams.matrix_head_color} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, matrix_head_color: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }} />
                    <TextField label="Matrix Char Size" type="number" value={visualizerParams.matrix_char_size} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, matrix_char_size: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="Head Step Time (s)" type="number" inputProps={{ step: 0.01 }} value={visualizerParams.head_step_time} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, head_step_time: parseFloat(e.target.value) }))} fullWidth />
                    <TextField label="Fade Time (s)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.fade_time} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, fade_time: parseFloat(e.target.value) }))} fullWidth />
                    <TextField label="Head Glow Alpha Decay" type="number" value={visualizerParams.head_glow_alpha_decay} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, head_glow_alpha_decay: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="Head Saw Period (s)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.head_saw_period} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, head_saw_period: parseFloat(e.target.value) }))} fullWidth />
                    <TextField label="Wave Color" type="color" value={visualizerParams.wave_color} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, wave_color: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }} />
                    <TextField label="Glow Alpha Decay" type="number" value={visualizerParams.glow_alpha_decay} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, glow_alpha_decay: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="FPS" type="number" value={visualizerParams.fps} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, fps: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="Resolution Width (px)" type="number" value={visualizerParams.resolution_width} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, resolution_width: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="Resolution Height (px)" type="number" value={visualizerParams.resolution_height} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, resolution_height: parseInt(e.target.value) }))} fullWidth />
                  </Box>
                  {/* Column 2 */}
                  <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <TextField label="Matrix Tail Color" type="color" value={visualizerParams.matrix_tail_color} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, matrix_tail_color: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }} />
                    <TextField label="Matrix Count" type="number" value={visualizerParams.matrix_count} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, matrix_count: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="Random X Jitter (px)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.random_x_jitter} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, random_x_jitter: parseFloat(e.target.value) }))} fullWidth />
                    <TextField label="Head Glow Passes" type="number" value={visualizerParams.head_glow_passes} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, head_glow_passes: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="Head Spawn Delay Min (s)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.head_spawn_delay_range_min} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, head_spawn_delay_range_min: parseFloat(e.target.value) }))} fullWidth />
                    <TextField label="Head Spawn Delay Max (s)" type="number" inputProps={{ step: 0.1 }} value={visualizerParams.head_spawn_delay_range_max} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, head_spawn_delay_range_max: parseFloat(e.target.value) }))} fullWidth />
                    <TextField label="Line Width (px)" type="number" value={visualizerParams.line_width} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, line_width: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="Trail Color 1" type="color" value={visualizerParams.trail_color_1} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, trail_color_1: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }}/>
                    <TextField label="Trail Color 2" type="color" value={visualizerParams.trail_color_2} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, trail_color_2: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }}/>
                    <TextField label="Trail Color 3" type="color" value={visualizerParams.trail_color_3} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, trail_color_3: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }}/>
                    <TextField label="Glow Passes" type="number" value={visualizerParams.glow_passes} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, glow_passes: parseInt(e.target.value) }))} fullWidth />
                    <TextField label="Font Path" type="text" value={visualizerParams.font_path} onChange={e => setVisualizerParams((prev: VisualizerParamsType) => ({ ...prev, font_path: e.target.value }))} fullWidth />
                  </Box>
                </Box>
              </>
            )}
          </CardContent>
        </Card>

        {/* Generate Podcast Button and Status */}
        <Card sx={{ width: '100%' }}>
          <CardContent>
            <Typography variant="h5" gutterBottom>Generate</Typography>
            
            {/* Show different buttons based on task state */}
            {isTaskCompleted ? (
              <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', sm: 'row' } }}>
                <Button
                  variant="outlined"
                  color="secondary"
                  fullWidth
                  onClick={handleResetTask}
                  sx={{ py: 1.5, fontSize: '1.1rem' }}
                >
                  Generate New Podcast
                </Button>
                {downloadInfo.isLoading ? (
                  <Button 
                    variant="contained" 
                    fullWidth 
                    disabled
                    sx={{ py: 1.5, fontSize: '1.1rem' }}
                  >
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    Preparing Download...
                  </Button>
                ) : downloadInfo.url ? (
                  <Button 
                    component="a" 
                    href={downloadInfo.url} 
                    download={downloadInfo.filename} 
                    variant="contained" 
                    fullWidth 
                    sx={{ py: 1.5, fontSize: '1.1rem' }}
                  >
                    Download {downloadInfo.type === 'video' ? 'Podcast Video' : 'Podcast Audio'}
                  </Button>
                ) : (
                  <Button 
                    variant="contained" 
                    fullWidth 
                    disabled
                    sx={{ py: 1.5, fontSize: '1.1rem' }}
                  >
                    Download Failed - Check Logs
                  </Button>
                )}
              </Box>
            ) : (
              <Button
                variant="contained"
                color="primary"
                fullWidth
                disabled={pdfFiles.length === 0 && urls.length === 0 || taskState.isRunning || isCheckingForActiveTasks}
                onClick={handleGeneratePodcast}
                sx={{ py: 1.5, fontSize: '1.1rem' }}
              >
                {isCheckingForActiveTasks ? 'Checking for active tasks...' :
                 taskState.isRunning ? `Generating... (${taskState.stage} ${taskState.progress.toFixed(0)}%)` : 
                 'Generate Podcast'}
              </Button>
            )}
            
            {taskState.isRunning && <CircularProgress sx={{ mt: 2, display: 'block', marginLeft: 'auto', marginRight: 'auto' }} />}
            
            {taskState.error && (
              <Typography color="error" sx={{ mt: 2, textAlign: 'center' }}>
                {taskState.error}
              </Typography>
            )}
            
            {taskState.taskId && taskState.isRunning && (
              <Typography sx={{ mt: 2, textAlign: 'center' }}>
                Podcast generation in progress. Task ID: {taskState.taskId}
                <br />
                Status: {taskState.message} ({taskState.progress.toFixed(0)}%)
              </Typography>
            )}
            
            {isTaskCompleted && (
               <Typography sx={{ mt: 2, textAlign: 'center' }} color="success.main">
                 Podcast Ready! Task ID: {taskState.taskId}
               </Typography>
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

export default Podcast;

