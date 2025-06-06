import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  IconButton,
  Paper,
  Chip,
} from '@mui/material';
import {
  Close as CloseIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { type LiteratureReviewResult } from '../hooks/useResearchAgent';

interface ReportViewerProps {
  open: boolean;
  onClose: () => void;
  review: LiteratureReviewResult | null;
}

const ReportViewer: React.FC<ReportViewerProps> = ({ open, onClose, review }) => {
  if (!review) return null;

  const handleDownload = () => {
    if (!review.report_text) return;
    
    const blob = new Blob([review.report_text], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `literature-review-${review.id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      slotProps={{
        paper: {
          sx: { height: '90vh', display: 'flex', flexDirection: 'column' }
        }
      }}
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, pr: 2 }}>
            Literature Review Report
          </Typography>
          <IconButton
            edge="end"
            color="inherit"
            onClick={onClose}
            aria-label="close"
          >
            <CloseIcon />
          </IconButton>
        </Box>
        <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Chip 
            label={`${review.total_papers} papers`} 
            size="small" 
            color="primary"
          />
          <Chip 
            label={formatTimestamp(review.created_ts)} 
            size="small" 
            variant="outlined"
          />
          <Chip 
            label={`Review #${review.id}`} 
            size="small" 
            variant="outlined"
          />
        </Box>
      </DialogTitle>
      
      <DialogContent sx={{ flexGrow: 1, overflow: 'hidden', p: 0 }}>
        <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
          {/* Research Question */}
          <Paper sx={{ p: 2, mb: 3, backgroundColor: 'grey.50' }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Research Question
            </Typography>
            <Typography variant="body1">
              {review.research_question}
            </Typography>
          </Paper>

          {/* Report Content */}
          {review.report_text ? (
            <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
                             <ReactMarkdown
                 components={{
                   h1: ({ children }: any) => (
                     <Typography variant="h4" gutterBottom sx={{ mt: 2, mb: 2 }}>
                       {children}
                     </Typography>
                   ),
                   h2: ({ children }: any) => (
                     <Typography variant="h5" gutterBottom sx={{ mt: 3, mb: 2 }}>
                       {children}
                     </Typography>
                   ),
                   h3: ({ children }: any) => (
                     <Typography variant="h6" gutterBottom sx={{ mt: 2, mb: 1 }}>
                       {children}
                     </Typography>
                   ),
                   p: ({ children }: any) => (
                     <Typography variant="body1" paragraph>
                       {children}
                     </Typography>
                   ),
                   ul: ({ children }: any) => (
                     <Box component="ul" sx={{ pl: 3, mb: 2 }}>
                       {children}
                     </Box>
                   ),
                   ol: ({ children }: any) => (
                     <Box component="ol" sx={{ pl: 3, mb: 2 }}>
                       {children}
                     </Box>
                   ),
                   li: ({ children }: any) => (
                     <Typography component="li" variant="body1" sx={{ mb: 0.5 }}>
                       {children}
                     </Typography>
                   ),
                   table: ({ children }: any) => (
                     <Box sx={{ overflowX: 'auto', mb: 2 }}>
                       <Box component="table" sx={{ 
                         width: '100%', 
                         borderCollapse: 'collapse',
                         '& th, & td': {
                           border: '1px solid',
                           borderColor: 'divider',
                           p: 1,
                           textAlign: 'left'
                         },
                         '& th': {
                           backgroundColor: 'grey.100',
                           fontWeight: 'bold'
                         }
                       }}>
                         {children}
                       </Box>
                     </Box>
                   ),
                   blockquote: ({ children }: any) => (
                     <Box sx={{ 
                       borderLeft: '4px solid',
                       borderColor: 'primary.main',
                       pl: 2,
                       py: 1,
                       mb: 2,
                       backgroundColor: 'grey.50',
                       fontStyle: 'italic'
                     }}>
                       {children}
                     </Box>
                   ),
                   code: ({ children, inline }: any) => 
                     inline ? (
                       <Box component="code" sx={{ 
                         backgroundColor: 'grey.100',
                         px: 0.5,
                         borderRadius: 0.5,
                         fontFamily: 'monospace',
                         fontSize: '0.875em'
                       }}>
                         {children}
                       </Box>
                     ) : (
                       <Paper sx={{ p: 2, mb: 2, backgroundColor: 'grey.100' }}>
                         <Box component="pre" sx={{ 
                           fontFamily: 'monospace',
                           fontSize: '0.875em',
                           overflow: 'auto',
                           m: 0
                         }}>
                           <code>{children}</code>
                         </Box>
                       </Paper>
                     )
                 }}
               >
                {review.report_text}
              </ReactMarkdown>
            </Paper>
          ) : (
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="body1" color="text.secondary">
                No detailed report available for this review.
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                The review contains {review.summaries.length} paper summaries.
              </Typography>
            </Paper>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose}>
          Close
        </Button>
        {review.report_text && (
          <Button
            variant="contained"
            startIcon={<DownloadIcon />}
            onClick={handleDownload}
          >
            Download Report
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ReportViewer; 