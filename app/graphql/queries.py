import strawberry
from typing import Optional, List
from bson import ObjectId
from app.graphql.types import (
    ComplaintType,
    AIAnalysisType,
    DuplicateCandidateType,
    DepartmentDashboardType,
    ComplaintFilterInput,
    PaginationInput
)
from app.graphql.context import require_auth
from app.graphql.mappers import map_complaint_doc
from app.core.complaints.service import get_complaint_by_id, get_complaints

@strawberry.type
class Query:
    @strawberry.field
    def complaint(self, info: strawberry.Info, id: strawberry.ID) -> Optional[ComplaintType]:
        user = require_auth(info)
        db = info.context["db"]
        
        try:
            doc = db.complaints.find_one({"_id": ObjectId(str(id))})
        except Exception:
            doc = None
            
        if not doc:
            return None

        # RBAC Check: Citizen can only view complaints if created by them or within their ward
        role = user.get("role")
        uid = str(user.get("id"))
        doc_citizen_id = str(doc.get("citizen_id", ""))
        
        if role == "citizen":
            user_ward = user.get("ward")
            if doc_citizen_id != uid and doc.get("ward") != user_ward:
                raise PermissionError("Access denied: You are not authorized to view this complaint.")
        elif role == "worker":
            # Worker can view complaints assigned to them or open in their ward
            worker_id = str(doc.get("assigned_worker_id", ""))
            user_ward = user.get("ward")
            if worker_id != uid and doc.get("ward") != user_ward:
                raise PermissionError("Access denied: You are not assigned to this complaint.")

        return map_complaint_doc(doc, db=db)

    @strawberry.field
    def complaints(
        self,
        info: strawberry.Info,
        filter: Optional[ComplaintFilterInput] = None,
        pagination: Optional[PaginationInput] = None
    ) -> List[ComplaintType]:
        user = require_auth(info)
        db = info.context["db"]
        
        mongo_filters = {}
        role = user.get("role")
        user_ward = user.get("ward")

        if role == "citizen":
            mongo_filters["ward"] = user_ward or "General"
        elif role == "worker":
            mongo_filters["$or"] = [
                {"assigned_worker_id": ObjectId(user["id"])},
                {"ward": user_ward}
            ]

        if filter:
            if filter.status:
                mongo_filters["status"] = filter.status
            if filter.category:
                mongo_filters["category"] = filter.category
            if filter.priority:
                mongo_filters["priority"] = filter.priority
            if filter.ward and role == "admin":
                mongo_filters["ward"] = filter.ward

        limit = pagination.limit if pagination and pagination.limit else 20
        offset = pagination.offset if pagination and pagination.offset else 0

        cursor = db.complaints.find(mongo_filters).sort("created_at", -1).skip(offset).limit(limit)
        return [map_complaint_doc(d, db=db) for d in cursor]

    @strawberry.field
    def my_complaints(
        self,
        info: strawberry.Info,
        pagination: Optional[PaginationInput] = None
    ) -> List[ComplaintType]:
        user = require_auth(info)
        db = info.context["db"]
        
        limit = pagination.limit if pagination and pagination.limit else 20
        offset = pagination.offset if pagination and pagination.offset else 0

        cursor = db.complaints.find({"citizen_id": ObjectId(user["id"])}).sort("created_at", -1).skip(offset).limit(limit)
        return [map_complaint_doc(d, db=db) for d in cursor]

    @strawberry.field
    def ai_analysis(self, info: strawberry.Info, complaint_id: strawberry.ID) -> Optional[AIAnalysisType]:
        user = require_auth(info)
        db = info.context["db"]
        
        try:
            doc = db.complaints.find_one({"_id": ObjectId(str(complaint_id))})
        except Exception:
            return None
            
        if not doc:
            return None

        complaint = map_complaint_doc(doc, db=db)
        return complaint.ai_analysis

    @strawberry.field
    def duplicate_candidates(self, info: strawberry.Info, complaint_id: strawberry.ID) -> List[DuplicateCandidateType]:
        user = require_auth(info)
        db = info.context["db"]
        
        try:
            doc = db.complaints.find_one({"_id": ObjectId(str(complaint_id))})
        except Exception:
            return []
            
        if not doc:
            return []

        complaint = map_complaint_doc(doc, db=db)
        return complaint.duplicate_candidates

    @strawberry.field
    def department_dashboard(self, info: strawberry.Info, department: Optional[str] = "Roads & Infrastructure") -> DepartmentDashboardType:
        user = require_auth(info)
        db = info.context["db"]
        
        dept_filter = {"assigned_department": department} if department else {}
        total = db.complaints.count_documents(dept_filter)
        pending = db.complaints.count_documents({**dept_filter, "status": {"$in": ["REPORTED", "VERIFIED", "ASSIGNED", "IN_PROGRESS"]}})
        resolved = db.complaints.count_documents({**dept_filter, "status": "RESOLVED"})
        breached = db.complaints.count_documents({**dept_filter, "sla_breached": True})

        breach_rate = round((breached / total * 100.0), 2) if total > 0 else 0.0

        # Average confidence
        pipeline = [
            {"$match": {**dept_filter, "ai_confidence": {"$ne": None}}},
            {"$group": {"_id": None, "avg_conf": {"$avg": "$ai_confidence"}}}
        ]
        conf_res = list(db.complaints.aggregate(pipeline))
        avg_conf = round(float(conf_res[0]["avg_conf"]), 3) if conf_res else 0.85

        return DepartmentDashboardType(
            department=department or "All Departments",
            total_complaints=total,
            pending_complaints=pending,
            resolved_complaints=resolved,
            sla_breach_rate=breach_rate,
            avg_confidence=avg_conf
        )

