// ============================================================================
// ORCA — Ocean Reasoning with Collaborative Agent
// Production Mock Dataset & Operational Telemetry
// ============================================================================

export const navGroups = [
  {
    label: 'CORE OPERATIONS',
    collapsible: false,
    items: [
      { label: 'Dashboard', path: '/dashboard', icon: 'LayoutDashboard', badge: null },
      { label: 'AI Copilot', path: '/ai-copilot', icon: 'Bot', badge: 'AI' },
      { label: 'Fishing', path: '/fishing', icon: 'Fish', badge: '7 PFZ' },
      { label: 'Safety', path: '/safety', icon: 'ShieldAlert', badge: null },
      { label: 'Route Planner', path: '/routes', icon: 'Route', badge: null },
      { label: 'Alerts', path: '/alerts', icon: 'Bell', badge: '3' },
    ]
  },
  {
    label: 'TOOLS & INTELLIGENCE',
    collapsible: false,
    items: [
      { label: 'Marine Map', path: '/marine-map', icon: 'Map', badge: 'LIVE' },
      { label: 'Multilingual', path: '/multilingual', icon: 'Globe', badge: null },
      { label: 'Knowledge Center', path: '/knowledge', icon: 'BookOpen', badge: null },
      { label: 'Scenario Lab', path: '/scenarios', icon: 'FlaskConical', badge: null },
      { label: 'Analytics', path: '/analytics', icon: 'BarChart3', badge: null },
    ]
  },
  {
    label: 'TECHNICAL',
    collapsible: true,
    items: [
      { label: 'ML Governance', path: '/ml-governance', icon: 'BrainCircuit', badge: null },
      { label: 'System Health', path: '/system-health', icon: 'ServerCog', badge: '99%' },
      { label: 'Workflow', path: '/workflow', icon: 'GitBranch', badge: null },
      { label: 'Mobile View', path: '/mobile', icon: 'Smartphone', badge: null },
    ]
  }
];

// Flat list kept for any code that imports navItems directly
export const navItems = navGroups.flatMap(g => g.items);

export const conditions = [
  ['Sea Surface Temp (SST)', '28.7 °C', '+0.4° vs avg', 'normal'],
  ['Chlorophyll-a', '0.82 mg/m³', 'High Bloom', 'safe'],
  ['Significant Wave Height', '1.4 m', 'Moderate Swell', 'caution'],
  ['Surface Wind', '18 km/h ENE', 'Gusts 24 km/h', 'normal'],
  ['Ocean Surface Current', '0.6 m/s @ 184°', 'Southerly Drift', 'normal'],
  ['Tidal Phase', 'High Tide (1.2 m)', 'Peak at 22:15 IST', 'normal'],
  ['Barometric Pressure', '1009.4 hPa', 'Stable', 'normal'],
  ['Underwater Visibility', '8.5 m', 'Clear Coastal', 'safe']
];

