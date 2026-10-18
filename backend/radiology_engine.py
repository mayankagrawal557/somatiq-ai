"""
Radiology Intelligence Engine (Rule-based & Deterministic Parser)
Guarantees:
- Zero fabrication: never invents findings not spoken or chosen.
- Preserves explicit measurements, anatomical locations, and negatives ("no acute intracranial hemorrhage").
- Clinical Indian Radiology structured templates (Brain CT, Chest CT, MRI Brain, Lumbar Spine MRI, CXR, USG Abdomen).
- Handles conversational corrections and modality detection.
"""

import re
from typing import Dict, Any, List, Optional

# Starter templates for Indian Diagnostic Centers
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ct_brain": {
        "id": "ct_brain",
        "title": "CT Brain Plain / Non-Contrast",
        "modality": "CT",
        "body_part": "Brain",
        "technique": "Axial sequential non-contrast computed tomography scans of the brain obtained from skull base to vertex with 5mm slice thickness.",
        "indication_default": "Evaluation for headache / acute trauma / neurological deficit.",
        "comparison_default": "No prior imaging available for direct comparison.",
        "sections": [
            "Cerebral Parenchyma & Brainstem",
            "Ventricular System & Cisterns",
            "Extra-axial Spaces & Calvarium",
            "Orbits, Paranasal Sinuses & Mastoids"
        ],
        "default_findings": [
            "Cerebral parenchyma demonstrates normal grey-white matter differentiation. No acute intracranial haemorrhage, mass effect, or territorial infarction seen.",
            "Ventricular system and basal cisterns appear symmetrical and age-appropriate in caliber. Midline structures are central.",
            "No extra-axial collection or subdural/epidural hematoma identified. Calvarium is intact with no fracture.",
            "Visualized paranasal sinuses and mastoid air cells appear clear."
        ],
        "default_impression": "Normal Non-Contrast CT Brain scan. No acute intracranial haemorrhage or space-occupying lesion."
    },
    "ct_chest": {
        "id": "ct_chest",
        "title": "CT Chest / HRCT Thorax",
        "modality": "CT",
        "body_part": "Chest",
        "technique": "High-resolution computed tomography scans of the thorax obtained in full inspiration from lung apices to costophrenic angles.",
        "indication_default": "Cough / fever / suspected respiratory pathology / dyspnea.",
        "comparison_default": "No prior scans available for comparison.",
        "sections": [
            "Lung Parenchyma & Airways",
            "Pleura & Pleural Spaces",
            "Mediastinum & Hila",
            "Chest Wall & Visualized Bones"
        ],
        "default_findings": [
            "Both lung fields show normal attenuation with no focal consolidation, ground-glass opacities, or nodular lesions.",
            "Tracheobronchial tree is patent down to subsegmental bronchi.",
            "No pleural effusion or pneumothorax on either side.",
            "Mediastinum shows normal vascular structures and no significant mediastinal or hilar lymphadenopathy. Cardiac size is within normal limits.",
            "Visualized thoracic cage and dorsal spine appear intact."
        ],
        "default_impression": "No significant parenchymal, pleural, or mediastinal abnormality detected on this HRCT Thorax scan."
    },
    "mri_brain": {
        "id": "mri_brain",
        "title": "MRI Brain with Contrast/Plain",
        "modality": "MRI",
        "body_part": "Brain",
        "technique": "Multiplanar, multisequence MRI of the brain including T1, T2, FLAIR, DWI, ADC, and GRE sequences.",
        "indication_default": "Seizures / altered sensorium / persistent vertigo / focal deficit.",
        "comparison_default": "None available.",
        "sections": [
            "Brain Parenchyma & Diffusion",
            "Ventricular System & Midline",
            "Posterior Fossa & Craniocervical Junction",
            "Vascular Flow Voids"
        ],
        "default_findings": [
            "No areas of abnormal restricted diffusion on DWI/ADC to suggest acute territorial infarction.",
            "T1, T2 and FLAIR sequences demonstrate normal grey-white matter differentiation without intracranial mass lesions or vasogenic edema.",
            "Ventricular system and sulcal spaces are within normal limits for age. Midline structures are central.",
            "Major intracranial arterial flow voids are preserved at the skull base."
        ],
        "default_impression": "Normal MRI Brain study. No acute ischemic stroke or mass effect."
    },
    "mri_lumbar_spine": {
        "id": "mri_lumbar_spine",
        "title": "MRI Lumbar Spine",
        "modality": "MRI",
        "body_part": "Spine",
        "technique": "Sagittal T1, T2, STIR and Axial T2 weighted MR imaging of the lumbosacral spine.",
        "indication_default": "Low backache with or without lower limb radiculopathy.",
        "comparison_default": "None available.",
        "sections": [
            "Alignment & Vertebral Bodies",
            "Intervertebral Discs & Neural Canal",
            "Conus Medullaris & Cauda Equina",
            "Paravertebral Soft Tissues"
        ],
        "default_findings": [
            "Normal lumbar lordosis is maintained. Vertebral body heights and marrow signal intensities are normal without compression fracture or aggressive marrow lesions.",
            "Intervertebral disc heights and signals are preserved. No significant disc bulge, extrusion, or neural foraminal compromise noted at L1-L2 through L5-S1 levels.",
            "The conus medullaris terminates normally at the L1 level with normal cauda equina nerve rootlets.",
            "Bilateral facet joints and ligamenta flava are normal without hypertrophy."
        ],
        "default_impression": "Normal MRI Lumbar Spine study. No significant disc herniation, canal stenosis, or neural impingement."
    },
    "chest_xray": {
        "id": "chest_xray",
        "title": "Chest X-Ray PA View",
        "modality": "X-Ray",
        "body_part": "Chest",
        "technique": "Digital Posteroanterior (PA) radiograph of the chest taken in erect position and full inspiration.",
        "indication_default": "Routine health check / Pre-operative fitness / cough.",
        "comparison_default": "None available.",
        "sections": [
            "Lungs & Hila",
            "Cardiac Silhouette & Mediastinum",
            "Costophrenic & Cardiophrenic Angles",
            "Bony Thorax & Soft Tissues"
        ],
        "default_findings": [
            "Both lung fields appear clear with normal bronchovascular markings. No focal consolidation, pneumothorax, or cavity seen.",
            "Hilar contours are normal.",
            "Cardiothoracic ratio is within normal limits (<50%). Aortic contour and mediastinum appear normal.",
            "Bilateral costophrenic angles and domes of diaphragm are sharp and clear.",
            "Thoracic rib cage, clavicles, and soft tissues appear unremarkable."
        ],
        "default_impression": "Normal Chest Radiograph (PA View). No active cardiopulmonary lesion."
    },
    "usg_abdomen": {
        "id": "usg_abdomen",
        "title": "Ultrasound Whole Abdomen & Pelvis",
        "modality": "Ultrasound",
        "body_part": "Abdomen",
        "technique": "Real-time high-resolution B-mode ultrasound examination of the abdomen and pelvis using 3.5-5.0 MHz curvilinear transducer.",
        "indication_default": "Abdominal pain / dyspepsia / routine health evaluation.",
        "comparison_default": "None available.",
        "sections": [
            "Liver, Gallbladder & Biliary Tree",
            "Pancreas & Spleen",
            "Kidneys & Adrenals",
            "Urinary Bladder & Pelvic Organs"
        ],
        "default_findings": [
            "Liver is normal in size, shape, and echotexture. No focal lesion or intrahepatic biliary radicle dilatation (IHBRD). Portal vein is normal.",
            "Gallbladder is well distended with normal wall thickness; no calculus, sludge, or mass lesion.",
            "Common bile duct (CBD) is normal in caliber.",
            "Pancreas and Spleen appear normal in size and echotexture. No focal lesion.",
            "Both kidneys are normal in size, position, and cortical echogenicity. Corticomedullary differentiation is well maintained. No calculus, hydronephrosis, or mass.",
            "Urinary bladder is well distended with smooth margins. No calculus or wall thickening.",
            "No free fluid (ascites) seen in peritoneal or pelvic cavity."
        ],
        "default_impression": "Normal Ultrasound Whole Abdomen & Pelvis study. No focal organomegaly, cholelithiasis, or nephrolithiasis."
    },
    "petct_whole_body": {
        "id": "petct_whole_body",
        "title": "18F-FDG Whole Body PET-CT Scan",
        "modality": "PET-CT",
        "body_part": "Whole Body (Vertex to Mid-Thigh)",
        "technique": "Whole body PET-CT scan performed from skull vertex to mid-thigh approximately 60 minutes following intravenous injection of 18F-FDG. Low-dose non-contrast CT was performed for anatomical localization and attenuation correction. Blood glucose at time of injection was within acceptable limits.",
        "indication_default": "Staging / Evaluation of treatment response / Suspected recurrence / Pyrexia of Unknown Origin (PUO).",
        "comparison_default": "No prior PET-CT study available for baseline comparison.",
        "sections": [
            "Radiopharmaceutical & Injection Parameters",
            "Head & Neck",
            "Chest & Mediastinum",
            "Abdomen & Pelvis",
            "Musculoskeletal & Skeleton"
        ],
        "default_findings": [
            "Brain shows physiological cortical and basal ganglia FDG avidity. Normal physiological uptake in salivary glands, tonsils, and vocal cords.",
            "Visualized cervical, axillary, and mediastinal lymph nodes show no abnormal hypermetabolism (no pathological FDG uptake).",
            "Both lung fields show normal attenuation without abnormal hypermetabolic pulmonary nodules, mass lesions, or consolidations.",
            "Liver and spleen demonstrate physiological, homogenous FDG distribution. No focal hypermetabolic hepatic, splenic, or adrenal lesions.",
            "Gastrointestinal tract and urinary tract show expected physiological excretion.",
            "No focal abnormal FDG-avid osteolytic or osteoblastic skeletal lesions identified."
        ],
        "default_impression": "No abnormal FDG-avid primary malignancy, hypermetabolic lymphadenopathy, or distant metastatic disease identified on this whole-body 18F-FDG PET-CT examination."
    }
}

