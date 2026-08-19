/**
 * TypeScript type definitions for OAI Network
 */

// Identity types
export interface AgentIdentity {
  did: string;
  publicKey: string;
  keyType: 'Ed25519' | 'RSA';
  createdAt: string;
  metadata?: Record<string, any>;
}

export interface IdentityProof {
  challenge: string;
  signature: string;
  signedAt: string;
  signerDid: string;
}

export interface IdentityDocument {
  identity: AgentIdentity;
  proof: IdentityProof;
  documentId: string;
  issuedAt: string;
  expiresAt?: string;
}

// Capability types
export interface Capability {
  name: string;
  description: string;
  type: string;
  inputSchema: Record<string, any>;
  outputSchema: Record<string, any>;
  pricing?: CapabilityPricing;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface CapabilityPricing {
  model: 'free' | 'per_call' | 'per_token' | 'subscription';
  pricePerCall?: number;
  pricePerToken?: number;
  currency?: string;
  subscriptionTier?: string;
}

export interface ServiceEndpoint {
  url: string;
  protocol: 'a2a' | 'mcp' | 'http' | 'grpc' | 'ws';
  description?: string;
  metadata?: Record<string, any>;
}

export interface AgentManifest {
  identity: AgentIdentity;
  name: string;
  description: string;
  version: string;
  capabilities: Capability[];
  endpoints: ServiceEndpoint[];
  trustMetrics?: TrustMetrics;
  metadata?: Record<string, any>;
  tags?: string[];
}

export interface TrustMetrics {
  score: number;
  interactionCount: number;
  successRate: number;
  averageLatencyMs: number;
  lastUpdated: string;
}

// Discovery types
export interface DiscoveryQuery {
  query?: string;
  capability?: string;
  capabilityType?: string;
  tags?: string[];
  minTrustScore?: number;
  verifiedOnly?: boolean;
  maxResults?: number;
  offset?: number;
}

export interface DiscoveryResult {
  agentDid: string;
  name: string;
  description: string;
  version: string;
  capabilities: string[];
  endpoints: ServiceEndpoint[];
  trustScore: number;
  identityVerified: boolean;
  status: HealthStatus;
  lastHeartbeat?: string;
  metadata?: Record<string, any>;
  relevanceScore?: number;
}

export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

export interface RegistryEntry {
  id: string;
  agentDid: string;
  name: string;
  description: string;
  version: string;
  endpoints: string[];
  protocols: string[];
  capabilities: string[];
  capabilityDetails: Record<string, any>;
  identityVerified: boolean;
  trustScore: number;
  publicKey?: string;
  status: HealthStatus;
  lastHeartbeat?: string;
  registeredAt: string;
  updatedAt: string;
  metadata?: Record<string, any>;
  tags?: string[];
}

// Delegation types
export interface DelegationTask {
  capability: string;
  inputData: Record<string, any>;
  description?: string;
  timeoutSeconds?: number;
  metadata?: Record<string, any>;
}

export interface DelegationRequest {
  delegatorDid: string;
  delegateeDid: string;
  task: DelegationTask;
  maxDepth?: number;
  timeoutSeconds?: number;
  priority?: number;
  metadata?: Record<string, any>;
}

export interface DelegationResponse {
  delegationId: string;
  accepted: boolean;
  reason?: string;
  estimatedCompletionSeconds?: number;
}

export interface DelegationStatus {
  delegationId: string;
  status: DelegationStatusType;
  progress?: number;
  result?: any;
  error?: string;
  startedAt: string;
  updatedAt: string;
  completedAt?: string;
}

export type DelegationStatusType = 'pending' | 'accepted' | 'in_progress' | 'completed' | 'failed' | 'cancelled';

export interface DelegationResult {
  delegationId: string;
  status: DelegationStatusType;
  result?: any;
  error?: string;
  completedAt: string;
  latencyMs?: number;
}

export interface DelegationChain {
  id: string;
  rootDelegationId: string;
  steps: DelegationChainStep[];
  status: DelegationStatusType;
  createdAt: string;
  completedAt?: string;
}

export interface DelegationChainStep {
  stepNumber: number;
  delegatorDid: string;
  delegateeDid: string;
  delegationId: string;
  status: DelegationStatusType;
}

// Trust types
export interface TrustScore {
  agentDid: string;
  overallScore: number;
  components: TrustComponents;
  lastUpdated: string;
  eventCount: number;
}

export interface TrustComponents {
  interactionScore: number;
  feedbackScore: number;
  identityScore: number;
  behaviorScore: number;
}

export interface TrustEvent {
  id: string;
  eventType: TrustEventType;
  sourceDid: string;
  targetDid: string;
  value: number;
  weight: number;
  timestamp: string;
  metadata?: Record<string, any>;
}

export type TrustEventType = 
  | 'successful_interaction'
  | 'failed_interaction'
  | 'positive_feedback'
  | 'negative_feedback'
  | 'identity_verified'
  | 'identity_revoked'
  | 'delegation_completed'
  | 'delegation_failed'
  | 'capability_demonstrated'
  | 'policy_violation';

export interface Feedback {
  id: string;
  sourceDid: string;
  targetDid: string;
  rating: number;
  comment?: string;
  interactionId?: string;
  timestamp: string;
}

export interface ReputationLedgerEntry {
  id: string;
  eventId: string;
  previousHash: string;
  currentHash: string;
  timestamp: string;
}

// Negotiation types
export interface NegotiationRequest {
  initiatorDid: string;
  counterpartyDid: string;
  template: string;
  proposedTerms: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface NegotiationResponse {
  sessionId: string;
  accepted: boolean;
  counterTerms?: Record<string, any>;
  reason?: string;
}

export interface NegotiationSession {
  id: string;
  initiatorDid: string;
  counterpartyDid: string;
  status: NegotiationStatus;
  terms: Record<string, any>;
  rounds: NegotiationRound[];
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

export type NegotiationStatus = 'pending' | 'active' | 'agreed' | 'rejected' | 'expired' | 'cancelled';

export interface NegotiationRound {
  roundNumber: number;
  proposerDid: string;
  terms: Record<string, any>;
  timestamp: string;
  accepted?: boolean;
}

// Policy types
export interface Policy {
  id: string;
  name: string;
  description: string;
  version: string;
  rules: PolicyRule[];
  budgets: Budget[];
  defaultEffect: PolicyEffect;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export type PolicyEffect = 'allow' | 'deny';

export interface PolicyRule {
  id: string;
  name: string;
  description: string;
  effect: PolicyEffect;
  conditions: PolicyCondition[];
  priority: number;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export type PolicyConditionType = 
  | 'agent_did'
  | 'agent_name'
  | 'identity_verified'
  | 'trust_score'
  | 'capability_name'
  | 'capability_type'
  | 'capability_tag'
  | 'requester_did'
  | 'delegation_depth'
  | 'is_delegation'
  | 'resource_type'
  | 'resource_path'
  | 'time_of_day'
  | 'day_of_week'
  | 'ip_address'
  | 'custom';

export type PolicyOperator = 
  | 'eq'
  | 'ne'
  | 'in'
  | 'not_in'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'contains'
  | 'starts_with'
  | 'ends_with'
  | 'regex'
  | 'exists';

export interface PolicyCondition {
  type: PolicyConditionType;
  operator: PolicyOperator;
  value: any;
  field?: string;
}

export type BudgetPeriod = 'hourly' | 'daily' | 'weekly' | 'monthly' | 'total';

export interface Budget {
  id: string;
  name: string;
  agentDid?: string;
  requesterDid?: string;
  capabilityName?: string;
  period: BudgetPeriod;
  maxCalls?: number;
  maxCost?: number;
  maxTokens?: number;
  maxLatencyMs?: number;
  currentCalls: number;
  currentCost: number;
  currentTokens: number;
  currentLatencyMs: number;
  periodStart: string;
  enabled: boolean;
}

// A2A Protocol types
export interface A2AMessage {
  id: string;
  type: A2AMessageType;
  timestamp: string;
  senderDid: string;
  recipientDid?: string;
  payload: any;
  signature?: string;
}

export type A2AMessageType = 
  | 'request'
  | 'response'
  | 'error'
  | 'capability_query'
  | 'capability_response'
  | 'delegation_request'
  | 'delegation_response'
  | 'delegation_status'
  | 'negotiation_request'
  | 'negotiation_response'
  | 'heartbeat'
  | 'agent_card';

export interface AgentCard {
  did: string;
  name: string;
  description: string;
  version: string;
  capabilities: Capability[];
  endpoints: ServiceEndpoint[];
  trustScore: number;
  identityVerified: boolean;
  protocols: string[];
}

// MCP Protocol types
export interface MCPRequest {
  jsonrpc: '2.0';
  id: string | number;
  method: string;
  params?: any;
}

export interface MCPResponse {
  jsonrpc: '2.0';
  id: string | number;
  result?: any;
  error?: MCPError;
}

export interface MCPError {
  code: number;
  message: string;
  data?: any;
}

export interface MCPNotification {
  jsonrpc: '2.0';
  method: string;
  params?: any;
}

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, any>;
}

export interface MCPResource {
  uri: string;
  name: string;
  description?: string;
  mimeType?: string;
}

export interface MCPPrompt {
  name: string;
  description: string;
  arguments?: MCPPromptArgument[];
}

export interface MCPPromptArgument {
  name: string;
  description: string;
  required: boolean;
}

// Gateway types
export interface GatewayRequest {
  id: string;
  method: string;
  path: string;
  headers: Record<string, string>;
  queryParams: Record<string, string>;
  body?: any;
  clientIp?: string;
  timestamp: string;
  agentDid?: string;
  capabilityName?: string;
  delegationDepth?: number;
  isDelegation?: boolean;
  requesterDid?: string;
}

export interface GatewayResponse {
  requestId: string;
  statusCode: number;
  headers: Record<string, string>;
  body?: any;
  latencyMs: number;
  upstreamLatencyMs?: number;
  timestamp: string;
  error?: string;
}

export interface RouteRule {
  id: string;
  name: string;
  pathPattern: string;
  methods: string[];
  targetUrl: string;
  targetType: string;
  policyEnabled: boolean;
  requiredCapability?: string;
  requiredTrustScore: number;
  requireVerified: boolean;
  rateLimitRpm?: number;
  rateLimitBurst?: number;
  connectTimeoutMs: number;
  requestTimeoutMs: number;
  maxRetries: number;
  retryOn: number[];
  loadBalancer: string;
  priority: number;
  enabled: boolean;
  metadata?: Record<string, any>;
}