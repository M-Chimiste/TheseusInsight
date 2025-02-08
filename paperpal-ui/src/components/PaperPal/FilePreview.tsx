import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
} from '@mui/material';
import { JsonView, darkStyles } from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';

interface FilePreviewProps {
  file: File | null;
  isOpen: boolean;
  onClose: () => void;
  type: 'json' | 'text';
}

const FilePreview: React.FC<FilePreviewProps> = ({
  file,
  isOpen,
  onClose,
  type,
}) => {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (file && isOpen) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const content = e.target?.result as string;
          if (type === 'json') {
            // Validate JSON
            JSON.parse(content);
          }
          setContent(content);
          setError(null);
        } catch (err) {
          setError(`Invalid ${type.toUpperCase()} format`);
          setContent(null);
        }
      };
      reader.onerror = () => {
        setError('Failed to read file');
        setContent(null);
      };
      reader.readAsText(file);
    }
  }, [file, isOpen, type]);

  return (
    <Dialog open={isOpen} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        File Preview: {file?.name}
      </DialogTitle>
      <DialogContent>
        {error ? (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        ) : content ? (
          <Box sx={{ mt: 2, maxHeight: '60vh', overflow: 'auto' }}>
            {type === 'json' ? (
              <JsonView 
                data={JSON.parse(content)} 
                style={darkStyles}
              />
            ) : (
              <Typography
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontFamily: 'monospace',
                }}
              >
                {content}
              </Typography>
            )}
          </Box>
        ) : (
          <Typography>Loading...</Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default FilePreview; 