export const alerts = [
  {
    id: 'ALT-2026-089',
    title: 'High Swell & Wave Warning',
    place: 'Lakshadweep Sea & South Kerala Coast',
    time: '15 min ago',
    level: 'HIGH',
    category: 'Weather',
    source: 'INCOIS Marine Forecast',
    validTill: '06 Sep 06:00 IST',
    desc: 'Rough sea conditions with waves reaching 2.4m to 2.8m expected. Traditional non-motorized craft advised not to venture beyond 12 NM.',
    coordinates: '09°42\'N, 075°50\'E',
    actionRequired: 'Avoid deep seaward departure for vessels under 15m.'
  },
  {
    id: 'ALT-2026-088',
    title: 'Temporary Navigation Restriction (Firing Exercise)',
    place: 'Sector Bravo — 12 km East-Southeast of Kochi',
    time: '3 hours ago',
    level: 'MEDIUM',
    category: 'Geofence',
    source: 'NAVAREA VIII Bulletin #0482',
    validTill: '05 Sep 18:00 IST',
    desc: 'Joint naval defense exercise underway. Commercial and artisanal fishing prohibited in designated box 09°50\'N to 10°05\'N.',
    coordinates: '09°58\'N, 076°22\'E',
    actionRequired: 'Divert via Route B (Northwest corridor).'
  },
  {
    id: 'ALT-2026-087',
    title: 'Coastal Squall & Lightning Advisory',
    place: 'Kerala Inshore Waters (Kochi to Alappuzha)',
    time: '5 hours ago',
    level: 'LOW',
    category: 'Safety',
    source: 'IMD Doppler Radar Cochin',
    validTill: '05 Sep 12:00 IST',
    desc: 'Isolated convective clouds detected. Surface gusts up to 35 km/h with localized lightning potential.',
    coordinates: '09°52\'N, 076°12\'E',
    actionRequired: 'Maintain VHF Channel 16 listening watch.'
  },
  {
    id: 'ALT-2026-086',
    title: 'PFZ Thermal Front Update',
    place: 'Southwest Offshore Sector',
    time: '12 hours ago',
    level: 'INFO',
    category: 'Fishing',
    source: 'ISRO MOSDAC / INCOIS',
    validTill: '06 Sep 12:00 IST',
    desc: 'Strong sea surface temperature gradient observed 14km SW of Kochi. Optimal pelagic aggregation expected.',
    coordinates: '09°48\'N, 076°08\'E',
    actionRequired: 'Inspect PFZ-01 and PFZ-02 coordinates.'
  },
  {
    id: 'ALT-2026-085',
    title: 'Telemetry Buoy AD04 Recalibration',
    place: 'Deep Sea Moored Buoy Network',
    time: '18 hours ago',
    level: 'INFO',
    category: 'System',
    source: 'NIOT Chennai Telemetry',
    validTill: '05 Sep 23:59 IST',
    desc: 'Scheduled sensor calibration completed. Salinity and acoustic Doppler current profiler operational.',
    coordinates: '10°10\'N, 075°30\'E',
    actionRequired: 'No action required. Telemetry healthy.'
  }
];

export const pfzZones = [
  {
    id: 'PFZ-01',
    name: 'Kochi Offshore Thermal Front',
    distance: '14.2 km',
    bearing: '235° SW',
    depth: '42 m',
    potential: 'High',
    catchIndex: '92/100',
    sst: '28.4 °C',
    chlorophyll: '0.88 mg/m³',
    targetSpecies: ['Yellowfin Tuna', 'Indian Mackerel', 'Skipjack'],
    risk: 'Low',
    restrictions: 'None',
    window: '04:30 – 09:30 IST',
    coordinates: '09°52\'14"N, 076°08\'32"E',
    recommended: true
  },
  {
    id: 'PFZ-02',
    name: 'Vypin Deep Upwelling Zone',
    distance: '21.5 km',
    bearing: '270° W',
    depth: '58 m',
    potential: 'High',
    catchIndex: '88/100',
    sst: '28.1 °C',
    chlorophyll: '0.79 mg/m³',
    targetSpecies: ['Sardine', 'Anchovy', 'Seer Fish'],
    risk: 'Low',
    restrictions: 'None',
    window: '05:00 – 10:30 IST',
    coordinates: '10°01\'45"N, 076°02\'10"E',
    recommended: false
  },
  {
    id: 'PFZ-03',
    name: 'Alappuzha Shelf Break',
    distance: '31.8 km',
    bearing: '195° SSW',
    depth: '75 m',
    potential: 'Medium',
    catchIndex: '74/100',
    sst: '27.8 °C',
    chlorophyll: '0.64 mg/m³',
    targetSpecies: ['Carangids', 'Ribbonfish', 'Tuna'],
    risk: 'Low',
    restrictions: 'None',
    window: '06:00 – 12:00 IST',
    coordinates: '09°34\'18"N, 076°11\'50"E',
    recommended: false
  },
  {
    id: 'PFZ-04',
    name: 'Chellanam Canyon Approach',
    distance: '42.0 km',
    bearing: '215° SW',
    depth: '110 m',
    potential: 'Medium',
    catchIndex: '68/100',
    sst: '27.5 °C',
    chlorophyll: '0.52 mg/m³',
    targetSpecies: ['Mahi Mahi', 'Squid', 'Tuna'],
    risk: 'Medium',
    restrictions: 'Bordering Naval Sector',
    window: '05:30 – 11:00 IST',
    coordinates: '09°28\'40"N, 075°58\'15"E',
    recommended: false
  },
  {
    id: 'PFZ-05',
    name: 'Munambam Outer Trench',
    distance: '56.4 km',
    bearing: '310° NW',
    depth: '160 m',
    potential: 'Low',
    catchIndex: '51/100',
    sst: '27.2 °C',
    chlorophyll: '0.41 mg/m³',
    targetSpecies: ['Snapper', 'Grouper', 'Reef Fish'],
    risk: 'Medium',
    restrictions: 'Elevated Swell Zone',
    window: '07:00 – 13:00 IST',
    coordinates: '10°18\'12"N, 075°45\'30"E',
    recommended: false
  },
  {
    id: 'PFZ-06',
    name: 'Malabar Deep Continental Margin',
    distance: '68.0 km',
    bearing: '300° WNW',
    depth: '320 m',
    potential: 'Low',
    catchIndex: '42/100',
    sst: '27.0 °C',
    chlorophyll: '0.38 mg/m³',
    targetSpecies: ['Oceanic Squid', 'Swordfish'],
    risk: 'Low',
    restrictions: 'None',
    window: '06:00 – 14:00 IST',
    coordinates: '10°24\'05"N, 075°32\'18"E',
    recommended: false
  },
  {
    id: 'PFZ-07',
    name: 'Lakshadweep Basin Edge',
    distance: '74.5 km',
    bearing: '255° WSW',
    depth: '550 m',
    potential: 'Low',
    catchIndex: '36/100',
    sst: '26.8 °C',
    chlorophyll: '0.32 mg/m³',
    targetSpecies: ['Pelagic Shark (Protected)', 'Skipjack'],
    risk: 'Low',
    restrictions: 'Protected Species Notice',
    window: '08:00 – 15:00 IST',
    coordinates: '09°46\'50"N, 075°24\'40"E',
    recommended: false
  }
];

