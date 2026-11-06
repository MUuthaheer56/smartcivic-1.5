from typing import Optional, List, Dict, Any
import datetime
from bson import ObjectId
from app.graphql.types import (
    ComplaintType,
    LocationType,
    SLAType,
    AIAnalysisType,
    TimelineEventType,
    DuplicateCandidateType
)

def format_iso(dt_val) -> Optional[str]:
    if isinstance(dt_val, datetime.datetime):
        return dt_val.isoformat()
    return str(dt_val) if dt_val else None

def map_complaint_doc(doc: Dict[str, Any], db=None) -> ComplaintType:
    if not doc:
        return None

    cid = str(doc["_id"])
    loc_data = doc.get("location") or {}
    location = LocationType(
        lat=float(loc_data.get("lat", 0.0)),
        lng=float(loc_data.get("lng", 0.0)),
        address=loc_data.get("address", "Bengaluru"),
        ward=doc.get("ward")
    )

    sla = SLAType(
        sla_hours=int(doc.get("sla_hours", 72)),
        deadline=format_iso(doc.get("sla_deadline")),
        is_breached=bool(doc.get("sla_breached", False))
    )

    # Compile AI Analysis
    ai_analysis = None
    if doc.get("ai_confidence") is not None or doc.get("routing_status") is not None:
        ai_analysis = AIAnalysisType(
            predicted_category=doc.get("category"),
            ai_confidence=float(doc.get("ai_confidence", 0.0)) if doc.get("ai_confidence") is not None else None,
            composite_confidence=int(doc.get("composite_confidence", 0)) if doc.get("composite_confidence") is not None else None,
            severity_score=float(doc.get("severity_score", 0.0)) if doc.get("severity_score") is not None else None,
            severity_level=doc.get("severity_level"),
            routing_status=doc.get("routing_status"),
            explanation=doc.get("explanation") or doc.get("ai_explanation"),
            model_name="yolov8n-multimodal-smartcivic",
            model_version="1.6.0"
        )

    # Compile Timeline Events
    timeline_events: List[TimelineEventType] = []
    events_raw = doc.get("timeline_events") or []
    for ev in events_raw:
        timeline_events.append(
            TimelineEventType(
                event_type=ev.get("event_type", "UPDATE"),
                timestamp=format_iso(ev.get("timestamp")),
                actor_role=ev.get("actor_role"),
                from_status=ev.get("from_status"),
                to_status=ev.get("to_status"),
                detail=str(ev.get("detail", "")) if ev.get("detail") else None
            )
        )

    # Compile Duplicate Candidates
    dup_candidates: List[DuplicateCandidateType] = []
    if doc.get("is_duplicate") and doc.get("duplicate_of"):
        dup_candidates.append(
            DuplicateCandidateType(
                complaint_id=str(doc.get("duplicate_of")),
                distance_meters=0.0,
                category=doc.get("category", "Unknown"),
                similarity_score=float(doc.get("image_similarity", 1.0)) if doc.get("image_similarity") is not None else None
            )
        )

    category = doc.get("category", "General")
    subcategory = doc.get("subcategory") or ""
    title = f"{category}: {subcategory}" if subcategory else category

    return ComplaintType(
        id=cid,
        title=title,
        category=category,
        subcategory=subcategory,
        description=doc.get("description", ""),
        status=doc.get("status", "REPORTED"),
        priority=doc.get("priority", "MEDIUM"),
        ward=doc.get("ward", "General"),
        location=location,
        sla=sla,
        ai_analysis=ai_analysis,
        timeline=timeline_events,
        duplicate_candidates=dup_candidates,
        image_path=doc.get("image_path"),
        before_image_path=doc.get("before_image_path") or doc.get("image_path"),
        after_image_path=doc.get("after_image_path"),
        created_at=format_iso(doc.get("created_at")) or datetime.datetime.utcnow().isoformat(),
        updated_at=format_iso(doc.get("updated_at")) or datetime.datetime.utcnow().isoformat()
    )