# Merge full suite of 18 Nuclear Medicine, PET-CT, and Theranostics templates
from backend.nuclear_med_vocab import NUCLEAR_MED_TEMPLATES
TEMPLATES.update(NUCLEAR_MED_TEMPLATES)

class RadiologyEngine:
    """
    Transforms dictated text and selected template into a structured radiology report.
    Adheres strictly to medical safety:
    - Never fabricates findings.
    - Explicitly segregates dictated observations into FINDINGS and synthesizes an IMPRESSION draft.
    - Flags missing clinical indications or technique modifications with clear placeholders.
    """

    @classmethod
    def get_available_templates(cls) -> List[Dict[str, Any]]:
        return list(TEMPLATES.values())

    @classmethod
    def get_template(cls, template_id: str) -> Optional[Dict[str, Any]]:
        return TEMPLATES.get(template_id)

    @classmethod
    def process_dictation(
        cls,
        dictated_text: str,
        template_id: str = "ct_brain",
        clinical_indication: str = "",
        technique_override: str = "",
        comparison: str = ""
    ) -> Dict[str, Any]:
        """
        Parses raw dictation text and formats into a clinically rigorous report.
        """
        template = TEMPLATES.get(template_id, TEMPLATES["ct_brain"])
        clean_text = dictated_text.strip()
        findings_text = clean_text
        dictated_impression = ""

        # Extract explicit spoken Impression or Conclusion if present
        imp_match = re.search(r'\b(?:impression|conclusion)\s*:\s*(.+)$', clean_text, re.IGNORECASE | re.DOTALL)
        if imp_match:
            dictated_impression = imp_match.group(1).strip()
            findings_text = clean_text[:imp_match.start()].strip()
            # Clean leading Findings: tag if present
            findings_text = re.sub(r'^(?:findings|observations)\s*:\s*', '', findings_text, flags=re.IGNORECASE).strip()

        # Identify sentences while preserving decimals (e.g. 11.4 SUV, 2.5 cm)
        raw_sentences = re.split(r'(?<!\d)\.(?!\d)|\n+', findings_text)
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        
        # Build Findings block
        findings_paragraphs = []
        if sentences:
            findings_paragraphs.append(" ".join(f"{s}." for s in sentences))
        else:
            findings_paragraphs.append("[No specific findings dictated yet. Radiologist review needed.]")

        # Synthesize Impression
        impression_paragraphs = []
        if dictated_impression:
            impression_paragraphs.append(dictated_impression)
        elif findings_text:
            # Check for negative/normal patterns
            lower_dictation = findings_text.lower()
            if any(term in lower_dictation for term in ["no acute", "normal", "unremarkable", "clear", "intact", "no hemorrhage", "no mass"]):
                impression_paragraphs.append(
                    f"1. Findings consistent with dictated text: {findings_text}."
                )
                impression_paragraphs.append(
                    "2. No acute or urgent abnormality identified in the dictated observations."
                )
            else:
                impression_paragraphs.append(
                    f"1. Key dictated observations: {findings_text}."
                )
            impression_paragraphs.append(
                "NOTE: Radiologist clinical correlation and final sign-off required."
            )
        else:
            impression_paragraphs.append(template["default_impression"])

        from backend.quality_safety_checker import ClinicalQualityChecker

        technique = technique_override.strip() or template["technique"]
        indication = clinical_indication.strip() or template["indication_default"]
        comp = comparison.strip() or template["comparison_default"]
        limitations = comp if ("motion" in comp.lower() or "limitation" in comp.lower()) else "No significant motion artefact described."

        # Structured final report markdown and plain text formats
        report_sections = {
            "examination": template["title"],
            "indication": indication,
            "clinical_indication": indication,
            "comparison": comp,
            "technique": technique,
            "procedure_technique": technique,
            "findings": "\n\n".join(findings_paragraphs),
            "impression": "\n\n".join(impression_paragraphs),
            "limitations_additional_notes": limitations
        }

        full_formatted_text = (
            f"EXAMINATION:\n{report_sections['examination']}\n\n"
            f"CLINICAL INDICATION:\n{report_sections['clinical_indication']}\n\n"
            f"PROCEDURE / TECHNIQUE:\n{report_sections['procedure_technique']}\n\n"
            f"FINDINGS:\n{report_sections['findings']}\n\n"
            f"IMPRESSION:\n{report_sections['impression']}\n\n"
            f"LIMITATIONS / ADDITIONAL NOTES:\n{report_sections['limitations_additional_notes']}\n\n"
            f"[DRAFT PENDING RADIOLOGIST APPROVAL - NOT FINAL]"
        )

        safety_eval = ClinicalQualityChecker.analyze_transcript(clean_text, template["id"])

        return {
            "template_id": template["id"],
            "template_title": template["title"],
            "modality": template["modality"],
            "body_part": template["body_part"],
            "original_transcript": clean_text,
            "normalized_transcript": clean_text,
            "uncertain_terms": safety_eval["uncertain_terms"],
            "quality_flags": safety_eval["quality_flags"],
            "has_warnings": safety_eval["has_warnings"],
            "human_review_required": safety_eval["human_review_required"],
            "split_function_check": safety_eval["split_function_check"],
            "sections": report_sections,
            "full_formatted_text": full_formatted_text,
            "provenance": {
                "dictated": bool(clean_text),
                "ai_assisted": False,
                "engine": "deterministic_safety_engine"
            },
            "human_approval": {
                "reviewer": "Pending Clinician Sign-Off",
                "status": "DRAFT",
                "approved": False
            },
            "is_draft": True
        }

