import React from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Tooltip,
  Typography,
} from '@mui/material';
import ObsCard from '../observatory/ObsCard';
import ObsKicker from '../observatory/ObsKicker';
import SettingsIcon from '@mui/icons-material/Settings';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import CloseIcon from '@mui/icons-material/Close';
import CheckIcon from '@mui/icons-material/Check';
import { useNavigate } from 'react-router-dom';
import { DndContext, PointerSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

import {
  DASHBOARD_SHORTCUTS,
  DEFAULT_PINNED_SHORTCUT_IDS,
  type DashboardShortcutDefinition,
  type DashboardShortcutId,
} from './shortcuts';

const STORAGE_KEY = 'theseus_dashboard_pinned_shortcuts_v1';

function loadPinnedIds(): DashboardShortcutId[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PINNED_SHORTCUT_IDS;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return DEFAULT_PINNED_SHORTCUT_IDS;
    return parsed.filter((v): v is DashboardShortcutId => typeof v === 'string') as DashboardShortcutId[];
  } catch {
    return DEFAULT_PINNED_SHORTCUT_IDS;
  }
}

function savePinnedIds(ids: DashboardShortcutId[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

function byIdMap(defs: DashboardShortcutDefinition[]) {
  const map = new Map<DashboardShortcutId, DashboardShortcutDefinition>();
  defs.forEach((d) => map.set(d.id, d));
  return map;
}

function SortablePinnedRowItem(props: {
  id: DashboardShortcutId;
  definition: DashboardShortcutDefinition;
  isPinned: boolean;
  onTogglePinned: (id: DashboardShortcutId) => void;
}) {
  const { id, definition, isPinned, onTogglePinned } = props;
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };

  return (
    <ListItem
      ref={setNodeRef}
      style={style}
      secondaryAction={
        <Tooltip title={isPinned ? 'Unpin' : 'Pin'}>
          <IconButton edge="end" onClick={() => onTogglePinned(id)} size="small">
            {isPinned ? <CheckIcon color="success" /> : <CheckIcon color="disabled" />}
          </IconButton>
        </Tooltip>
      }
      disableGutters
      sx={{
        px: 1,
        py: 0.5,
        borderRadius: 1,
        '&:hover': { bgcolor: 'action.hover' },
      }}
    >
      <ListItemIcon sx={{ minWidth: 36, color: 'text.secondary' }}>
        <span {...attributes} {...listeners} style={{ display: 'inline-flex', cursor: 'grab' }}>
          <DragIndicatorIcon fontSize="small" />
        </span>
      </ListItemIcon>
      <ListItemIcon sx={{ minWidth: 36 }}>{definition.icon}</ListItemIcon>
      <ListItemText
        primary={definition.label}
        secondary={definition.description}
        primaryTypographyProps={{ fontWeight: 600 }}
      />
    </ListItem>
  );
}

export function PinnedShortcuts() {
  const navigate = useNavigate();

  const defs = React.useMemo(() => DASHBOARD_SHORTCUTS, []);
  const defsById = React.useMemo(() => byIdMap(defs), [defs]);

  const [pinnedIds, setPinnedIds] = React.useState<DashboardShortcutId[]>(() => loadPinnedIds());
  const [manageOpen, setManageOpen] = React.useState(false);

  React.useEffect(() => {
    savePinnedIds(pinnedIds);
  }, [pinnedIds]);

  const pinnedDefs = pinnedIds
    .map((id) => defsById.get(id))
    .filter((d): d is DashboardShortcutDefinition => Boolean(d));

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const togglePinned = (id: DashboardShortcutId) => {
    setPinnedIds((prev) => {
      const isPinned = prev.includes(id);
      if (isPinned) return prev.filter((x) => x !== id);
      return [...prev, id];
    });
  };

  return (
    <ObsCard padding={18}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, mb: 1.5 }}>
          <Box>
            <ObsKicker>Shortcuts</ObsKicker>
            <Typography
              sx={{ fontFamily: '"Instrument Serif", Georgia, serif', fontSize: 22, lineHeight: 1.1, mt: 0.5 }}
            >
              Pinned
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Your shortcuts for quick navigation.
            </Typography>
          </Box>
          <Button
            variant="outlined"
            size="small"
            startIcon={<SettingsIcon />}
            onClick={() => setManageOpen(true)}
          >
            Manage
          </Button>
        </Box>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {pinnedDefs.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No pinned shortcuts yet. Use "Manage" to add a few.
            </Typography>
          ) : (
            pinnedDefs.map((d) => (
              <Chip
                key={d.id}
                icon={d.icon}
                label={d.label}
                onClick={() => navigate(d.path)}
                variant="outlined"
                clickable
                sx={{ py: 2 }}
              />
            ))
          )}
        </Box>

      <Dialog open={manageOpen} onClose={() => setManageOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
          Manage pinned shortcuts
          <IconButton onClick={() => setManageOpen(false)} size="small">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Drag to reorder. Toggle the checkmark to pin/unpin.
          </Typography>

          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={(event) => {
              const { active, over } = event;
              if (!over || active.id === over.id) return;
              setPinnedIds((prev) => {
                const oldIndex = prev.indexOf(active.id as DashboardShortcutId);
                const newIndex = prev.indexOf(over.id as DashboardShortcutId);
                if (oldIndex === -1 || newIndex === -1) return prev;
                return arrayMove(prev, oldIndex, newIndex);
              });
            }}
          >
            <SortableContext items={pinnedIds} strategy={verticalListSortingStrategy}>
              <List dense sx={{ mb: 2 }}>
                {pinnedIds.map((id) => {
                  const def = defsById.get(id);
                  if (!def) return null;
                  return (
                    <SortablePinnedRowItem
                      key={id}
                      id={id}
                      definition={def}
                      isPinned={true}
                      onTogglePinned={togglePinned}
                    />
                  );
                })}
              </List>
            </SortableContext>
          </DndContext>

          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Available shortcuts
          </Typography>
          <List dense>
            {defs
              .filter((d) => !pinnedIds.includes(d.id))
              .map((d) => (
                <ListItem
                  key={d.id}
                  secondaryAction={
                    <Tooltip title="Pin">
                      <IconButton edge="end" onClick={() => togglePinned(d.id)} size="small">
                        <CheckIcon color="disabled" />
                      </IconButton>
                    </Tooltip>
                  }
                  disableGutters
                  sx={{ px: 1, py: 0.5, borderRadius: 1, '&:hover': { bgcolor: 'action.hover' } }}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>{d.icon}</ListItemIcon>
                  <ListItemText
                    primary={d.label}
                    secondary={d.description}
                    primaryTypographyProps={{ fontWeight: 600 }}
                  />
                </ListItem>
              ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPinnedIds(DEFAULT_PINNED_SHORTCUT_IDS)} variant="text">
            Reset defaults
          </Button>
          <Button onClick={() => setManageOpen(false)} variant="contained">
            Done
          </Button>
        </DialogActions>
      </Dialog>
    </ObsCard>
  );
}

