"""Keyword / regex-based theme extractor."""

from __future__ import annotations

import re

from stock_themes.models import CompanyProfile, Theme, ExtractionMethod

# theme_name -> list of regex patterns
THEME_KEYWORDS: dict[str, list[str]] = {
    "artificial intelligence": [
        r"\bartificial intelligence\b", r"\bmachine learning\b", r"\bdeep learning\b",
        r"\bneural network", r"\bAI\b(?!r)", r"\bgenerat\w+ AI\b",
    ],
    "cloud computing": [
        r"\bcloud\b.*\b(?:comput|service|platform|infrastructure)\b",
        r"\bSaaS\b", r"\bPaaS\b", r"\bIaaS\b", r"\bcloud-based\b", r"\bcloud-native\b",
    ],
    "mobile": [
        r"\bmobile\b.*\b(?:device|app|platform|phone|commerce)\b", r"\bsmartphone\b",
        r"\biPhone\b", r"\biPad\b", r"\bAndroid\b",
    ],
    "wearable technology": [
        r"\bwearable\b", r"\bsmartwatc\w+\b", r"\bfitness track\w+\b",
        r"\bApple Watch\b", r"\bhealth monitor\w+\b",
    ],
    "cybersecurity": [
        r"\bcybersecurity\b", r"\bcyber\s*security\b", r"\bdata protection\b",
        r"\bencryption\b", r"\bthreat detection\b", r"\bsecurity software\b",
        r"\bzero trust\b",
    ],
    "e-commerce": [
        r"\be-commerce\b", r"\becommerce\b", r"\bonline retail\b",
        r"\bdigital marketplace\b", r"\bonline shopping\b",
    ],
    "fintech": [
        r"\bfintech\b", r"\bdigital payment\b", r"\bmobile payment\b",
        r"\bdigital banking\b", r"\bneobank\b",
    ],
    "electric vehicles": [
        r"\belectric vehicle\b", r"\bEV\b", r"\bbattery\b.*\b(?:electric|vehicle)\b",
        r"\bcharging station\b", r"\bcharging infrastructure\b",
    ],
    "5g": [
        r"\b5G\b", r"\bfifth generation\b", r"\b5G network\b",
        r"\bmmWave\b", r"\bsub-6\b",
    ],
    "big data": [
        r"\bbig data\b", r"\bdata analytics\b", r"\bdata-driven\b",
        r"\bdata warehouse\b", r"\bdata lake\b",
    ],
    "adtech": [
        r"\badvertising technolog\w+\b", r"\badtech\b", r"\bdigital advertising\b",
        r"\bprogrammatic\b", r"\bad exchange\b", r"\btargeted advertising\b",
    ],
    "semiconductors": [
        r"\bsemiconductor\b", r"\bchip\b.*\b(?:design|manufactur|fab)\b",
        r"\bintegrated circuit\b", r"\bwafer\b", r"\bfoundry\b",
    ],
    "healthcare": [
        r"\bhealthcare\b", r"\bmedical device\b", r"\bclinical trial\b",
        r"\bpatient care\b", r"\bhealth system\b",
    ],
    "biotechnology": [
        r"\bbiotech\w*\b", r"\bbiological\b.*\b(?:drug|therapy)\b",
        r"\bmonoclonal antibod\w+\b", r"\bcell therap\w+\b",
    ],
    "drug discovery": [
        r"\bdrug discover\w+\b", r"\bpharmaceutical\b", r"\bpipeline\b.*\b(?:drug|therapy)\b",
        r"\bclinical stage\b", r"\bFDA approv\w+\b",
    ],
    "genomics": [
        r"\bgenomic\b", r"\bgenome\b", r"\bgene therap\w+\b",
        r"\bCRISPR\b", r"\bDNA sequenc\w+\b",
    ],
    "renewable energy": [
        r"\brenewable energy\b", r"\bclean energy\b",
        r"\bgreen energy\b", r"\benergy transition\b",
    ],
    "solar": [
        r"\bsolar\b.*\b(?:energy|panel|farm|power)\b", r"\bphotovoltaic\b",
    ],
    "wind energy": [
        r"\bwind\b.*\b(?:energy|turbine|farm|power)\b", r"\boffshore wind\b",
    ],
    "battery technology": [
        r"\bbattery\b.*\b(?:technolog|storage|cell|pack)\b",
        r"\blithium-ion\b", r"\bsolid-state batter\w+\b",
    ],
    "autonomous driving": [
        r"\bautonomous\b.*\b(?:driv|vehicle)\b", r"\bself-driving\b",
        r"\blidar\b", r"\bADAS\b",
    ],
    "streaming": [
        r"\bstreaming\b.*\b(?:service|platform|content|video)\b",
        r"\bvideo on demand\b", r"\bOTT\b",
    ],
    "robotics": [
        r"\brobot\w+\b", r"\bindustrial automation\b",
        r"\brobotic process\b", r"\bcollaborative robot\b",
    ],
    "blockchain": [
        r"\bblockchain\b", r"\bdistributed ledger\b", r"\bsmart contract\b",
        r"\bWeb3\b",
    ],
    "cryptocurrency": [
        r"\bcryptocurrenc\w+\b", r"\bbitcoin\b", r"\bethereum\b",
        r"\bcrypto\b.*\b(?:asset|exchange|trading)\b",
    ],
    "space": [
        r"\bspace\b.*\b(?:explor|launch|satellite|orbit)\b",
        r"\brocket\b", r"\bspacecraft\b",
    ],
    "gaming": [
        r"\bvideo game\b", r"\bgaming\b.*\b(?:platform|console|industry)\b",
        r"\besport\b",
    ],
    "internet of things": [
        r"\binternet of things\b", r"\bIoT\b", r"\bconnected devices\b",
        r"\bsmart home\b", r"\bedge computing\b",
    ],
    "quantum computing": [
        r"\bquantum comput\w+\b", r"\bqubit\b",
        r"\bquantum\b.*\b(?:advantage|supremacy|algorithm)\b",
    ],
    "generative ai": [
        r"\bgenerative AI\b", r"\blarge language model\b", r"\bLLM\b",
        r"\bGPT\b", r"\bfoundation model\b", r"\btext-to-image\b",
    ],
    "lifestyle": [
        r"\blifestyle\b", r"\bconsumer\b.*\b(?:electronic|product|brand)\b",
        r"\bpremium\b.*\b(?:brand|product)\b", r"\becosystem\b",
    ],
    "digital payments": [
        r"\bdigital payment\b", r"\bcontactless\b", r"\bmobile wallet\b",
        r"\bpayment processing\b", r"\bNFC\b",
    ],
    "telehealth": [
        r"\btelehealth\b", r"\btelemedicine\b", r"\bremote\b.*\bcare\b",
        r"\bvirtual\b.*\b(?:clinic|care|visit)\b",
    ],
    "data center": [
        r"\bdata center\b", r"\bcolocation\b", r"\bhyperscale\b",
        r"\bserver\b.*\b(?:farm|rack|infrastructure)\b",
    ],
    "sustainability": [
        r"\bsustainab\w+\b", r"\bESG\b", r"\bcarbon\b.*\b(?:neutral|footprint|offset)\b",
        r"\bnet zero\b",
    ],
}


