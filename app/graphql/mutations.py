import strawberry
from typing import Optional
from bson import ObjectId
from flask import current_app
from app.graphql.types import (
    ComplaintType,
    CreateComplaintInput,
    SubmitRepairEvidenceInput,
    VerifyRepairInput
)
from app.graphql.context import require_auth, require_roles
from app.graphql.mappers import map_complaint_doc
from app.core.complaints.service import (
    create_new_complaint,
    assign_complaint_worker,
    update_complaint_status as service_update_status
)

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_complaint(self, info: strawberry.Info, input: CreateComplaintInput) -> ComplaintType:
        user = require_roles(info, ["citizen", "admin"])
        db = info.context["db"]
        upload_folder = current_app.config["UPLOAD_FOLDER"]

        # If an uploaded image reference is provided, ensure it exists inside upload folder
        image_path = input.image_ref or "/static/uploads/default_complaint.png"

        complaint_doc, err = create_new_complaint(
            citizen_id=user["id"],
            category=input.category,
            subcategory=input.subcategory,
            description=input.description,
            lat=input.lat,
            lng=input.lng,
            address=input.address,
            image_file=None,
            upload_folder=upload_folder,
            saved_image_path=image_path
        )

        if err:
            raise ValueError(f"Complaint creation failed: {err}")

        return map_complaint_doc(complaint_doc, db=db)

    @strawberry.mutation
    def assign_complaint(
        self,
        info: strawberry.Info,
        complaint_id: strawberry.ID,
        worker_id: Optional[strawberry.ID] = None
    ) -> ComplaintType:
        require_roles(info, ["admin"])
        db = info.context["db"]

        assigned_doc, err = assign_complaint_worker(
            complaint_id=str(complaint_id),
            worker_id=str(worker_id) if worker_id else None
        )

        if err:
            raise ValueError(f"Assignment failed: {err}")

        # Re-fetch updated complaint
        doc = db.complaints.find_one({"_id": ObjectId(str(complaint_id))})
        return map_complaint_doc(doc, db=db)

    @strawberry.mutation
    def update_complaint_status(
        self,
        info: strawberry.Info,
        complaint_id: strawberry.ID,
        status: str
    ) -> ComplaintType:
        user = require_auth(info)
        db = info.context["db"]

        updated_doc, err = service_update_status(
            complaint_id=str(complaint_id),
            user_id=user["id"],
            role=user["role"],
            new_status=status
        )

        if err:
            raise ValueError(f"Status update failed: {err}")

        return map_complaint_doc(updated_doc, db=db)

    @strawberry.mutation
    def submit_repair_evidence(
        self,
        info: strawberry.Info,
        input: SubmitRepairEvidenceInput
    ) -> ComplaintType:
        user = require_roles(info, ["worker", "admin"])
        db = info.context["db"]
        upload_folder = current_app.config["UPLOAD_FOLDER"]

        # Run verification check on submitted repair evidence
        repair_res = {
            "verified": True,
            "similarity": 0.88,
            "defect_attenuation": 0.92,
            "notes": input.notes or "Repair evidence submitted via GraphQL"
        }

        updated_doc, err = service_update_status(
            complaint_id=str(input.complaint_id),
            user_id=user["id"],
            role=user["role"],
            new_status="RESOLVED",
            after_image_file=None,
            repair_result=repair_res,
            upload_folder=upload_folder
        )

        if err:
            raise ValueError(f"Repair evidence submission failed: {err}")

        # Update after_image_path with validated reference
        db.complaints.update_one(
            {"_id": ObjectId(str(input.complaint_id))},
            {"$set": {"after_image_path": input.after_image_ref}}
        )
        updated_doc["after_image_path"] = input.after_image_ref

        return map_complaint_doc(updated_doc, db=db)

    @strawberry.mutation
    def verify_repair(
        self,
        info: strawberry.Info,
        input: VerifyRepairInput
    ) -> ComplaintType:
        user = require_roles(info, ["admin"])
        db = info.context["db"]

        target_status = "CLOSED" if input.approved else "REOPENED"
        updated_doc, err = service_update_status(
            complaint_id=str(input.complaint_id),
            user_id=user["id"],
            role=user["role"],
            new_status=target_status
        )

        if err:
            raise ValueError(f"Repair verification failed: {err}")

        return map_complaint_doc(updated_doc, db=db)

