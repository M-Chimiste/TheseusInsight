import React, { useState } from 'react';
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
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, podcastApi, taskApi } from '../services/api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

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
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

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
  const [generating, setGenerating] = useState<boolean>(false);
  const [podcastTaskId, setPodcastTaskId] = useState<string | null>(null);
  const [podcastError, setPodcastError] = useState<string | null>(null);
  
  // Handler to call generatePodcast API
  const handleGeneratePodcast = async () => {
    setGenerating(true);
    setPodcastError(null);
    try {
      const params = {
        // Determine input_type based on whether URLs or PDFs are provided, PDFs take precedence if both exist
        input_type: pdfFiles.length > 0 ? 'pdfs' : (urls.length > 0 ? 'urls' : 'none'), // Added 'none' case, though button should be disabled
        urls: urls.length > 0 ? urls : undefined,
        podcast_model_config: podcastModelConfig,
        tts_model_config: ttsModelConfig,
        create_visualization: false, // For now, can be made configurable later
        visualizer_params: null,    // For now, can be made configurable later
      };

      if (params.input_type === 'none') {
        setPodcastError('Please provide PDF files or URLs.');
        setGenerating(false);
        return;
      }

      const response = await podcastApi.generatePodcast(
        params,
        introMusicFile || undefined,
        pdfFiles.length > 0 ? pdfFiles : undefined
      );
      setPodcastTaskId(response.data.task_id);
    } catch (err: any) {
      setPodcastError(err.response?.data?.detail || err.message || 'Failed to start podcast generation');
    } finally {
      setGenerating(false);
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

  // Poll the task status and download when complete
  React.useEffect(() => {
    if (!podcastTaskId) return;
    const interval = setInterval(async () => {
      try {
        const statusRes = await taskApi.getTaskStatus(podcastTaskId);
        const status = statusRes.data.status;
        if (status === 'completed') {
          clearInterval(interval);
          setIsCompleted(true);
          const downloadRes = await taskApi.downloadTaskArtifact(podcastTaskId, 'audio');
          const blob = new Blob([downloadRes.data], { type: 'audio/mpeg' });
          setDownloadUrl(URL.createObjectURL(blob));
        } else if (status === 'failed') {
          clearInterval(interval);
          setPodcastError('Podcast generation failed.');
        }
      } catch {
        clearInterval(interval);
        setPodcastError('Error checking status.');
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [podcastTaskId]);

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
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
                variant="outlined"
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
                <Button
                  variant="contained"
                  onClick={() => saveConfigMutation.mutate({
                    ...orchestrationConfig,
                    podcast_model: podcastModelConfig,
                  })}
                  disabled={saveConfigMutation.status === 'pending'}
                >Save Podcast Model Settings</Button>
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
                <Button
                  variant="contained"
                  onClick={() => saveConfigMutation.mutate({
                    ...orchestrationConfig,
                    tts_model: ttsModelConfig,
                  })}
                  disabled={saveConfigMutation.status === 'pending'}
                >Save TTS Model Settings</Button>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* Intro Music Upload */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h5" gutterBottom>Intro Music (Optional)</Typography>
            <Button variant="outlined" component="label">
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

        {/* Generate Podcast Button and Status */}
        <Card>
          <CardContent>
            <Typography variant="h5" gutterBottom>Generate</Typography>
            <Button
              variant="contained"
              color="primary"
              fullWidth
              disabled={pdfFiles.length === 0 && urls.length === 0}
              onClick={handleGeneratePodcast}
              sx={{ py: 1.5, fontSize: '1.1rem' }}
            >
              Generate Podcast
            </Button>
            {generating && <CircularProgress sx={{ mt: 2, display: 'block', marginLeft: 'auto', marginRight: 'auto' }} />}
            {podcastError && (
              <Typography color="error" sx={{ mt: 2, textAlign: 'center' }}>
                {podcastError}
              </Typography>
            )}
            {podcastTaskId && !generating && !isCompleted && (
              <Typography sx={{ mt: 2, textAlign: 'center' }}>
                Podcast generation started. Task ID: {podcastTaskId}
              </Typography>
            )}
            {isCompleted && (
               <Typography sx={{ mt: 2, textAlign: 'center' }} color="success.main">
                 Podcast Ready!
               </Typography>
            )}
            {downloadUrl && (
              <Button component="a" href={downloadUrl} download="podcast.mp3" variant="contained" fullWidth sx={{ mt: 2 }}>
                Download Podcast
              </Button>
            )}
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default Podcast;

