"""
Radiology Medical Vocabulary Booster & Macros
Contains:
1. Custom initial prompts and medical hotwords for speech recognition engines.
2. Clinical normal macros for rapid expansion (e.g. 'normal liver', 'normal kidneys').
"""

# Common clinical hotwords in Indian Radiology & International Practice (250+ High-Precision Terms)
RADIOLOGY_HOTWORDS = [
    # 1. Ultrasound Whole Abdomen & Pelvis (USG)
    "Cholelithiasis", "Choledocholithiasis", "Hepatomegaly", "Splenomegaly", "Hepatosplenomegaly",
    "Hydronephrosis", "Hydroureteronephrosis", "Nephrolithiasis", "Cortical echogenicity",
    "Corticomedullary differentiation", "Mesenteric lymphadenopathy", "Bulky anteverted uterus",
    "Anteverted", "Retroverted", "Anteverted uterus", "Retroverted uterus", "Endometrial thickness", "Polycystic ovaries",
    "Follicular cyst", "Hemorrhagic cyst", "Tubo-ovarian mass", "Adenomyosis",
    "Intramural leiomyoma", "Subserosal fibroid", "Acoustic shadowing", "Posterior acoustic enhancement",
    "Comet-tail artifact", "Gallbladder sludge", "Sonographic Murphy's sign", "Common bile duct",
    "Portal vein", "Intrahepatic biliary radicles", "Fatty infiltration", "Hepatic steatosis",
    "Focal nodular hyperplasia", "Simple hepatic cyst", "Biliary cystadenoma", "Renal angiomyolipoma",
    "Medullary nephrocalcinosis", "Cystitis", "Urinary bladder diverticulum", "Prostatic enlargement",
    "Median lobe hypertrophy", "Seminal vesicles", "Psoas abscess", "Intussusception",
    "Appendicular lump", "Periappendiceal fluid", "Target sign", "Pseudokidney sign",
    "Morison's pouch", "Pouch of Douglas", "Free fluid in pelvis", "Anechoic",
    "Hypoechoic", "Hyperechoic", "Isoechoic", "Parenchyma", "Pelvicalyceal system",
    "Calculus in neck", "Calculus in fundus", "Gallbladder wall thickening", "Cholecystitis",
    "Choledochal cyst", "Contracted gallbladder", "Renal parenchymal disease", "Perirenal fluid",
    "Bile duct dilatation", "Hydrosalpinx", "Corpus luteum cyst", "Pelvic congestion",

    # 2. CT & MRI Neuro & Head-Neck
    "Intraparenchymal hemorrhage", "Hyperdense MCA sign", "Basal cisterns", "Midline shift",
    "Subarachnoid hemorrhage", "Subdural hematoma", "Epidural hematoma", "Intraventricular hemorrhage",
    "Hemorrhagic contusion", "Diffuse axonal injury", "Cytotoxic edema", "Vasogenic edema",
    "Grey-white matter differentiation", "Insular ribbon sign", "Sulcal effacement", "Ventricular compression",
    "Hydrocephalus", "Periventricular ooze", "Cavernoma", "Arteriovenous malformation",
    "Developmental venous anomaly", "Berry aneurysm", "Internal capsule", "Thalamus",
    "Lentiform nucleus", "Corona radiata", "Centrum semiovale", "Cerebellopontine angle",
    "Acoustic schwannoma", "Meningioma", "Pituitary macroadenoma", "Sella turcica",
    "Suprasellar extension", "Optic chiasm compression", "Calvarium", "Territorial infarction",
    "Lacunar infarct", "Ischemic penumbra", "Perfusion mismatch", "Major flow voids",
    "Craniocervical junction", "Meningeal enhancement", "Gliosis", "Microvascular ischemia",
    "Leukoaraiosis", "Encephalomalacia", "Pachymeningeal thickening", "Cerebellar tonsillar ectopia",

    # 3. CT & MRI Spine & Musculoskeletal
    "Intervertebral disc extrusion", "Disc protrusion", "Disc bulge", "Thecal sac indentation",
    "Thecal sac compression", "Neural foraminal narrowing", "Spinal canal stenosis", "Ligamentum flavum hypertrophy",
    "Facet joint arthropathy", "Spondylolisthesis", "Pars interarticularis defect",
    "Spondylolysis", "Schmorl's node", "Modic endplate changes", "Vertebral hemangioma",
    "Osteophytes", "Syndesmophytes", "Sacroiliitis", "Cord compression", "Cervical myelopathy",
    "Myelomalacia", "Conus medullaris", "Cauda equina", "Syringomyelia", "Chiari malformation",
    "Radiculopathy", "Facet hypertrophy", "Posterior longitudinal ligament", "Bilateral pars defect",
    "Disc space narrowing", "Endplate sclerosis", "Anterior listhesis", "Retrolisthesis",

    # 4. Chest, Thorax & Body (CT / HRCT / X-Ray)
    "Ground-glass opacities", "Consolidation", "Pleural effusion", "Pneumothorax",
    "Atelectasis", "Bronchiectasis", "Tree-in-bud sign", "Interlobular septal thickening",
    "Cavitation", "Centrilobular emphysema", "Panacinar emphysema", "Pneumomediastinum",
    "Pericardial effusion", "Cardiomegaly", "Aortic dissection", "Pulmonary thromboembolism",
    "Filling defect", "Hilar lymphadenopathy", "Subcarinal lymph node", "Paratracheal lymphadenopathy",
    "Pneumoperitoneum", "Peritoneal fluid", "Bowel wall thickening", "Mesenteric ischemia",
    "Cardiothoracic ratio", "Costophrenic angles", "Bronchovascular markings", "Apical fibrobullous",
    "Empyema", "Traction bronchiectasis", "Mosaic attenuation", "Honeycombing",

    # 5. Nuclear Medicine, PET-CT & Theranostics
    "Hypermetabolic FDG avidity", "Intense tracer avidity", "Physiological biodistribution",
    "SUVmax", "SUVmean", "SUVpeak", "Liver background", "Mediastinal blood pool",
    "Deauville criteria", "Deauville 5-PS", "Deauville score", "Lugano classification",
    "PERCIST", "Metabolic tumor volume", "Total lesion glycolysis", "Mediastinal lymph nodes",
    "Subcarinal lymphadenopathy", "Paratracheal nodes", "Supraclavicular lymph node",
    "Hilar adenopathy", "Retroperitoneal lymphadenopathy", "Mesenteric deposits",
    "Omental caking", "Peritoneal carcinomatosis", "Osteolytic lesion", "Osteosclerotic lesion",
    "Mixed blastic and lytic", "Tracer excretion", "Physiological urinary excretion",
    "Brown fat uptake", "Myocardial tracer uptake", "Myocardial perfusion imaging",
    "Split renal function", "GFR", "Renogram", "Cortical transit time", "18F-FDG",
    "68Ga-PSMA", "18F-PSMA", "68Ga-DOTATATE", "68Ga-DOTANOC", "68Ga-DOTATOC",
    "177Lu-PSMA", "177Lu-DOTATATE", "225Ac-PSMA", "99mTc-MDP", "99mTc-DTPA",
    "99mTc-DMSA", "99mTc-HIDA", "99mTc-Sestamibi", "Radioiodine I-131", "Thyroid uptake",
    "Radioiodine refractory", "Somatostatin receptor avidity", "Photopenic defect",
    "Osteoblastic metastasis", "Superscan", "Gated SPECT", "Ejection fraction",
    "Ventilation-perfusion match", "Mismatch defect", "Extravasation",

    # 6. Additional Diagnostic & Characteristic Signs
    "Hyperdense", "Hypodense", "Isodense", "Hyperintense", "Hypointense", "Isointense",
    "Restricted diffusion", "ADC map", "Diffusion restriction", "Apparent diffusion coefficient",
    "Fluid-fluid level", "DWI hyperintensity", "Blooming artifact", "Susceptibility artifact",
    "Contrast enhancement", "Ring enhancement", "Heterogeneous enhancement", "Homogeneous enhancement",
    "Non-enhancing", "Peripheral nodular enhancement", "Washout", "Arterial phase hyperenhancement",
    "Venous phase washout", "Capsule appearance", "LI-RADS", "PI-RADS", "BI-RADS", "TI-RADS"
]

