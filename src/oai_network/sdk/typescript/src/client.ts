/**
 * OAI Network TypeScript SDK Client
 * 
 * Main client for interacting with OAI Network services.
 */

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import WebSocket from 'ws';
import { v4 as uuidv4 } from 'uuid';

import {
  AgentIdentity,
  IdentityDocument,
  AgentManifest,
  Capability,
  ServiceEndpoint,
  DiscoveryQuery,
  DiscoveryResult,
  RegistryEntry,
  DelegationRequest,
  DelegationResponse,
  DelegationTask,
  DelegationResult,
  DelegationStatus,
  TrustScore,
  TrustEvent,
  Feedback,
  NegotiationRequest,
  NegotiationResponse,
  NegotiationSession,
  HealthStatus,
  A2AMessage,
  AgentCard,
  MCPClient as MCPClientType,
  MCPRequest,
  MCPResponse,
  MCPTool,
  MCPResource,
  MCPPrompt,
} from './types';

export interface OAIClientConfig {
  registryUrl?: string;
  gatewayUrl?: string;
  identity?: AgentIdentity;
  timeout?: number;
}

export class OAIClient {
  private registryUrl: string;
  private gatewayUrl: string;
  public identity: AgentIdentity | null = null;
  private timeout: number;
  private httpClient: AxiosInstance;
  private a2aWs: WebSocket | null = null;
  private mcpWs: WebSocket | null = null;
  private a2aPendingRequests: Map<string, (response: any) => void> = new Map();
  private mcpPendingRequests: Map<string, (response: any) => void> = new Map();

