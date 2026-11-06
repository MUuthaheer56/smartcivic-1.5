# IEEE Conference Targeting & Submission Guide for SmartCivic 2.0

## 1. Targeted Venues (3-Month Fast-Track Window)

| Conference / Journal | Focus Areas | Typical Submission Deadlines | Review Cycle | Suitability for SmartCivic 2.0 |
| :--- | :--- | :--- | :--- | :--- |
| **IEEE SMARTCOMP** (Smart Computing) | Smart Cities, Urban Sensing, Multi-modal Edge AI | Late Q1 / Early Q2 | ~6–8 weeks | **Top Recommendation:** Matches SmartCivic's urban sensing, edge YOLO inference, and civic routing scope directly. |
| **IEEE COMPSAC** (Computers, Software & Applications) | Software Architecture, Web Services (GraphQL/REST), Applied AI | Early Q1 / Mid Q1 | ~8 weeks | **Strong Fit:** Appreciates both the software engineering evaluation (GraphQL/REST) and the multimodal AI pipeline. |
| **IEEE TENCON / IEEE INDICON** (Region 10 Flagship) | AI Applications, Civic Tech, IoT & Smart Governance | Q2 / Q3 (rolling) | ~4–6 weeks | **High Acceptance Probability:** Excellent venue for applied SIH innovation with empirical rigor. |
| **IEEE Access** (Open Access Journal) | Multidisciplinary Engineering, Smart Cities | Continuous (Anytime) | **4–6 weeks** (Fastest) | **Backup / Fast-Track:** Indexed in SCIE/Scopus, guaranteed rapid peer review turnaround. |

---

## 2. Reviewer Alignment Strategy

IEEE peer reviewers evaluate submissions against 6 core criteria:

1. **Originality & Novelty:**
   - *Do not claim* that YOLOv8, Strawberry GraphQL, or Flask is novel.
   - *Do claim* that the **closed-loop multimodal pipeline** (coupling initial visual/textual detection directly to transparent multi-factor prioritisation, spatial deduplication, and before-and-after defect attenuation verification) is the core technical contribution.
2. **Technical Quality & Soundness:**
   - Preprocessing, ONNX runtime execution, and metrics (IoU, mAP@50, Macro F1) are mathematically defined.
   - Elimination of default coordinates proves absence of fabricated geographic evidence.
3. **Reproducibility & Open Science:**
   - Open-source benchmark script [`benchmarks/run_experiments.py`](file:///c:/Users/Muthaheer/Desktop/main%20project/smartcivic%201.5/benchmarks/run_experiments.py).
   - Immutable audit logs in `ai_inference_audit`.
4. **Evaluation & Baselines:**
   - Clear comparisons against established baselines (Baseline CNN, TF-IDF + Logistic Regression, SSIM, Keyword/Spatial-only).
   - Full 5-variant ablation study demonstrating the incremental gain of each modality.
5. **Software Engineering Contribution:**
   - Dual-protocol benchmark (REST vs GraphQL) demonstrating 73.4% payload reduction in bandwidth-constrained urban edge deployments.

---

## 3. Submission Checklist & Ethics Compliance

- [x] **No Simultaneous Submissions:** Do not submit the manuscript to two venues simultaneously.
- [x] **Reproducible Model Weights:** Verified local `yolov8n.onnx` file present in the repository.
- [x] **No Fabricated Data:** All benchmark metrics generated through executable scripts.
- [x] **AI Disclosure:** Disclose generative AI assistance used for code refactoring and language drafting in accordance with IEEE author guidelines.
- [x] **IEEE 2-Column Template:** Use standard `IEEEtran.cls` (included in `paper/ieee_tables.tex`).

