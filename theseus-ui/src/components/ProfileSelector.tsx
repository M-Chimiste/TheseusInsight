import React, { useState } from 'react';
import {
  Box,
  Button,
  Select,
  MenuItem,
  Chip,
  Typography,
  Autocomplete,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Paper,
  Divider,
  Collapse,
  IconButton,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import {
  Clear as ClearIcon,
  Add as AddIcon,
  Person as PersonIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';

import { useProfile } from '../contexts/ProfileContext';
import { profileApi } from '../services/api';
import { useQuery } from '@tanstack/react-query';


interface ProfileSelectorProps {
  onProfileChange?: (profileIds: number[]) => void;
  onTagChange?: (tags: string[]) => void;
  allowMultiple?: boolean;
  showTags?: boolean;
  label?: string;
  compact?: boolean;
  showSmartBar?: boolean;
  defaultExpanded?: boolean;
}

const ProfileSelector: React.FC<ProfileSelectorProps> = ({
  onProfileChange,
  onTagChange,
  allowMultiple = false,
  showTags = false,
  label = 'Select Profile',
  compact = false,
  showSmartBar = true,
  defaultExpanded = false,
}) => {
  const { profiles, selectedProfileIds, setSelectedProfileIds, isLoading, getSelectedProfiles } = useProfile();
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);

  // Load unique tags
  const { data: uniqueTags } = useQuery({
    queryKey: ['profile-tags'],
    queryFn: async () => {
      const response = await profileApi.getAllTags();
      return response.data;
    },
  });

  const selectedProfiles = getSelectedProfiles();

  // Calculate combined stats for selected profiles
  const combinedStats = {
    totalPapers: selectedProfiles.reduce((sum, profile) => sum + (profile.total_papers || 0), 0),
    totalRecipients: new Set(selectedProfiles.flatMap(profile => profile.email_recipients || [])).size,
    profileCount: selectedProfiles.length,
  };

  const handleProfileChange = (event: SelectChangeEvent<number | number[]>) => {
    if (allowMultiple) {
      const value = event.target.value as number[];
      setSelectedProfileIds(value);
      onProfileChange?.(value);
    } else {
      const value = event.target.value as number;
      setSelectedProfileIds([value]);
      onProfileChange?.([value]);
    }
  };

  const handleTagChange = (_event: React.SyntheticEvent, value: string[]) => {
    setSelectedTags(value);
    onTagChange?.(value);
  };

  const handleRemoveProfile = (profileId: number) => {
    const newIds = selectedProfileIds.filter(id => id !== profileId);
    setSelectedProfileIds(newIds);
    onProfileChange?.(newIds);
  };

  const handleAddProfile = (profileId: number) => {
    if (!selectedProfileIds.includes(profileId)) {
      const newIds = [...selectedProfileIds, profileId];
      setSelectedProfileIds(newIds);
      onProfileChange?.(newIds);
    }
  };

  const clearFilters = () => {
    setSelectedProfileIds([]);
    setSelectedTags([]);
    onProfileChange?.([]);
    onTagChange?.([]);
  };

  const availableProfiles = profiles.filter(profile => !selectedProfileIds.includes(profile.id));

  if (isLoading) {
    return <Typography>Loading profiles...</Typography>;
  }

  // Smart Selection Bar (Option A)
  if (showSmartBar) {
    return (
      <Paper 
        variant="outlined" 
        sx={{ 
          borderRadius: 2,
          backgroundColor: 'background.default',
          overflow: 'hidden',
        }}
      >
        {/* Header with toggle */}
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between', 
          p: 2,
          pb: selectedProfiles.length > 0 ? 1 : 2
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle2" sx={{ color: 'text.secondary', fontWeight: 600 }}>
              Profiles:
            </Typography>
            {selectedProfiles.length > 0 && (
              <Typography variant="caption" sx={{ 
                color: 'text.secondary',
                backgroundColor: 'action.hover',
                px: 1,
                py: 0.25,
                borderRadius: 1,
                fontWeight: 500
              }}>
                {selectedProfiles.length} selected
              </Typography>
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {selectedProfiles.length > 0 && (
              <IconButton
                onClick={() => setExpanded(!expanded)}
                size="small"
                sx={{ color: 'text.secondary' }}
              >
                {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </IconButton>
            )}
            {selectedProfiles.length > 0 && (
              <Button
                onClick={clearFilters}
                size="small"
                sx={{ 
                  minWidth: 'auto',
                  color: 'text.secondary',
                  '&:hover': { color: 'error.main' }
                }}
                startIcon={<ClearIcon fontSize="small" />}
              >
                Clear all
              </Button>
            )}
          </Box>
        </Box>
        
        {/* Profile chips row */}
        <Box sx={{ px: 2, pb: selectedProfiles.length > 0 ? 1 : 2 }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
            {selectedProfiles.map((profile) => (
              <Chip
                key={profile.id}
                label={profile.name}
                onDelete={() => handleRemoveProfile(profile.id)}
                sx={{
                  bgcolor: profile.color || '#1976d2',
                  color: 'white',
                  '& .MuiChip-deleteIcon': {
                    color: 'rgba(255, 255, 255, 0.8)',
                    '&:hover': {
                      color: 'white',
                    }
                  }
                }}
                icon={<PersonIcon sx={{ color: 'rgba(255, 255, 255, 0.8)' }} />}
              />
            ))}
            
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              onClick={() => setAddDialogOpen(true)}
              sx={{
                borderStyle: 'dashed',
                borderColor: 'primary.main',
                color: 'primary.main',
                '&:hover': {
                  backgroundColor: 'primary.50',
                  borderStyle: 'dashed',
                }
              }}
            >
              Add Profile
            </Button>
          </Box>
        </Box>

        {/* Collapsible content */}
        <Collapse in={expanded && selectedProfiles.length > 0}>
          <Box sx={{ px: 2, pb: 2 }}>
            {/* Combined stats */}
            <Box 
              sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 2, 
                p: 1.5, 
                backgroundColor: 'action.hover', 
                borderRadius: 1,
                fontSize: '0.875rem',
                mb: 1
              }}
            >
              <Typography variant="body2" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                📊 <strong>Combined:</strong> 
                {combinedStats.totalPapers.toLocaleString()} papers
              </Typography>
              <Divider orientation="vertical" flexItem />
              <Typography variant="body2" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                📧 {combinedStats.totalRecipients} unique recipients
              </Typography>
              {combinedStats.profileCount > 1 && (
                <>
                  <Divider orientation="vertical" flexItem />
                  <Typography variant="body2" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    👥 {combinedStats.profileCount} profiles
                  </Typography>
                </>
              )}
            </Box>

            {/* Profile details */}
            {selectedProfiles.length === 1 ? (
              <Typography variant="body2" color="text.secondary">
                Newsletter will be generated using: <strong>{selectedProfiles[0].name}</strong>
                {selectedProfiles[0].description && ` - ${selectedProfiles[0].description}`}
              </Typography>
            ) : selectedProfiles.length > 1 ? (
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Newsletter will be generated using: <strong>{selectedProfiles[0].name}</strong> (primary)
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Research interests and email recipients will be combined from all selected profiles.
                </Typography>
              </Box>
            ) : null}
          </Box>
        </Collapse>

        {/* Empty state */}
        {selectedProfiles.length === 0 && (
          <Box sx={{ px: 2, pb: 2 }}>
            <Box sx={{ textAlign: 'center', py: 2, color: 'text.secondary' }}>
              <PersonIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1 }} />
              <Typography variant="body2">
                No profiles selected. Click "Add Profile" to get started.
              </Typography>
            </Box>
          </Box>
        )}

        {/* Add Profile Dialog */}
        <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Add Profile</DialogTitle>
          <DialogContent sx={{ p: 0 }}>
            <List>
              {availableProfiles.map((profile) => (
                <ListItem key={profile.id} disablePadding>
                  <ListItemButton
                    onClick={() => {
                      handleAddProfile(profile.id);
                      setAddDialogOpen(false);
                    }}
                  >
                    <ListItemIcon>
                      <Box
                        sx={{
                          width: 16,
                          height: 16,
                          borderRadius: '50%',
                          bgcolor: profile.color || '#1976d2',
                        }}
                      />
                    </ListItemIcon>
                    <ListItemText
                      primary={profile.name}
                      secondary={
                        <Box sx={{ display: 'flex', gap: 2, mt: 0.5 }}>
                          <Typography variant="caption">
                            📄 {(profile.total_papers || 0).toLocaleString()} papers
                          </Typography>
                          <Typography variant="caption">
                            📧 {(profile.email_recipients?.length || 0)} recipients
                          </Typography>
                          {profile.tags && profile.tags.length > 0 && (
                            <Typography variant="caption">
                              🏷️ {profile.tags.join(', ')}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}
              {availableProfiles.length === 0 && (
                <ListItem>
                  <ListItemText
                    primary="No more profiles available"
                    secondary="All profiles are already selected"
                    sx={{ textAlign: 'center', color: 'text.secondary' }}
                  />
                </ListItem>
              )}
            </List>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setAddDialogOpen(false)}>Cancel</Button>
          </DialogActions>
        </Dialog>
      </Paper>
    );
  }

  // Legacy compact mode (preserved for backward compatibility)
  if (compact) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 200 }}>
        <Select
          value={allowMultiple ? selectedProfileIds : selectedProfileIds[0] || ''}
          onChange={handleProfileChange}
          multiple={allowMultiple}
          size="small"
          variant="outlined"
          displayEmpty
          sx={{ 
            minWidth: 150,
            '& .MuiSelect-select': {
              py: 1,
              fontSize: '0.875rem',
            }
          }}
          renderValue={(selected) => {
            if (allowMultiple) {
              const selectedIds = selected as number[];
              if (selectedIds.length === 0) return 'Select Profiles';
              if (selectedIds.length === 1) {
                const profile = profiles.find((p) => p.id === selectedIds[0]);
                return profile?.name || 'Profile';
              }
              return `${selectedIds.length} Profiles`;
            }
            const profile = profiles.find((p) => p.id === selected);
            return profile?.name || 'Select Profile';
          }}
        >
          {profiles.map((profile) => (
            <MenuItem key={profile.id} value={profile.id}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: profile.color || '#1976d2',
                  }}
                />
                {profile.name}
              </Box>
            </MenuItem>
          ))}
        </Select>

        {selectedProfileIds.length > 0 && (
          <Button
            onClick={clearFilters}
            variant="text"
            size="small"
            sx={{ 
              minWidth: 'auto',
              p: 0.5,
              color: 'text.secondary',
              '&:hover': {
                color: 'text.primary',
              }
            }}
          >
            <ClearIcon fontSize="small" />
          </Button>
        )}
      </Box>
    );
  }

  // Legacy full mode (preserved for backward compatibility)
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="body2" sx={{ mb: 1, color: 'text.secondary', fontWeight: 500 }}>
          {label}
        </Typography>
        <Select
          value={allowMultiple ? selectedProfileIds : selectedProfileIds[0] || ''}
          onChange={handleProfileChange}
          multiple={allowMultiple}
          fullWidth
          displayEmpty
          variant="outlined"
          renderValue={(selected) => {
            if (allowMultiple) {
              const selectedIds = selected as number[];
              if (selectedIds.length === 0) return 'Select Profiles';
              return (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {selectedIds.map((id) => {
                    const profile = profiles.find((p) => p.id === id);
                    return (
                      <Chip
                        key={id}
                        label={profile?.name || `Profile ${id}`}
                        size="small"
                        sx={{ bgcolor: profile?.color || '#1976d2', color: 'white' }}
                      />
                    );
                  })}
                </Box>
              );
            }
            const profile = profiles.find((p) => p.id === selected);
            return profile?.name || 'Select Profile';
          }}
        >
          {profiles.map((profile) => (
            <MenuItem key={profile.id} value={profile.id}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: profile.color || '#1976d2',
                  }}
                />
                {profile.name}
              </Box>
            </MenuItem>
          ))}
        </Select>
      </Box>

      {showTags && (
        <Box>
          <Typography variant="body2" sx={{ mb: 1, color: 'text.secondary', fontWeight: 500 }}>
            Filter by Tags
          </Typography>
          <Autocomplete
            multiple
            options={uniqueTags || []}
            value={selectedTags}
            onChange={handleTagChange}
            renderInput={(params) => (
              <TextField
                {...params}
                variant="outlined"
                placeholder="Select tags..."
              />
            )}
            renderTags={(value, getTagProps) =>
              value.map((option, index) => (
                <Chip
                  variant="outlined"
                  label={option}
                  {...getTagProps({ index })}
                  key={option}
                />
              ))
            }
          />
        </Box>
      )}

      {(selectedProfileIds.length > 0 || selectedTags.length > 0) && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            onClick={clearFilters}
            variant="outlined"
            size="small"
            startIcon={<ClearIcon />}
          >
            Clear All
          </Button>
        </Box>
      )}
    </Box>
  );
};

export default ProfileSelector; 