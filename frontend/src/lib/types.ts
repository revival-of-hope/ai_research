export type User = {
  id: number;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
};

export type Usage = {
  today_tokens: number;
  month_tokens: number;
  lifetime_tokens: number;
  input_tokens: number;
  output_tokens: number;
  by_provider: ProviderUsage[];
};

export type ProviderUsage = {
  provider_id: number | null;
  provider_name: string;
  model: string;
  today_tokens: number;
  month_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

export type ProviderType = "openai" | "deepseek" | "qwen" | "anthropic" | "custom";
export type ProviderCatalogEntry = {
  id: ProviderType;
  name: string;
  base_url: string;
  models: string[];
};
export type ProviderModels = { models: string[]; source: "live"; message?: string };

export type Provider = {
  id: number;
  name: string;
  base_url: string;
  model: string;
  compatible: boolean;
  has_api_key: boolean;
  provider_type: ProviderType;
};

export type SourceDocument = {
  id: number;
  filename: string;
  media_type: string;
  size_bytes: number;
  status: "processing" | "ready" | "failed";
  error_message: string | null;
  created_at: string;
};

export type Conversation = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id?: number;
  role: "user" | "assistant";
  content: string;
  mode?: ResearchMode;
  thinking?: string | null;
  provider_id?: number | null;
  provider_name?: string | null;
  model?: string | null;
  total_tokens?: number;
  created_at?: string;
  sources?: ResearchSource[];
  events?: ResearchEvent[];
  usage?: TokenUsage;
  run_id?: string;
  status?: "running" | "completed" | "failed" | "cancelled";
  error?: string | null;
};

export type ResearchRun = {
  id: string;
  conversation_id: number;
  provider_id?: number | null;
  provider_name?: string | null;
  model?: string | null;
  status: "running" | "completed" | "failed" | "cancelled";
  mode: ResearchMode;
  question: string;
  sources: ResearchSource[];
  events: ResearchEvent[];
  usage: TokenUsage;
  error?: string | null;
  created_at: string;
  finished_at?: string | null;
};

export type TokenUsage = { input_tokens: number; output_tokens: number; total_tokens: number };
export type ResearchSource = { label: string; title: string; url?: string | null; snippet?: string; document_id?: number };
export type ResearchEvent = { type: string; data: Record<string, unknown> };
export type ResearchMode = "quick" | "deep";
export type PlanStep = { id: string; title: string };
export type ResearchAgent = {
  id: string;
  parent_id?: string | null;
  name: string;
  task: string;
  status: "running" | "completed" | "failed";
  detail?: string;
};

export type ResearchReply = {
  conversation_id: number;
  provider_id: number;
  answer: string;
  usage: TokenUsage;
  sources: ResearchSource[];
};

export type AdminUser = User & { total_tokens: number };
