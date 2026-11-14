import { useEffect, useState } from "react";

// Farmer-page text in English, Sinhala and Tamil. Choice comes from ?lang=si|ta|en, then the last choice on this phone.
// Sinhala and Tamil drafts should be checked by a native speaker (ideally an agricultural instructor) before field use.
export const LANGS = { en: "English", si: "සිංහල", ta: "தமிழ்" };

const T = {
  en: {
    title: "What should I plant?",
    where: "Where is your field?", change: "Change",
    waterQ: "Where does your water come from?", rain: "Rain only", tank: "Tank or canal", well: "Well",
    goalQ: "What do you want most?", income: "More income", water: "Save water", soil: "Better soil", safe: "Low risk",
    show: "Show my best crops", pickFirst: "Choose your place first",
    sample: "Test version: money figures are examples, not real yet.",
    prices: "Money figures use 2021 farm-gate prices and typical costs. Your own prices and costs may differ.",
    bestFor: (p) => `Best choices for ${p}`, best: "Best match",
    maha: "Maha (Oct to Mar)", yala: "Yala (Apr to Sep)",
    perYear: "per hectare a year", to: "to", aYear: "a year",
    lessWater: (n) => `Uses about ${n} % less water than what most farmers here grow.`,
    legume: "The bean crop feeds the soil, so the next crop needs less urea.",
    more: (m) => `About ${m} more per hectare a year than what most farmers here grow.`,
    fits: "Suits the rain, soil and prices in your area.",
    care: "⚠️ Needs care: water may run short in some years.",
    saved: "✓ Saved. Your agriculture officer can now see your plan.", grow: "I will grow this",
    now: "What most farmers here grow now:",
    foot: "This is advice from weather and soil data. Ask your Agricultural Instructor before you decide.",
    detail: "More detail and more options →",
    gps: "📍 Use my location", finding: "Finding you…", or: "or",
    search: "Type your district, town or village", district: "district", myLoc: (d) => `My location (${d})`,
    noGps: "This phone or browser cannot give a location. Type your district instead.",
    outside: "Your location is outside Sri Lanka. Type your district instead.",
    refused: "Location permission was refused. Allow it, or type your district.",
    gpsFail: "Could not get a location. Type your district instead.",
    tagline: "Crop advice for your field",
    disclaimer: "Decision support only. It does not replace farmer judgment or the advice of agricultural officers.",
    offline: "Offline: using saved data",
  },
  si: {
    title: "මම මොනවද වගා කරන්න ඕනේ?",
    where: "ඔබේ කුඹුර / ඉඩම තියෙන්නේ කොහෙද?", change: "වෙනස් කරන්න",
    waterQ: "ඔබට වතුර ලැබෙන්නේ කොහෙන්ද?", rain: "වැසි ජලය පමණයි", tank: "වැව හෝ ඇළ", well: "ළිඳ",
    goalQ: "ඔබට වැඩියෙන්ම ඕනේ මොකක්ද?", income: "වැඩි ආදායමක්", water: "වතුර ඉතිරි කිරීම", soil: "හොඳ පස", safe: "අඩු අවදානම",
    show: "මට හොඳම බෝග පෙන්වන්න", pickFirst: "මුලින්ම ඔබේ ප්‍රදේශය තෝරන්න",
    sample: "පරීක්ෂණ සංස්කරණය: මුදල් ගණන් උදාහරණ පමණයි.",
    prices: "මුදල් ගණන් 2021 ගොවිපොළ මිල සහ සාමාන්‍ය වියදම් අනුවයි. ඔබේ මිල සහ වියදම් වෙනස් විය හැක.",
    bestFor: (p) => `${p} සඳහා හොඳම තේරීම්`, best: "හොඳම තේරීම",
    maha: "මහ කන්නය (ඔක්. - මාර්.)", yala: "යල කන්නය (අප්‍රේ. - සැප්.)",
    perYear: "හෙක්ටයාරයකට වසරකට", to: "සිට", aYear: "වසරකට",
    lessWater: (n) => `මෙහි බොහෝ ගොවීන් වගා කරන බෝගවලට වඩා ආසන්න වශයෙන් ${n} % අඩුවෙන් වතුර යයි.`,
    legume: "රනිල බෝගය පසට පෝෂණය දෙන නිසා ඊළඟ බෝගයට යූරියා අඩුවෙන් ඕනේ.",
    more: (m) => `මෙහි බොහෝ ගොවීන් වගා කරන බෝගවලට වඩා හෙක්ටයාරයකට වසරකට ආසන්න වශයෙන් ${m} වැඩියෙන්.`,
    fits: "ඔබේ ප්‍රදේශයේ වැසි, පස සහ මිල ගණන්වලට ගැළපේ.",
    care: "⚠️ සැලකිලිමත් වන්න: සමහර අවුරුදුවල වතුර මදි විය හැක.",
    saved: "✓ සුරැකිණි. ඔබේ කෘෂිකර්ම නිලධාරියාට දැන් ඔබේ සැලැස්ම බලන්න පුළුවන්.", grow: "මම මෙය වගා කරනවා",
    now: "මෙහි බොහෝ ගොවීන් දැන් වගා කරන්නේ:",
    foot: "මෙය කාලගුණ සහ පස දත්ත මත පදනම් වූ උපදෙසක්. තීරණය කිරීමට පෙර ඔබේ කෘෂිකර්ම උපදේශකගෙන් අහන්න.",
    detail: "වැඩි විස්තර සහ තවත් තේරීම් →",
    gps: "📍 මගේ ස්ථානය භාවිතා කරන්න", finding: "ඔබව සොයමින්…", or: "හෝ",
    search: "ඔබේ දිස්ත්‍රික්කය, නගරය හෝ ගම ටයිප් කරන්න", district: "දිස්ත්‍රික්කය", myLoc: (d) => `මගේ ස්ථානය (${d})`,
    noGps: "මෙම දුරකථනයට ස්ථානය ලබා දිය නොහැක. ඔබේ දිස්ත්‍රික්කය ටයිප් කරන්න.",
    outside: "ඔබේ ස්ථානය ශ්‍රී ලංකාවෙන් පිටතයි. ඔබේ දිස්ත්‍රික්කය ටයිප් කරන්න.",
    refused: "ස්ථාන අවසරය ප්‍රතික්ෂේප විය. අවසර දෙන්න, නැත්නම් දිස්ත්‍රික්කය ටයිප් කරන්න.",
    gpsFail: "ස්ථානය ලබා ගත නොහැකි විය. ඔබේ දිස්ත්‍රික්කය ටයිප් කරන්න.",
    tagline: "ඔබේ කුඹුරට බෝග උපදෙස්",
    disclaimer: "මෙය තීරණ ගැනීමට උදව්වක් පමණයි. ගොවියාගේ විනිශ්චය හෝ කෘෂිකර්ම නිලධාරීන්ගේ උපදෙස් වෙනුවට නොවේ.",
    offline: "අන්තර්ජාලය නැත: සුරැකි දත්ත භාවිතා කරයි",
  },
  ta: {
    title: "நான் என்ன பயிரிட வேண்டும்?",
    where: "உங்கள் வயல் எங்கே உள்ளது?", change: "மாற்று",
    waterQ: "உங்களுக்கு நீர் எங்கிருந்து கிடைக்கிறது?", rain: "மழை நீர் மட்டும்", tank: "குளம் அல்லது கால்வாய்", well: "கிணறு",
    goalQ: "உங்களுக்கு மிக முக்கியமானது எது?", income: "அதிக வருமானம்", water: "நீர் சேமிப்பு", soil: "நல்ல மண்", safe: "குறைந்த ஆபத்து",
    show: "எனக்கு சிறந்த பயிர்களைக் காட்டு", pickFirst: "முதலில் உங்கள் இடத்தைத் தேர்ந்தெடுக்கவும்",
    sample: "சோதனைப் பதிப்பு: பணத் தொகைகள் உதாரணங்கள் மட்டுமே.",
    prices: "பணத் தொகைகள் 2021 பண்ணை விலைகள் மற்றும் வழக்கமான செலவுகளின் அடிப்படையில். உங்கள் விலைகளும் செலவுகளும் வேறுபடலாம்.",
    bestFor: (p) => `${p} இற்கான சிறந்த தேர்வுகள்`, best: "சிறந்த தேர்வு",
    maha: "பெரும்போகம் (ஒக். - மார்.)", yala: "சிறுபோகம் (ஏப். - செப்.)",
    perYear: "ஒரு ஹெக்டேருக்கு ஆண்டுக்கு", to: "முதல்", aYear: "ஆண்டுக்கு",
    lessWater: (n) => `இங்குள்ள பெரும்பாலான விவசாயிகள் பயிரிடுவதை விட சுமார் ${n} % குறைவான நீர் தேவை.`,
    legume: "பயறு வகைப் பயிர் மண்ணை வளப்படுத்துவதால், அடுத்த பயிருக்கு குறைந்த யூரியா போதும்.",
    more: (m) => `இங்குள்ள பெரும்பாலான விவசாயிகள் பயிரிடுவதை விட ஹெக்டேருக்கு ஆண்டுக்கு சுமார் ${m} அதிகம்.`,
    fits: "உங்கள் பகுதியின் மழை, மண் மற்றும் விலைகளுக்கு ஏற்றது.",
    care: "⚠️ கவனம்: சில ஆண்டுகளில் நீர் பற்றாக்குறை ஏற்படலாம்.",
    saved: "✓ சேமிக்கப்பட்டது. உங்கள் விவசாய அலுவலர் இப்போது உங்கள் திட்டத்தைப் பார்க்கலாம்.", grow: "நான் இதைப் பயிரிடுவேன்",
    now: "இங்குள்ள பெரும்பாலான விவசாயிகள் இப்போது பயிரிடுவது:",
    foot: "இது வானிலை மற்றும் மண் தரவுகளின் அடிப்படையிலான ஆலோசனை. முடிவெடுக்கும் முன் உங்கள் விவசாயப் போதனாசிரியரிடம் கேளுங்கள்.",
    detail: "மேலும் விவரங்கள் மற்றும் தேர்வுகள் →",
    gps: "📍 எனது இருப்பிடத்தைப் பயன்படுத்து", finding: "உங்களைத் தேடுகிறது…", or: "அல்லது",
    search: "உங்கள் மாவட்டம், நகரம் அல்லது கிராமத்தை எழுதுங்கள்", district: "மாவட்டம்", myLoc: (d) => `எனது இருப்பிடம் (${d})`,
    noGps: "இந்தத் தொலைபேசியால் இருப்பிடத்தைத் தர முடியாது. உங்கள் மாவட்டத்தை எழுதுங்கள்.",
    outside: "உங்கள் இருப்பிடம் இலங்கைக்கு வெளியே உள்ளது. உங்கள் மாவட்டத்தை எழுதுங்கள்.",
    refused: "இருப்பிட அனுமதி மறுக்கப்பட்டது. அனுமதி தாருங்கள், அல்லது மாவட்டத்தை எழுதுங்கள்.",
    gpsFail: "இருப்பிடத்தைப் பெற முடியவில்லை. உங்கள் மாவட்டத்தை எழுதுங்கள்.",
    tagline: "உங்கள் வயலுக்கான பயிர் ஆலோசனை",
    disclaimer: "இது முடிவெடுக்க உதவும் கருவி மட்டுமே. விவசாயியின் முடிவையோ விவசாய அலுவலர்களின் ஆலோசனையையோ மாற்றாது.",
    offline: "இணைய இணைப்பு இல்லை: சேமித்த தரவு பயன்படுகிறது",
  },
};

