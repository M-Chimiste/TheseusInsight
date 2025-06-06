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
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { modelCatalogApi, settingsApi } from '../services/api';

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
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // View and filter state
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showFilters, setShowFilters] = useState(false);
  const [search, setSearch] = useState('');
  const [providerFilter, setProviderFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [favoriteFilter, setFavoriteFilter] = useState<boolean | null>(null);
  const [page, setPage] = useState(1);
  const [expandedCard, setExpandedCard] = useState<number | null>(null);
  
  // Dialog state
  const [isCreateEditDialogOpen, setIsCreateEditDialogOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelCatalogEntry | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<ModelCatalogEntry | null>(null);
  
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
    trust_remote_code: false,
    tags: [],
    is_favorite: false
  });

  // Available tags for autocomplete
  const availableTags = [
    'fast', 'accurate', 'reasoning', 'coding', 'creative', 'small', 'large', 
    'efficient', 'multilingual', 'vision', 'experimental', 'production'
  ];

  // Queries
  const { data: modelsData, isLoading: isLoadingModels } = useQuery({
    queryKey: ['modelCatalog', { 
      search, 
      provider_name: providerFilter || undefined, 
      model_type: typeFilter || undefined, 
      is_favorite: favoriteFilter, 
      page,
      page_size: 12
    }],
    queryFn: () => modelCatalogApi.searchModels({
      search: search || undefined,
      provider_name: providerFilter || undefined,
      model_type: typeFilter || undefined,
      is_favorite: favoriteFilter,
      page,
      page_size: 12
    }).then(res => res.data),
  });

  const { data: modelProviders } = useQuery({
    queryKey: ['modelProviders'],
    queryFn: () => settingsApi.getModelProviders().then(res => res.data || []),
  });

  // Mutations
  const createModelMutation = useMutation({
    mutationFn: (model: any) => modelCatalogApi.createModel(model),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modelCatalog'] });
      setSuccess('Model created successfully');
      setIsCreateEditDialogOpen(false);
      resetForm();
    },
    onError: (error: any) => setError(error?.response?.data?.detail || 'Failed to create model'),
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

  const getDescriptionSnippet = (description: string, maxLength: number = 100) => {
    if (!description) return '';
    if (description.length <= maxLength) return description;
    return description.substring(0, maxLength) + '...';
  };

  const ModelCard = ({ model, isExpanded }: { model: ModelCatalogEntry; isExpanded: boolean }) => (
    <Card 
      elevation={model.is_favorite ? 3 : 1}
      sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        border: model.is_favorite ? '2px solid #ff6b6b' : undefined,
        '&:hover': { elevation: 4 }
      }}
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

        {model.description && (
          <Box sx={{ mb: 2 }}>
            <Collapse in={isExpanded} collapsedSize={60}>
              <Paper elevation={0} sx={{ p: 1, bgcolor: 'grey.50' }}>
                <ReactMarkdown>
                  {isExpanded ? model.description : getDescriptionSnippet(model.description, 150)}
                </ReactMarkdown>
              </Paper>
            </Collapse>
            {model.description.length > 150 && (
              <Button
                size="small"
                onClick={() => setExpandedCard(isExpanded ? null : model.id)}
                startIcon={isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                sx={{ mt: 1 }}
              >
                {isExpanded ? 'Show Less' : 'Show More'}
              </Button>
            )}
          </Box>
        )}

        {/* Model Parameters */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
          {model.max_new_tokens && (
            <Chip label={`Tokens: ${model.max_new_tokens}`} size="small" />
          )}
          {model.temperature !== undefined && (
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
            onClick={() => toggleFavoriteMutation.mutate(model.id)}
            color={model.is_favorite ? 'error' : 'default'}
          >
            {model.is_favorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
          </IconButton>
          <IconButton onClick={() => openEditDialog(model)}>
            <EditIcon />
          </IconButton>
        </Box>
        <IconButton onClick={() => handleDelete(model)} color="error">
          <DeleteIcon />
        </IconButton>
      </CardActions>
    </Card>
  );

  if (isLoadingModels) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
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
              <Grid size={{ xs: 12, sm: 4 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Provider</InputLabel>
                  <Select
                    value={providerFilter}
                    label="Provider"
                    onChange={(e) => setProviderFilter(e.target.value)}
                  >
                    <MenuItem value="">All Providers</MenuItem>
                    {(modelProviders || []).map((provider: any) => (
                      <MenuItem key={provider.name} value={provider.name}>
                        {provider.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
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
              <Grid size={{ xs: 12, sm: 4 }}>
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
      {modelsData?.models && modelsData.models.length > 0 ? (
        <>
          <Grid container spacing={3}>
            {modelsData.models.map((model: ModelCatalogEntry) => (
              <Grid size={{ xs: 12, sm: viewMode === 'grid' ? 6 : 12, md: viewMode === 'grid' ? 4 : 12 }} key={model.id}>
                <ModelCard model={model} isExpanded={expandedCard === model.id} />
              </Grid>
            ))}
          </Grid>

          {/* Pagination */}
          {modelsData.total_pages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <Pagination
                count={modelsData.total_pages}
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
            {search || providerFilter || typeFilter || favoriteFilter !== null
              ? 'Try adjusting your filters'
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
      >
        <DialogTitle>
          {editingModel ? 'Edit Model' : 'Add New Model'}
          <IconButton
            onClick={() => setIsCreateEditDialogOpen(false)}
            sx={{ position: 'absolute', right: 8, top: 8 }}
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
              <TextField
                fullWidth
                label="Model String"
                value={formData.model_string}
                onChange={(e) => setFormData({ ...formData, model_string: e.target.value })}
                required
                helperText="e.g., phi4-mini:3.8b-q8_0"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth required>
                <InputLabel>Provider</InputLabel>
                <Select
                  value={formData.provider_name}
                  label="Provider"
                  onChange={(e) => setFormData({ ...formData, provider_name: e.target.value })}
                >
                  {(modelProviders || []).map((provider: any) => (
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

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Model</DialogTitle>
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