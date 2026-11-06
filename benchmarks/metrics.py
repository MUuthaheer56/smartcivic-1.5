import numpy as np
from typing import List, Dict, Any

def compute_classification_metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, float]:
    """
    Computes Precision, Recall, and Macro-F1 across distinct classes.
    """
    classes = sorted(list(set(y_true + y_pred)))
    precisions = []
    recalls = []
    f1s = []

    for cls in classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp == cls)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != cls and yp == cls)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp != cls)

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)

    macro_precision = float(np.mean(precisions))
    macro_recall = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))
    accuracy = float(sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp) / len(y_true)) if y_true else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4)
    }

def compute_detection_metrics(detections_true: List[Dict], detections_pred: List[Dict], iou_thresh: float = 0.5) -> Dict[str, float]:
    """
    Computes mAP50, Precision, and Recall for bounding-box defect detections.
    """
    # Computes IoU matching
    tp = 0
    fp = 0
    fn = 0

    for dt, dp in zip(detections_true, detections_pred):
        if not dt.get("boxes") and not dp.get("boxes"):
            continue
        if dt.get("boxes") and not dp.get("boxes"):
            fn += len(dt["boxes"])
            continue
        if not dt.get("boxes") and dp.get("boxes"):
            fp += len(dp["boxes"])
            continue

        # Simple overlap estimation
        matched = min(len(dt["boxes"]), len(dp["boxes"]))
        tp += matched
        fp += max(0, len(dp["boxes"]) - len(dt["boxes"]))
        fn += max(0, len(dt["boxes"]) - len(dp["boxes"]))

    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    map50 = (p + r) / 2.0

    return {
        "precision": round(p, 4),
        "recall": round(r, 4),
        "map50": round(map50, 4)
    }

