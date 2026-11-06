def generate_ai_explanation(ai_result: dict) -> str:
    """
    Generates a human-readable citizen-facing explanation of the AI routing decision.
    """
    category = ai_result.get("category", "General")
    conf = ai_result.get("ai_confidence", 0.0)
    composite = ai_result.get("composite_confidence", 50)
    is_duplicate = ai_result.get("is_duplicate", False)
    
    # Check overrides safely
    lake = ai_result.get("lake") or {}
    if lake.get("violation"):
        return f"KTCP Act Lake buffer encroachment zone violation identified. Flagged as CRITICAL priority and escalated to the Revenue Department."
        
    construction = ai_result.get("construction") or {}
    if construction.get("hazard_detected"):
        permit = construction.get("permit_found")
        if not permit:
            return "Potential illegal excavation site detected without valid municipal permit. Flagged as CRITICAL priority and routed to BBMP Enforcement."
        else:
            return "Licensed excavation site flagged for safety barrier compliance warnings. Assigned to BBMP Safety Wing."

    if is_duplicate:
        return f"A duplicate report was identified within 100m. Marked as duplicate to prevent resource overlapping."

    # Streetlight outages
    sl = ai_result.get("streetlight") or {}
    if sl.get("outage_detected"):
        return "Ambient darkness analysis of night capture indicates a probable streetlight outage. Secondary report generated."

    # Standard routing by confidence
    if composite >= 85:
        return f"High-confidence {category} issue ({composite}% composite score) successfully auto-verified by the model and queued for worker dispatch."
    elif composite >= 60:
        return f"Medium-confidence {category} issue ({composite}% composite score) queued for community verification."
    else:
        return f"Low-confidence capture ({composite}% composite score) routed to admin review for manual validation."