  constructor(config: OAIClientConfig = {}) {
    this.registryUrl = (config.registryUrl || 'http://localhost:8081').replace(/\/$/, '');
    this.gatewayUrl = (config.gatewayUrl || 'http://localhost:8080').replace(/\/$/, '');
    this.identity = config.identity || null;
    this.timeout = config.timeout || 30000;

    this.httpClient = axios.create({
      timeout: this.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // Identity management
  generateIdentity(name: string, keyType: 'Ed25519' | 'RSA' = 'Ed25519'): IdentityDocument {
    // In a real implementation, this would use Web Crypto API or a crypto library
    // For now, return a mock identity
    const did = `did:oai:${uuidv4()}`;
    const publicKey = `mock-public-key-${uuidv4()}`;
    
    const identity: AgentIdentity = {
      did,
      publicKey,
      keyType,
      createdAt: new Date().toISOString(),
    };

    const proof: IdentityDocument['proof'] = {
      challenge: uuidv4(),
      signature: `mock-signature-${uuidv4()}`,
      signedAt: new Date().toISOString(),
      signerDid: did,
    };

    return {
      identity,
      proof,
      documentId: uuidv4(),
      issuedAt: new Date().toISOString(),
    };
  }

  loadIdentity(identityDoc: IdentityDocument): AgentIdentity {
    this.identity = identityDoc.identity;
    return this.identity;
  }

  saveIdentity(path: string): void {
    if (!this.identity) {
      throw new Error('No identity loaded');
    }
    const fs = require('fs');
    fs.writeFileSync(path, JSON.stringify(this.identity, null, 2));
  }

  static loadIdentityFromFile(path: string): OAIClient {
    const fs = require('fs');
    const data = JSON.parse(fs.readFileSync(path, 'utf-8'));
    const identity: AgentIdentity = data;
    return new OAIClient({ identity });
  }

  // Registry operations
  async registerAgent(manifest: AgentManifest, identityProof?: string): Promise<any> {
    const payload = {
      agent_did: manifest.identity.did,
      name: manifest.name,
      description: manifest.description,
      version: manifest.version,
      endpoints: manifest.endpoints.map(e => e.url),
      protocols: [...new Set(manifest.endpoints.map(e => e.protocol))],
      capabilities: manifest.capabilities.map(c => c.name),
      capability_details: Object.fromEntries(
        manifest.capabilities.map(c => [c.name, c])
      ),
      public_key: manifest.identity.publicKey,
      identity_proof: identityProof,
      metadata: manifest.metadata,
      tags: manifest.tags,
    };

    const response = await this.httpClient.post(`${this.registryUrl}/register`, payload);
    return response.data;
  }

  async heartbeat(status: HealthStatus = 'healthy', metadata: Record<string, any> = {}): Promise<any> {
    if (!this.identity) {
      throw new Error('No identity loaded');
    }

    const payload = {
      agent_did: this.identity.did,
      status,
      metadata,
    };

    const response = await this.httpClient.post(`${this.registryUrl}/heartbeat`, payload);
    return response.data;
  }

  async unregisterAgent(): Promise<boolean> {
    if (!this.identity) {
      throw new Error('No identity loaded');
    }

    const response = await this.httpClient.delete(`${this.registryUrl}/agents/${this.identity.did}`);
    return response.status === 200;
  }

  // Discovery operations
  async discover(query: DiscoveryQuery): Promise<DiscoveryResult[]> {
    const params = new URLSearchParams();
    if (query.query) params.append('query', query.query);
    if (query.capability) params.append('capability', query.capability);
    if (query.capabilityType) params.append('capability_type', query.capabilityType);
    if (query.tags) params.append('tags', query.tags.join(','));
    if (query.minTrustScore) params.append('min_trust_score', query.minTrustScore.toString());
    if (query.verifiedOnly) params.append('verified_only', 'true');
    if (query.maxResults) params.append('limit', query.maxResults.toString());
    if (query.offset) params.append('offset', query.offset.toString());

    const response = await this.httpClient.get(`${this.registryUrl}/discover?${params.toString()}`);
    return response.data.results || [];
  }

  async findAgent(query: string): Promise<DiscoveryResult[]> {
    return this.discover({ query });
  }

  async getAgent(agentDid: string): Promise<RegistryEntry | null> {
    try {
      const response = await this.httpClient.get(`${this.registryUrl}/agents/${agentDid}`);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  // Capability operations
  async queryCapability(
    agentDid: string,
    capabilityName: string,
    inputData: Record<string, any>
  ): Promise<any> {
    const agent = await this.getAgent(agentDid);
    if (!agent) {
      throw new Error(`Agent not found: ${agentDid}`);
    }

    const capabilityDetail = agent.capabilityDetails[capabilityName];
    if (!capabilityDetail) {
      throw new Error(`Capability not found: ${capabilityName}`);
    }

    // Use A2A protocol to query
    const a2aClient = await this.getA2AClient(agent);
    return a2aClient.queryCapability(capabilityName, inputData);
  }

  // Delegation operations
  async delegate(
    task: string,
    capability: string,
    inputData: Record<string, any>,
    options: {
      preferredAgent?: string;
      maxDepth?: number;
      timeout?: number;
    } = {}
  ): Promise<DelegationResult> {
    if (!this.identity) {
      throw new Error('No identity loaded');
    }

    // Discover capable agents
    const agents = await this.discover({
      capability,
      minTrustScore: 0.5,
      verifiedOnly: true,
    });

    if (agents.length === 0) {
      throw new Error(`No agents found with capability: ${capability}`);
    }

    // Select agent
    let targetAgent = agents[0];
    if (options.preferredAgent) {
      const preferred = agents.find(a => a.agentDid === options.preferredAgent);
      if (preferred) targetAgent = preferred;
    }

    // Create delegation request
    const delegationRequest: DelegationRequest = {
      delegatorDid: this.identity.did,
      delegateeDid: targetAgent.agentDid,
      task: {
        capability,
        inputData,
        description: task,
      },
      maxDepth: options.maxDepth || 3,
      timeoutSeconds: options.timeout || 60,
    };

    // Execute delegation via A2A
    const a2aClient = await this.getA2AClient(targetAgent);
    const response = await a2aClient.delegate(delegationRequest);

    if (!response.accepted) {
      throw new Error(`Delegation rejected: ${response.reason}`);
    }

    // Wait for result
    return this.waitForDelegationResult(a2aClient, response.delegationId, options.timeout || 60000);
  }

  private async waitForDelegationResult(
    client: A2AClient,
    delegationId: string,
    timeout: number
  ): Promise<DelegationResult> {
    const start = Date.now();

    while (Date.now() - start < timeout) {
      const status = await client.getDelegationStatus(delegationId);

      if (status.status === 'completed') {
        return {
          delegationId,
          status: status.status,
          result: status.result,
          completedAt: new Date().toISOString(),
        };
      } else if (status.status === 'failed') {
        throw new Error(`Delegation failed: ${status.error}`);
      }

      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    throw new Error(`Delegation timed out after ${timeout}ms`);
  }

  // Trust operations
  async getTrustScore(agentDid: string): Promise<TrustScore | null> {
    try {
      const response = await this.httpClient.get(`${this.registryUrl}/trust/${agentDid}`);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  async submitFeedback(
    targetDid: string,
    rating: number,
    comment: string = '',
    interactionId?: string
  ): Promise<TrustEvent> {
    if (!this.identity) {
      throw new Error('No identity loaded');
    }

    const payload = {
      source_did: this.identity.did,
      target_did: targetDid,
      rating,
      comment,
      interaction_id: interactionId,
    };

    const response = await this.httpClient.post(`${this.registryUrl}/feedback`, payload);
    return response.data;
  }

  // Negotiation operations
  async negotiate(
    counterpartyDid: string,
    terms: Record<string, any>,
    template: string = 'standard'
  ): Promise<NegotiationSession> {
    if (!this.identity) {
      throw new Error('No identity loaded');
    }

    const request: NegotiationRequest = {
      initiatorDid: this.identity.did,
      counterpartyDid,
      template,
      proposedTerms: terms,
    };

    const counterparty = await this.getAgent(counterpartyDid);
    if (!counterparty) {
      throw new Error(`Counterparty not found: ${counterpartyDid}`);
    }

    const a2aClient = await this.getA2AClient(counterparty);
    const response = await a2aClient.negotiate(request);

    return {
      id: response.sessionId,
      initiatorDid: this.identity.did,
      counterpartyDid,
      status: 'active',
      terms: response.counterTerms || terms,
      rounds: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }

  // A2A Client
  private async getA2AClient(agent: RegistryEntry): Promise<A2AClient> {
    // Find A2A endpoint
    let a2aEndpoint = agent.endpoints.find(e => e.toLowerCase().includes('a2a'));
    if (!a2aEndpoint && agent.endpoints.length > 0) {
      a2aEndpoint = agent.endpoints[0];
    }

    if (!a2aEndpoint) {
      throw new Error(`No A2A endpoint for agent ${agent.agentDid}`);
    }

    const client = new A2AClient(a2aEndpoint, this.identity!);
    await client.connect();
    return client;
  }

  // MCP Client
  async getMCPClient(agent: RegistryEntry): Promise<MCPClient> {
    // Find MCP endpoint
    let mcpEndpoint = agent.endpoints.find(e => e.toLowerCase().includes('mcp'));
    if (!mcpEndpoint && agent.endpoints.length > 0) {
      mcpEndpoint = agent.endpoints[0];
    }

    if (!mcpEndpoint) {
      throw new Error(`No MCP endpoint for agent ${agent.agentDid}`);
    }

    const client = new MCPClient(mcpEndpoint);
    await client.initialize();
    return client;
  }

  // Utility methods
  async healthCheck(): Promise<Record<string, any>> {
    const results: Record<string, any> = {};

    try {
      const response = await this.httpClient.get(`${this.registryUrl}/health`);
      results.registry = response.data;
    } catch (error: any) {
      results.registry = { status: 'unhealthy', error: error.message };
    }

    try {
      const response = await this.httpClient.get(`${this.gatewayUrl}/health`);
      results.gateway = response.data;
    } catch (error: any) {
      results.gateway = { status: 'unhealthy', error: error.message };
    }

    return results;
  }

  // Discovery alias
  async discoverAgents(query: DiscoveryQuery): Promise<DiscoveryResult[]> {
    return this.discover(query);
  }

  // Delegation alias
  async delegateTask(
    task: string,
    capability: string,
    inputData: Record<string, any>,
    options: {
      preferredAgent?: string;
      maxDepth?: number;
      timeout?: number;
    } = {}
  ): Promise<DelegationResult> {
    return this.delegate(task, capability, inputData, options);
  }

  // Identity creation
  async createIdentity(name: string, keyType: 'Ed25519' | 'RSA' = 'Ed25519'): Promise<AgentIdentity> {
    const identity = this.generateIdentity(name, keyType);
    this.identity = identity.identity;
    return this.identity;
  }

  // Signing and verification
  async signMessage(message: string): Promise<string> {
    // In a real implementation, this would use the private key
    // For now, return a mock signature
    return `mock-signature-${uuidv4()}`;
  }

  async verifySignature(agentDid: string, message: string, signature: string): Promise<boolean> {
    // In a real implementation, this would verify the signature
    // For now, return true for mock signatures
    return signature.startsWith('mock-signature-');
  }

  async close(): Promise<void> {
    if (this.a2aWs) {
      this.a2aWs.close();
      this.a2aWs = null;
    }
    if (this.mcpWs) {
      this.mcpWs.close();
      this.mcpWs = null;
    }
  }
}

// A2A Client implementation
export class A2AClient {
  private baseUrl: string;
  private identity: AgentIdentity;
  private ws: WebSocket | null = null;
  private pendingRequests: Map<string, (response: any) => void> = new Map();
  private connected = false;

  constructor(baseUrl: string, identity: AgentIdentity) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.identity = identity;
  }

  async connect(): Promise<void> {
    const wsUrl = this.baseUrl.replace('http', 'ws') + '/a2a';
    this.ws = new WebSocket(wsUrl);

    return new Promise((resolve, reject) => {
      this.ws!.on('open', () => {
        this.connected = true;
        this.ws!.on('message', (data: Buffer) => this.handleMessage(data.toString()));
        resolve();
      });

      this.ws!.on('error', (error) => {
        reject(error);
      });

      this.ws!.on('close', () => {
        this.connected = false;
      });
    });
  }

  async connectWebSocket(): Promise<void> {
    return this.connect();
  }

  async sendRequest(message: any): Promise<any> {
    if (!this.ws || !this.connected) {
      throw new Error('Not connected to A2A server');
    }

    const requestId = message.id || uuidv4();
    message.id = requestId;

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(requestId, resolve);

      this.ws!.send(JSON.stringify(message));

      // Timeout after 30 seconds
      setTimeout(() => {
        if (this.pendingRequests.has(requestId)) {
          this.pendingRequests.delete(requestId);
          reject(new Error('Request timeout'));
        }
      }, 30000);
    });
  }

  async capabilityQuery(capabilityName: string, inputData: Record<string, any>): Promise<any> {
    return this.queryCapability(capabilityName, inputData);
  }

  async queryCapability(capabilityName: string, inputData: Record<string, any>): Promise<any> {
    const response = await this.sendRequest({
      type: 'capability_query',
      senderDid: this.identity.did,
      payload: {
        capability: capabilityName,
        input: inputData,
      },
    });

    if (response.error) {
      throw new Error(response.error);
    }

    return response.payload;
  }

  async delegate(request: DelegationRequest): Promise<DelegationResponse> {
    const response = await this.sendRequest({
      type: 'delegation_request',
      senderDid: this.identity.did,
      recipientDid: request.delegateeDid,
      payload: request,
    });

    return {
      delegationId: response.payload.delegationId,
      accepted: response.payload.accepted,
      reason: response.payload.reason,
      estimatedCompletionSeconds: response.payload.estimatedCompletionSeconds,
    };
  }

  async getDelegationStatus(delegationId: string): Promise<DelegationStatus> {
    const response = await this.sendRequest({
      type: 'delegation_status',
      senderDid: this.identity.did,
      payload: { delegationId },
    });

    return response.payload;
  }

  async negotiate(request: NegotiationRequest): Promise<NegotiationResponse> {
    const response = await this.sendRequest({
      type: 'negotiation_request',
      senderDid: this.identity.did,
      recipientDid: request.counterpartyDid,
      payload: request,
    });

    return {
      sessionId: response.payload.sessionId,
      accepted: response.payload.accepted,
      counterTerms: response.payload.counterTerms,
      reason: response.payload.reason,
    };
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.connected = false;
    }
  }
}

// MCP Client implementation
export class MCPClient {
  private baseUrl: string;
  private httpClient: AxiosInstance;
  private ws: WebSocket | null = null;
  private pendingRequests: Map<string, (response: any) => void> = new Map();
  private initialized = false;
  private serverInfo: any = null;
  private serverCapabilities: any = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.httpClient = axios.create({
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  async initialize(): Promise<any> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      id: uuidv4(),
      method: 'initialize',
      params: {
        protocolVersion: '2024-11-05',
        clientInfo: { name: 'oai-network-sdk', version: '0.1.0' },
      },
    };

    const response = await this.sendRequest(request);
    
    if (response.error) {
      throw new Error(`Initialization failed: ${response.error.message}`);
    }

    this.initialized = true;
    this.serverInfo = response.result.serverInfo;
    this.serverCapabilities = response.result.capabilities;

    return response.result;
  }

  async connectWebSocket(): Promise<void> {
    const wsUrl = this.baseUrl.replace('http', 'ws') + '/mcp';
    this.ws = new WebSocket(wsUrl);

    return new Promise((resolve, reject) => {
      this.ws!.on('open', () => {
        this.ws!.on('message', (data: Buffer) => this.handleMessage(data.toString()));
        resolve();
      });

      this.ws!.on('error', reject);
    });
  }

  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data);
      const requestId = message.id;

      if (requestId && this.pendingRequests.has(requestId)) {
        const resolver = this.pendingRequests.get(requestId)!;
        this.pendingRequests.delete(requestId);
        resolver(message);
      }
    } catch (error) {
      console.error('Failed to parse MCP message:', error);
    }
  }

  private async sendRequest(request: MCPRequest): Promise<MCPResponse> {
    if (this.ws) {
      const requestId = request.id as string;

      return new Promise((resolve, reject) => {
        this.pendingRequests.set(requestId, resolve);
        this.ws!.send(JSON.stringify(request));

        setTimeout(() => {
          if (this.pendingRequests.has(requestId)) {
            this.pendingRequests.delete(requestId);
            reject(new Error('Request timeout'));
          }
        }, 30000);
      });
    } else {
      const response = await this.httpClient.post(`${this.baseUrl}/mcp`, request);
      return response.data;
    }
  }

  async listTools(): Promise<MCPTool[]> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      id: uuidv4(),
      method: 'tools/list',
    };

    const response = await this.sendRequest(request);
    return response.result?.tools || [];
  }