const CROPS = {
  si: { paddy: "වී", maize: "බඩ ඉරිඟු", greengram: "මුං ඇට", cowpea: "කව්පි", bigonion: "ලොකු ළූණු", chilli: "අමු මිරිස්", fallow: "කුඹුර විවේක කරන්න" },
  ta: { paddy: "நெல்", maize: "சோளம்", greengram: "பாசிப்பயறு", cowpea: "கௌபி", bigonion: "பெரிய வெங்காயம்", chilli: "பச்சை மிளகாய்", fallow: "நிலத்தை ஓய்வில் விடுங்கள்" },
};
const DISTRICTS = {
  si: { colombo: "කොළඹ", gampaha: "ගම්පහ", kalutara: "කළුතර", kandy: "මහනුවර", matale: "මාතලේ", "nuwara-eliya": "නුවරඑළිය", galle: "ගාල්ල", matara: "මාතර", hambantota: "හම්බන්තොට", jaffna: "යාපනය", kilinochchi: "කිලිනොච්චිය", mannar: "මන්නාරම", vavuniya: "වවුනියාව", mullaitivu: "මුලතිව්", batticaloa: "මඩකලපුව", ampara: "අම්පාර", trincomalee: "ත්‍රිකුණාමලය", kurunegala: "කුරුණෑගල", puttalam: "පුත්තලම", anuradhapura: "අනුරාධපුරය", polonnaruwa: "පොළොන්නරුව", badulla: "බදුල්ල", monaragala: "මොණරාගල", ratnapura: "රත්නපුරය", kegalle: "කෑගල්ල" },
  ta: { colombo: "கொழும்பு", gampaha: "கம்பஹா", kalutara: "களுத்துறை", kandy: "கண்டி", matale: "மாத்தளை", "nuwara-eliya": "நுவரெலியா", galle: "காலி", matara: "மாத்தறை", hambantota: "அம்பாந்தோட்டை", jaffna: "யாழ்ப்பாணம்", kilinochchi: "கிளிநொச்சி", mannar: "மன்னார்", vavuniya: "வவுனியா", mullaitivu: "முல்லைத்தீவு", batticaloa: "மட்டக்களப்பு", ampara: "அம்பாறை", trincomalee: "திருகோணமலை", kurunegala: "குருநாகல்", puttalam: "புத்தளம்", anuradhapura: "அனுராதபுரம்", polonnaruwa: "பொலன்னறுவை", badulla: "பதுளை", monaragala: "மொனராகலை", ratnapura: "இரத்தினபுரி", kegalle: "கேகாலை" },
};

