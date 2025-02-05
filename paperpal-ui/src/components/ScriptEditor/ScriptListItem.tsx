import React, { useState } from 'react';
import {
  ListItem,
  IconButton,
  TextField,
  Box,
  Select,
  MenuItem,
} from '@mui/material';
import {
  DragHandle as DragHandleIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import { DialogueItem } from '../../types/api';

interface ScriptListItemProps {
  item: DialogueItem;
  dragHandleProps: any;
  onEdit: (item: DialogueItem) => void;
  onDelete: () => void;
}

const ScriptListItem: React.FC<ScriptListItemProps> = ({
  item,
  dragHandleProps,
  onEdit,
  onDelete,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(item.text);
  const [editedSpeaker, setEditedSpeaker] = useState(item.speaker);

  const handleSave = () => {
    onEdit({
      speaker: editedSpeaker,
      text: editedText,
    });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditedText(item.text);
    setEditedSpeaker(item.speaker);
    setIsEditing(false);
  };

  return (
    <ListItem
      sx={{
        bgcolor: 'background.default',
        borderRadius: 1,
        mb: 1,
        '&:hover': {
          bgcolor: 'action.hover',
        },
      }}
    >
      <Box {...dragHandleProps} sx={{ mr: 1, cursor: 'grab' }}>
        <DragHandleIcon />
      </Box>

      {isEditing ? (
        <Box sx={{ display: 'flex', flexGrow: 1, gap: 2, alignItems: 'start' }}>
          <Select
            value={editedSpeaker}
            onChange={(e) => setEditedSpeaker(e.target.value)}
            size="small"
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="speaker-1">Speaker 1</MenuItem>
            <MenuItem value="speaker-2">Speaker 2</MenuItem>
          </Select>
          <TextField
            fullWidth
            multiline
            size="small"
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            sx={{ flexGrow: 1 }}
          />
          <IconButton onClick={handleSave} color="primary" size="small">
            <SaveIcon />
          </IconButton>
          <IconButton onClick={handleCancel} color="error" size="small">
            <CancelIcon />
          </IconButton>
        </Box>
      ) : (
        <>
          <Box sx={{ flexGrow: 1 }}>
            <Box
              component="span"
              sx={{
                color: 'primary.main',
                fontWeight: 'bold',
                mr: 2,
              }}
            >
              {item.speaker === 'speaker-1' ? 'Speaker 1' : 'Speaker 2'}:
            </Box>
            {item.text}
          </Box>
          <IconButton onClick={() => setIsEditing(true)} size="small">
            <EditIcon />
          </IconButton>
          <IconButton onClick={onDelete} color="error" size="small">
            <DeleteIcon />
          </IconButton>
        </>
      )}
    </ListItem>
  );
};

export default ScriptListItem; 