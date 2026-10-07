import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("DeepShield.ScamDetector")

SCAM_TRIGGERS = [
    "urgent", "wire transfer", "gift card", "otp", "password", "bank account",
    "verification code", "send money", "crypto", "arrest", "irs", "police",
    "emergency fund", "kidnapped", "compromised", "confidential"
]

class ScamContextDetector:
    """
    Scam Context & Social Engineering Detector.
    Scans conversation context / transcript signals for social engineering pressure,
    urgency tactics, impersonation tropes, and credential harvesting patterns.
    Operates in clearly designated MOCK/DEMO mode with `is_mock: True` until full NLP model
    checkpoint is mounted.
    """
    def __init__(self):
        self.is_mock = True
        logger.info("ScamContextDetector initialized in MOCK/DEMO mode (is_mock=True).")

    def analyze(self, text_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates social engineering scam risk score (0.0 to 100.0).
        """
        if not text_context:
            return {
                "score": 5.0,
                "is_mock": True,
                "keywords_detected": []
            }

        text_lower = text_context.lower()
        matched = [k for k in SCAM_TRIGGERS if re.search(r'\b' + re.escape(k) + r'\b', text_lower)]

        threat_score = min(95.0, len(matched) * 25.0 + 10.0) if matched else 5.0

        return {
            "score": round(threat_score, 1),
            "is_mock": True,
            "keywords_detected": matched
        }
