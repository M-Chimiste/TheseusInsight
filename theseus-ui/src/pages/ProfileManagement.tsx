import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardActions,
  Typography,
  TextField,
  Grid,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
  Autocomplete,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';

import { 
  profileApi, 
  settingsApi,
  type ProfileApiResponse, 
  type ProfileCreateRequest, 
  type ProfileUpdateRequest,
  type ProfileInterestResponse
} from '../services/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useProfile } from '../contexts/ProfileContext';
import taxonomy from '../arxiv_taxonomy.json';

interface ProfileFormData {
  name: string;
  description: string;
  color: string;
  tags: string[];
  email_recipients: string[];
  arxiv_filters: string[];
  research_interests: string;
}

const ProfileManagement: React.FC = () => {
  const { profiles, refreshProfiles, isLoading, error } = useProfile();
  const queryClient = useQueryClient();
  
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [profileToDelete, setProfileToDelete] = useState<ProfileApiResponse | null>(null);
  const [editingProfile, setEditingProfile] = useState<ProfileApiResponse | null>(null);
  const [formData, setFormData] = useState<ProfileFormData>({
    name: '',
    description: '',
    color: '#2196F3',
    tags: [],
    email_recipients: [],
    arxiv_filters: [],
    research_interests: '',
  });

  // ArXiv category state
  const [selectedArxivMain, setSelectedArxivMain] = useState<string>('');
  const [selectedArxivSubs, setSelectedArxivSubs] = useState<string[]>([]);

  // Email input state for better user experience
  const [emailInput, setEmailInput] = useState<string>('');

  // Alias taxonomy as any to allow dynamic indexing
  const taxonomyAny = taxonomy as any;

  // Load available tags for autocomplete
  const { data: availableTags } = useQuery({
    queryKey: ['profile-tags'],
    queryFn: async () => {
      const response = await profileApi.getAllTags();
      return response.data;
    },
  });

  // Load settings for default profile population
  const { data: researchInterests } = useQuery({
    queryKey: ['research-interests'],
    queryFn: async () => {
      const response = await settingsApi.getResearchInterests();
      return response.data;
    },
  });

  const { data: emailRecipients } = useQuery({
    queryKey: ['email-recipients'],
    queryFn: async () => {
      const response = await settingsApi.getEmailRecipients();
      return response.data;
    },
  });

  const { data: arxivCategories } = useQuery({
    queryKey: ['arxiv-categories'],
    queryFn: async () => {
      const response = await settingsApi.getArxivCategories();
      return response.data;
    },
  });

  // Load profile interests when editing
  const { data: profileInterests } = useQuery<ProfileInterestResponse[] | null>({
    queryKey: ['profile-interests', editingProfile?.id],
    queryFn: async () => {
      if (!editingProfile) return null;
      const response = await profileApi.getProfileInterests(editingProfile.id);
      return response.data;
    },
    enabled: !!editingProfile,
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: (profile: ProfileCreateRequest) => profileApi.createProfile(profile),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      refreshProfiles();
      handleCloseDialog();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, profile }: { id: number; profile: ProfileUpdateRequest }) => 
      profileApi.updateProfile(id, profile),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      refreshProfiles();
      handleCloseDialog();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => profileApi.deleteProfile(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      refreshProfiles();
    },
  });

  // Update research interests when profile interests are loaded
  useEffect(() => {
    if (profileInterests && editingProfile) {
      const interestsText = profileInterests.map(interest => interest.interest_text).join('\n');
      setFormData(prev => ({ ...prev, research_interests: interestsText }));
    }
  }, [profileInterests, editingProfile]);

  // Helper function to parse arxiv_filters back to main/sub categories
  const parseArxivFilters = (filters: any) => {
    if (!filters || typeof filters !== 'object') return { main: '', subs: [] };
    
    if (Array.isArray(filters)) {
      // Handle array format (legacy)
      const mainCategory = filters.length > 0 ? filters[0].split('.')[0] : '';
      return { main: mainCategory, subs: filters };
    } else if (filters.main_category && filters.filter_categories) {
      // Handle object format with main_category and filter_categories
      return { main: filters.main_category, subs: filters.filter_categories };
    }
    
    return { main: '', subs: [] };
  };

  // Helper function to count ArXiv filters correctly
  const getArxivFiltersCount = (filters: any): number => {
    if (!filters) return 0;
    
    if (Array.isArray(filters)) {
      // Legacy format: count array length
      return filters.length;
    } else if (filters.filter_categories && Array.isArray(filters.filter_categories)) {
      // New format: count subcategories
      return filters.filter_categories.length;
    }
    
    return 0;
  };

  // Event handlers
  const handleOpenDialog = (profile?: ProfileApiResponse) => {
    if (profile) {
      setEditingProfile(profile);
      
      // Parse arxiv_filters for the dropdowns
      const parsedArxiv = parseArxivFilters(profile.arxiv_filters);
      setSelectedArxivMain(parsedArxiv.main);
      setSelectedArxivSubs(parsedArxiv.subs);
      
      // Initialize email input from profile data
      const emailRecipientsArray = Array.isArray(profile.email_recipients) ? profile.email_recipients : [];
      setEmailInput(emailRecipientsArray.join('\n'));
      
      setFormData({
        name: profile.name,
        description: profile.description || '',
        color: profile.color || '#2196F3',
        tags: Array.isArray(profile.tags) ? profile.tags : [],
        email_recipients: emailRecipientsArray,
        arxiv_filters: Array.isArray(profile.arxiv_filters) ? profile.arxiv_filters : [],
        research_interests: '', // Will be loaded from profileInterests query
      });
    } else {
      setEditingProfile(null);
      
      // Populate with existing settings when creating a new profile
      const emailRecipientsArray = emailRecipients?.recipients 
        ? Array.isArray(emailRecipients.recipients) ? emailRecipients.recipients : []
        : [];
      
      // Initialize email input from current settings
      setEmailInput(emailRecipientsArray.join('\n'));
      
      // Initialize ArXiv settings from current settings
      const arxivMain = arxivCategories?.main_category || 'cs';
      const arxivSubs = arxivCategories?.filter_categories || [];
      
      setSelectedArxivMain(arxivMain);
      setSelectedArxivSubs(arxivSubs);
      
      setFormData({
        name: '',
        description: '',
        color: '#2196F3',
        tags: [],
        email_recipients: emailRecipientsArray,
        arxiv_filters: arxivSubs,
        research_interests: researchInterests?.interests || '',
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingProfile(null);
    setSelectedArxivMain('');
    setSelectedArxivSubs([]);
    setEmailInput('');
    setFormData({
      name: '',
      description: '',
      color: '#2196F3',
      tags: [],
      email_recipients: [],
      arxiv_filters: [],
      research_interests: '',
    });
  };

  const handleInputChange = (field: keyof ProfileFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleTagChange = (_event: React.SyntheticEvent, value: string[]) => {
    setFormData(prev => ({ ...prev, tags: value }));
  };

  // Email parsing function to handle both commas and newlines
  const parseEmailRecipients = (input: string): string[] => {
    if (!input.trim()) return [];
    
    return input
      .split(/[,\n\s;]+/) // Split by comma, newline, space, or semicolon
      .map(email => email.trim())
      .filter(email => email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) // Basic email validation
      .filter((email, index, arr) => arr.indexOf(email) === index); // Remove duplicates
  };

  const handleEmailRecipientsChange = (input: string) => {
    setEmailInput(input);
    const parsedEmails = parseEmailRecipients(input);
    setFormData(prev => ({ ...prev, email_recipients: parsedEmails }));
  };

  const handleSubmit = async () => {
    // Parse research interests from form data
    const researchInterestsArray = formData.research_interests
      ? formData.research_interests.split('\n').filter((line: string) => line.trim() && !line.trim().startsWith('#'))
      : [];

    // Create arxiv_filters object from selected categories
    const arxivFiltersObject = {
      main_category: selectedArxivMain,
      filter_categories: selectedArxivSubs
    };

    const profileData = {
      name: formData.name,
      description: formData.description || undefined,
      color: formData.color,
      tags: formData.tags,
      email_recipients: formData.email_recipients,
      arxiv_filters: arxivFiltersObject as any, // Backend expects Dict[str, Any]
      research_interests: researchInterestsArray, // Include for both create and update
    };

    if (editingProfile) {
      updateMutation.mutate({ id: editingProfile.id, profile: profileData as any });
    } else {
      createMutation.mutate(profileData as any);
    }
  };

  const handleDelete = (profile: ProfileApiResponse) => {
    setProfileToDelete(profile);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (profileToDelete) {
      deleteMutation.mutate(profileToDelete.id);
    }
    setDeleteDialogOpen(false);
    setProfileToDelete(null);
  };

  const predefinedColors = [
    '#2196F3', '#4CAF50', '#FF9800', '#F44336', 
    '#9C27B0', '#00BCD4', '#8BC34A', '#FFC107'
  ];

  // Handle loading state
  if (isLoading) {
    return (
      <Box sx={{ p: 3, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading profiles...</Typography>
      </Box>
    );
  }

  // Handle error state
  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>Profile Management</Typography>
        <Box sx={{ p: 2, bgcolor: 'error.light', color: 'error.contrastText', borderRadius: 1 }}>
          <Typography>Error loading profiles: {error}</Typography>
          <Button 
            variant="contained" 
            onClick={refreshProfiles} 
            sx={{ mt: 2 }}
          >
            Retry
          </Button>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Profile Management</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          Create Profile
        </Button>
      </Box>

      {profiles.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No profiles found
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Create your first profile to get started
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
          >
            Create Profile
          </Button>
        </Box>
      ) : (
        <Grid container spacing={3}>
          {profiles.map((profile) => (
            <Grid size={{ xs: 12, md: 6, lg: 4 }} key={profile.id}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Box
                    sx={{
                      width: 24,
                      height: 24,
                      borderRadius: '50%',
                      bgcolor: profile.color || '#2196F3',
                      mr: 2,
                    }}
                  />
                  <Typography variant="h6" sx={{ flexGrow: 1 }}>
                    {profile.name}
                  </Typography>
                  {profile.is_default && (
                    <Chip label="Default" size="small" color="primary" />
                  )}
                </Box>

                {profile.description && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {profile.description}
                  </Typography>
                )}

                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" gutterBottom>
                    Papers: {profile.total_papers || 0}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    Recipients: {profile.email_recipients?.length || 0}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    ArXiv Filters: {getArxivFiltersCount(profile.arxiv_filters)}
                  </Typography>
                </Box>

                {profile.tags && profile.tags.length > 0 && (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
                    {profile.tags.map((tag) => (
                      <Chip key={tag} label={tag} size="small" variant="outlined" />
                    ))}
                  </Box>
                )}
              </CardContent>

              <CardActions>
                <Button
                  size="small"
                  startIcon={<EditIcon />}
                  onClick={() => handleOpenDialog(profile)}
                >
                  Edit
                </Button>
                {!profile.is_default && (
                  <Button
                    size="small"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={() => handleDelete(profile)}
                  >
                    Delete
                  </Button>
                )}
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>
      )}

      {/* Profile Form Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingProfile ? 'Edit Profile' : 'Create New Profile'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, pt: 1 }}>
            <TextField
              label="Profile Name"
              value={formData.name}
              onChange={(e) => handleInputChange('name', e.target.value)}
              required
              fullWidth
            />

            <TextField
              label="Description"
              value={formData.description}
              onChange={(e) => handleInputChange('description', e.target.value)}
              multiline
              rows={3}
              fullWidth
            />

            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Color
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {predefinedColors.map((color) => (
                  <IconButton
                    key={color}
                    onClick={() => handleInputChange('color', color)}
                    sx={{
                      width: 40,
                      height: 40,
                      bgcolor: color,
                      border: formData.color === color ? '3px solid #000' : '1px solid #ccc',
                      '&:hover': { scale: 1.1 },
                    }}
                  />
                ))}
              </Box>
            </Box>

            <Autocomplete
              multiple
              freeSolo
              options={availableTags || []}
              value={Array.isArray(formData.tags) ? formData.tags : []}
              onChange={handleTagChange}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Tags"
                  placeholder="Add tags..."
                />
              )}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip
                    {...getTagProps({ index })}
                    key={option}
                    label={option}
                    size="small"
                  />
                ))
              }
            />

            <TextField
              label="Email Recipients (one per line or comma-separated)"
              value={emailInput}
              onChange={(e) => handleEmailRecipientsChange(e.target.value)}
              multiline
              rows={4}
              fullWidth
              placeholder="user1@example.com, user2@example.com&#10;user3@example.com"
              helperText={!editingProfile ? "Pre-populated from current settings. Supports comma and newline separation." : "Supports comma and newline separation."}
            />
            
            {/* Email chips display for visual feedback */}
            {formData.email_recipients.length > 0 && (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
                {formData.email_recipients.map((email, index) => (
                  <Chip
                    key={index}
                    label={email}
                    size="small"
                    color="primary"
                    variant="outlined"
                    onDelete={() => {
                      const updatedEmails = formData.email_recipients.filter((_, i) => i !== index);
                      setFormData(prev => ({ ...prev, email_recipients: updatedEmails }));
                      setEmailInput(updatedEmails.join('\n'));
                    }}
                  />
                ))}
              </Box>
            )}

            <TextField
              label="Research Interests (one per line)"
              value={formData.research_interests}
              onChange={(e) => handleInputChange('research_interests', e.target.value)}
              multiline
              rows={6}
              fullWidth
              placeholder="1. Machine learning and AI&#10;2. Natural language processing&#10;3. Computer vision"
              helperText={
                editingProfile 
                  ? "Edit this profile's specific research interests" 
                  : "Automatically populated from current research interests in settings"
              }
            />

            {/* ArXiv Categories Section */}
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                ArXiv Categories
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* Main Category Selector */}
                <Autocomplete
                  options={Object.entries(taxonomyAny.main_categories).map(([value, label]) => ({ value: value as string, label: label as string }))}
                  getOptionLabel={(option) => option.label as string}
                  value={taxonomyAny.main_categories[selectedArxivMain] ? { value: selectedArxivMain, label: `${selectedArxivMain} - ${taxonomyAny.main_categories[selectedArxivMain]}` } : null}
                  onChange={(_, newValue) => {
                    setSelectedArxivMain(newValue?.value || '');
                    setSelectedArxivSubs([]);
                  }}
                  renderInput={(params) => <TextField {...params} label="Main Category" fullWidth />}
                />
                
                {/* Subcategories Multi-Select */}
                <Autocomplete
                  multiple
                  filterSelectedOptions
                  isOptionEqualToValue={(option, value) => option.value === value.value}
                  options={Object.entries(taxonomyAny[selectedArxivMain] || {}).map(([sub, desc]) => ({ value: `${selectedArxivMain}.${sub}`, label: `${selectedArxivMain}.${sub} - ${desc}` }))}
                  getOptionLabel={(option) => option.label as string}
                  value={Object.entries(taxonomyAny[selectedArxivMain] || {})
                    .map(([sub, desc]) => ({ value: `${selectedArxivMain}.${sub}`, label: `${selectedArxivMain}.${sub} - ${desc}` }))
                    .filter(opt => selectedArxivSubs.includes(opt.value))
                  }
                  onChange={(_, newValues) => setSelectedArxivSubs((newValues as any[]).map(opt => opt.value))}
                  renderTags={(value, getTagProps) =>
                    value.map((option, index) => {
                      const tagProps = getTagProps({ index });
                      const { key, ...otherProps } = tagProps;
                      return <Chip key={key} label={option.label as string} {...otherProps} />;
                    })
                  }
                  renderInput={(params) => <TextField {...params} label="Subcategories" placeholder="Select subcategories" fullWidth />}
                />
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                {!editingProfile ? "Pre-populated from current ArXiv settings" : ""}
              </Typography>
            </Box>

            {!editingProfile && (
              <Box sx={{ p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
                <Typography variant="body2" color="info.contrastText">
                  <strong>Note:</strong> New profiles will be automatically populated with your current research interests from settings.
                </Typography>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} startIcon={<CancelIcon />}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            startIcon={<SaveIcon />}
            disabled={!formData.name || createMutation.isPending || updateMutation.isPending}
          >
            {createMutation.isPending || updateMutation.isPending ? (
              <CircularProgress size={20} />
            ) : (
              editingProfile ? 'Update' : 'Create'
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-description"
      >
        <DialogTitle id="delete-dialog-title">Confirm Delete</DialogTitle>
        <DialogContent>
          <DialogContentText id="delete-dialog-description">
            Are you sure you want to delete the profile "{profileToDelete?.name}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} color="primary">
            Cancel
          </Button>
          <Button 
            onClick={handleDeleteConfirm} 
            color="error" 
            variant="contained"
            autoFocus
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ProfileManagement;