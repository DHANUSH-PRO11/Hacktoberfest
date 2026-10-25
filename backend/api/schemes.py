from typing import List, Optional
from fastapi import APIRouter, Query

router = APIRouter()

AGRICULTURAL_SCHEMES = [
    {
        "id": 1,
        "name": "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
        "name_ta": "பிஎம்-கிசான் திட்டம்",
        "scheme_type": "Central Government Scheme",
        "purpose": "Direct financial assistance to small and marginal farmer families to meet agricultural input and domestic needs.",
        "purpose_ta": "விவசாய இடுபொருட்கள் மற்றும் குடும்ப தேவைகளுக்கான நேரடி நிதி உதவி.",
        "category": "Direct Income Support",
        "who_can_apply": "All landholding farmer families across India",
        "who_can_apply_ta": "நிலம் வைத்துள்ள அனைத்து விவசாய குடும்பங்கள்",
        "benefits": "₹6,000 per year directly transferred to bank account in 3 equal four-monthly installments of ₹2,000 each.",
        "benefits_ta": "ஆண்டுக்கு ₹6,000, 3 தவணைகளில் (தவணைக்கு ₹2,000) நேரடியாக வங்கி கணக்கில் செலுத்தப்படும்.",
        "eligibility": "Operational agricultural landholders with active Aadhaar eKYC and land ownership records.",
        "eligibility_ta": "ஆதார் eKYC மற்றும் பட்டா சிட்டா ஆவணம் உள்ள விவசாயிகள்.",
        "application_steps": "1. Visit pmkisan.gov.in -> Farmer Corner. 2. Enter Aadhaar number and mobile. 3. Complete eKYC via OTP or biometric CSC. 4. Upload land records (Patta/Chitta).",
        "application_steps_ta": "1. pmkisan.gov.in தளத்திற்கு செல்லவும். 2. ஆதார் மற்றும் மொபைல் எண் உள்ளிடவும். 3. eKYC OTP அல்லது பயோமெட்ரிக் மூலம் முடிக்கவும். 4. பட்டா/சிட்டா ஆவணங்களை பதிவேற்றவும்.",
        "required_documents": "Aadhaar Card, Land Ownership Record (Patta/Chitta), Bank Account Passbook with IFSC, Mobile number linked to Aadhaar.",
        "required_documents_ta": "ஆதார் அட்டை, நில பட்டா/சிட்டா, வங்கி பாஸ்புக் நகல், ஆதாருடன் இணைக்கப்பட்ட தொலைபேசி எண்.",
        "official_portal": "https://pmkisan.gov.in/",
        "source": "https://pmkisan.gov.in/",
        "last_verified": "October 2026",
        "disclaimer": "AgroNex AI does not guarantee eligibility or subsidy approval. Disbursement is authorized solely by the Ministry of Agriculture & Farmers Welfare."
    },
    {
        "id": 2,
        "name": "PMFBY (Pradhan Mantri Fasal Bima Yojana)",
        "name_ta": "பிரதம மந்திரி பயிர் காப்பீட்டுத் திட்டம்",
        "scheme_type": "Central Government Scheme",
        "purpose": "Comprehensive insurance coverage and financial support to farmers suffering crop loss/damage arising out of non-preventable natural perils.",
        "purpose_ta": "இயற்கை பேரிடர்களால் ஏற்படும் பயிர் சேதங்களுக்கு விரிவான காப்பீட்டு பாதுகாப்பு.",
        "category": "Crop Insurance",
        "who_can_apply": "All farmers including sharecroppers and tenant farmers growing notified crops in notified areas.",
        "who_can_apply_ta": "அறிவிக்கப்பட்ட பகுதியில் பயிர் செய்யும் அனைத்து விவசாயிகள் மற்றும் குத்தகை விவசாயிகள்.",
        "benefits": "Comprehensive risk coverage against non-preventable natural risks (drought, flood, pests, unseasonal cyclone). Nominal farmer premium: 2% for Kharif, 1.5% for Rabi, 5% for commercial/horticulture.",
        "benefits_ta": "வறட்சி, வெள்ளம், பூச்சித் தாக்குதல் இழப்பிற்கு முழு காப்பீடு. மிகக் குறைந்த பிரீமியம் (1.5% முதல் 2%).",
        "eligibility": "Cultivators of notified crops with sowing certificate and village land passbook.",
        "eligibility_ta": "பயிர் சாகுபடி சான்றிதழ் மற்றும் நில ஆவணங்கள் உள்ள விவசாயிகள்.",
        "application_steps": "1. Enroll via bank branch, primary agricultural cooperative (PACCS), or pmfby.gov.in before seasonal cut-off date. 2. Submit sowing certificate and land doc. 3. Pay premium share.",
        "application_steps_ta": "1. வங்கி அல்லது தொடக்க வேளாண்மை கூட்டுறவு சங்கம் அல்லது pmfby.gov.in தளத்தில் பதிவு செய்யவும். 2. அடங்கல் சான்றிதழ் சமர்ப்பிக்கவும். 3. பிரீமியம் தொகையை செலுத்தவும்.",
        "required_documents": "Land possession doc/Adangal/Chitta, Sowing Certificate from VAO, Identity proof, Bank passbook.",
        "required_documents_ta": "நில உடமை ஆவணம்/அடங்கல்/சிட்டா, கிராம நிர்வாக அலுவலர் (VAO) விதைப்பு சான்றிதழ், ஆதார், வங்கி பாஸ்புக்.",
        "official_portal": "https://pmfby.gov.in/",
        "source": "https://pmfby.gov.in/",
        "last_verified": "October 2026",
        "disclaimer": "Claim settlement depends upon yield estimation surveys and insurance company verification."
    },
    {
        "id": 3,
        "name": "PMKSY — Per Drop More Crop (Micro Irrigation Scheme)",
        "name_ta": "சொட்டு நீர் பாசன மானியத் திட்டம் (PMKSY)",
        "scheme_type": "Central Government Scheme (with State Top-Up)",
        "purpose": "Maximizing water use efficiency at farm level through precision micro-irrigation systems (drip and sprinkler).",
        "purpose_ta": "சொட்டு நீர் மற்றும் தெளிப்பு நீர் பாசனம் மூலம் நீர் பயன்பாட்டு திறனை அதிகரித்தல்.",
        "category": "Irrigation & Water Conservation",
        "who_can_apply": "Small, marginal, and other farmers possessing assured water sources.",
        "who_can_apply_ta": "பாசன நீர் ஆதாரம் உள்ள சிறு மற்றும் குறு விவசாயிகள்.",
        "benefits": "Up to 100% subsidy for small/marginal farmers in Tamil Nadu (55% Central + 45% State top-up) and 75% for other category farmers for installing Drip & Sprinkler irrigation.",
        "benefits_ta": "சிறு, குறு விவசாயிகளுக்கு 100% மானியம், இதர விவசாயிகளுக்கு 75% மானியத்தில் சொட்டுநீர் பாசனக் கருவிகள்.",
        "eligibility": "Farmers with valid borewell/well/canal source and land records.",
        "eligibility_ta": "கிணறு அல்லது ஆழ்துளை கிணறு பாசன வசதி கொண்ட நில உரிமையாளர்கள்.",
        "application_steps": "1. Apply via Uzhavan App or pmksy.gov.in or Block Assistant Director of Horticulture (ADH) office. 2. Site inspection and micro-irrigation layout design. 3. Work order issue and installation.",
        "application_steps_ta": "1. உழவன் செயலி அல்லது தோட்டக்கலை உதவி இயக்குநர் அலுவலகத்தில் விண்ணப்பிக்கவும். 2. கள ஆய்வு மற்றும் பாசன அமைப்பு வரைபடம் தயாரித்தல். 3. ஆணை பெற்று கருவிகள் பொருத்துதல்.",
        "required_documents": "Patta, Chitta, FMB sketch, Water test report, Aadhaar, Passport photo, Bank passbook.",
        "required_documents_ta": "பட்டா, சிட்டா, FMB வரைபடம், பாசன நீர் ஆய்வு சான்று, ஆதார் அட்டை, பாஸ்போர்ட் புகைப்படம், வங்கி பாஸ்புக்.",
        "official_portal": "https://pmksy.gov.in/",
        "source": "https://pmksy.gov.in/",
        "last_verified": "October 2026",
        "disclaimer": "Subsidies are subject to annual budgetary allocations and verification by agricultural engineering/horticulture officers."
    },
    {
        "id": 4,
        "name": "Soil Health Card (SHC) Scheme",
        "name_ta": "மண் வள அட்டை திட்டம்",
        "scheme_type": "Central Government Scheme",
        "purpose": "Promoting balanced nutrient application through systematic laboratory testing of farm soil and crop-specific fertilizer guidance.",
        "purpose_ta": "மண் பரிசோதனை மூலம் சமச்சீர் உரப்பயன்பாட்டை ஊக்குவித்து உரச்செலவைக் குறைத்தல்.",
        "category": "Soil Management & Fertility",
        "who_can_apply": "All agricultural landowners and operational cultivators.",
        "who_can_apply_ta": "நிலம் வைத்துள்ள அனைத்து விவசாயிகள்.",
        "benefits": "Free comprehensive soil nutrient testing (12 parameters: N, P, K, S, Zn, Fe, Cu, Mn, Bo, pH, EC, OC) with customized dosage recommendations for fertilizers to reduce cultivation costs.",
        "benefits_ta": "12 வகையான மண் சத்துக்கள் இலவச ஆய்வு. உரச்செலவைக் குறைத்து மகசூலை அதிகரிக்க பரிந்துரை அட்டை.",
        "eligibility": "All farmland parcels surveyed in grid cycles (every 2-3 years).",
        "eligibility_ta": "அனைத்து விவசாய நிலங்கள்.",
        "application_steps": "1. Request soil sample collection through local Agricultural Extension Officer or Krishi Vigyan Kendra (KVK). 2. Sample testing at government soil testing laboratory. 3. Download card via soilhealth.dac.gov.in.",
        "application_steps_ta": "1. வேளாண்மை அலுவலர் அல்லது KVK மூலம் மண் மாதிரி சேகரிக்கக் கோரவும். 2. அரசு மண் பரிசோதனை மையத்தில் ஆய்வு. 3. soilhealth.dac.gov.in தளத்தில் அட்டையைப் பெறலாம்.",
        "required_documents": "Land survey number, Farmer mobile number, Aadhaar card copy.",
        "required_documents_ta": "நில புல எண் (Survey No), விவசாயியின் மொபைல் எண், ஆதார் நகல்.",
        "official_portal": "https://soilhealth.dac.gov.in/",
        "source": "https://soilhealth.dac.gov.in/",
        "last_verified": "October 2026",
        "disclaimer": "Soil testing is conducted cyclically by state agriculture departments based on grid sampling protocols."
    },
    {
        "id": 5,
        "name": "Kisan Credit Card (KCC) Scheme",
        "name_ta": "கிசான் கடன் அட்டை திட்டம்",
        "scheme_type": "Central Government Scheme",
        "purpose": "Timely access to affordable short-term institutional credit for cultivation, post-harvest expenses, and farm asset maintenance.",
        "purpose_ta": "விவசாய உற்பத்தி மற்றும் அறுவடை பின்செலவுகளுக்கான எளிய மற்றும் குறைந்த வட்டி வங்கி கடன்.",
        "category": "Subsidized Institutional Credit",
        "who_can_apply": "Individual/joint farmers, tenant farmers, self-help groups, animal husbandry and fisheries farmers.",
        "who_can_apply_ta": "தனிநபர் விவசாயிகள், குத்தகை விவசாயிகள் மற்றும் கால்நடை வளர்ப்போர்.",
        "benefits": "Short-term crop production loan up to ₹3,00,000 at concessional interest rate of 7%, reduced to effective 4% per annum upon prompt repayment (3% prompt repayment incentive).",
        "benefits_ta": "₹3 லட்சம் வரை பயிர்க் கடன். உரிய காலத்தில் திருப்பிச் செலுத்தினால் வெறும் 4% குறைந்த வட்டி.",
        "eligibility": "All active farmers with identity, land cultivation or lease documentation.",
        "eligibility_ta": "விவசாயம் செய்யும் விவசாயிகள் மற்றும் குத்தகைதாரர்கள்.",
        "application_steps": "1. Apply at any commercial, rural (RRB), or cooperative bank branch. 2. Submit simplified one-page KCC form. 3. Card and credit limit issued within 14 days.",
        "application_steps_ta": "1. அருகிலுள்ள வணிக வங்கி அல்லது கூட்டுறவு வங்கியில் விண்ணப்பிக்கவும். 2. எளிய விண்ணப்ப படிவம் சமர்ப்பிக்கவும். 3. 14 நாட்களுக்குள் அட்டை வழங்கப்படும்.",
        "required_documents": "Application form, Aadhaar/Voter ID, Land records with crop cultivation declaration.",
        "required_documents_ta": "விண்ணப்ப படிவம், ஆதார்/வாக்காளர் அட்டை, பயிர் சாகுபடி விவரங்களுடன் கூடிய நில ஆவணம்.",
        "official_portal": "https://myscheme.gov.in/schemes/kcc",
        "source": "https://myscheme.gov.in/schemes/kcc",
        "last_verified": "October 2026",
        "disclaimer": "Loan sanction and limits are subject to bank credit appraisal, scale of finance, and repayment history."
    },
    {
        "id": 6,
        "name": "Tamil Nadu Kalaignarin All Village Integrated Agriculture Development Programme (KAVIADP)",
        "name_ta": "கலைஞரின் அனைத்து கிராம ஒருங்கிணைந்த வேளாண் வளர்ச்சித் திட்டம்",
        "scheme_type": "State Government Scheme (Tamil Nadu)",
        "purpose": "Holistic village-level agricultural development through crop diversification, distribution of certified planting material, and water harvesting assets.",
        "purpose_ta": "கிராம அளவில் விவசாய வளர்ச்சியை மேம்படுத்த தரமான விதைகள், தென்னங்கன்றுகள் மற்றும் பாசன வசதிகள் வழங்குதல்.",
        "category": "State Integrated Development",
        "who_can_apply": "Farmers in selected Tamil Nadu village panchayats.",
        "who_can_apply_ta": "தேர்ந்தெடுக்கப்பட்ட தமிழக கிராம ஊராட்சிகளில் உள்ள அனைத்து விவசாயிகள்.",
        "benefits": "Free soil health cards, distribution of high-yield certified seeds, coconut saplings, vegetable seed kits, community farm ponds, and conversion of fallow lands into cultivable land.",
        "benefits_ta": "இலவச மண் பரிசோதனை அட்டை, தரமான விதைகள், தென்னங்கன்றுகள், காய்கறி தளைகள் மற்றும் பண்ணைக் குட்டை மானியம்.",
        "eligibility": "Resident agricultural landholders in scheme panchayats with Uzhavan App registration.",
        "eligibility_ta": "உழவன் செயலியில் பதிவு செய்துள்ள கிராம விவசாயிகள்.",
        "application_steps": "1. Check if village panchayat is notified in current year. 2. Register via Uzhavan App or contact Block Agricultural Officer. 3. Receive distribution kit at village camp.",
        "application_steps_ta": "1. கிராம ஊராட்சி நடப்பு திட்ட ஆண்டில் உள்ளதா என சோதிக்கவும். 2. உழவன் செயலி அல்லது வட்டார வேளாண் அலுவலரிடம் பதிவு செய்யவும். 3. கிராம முகாமில் மானியப் பொருட்களைப் பெறவும்.",
        "required_documents": "Uzhavan App farmer registration ID, Aadhaar, Land Patta/Chitta copy.",
        "required_documents_ta": "உழவன் செயலி பதிவு எண், ஆதார் அட்டை, பட்டா/சிட்டா நகல்.",
        "official_portal": "https://www.tn.gov.in/department/1",
        "source": "https://www.tn.gov.in/department/1",
        "last_verified": "October 2026",
        "disclaimer": "State scheme benefits are distributed subject to targeted panchayat lists and physical verification."
    }
]