export const routesData = [
  {
    id: 'route-b',
    name: 'Route B — Northwest Fairway (Recommended)',
    distance: '42.8 km (23.1 NM)',
    duration: '2h 14m @ 10.4 kts',
    risk: 'LOW',
    riskScore: 0.24,
    color: '#10B981',
    highWaveAreas: 0,
    restrictedZones: 0,
    fuelEstimate: '64 Litres HSD',
    waypoints: [
      { name: 'WP-01: Kochi Fishing Harbour', lat: '09°58.2\'N', lon: '076°14.4\'E', depth: '12m', status: 'Clear' },
      { name: 'WP-02: Cochin Fairway Buoy', lat: '09°58.8\'N', lon: '076°10.2\'E', depth: '24m', status: 'Nav Buoy' },
      { name: 'WP-03: Northern Deep Water Track', lat: '09°56.1\'N', lon: '076°05.4\'E', depth: '40m', status: 'Safe Channel' },
      { name: 'WP-04: PFZ-01 Entry Point', lat: '09°52.2\'N', lon: '076°08.5\'E', depth: '42m', status: 'Destination' }
    ],
    summary: 'Optimized routing through certified navigational fairways, bypassing high-wave coastal breakers and keeping 4.2 km clear of the active naval sector.'
  },
  {
    id: 'route-a',
    name: 'Route A — Direct Line (Shortest)',
    distance: '38.2 km (20.6 NM)',
    duration: '1h 56m @ 10.8 kts',
    risk: 'HIGH',
    riskScore: 0.78,
    color: '#EF4444',
    highWaveAreas: 1,
    restrictedZones: 1,
    fuelEstimate: '58 Litres HSD',
    waypoints: [
      { name: 'WP-01: Kochi Fishing Harbour', lat: '09°58.2\'N', lon: '076°14.4\'E', depth: '12m', status: 'Clear' },
      { name: 'WP-02: Naval Sector Edge Cross', lat: '09°54.5\'N', lon: '076°11.0\'E', depth: '32m', status: 'RESTRICTED HAZARD' },
      { name: 'WP-03: Swell Convergence Zone', lat: '09°53.1\'N', lon: '076°09.8\'E', depth: '38m', status: '2.4m Waves' },
      { name: 'WP-04: PFZ-01 Entry Point', lat: '09°52.2\'N', lon: '076°08.5\'E', depth: '42m', status: 'Destination' }
    ],
    summary: 'Saves 4.6 km but clips the eastern corner of NAVAREA VIII restricted exercise zone and intersects a 2.4m wave height convergence area. NOT RECOMMENDED.'
  },
  {
    id: 'route-c',
    name: 'Route C — Southern Offshore Detour (Alternative)',
    distance: '56.1 km (30.3 NM)',
    duration: '2h 55m @ 10.2 kts',
    risk: 'LOW',
    riskScore: 0.18,
    color: '#0099DD',
    highWaveAreas: 0,
    restrictedZones: 0,
    fuelEstimate: '85 Litres HSD',
    waypoints: [
      { name: 'WP-01: Kochi Fishing Harbour', lat: '09°58.2\'N', lon: '076°14.4\'E', depth: '12m', status: 'Clear' },
      { name: 'WP-02: Southern Inshore Lane', lat: '09°48.0\'N', lon: '076°15.1\'E', depth: '28m', status: 'Clear' },
      { name: 'WP-03: Westward Deep Leg', lat: '09°46.5\'N', lon: '076°07.2\'E', depth: '48m', status: 'Clear' },
      { name: 'WP-04: PFZ-01 Approach North', lat: '09°52.2\'N', lon: '076°08.5\'E', depth: '42m', status: 'Destination' }
    ],
    summary: 'Widest safety buffer. Completely clear of all naval and coastal traffic. Consumes approx 21 Litres more fuel.'
  }
];

