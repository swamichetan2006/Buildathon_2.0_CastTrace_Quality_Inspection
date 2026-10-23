export type UserRole = 'INSPECTOR' | 'SUPERVISOR' | 'QUALITY_MANAGER' | 'ADMIN';

export interface User {
  id: string;
  username: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: User;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  description?: string | null;
  material?: string | null;
  nominal_dimensions?: string | null;
  drawing_number?: string | null;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

export interface Batch {
  id: string;
  batch_number: string;
  product_id: string;
  product?: Product | null;
  manufacture_date: string;
  heat_number?: string | null;
  declared_quantity: number;
  status: 'PENDING' | 'IN_PRODUCTION' | 'ON_HOLD' | 'RELEASED' | 'SCRAPPED' | 'ARCHIVED';
  notes?: string | null;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

export type InspectionStatus = 'DRAFT' | 'SUBMITTED' | 'IN_REVIEW' | 'COMPLETED' | 'CANCELLED';
export type ItemStatus = 'PENDING' | 'AI_FLAGGED' | 'CONFIRMED_DEFECTIVE' | 'CLEAR' | 'DISPUTED';

export interface InspectionItem {
  id: string;
  inspection_id: string;
  item_identifier: string;
  cavity_number?: number | null;
  status: ItemStatus;
  created_at: string;
  updated_at: string;
  images?: ImageEvidence[];
  reviews?: Review[];
  defects?: Defect[];
}

export interface Inspection {
  id: string;
  inspection_number: string;
  batch_id: string;
  inspector_id: string;
  inspector?: User | null;
  stage: string;
  sampling_plan: string;
  status: InspectionStatus;
  notes?: string | null;
  created_at: string;
  completed_at?: string | null;
  items?: InspectionItem[];
}

export interface ImageEvidence {
  id: string;
  batch_id: string;
  inspection_item_id?: string | null;
  original_filename: string;
  file_size_bytes: number;
  mime_type: string;
  sha256_hash: string;
  image_scope: 'ITEM' | 'SURFACE' | 'BATCH_SAMPLE';
  surface_location?: string | null;
  is_superseded: boolean;
  superseded_by_id?: string | null;
  supersede_reason?: string | null;
  created_at: string;
  model_runs?: ModelRun[];
}

export interface ModelRun {
  id: string;
  logical_run_id: string;
  image_id: string;
  model_version_id?: string | null;
  status: 'QUEUED' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';
  predicted_label?: 'GOOD' | 'DEFECTIVE' | null;
  score?: number | null;
  score_type: string;
  threshold_applied: number;
  routing_outcome?: 'LIKELY_OK' | 'NEEDS_REVIEW' | 'LIKELY_DEFECTIVE' | null;
  routing_reason?: string | null;
  processing_latency_ms?: number | null;
  attempt_number: number;
  error_code?: string | null;
  created_at: string;
}

export type ReviewDecision = 'CONFIRMED_GOOD' | 'CONFIRMED_DEFECTIVE' | 'DISPUTED' | 'REQUEST_ADDITIONAL_EVIDENCE';

export interface Review {
  id: string;
  inspection_id: string;
  inspection_item_id: string;
  model_run_id?: string | null;
  reviewer_id: string;
  reviewer?: User | null;
  decision: ReviewDecision;
  model_disagreement: boolean;
  notes?: string | null;
  ai_snapshot?: Record<string, any> | null;
  created_at: string;
  defects?: Defect[];
}

export type DefectCategory =
  | 'BLOWHOLE'
  | 'SHRINKAGE_POROSITY'
  | 'PINHOLE'
  | 'HOT_TEAR'
  | 'COLD_SHUT'
  | 'CRACK'
  | 'SURFACE_ROUGHNESS'
  | 'INCLUSION'
  | 'OTHER';

export const DEFECT_CATEGORIES: DefectCategory[] = [
  'BLOWHOLE',
  'SHRINKAGE_POROSITY',
  'PINHOLE',
  'HOT_TEAR',
  'COLD_SHUT',
  'CRACK',
  'SURFACE_ROUGHNESS',
  'INCLUSION',
  'OTHER',
];

export type DefectSeverity = 'CRITICAL' | 'MAJOR' | 'MINOR';

export const DEFECT_SEVERITIES: DefectSeverity[] = ['CRITICAL', 'MAJOR', 'MINOR'];

export type DefectStatus =
  | 'OPEN'
  | 'ACTION_ASSIGNED'
  | 'IN_PROGRESS'
  | 'PENDING_REINSPECTION'
  | 'RESOLVED'
  | 'REOPENED';

export interface Defect {
  id: string;
  defect_number: string;
  inspection_item_id: string;
  inspection_item?: InspectionItem | null;
  review_id: string;
  category: DefectCategory;
  severity: DefectSeverity;
  status: DefectStatus;
  surface_location?: string | null;
  description: string;
  evidence_image_id?: string | null;
  evidence_image?: ImageEvidence | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  resolution_notes?: string | null;
  prior_defect_id?: string | null;
  prior_corrective_action_id?: string | null;
  created_at: string;
  updated_at: string;
  corrective_actions?: CorrectiveAction[];
  reinspections?: Reinspection[];
}

export type CAPAStatus = 'OPEN' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
export type VerificationStatus = 'PENDING' | 'VERIFIED' | 'REJECTED';

export interface CorrectiveAction {
  id: string;
  action_number: string;
  defect_id: string;
  defect?: Defect | null;
  title: string;
  action_type: 'REWORK' | 'SCRAP' | 'PROCESS_ADJUSTMENT' | 'TRAINING';
  description: string;
  assigned_to: string;
  assignee?: User | null;
  assigned_by: string;
  status: CAPAStatus;
  verification_status: VerificationStatus;
  due_date: string;
  root_cause?: string | null;
  preventive_action?: string | null;
  completion_notes?: string | null;
  completed_at?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  verification_notes?: string | null;
  evidence_image_id?: string | null;
  created_at: string;
  updated_at: string;
}

export type ReinspectionOutcome = 'DEFECT_RESOLVED' | 'DEFECT_RECURRED_REOPENED';

export interface Reinspection {
  id: string;
  reinspection_number: string;
  defect_id: string;
  corrective_action_id?: string | null;
  inspector_id: string;
  inspector?: User | null;
  outcome: ReinspectionOutcome;
  notes: string;
  evidence_image_id?: string | null;
  created_at: string;
}

export interface ReleaseBlocker {
  code: string;
  category: string;
  message: string;
  entity_type?: string | null;
  entity_id?: string | null;
  details?: Record<string, any> | null;
}

export interface ReleaseGateCounts {
  total_items: number;
  inspected_items: number;
  reviewed_items: number;
  pending_inspection_items: number;
  pending_review_items: number;
  unresolved_defects: number;
  resolved_defects: number;
  defects_requiring_reinspection: number;
  capa_requiring_verification: number;
  capa_verified: number;
  pending_or_failed_reinspections: number;
}

export interface ReleaseGateResponse {
  batch_id: string;
  batch_status: string;
  is_permitted: boolean;
  summary: string;
  blockers: ReleaseBlocker[];
  counts: ReleaseGateCounts;
  evaluated_at: string;
}

export interface DecisionSnapshot {
  decision_id: string;
  batch_id: string;
  batch_number: string;
  decision: string;
  decided_by: string;
  decided_at: string;
  reason: string;
  is_concession: boolean;
  concession_justification?: string | null;
  conditions?: string | null;
  is_permitted: boolean;
  blockers: ReleaseBlocker[];
  counts: ReleaseGateCounts;
  entities: {
    inspection_ids: string[];
    item_ids: string[];
    defect_ids: string[];
    capa_ids: string[];
    reinspection_ids: string[];
  };
}

export interface BatchDecision {
  id: string;
  batch_id: string;
  decision: 'RELEASE' | 'HOLD' | 'REJECT_SCRAP' | 'CONCESSION_DEVIATION';
  reason: string;
  decided_by: string;
  decided_at?: string;
  conditions?: string | null;
  snapshot?: DecisionSnapshot | null;
  created_at: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, any> | null;
    request_id?: string;
  };
}
