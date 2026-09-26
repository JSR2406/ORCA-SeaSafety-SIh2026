"""Free/demo-tier SMS dispatch: provider free-tier when keys exist, else DEMO MODE.

Keys live ONLY in backend env (never frontend):
  FAST2SMS_API_KEY — Fast2SMS free tier
  TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM — Twilio trial
  EMERGENCY_SMS_NUMBER — default recipient for auto-enqueued HIGH alerts
No key -> DEMO MODE: payload logged + kept in memory, clearly labeled simulated.
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

SENT_SMS_LOG: List[Dict[str, Any]] = []
MAX_LOG = 200


def _log(entry: Dict[str, Any]) -> Dict[str, Any]:
    entry.setdefault("at", datetime.utcnow().isoformat())
    SENT_SMS_LOG.append(entry)
    del SENT_SMS_LOG[: max(0, len(SENT_SMS_LOG) - MAX_LOG)]
    print(f"[SMS] {entry}", flush=True)
    return entry


def _via_fast2sms(phone: str, message: str) -> Optional[Dict[str, Any]]:
    key = os.getenv("FAST2SMS_API_KEY", "")
    if not key:
        return None
    r = httpx.post("https://www.fast2sms.com/dev/bulkV2", timeout=10,
                   headers={"authorization": key},
                   data={"route": "q", "message": message, "numbers": phone})
    r.raise_for_status()
    return {"provider": "fast2sms", "provider_status": r.json()}


def _via_twilio(phone: str, message: str) -> Optional[Dict[str, Any]]:
    sid, tok, frm = (os.getenv("TWILIO_ACCOUNT_SID", ""), os.getenv("TWILIO_AUTH_TOKEN", ""),
                     os.getenv("TWILIO_FROM", ""))
    if not (sid and tok and frm):
        return None
    r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                   timeout=10, auth=(sid, tok),
                   data={"From": frm, "To": phone, "Body": message})
    r.raise_for_status()
    return {"provider": "twilio", "provider_status": r.json()}


def dispatch_sms(phone: str, message: str, alert_id: Optional[str] = None,
                 severity: str = "INFO") -> Dict[str, Any]:
    """Send via free-tier provider if configured, else DEMO MODE (logged, labeled)."""
    base = {"phone": phone, "message": message, "alert_id": alert_id,
            "severity": severity.upper()}
    for sender in (_via_fast2sms, _via_twilio):
        try:
            res = sender(phone, message)
        except Exception as e:
            return _log({**base, "status": "failed", "sent": True, "demo": False,
                         "reason": f"provider error: {e}"})
        if res:
            return _log({**base, "status": "sent", "sent": True, "demo": False, **res})
    return _log({**base, "status": "demo", "sent": False, "demo": True,
                 "reason": "no provider key (FAST2SMS_API_KEY / TWILIO_*) — simulated dispatch"})


def maybe_auto_sms(severity: str, wave_h: Optional[float] = None,
                   wave_threshold: Optional[float] = None,
                   message: str = "", alert_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Trigger: HIGH severity OR Hs > user's waveRiskThreshold → emergency number."""
    emergency = os.getenv("EMERGENCY_SMS_NUMBER", "")
    wave_breach = (wave_h is not None and wave_threshold is not None and wave_h > wave_threshold)
    if (severity or "").upper() == "HIGH" or wave_breach:
        if emergency:
            why = "HIGH severity" if (severity or "").upper() == "HIGH" else f"Hs {wave_h}m > threshold {wave_threshold}m"
            return dispatch_sms(emergency, f"[ORCA AUTO-SMS: {why}] {message}",
                                alert_id=alert_id, severity="HIGH")
        return {"status": "skipped", "sent": False, "demo": True,
                "reason": "auto-trigger matched but EMERGENCY_SMS_NUMBER unset"}
    return None


def sms_log(limit: int = 50) -> List[Dict[str, Any]]:
    return list(reversed(SENT_SMS_LOG[-limit:]))
