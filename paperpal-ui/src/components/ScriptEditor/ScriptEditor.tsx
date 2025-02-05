import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  TextField,
  Typography,
  Alert,
  Snackbar,
  CircularProgress,
} from '@mui/material';
import { Add as AddIcon, Save as SaveIcon } from '@mui/icons-material';
import { useLoadScript, useSaveScript } from '../../hooks/useScript';
import { DialogueItem, Script } from '../../types/api';
import ScriptList from './ScriptList';

interface ScriptEditorProps {
  initialScript?: Script;
  filename?: string;
  onSave?: (script: Script) => void;
}

const ScriptEditor: React.FC<ScriptEditorProps> = ({
  initialScript,
  filename,
  onSave,
}) => {
  const [items, setItems] = useState<DialogueItem[]>(
    initialScript?.dialogue || []
  );
  const [newItemText, setNewItemText] = useState('');
  const [currentSpeaker, setCurrentSpeaker] = useState<'speaker-1' | 'speaker-2'>(
    'speaker-1'
  );
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    data: loadedScript,
    isLoading: isLoadingScript,
    error: loadError,
  } = useLoadScript(filename || '');

  const {
    mutate: saveScript,
    isLoading: isSaving,
    error: saveError,
  } = useSaveScript();

  useEffect(() => {
    if (loadedScript) {
      setItems(loadedScript.dialogue);
    }
  }, [loadedScript]);

  useEffect(() => {
    if (loadError) {
      setError(loadError.message);
    }
  }, [loadError]);

  useEffect(() => {
    if (saveError) {
      setError(saveError.message);
    }
  }, [saveError]);

  const handleAddItem = () => {
    if (!newItemText.trim()) return;

    const newItem: DialogueItem = {
      speaker: currentSpeaker,
      text: newItemText.trim(),
    };

    setItems([...items, newItem]);
    setNewItemText('');
    setCurrentSpeaker(
      currentSpeaker === 'speaker-1' ? 'speaker-2' : 'speaker-1'
    );
  };

  const handleSave = () => {
    const script: Script = {
      dialogue: items,
    };

    if (filename) {
      saveScript(
        { script, filename },
        {
          onSuccess: () => {
            setSuccessMessage('Script saved successfully');
            if (onSave) {
              onSave(script);
            }
          },
        }
      );
    } else if (onSave) {
      onSave(script);
    }
  };

  const handleReorder = (newItems: DialogueItem[]) => {
    setItems(newItems);
  };

  const handleDelete = (index: number) => {
    const newItems = [...items];
    newItems.splice(index, 1);
    setItems(newItems);
  };

  const handleEdit = (index: number, updatedItem: DialogueItem) => {
    const newItems = [...items];
    newItems[index] = updatedItem;
    setItems(newItems);
  };

  if (isLoadingScript) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          {filename ? `Editing: ${filename}` : 'New Script'}
        </Typography>
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            alignItems: 'start',
            mb: 2,
          }}
        >
          <TextField
            fullWidth
            multiline
            label="New dialogue line"
            value={newItemText}
            onChange={(e) => setNewItemText(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleAddItem();
              }
            }}
          />
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddItem}
            disabled={!newItemText.trim()}
          >
            Add Line
          </Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={() =>
              setCurrentSpeaker(
                currentSpeaker === 'speaker-1' ? 'speaker-2' : 'speaker-1'
              )
            }
          >
            Current: {currentSpeaker === 'speaker-1' ? 'Speaker 1' : 'Speaker 2'}
          </Button>
        </Box>
      </Box>

      <ScriptList
        items={items}
        onReorder={handleReorder}
        onDelete={handleDelete}
        onEdit={handleEdit}
      />

      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          variant="contained"
          color="primary"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={isSaving || items.length === 0}
        >
          {isSaving ? 'Saving...' : 'Save Script'}
        </Button>
      </Box>

      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
      >
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Snackbar>

      <Snackbar
        open={!!successMessage}
        autoHideDuration={6000}
        onClose={() => setSuccessMessage(null)}
      >
        <Alert severity="success" onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ScriptEditor; 