  async callTool(name: string, arguments_: Record<string, any>): Promise<any> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      id: uuidv4(),
      method: 'tools/call',
      params: { name, arguments: arguments_ },
    };

    const response = await this.sendRequest(request);
    
    if (response.error) {
      throw new Error(`Tool call failed: ${response.error.message}`);
    }

    return response.result;
  }

  async listResources(): Promise<MCPResource[]> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      id: uuidv4(),
      method: 'resources/list',
    };

    const response = await this.sendRequest(request);
    return response.result?.resources || [];
  }

  async readResource(uri: string): Promise<any> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      id: uuidv4(),
      method: 'resources/read',
      params: { uri },
    };

    const response = await this.sendRequest(request);
    
    if (response.error) {
      throw new Error(`Failed to read resource: ${response.error.message}`);
    }

    return response.result;
  }

  async listPrompts(): Promise<MCPPrompt[]> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      id: uuidv4(),
      method: 'prompts/list',
    };

    const response = await this.sendRequest(request);
    return response.result?.prompts || [];
  }

  async getPrompt(name: string, arguments_: Record<string, any> = {}): Promise<any> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      id: uuidv4(),
      method: 'prompts/get',
      params: { name, arguments: arguments_ },
    };

    const response = await this.sendRequest(request);
    
    if (response.error) {
      throw new Error(`Failed to get prompt: ${response.error.message}`);
    }

    return response.result;
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}