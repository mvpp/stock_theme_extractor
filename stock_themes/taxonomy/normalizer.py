"""Theme name normalization and deduplication."""

from __future__ import annotations

from stock_themes.taxonomy.themes import ALL_THEMES, THEME_CATEGORIES

ALIASES: dict[str, str] = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "ev": "electric vehicles",
    "evs": "electric vehicles",
    "iot": "internet of things",
    "vr": "virtual reality",
    "ar": "augmented reality",
    "xr": "augmented reality",
    "saas": "cloud computing",
    "paas": "cloud computing",
    "iaas": "cloud computing",
    "cyber security": "cybersecurity",
    "cyber-security": "cybersecurity",
    "self-driving": "autonomous driving",
    "driverless": "autonomous driving",
    "online retail": "e-commerce",
    "digital commerce": "e-commerce",
    "ecommerce": "e-commerce",
    "chips": "semiconductors",
    "chip": "semiconductors",
    "biotech": "biotechnology",
    "medtech": "medical devices",
    "green energy": "renewable energy",
    "clean tech": "cleantech",
    "smart watch": "wearable technology",
    "smartwatch": "wearable technology",
    "wearables": "wearable technology",
    "data analytics": "big data",
    "data science": "big data",
    "analytics": "big data",
    "digital advertising": "adtech",
    "advertising technology": "adtech",
    "programmatic advertising": "adtech",
    "gen ai": "generative ai",
    "genai": "generative ai",
    "llm": "generative ai",
    "large language model": "generative ai",
    "chatbot": "generative ai",
    "gpt": "generative ai",
    "deep learning": "artificial intelligence",
    "neural network": "artificial intelligence",
    "neural networks": "artificial intelligence",
    "telemedicine": "telehealth",
    "pharma": "drug discovery",
    "pharmaceutical": "drug discovery",
    "biopharma": "drug discovery",
    "biopharmaceutical": "drug discovery",
    "crypto": "cryptocurrency",
    "bitcoin": "cryptocurrency",
    "ethereum": "cryptocurrency",
    "neobank": "fintech",
    "digital bank": "fintech",
    "digital banking": "fintech",
    "mobile payments": "digital payments",
    "contactless payments": "digital payments",
    "uav": "drones",
    "unmanned aerial": "drones",
    "3d print": "3d printing",
    "additive manufacturing": "3d printing",
    "reit": "real estate",
    "property": "real estate",
    "solar energy": "solar",
    "solar power": "solar",
    "wind power": "wind energy",
    "offshore wind": "wind energy",
    "ev charging": "electric vehicles",
    "charging infrastructure": "electric vehicles",
    "lithium-ion": "battery technology",
    "solid-state battery": "battery technology",
    "energy transition": "clean energy",
    "decarbonization": "clean energy",
    "net zero": "clean energy",
    "carbon neutral": "clean energy",
    "metaverse": "metaverse",
    "web3": "blockchain",
    "web 3": "blockchain",
    "defi": "defi",
    "decentralized finance": "defi",
    "nft": "nft",
    "non-fungible": "nft",
    "pet care": "pet economy",
    "veterinary": "pet economy",
    "senior care": "aging population",
    "elderly care": "aging population",
    "work from home": "remote work",
    "wfh": "remote work",
    "hybrid work": "remote work",
    "freelance": "gig economy",
    "gpu": "ai chips",
    "tpu": "ai chips",
    "ai accelerator": "ai chips",
    "cloud infrastructure": "cloud infrastructure",
    "hyperscale": "data center",
    "colocation": "data center",
}


class ThemeNormalizer:
    def normalize(self, theme: str) -> str:
        """Normalize a theme string to its canonical form."""
        cleaned = theme.strip().lower()
        if cleaned in ALIASES:
            return ALIASES[cleaned]
        if cleaned in ALL_THEMES:
            return cleaned
        return cleaned

    def get_category(self, theme: str) -> str | None:
        normalized = self.normalize(theme)
        return THEME_CATEGORIES.get(normalized)

    def is_known(self, theme: str) -> bool:
        normalized = self.normalize(theme)
        return normalized in ALL_THEMES
