import React from 'react';
import { Box, Typography, Card, CardContent } from '@mui/material';

const Podcast: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Podcast Creator
      </Typography>
      <Card>
        <CardContent>
          <Typography variant="body1">
            Podcast creator functionality coming soon...
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Podcast; 