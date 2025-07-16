



//TODO sections has no nodes lol
// Add locked and disabled nodes to the sections data
export const sections = [
  {
    id: 0,
    title: "Freshman Fall",
    //nodes: [{ id: 1, label: "6.100" }],
  },
  {
    id: 1,
    title: "Freshman Spring",
    // nodes: [
    //   { id: 2, label: "6.1200" },
    //   { id: 3, label: "6.120a", locked: true }, // Add locked node
    // ],
  },
  {
    id: 2,
    title: "Sophomore Fall",
    //nodes: [{ id: 4, label: "6.sex1", disabled: false }], // Add disabled node
  },
  {
    id: 3,
    title: "Sophomore Spring",
    // nodes: [
    //   { id: 5, label: "6.sex2" },
    //   { id: 6, label: "6.sex3", locked: false }, // Add locked node
    //   { id: 7, label: "6.sex4" },
    // ],
  },
  {
    id: 4,
    title: "Junior Fall",
    //nodes: [{ id: 8, label: "6.sex5" }],
  },
  {
    id: 5,
    title: "Junior Spring",
    // nodes: [
    //   { id: 9, label: "Generate Report" },
    //   { id: 10, label: "Archive Data", disabled: false }, // Add disabled node
    // ],
  },
];

// Add this predefined list of available nodes after the existing data structures
export const availableNodes = [
  {
    id: "auth-1",
    name: "OAuth Authentication",
    category: "Authentication",
    description: "Implement OAuth 2.0 authentication flow",
  },
  {
    id: "auth-2",
    name: "JWT Validation",
    category: "Authentication",
    description: "Validate JSON Web Tokens",
  },
];

// Reduced edges - some nodes are intentionally not connected
//
//
// We can calculate this using autoroad. Do not use the sex
export const edges = [
  // Main flow path
  { from: 1, to: 2 },
  { from: 2, to: 4 },
  { from: 3, to: 4 },
  { from: 4, to: 5 },
  { from: 5, to: 8 },
  { from: 6, to: 8 },
  { from: 8, to: 9 },
  // Add some long-distance connections to demonstrate curved paths
  { from: 1, to: 8 }, // Skip multiple sections
  { from: 3, to: 9 }, // Skip multiple sections
  { from: 2, to: 9 }, // Very long distance connection

  // Note: Nodes 7, 10 are intentionally disconnected
  // They exist in their sections but don't participate in the main flow
];

// Special section that's always present and styled differently
export const specialSection = {
  id: -1,
  title: "ASEs",
  nodes: [{ id: 0, label: "18.01" }],
};

export const nodeDetails = {
  // Special nodes
  0: {
    title: "Entry Point",
    description: "Primary entry point for all workflow processes",
    type: "Gateway",
    status: "Active",
    connections: 1,
    lastUpdated: "2 minutes ago",
  },
  // Regular nodes
  1: {
    title: "Initialize",
    description: "System initialization and startup procedures",
    type: "Process",
    status: "Active",
    connections: 1,
    lastUpdated: "1 minute ago",
  },
  2: {
    title: "Load Data",
    description: "Loads input data from various sources",
    type: "Input",
    status: "Active",
    connections: 2,
    lastUpdated: "30 seconds ago",
  },
  3: {
    title: "Validate Input",
    description: "Validates incoming data for correctness - LOCKED",
    type: "Validation",
    status: "Locked",
    connections: 1,
    lastUpdated: "45 seconds ago",
  },
  4: {
    title: "Verify User",
    description: "Authenticates user credentials - DISABLED",
    type: "Authentication",
    status: "Disabled",
    connections: 0,
    lastUpdated: "20 seconds ago",
  },
  5: {
    title: "Transform Data",
    description: "Processes and transforms input data",
    type: "Processing",
    status: "Active",
    connections: 2,
    lastUpdated: "15 seconds ago",
  },
  6: {
    title: "Apply Filters",
    description: "Applies filtering rules to processed data - LOCKED",
    type: "Processing",
    status: "Locked",
    connections: 1,
    lastUpdated: "10 seconds ago",
  },
  7: {
    title: "Cache Results",
    description: "Stores processed results in cache",
    type: "Storage",
    status: "Idle",
    connections: 0,
    lastUpdated: "3 minutes ago",
  },
  8: {
    title: "Calculate Metrics",
    description: "Computes performance and business metrics",
    type: "Analytics",
    status: "Active",
    connections: 3,
    lastUpdated: "5 seconds ago",
  },
  9: {
    title: "Generate Report",
    description: "Creates output reports and summaries",
    type: "Output",
    status: "Active",
    connections: 1,
    lastUpdated: "Just now",
  },
  10: {
    title: "Archive Data",
    description: "Archives processed data for long-term storage - DISABLED",
    type: "Storage",
    status: "Disabled",
    connections: 0,
    lastUpdated: "7 minutes ago",
  },
};
