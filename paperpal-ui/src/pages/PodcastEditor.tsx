import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { useListScripts, useDeleteScript } from '../hooks/useScript';
import ScriptEditor from '../components/ScriptEditor/ScriptEditor';
import { Script } from '../types/api';

const PodcastEditor: React.FC = () => {
  const [selectedScript, setSelectedScript] = useState<string | null>(null);
  const [isNewScriptDialogOpen, setIsNewScriptDialogOpen] = useState(false);
  const [newScriptName, setNewScriptName] = useState('');

  const {
    data: scripts,
    isLoading,
    refetch: refetchScripts,
  } = useListScripts();

  const { mutate: deleteScript } = useDeleteScript();

  const handleCreateNewScript = () => {
    if (!newScriptName.trim()) return;
    setSelectedScript(newScriptName);
    setIsNewScriptDialogOpen(false);
    setNewScriptName('');
  };

  const handleDeleteScript = (filename: string) => {
    deleteScript(filename, {
      onSuccess: () => {
        refetchScripts();
        if (selectedScript === filename) {
          setSelectedScript(null);
        }
      },
    });
  };

  const handleScriptSaved = () => {
    refetchScripts();
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 4,
        }}
      >
        <Typography variant="h2" gutterBottom>
          Podcast Script Editor
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setIsNewScriptDialogOpen(true)}
        >
          New Script
        </Button>
      </Box>

      {selectedScript ? (
        <ScriptEditor
          filename={selectedScript}
          onSave={handleScriptSaved}
        />
      ) : (
        <Box>
          <Typography variant="h5" gutterBottom>
            Available Scripts
          </Typography>
          <List>
            {scripts?.map((script) => (
              <ListItem
                key={script.filename}
                sx={{
                  bgcolor: 'background.paper',
                  mb: 1,
                  borderRadius: 1,
                }}
              >
                <ListItemText
                  primary={script.filename}
                  secondary={new Date(
                    script.last_modified * 1000
                  ).toLocaleString()}
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    onClick={() => setSelectedScript(script.filename)}
                  >
                    <EditIcon />
                  </IconButton>
                  <IconButton
                    edge="end"
                    onClick={() => handleDeleteScript(script.filename)}
                  >
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </Box>
      )}

      <Dialog
        open={isNewScriptDialogOpen}
        onClose={() => setIsNewScriptDialogOpen(false)}
      >
        <DialogTitle>Create New Script</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Script Name"
            fullWidth
            value={newScriptName}
            onChange={(e) => setNewScriptName(e.target.value)}
            helperText="The script will be saved with a .json extension"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsNewScriptDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateNewScript} disabled={!newScriptName.trim()}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default PodcastEditor; 