import React, { useCallback, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Divider,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';

interface FileUploadProps {
  files: File[];
  urls: string[];
  onFilesChange: (files: File[]) => void;
  onUrlsChange: (urls: string[]) => void;
}

const FileUpload: React.FC<FileUploadProps> = ({
  files,
  urls,
  onFilesChange,
  onUrlsChange,
}) => {
  const [newUrl, setNewUrl] = useState('');

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const pdfFiles = acceptedFiles.filter(
        (file) => file.type === 'application/pdf'
      );
      onFilesChange([...files, ...pdfFiles]);
    },
    [files, onFilesChange]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  });

  const handleAddUrl = () => {
    if (newUrl.trim() && isValidUrl(newUrl)) {
      onUrlsChange([...urls, newUrl.trim()]);
      setNewUrl('');
    }
  };

  const handleRemoveFile = (index: number) => {
    const newFiles = [...files];
    newFiles.splice(index, 1);
    onFilesChange(newFiles);
  };

  const handleRemoveUrl = (index: number) => {
    const newUrls = [...urls];
    newUrls.splice(index, 1);
    onUrlsChange(newUrls);
  };

  const isValidUrl = (url: string) => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
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
              ? 'Drop your PDF files here'
              : 'Drag and drop PDF files here, or click to select files'}
          </Typography>
          <Typography variant="body2" color="textSecondary" align="center">
            Only PDF files are accepted
          </Typography>
        </Box>
      </Paper>

      {files.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Selected Files
          </Typography>
          <List>
            {files.map((file, index) => (
              <ListItem key={`${file.name}-${index}`}>
                <ListItemText
                  primary={file.name}
                  secondary={`${(file.size / 1024 / 1024).toFixed(2)} MB`}
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    onClick={() => handleRemoveFile(index)}
                    size="small"
                  >
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </Box>
      )}

      <Divider sx={{ my: 3 }} />

      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Add PDF URLs
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <TextField
            fullWidth
            size="small"
            label="PDF URL"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            error={newUrl.trim() !== '' && !isValidUrl(newUrl)}
            helperText={
              newUrl.trim() !== '' && !isValidUrl(newUrl)
                ? 'Please enter a valid URL'
                : ''
            }
            onKeyPress={(e) => {
              if (e.key === 'Enter' && isValidUrl(newUrl)) {
                e.preventDefault();
                handleAddUrl();
              }
            }}
          />
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddUrl}
            disabled={!isValidUrl(newUrl)}
          >
            Add URL
          </Button>
        </Box>

        {urls.length > 0 && (
          <List>
            {urls.map((url, index) => (
              <ListItem key={`${url}-${index}`}>
                <ListItemText primary={url} />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    onClick={() => handleRemoveUrl(index)}
                    size="small"
                  >
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        )}
      </Box>
    </Box>
  );
};

export default FileUpload; 