"""
Radiology Medical Vocabulary Booster & Macros
Contains:
1. Custom initial prompts and medical hotwords for speech recognition engines.
2. Clinical normal macros for rapid expansion (e.g. 'normal liver', 'normal kidneys').
"""

# Common clinical hotwords in Indian Radiology & International Practice
RADIOLOGY_HOTWORDS = [
    "Hepatomegaly",
    "Splenomegaly",
    "Pleural effusion",
    "Parenchyma",
    "Cholelithiasis",
    "Cholecystitis",
    "Hydronephrosis",
    "Hydroureteronephrosis",
    "T1 hyperintense",
    "T2 hyperintense",
    "FLAIR hyperintense",
    "Mediastinum",
    "Pneumothorax",
    "Osteophytes",
    "Spondylolisthesis",
    "Atelectasis",
    "Hemangioma",
    "Calculus",
    "Lymphadenopathy",
    "Contrast enhancement",
    "Basal cisterns",
    "Calvarium",
    "Consolidation",
    "Ground-glass opacities",
    "Infarction",
    "Intracranial haemorrhage",
    "Mass effect",
    "Midline shift",
    "Subdural hematoma",
    "Epidural hematoma",
    "Subarachnoid hemorrhage",
    "Pneumoperitoneum",
    "Ascites",
    "Conus medullaris",
    "Cauda equina",
    "Ligamentum flavum",
    "Facet joint arthropathy",
    "Intervertebral disc extrusion",
    "Radiculopathy",
    "Cardiomegaly",
    "Costophrenic angles",
    "Bronchovascular markings",
    "18F-FDG",
    "SUVmax",
    "Hypermetabolic",
    "Hypometabolic"
]

# Clinical prompt guiding Whisper / Speech engines towards radiology domain
RADIOLOGY_INITIAL_PROMPT = (
    "Radiology medical report dictation with terms: CT, MRI, X-ray, Ultrasound, PET-CT, "
    "hepatomegaly, splenomegaly, pleural effusion, cholelithiasis, hydronephrosis, parenchymal, "
    "T1/T2 FLAIR hyperintense, mediastinum, pneumothorax, osteophytes, spondylolisthesis, "
    "atelectasis, hemangioma, calculus, lymphadenopathy, contrast enhancement, 18F-FDG SUVmax."
)

# Standardized normal clinical macro templates
CLINICAL_MACROS = {
    "normal liver": (
        "Liver is normal in size, shape, and echotexture. No focal solid or cystic lesion is seen. "
        "Intrahepatic biliary radicles (IHBRD) and portal vein are normal."
    ),
    "normal gallbladder": (
        "Gallbladder is well-distended with thin, smooth walls. No intraluminal calculus, sludge, "
        "or wall thickening identified. Common bile duct (CBD) is normal in caliber."
    ),
    "normal kidneys": (
        "Both kidneys are normal in size, shape, and position with preserved corticomedullary differentiation. "
        "No evidence of nephrolithiasis, hydronephrosis, or focal mass lesion."
    ),
    "normal spleen": (
        "Spleen is normal in size and homogeneous in echotexture. No splenomegaly or focal lesion seen."
    ),
    "normal pancreas": (
        "Pancreas is normal in size and parenchymal echogenicity. Main pancreatic duct is not dilated. "
        "No focal peripancreatic fluid collection."
    ),
    "normal urinary bladder": (
        "Urinary bladder is adequately distended with smooth uniform margins. No intraluminal calculus or diverticulum."
    ),
    "normal brain": (
        "Cerebral parenchyma demonstrates preserved grey-white matter differentiation. No acute intracranial "
        "haemorrhage, territorial infarction, or mass effect. Ventricles, sulci, and basal cisterns are age-appropriate."
    ),
    "normal chest": (
        "Both lung fields are clear with normal bronchovascular markings. No focal airspace consolidation, "
        "pleural effusion, or pneumothorax. Cardiothoracic ratio is normal."
    ),
    "normal petct": (
        "Normal physiological FDG distribution in the brain, myocardium, liver, and spleen. "
        "No abnormal hypermetabolic primary lesion, pathological lymphadenopathy, or distant metastases."
    ),
    "normal brain pet": (
        "Physiological symmetrical FDG uptake is noted in the bilateral cerebral and cerebellar cortices, "
        "basal ganglia, and thalami. No focal area of hyper- or hypometabolism is seen."
    ),
    "normal physiological fdg": (
        "Physiological FDG biodistribution is seen in the brain, myocardium, liver, spleen, bowel, and urinary tract."
    ),
    "normal bone scan": (
        "Whole body 99mTc-MDP bone scintigraphy shows normal symmetrical tracer uptake throughout the axial and "
        "appendicular skeleton. No focal osteoblastic lesion is identified. Bilateral kidneys and urinary bladder "
        "show normal physiological excretion."
    ),
    "normal dtpa left": (
        "Left kidney shows normal perfusion, prompt cortical uptake, and unobstructed drainage on post-lasix images."
    ),
    "normal dtpa right": (
        "Right kidney shows normal perfusion, prompt cortical uptake, and unobstructed drainage on post-lasix images."
    ),
    "normal psma": (
        "Physiological PSMA tracer biodistribution noted in salivary glands, lacrimal glands, liver, spleen, "
        "kidneys, and bowel. No abnormal PSMA-avid primary, nodal, or distant skeletal metastasis."
    )
}
