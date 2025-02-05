import React, { useState, useRef, useEffect } from 'react';
import {
  Paper,
  TextField,
  IconButton,
  Box,
  Select,
  MenuItem,
  SelectChangeEvent,
} from '@mui/material';
import {
  DragHandle as DragHandleIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { Draggable } from 'react-beautiful-dnd';
import { DialogueItem as DialogueItemType } from '../../types/api';

interface Props {
  item: DialogueItemType;
  index: number;
  onUpdate: (index: number, item: DialogueItemType) => void;
  onDelete: (index: number) => void;
}

const DialogueItem: React.FC<Props> = ({ item, index, onUpdate, onDelete }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [text, setText] = useState(item.text);
  const textFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && textFieldRef.current) {
      textFieldRef.current.focus();
    }
  }, [isEditing]);

  const handleTextChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setText(event.target.value);
  };

  const handleTextBlur = () => {
    setIsEditing(false);
    if (text !== item.text) {
      onUpdate(index, { ...item, text });
    }
  };

  const handleSpeakerChange = (event: SelectChangeEvent<string>) => {
    onUpdate(index, { ...item, speaker: event.target.value });
  };

  return (
    <Draggable draggableId={`item-${index}`} index={index}>
      {(provided, snapshot) => (
        <Paper
          ref={provided.innerRef}
          {...provided.draggableProps}
          elevation={snapshot.isDragging ? 6 : 1}
          sx={{
            p: 2,
            mb: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            backgroundColor: snapshot.isDragging ? 'background.paper' : 'inherit',
            '&:hover': {
              '& .MuiIconButton-root': {
                opacity: 1,
              },
            },
          }}
        >
          <IconButton
            {...provided.dragHandleProps}
            size="small"
            sx={{ cursor: 'grab' }}
          >
            <DragHandleIcon />
          </IconButton>

          <Select
            value={item.speaker}
            onChange={handleSpeakerChange}
            size="small"
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="speaker-1">Speaker 1</MenuItem>
            <MenuItem value="speaker-2">Speaker 2</MenuItem>
          </Select>

          <Box sx={{ flex: 1 }}>
            {isEditing ? (
              <TextField
                fullWidth
                multiline
                value={text}
                onChange={handleTextChange}
                onBlur={handleTextBlur}
                inputRef={textFieldRef}
                variant="standard"
                autoFocus
              />
            ) : (
              <Box
                onClick={() => setIsEditing(true)}
                sx={{
                  p: 1,
                  minHeight: '1.5em',
                  cursor: 'text',
                  '&:hover': {
                    backgroundColor: 'action.hover',
                  },
                }}
              >
                {text}
              </Box>
            )}
          </Box>

          <IconButton
            onClick={() => onDelete(index)}
            size="small"
            sx={{
              opacity: 0,
              transition: 'opacity 0.2s',
              '&:hover': {
                color: 'error.main',
              },
            }}
          >
            <DeleteIcon />
          </IconButton>
        </Paper>
      )}
    </Draggable>
  );
};

export default DialogueItem; 