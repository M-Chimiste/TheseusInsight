import React from 'react';
import {
  List,
  Paper,
  Typography,
  Box,
} from '@mui/material';
import {
  DragDropContext,
  Droppable,
  Draggable,
  DropResult,
} from 'react-beautiful-dnd';
import { DialogueItem } from '../../types/api';
import ScriptListItem from './ScriptListItem';

interface ScriptListProps {
  items: DialogueItem[];
  onReorder: (items: DialogueItem[]) => void;
  onDelete: (index: number) => void;
  onEdit: (index: number, item: DialogueItem) => void;
}

const ScriptList: React.FC<ScriptListProps> = ({
  items,
  onReorder,
  onDelete,
  onEdit,
}) => {
  const handleDragEnd = (result: DropResult) => {
    if (!result.destination) return;

    const reorderedItems = Array.from(items);
    const [removed] = reorderedItems.splice(result.source.index, 1);
    reorderedItems.splice(result.destination.index, 0, removed);

    onReorder(reorderedItems);
  };

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <Box sx={{ mt: 2 }}>
        <Droppable droppableId="droppable-list">
          {(provided, snapshot) => (
            <List
              ref={provided.innerRef}
              {...provided.droppableProps}
              sx={{
                bgcolor: snapshot.isDraggingOver ? 'action.hover' : 'background.paper',
                minHeight: '200px',
                p: 2,
                borderRadius: 1,
              }}
            >
              {items.map((item, index) => (
                <Draggable
                  key={`${item.speaker}-${index}`}
                  draggableId={`draggable-${index}`}
                  index={index}
                >
                  {(provided, snapshot) => (
                    <Box
                      ref={provided.innerRef}
                      {...provided.draggableProps}
                      sx={{
                        mb: 1,
                        transform: snapshot.isDragging ? 'scale(1.02)' : 'none',
                        transition: 'transform 0.2s ease',
                      }}
                    >
                      <Paper
                        elevation={snapshot.isDragging ? 8 : 1}
                        sx={{
                          bgcolor: 'background.paper',
                          '&:hover': {
                            bgcolor: 'action.hover',
                          },
                        }}
                      >
                        <ScriptListItem
                          item={item}
                          dragHandleProps={provided.dragHandleProps}
                          onEdit={(updatedItem) => onEdit(index, updatedItem)}
                          onDelete={() => onDelete(index)}
                        />
                      </Paper>
                    </Box>
                  )}
                </Draggable>
              ))}
              {provided.placeholder}
              {items.length === 0 && (
                <Typography
                  variant="body1"
                  color="textSecondary"
                  align="center"
                  sx={{ py: 4 }}
                >
                  No dialogue items yet. Add some or load a script.
                </Typography>
              )}
            </List>
          )}
        </Droppable>
      </Box>
    </DragDropContext>
  );
};

export default ScriptList; 