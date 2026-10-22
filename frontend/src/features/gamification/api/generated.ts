/** Generated from docs/adaptive-gamified-learning/openapi-pilot-v1.json. Do not edit. */

export interface AcceptedView {
	status: string;
}

export interface ApprovalView {
	content_id?: string | null;
	model_id?: string | null;
	status?: string | null;
	version?: number | null;
	approved?: boolean | null;
	model_version?: string | null;
}

export interface AssignmentRequest {
	experiment_id: string;
	learner_id: string;
	seed: number;
	protocol_hash: string;
}

export interface AssignmentView {
	experiment_id: string;
	learner_id: string;
	arm_key: string;
	decision_mode: string;
	seed: number;
}

export interface BeliefView {
	code: string;
	probability: number;
}

export interface CandidateView {
	action_id: string;
	action_type: string;
	propensity: number;
	predicted_reward: number | null;
	eligible: boolean;
}

export interface ConsentReferenceRequest {
	learner_id: string;
	purpose: "research_export";
	consent_reference: string;
	consent_version: string;
}

export interface ContentApprovalRequest {
	reviewer_id: string;
	decision?: "approve" | "revoke";
}

export interface CreateSessionRequest {
	learner_id: string;
	client_session_id: string;
	language?: string;
}

export interface EventBatchRequest {
	first_sequence_no: number;
	events: TelemetryEvent[];
}

export interface EventBatchResult {
	accepted: number;
	duplicate: number;
	quarantined: number;
	expected_next_sequence: number;
}

export interface ExportRequest {
	learner_id: string;
	purpose: "research_export";
}

export interface ExportView {
	export_id: string;
	learner_id: string;
	purpose: string;
	consent_reference: string;
	status: string;
	records: Record<string, string | boolean>;
}

export interface GameInstanceRequest {
	instance_id: string;
	skill_code: string;
	language: "si";
	prompt_label: string;
	option_labels: string[];
}

export interface GameProgressView {
	learner_id: string;
	session_count: number;
	sessions: SessionSummary[];
	next_cursor: string | null;
}

export interface HTTPValidationError {
	detail?: ValidationError[];
}

export interface IngestRequest {
	text: string;
}

export interface InstanceManifestView {
	instance_id: string;
	language: string;
	skill_code: string;
	prompt_label: string;
	options: ManifestOption[];
	content_version: number;
}

export interface JobView {
	source_id?: string | null;
	job_id?: string | null;
	status: string;
	content_id?: string | null;
	instance_id?: string | null;
	asset_id?: string | null;
	pair_id?: string | null;
	version?: string | number | null;
}

export interface LearnerStepView {
	episode_id: string;
	next_step:
		| "continue"
		| "present_support"
		| "present_verification"
		| "finish"
		| "safe_fallback";
	template_key: string | null;
}

export interface ManifestOption {
	option_id: string;
	text: string;
}

export interface ManifestView {
	item_id: string;
	question_text: string;
	language: string;
	template_key: string;
	options: OptionView[];
}

export interface MetricsView {
	requests: number;
	errors: number;
	latency_p95_ms: number;
	event_accepted: number;
	event_duplicates: number;
	event_quarantined: number;
	fallbacks: number;
	abstentions: number;
	support_failures: number;
	verification_unavailable: number;
	job_failures: number;
	spans: string[];
}

export interface ModelApprovalRequest {
	model_version: string;
	artifact_digest: string;
	decision?: "approve" | "revoke";
}

export interface MonitoringView {
	episodes: number;
	invalid_episode_rate_by_reason: Record<string, number>;
	invalid_episodes: number;
	fallback_rate: number;
	action_coverage_by_arm: Record<string, Record<string, number>>;
	verification_availability: number;
	abstention_rate: number;
	inputs: string;
}

export interface NextActivityRequest {
	skill_id: string;
	device_capabilities?: string[];
}

export interface OptionView {
	option_id: string;
	text: string;
}

export interface ReconstructionView {
	episode_id: string;
	phase: string;
	beliefs: BeliefView[];
	candidates: CandidateView[];
	delivered_scaffold_id: string | null;
	baseline_score: number | null;
	verification_score: number | null;
	independence_gain: number | null;
	validity: string | null;
}

export interface ResponseRequest {
	episode_id: string;
	selected_option_id: string;
	response_time_ms?: number | null;
	visual?: VisualFeatureWindow | null;
}

export interface RewardEntryView {
	episode_id: string;
	points: number;
	reason_code: string;
}

export interface RewardsView {
	learner_id: string;
	balance: number;
	entries: RewardEntryView[];
}

export interface SessionCreated {
	session_id: string;
	learner_id: string;
	status: string;
	language: string;
}

export interface SessionSummary {
	session_id: string;
	status: string;
}

export interface SkillMappingRequest {
	skill_code: string;
	universal_skill_id: string;
	source_id: string;
	mapping_version: string;
}

export interface SkillProgressView {
	learner_id: string;
	skill_code: string;
	unsupported_attempts: number;
	supported_exposures: number;
	independent_accuracy: number | null;
	supported_accuracy: number | null;
	mean_independence_gain: number | null;
}

export interface SourceRequest {
	source_id: string;
	title: string;
	grade: 5;
	language: "si";
	version: string;
}

export interface StepView {
	episode_id: string;
	template_key: string | null;
	next_step:
		| "continue"
		| "present_support"
		| "present_verification"
		| "finish"
		| "safe_fallback";
	manifest: ManifestView | null;
	support: SupportView | null;
}

export interface SupportAssetRequest {
	asset_id: string;
	scaffold_type: string;
	step_count: number;
}

export interface SupportCompleteRequest {
	duration_ms: number;
	step_count: number;
}

export interface SupportContinued {
	episode_id: string;
	next_step: "continue";
}

export interface SupportView {
	scaffold_type: string;
	title: string;
	steps: string[];
	maximum_duration_ms: number;
	maximum_number_of_steps: number;
	diagram?: Record<string, string | number | boolean> | null;
}

export interface TelemetryEvent {
	event_id: string;
	sequence_no: number;
	event_type:
		| "item_presented"
		| "option_selected"
		| "option_changed"
		| "answer_submitted"
		| "support_presented"
		| "support_dismissed"
		| "support_withdrawn"
		| "verification_presented"
		| "verification_submitted";
	event_version: 1;
	client_occurred_at: string;
	payload?: Record<string, string | number | boolean>;
}

export interface ValidationError {
	loc: (string | number)[];
	msg: string;
	type: string;
	input?: unknown;
	ctx?: Record<string, unknown>;
}

export interface VerificationPairRequest {
	pair_id: string;
	baseline_instance_id: string;
	verification_instance_id: string;
}

export interface VisualFeatureWindow {
	mean_eye_openness: number;
	std_eye_openness: number;
	mean_gaze_ratio: number;
	std_gaze_ratio: number;
	mean_pitch: number;
	mean_yaw: number;
	mean_roll: number;
	mean_abs_pitch: number;
	mean_abs_yaw: number;
	mean_abs_roll: number;
	face_visibility_ratio: number;
}