function initial() {
  const q = new URLSearchParams(location.search).get("lang");
  if (q && T[q]) return q;
  try { const s = localStorage.getItem("fs-lang"); if (s && T[s]) return s; } catch { /* storage blocked */ }
  return "en";
}

let current = initial();
const listeners = new Set();
export function setLang(l) {
  current = l;
  try { localStorage.setItem("fs-lang", l); } catch { /* storage blocked */ }
  document.documentElement.lang = l;
  listeners.forEach((f) => f(l));
}

/** Returns { lang, t, crop(id, englishName), district(id, englishName) } and re-renders on language change. */
export function useLang() {
  const [lang, set] = useState(current);
  useEffect(() => { listeners.add(set); document.documentElement.lang = current; return () => listeners.delete(set); }, []);
  return {
    lang,
    t: T[lang],
    crop: (id, en) => CROPS[lang]?.[id] || en,
    district: (id, en) => DISTRICTS[lang]?.[id] || en,
  };
}

export function LangSwitch() {
  const { lang } = useLang();
  return (
    <div className="langs" role="group" aria-label="Language">
      {Object.entries(LANGS).map(([k, v]) => <button key={k} lang={k} className={lang === k ? "on" : ""} aria-pressed={lang === k} onClick={() => setLang(k)}>{v}</button>)}
    </div>
  );
}
