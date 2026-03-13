from typing import Any

from pydantic import BaseModel, Field

from app.schemas.onboarding import LaunchPackProvisionResponse
from app.schemas.semantic import CertificationStatus, SemanticModelResponse


class MigrationBenchmarkRow(BaseModel):
    kpi_name: str = Field(min_length=1, max_length=255)
    expected_value: float
    dimension_name: str | None = Field(default=None, max_length=255)
    dimension_value: Any = None
    label: str | None = Field(default=None, max_length=255)
    start_date: str | None = Field(default=None, max_length=255)
    end_date: str | None = Field(default=None, max_length=255)


class ImportedKpiDefinition(BaseModel):
    source_name: str = Field(min_length=1, max_length=255)
    label: str | None = Field(default=None, max_length=255)
    formula: str | None = None
    aggregation: str = "sum"
    value_format: str | None = Field(default=None, max_length=64)
    description: str | None = None


class ImportedWorkbookBundle(BaseModel):
    source_tool: str = Field(min_length=2, max_length=50)
    workbook_name: str
    dashboard_names: list[str] = Field(default_factory=list)
    report_names: list[str] = Field(default_factory=list)
    kpi_names: list[str] = Field(default_factory=list)
    dimension_names: list[str] = Field(default_factory=list)
    benchmark_rows: list[MigrationBenchmarkRow] = Field(default_factory=list)
    kpi_definitions: list[ImportedKpiDefinition] = Field(default_factory=list)
    notes: str | None = None


class MigrationAnalysisRequest(BaseModel):
    source_tool: str = Field(min_length=2, max_length=50)
    semantic_model_id: str
    dashboard_names: list[str] = Field(default_factory=list)
    report_names: list[str] = Field(default_factory=list)
    kpi_names: list[str] = Field(default_factory=list)
    dimension_names: list[str] = Field(default_factory=list)
    benchmark_rows: list[MigrationBenchmarkRow] = Field(default_factory=list)
    notes: str | None = None


class MigrationCandidateMatch(BaseModel):
    source_name: str
    target_id: str | None = None
    target_name: str | None = None
    target_label: str | None = None
    target_type: str | None = None
    score: float = Field(ge=0, le=1)
    status: str
    rationale: str


class MigrationOutputSuggestion(BaseModel):
    source_name: str
    recommended_launch_pack_id: str | None = None
    recommended_launch_pack_title: str | None = None
    recommended_dashboard_name: str
    suggested_goal: str
    matched_targets: list[str] = Field(default_factory=list)
    rationale: str


class MigrationCoverage(BaseModel):
    matched_kpis: int
    total_kpis: int
    matched_dimensions: int
    total_dimensions: int
    unmatched_assets: int


class MigrationTrustComparisonRow(BaseModel):
    label: str
    source_name: str
    target_name: str | None = None
    target_label: str | None = None
    dimension_name: str | None = None
    dimension_value: Any = None
    expected_value: float
    governed_value: float | None = None
    variance: float | None = None
    variance_pct: float | None = None
    status: str
    rationale: str


class MigrationTrustComparisonSummary(BaseModel):
    compared_rows: int
    pass_count: int
    review_count: int
    fail_count: int
    pending_count: int


class MigrationTrustComparison(BaseModel):
    rows: list[MigrationTrustComparisonRow] = Field(default_factory=list)
    summary: MigrationTrustComparisonSummary


class MigrationAnalysisResponse(BaseModel):
    source_tool: str
    semantic_model_id: str
    recommended_launch_pack_id: str | None = None
    recommended_launch_pack_title: str | None = None
    primary_asset_title: str
    dashboard_matches: list[MigrationOutputSuggestion]
    report_matches: list[MigrationOutputSuggestion]
    kpi_matches: list[MigrationCandidateMatch]
    dimension_matches: list[MigrationCandidateMatch]
    trust_validation_checks: list[str]
    automated_trust_comparison: MigrationTrustComparison
    bootstrap_goal: str
    coverage: MigrationCoverage


class MigrationBootstrapRequest(MigrationAnalysisRequest):
    dashboard_name_override: str | None = Field(default=None, max_length=255)
    email_to: list[str] = Field(default_factory=list)
    create_schedule: bool = True


class MigrationBootstrapResponse(BaseModel):
    analysis: MigrationAnalysisResponse
    provisioned_pack: LaunchPackProvisionResponse


class MigrationCertificationReviewRequest(BaseModel):
    semantic_model_id: str
    source_tool: str = Field(min_length=2, max_length=50)
    selected_source_names: list[str] = Field(default_factory=list)
    imported_kpis: list[ImportedKpiDefinition] = Field(default_factory=list)
    benchmark_rows: list[MigrationBenchmarkRow] = Field(default_factory=list)
    owner_name: str | None = Field(default=None, max_length=255)
    certification_status: CertificationStatus = "review"
    notes: str | None = None


class MigrationCertificationEvidenceSummary(BaseModel):
    compared_rows: int
    pass_count: int
    review_count: int
    fail_count: int
    pending_count: int


class MigrationCertificationReviewItem(BaseModel):
    source_name: str
    label: str
    target_name: str | None = None
    target_label: str | None = None
    target_type: str | None = None
    match_status: str
    recommended_action: str
    readiness_status: str
    readiness_score: int = Field(ge=0, le=100)
    proposed_owner_name: str | None = None
    proposed_certification_status: CertificationStatus
    suggested_synonyms: list[str] = Field(default_factory=list)
    benchmark_evidence: MigrationCertificationEvidenceSummary
    blockers: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
    certification_note: str | None = None
    lineage_preview: dict[str, Any] = Field(default_factory=dict)


class MigrationCertificationReviewSummary(BaseModel):
    total_items: int
    ready_count: int
    review_count: int
    blocked_count: int
    benchmark_fail_count: int


class MigrationCertificationReviewResponse(BaseModel):
    semantic_model_id: str
    source_tool: str
    requested_owner_name: str | None = None
    requested_certification_status: CertificationStatus
    notes: str | None = None
    summary: MigrationCertificationReviewSummary
    items: list[MigrationCertificationReviewItem] = Field(default_factory=list)


class MigrationPromotionReviewItem(BaseModel):
    source_name: str
    proposed_owner_name: str | None = None
    proposed_certification_status: CertificationStatus = "review"
    suggested_synonyms: list[str] = Field(default_factory=list)
    certification_note: str | None = None
    readiness_status: str | None = None
    blockers: list[str] = Field(default_factory=list)
    lineage_preview: dict[str, Any] = Field(default_factory=dict)


class MigrationPromoteKpisRequest(BaseModel):
    semantic_model_id: str
    source_tool: str = Field(min_length=2, max_length=50)
    selected_source_names: list[str] = Field(default_factory=list)
    imported_kpis: list[ImportedKpiDefinition] = Field(default_factory=list)
    owner_name: str | None = Field(default=None, max_length=255)
    certification_status: CertificationStatus = "review"
    notes: str | None = None
    review_items: list[MigrationPromotionReviewItem] = Field(default_factory=list)


class MigrationPromotionResult(BaseModel):
    source_name: str
    status: str
    target_name: str | None = None
    target_label: str | None = None
    owner_name: str | None = None
    certification_status: CertificationStatus
    rationale: str


class MigrationPromoteKpisResponse(BaseModel):
    semantic_model: SemanticModelResponse
    promoted_count: int
    results: list[MigrationPromotionResult] = Field(default_factory=list)
