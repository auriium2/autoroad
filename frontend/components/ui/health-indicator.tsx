import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { optimizerApi } from '@/services/optimizer';
import { fireroadApi } from '@/services/fireroad';

interface HealthIndicatorProps {
  className?: string;
}

export function HealthIndicator({ className }: HealthIndicatorProps) {
  // Check optimizer health
  const { data: optimizerHealth, isError: optimizerError } = useQuery({
    queryKey: ['optimizer-health'],
    queryFn: () => optimizerApi.checkHealth(),
    refetchInterval: 30000, // Check every 30 seconds
    retry: 1,
  });

  // Check Fireroad health
  const { data: fireroadHealth, isError: fireroadError } = useQuery({
    queryKey: ['fireroad-health'],
    queryFn: () => fireroadApi.checkHealth(),
    refetchInterval: 30000, // Check every 30 seconds
    retry: 1,
  });

  const optimizerHealthy = !optimizerError && optimizerHealth?.status === 'healthy';
  const fireroadHealthy = !fireroadError && fireroadHealth?.status === 'healthy';

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {/* Optimizer status */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-foreground text-right w-16">
          Autoroad
        </span>
        <div
          className={`w-2 h-2 rounded-full flex-shrink-0 ${
            optimizerHealthy ? 'bg-green-500' : 'bg-red-500'
          }`}
          title={optimizerHealthy ? 'Optimizer: Healthy' : 'Optimizer: Unavailable'}
        />
      </div>

      {/* Fireroad status */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-foreground text-right w-16">
          Fireroad
        </span>
        <div
          className={`w-2 h-2 rounded-full flex-shrink-0 ${
            fireroadHealthy ? 'bg-green-500' : 'bg-red-500'
          }`}
          title={fireroadHealthy ? 'Fireroad: Healthy' : 'Fireroad: Unavailable'}
        />
      </div>
    </div>
  );
}
