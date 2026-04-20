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

export interface AnalysisResult {
  summary: string;
  total_cost: number;
  currency: string;
  period: string;
  service_breakdown: CostBreakdown[];
  time_series: TimeSeriesPoint[];
  top_costs: CostDataPoint[];
  recommendations: string[];
  raw_response: string;
  chart_type: 'bar' | 'line' | 'pie' | 'area';
}

export interface QueryResponse {
  success: boolean;
  data: AnalysisResult | null;
  error: string | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  data?: AnalysisResult;
  timestamp: Date;
  loading?: boolean;
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
}

export interface Suggestion {
  text: string;
}
