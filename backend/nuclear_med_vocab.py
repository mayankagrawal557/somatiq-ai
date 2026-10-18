"""
Nuclear Medicine, PET-CT & Theranostics Vocabulary Booster
Covers:
- Category 1: PET-CT Scans (Whole Body FDG, PSMA, DOTANOC/DOTATATE, Brain PET, Cardiac PET)
- Category 2: Gamma Camera Scans (Bone Scan 99mTc-MDP, Renal Scans DTPA/EC/DMSA, Thyroid/Parathyroid, Cardiac Perfusion, Lung V/Q, HIDA, Brain SPECT)
- Category 3: Therapeutic Nuclear Medicine & Theranostics (I-131, Lu-177 PSMA, Lu-177 DOTATATE PRRT, Ac-225 PSMA, Bone Pain Palliation, Radiosynovectomy)
"""

from typing import Dict, List, Any

# Extensive Nuclear Medicine & Radiopharmacy Hotwords
NUCLEAR_MED_HOTWORDS = [
    # Isotopes & Radiopharmaceuticals
    "18F-FDG", "Fluorodeoxyglucose", "68Ga-PSMA", "PSMA-11", "18F-PSMA",
    "DOTANOC", "DOTATATE", "68Ga-DOTANOC", "68Ga-DOTATATE", "99mTc-MDP",
    "99mTc-DTPA", "99mTc-EC", "99mTc-DMSA", "99mTc-Sestamibi", "99mTc-MAA",
    "99mTc-Pertechnetate", "99mTc-HIDA", "99mTc-Mebrofenin", "I-131", "Iodine-131",
    "Lu-177", "Lutetium-177", "Lu-177 PSMA", "Lu-177 DOTATATE",
    "Ac-225", "Actinium-225", "Ac-225 PSMA", "Samarium-153", "Strontium-89",
    "Yttrium-90", "Rhenium-186", "Radiosynovectomy", "Theranostics",

    # PET-CT & Scintigraphy Quantitative & Clinical Terms
    "SUVmax", "SUVmean", "SUVpeak", "FDG-avid", "PSMA-avid", "SSTR-avid",
    "Hypermetabolic", "Hypometabolic", "Iso-metabolic", "Physiological uptake",
    "Blood glucose", "Injected activity", "Uptake time", "Deauville score",
    "PERCIST", "RECIST", "Somatostatin receptor", "Neuroendocrine tumor",

    # Bone & Gamma Camera Terms
    "Photopenic defect", "Osteoblastic lesion", "Superscan", "Three-phase bone scan",
    "Angiographic phase", "Blood pool phase", "Delayed mineral phase",
    "Symmetrical tracer uptake", "Axial skeleton", "Appendicular skeleton",

    # Renal & HIDA Scans
    "Split renal function", "Differential renal function", "GFR", "Renogram",
    "T-max", "T-half", "Lasix washout", "Diuretic renography", "Tracer retention",
    "Cortical retention", "Cholecystokinin", "Ejection fraction",
    "Biliary atresia", "Enterogastric reflux", "Common bile duct",

    # Cardiac & Lung Perfusion
    "Myocardial perfusion scintigraphy", "Stress/rest", "Reversible ischemia",
    "Fixed perfusion defect", "Summed stress score", "Summed rest score",
    "LVEF", "TID ratio", "V/Q scan", "Mismatched perfusion defect",

    # Therapy & Dosimetry
    "PRRT", "Targeted alpha therapy", "Beta emitter", "Alpha emitter",
    "Amino acid infusion", "Renal protection", "Dosimetry", "Whole body retention",
    "Radiation safety", "Post-therapy scan", "Biodistribution"
]

NUCLEAR_INITIAL_PROMPT = (
    "Nuclear medicine, PET-CT, and Theranostics report dictation: 18F-FDG, 68Ga-PSMA, "
    "DOTANOC, DOTATATE, 99mTc-MDP, DTPA, EC, DMSA, HIDA, Sestamibi, I-131, Lu-177, Ac-225, "
    "SUVmax, FDG-avid, PSMA-avid, SSTR-avid, hypermetabolic, physiological biodistribution, "
    "photopenic defect, osteoblastic, superscan, Deauville score, split renal function, GFR, "
    "reversible ischemia, theranostics, post-therapy scan."
)

