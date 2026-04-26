import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Tooltip } from '@mui/material';
import {
  Home,
  Sparkles,
  BookOpen,
  Library,
  Network,
  LineChart,
  Star,
  Mail,
  Mic,
  Briefcase,
  Settings,
  Search,
  Database,
  Users,
  History,
  ListMusic,
  Film,
  Activity,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { OBS, withAlpha } from '../../styles/observatoryTokens';
import { useDesign } from '../../contexts/DesignContext';

interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const GROUPS: NavGroup[] = [
  {
    label: 'Research',
    items: [
      { label: 'Dashboard',         path: '/',                  icon: Home },
      { label: 'Research Agent',    path: '/research-agent',    icon: Sparkles },
      { label: 'Papers',            path: '/papers',            icon: BookOpen },
      { label: 'Research Library',  path: '/research-library',  icon: Library },
    ],
  },
  {
    label: 'Analysis',
    items: [
      { label: 'Mind-Map Reports',  path: '/mindmap-reports',   icon: Network },
      { label: 'Research Timeline', path: '/timeline',          icon: LineChart },
      { label: 'Star Map',          path: '/star-map',          icon: Star },
    ],
  },
  {
    label: 'Output',
    items: [
      { label: 'Newsletter',        path: '/newsletter',        icon: Mail },
      { label: 'Podcast',           path: '/podcast',           icon: Mic },
      { label: 'Podcast History',   path: '/podcast-history',   icon: ListMusic },
      { label: 'Visualizer',        path: '/visualizer',        icon: Film },
    ],
  },
  {
    label: 'System',
    items: [
      { label: 'Bulk Operations',   path: '/bulk-operations',   icon: Briefcase },
      { label: 'Job Monitoring',    path: '/job-monitoring',    icon: Activity },
      { label: 'Profile Management', path: '/profile-management', icon: Users },
      { label: 'Model Catalog',     path: '/model-catalog',     icon: Database },
      { label: 'Run History',       path: '/run-history',       icon: History },
      { label: 'Settings',          path: '/settings',          icon: Settings },
    ],
  },
];

interface ObsSidebarProps {
  width: number;
  collapsed: boolean;
  onToggle: () => void;
}

const ObsSidebar: React.FC<ObsSidebarProps> = ({ width, collapsed, onToggle }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { accent } = useDesign();
  const { density } = useDesign();
  // density was already destructured above; keep it for itemH calc
  const itemH = density === 'dense' ? 28 : density === 'spacious' ? 36 : 32;

  return (
    <aside
      style={{
        width,
        height: '100vh',
        position: 'fixed',
        top: 0,
        left: 0,
        background: OBS.bg,
        borderRight: `1px solid ${OBS.border}`,
        padding: collapsed ? '14px 8px' : '14px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        fontFamily: OBS.sans,
        color: OBS.text,
        flexShrink: 0,
        transition: 'width 0.25s ease, padding 0.25s ease',
        zIndex: 1200,
        overflow: 'hidden',
      }}
    >
      {/* Brand */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: collapsed ? '0 4px 6px' : '0 6px 6px',
          minHeight: 28,
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: 6,
            background: `radial-gradient(circle at 30% 30%, ${accent}, #2E6B82 70%)`,
            boxShadow: `0 0 12px ${withAlpha(accent, 0.4)}`,
            flexShrink: 0,
          }}
        />
        {!collapsed && (
          <>
            <div style={{ fontFamily: OBS.serif, fontSize: 17, letterSpacing: '-0.01em' }}>
              Theseus
            </div>
            <div
              style={{
                fontFamily: OBS.mono,
                fontSize: 9,
                color: OBS.textDim,
                marginLeft: 'auto',
                padding: '2px 5px',
                border: `1px solid ${OBS.border}`,
                borderRadius: 3,
              }}
            >
              v2.1
            </div>
          </>
        )}
      </div>

      {/* Search */}
      {!collapsed && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 8px',
            background: OBS.surface,
            borderRadius: 6,
            fontSize: 11,
            color: OBS.textMuted,
            border: `1px solid ${OBS.border}`,
          }}
        >
          <Search size={12} color={OBS.textDim} strokeWidth={1.6} />
          <span style={{ flex: 1 }}>Search…</span>
          <span
            style={{
              fontFamily: OBS.mono,
              fontSize: 9,
              color: OBS.textDim,
              padding: '1px 4px',
              border: `1px solid ${OBS.border}`,
              borderRadius: 3,
            }}
          >
            ⌘K
          </span>
        </div>
      )}

      {/* Groups */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0 }}>
        {GROUPS.map((g) => (
          <div key={g.label} style={{ marginBottom: 14 }}>
            {!collapsed && (
              <div
                style={{
                  fontFamily: OBS.mono,
                  fontSize: 9,
                  letterSpacing: '0.1em',
                  color: OBS.textDim,
                  textTransform: 'uppercase',
                  padding: '0 8px 6px',
                }}
              >
                {g.label}
              </div>
            )}
            {g.items.map((it) => {
              const isActive =
                it.path === '/'
                  ? location.pathname === '/'
                  : location.pathname === it.path || location.pathname.startsWith(`${it.path}/`);
              const IconCmp = it.icon;
              const row = (
                <div
                  key={it.label}
                  onClick={() => navigate(it.path)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: collapsed ? 0 : 9,
                    height: itemH,
                    padding: collapsed ? '0 12px' : '0 8px',
                    margin: collapsed ? '2px 0' : '1px 0',
                    borderRadius: 5,
                    fontSize: 12,
                    color: isActive ? OBS.text : OBS.textMuted,
                    background: isActive ? OBS.surface : 'transparent',
                    position: 'relative',
                    cursor: 'pointer',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    transition: 'background 0.12s ease, color 0.12s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      (e.currentTarget as HTMLDivElement).style.color = OBS.text;
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      (e.currentTarget as HTMLDivElement).style.color = OBS.textMuted;
                    }
                  }}
                >
                  {isActive && (
                    <div
                      style={{
                        position: 'absolute',
                        left: collapsed ? 4 : -12,
                        top: 6,
                        bottom: 6,
                        width: 2,
                        background: accent,
                        borderRadius: 2,
                        boxShadow: `0 0 6px ${accent}`,
                      }}
                    />
                  )}
                  <IconCmp
                    size={14}
                    color={isActive ? accent : OBS.textDim}
                    strokeWidth={1.6}
                  />
                  {!collapsed && (
                    <span
                      style={{
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {it.label}
                    </span>
                  )}
                </div>
              );
              return collapsed ? (
                <Tooltip key={it.label} title={it.label} placement="right" arrow>
                  {row}
                </Tooltip>
              ) : (
                row
              );
            })}
          </div>
        ))}
      </div>

      {/* Footer / collapse */}
      <div
        style={{
          marginTop: 'auto',
          paddingTop: 10,
          borderTop: `1px solid ${OBS.border}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          gap: 8,
        }}
      >
        {!collapsed && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              minWidth: 0,
              flex: 1,
            }}
          >
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: 13,
                background: '#1E2B4A',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: OBS.mono,
                fontSize: 10,
                color: accent,
                flexShrink: 0,
              }}
            >
              TI
            </div>
            <div style={{ fontSize: 11, color: OBS.textMuted, lineHeight: 1.2, minWidth: 0 }}>
              <div
                style={{
                  color: OBS.text,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                Researcher
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: OBS.textDim,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                Local instance
              </div>
            </div>
          </div>
        )}
        <Tooltip
          title={collapsed ? 'Expand' : 'Collapse'}
          placement={collapsed ? 'right' : 'top'}
          arrow
        >
          <div
            onClick={onToggle}
            style={{
              width: 24,
              height: 24,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 4,
              cursor: 'pointer',
              color: OBS.textDim,
            }}
          >
            {collapsed ? (
              <ChevronRight size={14} strokeWidth={1.6} />
            ) : (
              <ChevronLeft size={14} strokeWidth={1.6} />
            )}
          </div>
        </Tooltip>
      </div>
    </aside>
  );
};

export default ObsSidebar;
