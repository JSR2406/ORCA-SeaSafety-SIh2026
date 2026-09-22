# Phase 6 - deterministic response localization.
#
# The orchestrator response is generated in the user's detected language while
# structured numerical data (coordinates, units, source IDs, timestamps, model
# versions) stays language-neutral.  Localization is a pure, offline dictionary
# of the fixed operational phrasing used by synthesis and the map/chart/alert
# builders; variable evidence lines (fused variable dumps, citations) are not
# template-translated.  Languages: en, hi, ml, ta, te, kn, mr (mr shares the
# Devanagari script with hi and is detected as hi-IN).
LANGUAGE_CODES = ("en-IN", "hi-IN", "ml-IN", "ta-IN", "te-IN", "kn-IN", "mr-IN")

_PHRASES: dict = {
    # ---------------------------------------------------------------- titles
    "title.risk_profile": {
        "en-IN": "Risk profile",
        "hi-IN": "जोखिम प्रोफाइल",
        "ml-IN": "അപകട പ്രൊഫൈൽ",
        "ta-IN": "ஆபத்து சுயவிவரம்",
        "te-IN": "ప్రమాద ప్రొఫైల్",
        "kn-IN": "ಅಪಾಯದ ಪ್ರೊಫೈಲ್",
        "mr-IN": "जोखिम प्रोफाइल",
    },
    "title.safety_check": {
        "en-IN": "Safety check",
        "hi-IN": "सुरक्षा जांच",
        "ml-IN": "സുരക്ഷാ പരിശോധന",
        "ta-IN": "பாதுகாப்பு சரிபார்ப்பு",
        "te-IN": "భద్రతా తనిఖీ",
        "kn-IN": "ಸುರಕ್ಷತಾ ಪರಿಶೀಲನೆ",
        "mr-IN": "सुरक्षा तपासणी",
    },
    "title.fused_marine_state": {
        "en-IN": "Fused marine state",
        "hi-IN": "संयुक्त समुद्री स्थिति",
        "ml-IN": "സമന്വയിപ്പിച്ച സമുദ്ര നില",
        "ta-IN": "இணைந்த கடல் நிலை",
        "te-IN": "సమ్మేళిత సముద్ర స్థితి",
        "kn-IN": "ಸಂಯೋಜಿತ ಸಮುದ್ರ ಸ್ಥಿತಿ",
        "mr-IN": "संयुक्त समुद्री स्थिती",
    },
    "title.marine_briefing": {
        "en-IN": "Marine briefing",
        "hi-IN": "समुद्री ब्रीफिंग",
        "ml-IN": "സമുദ്ര ബ്രീഫിംഗ്",
        "ta-IN": "கடல் விவரம்",
        "te-IN": "సముద్ర బ్రీఫింగ్",
        "kn-IN": "ಸಮುದ್ರ ಸಾರಾಂಶ",
        "mr-IN": "समुद्री ब्रीफिंग",
    },
    "title.pfz_nearest": {
        "en-IN": "PFZ advisory (nearest)",
        "hi-IN": "पीएफजेड सलाह (निकटतम)",
        "ml-IN": "PFZ ഉപദേശം (ഏറ്റവും അടുത്ത്)",
        "ta-IN": "PFZ அறிவுரை (அருகிலுள்ள)",
        "te-IN": "PFZ సలహా (సమీప)",
        "kn-IN": "PFZ ಸಲಹೆ (ಹತ್ತಿರದ)",
        "mr-IN": "पीएफझेड सल्ला (सर्वात जवळ)",
    },
    "title.fishing_potential": {
        "en-IN": "Fishing potential",
        "hi-IN": "मछली पकड़ने की संभावना",
        "ml-IN": "മത്സ്യബന്ധന സാധ്യത",
        "ta-IN": "மீன்பிடி சாத்தியம்",
        "te-IN": "చేపలు పట్టే సంభావ్యత",
        "kn-IN": "ಮೀನುಗಾರಿಕೆ ಸಂಭಾವ್ಯತೆ",
        "mr-IN": "मासेमारी क्षमता",
    },
    "title.zone_marine_state": {
        "en-IN": "Zone marine state",
        "hi-IN": "क्षेत्र की समुद्री स्थिति",
        "ml-IN": "മേഖലയിലെ സമുദ്ര നില",
        "ta-IN": "மண்டல கடல் நிலை",
        "te-IN": "జోన్ సముద్ర స్థితి",
        "kn-IN": "ವಲಯದ ಸಮುದ್ರ ಸ್ಥಿತಿ",
        "mr-IN": "क्षेत्राची समुद्री स्थिती",
    },
    "title.productivity": {
        "en-IN": "Productivity",
        "hi-IN": "उत्पादकता",
        "ml-IN": "ഉൽപ്പാദനക്ഷമത",
        "ta-IN": "உற்பத்தித்திறன்",
        "te-IN": "ఉత్పాదకత",
        "kn-IN": "ಉತ್ಪಾದಕತೆ",
        "mr-IN": "उत्पादकता",
    },
    "title.productivity_index": {
        "en-IN": "Productivity index",
        "hi-IN": "उत्पादकता सूचकांक",
        "ml-IN": "ഉൽപ്പാദന സൂചിക",
        "ta-IN": "உற்பத்தி குறியீடு",
        "te-IN": "ఉత్పాదకత సూచిక",
        "kn-IN": "ಉತ್ಪಾದಕತಾ ಸೂಚ್ಯಂಕ",
        "mr-IN": "उत्पादकता निर्देशांक",
    },
    "title.route_restrictions": {
        "en-IN": "Route restrictions",
        "hi-IN": "मार्ग प्रतिबंध",
        "ml-IN": "റൂട്ട് നിയന്ത്രണങ്ങൾ",
        "ta-IN": "வழி தடைகள்",
        "te-IN": "మార్గ పరిమితులు",
        "kn-IN": "ಮಾರ್ಗ ನಿರ್ಬಂಧಗಳು",
        "mr-IN": "मार्ग निर्बंध",
    },
    "title.endpoint_state": {
        "en-IN": "Endpoint {index} marine state",
        "hi-IN": "गंतव्य {index} समुद्री स्थिति",
        "ml-IN": "അറ്റം {index} സമുദ്ര നില",
        "ta-IN": "முனை {index} கடல் நிலை",
        "te-IN": "చివరి {index} సముద్ర స్థితి",
        "kn-IN": "ಅಂತ್ಯ {index} ಸಮುದ್ರ ಸ್ಥಿತಿ",
        "mr-IN": "सीमा {index} समुद्री स्थिती",
    },
    "title.scenario_comparison": {
        "en-IN": "Scenario comparison",
        "hi-IN": "परिदृश्य तुलना",
        "ml-IN": "സാഹചര്യ താരതമ്യം",
        "ta-IN": "காட்சி ஒப்பீடு",
        "te-IN": "దృశ్య పోలిక",
        "kn-IN": "ಸನ್ನಿವೇಶ ಹೋಲಿಕೆ",
        "mr-IN": "परिदृश्य तुलना",
    },
    "title.option": {
        "en-IN": "Option {index}",
        "hi-IN": "विकल्प {index}",
        "ml-IN": "ഓപ്ഷൻ {index}",
        "ta-IN": "விருப்பம் {index}",
        "te-IN": "ఎంపిక {index}",
        "kn-IN": "ಆಯ್ಕೆ {index}",
        "mr-IN": "पर्याय {index}",
    },
    "title.knowledge_summary": {
        "en-IN": "Knowledge summary",
        "hi-IN": "ज्ञान सारांश",
        "ml-IN": "വിജ്ഞാന സംഗ്രഹം",
        "ta-IN": "அறிவு சுருக்கம்",
        "te-IN": "జ్ఞాన సారాంశం",
        "kn-IN": "ಜ್ಞಾನ ಸಾರಾಂಶ",
        "mr-IN": "ज्ञान सारांश",
    },
    # ------------------------------------------------------------------ lines
    "line.aborted": {
        "en-IN": "The request could not be completed; no agent responses were produced.",
        "hi-IN": "अनुरोध पूरा नहीं किया जा सका; कोई एजेंट प्रतिक्रिया उत्पन्न नहीं हुई।",
        "ml-IN": "അഭ്യർത്ഥന പൂർത്തിയാക്കാനായില്ല; ഒരു ഏജന്റ് പ്രതികരണവും ഉണ്ടായില്ല.",
        "ta-IN": "கோரிக்கையை முடிக்க முடியவில்லை; எந்த மறுமொழியும் உருவாக்கப்படவில்லை.",
        "te-IN": "అభ్యర్థనను పూర్తి చేయలేకపోయాము; ఎటువంటి స్పందనా రాలేదు.",
        "kn-IN": "ವಿನಂತಿಯನ್ನು ಪೂರ್ಣಗೊಳಿಸಲಾಗಲಿಲ್ಲ; ಯಾವುದೇ ಪ್ರತಿಕ್ರಿಯೆ ಉತ್ಪತ್ತಿಯಾಗಲಿಲ್ಲ.",
        "mr-IN": "विनंती पूर्ण करता आली नाही; कोणतेही प्रतिसाद निर्माण झाले नाहीत.",
    },
    "line.partial": {
        "en-IN": "Partial result: some capability providers did not respond ({failed} failed task(s)).",
        "hi-IN": "आंशिक परिणाम: कुछ क्षमता प्रदाताओं ने प्रतिक्रिया नहीं दी ({failed} विफल कार्य)।",
        "ml-IN": "ഭാഗിക ഫലം: ചില ശേഷി ദാതാക്കൾ പ്രതികരിച്ചില്ല ({failed} പരാജയപ്പെട്ട ജോലി).",
        "ta-IN": "பகுதி முடிவு: சில திறன் வழங்குநர்கள் பதிலளிக்கவில்லை ({failed} தோல்வியுற்ற பணிகள்).",
        "te-IN": "పాక్షిక ఫలితం: కొన్ని సేవలు స్పందించలేదు ({failed} విఫల పనులు).",
        "kn-IN": "ಭಾಗಶಃ ಫಲಿತಾಂಶ: ಕೆಲವು ಸೇವೆಗಳು ಪ್ರತಿಕ್ರಿಯಿಸಲಿಲ್ಲ ({failed} ವಿಫಲ ಕಾರ್ಯಗಳು).",
        "mr-IN": "आंशिक परिणाम: काही सेवा प्रदात्यांनी प्रतिसाद दिला नाही ({failed} अयशस्वी कामे).",
    },
    "line.empty_synthesis": {
        "en-IN": "No synthesis was produced from the available evidence.",
        "hi-IN": "उपलब्ध साक्ष्य से कोई उत्तर तैयार नहीं किया जा सका।",
        "ml-IN": "ലഭ്യമായ തെളിവുകളിൽ നിന്ന് ഒരു ഉത്തരവും രൂപപ്പെടുത്തിയില്ല.",
        "ta-IN": "கிடைக்கக்கூடிய சான்றுகளிலிருந்து எந்த பதிலும் உருவாக்கப்படவில்லை.",
        "te-IN": "అందుబాటులో ఉన్న ఆధారాల నుండి ఎటువంటి సమాధానం లేదు.",
        "kn-IN": "ಲಭ್ಯವಿರುವ ಪುರಾವೆಗಳಿಂದ ಯಾವುದೇ ಉತ್ತರ ರಚಿಸಲಾಗಿಲ್ಲ.",
        "mr-IN": "उपलब्ध पुराव्यांवरून कोणतेही उत्तर तयार झाले नाही.",
    },
    "line.briefing_prepared": {
        "en-IN": "Briefing prepared for {point}.",
        "hi-IN": "के लिए ब्रीफिंग तैयार {point}।",
        "ml-IN": "സംഗ്രഹം തയ്യാറാക്കി: {point}.",
        "ta-IN": "விவரம் தயாரிக்கப்பட்டது: {point}.",
        "te-IN": "బ్రీఫింగ్ సిద్ధం: {point}.",
        "kn-IN": "ಬ್ರೀಫಿಂಗ್ ಸಿದ್ಧ: {point}.",
        "mr-IN": "साठी ब्रीफिंग तयार {point}.",
    },
    "line.favorability": {
        "en-IN": "Favorability index: {score} (target: {target})",
        "hi-IN": "अनुकूलता सूचकांक: {score} (लक्ष्य: {target})",
        "ml-IN": "അനുകൂല സൂചിക: {score} (ലക്ഷ്യം: {target})",
        "ta-IN": "சாதக குறியீடு: {score} (இலக்கு: {target})",
        "te-IN": "అనుకూల సూచిక: {score} (లక్ష్యం: {target})",
        "kn-IN": "ಅನುಕೂಲ ಸೂಚ್ಯಂಕ: {score} (ಗುರಿ: {target})",
        "mr-IN": "अनुकूलता निर्देशांक: {score} (उद्देश्य: {target})",
    },
    "line.safety_unavailable": {
        "en-IN": "Safety verdict: data unavailable - do not assume a safe condition.",
        "hi-IN": "सुरक्षा निर्णय: डेटा अनुपलब्ध - सुरक्षित स्थिति न मानें।",
        "ml-IN": "സുരക്ഷാ നിഗമനം: ഡാറ്റ ലഭ്യമല്ല - സുരക്ഷിതമാണെന്ന് കരുതരുത്.",
        "ta-IN": "பாதுகாப்பு தீர்ப்பு: தரவு இல்லை - பாதுகாப்பானது என்று கருதாதீர்கள்.",
        "te-IN": "భద్రతా తీర్పు: డేటా అందుబాటులో లేదు - సురక్షితమని భావించవద్దు.",
        "kn-IN": "ಸುರಕ್ಷತಾ ತೀರ್ಮಾನ: ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ - ಸುರಕ್ಷಿತವೆಂದು ಭಾವಿಸಬೇಡಿ.",
        "mr-IN": "सुरक्षा निर्णय: डेटा उपलब्ध नाही - सुरक्षित स्थिती समजू नका.",
    },
    "line.risk_point": {
        "en-IN": "Risk level {level} for this point.",
        "hi-IN": "इस क्षेत्र के लिए जोखिम स्तर {level}।",
        "ml-IN": "ഈ പോയിന്റിനുള്ള അപകട നില {level}.",
        "ta-IN": "இந்த புள்ளிக்கான ஆபத்து நிலை {level}.",
        "te-IN": "ఈ పాయింట్కి ప్రమాద స్థాయి {level}.",
        "kn-IN": "ಈ ಸ್ಥಳಕ್ಕೆ ಅಪಾಯದ ಮಟ್ಟ {level}.",
        "mr-IN": "या ठिकाणासाठी धोका पातळी {level}.",
    },
    "line.risk_hard_constraint": {
        "en-IN": "ELEVATED RISK (hard constraint): an active warning or restricted area applies. Avoid the area and follow official warnings; do not proceed.",
        "hi-IN": "उच्च जोखिम (कठोर बाध्यता): सक्रिय चेतावनी या प्रतिबंधित क्षेत्र लागू है। क्षेत्र से बचें और आधिकारिक चेतावनियों का पालन करें; आगे न बढ़ें।",
        "ml-IN": "ഉയർന്ന അപകടം (കർശന നിയന്ത്രണം): സജീവ മുന്നറിയിപ്പോ നിയന്ത്രിത മേഖലയോ ബാധകമാണ്. മേഖല ഒഴിവാക്കുക, ഔദ്യോഗിക മുന്നറിയിപ്പുകൾ പാലിക്കുക; മുന്നോട്ട് പോകരുത്.",
        "ta-IN": "உயர் ஆபத்து (கடுமையான கட்டுப்பாடு): செயலில் எச்சரிக்கை அல்லது தடை பகுதி உள்ளது. பகுதியைத் தவிர்த்து அதிகாரப்பூர்வ எச்சரிக்கைகளைப் பின்பற்றுங்கள்; முன்னேற வேண்டாம்.",
        "te-IN": "అధిక ప్రమాదం (కఠిన నిబంధన): క్రియాశీల హెచ్చరిక లేదా నిషేధిత ప్రాంతం ఉంది. ఆ ప్రాంతాన్ని నివారించి అధికారిక హెచ్చరికలను పాటించండి; ముందుకు సాగవద్దు.",
        "kn-IN": "ಅಧಿಕ ಅಪಾಯ (ಕಟ್ಟುನಿಟ್ಟಿನ ನಿರ್ಬಂಧ): ಸಕ್ರಿಯ ಎಚ್ಚರಿಕೆ ಅಥವಾ ನಿಷೇಧಿತ ಪ್ರದೇಶವಿದೆ. ಪ್ರದೇಶವನ್ನು ತಪ್ಪಿಸಿ ಅಧಿಕೃತ ಎಚ್ಚರಿಕೆಗಳನ್ನು ಪಾಲಿಸಿ; ಮುಂದುವರಿಯಬೇಡಿ.",
        "mr-IN": "उच्च धोका (कठोर बंधन): सक्रिय इशारा किंवा प्रतिबंधित क्षेत्र लागू आहे. क्षेत्र टाळा आणि अधिकृत इशाऱ्यांचे पालन करा; पुढे जाऊ नका.",
    },
    "line.pfz_zone": {
        "en-IN": "Nearest PFZ zone {zone} {placement} {distance} km from the query point",
        "hi-IN": "निकटतम पीएफजेड क्षेत्र {zone} {placement} {distance} किमी दूर है",
        "ml-IN": "ഏറ്റവും അടുത്ത PFZ മേഖല {zone} {placement} {distance} കി.മീ. അകലെ",
        "ta-IN": "அருகிலுள்ள PFZ மண்டலம் {zone} {placement} {distance} கி.மீ. தொலைவில்",
        "te-IN": "సమీప PFZ జోన్ {zone} {placement} {distance} కి.మీ దూరంలో",
        "kn-IN": "ಹತ್ತಿರದ PFZ ವಲಯ {zone} {placement} {distance} ಕಿ.ಮೀ ದೂರದಲ್ಲಿ",
        "mr-IN": "जवळचे पीएफझेड क्षेत्र {zone} {placement} {distance} किमी अंतरावर",
    },
    "line.pfz_contains": {
        "en-IN": "contains",
        "hi-IN": "में स्थित है",
        "ml-IN": "ഉൾക്കൊള്ളുന്നു",
        "ta-IN": "உள்ளது",
        "te-IN": "ఉన్నాయి",
        "kn-IN": "ಹೊಂದಿದೆ",
        "mr-IN": "मध्ये आहे",
    },
    "line.pfz_at": {
        "en-IN": "at",
        "hi-IN": "पर",
        "ml-IN": "അകലെ",
        "ta-IN": "இல்",
        "te-IN": "వద్ద",
        "kn-IN": "ನಲ್ಲಿ",
        "mr-IN": "येथे",
    },
    "line.fishing_potential_zone": {
        "en-IN": "Fishing potential at the zone: {potential} ({level})",
        "hi-IN": "क्षेत्र में मछली पकड़ने की संभावना: {potential} ({level})",
        "ml-IN": "മേഖലയിലെ മത്സ്യബന്ധന സാധ്യത: {potential} ({level})",
        "ta-IN": "மண்டலத்தில் மீன்பிடி சாத்தியம்: {potential} ({level})",
        "te-IN": "జోన్లో చేపలు పట్టే సంభావ్యత: {potential} ({level})",
        "kn-IN": "ವಲಯದಲ್ಲಿ ಮೀನುಗಾರಿಕೆ ಸಂಭಾವ್ಯತೆ: {potential} ({level})",
        "mr-IN": "क्षेत्रातील मासेमारी क्षमता: {potential} ({level})",
    },
    "line.productivity_index": {
        "en-IN": "Productivity index: {productivity} ({label})",
        "hi-IN": "उत्पादकता सूचकांक: {productivity} ({label})",
        "ml-IN": "ഉൽപ്പാദന സൂചിക: {productivity} ({label})",
        "ta-IN": "உற்பத்தி குறியீடு: {productivity} ({label})",
        "te-IN": "ఉత్పాదకత సూచిక: {productivity} ({label})",
        "kn-IN": "ಉತ್ಪಾದಕತಾ ಸೂಚ್ಯಂಕ: {productivity} ({label})",
        "mr-IN": "उत्पादकता निर्देशांक: {productivity} ({label})",
    },
    "line.no_route_restrictions": {
        "en-IN": "no restricted-area intersections reported",
        "hi-IN": "कोई प्रतिबंधित क्षेत्र प्रतिच्छेदन नहीं",
        "ml-IN": "നിയന്ത്രിത മേഖല കടന്നുപോകൽ രേഖപ്പെടുത്തിയിട്ടില്ല",
        "ta-IN": "தடை பகுதி குறுக்கீடு எதுவும் இல்லை",
        "te-IN": "నిషేధిత ప్రాంత ఖండన లేదు",
        "kn-IN": "ನಿರ್ಬಂಧಿತ ಪ್ರದೇಶ ಛೇದನ ವರದಿಯಾಗಿಲ್ಲ",
        "mr-IN": "प्रतिबंधित क्षेत्र छेदन नाही",
    },
    "line.route_restrictions_count": {
        "en-IN": "{count} restricted-area intersection(s) on route",
        "hi-IN": "मार्ग पर {count} प्रतिबंधित क्षेत्र प्रतिच्छेदन",
        "ml-IN": "റൂട്ടിൽ {count} നിയന്ത്രിത മേഖല കടന്നുപോകൽ",
        "ta-IN": "வழியில் {count} தடை பகுதி குறுக்கீடு",
        "te-IN": "మార్గంలో {count} నిషేధిత ప్రాంత ఖండనలు",
        "kn-IN": "ಮಾರ್ಗದಲ್ಲಿ {count} ನಿರ್ಬಂಧಿತ ಪ್ರದೇಶ ಛೇದನ",
        "mr-IN": "मार्गावर {count} प्रतिबंधित क्षेत्र छेदन",
    },
    "line.scenario_compared": {
        "en-IN": "compared {count} state(s)",
        "hi-IN": "{count} स्थितियाँ तुलना की गईं",
        "ml-IN": "{count} നിലകൾ താരതമ്യം ചെയ്തു",
        "ta-IN": "{count} நிலைகள் ஒப்பிடப்பட்டன",
        "te-IN": "{count} స్థితులు పోల్చబడ్డాయి",
        "kn-IN": "{count} ಸ್ಥಿತಿಗಳನ್ನು ಹೋಲಿಸಲಾಗಿದೆ",
        "mr-IN": "{count} स्थितींची तुलना केली",
    },
    "line.retrieval_mode": {
        "en-IN": "retrieval mode: {mode}",
        "hi-IN": "पुनर्प्राप्ति मोड: {mode}",
        "ml-IN": "വീണ്ടെടുക്കൽ രീതി: {mode}",
        "ta-IN": "மீட்டெடுப்பு முறை: {mode}",
        "te-IN": "పునరుద్ధరణ విధానం: {mode}",
        "kn-IN": "ಮರುಪಡೆಯುವಿಕೆ ವಿಧಾನ: {mode}",
        "mr-IN": "पुनर्प्राप्ती पद्धत: {mode}",
    },
    "line.source_unavailable": {
        "en-IN": "Source unavailable: {source}",
        "hi-IN": "स्रोत अनुपलब्ध: {source}",
        "ml-IN": "ഉറവിടം ലഭ്യമല്ല: {source}",
        "ta-IN": "மூலம் இல்லை: {source}",
        "te-IN": "మూలం అందుబాటులో లేదు: {source}",
        "kn-IN": "ಮೂಲ ಲಭ್ಯವಿಲ್ಲ: {source}",
        "mr-IN": "स्रोत अनुपलब्ध: {source}",
    },
    "line.stale_hours": {
        "en-IN": "Latest available ocean observation is {hours} hours old.",
        "hi-IN": "नवीनतम उपलब्ध समुद्री अवलोकन {hours} घंटे पुराना है।",
        "ml-IN": "പുതിയ ലഭ്യമായ സമുദ്ര നിരീക്ഷണം {hours} മണിക്കൂർ പഴയതാണ്.",
        "ta-IN": "கிடைக்கும் சமீபத்திய கடல் கண்காணிப்பு {hours} மணிநேரம் பழமையானது.",
        "te-IN": "సమీపంలో లభ్యమైన సముద్ర పరిశీలన {hours} గంటల పాతది.",
        "kn-IN": "ಲಭ್ಯವಿರುವ ಇತ್ತೀಚಿನ ಸಮುದ್ರ ವೀಕ್ಷಣೆ {hours} ಗಂಟೆ ಹಳೆಯದು.",
        "mr-IN": "सर्वात अलीकडील समुद्री निरीक्षण {hours} तास जुने आहे.",
    },
    "line.insufficient_data": {
        "en-IN": "INSUFFICIENT DATA",
        "hi-IN": "अपर्याप्त डेटा",
        "ml-IN": "മതിയായ ഡാറ്റ ലഭ്യമല്ല",
        "ta-IN": "போதுமான தரவு இல்லை",
        "te-IN": "తగినంత డేటా లేదు",
        "kn-IN": "ಸಾಕಷ್ಟು ಡೇಟಾ ಇಲ್ಲ",
        "mr-IN": "अपुरा डेटा",
    },
    "line.which_location": {
        "en-IN": "Which location are you asking about?",
        "hi-IN": "आप किस स्थान के बारे में पूछ रहे हैं?",
        "ml-IN": "ഏത് സ്ഥലത്തെക്കുറിച്ചാണ് നിങ്ങൾ ചോദിക്കുന്നത്?",
        "ta-IN": "எந்த இடத்தைப் பற்றி கேட்கிறீர்கள்?",
        "te-IN": "మీరు ఏ ప్రదేశం గురించి అడుగుతున్నారు?",
        "kn-IN": "ನೀವು ಯಾವ ಸ್ಥಳದ ಬಗ್ಗೆ ಕೇಳುತ್ತಿದ್ದೀರಿ?",
        "mr-IN": "तुम्ही कोणत्या ठिकाणाबद्दल विचारत आहात?",
    },
    # ------------------------------------------------------- outputs (titles)
    "output.map.pfz": {
        "en-IN": "Nearest PFZ advisory zone",
        "hi-IN": "निकटतम पीएफजेड सलाह क्षेत्र",
        "ml-IN": "ഏറ്റവും അടുത്ത PFZ ഉപദേശ മേഖല",
        "ta-IN": "அருகிலுள்ள PFZ அறிவுரை மண்டலம்",
        "te-IN": "సమీప PFZ సలహా జోన్",
        "kn-IN": "ಹತ್ತಿರದ PFZ ಸಲಹಾ ವಲಯ",
        "mr-IN": "जवळचे पीएफझेड सल्ला क्षेत्र",
    },
    "output.map.search_area": {
        "en-IN": "Nearest PFZ search radius",
        "hi-IN": "निकटतम पीएफजेड खोज त्रिज्या",
        "ml-IN": "ഏറ്റവും അടുത്ത PFZ തിരയൽ പരിധി",
        "ta-IN": "அருகிலுள்ள PFZ தேடல் ஆரம்",
        "te-IN": "సమీప PFZ శోధన వ్యాసార్థం",
        "kn-IN": "ಹತ್ತಿರದ PFZ ಹುಡುಕಾಟ ತ್ರಿಜ್ಯ",
        "mr-IN": "जवळचे पीएफझेड शोध त्रिज्या",
    },
    "output.chart.fishing_potential": {
        "en-IN": "Fishing potential",
        "hi-IN": "मछली पकड़ने की संभावना",
        "ml-IN": "മത്സ്യബന്ധന സാധ്യത",
        "ta-IN": "மீன்பிடி சாத்தியம்",
        "te-IN": "చేపలు పట్టే సంభావ్యత",
        "kn-IN": "ಮೀನುಗಾರಿಕೆ ಸಂಭಾವ್ಯತೆ",
        "mr-IN": "मासेमारी क्षमता",
    },
    "output.chart.productivity": {
        "en-IN": "Productivity index",
        "hi-IN": "उत्पादकता सूचकांक",
        "ml-IN": "ഉൽപ്പാദന സൂചിക",
        "ta-IN": "உற்பத்தி குறியீடு",
        "te-IN": "ఉత్పాదకత సూచిక",
        "kn-IN": "ಉತ್ಪಾದಕತಾ ಸೂಚ್ಯಂಕ",
        "mr-IN": "उत्पादकता निर्देशांक",
    },
    "output.chart.marine_risk": {
        "en-IN": "Marine risk",
        "hi-IN": "समुद्री जोखिम",
        "ml-IN": "സമുദ്ര അപകടം",
        "ta-IN": "கடல் ஆபத்து",
        "te-IN": "సముద్ర ప్రమాదం",
        "kn-IN": "ಸಮುದ್ರ ಅಪಾಯ",
        "mr-IN": "समुद्री धोका",
    },
    "output.chart.sst": {
        "en-IN": "Sea surface temperature",
        "hi-IN": "समुद्र सतह तापमान",
        "ml-IN": "കടൽ ഉപരിതല താപനില",
        "ta-IN": "கடல் மேற்பரப்பு வெப்பநிலை",
        "te-IN": "సముద్ర ఉపరితల ఉష్ణోగ్రత",
        "kn-IN": "ಸಮುದ್ರ ಮೇಲ್ಮೈ ತಾಪಮಾನ",
        "mr-IN": "समुद्र पृष्ठभाग तापमान",
    },
    "output.chart.chlorophyll": {
        "en-IN": "Chlorophyll",
        "hi-IN": "क्लोरोफिल",
        "ml-IN": "ക്ലോറോഫിൽ",
        "ta-IN": "குளோரோபில்",
        "te-IN": "క్లోరోఫిల్",
        "kn-IN": "ಕ್ಲೋರೋಫಿಲ್",
        "mr-IN": "क्लोरोफिल",
    },
    "output.chart.wave_height": {
        "en-IN": "Wave height",
        "hi-IN": "लहर ऊंचाई",
        "ml-IN": "തിരമാല ഉയരം",
        "ta-IN": "அலை உயரம்",
        "te-IN": "అల ఎత్తు",
        "kn-IN": "ಅಲೆಯ ಎತ್ತರ",
        "mr-IN": "लाटांची उंची",
    },
    "output.chart.wave_period": {
        "en-IN": "Wave period",
        "hi-IN": "लहर अवधि",
        "ml-IN": "തിരമാല കാലയളവ്",
        "ta-IN": "அலை காலம்",
        "te-IN": "అల కాలం",
        "kn-IN": "ಅಲೆಯ ಅವಧಿ",
        "mr-IN": "लाटा कालावधी",
    },
    "output.chart.wind": {
        "en-IN": "Wind speed",
        "hi-IN": "हवा की गति",
        "ml-IN": "കാറ്റിന്റെ വേഗത",
        "ta-IN": "காற்றின் வேகம்",
        "te-IN": "గాలి వేగం",
        "kn-IN": "ಗಾಳಿಯ ವೇಗ",
        "mr-IN": "वाऱ्याचा वेग",
    },
    "output.chart.current": {
        "en-IN": "Current speed",
        "hi-IN": "धारा गति",
        "ml-IN": "ഒഴുക്കിന്റെ വേഗത",
        "ta-IN": "நீரோட்ட வேகம்",
        "te-IN": "ప్రవాహ వేగం",
        "kn-IN": "ಪ್ರವಾಹದ ವೇಗ",
        "mr-IN": "प्रवाहाचा वेग",
    },
    # ----------------------------------------------------------------- alerts
    "alert.title.restriction": {
        "en-IN": "Active safety constraint",
        "hi-IN": "सक्रिय सुरक्षा बाध्यता",
        "ml-IN": "സജീവ സുരക്ഷാ നിയന്ത്രണം",
        "ta-IN": "செயலில் பாதுகாப்பு கட்டுப்பாடு",
        "te-IN": "క్రియాశీల భద్రతా నిబంధన",
        "kn-IN": "ಸಕ್ರಿಯ ಸುರಕ್ಷತಾ ನಿರ್ಬಂಧ",
        "mr-IN": "सक्रिय सुरक्षा बंधन",
    },
    "alert.title.dynamic_restriction": {
        "en-IN": "Active dynamic restrictions",
        "hi-IN": "सक्रिय गतिशील प्रतिबंध",
        "ml-IN": "സജീവ ചലനാത്മക നിയന്ത്രണങ്ങൾ",
        "ta-IN": "செயலில் மாறும் தடைகள்",
        "te-IN": "క్రియాశీల డైనమిక్ పరిమితులు",
        "kn-IN": "ಸಕ್ರಿಯ ಡೈನಾಮಿಕ್ ನಿರ್ಬಂಧಗಳು",
        "mr-IN": "सक्रिय गतिशील निर्बंध",
    },
    "alert.title.route_restriction": {
        "en-IN": "Route intersects restricted area",
        "hi-IN": "मार्ग प्रतिबंधित क्षेत्र से टकराता है",
        "ml-IN": "റൂട്ട് നിയന്ത്രിത മേഖലയെ മുറിച്ചുകടക്കുന്നു",
        "ta-IN": "வழி தடை பகுதியை கடக்கிறது",
        "te-IN": "మార్గం నిషేధిత ప్రాంతాన్ని ఖండిస్తుంది",
        "kn-IN": "ಮಾರ್ಗವು ನಿರ್ಬಂಧಿತ ಪ್ರದೇಶವನ್ನು ಛೇದಿಸುತ್ತದೆ",
        "mr-IN": "मार्ग प्रतिबंधित क्षेत्राला छेदतो",
    },
    "alert.title.geofence": {
        "en-IN": "Inside a static marine geofence",
        "hi-IN": "स्थिर समुद्री भू-सीमा के अंदर",
        "ml-IN": "സ്ഥിര സമുദ്ര ജിയോഫെൻസിനുള്ളിൽ",
        "ta-IN": "நிலையான கடல் புவி-எல்லைக்குள்",
        "te-IN": "స్థిర సముద్ర జియోఫెన్స్ లోపల",
        "kn-IN": "ಸ್ಥಿರ ಸಮುದ್ರ ಜಿಯೋಫೆನ್ಸ್ ಒಳಗೆ",
        "mr-IN": "स्थिर समुद्री भू-सीमेच्या आत",
    },
    "alert.title.data_quality": {
        "en-IN": "Data quality",
        "hi-IN": "डेटा गुणवत्ता",
        "ml-IN": "ഡാറ്റ നിലവാരം",
        "ta-IN": "தரவு தரம்",
        "te-IN": "డేటా నాణ్యత",
        "kn-IN": "ಡೇಟಾ ಗುಣಮಟ್ಟ",
        "mr-IN": "डेटा गुणवत्ता",
    },
    "alert.msg.dynamic_restrictions": {
        "en-IN": "{count} official dynamic restriction(s) active at the point.",
        "hi-IN": "{count} आधिकारिक गतिशील प्रतिबंध इस क्षेत्र में सक्रिय हैं।",
        "ml-IN": "{count} ഔദ്യോഗിക ചലനാത്മക നിയന്ത്രണങ്ങൾ ഈ പോയിന്റിൽ സജീവമാണ്.",
        "ta-IN": "{count} அதிகாரப்பூர்வ மாறும் தடைகள் இந்த புள்ளியில் செயலில் உள்ளன.",
        "te-IN": "{count} అధికారిక డైనమిక్ పరిమితులు ఈ పాయింట్లో క్రియాశీలంగా ఉన్నాయి.",
        "kn-IN": "{count} ಅಧಿಕೃತ ಡೈನಾಮಿಕ್ ನಿರ್ಬಂಧಗಳು ಈ ಸ್ಥಳದಲ್ಲಿ ಸಕ್ರಿಯವಾಗಿವೆ.",
        "mr-IN": "{count} अधिकृत गतिशील निर्बंध या ठिकाणी सक्रिय आहेत.",
    },
    "alert.msg.geofence": {
        "en-IN": "Point is inside {name}.",
        "hi-IN": "बिंदु {name} के अंदर है।",
        "ml-IN": "പോയിന്റ് {name} നുള്ളിലാണ്.",
        "ta-IN": "புள்ளி {name} க்குள் உள்ளது.",
        "te-IN": "పాయింట్ {name} లోపల ఉంది.",
        "kn-IN": "ಬಿಂದು {name} ಒಳಗಿದೆ.",
        "mr-IN": "बिंदू {name} च्या आत आहे.",
    },
    "alert.msg.route_restriction": {
        "en-IN": "The requested route intersects {count} restricted area(s) and is not recommended.",
        "hi-IN": "अनुरोधित मार्ग {count} प्रतिबंधित क्षेत्र से टकराता है और अनुशंसित नहीं है।",
        "ml-IN": "അഭ്യർത്ഥിച്ച റൂട്ട് {count} നിയന്ത്രിത മേഖലയെ മുറിച്ചുകടക്കുന്നു, ശുപാർശയില്ല.",
        "ta-IN": "கோரிய வழி {count} தடை பகுதியை கடக்கிறது, பரிந்துரைக்கப்படவில்லை.",
        "te-IN": "అభ్యర్థించిన మార్గం {count} నిషేధిత ప్రాంతాన్ని ఖండిస్తుంది, సిఫార్సు చేయబడదు.",
        "kn-IN": "ವಿನಂತಿಸಿದ ಮಾರ್ಗವು {count} ನಿರ್ಬಂಧಿತ ಪ್ರದೇಶವನ್ನು ಛೇದಿಸುತ್ತದೆ, ಶಿಫಾರಸು ಮಾಡಿಲ್ಲ.",
        "mr-IN": "विनंती केलेला मार्ग {count} प्रतिबंधित क्षेत्राला छेदतो आणि शिफारस नाही.",
    },
}


