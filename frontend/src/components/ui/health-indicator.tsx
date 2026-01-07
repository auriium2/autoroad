import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { Server, Globe } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: {
    backend: { status: string };
    fireroad: { status: string; error?: string };
  };
}

interface HealthIndicatorProps {
  className?: string;
}

export function HealthIndicator({ className }: HealthIndicatorProps) {
  const { data, isError } = useQuery({
    queryKey: queryKeys.health.backend(),
    queryFn: async (): Promise<HealthResponse> => {
      const response = await fetch('/api/health', {
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error('Health check failed');
      return response.json();
    },
    refetchInterval: 30000,
    retry: 1,
  });

  const backendHealthy = !isError && data?.services?.backend?.status === 'healthy';
  const fireroadHealthy = data?.services?.fireroad?.status === 'healthy';

  return (
    <div className={`flex flex-row gap-2 ${className}`}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`${backendHealthy ? 'text-green-500' : 'text-red-500'}`}>
            <Server className="h-4 w-4" />
          </div>
        </TooltipTrigger>
        <TooltipContent>{backendHealthy ? 'Backend: Healthy' : 'Backend: Unavailable'}</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`${fireroadHealthy ? 'text-green-500' : isError ? 'text-gray-500' : 'text-red-500'}`}>
            <Globe className="h-4 w-4" />
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {fireroadHealthy ? 'Fireroad: Healthy' : `Fireroad: ${data?.services?.fireroad?.error || 'Unavailable'}`}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
