import strawberry
from typing import Optional, List
import datetime

@strawberry.type
class LocationType:
    lat: float
    lng: float
    address: str
    ward: Optional[str] = None

@strawberry.type
class SLAType:
    sla_hours: int
    deadline: Optional[str]
    is_breached: bool

@strawberry.type
class AIAnalysisType:
    predicted_category: Optional[str] = None
    ai_confidence: Optional[float] = None
    composite_confidence: Optional[int] = None
    severity_score: Optional[float] = None
    severity_level: Optional[str] = None
    routing_status: Optional[str] = None
    explanation: Optional[str] = None
    model_name: Optional[str] = "smartcivic-multimodal-v1"
    model_version: Optional[str] = "1.0.0"

@strawberry.type
class TimelineEventType:
    event_type: str
    timestamp: str
    actor_role: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    detail: Optional[str] = None

@strawberry.type
class DuplicateCandidateType:
    complaint_id: strawberry.ID
    distance_meters: float
    category: str
    similarity_score: Optional[float] = None

@strawberry.type
class ComplaintType:
    id: strawberry.ID
    title: str
    category: str
    subcategory: Optional[str]
    description: str
    status: str
    priority: str
    ward: str
    location: LocationType
    sla: SLAType
    ai_analysis: Optional[AIAnalysisType]
    timeline: List[TimelineEventType]
    duplicate_candidates: List[DuplicateCandidateType]
    image_path: Optional[str] = None
    before_image_path: Optional[str] = None
    after_image_path: Optional[str] = None
    created_at: str
    updated_at: str

@strawberry.type
class DepartmentDashboardType:
    department: str
    total_complaints: int
    pending_complaints: int
    resolved_complaints: int
    sla_breach_rate: float
    avg_confidence: float

@strawberry.input
class ComplaintFilterInput:
    status: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    ward: Optional[str] = None

@strawberry.input
class PaginationInput:
    limit: Optional[int] = 20
    offset: Optional[int] = 0

@strawberry.input
class CreateComplaintInput:
    category: str
    subcategory: str
    description: str
    lat: float
    lng: float
    address: str
    image_ref: Optional[str] = None

@strawberry.input
class SubmitRepairEvidenceInput:
    complaint_id: strawberry.ID
    after_image_ref: str
    notes: Optional[str] = None

@strawberry.input
class VerifyRepairInput:
    complaint_id: strawberry.ID
    approved: bool
    rejection_reason: Optional[str] = None

