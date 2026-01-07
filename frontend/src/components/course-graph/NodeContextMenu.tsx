
import * as React from "react";
import * as ContextMenu from "@radix-ui/react-context-menu";
import { Pin, Ban, Trash2 } from "lucide-react";
import type { CourseNode } from "@/types";

interface NodeContextMenuProps {
  node: CourseNode;
  onPin: () => void;
  onBanish: () => void;
  onRemove: () => void;
  children: React.ReactNode;
}

export function NodeContextMenu({
  node,
  onPin,
  onBanish,
  onRemove,
  children,
}: NodeContextMenuProps) {
  // Only show context menu for user-controlled nodes
  if (!node.userControlled) {
    return <>{children}</>;
  }

  const currentStatus = node.nodeStatus || 'pin';

  return (
    <ContextMenu.Root>
      <ContextMenu.Trigger asChild>
        {children}
      </ContextMenu.Trigger>

      <ContextMenu.Portal>
        <ContextMenu.Content
          className="min-w-[180px] bg-card border border-border rounded-md shadow-lg p-1 z-50"
        >
          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer outline-none hover:bg-muted/50 focus:bg-muted/50 transition-colors data-[disabled]:opacity-50 data-[disabled]:pointer-events-none"
            onSelect={onPin}
            disabled={currentStatus === 'pin'}
          >
            <Pin className="w-4 h-4" />
            <span>Pin (default)</span>
            {currentStatus === 'pin' && (
              <span className="ml-auto text-xs text-muted-foreground">✓</span>
            )}
          </ContextMenu.Item>

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer outline-none hover:bg-muted/50 focus:bg-muted/50 transition-colors data-[disabled]:opacity-50 data-[disabled]:pointer-events-none"
            onSelect={onBanish}
            disabled={currentStatus === 'banish'}
          >
            <Ban className="w-4 h-4" />
            <span>Banish</span>
            {currentStatus === 'banish' && (
              <span className="ml-auto text-xs text-muted-foreground">✓</span>
            )}
          </ContextMenu.Item>

          <ContextMenu.Separator className="h-px bg-border my-1" />

          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer outline-none hover:bg-destructive/10 focus:bg-destructive/10 text-destructive transition-colors"
            onSelect={onRemove}
          >
            <Trash2 className="w-4 h-4" />
            <span>Remove marker</span>
          </ContextMenu.Item>
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  );
}