def t(language: str, key: str, **fmt) -> str:
    """Localized phrase for `language` (fallback: English), format-filled."""
    entry = _PHRASES.get(key) or {}
    phrase = entry.get(language) or entry.get("en-IN") or key
    try:
        return phrase.format(**fmt) if fmt else phrase
    except (KeyError, IndexError, ValueError):
        # A misplaced placeholder must never crash synthesis.
        return entry.get("en-IN", key)


def section_title(language: str, title: str) -> str:
    """Translate a known English section title; pass through otherwise."""
    _KEY_BY_TITLE = {v["en-IN"]: k for k, v in _PHRASES.items()
                     if k.startswith("title.")}
    key = _KEY_BY_TITLE.get(title)
    return t(language, key) if key else title


def _localize_line(language: str, line: str) -> str:
    """Translate the fixed operational line templates in `line` (English input)."""
    if language == "en-IN":
        return line
    import re

    rule = line.strip().lower()
    pfz = re.fullmatch(
        r"nearest pfz zone (\S+) (contains|at) ([\d.]+) km from the query point",
        rule)
    if pfz:
        placement = t(language, "line.pfz_contains") if pfz.group(2) == "contains" \
            else t(language, "line.pfz_at")
        return t(language, "line.pfz_zone",
                  zone=pfz.group(1), placement=placement, distance=pfz.group(3))
    count = re.fullmatch(r"(\d+) restricted-area intersection\(s\) on route", rule)
    if count:
        return t(language, "line.route_restrictions_count", count=count.group(1))
    partial = re.fullmatch(
        r"partial result: some capability providers did not respond \((\d+) failed task\(s\)\)\.?",
        rule)
    if partial:
        return t(language, "line.partial", failed=partial.group(1))
    compared = re.fullmatch(r"compared (\d+) state\(s\)", rule)
    if compared:
        return t(language, "line.scenario_compared", count=compared.group(1))
    retrieval = re.fullmatch(r"retrieval mode: (.+)", rule)
    if retrieval:
        return t(language, "line.retrieval_mode", mode=retrieval.group(1))
    stove = re.fullmatch(r".*zone generated:.*", rule)
    if stove:
        return line
    _EXACT = {
        "the request could not be completed; no agent responses were produced.": "line.aborted",
        "partial result: some capability providers did not respond (0 failed task(s)).": "line.partial",
        "no synthesis was produced from the available evidence.": "line.empty_synthesis",
        "safety verdict: data unavailable - do not assume a safe condition.": "line.safety_unavailable",
        "no restricted-area intersections reported": "line.no_route_restrictions",
        "risk level moderate for this point.": "line.risk_point",
        "risk level elevated for this point.": "line.risk_point",
        "risk level critical for this point.": "line.risk_point",
        "risk level high for this point.": "line.risk_point",
        "risk level caution for this point.": "line.risk_point",
        "risk level safe for this point.": "line.risk_point",
        "risk level insufficient for this point.": "line.risk_point",
    }
    key = _EXACT.get(rule)
    if key is None:
        return line
    if key == "line.risk_point":
        match = re.fullmatch(r"risk level (\w+) for this point.", rule)
        return t(language, "line.risk_point", level=match.group(1))
    return t(language, key)


def localize_response(response: dict, language: str) -> dict:
    """Post-pass: translate the fixed operational frame of an orchestrator
    response into `language`.  English messages are unchanged."""
    if language == "en-IN":
        return response
    response["sections"] = [
        {**s, "title": section_title(language, s.get("title", ""))}
        if s.get("title") else s
        for s in response["sections"] or []]
    lines = (response.get("message") or "").split("\n")
    localized = [_localize_line(language, ln) for ln in lines]
    message = "\n".join(localized)
    response["message"] = message
    response["answer"] = message
    for output in response.get("outputs", {}).get("alerts") or []:
        title = output.get("title") or ""
        key = _ALERT_TITLE_KEY.get(title)
        if key:
            output["title"] = t(language, key)
            if output.get("kind") == "restriction" and output.get("count"):
                pass
    return response


_ALERT_TITLE_KEY = {
    "Active safety constraint": "alert.title.restriction",
    "Active dynamic restrictions": "alert.title.dynamic_restriction",
    "Route intersects restricted area": "alert.title.route_restriction",
    "Inside a static marine geofence": "alert.title.geofence",
    "Data quality": "alert.title.data_quality",
}