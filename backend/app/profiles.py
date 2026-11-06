"""Display metadata for the web form, per training profile (labels, units, groups, option text).

A profile only changes how inputs are *presented*. The model itself is trained from whichever CSV you point
TRAIN_CSV at; unknown columns fall back to an automatic label.
"""
YESNO = {0: "No", 1: "Yes"}

PROFILES = {
    "cardio": {
        "title": "Cardiovascular disease screening",
        "fields": {
            "Age": {"label": "Age", "unit": "years", "group": "About you"},
            "Gender": {"label": "Sex", "group": "About you"},
            "Height_cm": {"label": "Height", "unit": "cm", "group": "About you"},
            "Weight_kg": {"label": "Weight", "unit": "kg", "group": "About you"},
            "Systolic_BP": {"label": "Systolic blood pressure", "unit": "mmHg", "group": "Vitals and lab results"},
            "Diastolic_BP": {"label": "Diastolic blood pressure", "unit": "mmHg", "group": "Vitals and lab results"},
            "Cholesterol": {"label": "Cholesterol level", "group": "Vitals and lab results",
                            "options": {1: "Normal", 2: "Above normal", 3: "Well above normal"}},
            "Glucose": {"label": "Blood glucose level", "group": "Vitals and lab results",
                        "options": {1: "Normal", 2: "Above normal", 3: "Well above normal"}},
            "Smoker": {"label": "Smoker", "group": "Lifestyle", "options": YESNO},
            "Alcohol": {"label": "Regular alcohol intake", "group": "Lifestyle", "options": YESNO},
            "Physically_Active": {"label": "Physically active", "group": "Lifestyle", "options": YESNO},
        },
    },
    "india10k": {
        "title": "Indian 10,000-record dataset",
        "fields": {
            "Age": {"label": "Age", "unit": "years", "group": "About you"},
            "Gender": {"label": "Sex", "group": "About you"},
            "Diabetes": {"label": "Diabetes", "group": "Medical history", "options": YESNO},
            "Hypertension": {"label": "Hypertension", "group": "Medical history", "options": YESNO},
            "Obesity": {"label": "Obesity", "group": "Medical history", "options": YESNO},
            "Family_History": {"label": "Family history of heart disease", "group": "Medical history", "options": YESNO},
            "Heart_Attack_History": {"label": "Previous heart attack", "group": "Medical history", "options": YESNO},
            "Smoking": {"label": "Smoking", "group": "Lifestyle", "options": YESNO},
            "Alcohol_Consumption": {"label": "Alcohol consumption", "group": "Lifestyle", "options": YESNO},
            "Physical_Activity": {"label": "Physically active", "group": "Lifestyle", "options": YESNO},
            "Diet_Score": {"label": "Diet score (0 poor to 10 good)", "group": "Lifestyle"},
            "Stress_Level": {"label": "Stress level (1 to 10)", "group": "Lifestyle"},
            "Cholesterol_Level": {"label": "Total cholesterol", "unit": "mg/dL", "group": "Vitals and lab results"},
            "Triglyceride_Level": {"label": "Triglycerides", "unit": "mg/dL", "group": "Vitals and lab results"},
            "LDL_Level": {"label": "LDL cholesterol", "unit": "mg/dL", "group": "Vitals and lab results"},
            "HDL_Level": {"label": "HDL cholesterol", "unit": "mg/dL", "group": "Vitals and lab results"},
            "Systolic_BP": {"label": "Systolic blood pressure", "unit": "mmHg", "group": "Vitals and lab results"},
            "Diastolic_BP": {"label": "Diastolic blood pressure", "unit": "mmHg", "group": "Vitals and lab results"},
        },
    },
    "heart13": {
        "title": "Clinical cardiovascular disease dataset (1,000 patients)",
        "fields": {
            "chestpain": {"label": "Chest pain type", "group": "Heart symptoms",
                          "options": {0: "Typical angina", 1: "Atypical angina", 2: "Non-anginal pain", 3: "No chest pain"}},
            "exerciseangia": {"label": "Chest pain during exercise", "group": "Heart symptoms", "options": YESNO},
            "restingBP": {"label": "Resting blood pressure", "unit": "mmHg", "group": "Blood pressure and blood tests"},
            "serumcholestrol": {"label": "Serum cholesterol", "unit": "mg/dL", "group": "Blood pressure and blood tests"},
            "fastingbloodsugar": {"label": "Fasting blood sugar above 120 mg/dL", "group": "Blood pressure and blood tests", "options": YESNO},
            "restingrelectro": {"label": "Resting ECG result", "group": "ECG and exercise test",
                                "options": {0: "Normal", 1: "ST-T wave abnormality", 2: "Left ventricular hypertrophy"}},
            "maxheartrate": {"label": "Maximum heart rate achieved", "unit": "bpm", "group": "ECG and exercise test"},
            "oldpeak": {"label": "ST depression (oldpeak)", "unit": "mm", "group": "ECG and exercise test"},
            "slope": {"label": "ST segment slope", "group": "ECG and exercise test",
                      "options": {0: "Type 0", 1: "Type 1 (upsloping)", 2: "Type 2 (flat)", 3: "Type 3 (downsloping)"}},
            "noofmajorvessels": {"label": "Major vessels seen on imaging", "group": "ECG and exercise test",
                                 "options": {0: "0 vessels", 1: "1 vessel", 2: "2 vessels", 3: "3 vessels"}},
            "age": {"label": "Age", "unit": "years", "group": "About you"},
            "gender": {"label": "Sex", "group": "About you", "options": {0: "Female", 1: "Male"}},
        },
    },
}


def pretty(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


def label_for(profile: str | None, col: str) -> str:
    return PROFILES.get(profile or "", {}).get("fields", {}).get(col, {}).get("label", pretty(col))


def value_text(profile: str | None, col: str, value):
    """Human text for a stored value (used by the explanation and the PDF)."""
    meta = PROFILES.get(profile or "", {}).get("fields", {}).get(col, {})
    opts = meta.get("options")
    unit = meta.get("unit")
    if opts is not None:
        try:
            return opts.get(int(float(value)), str(value))
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value} {unit}" if unit else str(value)
