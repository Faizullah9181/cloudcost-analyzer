export type CloudProvider = 'aws' | 'azure' | 'gcp' | 'digitalocean';
export type ChartType = 'bar' | 'line' | 'pie' | 'area';

export interface CostDataPoint {
  label: string;
  value: number;
  unit: string;
}

export interface CostBreakdown {
  service: string;
  cost: number;
  percentage: number;
  change: number;
}

export interface TimeSeriesPoint {
  date: string;
  cost: number;
  service: string;
}

export interface ProviderTotals {
  total: number;
  services: Record<string, number>;
}

export interface AnalysisResult {
  summary: string;
  total_cost: number;
  currency: string;
  period: string;
  providers: Record<string, ProviderTotals>;
  service_breakdown: CostBreakdown[];
  time_series: TimeSeriesPoint[];
  top_costs: CostDataPoint[];
  recommendations: string[];
  raw_response: string;
  chart_type: ChartType;
  query_type: string;
  a2ui_messages: Array<Record<string, unknown>>;
}

export interface QueryResponse {
  success: boolean;
  data: AnalysisResult | null;
  error: string | null;
  session_id?: string | null;
}

export interface ToolCall {
  tool: string;
  calls: number;
  successes: number;
  errors: number;
  seconds: number;
}

export interface ChatResponse {
  success: boolean;
  session_id: string;
  message: string;
  data: AnalysisResult | null;
  error: string | null;
  memory: Record<string, unknown>;
  tool_calls: ToolCall[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  data?: AnalysisResult;
  timestamp: Date;
  loading?: boolean;
  error?: boolean;
  toolCalls?: ToolCall[];
}

export type ConnectionContext = Record<string, Record<string, string>>;

export interface SessionSummary {
  id: string;
  name: string;
  user_id?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  context_tokens: number;
  compression_count: number;
  cloud_providers: Record<string, boolean>;
  connection_context: ConnectionContext;
  llm_provider: string;
  llm_model: string;
  is_active: boolean;
  tags: string[];
}

export interface SessionMessage {
  id: string;
  seq: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string | null;
  tokens_used: number;
  provider: string | null;
  tags: string[];
  analysis: Partial<AnalysisResult> | null;
  is_summary: boolean;
}

export interface MessagesResponse {
  session_id: string;
  message_count: number;
  messages: SessionMessage[];
}

export interface SessionCreatePayload {
  name: string;
  cloud_providers: string[];
  llm_provider?: string;
  connection_context?: ConnectionContext;
  user_id?: string;
}

export interface ProviderStatus {
  name: CloudProvider;
  configured: boolean;
  details: Record<string, unknown>;
  tools: string[];
}

export interface ProvidersResponse {
  llm_provider: string;
  llm_model: string;
  providers: ProviderStatus[];
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  llm_provider: string;
  llm_model: string;
}

export interface CompressResponse {
  session_id: string;
  compressed_messages: number;
  pruned_messages: number;
  summary: string;
  compression_count: number;
}
