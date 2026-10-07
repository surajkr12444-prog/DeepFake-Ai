import logging
from typing import Dict, Any, List

logger = logging.getLogger("DeepShield.RiskFusion")

class RiskFusionEngine:
    """
    Authoritative Risk Fusion Engine.
    Combines multi-modal signals (Video Deepfake Forensics, Audio Voice Cloning,
    Lip-Sync Coherence, and Scam Context) into a single unified threat assessment.
    
    Score range is consistently 0.0 to 100.0 (where higher = higher scam / deepfake risk).
    """
    def __init__(self, weight_video: float = 0.50, weight_audio: float = 0.25,
                 weight_lipsync: float = 0.15, weight_scam: float = 0.10):
        self.w_video = weight_video
        self.w_audio = weight_audio
        self.w_lipsync = weight_lipsync
        self.w_scam = weight_scam

    def fuse(self,
             video_res: Dict[str, Any],
             audio_res: Dict[str, Any],
             lipsync_res: Dict[str, Any],
             scam_res: Dict[str, Any],
             sensitivity_threshold: float = 60.0) -> Dict[str, Any]:

        v_score = float(video_res.get("score", 0.0))
        a_score = float(audio_res.get("score", 0.0))
        l_score = float(lipsync_res.get("score", 0.0))
        s_score = float(scam_res.get("score", 0.0))

        reasons: List[str] = []

        # Collect video reasons
        for anomaly in video_res.get("anomalies", []):
            reasons.append(f"Visual: {anomaly}")

        if not video_res.get("is_live", True) and video_res.get("face_detected", False):
            reasons.append("Visual: Screen replay / Anti-spoofing check failed")

        # Collect audio reasons
        if a_score > 50.0:
            reasons.append(f"Acoustic: Synthetic vocal profile ({int(a_score)}% anomaly)")

        # Collect lip-sync reasons
        if l_score > 60.0:
            reasons.append(f"Sync: Viseme-phoneme temporal desynchronization ({int(l_score)}%)")

        # Collect scam context reasons
        for kw in scam_res.get("keywords_detected", []):
            reasons.append(f"Social Engineering: Trigger keyword '{kw}' detected")

        # Weighted calculation
        if video_res.get("face_detected", False):
            fused_score = (self.w_video * v_score) + (self.w_audio * a_score) + \
                          (self.w_lipsync * l_score) + (self.w_scam * s_score)
        else:
            # When face is absent, rely on acoustic and context signals
            fused_score = (0.60 * a_score) + (0.40 * s_score)
            if not reasons:
                reasons.append("Telemetry: No human face in camera frame")

        # Clamping
        fused_score = float(max(0.0, min(100.0, fused_score)))

        # Determine level and label
        if fused_score >= 75.0 or (video_res.get("is_deepfake", False) and v_score >= 70.0):
            level = "CRITICAL"
            label = "🚨 CRITICAL: AI Deepfake Threat Confirmed"
            if not any("Deepfake" in r for r in reasons):
                reasons.append("Multi-modal AI forensics flagged high-confidence synthetic manipulation")
        elif fused_score >= 50.0:
            level = "HIGH"
            label = "⚠️ HIGH RISK: Suspicious Synthetic Attributes"
        elif fused_score >= 30.0:
            level = "MEDIUM"
            label = "⚡ MEDIUM: Minor Discrepancies Detected"
        else:
            level = "LOW"
            label = "✓ AUTHENTIC: Verified Natural Biometrics"
            if not reasons:
                reasons.append("All visual, acoustic, and behavioral biometrics within normal human thresholds")

        return {
            "score": round(fused_score, 1),
            "level": level,
            "label": label,
            "reasons": reasons
        }
