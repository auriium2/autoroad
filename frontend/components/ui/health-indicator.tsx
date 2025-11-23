import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { optimizerApi } from '@/services/optimizer';
import { fireroadApi } from '@/services/fireroad';
import { BrainCircuit, Globe, Server } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface HealthIndicatorProps {
  className?: string;
}

export function HealthIndicator({ className }: HealthIndicatorProps) {
  // Check backend (optimizer) health
  const { data: backendHealth, isError: backendError } = useQuery({
    queryKey: ['backend-health'],
    queryFn: () => optimizerApi.checkHealth(),
    refetchInterval: 30000,
    retry: 1,
  });

  // Check Fireroad health
  const { data: fireroadHealth, isError: fireroadError } = useQuery({
    queryKey: ['fireroad-health'],
    queryFn: () => fireroadApi.checkHealth(),
    refetchInterval: 30000,
    retry: 1,
  });

  // Check Next.js health
  const { data: nextjsHealth, isError: nextjsError } = useQuery({
    queryKey: ['nextjs-health'],
    queryFn: async () => {
      const response = await fetch('/api/health', {
        signal: AbortSignal.timeout(3000),
      });
      if (!response.ok) throw new Error('Health check failed');
      return response.json();
    },
    refetchInterval: 30000,
    retry: 1,
  });

  const backendHealthy = !backendError && backendHealth?.status === 'healthy';
  const fireroadHealthy = !fireroadError && fireroadHealth?.status === 'healthy';
  const nextjsHealthy = !nextjsError && nextjsHealth?.status === 'healthy';

  return (
    <div className={`flex flex-row gap-2 ${className}`}>
      {/* Backend status */}
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`${backendHealthy ? 'text-green-500' : 'text-red-500'}`}>
            <BrainCircuit className="h-4 w-4" />
          </div>
        </TooltipTrigger>
        <TooltipContent>{backendHealthy ? 'Optimizer: Healthy' : 'Optimizer: Unavailable'}</TooltipContent>
      </Tooltip>

      {/* Fireroad status */}
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`${fireroadHealthy ? 'text-green-500' : 'text-red-500'}`}>
            <Globe className="h-4 w-4" />
          </div>
        </TooltipTrigger>
        <TooltipContent>{fireroadHealthy ? 'Fireroad: Healthy' : 'Fireroad: Unavailable'}</TooltipContent>
      </Tooltip>

      {/* Next.js status */}
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`${nextjsHealthy ? 'text-green-500' : 'text-red-500'}`}>
            <Server className="h-4 w-4" />
          </div>
        </TooltipTrigger>
        <TooltipContent>{nextjsHealthy ? 'Auriium.xyz: Healthy' : 'Auriium.xyz: Unavailable'}</TooltipContent>
      </Tooltip>
    </div>
  );
}
