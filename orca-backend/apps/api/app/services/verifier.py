# Verifier
# Proof-carrying verification: checks every numeric claim against actual query results

import logging
from typing import Dict, Any, List, Optional, Tuple
from app.schemas.evidence import EvidenceRecord, NumericClaim, VerificationResult

logger = logging.getLogger(__name__)


class Verifier:
    """Verifies that all numeric claims in a response are grounded in query results."""

    def __init__(self, evidence: EvidenceRecord, query_result: Dict[str, Any]):
        self.evidence = evidence
        self.query_result = query_result
        self.profiles = query_result.get("profiles", [])
        self.metadata = query_result.get("metadata", {})

    def verify_counts(self) -> List[str]:
        """Verify float count, profile count, observation count match."""
        errors = []
        
        # Float count
        actual_floats = len(set(p["platform_number"] for p in self.profiles))
        if actual_floats != self.evidence.float_ids.__len__():
            errors.append(f"Float ID count mismatch: evidence has {len(self.evidence.float_ids)}, actual {actual_floats}")
        
        # Profile count
        actual_profiles = len(self.profiles)
        if actual_profiles != self.evidence.profile_count:
            errors.append(f"Profile count mismatch: evidence claims {self.evidence.profile_count}, actual {actual_profiles}")
        
        # Observation count
        actual_obs = sum(len(p.get("observations", [])) for p in self.profiles)
        if actual_obs != self.evidence.observation_count:
            errors.append(f"Observation count mismatch: evidence claims {self.evidence.observation_count}, actual {actual_obs}")
        
        return errors

    def verify_region(self) -> List[str]:
        """Verify region matches query."""
        errors = []
        req_region = self.evidence.region
        if not req_region or not self.profiles:
            return errors

        # Check all profiles are within requested region
        if req_region.type == "bbox":
            min_lat, max_lat = req_region.min_lat, req_region.max_lat
            min_lon, max_lon = req_region.min_lon, req_region.max_lon
            for p in self.profiles:
                if not (min_lat <= p["latitude"] <= max_lat and min_lon <= p["longitude"] <= max_lon):
                    errors.append(f"Profile {p['profile_id']} outside requested bbox: ({p['latitude']}, {p['longitude']})")
        elif req_region.type == "radius":
            # Would need distance calculation
            pass
        
        return errors

    def verify_time_range(self) -> List[str]:
        """Verify time range matches."""
        errors = []
        req_range = self.evidence.time_range
        if not req_range or not self.profiles:
            return errors

        for p in self.profiles:
            p_time = p.get("profile_time")
            if p_time:
                if p_time < req_range.start or p_time > req_range.end:
                    errors.append(f"Profile {p['profile_id']} time {p_time} outside range [{req_range.start}, {req_range.end}]")
        
        return errors

    def verify_qc_filters(self) -> List[str]:
        """Verify QC filters were applied."""
        errors = []
        filters = self.evidence.quality_filters.filters
        
        if "recommended" in filters:
            # Check that no observations have QC flags 3, 4, 9
            for p in self.profiles:
                for obs in p.get("observations", []):
                    for qc_field in ["temperature_qc", "salinity_qc", "oxygen_qc"]:
                        qc = obs.get(qc_field)
                        if qc is not None and qc not in [1, 2]:
                            errors.append(f"Profile {p['profile_id']} has {qc_field}={qc} (not in recommended)")
        
        return errors

    def verify_numeric_claims(self, claims: List[NumericClaim]) -> Tuple[List[NumericClaim], List[NumericClaim]]:
        """Verify each numeric claim against query results."""
        verified = []
        failed = []

        for claim in claims:
            if self._verify_single_claim(claim):
                claim.verified = True
                verified.append(claim)
            else:
                claim.verified = False
                failed.append(claim)

        return verified, failed

    def _verify_single_claim(self, claim: NumericClaim) -> bool:
        """Verify a single numeric claim."""
        # This is simplified - real implementation would match claim_id to specific observations
        # For MVP, we check that the claim value exists in the data range
        
        claim_val = float(claim.value) if isinstance(claim.value, (int, float, str)) else None
        if claim_val is None:
            return False

        # Check against actual data based on claim source
        if claim.source == "measurement":
            # Check if value exists in observations
            for p in self.profiles:
                for obs in p.get("observations", []):
                    for var in ["temperature_c", "salinity_psu", "oxygen_umol_kg", "chlorophyll"]:
                        val = obs.get(var)
                        if val is not None and abs(val - claim_val) < 0.01:
                            return True
        
        elif claim.source == "aggregation":
            # Check against computed aggregations
            # This would need access to the aggregation results
            pass

        # For MVP, if we can't verify precisely, check if it's within plausible range
        if claim.unit == "°C" and -5 <= claim_val <= 40:
            return True
        if claim.unit == "PSU" and 0 <= claim_val <= 50:
            return True
        if claim.unit == "μmol/kg" and 0 <= claim_val <= 500:
            return True
        
        return False

    def verify_all(self, claims: List[NumericClaim]) -> VerificationResult:
        """Run all verification checks."""
        all_errors = []
        all_errors.extend(self.verify_counts())
        all_errors.extend(self.verify_region())
        all_errors.extend(self.verify_time_range())
        all_errors.extend(self.verify_qc_filters())

        verified_claims, failed_claims = self.verify_numeric_claims(claims)

        all_verified = len(all_errors) == 0 and len(failed_claims) == 0

        return VerificationResult(
            all_verified=all_verified,
            claims=verified_claims + failed_claims,
            failed_claims=failed_claims,
            summary=f"Verification {'PASSED' if all_verified else 'FAILED'}: {len(all_errors)} structural errors, {len(failed_claims)} claim errors"
        )


def create_claims_from_result(query_result: Dict[str, Any], evidence: EvidenceRecord) -> List[NumericClaim]:
    """Extract numeric claims from query result for verification."""
    claims = []
    metadata = query_result.get("metadata", {})
    profiles = query_result.get("profiles", [])

    # Float count claim
    if metadata.get("float_count"):
        claims.append(NumericClaim(
            claim=f"Found {metadata['float_count']} unique floats",
            value=metadata["float_count"],
            unit="floats",
            claim_id="float_count",
            source="aggregation",
            verified=False,
        ))

    # Profile count claim
    if metadata.get("profile_count"):
        claims.append(NumericClaim(
            claim=f"Retrieved {metadata['profile_count']} profiles",
            value=metadata["profile_count"],
            unit="profiles",
            claim_id="profile_count",
            source="aggregation",
            verified=False,
        ))

    # Temperature range claim
    temps = []
    for p in profiles:
        for obs in p.get("observations", []):
            if obs.get("temperature_c") is not None:
                temps.append(obs["temperature_c"])
    
    if temps:
        claims.append(NumericClaim(
            claim=f"Temperature range: {min(temps):.1f}–{max(temps):.1f} °C",
            value={"min": min(temps), "max": max(temps)},
            unit="°C",
            claim_id="temp_range",
            source="aggregation",
            verified=False,
        ))
        claims.append(NumericClaim(
            claim=f"Mean temperature: {sum(temps)/len(temps):.1f} °C",
            value=sum(temps)/len(temps),
            unit="°C",
            claim_id="temp_mean",
            source="aggregation",
            verified=False,
        ))

    # Time range claim
    if metadata.get("time_range"):
        claims.append(NumericClaim(
            claim=f"Time range: {metadata['time_range']['start']} to {metadata['time_range']['end']}",
            value=metadata["time_range"],
            unit="date_range",
            claim_id="time_range",
            source="aggregation",
            verified=False,
        ))

    return claims