# Modality templates dictionary for all 18 Nuclear Medicine & Theranostics services
NUCLEAR_MED_TEMPLATES: Dict[str, Dict[str, Any]] = {
    # ----------------------------------------------------
    # Category 1: PET-CT Scans
    # ----------------------------------------------------
    "petct_fdg_whole_body": {
        "id": "petct_fdg_whole_body",
        "category": "PET-CT Scan",
        "title": "18F-FDG Whole Body PET-CT Scan",
        "modality": "PET-CT",
        "body_part": "Whole Body (Vertex to Mid-Thigh)",
        "radiopharmaceutical": "18F-Fluorodeoxyglucose (18F-FDG)",
        "technique": "Whole body PET-CT imaging performed from skull vertex to mid-thigh approximately 60 minutes after intravenous injection of 18F-FDG. Low-dose non-contrast CT was acquired for anatomical localization and attenuation correction. Fasting blood glucose level at injection was within acceptable range (<140 mg/dL).",
        "indication_default": "Staging / Response evaluation / Restaging / Suspected recurrence.",
        "comparison_default": "No prior PET-CT study available for baseline comparison.",
        "header_fields": ["Radiopharmaceutical: 18F-FDG", "Injected Dose: ~5-8 mCi (185-296 MBq)", "Uptake Time: 60 mins", "Fasting Blood Sugar: mg/dL", "CT Contrast: Non-contrast / IV Contrast"],
        "sections": ["Head & Neck", "Chest & Mediastinum", "Abdomen & Pelvis", "Musculoskeletal System"],
        "default_findings": [
            "Physiological FDG distribution in the cerebral cortex, myocardium, liver, spleen, bowel, and urinary tract.",
            "Visualized cervical, axillary, and mediastinal lymph nodes show no abnormal hypermetabolism.",
            "Lungs are clear with no hypermetabolic parenchymal nodules or consolidations.",
            "No hypermetabolic focal liver lesions, adrenal masses, or peritoneal nodules.",
            "No abnormal FDG-avid osteolytic or osteoblastic skeletal lesions."
        ],
        "default_impression": "No abnormal FDG-avid primary malignancy, hypermetabolic lymphadenopathy, or distant metastatic disease identified."
    },
    "petct_psma": {
        "id": "petct_psma",
        "category": "PET-CT Scan",
        "title": "68Ga / 18F-PSMA PET-CT Scan",
        "modality": "PET-CT",
        "body_part": "Whole Body (Prostate Protocol)",
        "radiopharmaceutical": "68Ga-PSMA-11 / 18F-PSMA-1007",
        "technique": "PET-CT imaging performed 60 minutes after intravenous injection of PSMA radiotracer from skull base to mid-thigh. Low-dose CT acquired for anatomical localization.",
        "indication_default": "Carcinoma prostate staging / Biochemical recurrence (elevated PSA post-prostatectomy or RT).",
        "comparison_default": "None available.",
        "header_fields": ["Radiopharmaceutical: 68Ga-PSMA-11", "Serum PSA: ng/mL", "Injected Dose: ~2-4 mCi (74-148 MBq)", "Uptake Time: 60 mins"],
        "sections": ["Prostate Bed / Primary", "Pelvic & Retroperitoneal Lymph Nodes", "Distant Metastases & Skeleton"],
        "default_findings": [
            "Physiological PSMA tracer uptake noted in salivary glands, lacrimal glands, liver, spleen, kidneys, and bowel.",
            "Prostate bed demonstrates no focal abnormal PSMA-avid lesion.",
            "No PSMA-avid internal/external iliac, obturator, or retroperitoneal lymphadenopathy.",
            "No PSMA-avid osteoblastic or osteolytic skeletal metastases."
        ],
        "default_impression": "No PSMA-avid local recurrence, regional lymph nodal metastasis, or distant metastatic disease identified."
    },
    "petct_dotanoc": {
        "id": "petct_dotanoc",
        "category": "PET-CT Scan",
        "title": "68Ga-DOTANOC / DOTATATE PET-CT (SSTR)",
        "modality": "PET-CT",
        "body_part": "Whole Body (Neuroendocrine Protocol)",
        "radiopharmaceutical": "68Ga-DOTANOC / 68Ga-DOTATATE",
        "technique": "Whole body PET-CT imaging performed following intravenous injection of 68Ga-DOTANOC/DOTATATE for somatostatin receptor (SSTR) expressing tumors.",
        "indication_default": "Staging / Evaluation of Neuroendocrine Tumour (NET) / Assessment for PRRT eligibility.",
        "comparison_default": "None available.",
        "header_fields": ["Radiopharmaceutical: 68Ga-DOTANOC", "Injected Dose: ~3-5 mCi", "SSTR Target: SSTR2, SSTR5"],
        "sections": ["Primary Tumor Site", "Gastroenteropancreatic (GEP) Axis", "Liver & Peritoneal Cavity", "Lymph Nodes & Skeleton"],
        "default_findings": [
            "Physiological SSTR uptake seen in pituitary gland, thyroid, adrenal glands, liver, spleen, and urinary excretion.",
            "No focal abnormal SSTR-avid lesion in the pancreas or gastrointestinal tract.",
            "No hypermetabolic SSTR-avid hepatic, mesenteric, or retroperitoneal lymph nodes."
        ],
        "default_impression": "No abnormal SSTR-avid primary neuroendocrine tumor, hepatic metastasis, or distant receptor-positive disease identified."
    },
    "petct_brain": {
        "id": "petct_brain",
        "category": "PET-CT Scan",
        "title": "18F-FDG Brain PET-CT (Neuro / Dementia)",
        "modality": "PET-CT",
        "body_part": "Brain",
        "radiopharmaceutical": "18F-FDG (Brain Protocol)",
        "technique": "High-resolution 3D PET imaging of the brain performed 40 minutes post-injection with patient resting quietly in a dimly lit, quiet room with eyes open.",
        "indication_default": "Evaluation of cognitive decline / Suspected Alzheimer's / Frontotemporal dementia / Intractable epilepsy.",
        "comparison_default": "None available.",
        "header_fields": ["Radiopharmaceutical: 18F-FDG", "Dose: ~3-5 mCi", "Injection Conditions: Quiet room, eyes open"],
        "sections": ["Frontal, Parietal, Temporal, Occipital Cortices", "Posterior Cingulate & Precuneus", "Basal Ganglia & Thalami", "Cerebellar Hemispheres"],
        "default_findings": [
            "Symmetrical physiological FDG uptake is noted throughout the bilateral cerebral and cerebellar cortices, basal ganglia, and thalami.",
            "No focal regional hypometabolism identified in the bilateral temporoparietal cortices, posterior cingulate, or precuneus."
        ],
        "default_impression": "Normal Brain FDG PET-CT scan. No evidence of neurodegenerative metabolic pattern or focal epileptic hypometabolism."
    },
    "petct_cardiac": {
        "id": "petct_cardiac",
        "category": "PET-CT Scan",
        "title": "18F-FDG Cardiac PET-CT (Myocardial Viability)",
        "modality": "PET-CT",
        "body_part": "Heart / Myocardium",
        "radiopharmaceutical": "18F-FDG (Glucose Loaded / Hyperinsulinemic Clamp)",
        "technique": "Cardiac gated PET-CT performed after oral glucose loading or hyperinsulinemic-euglycemic clamp to optimize myocardial FDG uptake for viability evaluation.",
        "indication_default": "Assessment of myocardial viability in ischemic cardiomyopathy prior to revascularization.",
        "comparison_default": "SPECT myocardial perfusion scan.",
        "header_fields": ["Radiopharmaceutical: 18F-FDG", "Dose: ~5-10 mCi", "Preparation: Oral glucose loading protocol"],
        "sections": ["Anterior, Septal, Lateral, Inferior Segments", "Apex", "Perfusion-Metabolism Mismatch"],
        "default_findings": [
            "Homogeneous and robust FDG uptake throughout all 17 myocardial segments of the left ventricle.",
            "No segments of perfusion-metabolism mismatch (hibernating myocardium) or match (transmural scar)."
        ],
        "default_impression": "Normal myocardial glucose metabolism. Evidence of viable myocardium throughout the left ventricle."
    },

    # ----------------------------------------------------
    # Category 2: Gamma Camera Scans (SPECT / Scintigraphy)
    # ----------------------------------------------------
    "spect_bone_scan": {
        "id": "spect_bone_scan",
        "category": "Gamma Camera Scan",
        "title": "99mTc-MDP Whole Body Bone Scan (Three-Phase / Planar)",
        "modality": "Gamma Camera / SPECT",
        "body_part": "Whole Skeleton",
        "radiopharmaceutical": "99mTc-Methylene Diphosphonate (99mTc-MDP)",
        "technique": "Whole body anterior and posterior planar scintigraphic images obtained 3 hours post intravenous injection of 99mTc-MDP. Spot views / SPECT-CT acquired as needed.",
        "indication_default": "Skeletal metastases evaluation / Bone pain / Osteomyelitis / Stress fracture / Paget's disease.",
        "comparison_default": "None available.",
        "header_fields": ["Radiopharmaceutical: 99mTc-MDP", "Dose: 20 mCi (740 MBq)", "Delay Time: 3 hours"],
        "sections": ["Axial Skeleton (Spine, Pelvis, Ribs, Sternum)", "Appendicular Skeleton (Extremities)", "Renal & Soft Tissue Excretion"],
        "default_findings": [
            "Whole body 99mTc-MDP bone scintigraphy demonstrates symmetrical, physiological tracer uptake throughout the axial and appendicular skeleton.",
            "No focal osteoblastic or osteolytic skeletal lesion identified to suggest metastasis.",
            "Bilateral kidneys and urinary bladder show normal prompt physiological tracer excretion."
        ],
        "default_impression": "Normal whole body 99mTc-MDP bone scintigraphy. No evidence of osteoblastic skeletal metastasis."
    },
    "spect_renal_dtpa": {
        "id": "spect_renal_dtpa",
        "category": "Gamma Camera Scan",
        "title": "99mTc-DTPA Dynamic Renal Scan (Diuretic Renography)",
        "modality": "Gamma Camera / SPECT",
        "body_part": "Kidneys & Urinary Tract",
        "radiopharmaceutical": "99mTc-Diethylenetriaminepentaacetic acid (99mTc-DTPA)",
        "technique": "Dynamic posterior acquisition initiated simultaneously with intravenous bolus injection of 99mTc-DTPA with hydration protocol. Diuretic (Inj. Furosemide/Lasix 20mg IV) administered as per protocol.",
        "indication_default": "Hydronephrosis / Pelviureteric Junction (PUJ) obstruction / Split renal function / GFR calculation.",
        "comparison_default": "None available.",
        "header_fields": ["Radiopharmaceutical: 99mTc-DTPA", "Dose: 3-5 mCi", "Diuretic Protocol: F+20 Lasix"],
        "sections": ["Perfusion Phase", "Extraction & Cortical Transit", "Excretion Phase & Lasix Response", "Quantitative Split Renal Function & GFR"],
        "default_findings": [
            "Both kidneys show prompt, symmetrical perfusion and rapid peak cortical uptake (T-max within 3-5 mins).",
            "Clearance from bilateral collecting systems is prompt with complete washout following diuretic administration (T-1/2 < 10 mins).",
            "Split Renal Function: Left Kidney = 51%, Right Kidney = 49%. Total GFR is within normal limits."
        ],
        "default_impression": "Normal dynamic renal scintigraphy. Bilateral normal GFR with unobstructed renal drainage."
    },
    "spect_renal_dmsa": {
        "id": "spect_renal_dmsa",
        "category": "Gamma Camera Scan",
        "title": "99mTc-DMSA Static Renal Cortical Scan",
        "modality": "Gamma Camera / SPECT",
        "body_part": "Kidneys (Cortical)",
        "radiopharmaceutical": "99mTc-Dimercaptosuccinic acid (99mTc-DMSA)",
        "technique": "High-resolution static anterior, posterior, and posterior oblique views obtained 2-3 hours following intravenous injection of 99mTc-DMSA.",
        "indication_default": "Evaluation of renal cortical scarring / Pyelonephritis sequelae / Ectopic kidney / Differential cortical function.",
        "comparison_default": "None available.",
        "header_fields": ["Radiopharmaceutical: 99mTc-DMSA", "Dose: 3 mCi", "Acquisition: Static 2-3h post-injection"],
        "sections": ["Right Kidney Morphology & Function", "Left Kidney Morphology & Function", "Differential Cortical Uptake %"],
        "default_findings": [
            "Both kidneys are normal in size, shape, and position with smooth cortical outlines.",
            "Uniform tracer distribution throughout the cortex of both kidneys. No focal photopenic cortical defect or scar.",
            "Differential Cortical Function: Left Kidney = 50%, Right Kidney = 50%."
        ],
        "default_impression": "Normal 99mTc-DMSA cortical scintigraphy. No evidence of renal cortical scarring or focal photopenic defect."
    },
    "spect_thyroid": {
        "id": "spect_thyroid",
        "category": "Gamma Camera Scan",
        "title": "99mTc-Pertechnetate / Sestamibi Thyroid & Parathyroid Scan",
        "modality": "Gamma Camera / SPECT",
        "body_part": "Neck / Thyroid / Parathyroid",
        "radiopharmaceutical": "99mTc-Pertechnetate / 99mTc-Sestamibi",
        "technique": "Anterior neck acquisition using a pinhole collimator 20 minutes post-injection of 99mTc-pertechnetate. Dual-phase imaging at 15m and 2h for parathyroid sestamibi evaluation.",
        "indication_default": "Hyperthyroidism / Thyroid nodule characterization / Primary hyperparathyroidism adenoma localization.",
        "comparison_default": "Serum TSH, Free T3, Free T4 / Serum Calcium & intact PTH levels.",
        "header_fields": ["Radiopharmaceutical: 99mTc-Pertechnetate", "Dose: 3-5 mCi", "Collimator: Pinhole / LEHR"],
        "sections": ["Thyroid Gland Morphology", "Tracer Trapping / Uptake", "Focal Warm/Cold Nodules", "Parathyroid Washout"],
        "default_findings": [
            "Normal symmetrical butterfly configuration of both thyroid lobes with uniform tracer distribution.",
            "Normal salivary-to-thyroid ratio. No focal hyperfunctioning (hot) or non-functioning (cold) nodules.",
            "Delayed sestamibi images show normal rapid thyroid washout with no persistent focal uptake to suggest parathyroid adenoma."
        ],
        "default_impression": "Normal thyroid scintigraphy with homogeneous tracer distribution. No evidence of functioning autonomously hot nodule or parathyroid adenoma."
    },
    "spect_cardiac_perfusion": {
        "id": "spect_cardiac_perfusion",
        "category": "Gamma Camera Scan",
        "title": "Myocardial Perfusion Scintigraphy (Stress & Rest SPECT)",
        "modality": "Gamma Camera / SPECT",
        "body_part": "Heart / Myocardium",
        "radiopharmaceutical": "99mTc-Sestamibi / Tetrofosmin",
        "technique": "Single-day or two-day Stress/Rest ECG-gated SPECT acquisition following treadmill exercise stress or pharmacological stress (Adenosine / Regadenoson / Dobutamine).",
        "indication_default": "Coronary artery disease (CAD) evaluation / Atypical chest pain / Pre-operative cardiac risk assessment.",
        "comparison_default": "Baseline ECG and coronary angiography.",
        "header_fields": ["Radiopharmaceutical: 99mTc-Sestamibi", "Stress Modality: Exercise Treadmill / Pharmacological", "Peak Heart Rate: bpm (% MPR)"],
        "sections": ["Stress Perfusion Images", "Rest Perfusion Images", "Gated SPECT Function (LVEF %, Wall Motion)", "Summed Stress & Rest Scores"],
        "default_findings": [
            "Homogeneous radiotracer uptake throughout all left ventricular myocardial walls on both stress and rest acquisitions.",
            "No evidence of stress-induced reversible ischemia or fixed myocardial perfusion defect.",
            "Gated SPECT reveals normal regional wall motion and thickening. Calculated LVEF is 60%."
        ],
        "default_impression": "Normal myocardial perfusion scintigraphy. No evidence of inducible myocardial ischemia or prior myocardial infarction."
    },
    "spect_lung_vq": {
        "id": "spect_lung_vq",
        "category": "Gamma Camera Scan",
        "title": "Lung Perfusion & Ventilation Scan (V/Q Scan)",
        "modality": "Gamma Camera / SPECT",
        "body_part": "Lungs / Thorax",
        "radiopharmaceutical": "99mTc-Macroaggregated Albumin (99mTc-MAA)",
        "technique": "Perfusion scintigraphy acquired in 6 views (Ant, Post, RPO, LPO, Rt Lat, Lt Lat) following intravenous injection of 99mTc-MAA in supine position.",
        "indication_default": "Suspected acute pulmonary embolism (PE) / Contraindication to CTPA (contrast allergy or renal failure).",
        "comparison_default": "Recent Chest X-Ray.",
        "header_fields": ["Radiopharmaceutical: 99mTc-MAA", "Dose: 3-4 mCi", "Chest X-Ray Correlation: Clear lungs"],
        "sections": ["Right Lung Perfusion", "Left Lung Perfusion", "Segmental/Subsegmental Defects", "Chest Radiograph Match/Mismatch"],
        "default_findings": [
            "Uniform, symmetrical radiotracer distribution throughout all bronchopulmonary segments of both lungs.",
            "No wedge-shaped, segmental, or subsegmental perfusion defects identified."
        ],
        "default_impression": "Normal lung perfusion scintigraphy. Low probability for acute pulmonary embolism (<1%)."
    },
    "spect_hida": {
        "id": "spect_hida",
        "category": "Gamma Camera Scan",
        "title": "Hepatobiliary Scintigraphy (HIDA / Mebrofenin Scan)",
        "modality": "Gamma Camera / SPECT",
        "body_part": "Hepatobiliary System",
        "radiopharmaceutical": "99mTc-Mebrofenin / 99mTc-DISIDA",
        "technique": "Serial dynamic imaging acquired over 60 minutes following IV injection of 99mTc-Mebrofenin under fasting state. Delayed images up to 4 hours as required.",
        "indication_default": "Suspected acute cholecystitis / Biliary dyskinesia / Biliary atresia in neonates / Post-cholecystectomy bile leak.",
        "comparison_default": "Ultrasound abdomen.",
        "header_fields": ["Radiopharmaceutical: 99mTc-Mebrofenin", "Dose: 5 mCi", "Fasting Status: 4-6 hours fasted"],
        "sections": ["Hepatic Clearance Phase", "Gallbladder Visualization", "Biliary Ducts & Bowel Transit", "Gallbladder Ejection Fraction (GBEF)"],
        "default_findings": [
            "Prompt, homogeneous hepatic extraction with normal cardiac blood pool clearance by 5 minutes.",
            "Common bile duct and gallbladder are clearly visualized within 30 minutes of tracer injection.",
            "Prompt, unobstructed biliary excretion into duodenum and proximal small bowel by 45 minutes."
        ],
        "default_impression": "Normal hepatobiliary scintigraphy. Patent cystic duct and common bile duct with prompt transit into bowel. Excludes acute cholecystitis."
    },
    "spect_brain": {
        "id": "spect_brain",
        "category": "Gamma Camera Scan",
        "title": "99mTc-HMPAO / ECD Brain SPECT (Perfusion)",
        "modality": "Gamma Camera / SPECT",
        "body_part": "Brain",
        "radiopharmaceutical": "99mTc-Hexamethylpropyleneamine oxime (99mTc-HMPAO) / 99mTc-ECD",
        "technique": "High-resolution 360-degree Brain SPECT acquisition 45 minutes post-injection with patient resting in quiet, dim-lit environment.",
        "indication_default": "Ictal/Interictal epilepsy focus localization / Cerebrovascular disease reserve / Differential diagnosis of dementia.",
        "comparison_default": "MRI Brain.",
        "header_fields": ["Radiopharmaceutical: 99mTc-HMPAO", "Dose: 20 mCi", "State: Interictal / Resting"],
        "sections": ["Cerebral Cortices (Frontal, Parietal, Temporal, Occipital)", "Basal Ganglia & Thalami", "Cerebellar Perfusion"],
        "default_findings": [
            "Symmetrical, homogeneous cerebral perfusion throughout the bilateral cerebral and cerebellar hemispheres.",
            "No focal area of marked hyperperfusion or hypoperfusion identified."
        ],
        "default_impression": "Normal brain perfusion SPECT study. No focal perfusion asymmetry or regional ischemic deficit."
    },

    # ----------------------------------------------------
    # Category 3: Therapeutic Nuclear Medicine (Theranostics)
    # ----------------------------------------------------
    "thera_radioiodine_i131": {
        "id": "thera_radioiodine_i131",
        "category": "Therapeutic Nuclear Medicine",
        "title": "Radioiodine (I-131) Therapy Administration & Post-Therapy Scintigraphy",
        "modality": "Theranostics",
        "body_part": "Thyroid / Whole Body",
        "radiopharmaceutical": "Sodium Iodide I-131 (Oral Solution / Capsule)",
        "technique": "Oral administration of therapeutic I-131 followed by radiation safety isolation, dosimetry monitoring, and post-therapy whole-body scan (RxWBS) at 5-7 days.",
        "indication_default": "Post-thyroidectomy ablation for differentiated thyroid cancer (DTC) / Toxic hyperthyroidism.",
        "comparison_default": "Pre-therapy diagnostic I-131/Tc-99m scan, serum Thyroglobulin (Tg), and anti-Tg levels.",
        "header_fields": ["Therapeutic Agent: Sodium Iodide I-131", "Administered Activity: mCi (MBq)", "TSH Level: >30 mIU/L (Stimulated)", "Low-Iodine Diet Compliance: Yes (2 weeks)"],
        "sections": ["Clinical History & Treatment Intent", "Administered Dose & Radioprotection Measures", "Post-Therapy Whole Body Scan (RxWBS) Findings", "Radiation Safety & Discharge Instructions"],
        "default_findings": [
            "Patient successfully administered prescribed therapeutic dose of I-131 with no acute adverse reaction.",
            "Post-therapy whole body scintigraphy demonstrates expected focal tracer uptake in thyroid bed remnant.",
            "No abnormal focal iodine-avid cervical lymph nodes, pulmonary metastases, or skeletal metastases."
        ],
        "default_impression": "Successful administration of I-131 therapy. Post-therapy whole body scan reveals thyroid remnant uptake with no distant iodine-avid metastatic disease."
    },
    "thera_lu177_psma": {
        "id": "thera_lu177_psma",
        "category": "Therapeutic Nuclear Medicine",
        "title": "Lutetium-177 (Lu-177) PSMA Therapy & Post-Therapy Scan",
        "modality": "Theranostics",
        "body_part": "Whole Body (Metastatic Prostate Cancer)",
        "radiopharmaceutical": "Lu-177-PSMA-617 / PSMA-I&T",
        "technique": "Intravenous infusion of Lu-177-PSMA administered over 20-30 minutes with hydration, antiemetic prophylaxis, and salivary gland cooling (ice packs). Post-therapy SPECT/CT at 24-48 hours.",
        "indication_default": "Metastatic castration-resistant prostate cancer (mCRPC) progressive on androgen receptor pathway inhibitors and taxane chemotherapy.",
        "comparison_default": "Baseline 68Ga-PSMA PET-CT scan.",
        "header_fields": ["Therapeutic Radiopharmaceutical: Lu-177 PSMA-617", "Administered Activity: 7.4 GBq (200 mCi)", "Cycle Number: Cycle 1 of 4-6", "Pre-therapy Renal Parameters: Serum Creatinine / GFR Normal"],
        "sections": ["Clinical Status & Cycle Info", "Administration Details & Pre-Medications", "Post-Therapy Whole Body Scintigraphy Findings", "Adverse Reactions & Discharge Precautions"],
        "default_findings": [
            "Lu-177 PSMA administered intravenously with pre-hydration and ice-pack salivary gland protection. Procedure tolerated well.",
            "Post-therapy whole body scan reveals intense target radiotracer accumulation in known prostate bed, retroperitoneal nodes, and skeletal lesions concordant with baseline PSMA PET.",
            "Physiological clearance via kidneys into bladder; expected uptake in lacrimal and salivary glands."
        ],
        "default_impression": "Successful administration of Lu-177 PSMA therapy. Post-therapy whole body scintigraphy confirms excellent target lesion uptake."
    },
    "thera_lu177_dotatate": {
        "id": "thera_lu177_dotatate",
        "category": "Therapeutic Nuclear Medicine",
        "title": "Lutetium-177 DOTATATE Peptide Receptor Radionuclide Therapy (PRRT)",
        "modality": "Theranostics",
        "body_part": "Whole Body (Neuroendocrine Tumors)",
        "radiopharmaceutical": "Lu-177-DOTATATE (Lutathera)",
        "technique": "Intravenous infusion of Lu-177 DOTATATE co-administered with dedicated renal protective amino acid solution (Lysine/Arginine 2.5%) infused over 4 hours.",
        "indication_default": "Progressive, unresectable well-differentiated metastatic gastroenteropancreatic neuroendocrine tumor (GEP-NET).",
        "comparison_default": "Baseline 68Ga-DOTANOC / DOTATATE PET-CT.",
        "header_fields": ["Therapeutic Agent: Lu-177 DOTATATE", "Administered Dose: 7.4 GBq (200 mCi)", "Renal Protection: Lysine/Arginine amino acid infusion 4h", "Cycle Number: Cycle 1 of 4"],
        "sections": ["Diagnosis & Pre-requisite Checks", "Infusion & Renal Protection Protocol", "Post-Therapy Whole Body Scan Findings", "Follow-up Advice & Hematologic Monitoring"],
        "default_findings": [
            "Therapy completed uneventfully under renal protective amino acid infusion. No acute nausea or hemodynamic instability.",
            "Post-therapy scan shows high-intensity radiotracer localization in primary neuroendocrine lesions and hepatic metastases concordant with pre-therapy SSTR PET."
        ],
        "default_impression": "Successful administration of Lu-177 DOTATATE PRRT. Post-treatment scintigraphy demonstrates intense tumoricidal radiotracer localization."
    },
    "thera_ac225_psma": {
        "id": "thera_ac225_psma",
        "category": "Therapeutic Nuclear Medicine",
        "title": "Actinium-225 (Ac-225) PSMA Targeted Alpha Therapy (TAT)",
        "modality": "Theranostics",
        "body_part": "Whole Body (Advanced Prostate Cancer)",
        "radiopharmaceutical": "Ac-225-PSMA-617 (Targeted Alpha Emitter)",
        "technique": "Intravenous injection of alpha-emitting Ac-225 PSMA for diffuse skeletal or visceral metastases refractory to beta therapy (Lu-177).",
        "indication_default": "Advanced mCRPC with diffuse bone marrow involvement or resistance to Lu-177 PSMA.",
        "comparison_default": "Post-Lu-177 progression imaging.",
        "header_fields": ["Targeted Alpha Radiopharmaceutical: Ac-225 PSMA-617", "Administered Activity: 100 kBq/kg body weight (~6-8 MBq)", "Salivary Gland Sparing Protocol: Intravenous hydration & cooling"],
        "sections": ["Therapeutic Rationale & Pre-evaluation", "Alpha Therapy Administration Protocol", "Hematologic & Salivary Function Parameters", "Monitoring & Follow-up"],
        "default_findings": [
            "Alpha-emitting Ac-225 PSMA administered as slow intravenous push with pre- and post-hydration.",
            "No immediate adverse reaction noted. Patient instructed on hydration and salivary care."
        ],
        "default_impression": "Successful administration of Ac-225 PSMA targeted alpha therapy. Patient discharged under standard radiation safety protocol."
    },
    "thera_bone_pain_palliation": {
        "id": "thera_bone_pain_palliation",
        "category": "Therapeutic Nuclear Medicine",
        "title": "Bone Pain Palliation Therapy (Samarium-153 / Strontium-89)",
        "modality": "Theranostics",
        "body_part": "Skeleton / Bone Metastases",
        "radiopharmaceutical": "Samarium-153 EDTMP / Strontium-89 Chloride",
        "technique": "Slow intravenous infusion of bone-seeking beta emitter for diffuse painful osteoblastic skeletal metastases.",
        "indication_default": "Intractable bone pain from multifocal osteoblastic metastases (carcinoma prostate / breast) refractory to conventional analgesics.",
        "comparison_default": "99mTc-MDP Bone Scan showing osteoblastic metastases.",
        "header_fields": ["Radiopharmaceutical: Samarium-153 EDTMP", "Administered Dose: 1.0 mCi/kg (37 MBq/kg)", "Baseline Platelets & Hemoglobin: Adequate (>100k/uL)"],
        "sections": ["Pain Score (VAS 1-10) & Clinical History", "Administered Dose & Delivery", "Expected Response Timeline (Flare vs Pain Relief)", "Hematological Surveillance"],
        "default_findings": [
            "Therapeutic radionuclide administered slowly into free-flowing IV line with no extravasation.",
            "Patient counseled on possible transient pain flare in 48-72h followed by analgesic relief over subsequent 2-8 weeks."
        ],
        "default_impression": "Successful administration of bone pain palliation therapy. Advised weekly complete blood counts to monitor transient marrow suppression."
    },
    "thera_radiosynovectomy": {
        "id": "thera_radiosynovectomy",
        "category": "Therapeutic Nuclear Medicine",
        "title": "Radiosynovectomy (Yttrium-90 / Rhenium-186 Local Joint Therapy)",
        "modality": "Theranostics",
        "body_part": "Joint (Knee / Shoulder / Elbow / Ankle)",
        "radiopharmaceutical": "Yttrium-90 Colloid (Knee) / Rhenium-186 (Medium joints)",
        "technique": "Direct intra-articular injection of beta-emitting colloid performed under strict aseptic conditions and fluoroscopic / ultrasound guidance, followed by joint immobilization.",
        "indication_default": "Persistent inflammatory synovitis / Recurrent hemarthrosis in hemophilia / Rheumatoid arthritis refractory to intra-articular steroids.",
        "comparison_default": "Baseline Joint Ultrasound / MRI.",
        "header_fields": ["Radioisotope: Yttrium-90 Colloid", "Target Joint: Right Knee", "Administered Activity: 185 MBq (5 mCi)", "Joint Immobilization: 48 hours splint"],
        "sections": ["Aspiration of Joint Effusion", "Radionuclide Injection Technique", "Immediate Post-Injection Scintigraphy (Leakage Check)", "Joint Splinting & Care"],
        "default_findings": [
            "Diagnostic arthrocentesis performed under sterile precautions. Intra-articular position confirmed.",
            "Radioactive colloid injected cleanly into joint space followed by flushing.",
            "Post-injection planar scan confirms uniform distribution of radioactivity within the synovial space with zero extra-articular leakage or regional lymph node drainage."
        ],
        "default_impression": "Successful radiosynovectomy of the target joint. No extra-articular tracer leakage identified. Joint splinted for 48 hours."
    }
}