export const knowledgeDocs = [
  {
    id: 'doc-01',
    title: 'Marine Fishing Regulation Act (MFRA) 2024 Amendments',
    source: 'Department of Fisheries, Ministry of Earth Sciences, Govt of India',
    updated: '04 Sep 2026',
    category: 'Regulations',
    relevance: '98%',
    readTime: '8 min read',
    summary: 'Updated guidelines on motorized craft limits, automated transponder mandates, safety gear checklists, and monsoon seasonal ban boundaries.'
  },
  {
    id: 'doc-02',
    title: 'Kerala Coastal Operational Fishery Advisory Bulletin #142',
    source: 'INCOIS Ocean State Forecast Centre',
    updated: '04 Sep 2026',
    category: 'Advisories',
    relevance: '94%',
    readTime: '4 min read',
    summary: 'Bathymetric upwelling observations along the Malabar shelf, chlorophyll bloom tracking, and sea surface temperature fronts for the current moon phase.'
  },
  {
    id: 'doc-03',
    title: 'Sustainable Pelagic Harvesting & Bycatch Mitigation Guidelines',
    source: 'Food and Agriculture Organization (FAO) / CMFRI Cochin',
    updated: '20 Feb 2026',
    category: 'Research',
    relevance: '91%',
    readTime: '12 min read',
    summary: 'Science-backed fishing strategies to preserve juvenile mackerel stocks and avoid protected marine turtle corridors in southwest inshore waters.'
  },
  {
    id: 'doc-04',
    title: 'National Cyclone & Severe Weather Preparedness Protocol for Small Craft',
    source: 'National Disaster Management Authority (NDMA)',
    updated: '10 Jan 2026',
    category: 'Reports',
    relevance: '88%',
    readTime: '15 min read',
    summary: 'Emergency evacuation procedures, distress signaling on VHF Ch 16, safe harbor refuge points along Kerala coast, and communication loss protocols.'
  },
  {
    id: 'doc-05',
    title: 'Indian Maritime Boundary Line (IMBL) & Continental Shelf Coordinates',
    source: 'National Hydrographic Office (NHO) Dehradun',
    updated: '15 May 2026',
    category: 'Regulations',
    relevance: '86%',
    readTime: '6 min read',
    summary: 'Official nautical charts and geodetic coordinate benchmarks for territorial waters (12 NM), contiguous zone (24 NM), and Exclusive Economic Zone (EEZ 200 NM).'
  }
];

