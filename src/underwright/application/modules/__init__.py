"""Feature modules that group Underwright capabilities by business area."""

from underwright.application.modules.contract_drafting_module import (
    ContractDraftingModule,
)
from underwright.application.modules.contract_payload_builder import (
    ContractPayloadBuilder,
)
from underwright.application.modules.claim_classification_module import (
    ClaimClassificationModule,
)
from underwright.application.modules.claim_confidence_module import ClaimConfidenceModule
from underwright.application.modules.claim_review_screen_builder_module import (
    ClaimReviewScreenBuilderModule,
)
from underwright.application.modules.claim_summary_module import ClaimSummaryModule
from underwright.application.modules.claim_validation_module import ClaimValidationModule
from underwright.application.modules.coverage_assessment_module import (
    CoverageAssessmentModule,
)
from underwright.application.modules.document_consistency_module import (
    DocumentConsistencyModule,
)
from underwright.application.modules.evidence_requirement_module import (
    EvidenceRequirementModule,
)
from underwright.application.modules.policy_rules_module import PolicyRulesModule
from underwright.application.modules.pricing_calculation_module import (
    PricingCalculationModule,
)
from underwright.application.modules.review_screen_builder_module import (
    ReviewScreenBuilderModule,
)
from underwright.application.modules.quote_approval_module import QuoteApprovalModule
from underwright.application.modules.quote_data_completion_module import (
    QuoteDataCompletionModule,
)
from underwright.application.modules.quote_document_generation_module import (
    QuoteDocumentGenerationModule,
)
from underwright.application.modules.quote_payload_builder import QuotePayloadBuilder

__all__ = [
    "ClaimClassificationModule",
    "ClaimConfidenceModule",
    "ClaimReviewScreenBuilderModule",
    "ClaimSummaryModule",
    "ClaimValidationModule",
    "ContractDraftingModule",
    "ContractPayloadBuilder",
    "CoverageAssessmentModule",
    "DocumentConsistencyModule",
    "EvidenceRequirementModule",
    "PolicyRulesModule",
    "PricingCalculationModule",
    "QuoteApprovalModule",
    "QuoteDataCompletionModule",
    "QuoteDocumentGenerationModule",
    "QuotePayloadBuilder",
    "ReviewScreenBuilderModule",
]
