import React, { useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';

interface AudioUploadProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
}

const AudioUpload: React.FC<AudioUploadProps> = ({ file, onFileChange }) => {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFileChange(acceptedFiles[0]);
      }
    },
    [onFileChange]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/wav': ['.wav'],
      'audio/mp3': ['.mp3'],
      'audio/ogg': ['.ogg'],
      'audio/flac': ['.flac'],
    },
    multiple: false,
  });

  const handleRemoveFile = () => {
    onFileChange(null);
  };

  return (
    <Box>
      <Paper
        {...getRootProps()}
        sx={{
          p: 3,
          mb: 3,
          border: '2px dashed',
          borderColor: isDragActive ? 'primary.main' : 'divider',
          bgcolor: isDragActive ? 'action.hover' : 'background.paper',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          '&:hover': {
            borderColor: 'primary.main',
            bgcolor: 'action.hover',
          },
        }}
      >
        <input {...getInputProps()} />
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <CloudUploadIcon sx={{ fontSize: 48, color: 'primary.main' }} />
          <Typography variant="h6" align="center">
            {isDragActive
              ? 'Drop your audio file here'
              : 'Drag and drop an audio file here, or click to select a file'}
          </Typography>
          <Typography variant="body2" color="textSecondary" align="center">
            Supported formats: WAV, MP3, OGG, FLAC
          </Typography>
        </Box>
      </Paper>

      {file && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Selected File
          </Typography>
          <List>
            <ListItem>
              <ListItemText
                primary={file.name}
                secondary={`${(file.size / 1024 / 1024).toFixed(2)} MB`}
              />
              <ListItemSecondaryAction>
                <IconButton
                  edge="end"
                  onClick={handleRemoveFile}
                  size="small"
                >
                  <DeleteIcon />
                </IconButton>
              </ListItemSecondaryAction>
            </ListItem>
          </List>
        </Box>
      )}
    </Box>
  );
};

export default AudioUpload; 