# Clinical prompt guiding Whisper / Speech engines towards radiology domain
RADIOLOGY_INITIAL_PROMPT = (
    "Radiology medical report dictation with terms: CT, MRI, X-ray, Ultrasound, PET-CT, "
    "hepatomegaly, splenomegaly, pleural effusion, cholelithiasis, choledocholithiasis, hydronephrosis, "
    "parenchymal, cortical echogenicity, mesenteric lymphadenopathy, bulky anteverted uterus, polycystic ovaries, "
    "intraparenchymal hemorrhage, hyperdense MCA sign, basal cisterns, midline shift, disc extrusion, thecal sac indentation, "
    "neural foraminal narrowing, osteophytes, ligamentum flavum hypertrophy, T1/T2 FLAIR hyperintense, mediastinum, "
    "pneumothorax, atelectasis, hemangioma, calculus, lymphadenopathy, contrast enhancement, 18F-FDG SUVmax, "
    "hypermetabolic FDG avidity, mediastinal lymph nodes, osteolytic lesion, tracer excretion, Deauville criteria."
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
    ),
    "physiological biodistribution": (
        "Physiological tracer distribution is noted in brain parenchyma, myocardium, liver, spleen, bowel, "
        "urinary bladder, and excreted tracer in bilateral kidneys. No abnormal hypermetabolic lesion identified."
    ),
    "no distant metastasis": (
        "No hypermetabolic osseous, pulmonary, hepatic, or peritoneal lesion identified to suggest distant metastatic disease."
    ),
    "normal brown fat": (
        "Mild symmetrical tracer concentration in bilateral supraclavicular fat compartments, consistent with physiological brown adipose tissue uptake."
    ),
    "deauville score 1": "Deauville score 1: No tracer uptake above background.",
    "deauville score 2": "Deauville score 2: Uptake less than or equal to mediastinal blood pool.",
    "deauville score 3": "Deauville score 3: Uptake greater than mediastinum but less than or equal to liver background.",
    "deauville score 4": "Deauville score 4: Uptake moderately higher than liver.",
    "deauville score 5": "Deauville score 5: Uptake markedly higher than liver or new lesion."
}
