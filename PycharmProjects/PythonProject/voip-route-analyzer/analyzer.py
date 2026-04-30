"""
analyzer.py
-----------
Core analysis engine for VoIP Route Analyzer Lite.

This file contains only the business logic:
- load call logs
- group calls by route
- calculate ASR
- calculate average PDD
- detect SIP/failure patterns
- detect possible FAS fraud
- detect missing RBT
- generate NOC-style recommendations

The UI layer should be placed separately in app.py.
"""

from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Dict, List

import pandas as pd


# -----------------------------
# Threshold configuration
# -----------------------------

ASR_BAD_THRESHOLD = 30.0
ASR_GOOD_THRESHOLD = 50.0
PDD_HIGH_THRESHOLD = 5.0
SHORT_CALL_DURATION_THRESHOLD = 3
FAS_SHORT_CALL_RATIO_THRESHOLD = 25.0
MISSING_RBT_RATIO_THRESHOLD = 20.0


# -----------------------------
# Data loading and validation
# -----------------------------

REQUIRED_COLUMNS = [
    "call_id",
    "route",
    "destination",
    "status",
    "duration_seconds",
    "pdd_seconds",
    "rbt_status",
    "sip_code",
]


def validate_columns(df: pd.DataFrame) -> None:
    """
    Validate that the uploaded CSV contains all required columns.

    Raises:
        ValueError: if one or more required columns are missing.
    """
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]

    if missing_columns:
        raise ValueError(
            "Missing required column(s): " + ", ".join(missing_columns)
        )


def clean_call_logs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize call log data.

    Expected columns:
    - call_id
    - route
    - destination
    - status
    - duration_seconds
    - pdd_seconds
    - rbt_status
    - sip_code
    """
    validate_columns(df)

    cleaned = df.copy()

    cleaned["route"] = cleaned["route"].astype(str).str.strip()
    cleaned["destination"] = cleaned["destination"].astype(str).str.strip()
    cleaned["status"] = cleaned["status"].astype(str).str.strip().str.upper()
    cleaned["rbt_status"] = cleaned["rbt_status"].astype(str).str.strip().str.upper()
    cleaned["sip_code"] = cleaned["sip_code"].astype(str).str.strip()

    cleaned["duration_seconds"] = pd.to_numeric(
        cleaned["duration_seconds"], errors="coerce"
    ).fillna(0).astype(int)

    cleaned["pdd_seconds"] = pd.to_numeric(
        cleaned["pdd_seconds"], errors="coerce"
    ).fillna(0.0).astype(float)

    return cleaned


def load_call_logs(file_path: str) -> pd.DataFrame:
    """
    Load call logs from a CSV file and return a cleaned DataFrame.
    """
    df = pd.read_csv(file_path)
    return clean_call_logs(df)


# -----------------------------
# Core KPI calculations
# -----------------------------


def calculate_asr(route_df: pd.DataFrame) -> float:
    """
    Calculate ASR: answered calls / total calls * 100.

    ASR = Answer-Seizure Ratio.
    It is used to estimate route quality.
    """
    total_calls = len(route_df)

    if total_calls == 0:
        return 0.0

    answered_calls = len(route_df[route_df["status"] == "ANSWERED"])
    return round((answered_calls / total_calls) * 100, 2)


def interpret_asr(asr: float) -> str:
    """
    Convert ASR value into a readable NOC-style interpretation.
    """
    if asr < ASR_BAD_THRESHOLD:
        return "Bad route quality"
    if asr < ASR_GOOD_THRESHOLD:
        return "Weak / needs monitoring"
    return "Acceptable"


def calculate_average_pdd(route_df: pd.DataFrame) -> float:
    """
    Calculate average PDD.

    PDD = Post Dial Delay.
    It measures how long call setup takes before ringing/answer.
    """
    if route_df.empty:
        return 0.0

    return round(float(route_df["pdd_seconds"].mean()), 2)


def interpret_pdd(avg_pdd: float) -> str:
    """
    Convert average PDD into a readable interpretation.
    """
    if avg_pdd > PDD_HIGH_THRESHOLD:
        return "High PDD - slow call setup"
    return "Normal"


# -----------------------------
# Pattern detection
# -----------------------------


def most_common_value(values: List[Any]) -> str:
    """
    Return the most common value from a list.
    """
    if not values:
        return "None"

    return str(Counter(values).most_common(1)[0][0])


def detect_failure_patterns(route_df: pd.DataFrame) -> Dict[str, str]:
    """
    Detect dominant failure status and SIP error code.
    """
    failed_df = route_df[route_df["status"] != "ANSWERED"]

    if failed_df.empty:
        return {
            "main_failure_status": "None",
            "main_sip_code": "None",
        }

    return {
        "main_failure_status": most_common_value(failed_df["status"].tolist()),
        "main_sip_code": most_common_value(failed_df["sip_code"].tolist()),
    }


def detect_fas_suspicion(route_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect possible FAS fraud suspicion.

    Simple heuristic:
    - Get all answered calls.
    - Count answered calls with very short duration.
    - If the short answered call ratio is high, flag possible FAS.

    FAS = Fake Answer Supervision.
    """
    answered_df = route_df[route_df["status"] == "ANSWERED"]

    if answered_df.empty:
        return {
            "fas_suspected": False,
            "short_answered_calls": 0,
            "short_answered_ratio": 0.0,
        }

    short_answered_df = answered_df[
        answered_df["duration_seconds"] <= SHORT_CALL_DURATION_THRESHOLD
    ]

    ratio = round((len(short_answered_df) / len(answered_df)) * 100, 2)

    return {
        "fas_suspected": ratio >= FAS_SHORT_CALL_RATIO_THRESHOLD,
        "short_answered_calls": len(short_answered_df),
        "short_answered_ratio": ratio,
    }


