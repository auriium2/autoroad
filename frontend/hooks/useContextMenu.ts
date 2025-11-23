import * as React from 'react';
import type { Node } from 'reactflow';

interface ContextMenuState {
  nodeUuid: string;
  x: number;
  y: number;
}

interface UseContextMenuProps {
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  isOptimizing: boolean;
}

export function useContextMenu({ setNodes, isOptimizing }: UseContextMenuProps) {
  const [contextMenu, setContextMenu] = React.useState<ContextMenuState | null>(null);

  // Handle right-click on node
  const onNodeContextMenu = React.useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault();

    // Don't show context menu during optimization
    if (isOptimizing) {
      return;
    }

    setContextMenu({
      nodeUuid: node.id,
      x: event.clientX,
      y: event.clientY,
    });
  }, [isOptimizing]);

  // Close context menu on click outside and manage tooltip states
  React.useEffect(() => {
    if (!contextMenu) return;

    const handleClick = () => setContextMenu(null);
    window.addEventListener('click', handleClick);

    // Disable tooltip for the context menu node
    setNodes((currentNodes) =>
      currentNodes.map((node) =>
        node.id === contextMenu.nodeUuid
          ? { ...node, data: { ...node.data, disableTooltip: true } }
          : node.data.disableTooltip
          ? { ...node, data: { ...node.data, disableTooltip: false } }
          : node
      )
    );

    return () => {
      window.removeEventListener('click', handleClick);
      
      // Clear all disableTooltip flags when context menu closes
      setNodes((currentNodes) =>
        currentNodes.map((node) =>
          node.data.disableTooltip
            ? { ...node, data: { ...node.data, disableTooltip: false } }
            : node
        )
      );
    };
  }, [contextMenu, setNodes]);

  return {
    contextMenu,
    setContextMenu,
    onNodeContextMenu,
  };
}
