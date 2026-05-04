export type ResponseType = "text" | "table" | "bar_chart" | "line_chart" | "pie_chart" | "funnel_chart";

export interface HistoryTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChartConfig {
  type: "bar" | "line" | "pie" | "funnel";
  labels: string[];
  datasets: Record<string, unknown>[];
  title?: string;
}

export interface TableData {
  columns: string[];
  rows: (string | number | null)[][];
}

export interface ChatResponse {
  answer: string;
  response_type: ResponseType;
  chart_config?: ChartConfig;
  table_data?: TableData;
  sql_used?: string;
  session_id: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  response_type?: ResponseType;
  chart_config?: ChartConfig;
  table_data?: TableData;
  sql_used?: string;
  timestamp: Date;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