export const systemServices = [
  { name: 'REST API Gateway (FastAPI)', status: 'HEALTHY', latency: '42 ms', uptime: '99.99%', version: 'v2.8.4' },
  { name: 'Database (PostgreSQL / TimescaleDB)', status: 'HEALTHY', latency: '18 ms', uptime: '99.98%', version: 'v16.2' },
  { name: 'Geospatial Spatial Engine (PostGIS)', status: 'HEALTHY', latency: '34 ms', uptime: '99.99%', version: 'v3.4.1' },
  { name: 'MCP Agentic Tools Cluster', status: 'HEALTHY', latency: '68 ms', uptime: '99.95%', version: 'v1.4.0' },
  { name: 'Cognitive Orchestrator', status: 'HEALTHY', latency: '124 ms', uptime: '99.97%', version: 'v3.1.0' },
  { name: 'LLM Inference Gateway (FloatChat Engine)', status: 'HEALTHY', latency: '380 ms', uptime: '99.92%', version: 'Claude 3.5' },
  { name: 'Vector Knowledge Store (pgvector RAG)', status: 'HEALTHY', latency: '52 ms', uptime: '99.98%', version: 'v0.7.0' },
  { name: 'Marine ML Inference Engine (Triton)', status: 'HEALTHY', latency: '89 ms', uptime: '99.96%', version: 'v2.4.0' },
  { name: 'Data Ingestion Telemetry (INCOIS / IMD)', status: 'HEALTHY', latency: '115 ms', uptime: '99.99%', version: 'Live Feeds' },
  { name: 'WebSocket Realtime Broadcast Bus', status: 'HEALTHY', latency: '12 ms', uptime: '99.99%', version: 'Socket.IO' }
];

