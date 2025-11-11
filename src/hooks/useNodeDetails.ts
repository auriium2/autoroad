import { useQuery } from '@tanstack/react-query';

export interface NodeDetail {
  title: string;
  description: string;
  type: string;
  status: string;
  connections: number;
  lastUpdated: string;
  units?: number;
  prerequisites?: string[];
  corequisites?: string[];
}

// Mock data for development until we have a real API endpoint
const mockNodeDetails: Record<string, NodeDetail> = {
  "0": {
    title: "18.01 - Calculus",
    description: "Single Variable Calculus",
    type: "ASE",
    status: "Active",
    connections: 1,
    lastUpdated: "2 minutes ago",
    units: 12,
    prerequisites: [],
  },
  "1": {
    title: "6.100A - Introduction to Programming",
    description: "Introduction to computer programming and algorithm development",
    type: "Course",
    status: "Active",
    connections: 1,
    lastUpdated: "1 minute ago",
    units: 12,
    prerequisites: [],
  },
  "2": {
    title: "6.1200 - Mathematics for Computer Science",
    description: "Elementary discrete mathematics for science and engineering",
    type: "Course",
    status: "Active",
    connections: 2,
    lastUpdated: "30 seconds ago",
    units: 12,
    prerequisites: ["1"],
  },
  "3": {
    title: "6.120A - Discrete Mathematics",
    description: "Advanced discrete mathematics topics",
    type: "Course",
    status: "Locked",
    connections: 1,
    lastUpdated: "45 seconds ago",
    units: 12,
    prerequisites: ["1"],
  },
  "4": {
    title: "6.1010 - Fundamentals of Programming",
    description: "Advanced programming concepts",
    type: "Course",
    status: "Disabled",
    connections: 0,
    lastUpdated: "20 seconds ago",
    units: 12,
    prerequisites: ["2", "3"],
  },
  "5": {
    title: "6.1020 - Software Construction",
    description: "Concepts and techniques for software construction",
    type: "Course",
    status: "Active",
    connections: 2,
    lastUpdated: "15 seconds ago",
    units: 12,
    prerequisites: ["4"],
  },
};

// Fetcher function for TanStack Query
const fetchNodeDetails = async (nodeId: string): Promise<NodeDetail> => {
  try {
    // Make an API call to fetch node details
    const response = await fetch(`/api/nodes/${nodeId}`);
    if (!response.ok) throw new Error('Failed to fetch node details');
    return await response.json();
  } catch (error) {
    console.error(`Error fetching details for node ${nodeId}:`, error);

    // Fallback to mock data in case of error
    if (mockNodeDetails[nodeId]) {
      return mockNodeDetails[nodeId];
    }

    // Return default data if all else fails
    return {
      title: `Course ${nodeId}`,
      description: "No description available",
      type: "Course",
      status: "Unknown",
      connections: 0,
      lastUpdated: "Unknown",
      units: 12,
      prerequisites: [],
    };
  }
};

export function useNodeDetails(nodeId: string) {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['node', nodeId],
    queryFn: () => fetchNodeDetails(nodeId),
    enabled: !!nodeId,
    staleTime: 60000, // 1 minute
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  return {
    nodeDetails: data,
    isLoading,
    isError: !!error,
    refresh: refetch,
  };
}