@router.get("/")
def get_schemes(
    lang: Optional[str] = Query("en", description="Preferred language ('en' or 'ta')"),
    search: Optional[str] = Query(None, description="Search term for scheme name, benefits, or category"),
    category: Optional[str] = Query(None, description="Filter by scheme category"),
    scheme_type: Optional[str] = Query(None, description="Filter by Central or State scheme type")
):
    """Returns verified Indian and Tamil Nadu government agricultural schemes and subsidies."""
    results = AGRICULTURAL_SCHEMES

    # Normalize parameter inputs when invoked directly as a Python function in tests
    st_val = scheme_type if isinstance(scheme_type, str) else None
    cat_val = category if isinstance(category, str) else None
    search_val = search if isinstance(search, str) else None

    if st_val:
        st = st_val.lower().strip()
        results = [s for s in results if st in s.get("scheme_type", "").lower()]

    if cat_val and cat_val.upper() != "ALL":
        cat = cat_val.lower().strip()
        results = [s for s in results if cat in s.get("category", "").lower()]

    if search_val:
        s = search_val.lower().strip()
        results = [
            scheme for scheme in results
            if s in scheme["name"].lower()
            or s in scheme.get("name_ta", "").lower()
            or s in scheme["category"].lower()
            or s in scheme["benefits"].lower()
            or s in scheme.get("benefits_ta", "").lower()
            or s in scheme.get("purpose", "").lower()
            or s in scheme.get("purpose_ta", "").lower()
            or s in scheme.get("scheme_type", "").lower()
        ]
    return results