export const multilingualTranslations = {
  en: {
    name: 'English',
    nativeName: 'English (EN)',
    query: 'Is it safe to fish near Kochi tomorrow morning?',
    time: '9:32 PM IST',
    riskLevel: 'MODERATE RISK',
    riskScore: '0.61',
    verdict: 'Sea conditions near Kochi tomorrow morning are evaluated as MODERATE RISK for fishing vessels under 15m.',
    bullets: [
      'Wave height: 1.6 – 1.8 m (moderate swell with morning peak)',
      'Wind velocity: 18 – 23 km/h ENE (safe navigational envelope)',
      'Cyclone status: No active depressions detected in Arabian Sea',
      'Naval restriction: Temporary firing sector 12 km east until 18:00',
      'Fishing potential: Excellent pelagic fronts at PFZ-01 (14 km SW)'
    ],
    audioTitle: 'Audio Bulletin — English Coastal Broadcast',
    audioDuration: '0:42',
    disclaimer: 'Official decision support advisory based on fused INCOIS, IMD, and NAVAREA VIII telemetry.'
  },
  hi: {
    name: 'Hindi',
    nativeName: 'हिन्दी (HI)',
    query: 'क्या कल सुबह कोच्चि के पास मछली पकड़ने जाना सुरक्षित है?',
    time: 'रात 9:32 IST',
    riskLevel: 'मध्यम जोखिम (MODERATE RISK)',
    riskScore: '0.61',
    verdict: 'कल सुबह कोच्चि तट के पास समुद्र की स्थिति 15 मीटर से छोटी नौकाओं के लिए मध्यम जोखिम वाली आंकी गई है।',
    bullets: [
      'लहरों की ऊंचाई: 1.6 – 1.8 मीटर (सुबह के समय मध्यम उछाल)',
      'हवा की गति: 18 – 23 किमी/घंटा पूर्व-उत्तर-पूर्व (सुरक्षित सीमा में)',
      'चक्रवात स्थिति: अरब सागर में कोई सक्रिय चक्रवाती दबाव नहीं',
      'नौसेना प्रतिबंध: कोच्चि के पूर्व 12 किमी में शाम 18:00 बजे तक अस्थायी अभ्यास क्षेत्र',
      'मत्स्य पालन संभावना: PFZ-01 (14 किमी दक्षिण-पश्चिम) पर प्रचुर मछली क्षेत्र'
    ],
    audioTitle: 'ऑडियो बुलेटिन — हिन्दी तटीय प्रसारण',
    audioDuration: '0:48',
    disclaimer: 'INCOIS, IMD एवं NAVAREA VIII डेटा पर आधारित आधिकारिक निर्णय सहायता बुलेटिन।'
  },
  ml: {
    name: 'Malayalam',
    nativeName: 'മലയാളം (ML)',
    query: 'നാളെ രാവിലെ കൊച്ചിക്ക് സമീപം മത്സ്യബന്ധനത്തിന് പോകുന്നത് സുരക്ഷിതമാണോ?',
    time: 'രാത്രി 9:32 IST',
    riskLevel: 'മിതമായ അപകടസാധ്യത (MODERATE RISK)',
    riskScore: '0.61',
    verdict: 'നാളെ രാവിലെ കൊച്ചി തീരത്ത് 15 മീറ്ററിൽ താഴെയുള്ള വള്ളങ്ങൾക്ക് കടൽസ്ഥിതി മിതമായ അപകടസാധ്യതയുള്ളതായി കണക്കാക്കുന്നു.',
    bullets: [
      'തിരമാല ഉയരം: 1.6 – 1.8 മീറ്റർ (രാവിലെ ഉയർന്ന തിരമാലകൾക്ക് സാധ്യത)',
      'കാറ്റിന്റെ വേഗത: 18 – 23 കി.മീ/മണിക്കൂർ കിഴക്ക്-വടക്കുകിഴക്ക് (നിയന്ത്രണ വിധേയം)',
      'ചുഴലിക്കാറ്റ് മുന്നറിയിപ്പ്: അറബിക്കടലിൽ നിലവിൽ ന്യൂനമർദ്ദ ഭീഷണിയില്ല',
      'നാവികസേന നിയന്ത്രണം: കൊച്ചിക്ക് കിഴക്ക് 12 കി.മീ ദൂരത്തിൽ വൈകുന്നേരം 6 വരെ നിയന്ത്രിത മേഖല',
      'മത്സ്യലഭ്യത: PFZ-01 മേഖലയിൽ (14 കി.മീ തെക്കുപടിഞ്ഞാറ്) മികച്ച സാധ്യത'
    ],
    audioTitle: 'ഓഡിയോ ബുള്ളറ്റിൻ — മലയാളം തീരദേശ അറിയിപ്പ്',
    audioDuration: '0:45',
    disclaimer: 'ഇൻകോയിസ് (INCOIS), കാലാവസ്ഥാ വകുപ്പ് (IMD) വിവരങ്ങൾ അടിസ്ഥാനമാക്കിയുള്ള ഔദ്യോഗിക അറിയിപ്പ്.'
  },
  ta: {
    name: 'Tamil',
    nativeName: 'தமிழ் (TA)',
    query: 'நாளை காலை கொச்சி அருகே மீன்பிடிக்க செல்வது பாதுகாப்பானதா?',
    time: 'இரவு 9:32 IST',
    riskLevel: 'மிதமான ஆபத்து (MODERATE RISK)',
    riskScore: '0.61',
    verdict: 'நாளை காலை கொச்சி கடற்கரைக்கு அருகில் 15 மீட்டருக்கும் குறைவான படகுகளுக்கு கடல் நிலை மிதமான ஆபத்தானது என கணிக்கப்பட்டுள்ளது.',
    bullets: [
      'அலை உயரம்: 1.6 – 1.8 மீட்டர் (காலை வேளையில் மிதமான அலை வீச்சு)',
      'காற்று வேகம்: 18 – 23 கிமீ/மணி கிழக்கு-வடகிழக்கு (பாதுகாப்பானது)',
      'புயல் எச்சரிக்கை: அரபிக்கடலில் எவ்வித காற்றழுத்த தாழ்வு மண்டலமும் இல்லை',
      'கடற்படை கட்டுப்பாடு: கொச்சிக்கு கிழக்கே 12 கிமீ தொலைவில் மாலை 6 வரை பயிற்சி பகுதி',
      'மீன்வள வாய்ப்பு: PFZ-01 மண்டலத்தில் (14 கிமீ தென்மேற்கு) அதிக மீன்கள் கிடைக்கும்'
    ],
    audioTitle: 'ஆடியோ செய்தி — தமிழ் கடலோர ஒலிபரப்பு',
    audioDuration: '0:47',
    disclaimer: 'INCOIS மற்றும் இந்திய வானிலை ஆய்வு மைய தகவல்களின் அடிப்படையிலான அதிகாரப்பூர்வ அறிக்கை.'
  },
  te: {
    name: 'Telugu',
    nativeName: 'తెలుగు (TE)',
    query: 'రేపు ఉదయం కొచ్చి సమీపంలో చేపల వేటకు వెళ్లడం సురక్షితమేనా?',
    time: 'రాత్రి 9:32 IST',
    riskLevel: 'మధ్యస్థ ప్రమాదం (MODERATE RISK)',
    riskScore: '0.61',
    verdict: 'రేపు ఉదయం కొచ్చి తీరం వెంబడి 15 మీటర్ల కంటే తక్కువ పరిమాణమున్న పడవలకు సముద్ర పరిస్థితులు మధ్యస్థ ప్రమాదకరంగా గుర్తించబడ్డాయి.',
    bullets: [
      'అలల ఎత్తు: 1.6 – 1.8 మీటర్లు (ఉదయం వేళ అలల తాకిడి ఎక్కువ)',
      'గాలి వేగం: గంటకు 18 – 23 కిమీ (సురక్షిత పరిమితిలో)',
      'తుఫాను పరిస్థితి: అరేబియా సముద్రంలో ఎటువంటి తుఫాను హెచ్చరిక లేదు',
      'నౌకాదళ ఆంక్షలు: కొచ్చికి తూర్పున 12 కిమీ దూరంలో సాయంత్రం 6 వరకు నిషిద్ధ ప్రాంతం',
      'చేపల లభ్యత: PFZ-01 జోన్ (14 కిమీ నైరుతి) వద్ద అద్భుతమైన అవకాశాలు'
    ],
    audioTitle: 'ఆడియో బులెటిన్ — తెలుగు తీరప్రాంత సమాచారం',
    audioDuration: '0:46',
    disclaimer: 'INCOIS, IMD అధికారిక సమాచారం ఆధారంగా రూపొందించబడిన విశ్లేషణ.'
  },
  ur: {
    name: 'Urdu',
    nativeName: 'اردو (UR)',
    query: 'کیا کل صبح کوچی کے قریب ماہی گیری کے لیے جانا محفوظ ہے؟',
    time: 'رات 9:32 IST',
    riskLevel: 'معتدل خطرہ (MODERATE RISK)',
    riskScore: '0.61',
    verdict: 'کل صبح کوچی ساحل کے قریب 15 میٹر سے چھوٹی کشتیوں کے لیے سمندری حالات معتدل خطرے کے زمرے میں ہیں۔',
    bullets: [
      'لہروں کی اونچائی: 1.6 سے 1.8 میٹر (صبح کے وقت معتدل اٹھاؤ)',
      'ہوا کی رفتار: 18 سے 23 کلومیٹر فی گھنٹہ (محفوظ حد میں)',
      'طوفان کی صورتحال: بحیرہ عرب میں کوئی فعال طوفانی دباؤ نہیں ہے',
      'بحریہ کی پابندی: کوچی کے مشرق میں 12 کلومیٹر پر شام 6 بجے تک مشقی علاقہ',
      'ماہی گیری کا امکان: PFZ-01 زون (14 کلومیٹر جنوب مغرب) میں وافر امکانات'
    ],
    audioTitle: 'آڈیو بلیٹن — اردو ساحلی نشریات',
    audioDuration: '0:49',
    disclaimer: 'INCOIS اور IMD کے سرکاری ڈیٹا پر مبنی مستند مشاورتی رپورٹ۔'
  },
  mr: {
    name: 'Marathi',
    nativeName: 'मराठी (MR)',
    query: 'उद्या सकाळी कोचीजवळ मासेमारीला जाणे सुरक्षित आहे का?',
    time: 'रात्री ९:३२ IST',
    riskLevel: 'मध्यम जोखीम (MODERATE RISK)',
    riskScore: '0.61',
    verdict: 'उद्या सकाळी कोची किनारपट्टीजवळ समुद्राची परिस्थिती १५ मीटरपेक्षा लहान नौकांसाठी मध्यम जोखीम असलेली मानली गेली आहे.',
    bullets: [
      'लाटांची उंची: १.६ – १.८ मीटर (सकाळच्या वेळी मध्यम उसळीसह वाढ)',
      'वाऱ्याचा वेग: १८ – २३ किमी/तास पूर्व-ईशान्य (सुरक्षित मर्यादेत)',
      'चक्रीवादळ स्थिती: अरबी समुद्रात सध्या कोणताही सक्रिय हवेचा कमी दाबाचा पट्टा नाही',
      'नौदल निर्बंध: कोचीच्या पूर्वेस १२ किमी अंतरावर संध्याकाळी १८:०० वाजेपर्यंत तात्पुरता सराव भाग',
      'मासेमारी संभाव्यता: PFZ-01 विभागात (१४ किमी नैऋत्य) मुबलक पेलाजिक मासेमारीचे क्षेत्र'
    ],
    audioTitle: 'ऑडिओ बुलेटिन — मराठी किनारपट्टी प्रसारण',
    audioDuration: '0:46',
    disclaimer: 'INCOIS, IMD आणि NAVAREA VIII च्या एकत्रित माहितीवर आधारित अधिकृत निर्णय सहाय्यक बुलेटिन.'
  }
};