class KeywordExtractor:
    name = "keyword_nlp"

    def __init__(self):
        self._patterns = {
            theme: [re.compile(p, re.IGNORECASE) for p in patterns]
            for theme, patterns in THEME_KEYWORDS.items()
        }

    def extract(self, profile: CompanyProfile) -> list[Theme]:
        # Combine all available text
        text_parts = []
        if profile.business_description:
            text_parts.append(profile.business_description)
        if profile.business_summary:
            text_parts.append(profile.business_summary)
        if profile.risk_factors:
            text_parts.append(profile.risk_factors)
        if profile.social_text:
            text_parts.append(profile.social_text)

        if not text_parts:
            return []

        combined_text = " ".join(text_parts)
        themes = []

        for theme_name, patterns in self._patterns.items():
            match_count = 0
            first_match_context = None

            for pattern in patterns:
                matches = pattern.findall(combined_text)
                if matches:
                    match_count += len(matches)
                    if first_match_context is None:
                        m = pattern.search(combined_text)
                        if m:
                            start = max(0, m.start() - 40)
                            end = min(len(combined_text), m.end() + 40)
                            first_match_context = combined_text[start:end].strip()

            if match_count >= 1:
                text_length = len(combined_text)
                density = match_count / (text_length / 1000)
                confidence = min(0.9, 0.35 + density * 0.08)

                themes.append(Theme(
                    name=theme_name,
                    confidence=round(confidence, 3),
                    source=ExtractionMethod.KEYWORD_NLP,
                    evidence=first_match_context,
                ))

        themes.sort(key=lambda t: t.confidence, reverse=True)
        return themes
