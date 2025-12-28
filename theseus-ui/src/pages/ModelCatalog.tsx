import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardActions,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Alert,
  Snackbar,
  CircularProgress,
  Container,
  Grid,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
  Pagination,
  Autocomplete,
  ToggleButton,
  ToggleButtonGroup,
  Collapse,
  Paper,
  Divider,
  Fab
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Favorite as FavoriteIcon,
  FavoriteBorder as FavoriteBorderIcon,
  ViewList as ViewListIcon,
  ViewModule as ViewModuleIcon,
  FilterList as FilterIcon,

  Close as CloseIcon
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { modelCatalogApi, settingsApi, ollamaServersApi } from '../services/api';
import { useLayout } from '../contexts/LayoutContext';

interface ModelCatalogEntry {
  id: number;
  alias: string;
  model_string: string;
  provider_name: string;
  model_type: string;
  description?: string;
  max_new_tokens?: number;
  temperature?: number;
  num_ctx?: number;
  host?: string;
  trust_remote_code?: boolean;
  tags?: string[];
  is_favorite?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface CreateEditModelData {
  alias: string;
  model_string: string;
  provider_name: string;
  model_type: string;
  description: string;
  max_new_tokens?: number;
  temperature?: number;
  num_ctx?: number;
  host?: string;
  trust_remote_code: boolean;
  tags: string[];
  is_favorite: boolean;
}

const MODEL_TYPES = [
  'chat',
  'completion',
  'embedding',
  'instruct',
  'code',
  'multimodal'
];

const ModelCatalog: React.FC = () => {
  const queryClient = useQueryClient();
  const { headerHeight } = useLayout(); // Get dynamic header height
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // View and filter state
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showFilters, setShowFilters] = useState(false);
  const [search, setSearch] = useState('');
  const [providerFilter, setProviderFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [favoriteFilter, setFavoriteFilter] = useState<boolean | null>(null);
  const [page, setPage] = useState(1);
  
  // Dialog state
  const [isCreateEditDialogOpen, setIsCreateEditDialogOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelCatalogEntry | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<ModelCatalogEntry | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelCatalogEntry | null>(null);
  
  // Form state
  const [formData, setFormData] = useState<CreateEditModelData>({
    alias: '',
    model_string: '',
    provider_name: '',
    model_type: '',
    description: '',
    max_new_tokens: undefined,
    temperature: undefined,
    num_ctx: undefined,
    host: undefined,
    trust_remote_code: false,
    tags: [],
    is_favorite: false
  });

  // Available tags for autocomplete
  const availableTags = [
    'fast', 'accurate', 'reasoning', 'coding', 'creative', 'small', 'large', 
    'efficient', 'multilingual', 'vision', 'experimental', 'production'
  ];

  // Queries - Get all models for client-side filtering
  const { data: allModelsData, isLoading: isLoadingModels, error: modelsError } = useQuery({
    queryKey: ['modelCatalog'],
    queryFn: () => modelCatalogApi.searchModels({
      page: 1,
      page_size: 100 // Get more models for client-side filtering
    }).then((res: any) => res.data),
  });

  const { data: modelProviders, error: providersError } = useQuery({
    queryKey: ['modelProviders'],
    queryFn: () => settingsApi.getModelProviders().then(res => res.data || []),
  });

  // Query for inference servers to provide host autocomplete
  const { data: inferenceServers } = useQuery({
    queryKey: ['inferenceServersForModelCatalog'],
    queryFn: () => ollamaServersApi.getAllServers().then((res: any) => res.data)
  });

  // Helper function to get hosts filtered by provider
  const getHostsByProvider = React.useCallback((provider: string) => {
    if (!inferenceServers || !Array.isArray(inferenceServers)) return [];

    // Map provider_name to inference server provider type
    const providerTypeMap: { [key: string]: 'ollama' | 'lmstudio' | 'custom-oai' | null } = {
      'ollama': 'ollama',
      'lmstudio': 'lmstudio',
      'custom-oai': 'custom-oai',
    };

    const providerType = providerTypeMap[provider.toLowerCase()];
    if (!providerType) return [];

    // For custom-oai, show all hosts
    if (providerType === 'custom-oai') {
      const hosts = inferenceServers.map((server: any) => server.url);
      return Array.from(new Set(hosts)).sort();
    }

    // Filter by provider and extract URLs
    const hosts = inferenceServers
      .filter((server: any) => server.provider === providerType)
      .map((server: any) => server.url);
    return Array.from(new Set(hosts)).sort();
  }, [inferenceServers]);

  // Query Ollama models when provider is ollama
  const ollamaHost = formData.provider_name === 'ollama'
    ? (formData.host || 'localhost:11434')
    : null;

  const { data: ollamaModels, isLoading: ollamaModelsLoading } = useQuery({
    queryKey: ['ollamaModels', ollamaHost],
    queryFn: async () => {
      if (!ollamaHost) return [];

      try {
        // Ensure host has protocol
        const hostWithProtocol = ollamaHost.startsWith('http')
          ? ollamaHost
          : `http://${ollamaHost}`;

        const response = await fetch(`${hostWithProtocol}/api/tags`);
        if (!response.ok) return [];

        const data = await response.json();
        // Extract model names from the response
        return data.models?.map((model: any) => model.name) || [];
      } catch (error) {
        console.error('Failed to fetch Ollama models:', error);
        return [];
      }
    },
    enabled: formData.provider_name === 'ollama',
    staleTime: 60000, // Cache for 1 minute
  });

  // Query LMStudio models when provider is lmstudio
  const lmstudioHost = formData.provider_name === 'lmstudio'
    ? (formData.host || 'localhost:1234')
    : null;

  const { data: lmstudioModels, isLoading: lmstudioModelsLoading } = useQuery({
    queryKey: ['lmstudioModels', lmstudioHost],
    queryFn: async () => {
      if (!lmstudioHost) return [];

      try {
        // Ensure host has protocol
        const hostWithProtocol = lmstudioHost.startsWith('http')
          ? lmstudioHost
          : `http://${lmstudioHost}`;

        const response = await fetch(`${hostWithProtocol}/v1/models`);
        if (!response.ok) return [];

        const data = await response.json();
        // Extract model IDs from the response
        return data.data?.map((model: any) => model.id) || [];
      } catch (error) {
        console.error('Failed to fetch LMStudio models:', error);
        return [];
      }
    },
    enabled: formData.provider_name === 'lmstudio',
    staleTime: 60000, // Cache for 1 minute
  });

  // Query custom-oai models when provider is custom-oai
  const customOaiHost = formData.provider_name === 'custom-oai'
    ? formData.host
    : null;

  const { data: customOaiModels, isLoading: customOaiModelsLoading } = useQuery({
    queryKey: ['customOaiModels', customOaiHost],
    queryFn: async () => {
      if (!customOaiHost) return [];

      try {
        // Ensure host has protocol
        const hostWithProtocol = customOaiHost.startsWith('http')
          ? customOaiHost
          : `https://${customOaiHost}`;

        const response = await fetch(`${hostWithProtocol}/v1/models`);
        if (!response.ok) return [];

        const data = await response.json();
        // Extract model IDs from the response
        return data.data?.map((model: any) => model.id) || [];
      } catch (error) {
        console.error('Failed to fetch custom-oai models:', error);
        return [];
      }
    },
    enabled: formData.provider_name === 'custom-oai' && !!customOaiHost,
    staleTime: 60000, // Cache for 1 minute
  });

  // Client-side filtering function
  const filterModels = (models: ModelCatalogEntry[]) => {
    if (!models) return [];

    return models.filter(model => {
      // Search filter - keyword-based search across multiple fields
      if (search.trim()) {
        const searchTerms = search.toLowerCase().trim().split(/\s+/);
        const searchableText = [
          model.alias,
          model.model_string,
          model.description || '',
          ...(model.tags || [])
        ].join(' ').toLowerCase();

        const matchesSearch = searchTerms.every(term => 
          searchableText.includes(term)
        );
        if (!matchesSearch) return false;
      }

      // Provider filter
      if (providerFilter && model.provider_name !== providerFilter) {
        return false;
      }

      // Type filter
      if (typeFilter && model.model_type !== typeFilter) {
        return false;
      }

      // Tag filter
      if (tagFilter && (!model.tags || !model.tags.includes(tagFilter))) {
        return false;
      }

      // Favorite filter
      if (favoriteFilter !== null && Boolean(model.is_favorite) !== favoriteFilter) {
        return false;
      }

      return true;
    });
  };

  // Apply filters to get filtered models
  const filteredModels = filterModels((allModelsData as any)?.models || []);

  // Pagination for filtered results
  const modelsPerPage = 12;
  const totalPages = Math.ceil(filteredModels.length / modelsPerPage);
  const startIndex = (page - 1) * modelsPerPage;
  const endIndex = startIndex + modelsPerPage;
  const paginatedModels = filteredModels.slice(startIndex, endIndex);

  // Create modelsData structure to match the original API response
  const modelsData = {
    models: paginatedModels,
    total_count: filteredModels.length,
    total_pages: totalPages,
    current_page: page,
    page_size: modelsPerPage
  };

  // Get all available tags for the filter dropdown
  const allTags = React.useMemo(() => {
    const tagSet = new Set<string>();
    ((allModelsData as any)?.models || []).forEach((model: ModelCatalogEntry) => {
      if (model.tags) {
        model.tags.forEach(tag => tagSet.add(tag));
      }
    });
    return Array.from(tagSet).sort();
  }, [allModelsData]);

  // Reset to page 1 when filters change
  React.useEffect(() => {
    setPage(1);
  }, [search, providerFilter, typeFilter, tagFilter, favoriteFilter]);

  // Handle errors from queries
  React.useEffect(() => {
    if (modelsError) {
      console.error('Models fetch error:', modelsError);
      const errorMsg = (modelsError as any)?.response?.data?.detail || 
                      (modelsError as any)?.message || 
                      'Failed to fetch models';
      setError(`Models error: ${errorMsg}`);
    }
  }, [modelsError]);

  React.useEffect(() => {
    if (providersError) {
      console.error('Providers fetch error:', providersError);
      const errorMsg = (providersError as any)?.response?.data?.detail || 
                      (providersError as any)?.message || 
                      'Failed to fetch providers';
      setError(`Providers error: ${errorMsg}`);
    }
  }, [providersError]);

  // Mutations
  const createModelMutation = useMutation({
    mutationFn: (model: any) => {
      console.log('Creating model with data:', model);
      return modelCatalogApi.createModel(model);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modelCatalog'] });
      setSuccess('Model created successfully');
      setIsCreateEditDialogOpen(false);
      resetForm();
    },
    onError: (error: any) => {
      console.error('Create model error:', error);
      console.error('Error response:', error?.response);
      console.error('Error data:', error?.response?.data);
      setError(`Failed to create model: ${error?.response?.status} ${error?.response?.statusText || ''} - ${error?.response?.data?.detail || error?.message || 'Unknown error'}`);
    },
  });

  const updateModelMutation = useMutation({
    mutationFn: ({ modelId, model }: { modelId: number; model: any }) => 
      modelCatalogApi.updateModel(modelId, model),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modelCatalog'] });
      setSuccess('Model updated successfully');
      setIsCreateEditDialogOpen(false);
      resetForm();
      setEditingModel(null);
    },
    onError: (error: any) => setError(error?.response?.data?.detail || 'Failed to update model'),
  });

  const deleteModelMutation = useMutation({
    mutationFn: (modelId: number) => modelCatalogApi.deleteModel(modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modelCatalog'] });
      setSuccess('Model deleted successfully');
      setDeleteDialogOpen(false);
      setModelToDelete(null);
    },
    onError: (error: any) => setError(error?.response?.data?.detail || 'Failed to delete model'),
  });

  const toggleFavoriteMutation = useMutation({
    mutationFn: (modelId: number) => modelCatalogApi.toggleFavorite(modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modelCatalog'] });
    },
    onError: (error: any) => setError(error?.response?.data?.detail || 'Failed to toggle favorite'),
  });

  const resetForm = () => {
    setFormData({
      alias: '',
      model_string: '',
      provider_name: '',
      model_type: '',
      description: '',
      max_new_tokens: undefined,
      temperature: undefined,
      num_ctx: undefined,
      host: undefined,
      trust_remote_code: false,
      tags: [],
      is_favorite: false
    });
  };

  const openCreateDialog = () => {
    resetForm();
    setEditingModel(null);
    setIsCreateEditDialogOpen(true);
  };

  const openEditDialog = (model: ModelCatalogEntry) => {
    setFormData({
      alias: model.alias,
      model_string: model.model_string,
      provider_name: model.provider_name,
      model_type: model.model_type,
      description: model.description || '',
      max_new_tokens: model.max_new_tokens,
      temperature: model.temperature,
      num_ctx: model.num_ctx,
      host: model.host,
      trust_remote_code: model.trust_remote_code || false,
      tags: model.tags || [],
      is_favorite: model.is_favorite || false
    });
    setEditingModel(model);
    setIsCreateEditDialogOpen(true);
  };

  const handleSave = () => {
    if (editingModel) {
      updateModelMutation.mutate({ modelId: editingModel.id, model: formData });
    } else {
      createModelMutation.mutate(formData);
    }
  };

  const handleDelete = (model: ModelCatalogEntry) => {
    setModelToDelete(model);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (modelToDelete) {
      deleteModelMutation.mutate(modelToDelete.id);
    }
  };

  const openDetailView = (model: ModelCatalogEntry) => {
    setSelectedModel(model);
    setDetailDialogOpen(true);
  };

  const getDescriptionSnippet = (description: string, maxLength: number = 100) => {
    if (!description || description.trim() === '') return '';
    
    // Strip markdown formatting for preview
    const plainText = description
      .replace(/^#{1,6}\s+/gm, '') // Remove headers
      .replace(/\*\*(.*?)\*\*/g, '$1') // Remove bold
      .replace(/\*(.*?)\*/g, '$1') // Remove italic
      .replace(/`(.*?)`/g, '$1') // Remove inline code
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // Remove links, keep text
      .replace(/^\s*[-*+]\s+/gm, '') // Remove list bullets
      .replace(/^\s*\d+\.\s+/gm, '') // Remove numbered lists
      .replace(/^\s*>\s+/gm, '') // Remove blockquotes
      .replace(/\n\s*\n/g, ' ') // Replace multiple newlines with space
      .replace(/\s+/g, ' ') // Collapse multiple spaces
      .trim();
    
    if (plainText.length <= maxLength) return plainText;
    return plainText.substring(0, maxLength) + '...';
  };



    const ModelCard = ({ model }: { model: ModelCatalogEntry }) => {
    return (
    <Card 
      elevation={model.is_favorite ? 3 : 1}
      sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        border: model.is_favorite ? '2px solid #ff6b6b' : undefined,
        cursor: 'pointer',
        transition: 'all 0.2s ease-in-out',
        '&:hover': { 
          elevation: 8,
          transform: 'translateY(-2px)'
        }
      }}
      onClick={() => openDetailView(model)}
    >
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="h6" component="h2" sx={{ fontWeight: 'bold' }}>
            {model.alias}
            {model.is_favorite && (
              <FavoriteIcon sx={{ ml: 1, color: '#ff6b6b', fontSize: '1rem' }} />
            )}
          </Typography>
          <Chip 
            label={model.provider_name}
            size="small"
            color="primary"
            variant="outlined"
          />
        </Box>
        
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          <strong>Model:</strong> {model.model_string}
        </Typography>
        
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          <strong>Type:</strong> {model.model_type}
        </Typography>

        {model.tags && model.tags.length > 0 && (
          <Box sx={{ mb: 2 }}>
            {model.tags.map((tag, index) => (
              <Chip 
                key={index} 
                label={tag} 
                size="small" 
                sx={{ mr: 0.5, mb: 0.5 }}
                variant="outlined"
              />
            ))}
          </Box>
        )}

        {model.description && model.description.trim() && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              <strong>Description:</strong>
            </Typography>
            <Typography 
              variant="body2"
              color="text.primary"
              sx={{ 
                display: '-webkit-box',
                overflow: 'hidden',
                WebkitBoxOrient: 'vertical',
                WebkitLineClamp: 3,
                lineHeight: 1.4,
                fontSize: '0.875rem'
              }}
            >
              {getDescriptionSnippet(model.description, 100)}
            </Typography>
          </Box>
        )}

        {/* Model Parameters */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
          {model.max_new_tokens && (
            <Chip label={`Tokens: ${model.max_new_tokens}`} size="small" />
          )}
          {model.temperature && (
            <Chip label={`Temp: ${model.temperature}`} size="small" />
          )}
          {model.num_ctx && (
            <Chip label={`Context: ${model.num_ctx}`} size="small" />
          )}
        </Box>
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between', pt: 0 }}>
        <Box>
          <IconButton 
            onClick={(e) => {
              e.stopPropagation();
              toggleFavoriteMutation.mutate(model.id);
            }}
            color={model.is_favorite ? 'error' : 'default'}
          >
            {model.is_favorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
          </IconButton>
          <IconButton 
            onClick={(e) => {
              e.stopPropagation();
              openEditDialog(model);
            }}
          >
            <EditIcon />
          </IconButton>
        </Box>
        <IconButton 
          onClick={(e) => {
            e.stopPropagation();
            handleDelete(model);
          }} 
          color="error"
        >
          <DeleteIcon />
        </IconButton>
      </CardActions>
    </Card>
    );
  };

  if (isLoadingModels) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh" sx={{ pt: `${headerHeight + 24}px` }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ pt: `${headerHeight + 32}px`, pb: 4 }}>
      <Snackbar
        open={Boolean(error)}
        autoHideDuration={4000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={() => setError(null)} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>

      <Snackbar
        open={Boolean(success)}
        autoHideDuration={4000}
        onClose={() => setSuccess(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={() => setSuccess(null)} severity="success" sx={{ width: '100%' }}>
          {success}
        </Alert>
      </Snackbar>

      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Model Catalog
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, newMode) => newMode && setViewMode(newMode)}
            size="small"
          >
            <ToggleButton value="grid">
              <ViewModuleIcon />
            </ToggleButton>
            <ToggleButton value="list">
              <ViewListIcon />
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {/* Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: showFilters ? 2 : 0 }}>
            <TextField
              label="Search models..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{ flexGrow: 1, mr: 2 }}
              size="small"
            />
            <Button
              startIcon={<FilterIcon />}
              onClick={() => setShowFilters(!showFilters)}
              variant={showFilters ? "contained" : "outlined"}
            >
              Filters
            </Button>
          </Box>
          
          <Collapse in={showFilters}>
            <Divider sx={{ mb: 2 }} />
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 3 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Provider</InputLabel>
                  <Select
                    value={providerFilter}
                    label="Provider"
                    onChange={(e) => setProviderFilter(e.target.value)}
                  >
                    <MenuItem value="">All Providers</MenuItem>
                    {((modelProviders as any) || []).map((provider: any) => (
                      <MenuItem key={provider.name} value={provider.name}>
                        {provider.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 3 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Type</InputLabel>
                  <Select
                    value={typeFilter}
                    label="Type"
                    onChange={(e) => setTypeFilter(e.target.value)}
                  >
                    <MenuItem value="">All Types</MenuItem>
                    {MODEL_TYPES.map((type) => (
                      <MenuItem key={type} value={type}>
                        {type}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 3 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Tag</InputLabel>
                  <Select
                    value={tagFilter}
                    label="Tag"
                    onChange={(e) => setTagFilter(e.target.value)}
                  >
                    <MenuItem value="">All Tags</MenuItem>
                    {allTags.map((tag) => (
                      <MenuItem key={tag} value={tag}>
                        {tag}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 3 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Favorites</InputLabel>
                  <Select
                    value={favoriteFilter === null ? 'all' : favoriteFilter ? 'true' : 'false'}
                    label="Favorites"
                    onChange={(e) => {
                      const value = e.target.value;
                      setFavoriteFilter(value === 'all' ? null : value === 'true');
                    }}
                  >
                    <MenuItem value="all">All Models</MenuItem>
                    <MenuItem value="true">Favorites Only</MenuItem>
                    <MenuItem value="false">Non-Favorites</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Collapse>
        </CardContent>
      </Card>

      {/* Models Grid/List */}
      {modelsData && (modelsData as any)?.models && (modelsData as any).models.length > 0 ? (
        <>
          <Grid container spacing={3}>
            {(modelsData as any).models.map((model: ModelCatalogEntry) => (
              <Grid size={{ xs: 12, sm: viewMode === 'grid' ? 6 : 12, md: viewMode === 'grid' ? 4 : 12 }} key={model.id}>
                <ModelCard model={model} />
              </Grid>
            ))}
          </Grid>

          {/* Pagination */}
          {(modelsData as any).total_pages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <Pagination
                count={(modelsData as any).total_pages}
                page={page}
                onChange={(_, newPage) => setPage(newPage)}
                color="primary"
              />
            </Box>
          )}
        </>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary">
            No models found
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {search || providerFilter || typeFilter || tagFilter || favoriteFilter !== null
              ? 'Try adjusting your search terms or filters'
              : 'Start by adding your first model to the catalog'
            }
          </Typography>
          <Button variant="contained" onClick={openCreateDialog}>
            Add First Model
          </Button>
        </Paper>
      )}

      {/* FAB for adding new model */}
      <Fab
        color="primary"
        aria-label="add model"
        sx={{ position: 'fixed', bottom: 16, right: 16 }}
        onClick={openCreateDialog}
      >
        <AddIcon />
      </Fab>

      {/* Create/Edit Dialog */}
      <Dialog 
        open={isCreateEditDialogOpen} 
        onClose={() => setIsCreateEditDialogOpen(false)}
        maxWidth="md"
        fullWidth
        disableEscapeKeyDown={false}
        keepMounted={false}
        aria-labelledby="model-dialog-title"
      >
        <DialogTitle id="model-dialog-title">
          {editingModel ? 'Edit Model' : 'Add New Model'}
          <IconButton
            onClick={() => setIsCreateEditDialogOpen(false)}
            sx={{ position: 'absolute', right: 8, top: 8 }}
            aria-label="Close dialog"
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                label="Alias (Display Name)"
                value={formData.alias}
                onChange={(e) => setFormData({ ...formData, alias: e.target.value })}
                required
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              {formData.provider_name === 'ollama' ? (
                <Autocomplete
                  fullWidth
                  freeSolo
                  options={ollamaModels || []}
                  value={formData.model_string}
                  loading={ollamaModelsLoading}
                  onInputChange={(_, newInputValue) => {
                    setFormData({ ...formData, model_string: newInputValue });
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Model String"
                      required
                      helperText={
                        ollamaModelsLoading
                          ? 'Loading models from Ollama...'
                          : ollamaModels && ollamaModels.length > 0
                            ? `${ollamaModels.length} models available - select or enter custom name`
                            : 'Enter model name (models list unavailable)'
                      }
                    />
                  )}
                />
              ) : formData.provider_name === 'lmstudio' ? (
                <Autocomplete
                  fullWidth
                  freeSolo
                  options={lmstudioModels || []}
                  value={formData.model_string}
                  loading={lmstudioModelsLoading}
                  onInputChange={(_, newInputValue) => {
                    setFormData({ ...formData, model_string: newInputValue });
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Model String"
                      required
                      helperText={
                        lmstudioModelsLoading
                          ? 'Loading models from LMStudio...'
                          : lmstudioModels && lmstudioModels.length > 0
                            ? `${lmstudioModels.length} models available - select or enter custom name`
                            : 'Enter model name (models list unavailable)'
                      }
                    />
                  )}
                />
              ) : formData.provider_name === 'custom-oai' ? (
                <Autocomplete
                  fullWidth
                  freeSolo
                  options={customOaiModels || []}
                  value={formData.model_string}
                  loading={customOaiModelsLoading}
                  onInputChange={(_, newInputValue) => {
                    setFormData({ ...formData, model_string: newInputValue });
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Model String"
                      required
                      helperText={
                        !formData.host
                          ? 'Enter host first to load available models'
                          : customOaiModelsLoading
                            ? 'Loading models from server...'
                            : customOaiModels && customOaiModels.length > 0
                              ? `${customOaiModels.length} models available - select or enter custom name`
                              : 'Enter model name (models list unavailable)'
                      }
                    />
                  )}
                />
              ) : (
                <TextField
                  fullWidth
                  label="Model String"
                  value={formData.model_string}
                  onChange={(e) => setFormData({ ...formData, model_string: e.target.value })}
                  required
                  helperText="e.g., phi4-mini:3.8b-q8_0"
                />
              )}
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth required>
                <InputLabel>Provider</InputLabel>
                <Select
                  value={formData.provider_name}
                  label="Provider"
                  onChange={(e) => setFormData({ ...formData, provider_name: e.target.value })}
                >
                  {((modelProviders as any) || []).map((provider: any) => (
                    <MenuItem key={provider.name} value={provider.name}>
                      {provider.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth required>
                <InputLabel>Type</InputLabel>
                <Select
                  value={formData.model_type}
                  label="Type"
                  onChange={(e) => setFormData({ ...formData, model_type: e.target.value })}
                >
                  {MODEL_TYPES.map((type) => (
                    <MenuItem key={type} value={type}>
                      {type}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            {(formData.provider_name === 'ollama' || formData.provider_name === 'lmstudio' || formData.provider_name === 'custom-oai') && (
              <Grid size={{ xs: 12 }}>
                <Autocomplete
                  fullWidth
                  freeSolo
                  options={getHostsByProvider(formData.provider_name)}
                  value={formData.host || ''}
                  onInputChange={(_, newInputValue) => {
                    setFormData({ ...formData, host: newInputValue || undefined });
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Host (Optional)"
                      placeholder={
                        formData.provider_name === 'ollama' ? 'athena.local:11434' :
                        formData.provider_name === 'lmstudio' ? 'localhost:1234' :
                        'http://custom-server:8000'
                      }
                      helperText="Custom host for this model (leave empty to use environment default)"
                    />
                  )}
                />
              </Grid>
            )}
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                label="Description (Markdown supported)"
                multiline
                rows={4}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                helperText="Supports markdown formatting"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <TextField
                fullWidth
                label="Max Tokens"
                type="number"
                value={formData.max_new_tokens || ''}
                onChange={(e) => setFormData({ ...formData, max_new_tokens: e.target.value ? Number(e.target.value) : undefined })}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <TextField
                fullWidth
                label="Temperature"
                type="number"
                inputProps={{ step: 0.1, min: 0, max: 2 }}
                value={formData.temperature || ''}
                onChange={(e) => setFormData({ ...formData, temperature: e.target.value ? Number(e.target.value) : undefined })}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <TextField
                fullWidth
                label="Context Window"
                type="number"
                value={formData.num_ctx || ''}
                onChange={(e) => setFormData({ ...formData, num_ctx: e.target.value ? Number(e.target.value) : undefined })}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <Autocomplete
                multiple
                freeSolo
                options={availableTags}
                value={formData.tags}
                onChange={(_, newValue) => setFormData({ ...formData, tags: newValue })}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip variant="outlined" label={option} {...getTagProps({ index })} key={index} />
                  ))
                }
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Tags"
                    placeholder="Add tags..."
                  />
                )}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.trust_remote_code}
                      onChange={(e) => setFormData({ ...formData, trust_remote_code: e.target.checked })}
                    />
                  }
                  label="Trust Remote Code"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.is_favorite}
                      onChange={(e) => setFormData({ ...formData, is_favorite: e.target.checked })}
                    />
                  }
                  label="Mark as Favorite"
                />
              </Box>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsCreateEditDialogOpen(false)}>
            Cancel
          </Button>
          <Button 
            onClick={handleSave}
            variant="contained"
            disabled={!formData.alias || !formData.model_string || !formData.provider_name || !formData.model_type}
          >
            {editingModel ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Model Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="md"
        fullWidth
        aria-labelledby="detail-dialog-title"
        keepMounted={false}
      >
        <DialogTitle id="detail-dialog-title" sx={{ pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="h5" component="h2" sx={{ fontWeight: 'bold' }}>
                {selectedModel?.alias}
              </Typography>
              {selectedModel?.is_favorite && (
                <FavoriteIcon sx={{ color: '#ff6b6b' }} />
              )}
              <Chip 
                label={selectedModel?.provider_name}
                color="primary"
                variant="outlined"
              />
            </Box>
            <IconButton
              onClick={() => setDetailDialogOpen(false)}
              aria-label="Close dialog"
            >
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        
        <DialogContent sx={{ pt: 0 }}>
          {selectedModel && (
            <Box>
              {/* Basic Info */}
              <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                  Model Information
                </Typography>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Model String:</strong>
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 1 }}>
                      {selectedModel.model_string}
                    </Typography>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Type:</strong>
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 1 }}>
                      {selectedModel.model_type}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>

              {/* Parameters */}
              <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                  Model Parameters
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {selectedModel.max_new_tokens && (
                    <Chip label={`Max Tokens: ${selectedModel.max_new_tokens}`} variant="outlined" />
                  )}
                  {selectedModel.temperature !== undefined && (
                    <Chip label={`Temperature: ${selectedModel.temperature}`} variant="outlined" />
                  )}
                  {selectedModel.num_ctx && (
                    <Chip label={`Context Window: ${selectedModel.num_ctx}`} variant="outlined" />
                  )}
                  {selectedModel.trust_remote_code && (
                    <Chip label="Trust Remote Code" color="warning" variant="outlined" />
                  )}
                </Box>
              </Paper>

              {/* Tags */}
              {selectedModel.tags && selectedModel.tags.length > 0 && (
                <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                    Tags
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {selectedModel.tags.map((tag, index) => (
                      <Chip key={index} label={tag} color="primary" variant="outlined" />
                    ))}
                  </Box>
                </Paper>
              )}

              {/* Description */}
              {selectedModel.description && selectedModel.description.trim() && (
                <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                    Description
                  </Typography>
                                     <Box 
                     sx={{ 
                       '& h1, & h2, & h3, & h4, & h5, & h6': {
                         fontWeight: 'bold',
                         margin: '16px 0 8px 0',
                         '&:first-of-type': { marginTop: 0 }
                       },
                       '& h1': { fontSize: '1.5rem' },
                       '& h2': { fontSize: '1.25rem' },
                       '& h3': { fontSize: '1.1rem' },
                       '& p': {
                         margin: '8px 0',
                         lineHeight: 1.6
                       },
                       '& ul, & ol': {
                         margin: '8px 0',
                         paddingLeft: '24px'
                       },
                       '& li': {
                         margin: '4px 0'
                       },
                       '& code': {
                         backgroundColor: 'rgba(0, 0, 0, 0.05)',
                         padding: '2px 4px',
                         borderRadius: '4px',
                         fontFamily: 'monospace',
                         fontSize: '0.9em'
                       },
                       '& pre': {
                         backgroundColor: 'rgba(0, 0, 0, 0.05)',
                         padding: '12px',
                         borderRadius: '4px',
                         overflow: 'auto',
                         fontFamily: 'monospace'
                       },
                       '& table': {
                         width: '100%',
                         borderCollapse: 'collapse',
                         margin: '16px 0',
                         fontSize: '0.75rem',
                         border: '1px solid rgba(224, 224, 224, 1)'
                       },
                       '& th': {
                         border: '1px solid rgba(224, 224, 224, 1)',
                         padding: '6px 8px',
                         backgroundColor: 'rgba(0, 0, 0, 0.04)',
                         fontWeight: 'bold',
                         textAlign: 'left'
                       },
                       '& td': {
                         border: '1px solid rgba(224, 224, 224, 1)',
                         padding: '6px 8px',
                         textAlign: 'left'
                       },
                       '& tbody tr:nth-of-type(odd)': {
                         backgroundColor: 'rgba(0, 0, 0, 0.02)'
                       },
                       '& blockquote': {
                         borderLeft: '4px solid',
                         borderColor: 'primary.main',
                         paddingLeft: '16px',
                         margin: '16px 0',
                         fontStyle: 'italic'
                       }
                     }}
                   >
                     <ReactMarkdown
                       remarkPlugins={[remarkGfm]}
                       components={{
                         table: ({node, ...props}) => (
                           <Box sx={{ overflowX: 'auto', mb: 2 }}>
                             <table {...props} />
                           </Box>
                         )
                       }}
                     >
                       {selectedModel.description}
                     </ReactMarkdown>
                   </Box>
                </Paper>
              )}

              {/* Metadata */}
              {(selectedModel.created_at || selectedModel.updated_at) && (
                <Paper elevation={1} sx={{ p: 2 }}>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                    Metadata
                  </Typography>
                  <Grid container spacing={2}>
                    {selectedModel.created_at && (
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <Typography variant="body2" color="text.secondary">
                          <strong>Created:</strong>
                        </Typography>
                        <Typography variant="body1">
                          {new Date(selectedModel.created_at).toLocaleString()}
                        </Typography>
                      </Grid>
                    )}
                    {selectedModel.updated_at && (
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <Typography variant="body2" color="text.secondary">
                          <strong>Updated:</strong>
                        </Typography>
                        <Typography variant="body1">
                          {new Date(selectedModel.updated_at).toLocaleString()}
                        </Typography>
                      </Grid>
                    )}
                  </Grid>
                </Paper>
              )}
            </Box>
          )}
        </DialogContent>

        <DialogActions>
          <Button onClick={() => setDetailDialogOpen(false)}>
            Close
          </Button>
          {selectedModel && (
            <>
              <Button
                onClick={() => {
                  setDetailDialogOpen(false);
                  openEditDialog(selectedModel);
                }}
                startIcon={<EditIcon />}
              >
                Edit
              </Button>
              <Button
                onClick={() => {
                  setDetailDialogOpen(false);
                  handleDelete(selectedModel);
                }}
                color="error"
                startIcon={<DeleteIcon />}
              >
                Delete
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog 
        open={deleteDialogOpen} 
        onClose={() => setDeleteDialogOpen(false)}
        aria-labelledby="delete-dialog-title"
        keepMounted={false}
      >
        <DialogTitle id="delete-dialog-title">Delete Model</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete "{modelToDelete?.alias}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default ModelCatalog; 