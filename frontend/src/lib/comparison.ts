export type ComparisonFieldKey =
  | "dataset" | "version" | "split" | "model" | "training" | "preprocessing"
  | "seed" | "metric" | "unit" | "value";

export type ComparisonStatus = "pending" | "confirmed";
export type FieldStatus = "aligned" | "mismatch" | "unknown";
export type ReviewStatus = "pending" | "confirmed" | "unresolved";

export type ComparisonEvidence = {
  value: string | null;
  excerpt: string | null;
  chunk_id: number | null;
};

export type ComparisonSourceChunk = {
  chunk_id: number;
  ordinal: number;
  content: string;
};

export type ComparisonField = {
  key: ComparisonFieldKey;
  label: string;
  paper: ComparisonEvidence;
  run: ComparisonEvidence;
  status: FieldStatus;
  review_status: ReviewStatus;
  note: string;
};

export type Comparison = {
  id: number;
  metric: string;
  paper_document_id: number;
  run_document_id: number;
  paper_name: string;
  run_name: string;
  provider_id: number | null;
  status: ComparisonStatus;
  fields: ComparisonField[];
  created_at: string;
};

export type ComparisonListItem = Pick<
  Comparison, "id" | "metric" | "paper_name" | "run_name" | "status" | "created_at"
>;