def detect_rbt_issues(route_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect missing RBT cases.

    RBT = Ringback Tone.
    Missing RBT may indicate poor caller experience.
    """
    total_calls = len(route_df)

    if total_calls == 0:
        return {
            "missing_rbt_count": 0,
            "missing_rbt_ratio": 0.0,
        }

    missing_rbt_df = route_df[route_df["rbt_status"] == "MISSING"]
    ratio = round((len(missing_rbt_df) / total_calls) * 100, 2)

    return {
        "missing_rbt_count": len(missing_rbt_df),
        "missing_rbt_ratio": ratio,
    }


# -----------------------------
# Recommendations
# -----------------------------


def create_recommendation(result: Dict[str, Any]) -> str:
    """
    Create a practical NOC-style recommendation.
    """
    recommendations = []

    if result["asr"] < ASR_BAD_THRESHOLD:
        recommendations.append("Replace or deprioritize this route due to low ASR.")
    elif result["asr"] < ASR_GOOD_THRESHOLD:
        recommendations.append("Monitor this route and compare it with alternatives.")

    if result["average_pdd"] > PDD_HIGH_THRESHOLD:
        recommendations.append("Investigate upstream carrier due to high PDD.")

    if result["fas_suspected"]:
        recommendations.append(
            "Possible FAS detected: validate short answered calls and billing risk."
        )

    if result["missing_rbt_ratio"] > MISSING_RBT_RATIO_THRESHOLD:
        recommendations.append(
            "Investigate RBT issues; callers may experience silence before answer."
        )

    if not recommendations:
        recommendations.append("Route looks stable based on current sample.")

    return " ".join(recommendations)


# -----------------------------
# Main route analysis
# -----------------------------


def analyze_route(route_name: str, route_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze one route and return structured KPI results.
    """
    asr = calculate_asr(route_df)
    average_pdd = calculate_average_pdd(route_df)
    failure_patterns = detect_failure_patterns(route_df)
    fas = detect_fas_suspicion(route_df)
    rbt = detect_rbt_issues(route_df)

    result = {
        "route": route_name,
        "destination": str(route_df["destination"].iloc[0]) if not route_df.empty else "Unknown",
        "total_calls": len(route_df),
        "asr": asr,
        "asr_interpretation": interpret_asr(asr),
        "average_pdd": average_pdd,
        "pdd_interpretation": interpret_pdd(average_pdd),
        "main_failure_status": failure_patterns["main_failure_status"],
        "main_sip_code": failure_patterns["main_sip_code"],
        "fas_suspected": fas["fas_suspected"],
        "short_answered_calls": fas["short_answered_calls"],
        "short_answered_ratio": fas["short_answered_ratio"],
        "missing_rbt_count": rbt["missing_rbt_count"],
        "missing_rbt_ratio": rbt["missing_rbt_ratio"],
    }

    result["recommendation"] = create_recommendation(result)

    return result


def analyze_all_routes(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Analyze all routes from a call log DataFrame.
    """
    cleaned_df = clean_call_logs(df)
    results = []

    for route_name, route_df in cleaned_df.groupby("route"):
        results.append(analyze_route(route_name, route_df))

    return rank_routes(results)


def rank_routes(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank routes by:
    1. highest ASR
    2. lowest average PDD
    3. no FAS suspicion preferred
    """
    return sorted(
        results,
        key=lambda row: (
            row["fas_suspected"],
            -row["asr"],
            row["average_pdd"],
        ),
    )


def get_global_summary(df: pd.DataFrame, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create global dashboard KPIs.
    """
    cleaned_df = clean_call_logs(df)
    total_calls = len(cleaned_df)
    answered_calls = len(cleaned_df[cleaned_df["status"] == "ANSWERED"])

    global_asr = 0.0
    if total_calls > 0:
        global_asr = round((answered_calls / total_calls) * 100, 2)

    average_pdd = 0.0
    if total_calls > 0:
        average_pdd = round(float(cleaned_df["pdd_seconds"].mean()), 2)

    fas_alerts = sum(1 for result in results if result["fas_suspected"])
    preferred_route = results[0]["route"] if results else "None"

    return {
        "total_calls": total_calls,
        "answered_calls": answered_calls,
        "global_asr": global_asr,
        "average_pdd": average_pdd,
        "fas_alerts": fas_alerts,
        "preferred_route": preferred_route,
    }


# -----------------------------
# Sample data helper
# -----------------------------


def create_sample_dataframe() -> pd.DataFrame:
    """
    Create sample VoIP call logs for demo/testing.
    This can be used by app.py when no file is uploaded.
    """
    data = [
        ["1", "UK_1", "United Kingdom", "ANSWERED", 45, 3.2, "OK", "200"],
        ["2", "UK_1", "United Kingdom", "FAILED", 0, 5.8, "MISSING", "503"],
        ["3", "UK_1", "United Kingdom", "ANSWERED", 2, 2.1, "OK", "200"],
        ["4", "UK_1", "United Kingdom", "NO_ANSWER", 0, 6.0, "OK", "408"],
        ["5", "UK_1", "United Kingdom", "ANSWERED", 60, 3.7, "OK", "200"],
        ["6", "UK_2", "United Kingdom", "ANSWERED", 120, 2.4, "OK", "200"],
        ["7", "UK_2", "United Kingdom", "ANSWERED", 90, 2.8, "OK", "200"],
        ["8", "UK_2", "United Kingdom", "FAILED", 0, 3.1, "OK", "486"],
        ["9", "UK_2", "United Kingdom", "ANSWERED", 75, 2.6, "OK", "200"],
        ["10", "UK_2", "United Kingdom", "NO_ANSWER", 0, 3.3, "OK", "408"],
        ["11", "DE_1", "Germany", "ANSWERED", 1, 1.8, "OK", "200"],
        ["12", "DE_1", "Germany", "ANSWERED", 2, 1.9, "OK", "200"],
        ["13", "DE_1", "Germany", "ANSWERED", 1, 2.0, "OK", "200"],
        ["14", "DE_1", "Germany", "FAILED", 0, 4.9, "MISSING", "503"],
        ["15", "DE_1", "Germany", "NO_ANSWER", 0, 5.3, "MISSING", "408"],
    ]

    return pd.DataFrame(data, columns=REQUIRED_COLUMNS)
