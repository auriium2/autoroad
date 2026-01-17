import * as React from "react";
import { Pin, Ban, Trash2, Unlink } from "lucide-react";
import type { CourseNode } from "@/stores/roadStore";

interface ContextMenuState {
  nodeUuid: string;
  x: number;
  y: number;
}

interface NodeContextMenuProps {
  contextMenu: ContextMenuState | null;
  storeNodes: CourseNode[];
  onPin: (nodeId: string) => void;
  onOverride: (nodeId: string) => void;
  onBanish: (nodeId: string) => void;
  onRemove: (nodeId: string) => void;
  onConvertToMarker: (nodeId: string) => void;
}

export function NodeContextMenu({
  contextMenu,
  storeNodes,
  onPin,
  onOverride,
  onBanish,
  onRemove,
  onConvertToMarker,
}: NodeContextMenuProps) {
  if (!contextMenu) return null;

  const node = storeNodes.find(n => n.uuid === contextMenu.nodeUuid);
  if (!node) return null;

  const isUserControlled = node.userControlled;
  const currentStatus = node.nodeStatus || 'pin';
  const isInMustTake = node.section === -2;
  const isInASE = node.section === -1;

  return (
    <div
      className="fixed bg-popover/95 border border-border rounded-lg shadow-lg backdrop-blur-md p-1"
      style={{
        top: contextMenu.y,
        left: contextMenu.x,
        zIndex: 10000,
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {isUserControlled ? (
        <>
          <button
            className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => onPin(contextMenu.nodeUuid)}
            disabled={currentStatus === 'pin'}
          >
            <Pin className="w-3 h-3" />
            <span>Pin (default)</span>
            {currentStatus === 'pin' && (
              <span className="ml-auto text-[10px] text-muted-foreground">✓</span>
            )}
          </button>

          <button
            className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => onOverride(contextMenu.nodeUuid)}
            disabled={currentStatus === 'override' || isInMustTake}
            title={isInMustTake ? "Override not available in Must Take - move to a specific semester" : undefined}
          >
            <Unlink className="w-3 h-3" />
            <span>Pin + ignore prerequisites</span>
            {currentStatus === 'override' && (
              <span className="ml-auto text-[10px] text-muted-foreground">✓</span>
            )}
          </button>

          <button
            className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => onBanish(contextMenu.nodeUuid)}
            disabled={currentStatus === 'banish' || isInASE}
            title={isInASE ? "Banish not available in ASE" : undefined}
          >
            <Ban className="w-3 h-3" />
            <span>{isInMustTake ? "Banish (never take)" : "Banish"}</span>
            {currentStatus === 'banish' && (
              <span className="ml-auto text-[10px] text-muted-foreground">✓</span>
            )}
          </button>

          <div className="h-px bg-border/50 my-0.5" />

          <button
            className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-destructive/10 text-destructive transition-colors w-full text-left"
            onClick={() => onRemove(contextMenu.nodeUuid)}
          >
            <Trash2 className="w-3 h-3" />
            <span>Remove marker</span>
          </button>
        </>
      ) : (
        <button
          className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left"
          onClick={() => onConvertToMarker(contextMenu.nodeUuid)}
        >
          <Pin className="w-3 h-3" />
          <span>Convert to marker</span>
        </button>
      )}
    </div>
  );
}
