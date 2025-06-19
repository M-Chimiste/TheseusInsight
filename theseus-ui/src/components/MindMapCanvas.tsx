import React, { useCallback, useMemo, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  ConnectionMode,
  BackgroundVariant,
} from '@xyflow/react';
import type {
  Connection,
  Edge,
  Node,
  NodeTypes,
  EdgeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Box, Paper, useTheme } from '@mui/material';
import type { MindMapData } from '../services/api';
import MindMapNode from './MindMapNode';
import MindMapEdge from './MindMapEdge';
import {
  forceSimulation,
  forceLink,
  forceCollide,
} from 'd3-force';

// Helper to determine the best handles for an edge to connect to
const getOptimalHandles = (sourceNode: Node, targetNode: Node): { sourceHandle: string; targetHandle: string } => {
  const dx = targetNode.position.x - sourceNode.position.x;
  const dy = targetNode.position.y - sourceNode.position.y;

  // Horizontal connection is best
  if (Math.abs(dx) > Math.abs(dy)) {
    return dx > 0
      ? { sourceHandle: 'right', targetHandle: 'left' }   // Right to Left
      : { sourceHandle: 'left', targetHandle: 'right' };  // Left to Right
  }
  
  // Vertical connection is best
  return dy > 0
    ? { sourceHandle: 'bottom', targetHandle: 'top' }    // Bottom to Top
    : { sourceHandle: 'top', targetHandle: 'bottom' };   // Top to Bottom
};

// Helper to generate concentric ring positions grouped by similarity bands
const generateConcentricPositions = (
  nodes: any[],
  seedPaperId: number | string,
  {
    baseRadius = 600,   // much wider initial ring
    ringGap = 500,      // greater gap between rings
    nodeSpacing = 360,  // larger arc length per node
  } = {}
): Map<string, { x: number; y: number }> => {
  const seedId = Number(seedPaperId);
  const seedNode = nodes.find((n) => n.id === seedId);

  // Four similarity bands (>=0.8, 0.6-0.8, 0.4-0.6, <0.4)
  const bands: { min: number; nodes: any[] }[] = [
    { min: 0.8, nodes: [] },
    { min: 0.6, nodes: [] },
    { min: 0.4, nodes: [] },
    { min: 0.0, nodes: [] },
  ];

  nodes.forEach((n) => {
    if (n.id === seedId) return; // skip seed
    const s = n.similarity_score ?? 0;
    const band = bands.find((b) => s >= b.min);
    band?.nodes.push(n);
  });

  const positions = new Map<string, { x: number; y: number }>();
  // seed at origin
  if (seedNode) positions.set(String(seedNode.id), { x: 0, y: 0 });

  bands.forEach((band, tierIdx) => {
    const n = band.nodes.length;
    if (n === 0) return;
    // Compute radius large enough for spacing
    const minRadius = baseRadius + tierIdx * ringGap;
    const requiredRadius = (n * nodeSpacing) / (2 * Math.PI);
    const radius = Math.max(minRadius, requiredRadius);

    const angleStep = (2 * Math.PI) / n;
    const startAngle = (tierIdx % 2 === 0 ? 0 : angleStep / 2);
    const snap = Math.PI / 12; // 15° snapping

    band.nodes.forEach((node, i) => {
      const rawAngle = startAngle + i * angleStep;
      const angle = Math.round(rawAngle / snap) * snap;
      positions.set(String(node.id), {
        x: radius * Math.cos(angle),
        y: radius * Math.sin(angle),
      });
    });
  });

  return positions;
};

interface MindMapCanvasProps {
  data: MindMapData;
  onNodeClick?: (nodeId: string) => void;
  onNodeExpand?: (nodeId: string) => void;
  onNodeDoubleClick?: (nodeId: string) => void;
  onPaneClick?: () => void;
  isLoading?: boolean;
}

// Define custom node and edge types
const nodeTypes: NodeTypes = {
  mindMapNode: MindMapNode,
};

const edgeTypes: EdgeTypes = {
  mindMapEdge: MindMapEdge,
};

