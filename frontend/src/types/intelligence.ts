export interface SourceReference {
  entity: string;
  id: string;
  reference: string;
}

export interface Citation {
  source_reference: string;
  entity?: string | null;
  id?: string | null;
  is_verified: boolean;
}

export interface DeterministicQualityMetrics {
  total_declared_quantity: number;
  total_items_registered: number;
  inspected_items: number;
  inspection_coverage_pct: number;
  reviewed_items: number;
  pending_review_items: number;
  unreviewed_ai_flagged_items: number;
  confirmed_defects_count: number;
  open_defects_count: number;
  resolved_defects_count: number;
  active_capas_count: number;
  overdue_capas_count: number;
  verified_capas_count: number;
  is_release_eligible: boolean;
  release_blockers_count: number;
  release_blockers: string[];
}

export interface IntelligenceQueryRequest {
  batch_identifier: string;
  target_batch_id?: string;
  question: string;
  prompt?: string;
}

export interface IntelligenceQueryResponse {
  answer: string;
  is_fallback: boolean;
  model_provider: string;
  model_name: string;
  deterministic_metrics: DeterministicQualityMetrics;
  retrieved_source_ids: SourceReference[];
  citations: Citation[];
  unverified_citations: string[];
  limitations: string[];
  disclaimer: string;
  latency_ms?: number | null;
}

export type AttentionPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type AttentionCategory = 'RELEASE_BLOCKER' | 'DEFECT' | 'CORRECTIVE_ACTION' | 'INSPECTION' | 'REVIEW';

export interface AttentionItem {
  item_id: string;
  priority: AttentionPriority;
  category: AttentionCategory;
  reason_code: string;
  title: string;
  explanation: string;
  batch_id?: string | null;
  batch_number?: string | null;
  entity_type: string;
  entity_id: string;
  business_identifier: string;
  current_status: string;
  due_date?: string | null;
  is_overdue: boolean;
  related_defect_id?: string | null;
  related_capa_id?: string | null;
  related_inspection_id?: string | null;
  reasons: string[];
  citations: Citation[];
}

export interface AttentionResponse {
  analysis_timestamp: string;
  total_items: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  overdue_capas_count: number;
  pending_verification_capas_count: number;
  unresolved_defects_count: number;
  pending_reviews_count: number;
  active_release_blockers_count: number;
  items: AttentionItem[];
  ai_summary?: string | null;
  limitations: string[];
}

export interface MatchingAttribute {
  name: string;
  matched: boolean;
  weight: number;
  details: string;
}

export interface HistoricalDefectMatch {
  defect_id: string;
  defect_number: string;
  category: string;
  severity: string;
  status: string;
  review_decision?: string | null;
  surface_location?: string | null;
  description?: string | null;
  created_at: string;
  batch_id?: string | null;
  batch_number?: string | null;
  product_id?: string | null;
  product_sku?: string | null;
  product_name?: string | null;
  is_cross_product: boolean;
  match_score: number;
  confidence_tier: 'HIGH' | 'MODERATE' | 'LOW';
  matching_attributes: string[];
  matching_reasons: string[];
  attribute_breakdown: MatchingAttribute[];
  has_prior_link: boolean;
  corrective_actions: Array<{
    action_number: string;
    status: string;
    verification_status: string;
    root_cause?: string | null;
    preventive_action?: string | null;
    due_date?: string | null;
  }>;
  reinspections: Array<{
    outcome: string;
    notes?: string | null;
    created_at?: string | null;
  }>;
  resolution_notes?: string | null;
  resolved_at?: string | null;
  citations: Citation[];
}

export interface HistoricalSimilarityResponse {
  analysis_timestamp: string;
  source_defect: {
    id: string;
    defect_number: string;
    category: string;
    severity: string;
    status: string;
    review_decision?: string | null;
    surface_location?: string | null;
    description?: string | null;
    batch_id?: string | null;
    batch_number?: string | null;
    product_sku?: string | null;
    product_name?: string | null;
  };
  total_candidates_evaluated: number;
  matches_found: number;
  algorithm_description: string;
  matches: HistoricalDefectMatch[];
  ai_synthesis?: string | null;
  citations: Citation[];
  limitations: string[];
}

export interface BatchDefectOption {
  id: string;
  defect_number: string;
  category: string;
  severity: string;
  status: string;
  review_decision?: string | null;
  surface_location?: string | null;
  description?: string | null;
  created_at: string;
}

