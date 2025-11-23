interface GraphOverlayProps {
  isOptimizing: boolean;
}

export function GraphOverlay({ isOptimizing }: GraphOverlayProps) {
  if (!isOptimizing) return null;
  
  return (
    <div className="absolute inset-0 bg-black/20 backdrop-blur-[1.5px] z-[100] pointer-events-none" />
  );
}