const MindMapCanvas: React.FC<MindMapCanvasProps> = ({
  data,
  onNodeClick,
  onNodeExpand,
  onNodeDoubleClick,
  onPaneClick,
  isLoading = false,
}) => {
  const theme = useTheme();

  // Convert mind-map data to React Flow format with better initial positioning
  const initialNodes = useMemo(() => {
    if (!data.nodes || data.nodes.length === 0) {
      return [];
    }

    // Generate initial positions using concentric similarity bands
    const posMap = generateConcentricPositions(data.nodes, data.seed_paper_id);
    
    const convertedNodes = data.nodes.map((node): Node => {
      const pos = posMap.get(String(node.id)) ?? { x: 0, y: 0 };
      
      return {
        id: String(node.id),
        type: 'mindMapNode',
        position: pos,
        data: {
          ...node,
          isSelected: false,
        },
        draggable: true,
        selectable: true,
      };
    });
    
    return convertedNodes;
  }, [data.nodes, data.seed_paper_id]);

  const initialEdges = useMemo(() => {
    if (!data.edges || data.edges.length === 0 || !initialNodes || initialNodes.length === 0) {
      return [];
    }

    const nodeMap = new Map(initialNodes.map(node => [node.id, node]));

    return data.edges.map((edge): Edge => {
      const sourceId = String(edge.source_id);
      const targetId = String(edge.target_id);
      const sourceNode = nodeMap.get(sourceId);
      const targetNode = nodeMap.get(targetId);

      let handles = { sourceHandle: 'bottom', targetHandle: 'top' }; // Default
      if (sourceNode && targetNode) {
        handles = getOptimalHandles(sourceNode, targetNode);
      }
      
      return {
        id: `${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        type: 'mindMapEdge',
        data: {
          similarity_score: edge.similarity_score,
        },
        animated: false,
        style: {
          stroke: theme.palette.mode === 'dark' ? '#666' : '#b1b1b7',
          strokeWidth: Math.max(1, edge.similarity_score * 3),
        },
      };
    });
  }, [data.edges, initialNodes, theme.palette.mode]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Apply force-directed layout when data changes
  useEffect(() => {
    if (!initialNodes || initialNodes.length <= 1) {
      return;
    }

    // Create simulation nodes with initial positions
    const simulationNodes = initialNodes.map(node => ({
      id: node.id,
      x: node.position.x,
      y: node.position.y,
      // Store reference to original node
      node: node,
    }));

    // Create simulation links with increased distances
    const simulationLinks = initialEdges.map(edge => ({
      source: edge.source,
      target: edge.target,
      distance: 400, // Increased distance between connected nodes
      strength: edge.data?.similarity_score || 0.5,
    }));

    // Use minimal simulation since we have a structured initial layout
    const simulation = forceSimulation(simulationNodes)
      .force('link', forceLink(simulationLinks)
        .id((d: any) => d.id)
        .distance((d: any) => d.distance)
        .strength((d: any) => d.strength * 0.1) // Very low strength to maintain structure
      )
      .force('collision', forceCollide()
        .radius(220) // Prevent overlapping
        .strength(0.7)
        .iterations(2)
      )
      .alphaDecay(0.05) // Faster cooling since we start with good positions
      .velocityDecay(0.6); // Higher friction for stability

    // Run fewer iterations since we start with a good layout
    simulation.stop();
    for (let i = 0; i < 100; i++) {
      simulation.tick();
    }

    // Update node positions based on simulation results
    const updatedNodes = simulation.nodes().map((sNode: any) => ({
      ...sNode.node,
      position: { 
        x: Math.round(sNode.x), 
        y: Math.round(sNode.y) 
      },
    }));

    // Update handles for edges based on new positions
    const nodeMap = new Map(updatedNodes.map(node => [node.id, node]));
    const updatedEdges = initialEdges.map(edge => {
      const sourceNode = nodeMap.get(edge.source);
      const targetNode = nodeMap.get(edge.target);
      
      if (sourceNode && targetNode) {
        const handles = getOptimalHandles(sourceNode, targetNode);
        return {
          ...edge,
          sourceHandle: handles.sourceHandle,
          targetHandle: handles.targetHandle,
        };
      }
      
      return edge;
    });

    setNodes(updatedNodes);
    setEdges(updatedEdges);
    
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Handle connections (if users manually connect nodes)
  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Handle node selection
  const handleNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.stopPropagation();
      
      // Update node selection state
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: {
            ...n.data,
            isSelected: n.id === node.id,
          },
        }))
      );

      onNodeClick?.(node.id);
    },
    [onNodeClick, setNodes]
  );

  // Handle node double-click for expansion
  const handleNodeDoubleClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.stopPropagation();
      onNodeDoubleClick?.(node.id);
    },
    [onNodeDoubleClick]
  );

  // Handle pane click to clear selection
  const handlePaneClick = useCallback(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          isSelected: false,
        },
      }))
    );
    onPaneClick?.();
  }, [onPaneClick, setNodes]);

  // Handle node expansion from context menu
  const handleNodeExpand = useCallback(
    (nodeId: string) => {
      onNodeExpand?.(nodeId);
    },
    [onNodeExpand]
  );

  // Update nodes with expand handler
  const nodesWithHandlers = useMemo(() => {
    return nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        onExpand: () => handleNodeExpand(node.id),
      },
    }));
  }, [nodes, handleNodeExpand]);

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        position: 'relative',
        '& .react-flow': {
          backgroundColor: theme.palette.background.default,
        },
        '& .react-flow__background': {
          backgroundColor: theme.palette.background.default,
        },
        '& .react-flow__controls': {
          backgroundColor: theme.palette.background.paper,
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: theme.shape.borderRadius,
        },
        '& .react-flow__controls button': {
          backgroundColor: 'transparent',
          color: theme.palette.text.primary,
          border: 'none',
          '&:hover': {
            backgroundColor: theme.palette.action.hover,
          },
        },
        '& .react-flow__minimap': {
          backgroundColor: theme.palette.background.paper,
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: theme.shape.borderRadius,
        },
        '& .react-flow__attribution': {
          backgroundColor: theme.palette.background.paper,
          color: theme.palette.text.secondary,
          fontSize: '10px',
          padding: '2px 4px',
          borderRadius: theme.shape.borderRadius,
        },
      }}
    >
      <ReactFlow
        nodes={nodesWithHandlers}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={handleNodeClick}
        onNodeDoubleClick={handleNodeDoubleClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView={true}
        fitViewOptions={{
          padding: 0.3,
          includeHiddenNodes: false,
          minZoom: 0.15,
          maxZoom: 1.5,
        }}
        defaultViewport={{ x: 0, y: 0, zoom: 0.4 }}
        minZoom={0.1}
        maxZoom={2}
        deleteKeyCode={null} // Disable delete key
        multiSelectionKeyCode={null} // Disable multi-selection
        panOnScroll
        selectionOnDrag={false}
        snapToGrid={false}
        snapGrid={[15, 15]}
        connectionMode={ConnectionMode.Loose}
        style={{
          backgroundColor: theme.palette.background.default,
        }}
      >
        <Background
          color={theme.palette.mode === 'dark' ? '#333' : '#aaa'}
          gap={20}
          size={1}
          variant={BackgroundVariant.Dots}
        />
        <Controls
          position="top-left"
          showZoom={true}
          showFitView={true}
          showInteractive={false}
        />
        <MiniMap
          position="bottom-right"
          nodeStrokeColor={theme.palette.primary.main}
          nodeColor={theme.palette.background.paper}
          nodeBorderRadius={8}
          maskColor={theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,255,0.6)'}
          style={{
            height: 120,
            width: 200,
          }}
        />
      </ReactFlow>

      {/* Loading overlay */}
      {isLoading && (
        <Paper
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            p: 3,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
            zIndex: 1000,
            backgroundColor: theme.palette.background.paper,
            borderRadius: 2,
            boxShadow: theme.shadows[8],
          }}
        >
          {/* Loading content will be handled by parent component */}
        </Paper>
      )}
    </Box>
  );
};

export default MindMapCanvas; 