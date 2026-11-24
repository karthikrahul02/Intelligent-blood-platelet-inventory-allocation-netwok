"""
SNOMED CT Concept Detail Extractor (Safe Version)
===================================================
Extracts concept details from the SNOMED International Snowstorm API.
Includes delays between requests to avoid rate limiting.

Usage:
    python snomed_concept_extractor.py 53741008 (or any other SNOMED concept)
    python snomed_concept_extractor.py "https://browser.ihtsdotools.org/?perspective=full&conceptId1=53741008"

Author: Elina Nuerenberg-Goloub with Claude Opus 4.6 by Anthropic
Date: 2026-02-15


"""

import json
import re
import sys
import time
from urllib.parse import urlparse, parse_qs

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

BASE_URL = "https://snowstorm.ihtsdotools.org/snowstorm/snomed-ct"
BRANCH = "MAIN"
DELAY_BETWEEN_CALLS = 3  # seconds between each API call

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SNOMED-Research-Tool/1.0",
}


def extract_concept_id(input_str: str) -> str:
    input_str = input_str.strip()
    if input_str.isdigit():
        return input_str
    try:
        parsed = urlparse(input_str)
        params = parse_qs(parsed.query)
        if "conceptId1" in params:
            return params["conceptId1"][0]
    except Exception:
        pass
    match = re.search(r"\b(\d{6,18})\b", input_str)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract a concept ID from: {input_str}")


def safe_get(url: str, params: dict = None) -> requests.Response:
    """Single request with one gentle retry on 429."""
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    if resp.status_code == 429:
        print("    Rate limited - waiting 30s before one retry...")
        time.sleep(30)
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp


def main():
    if len(sys.argv) > 1:
        raw_input = sys.argv[1]
    else:
        raw_input = "53741008"

    concept_id = extract_concept_id(raw_input)
    print(f"\n  Fetching SNOMED CT concept: {concept_id}")
    print(f"  (pausing {DELAY_BETWEEN_CALLS}s between requests to be safe)\n")

    # --- 1. Concept details ---
    print("  [1/3] Getting concept details...")
    try:
        data = safe_get(f"{BASE_URL}/browser/{BRANCH}/concepts/{concept_id}").json()
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    time.sleep(DELAY_BETWEEN_CALLS)

    # --- 2. Parents ---
    print("  [2/3] Getting parent concepts...")
    try:
        parents = safe_get(
            f"{BASE_URL}/browser/{BRANCH}/concepts/{concept_id}/parents",
            params={"form": "inferred"}
        ).json()
    except Exception:
        parents = []
        print("    (could not fetch parents, skipping)")

    time.sleep(DELAY_BETWEEN_CALLS)

    # --- 3. Children ---
    print("  [3/3] Getting child concepts...")
    try:
        children = safe_get(
            f"{BASE_URL}/{BRANCH}/concepts/{concept_id}/children",
            params={"form": "inferred", "limit": 50}
        ).json()
    except Exception:
        children = []
        print("    (could not fetch children, skipping)")

    # --- Display ---
    sep = "=" * 70
    print(f"\n{sep}")
    print("  SNOMED CT Concept Details")
    print(sep)

    print(f"\n  Concept ID      : {data.get('conceptId', 'N/A')}")
    print(f"  Active          : {data.get('active', 'N/A')}")
    print(f"  Definition      : {data.get('definitionStatus', 'N/A')}")
    print(f"  Module ID       : {data.get('moduleId', 'N/A')}")
    print(f"  Effective Time  : {data.get('effectiveTime', 'N/A')}")

    fsn = data.get("fsn", {})
    pt = data.get("pt", {})
    print(f"\n  Fully Specified Name : {fsn.get('term', 'N/A')}")
    print(f"  Preferred Term       : {pt.get('term', 'N/A')}")

    descriptions = data.get("descriptions", [])
    if descriptions:
        print(f"\n  Descriptions ({len(descriptions)}):")
        for d in descriptions:
            status = "active" if d.get("active") else "inactive"
            lang = d.get("lang", "?")
            dtype = d.get("type", "?")
            print(f"    [{status}] ({dtype}, {lang}) {d.get('term', '')}")

    class_axioms = data.get("classAxioms", [])
    if class_axioms:
        print(f"\n  Defining Relationships:")
        for axiom in class_axioms:
            for rel in axiom.get("relationships", []):
                type_term = rel.get("type", {}).get("pt", {}).get("term",
                            rel.get("type", {}).get("fsn", {}).get("term", "?"))
                target_term = rel.get("target", {}).get("pt", {}).get("term",
                              rel.get("target", {}).get("fsn", {}).get("term", "?"))
                target_id = rel.get("target", {}).get("conceptId", "")
                print(f"    * {type_term}  ->  {target_term} ({target_id})")

    if parents:
        print(f"\n  Parent Concepts ({len(parents)}):")
        for p in parents:
            pid = p.get("conceptId", "?")
            pterm = p.get("pt", {}).get("term", p.get("fsn", {}).get("term", "?"))
            print(f"    ^ {pterm} ({pid})")

    if children:
        print(f"\n  Child Concepts ({len(children)}):")
        for c in children:
            cid = c.get("conceptId", "?")
            cterm = c.get("pt", {}).get("term", c.get("fsn", {}).get("term", "?"))
            leaf = " [leaf]" if c.get("isLeafInferred") else ""
            print(f"    v {cterm} ({cid}){leaf}")

    print(f"\n  Browser URL: https://browser.ihtsdotools.org/?perspective=full&conceptId1={concept_id}")
    print(sep)

    # --- Save JSON ---
    output_file = f"snomed_concept_{concept_id}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"concept": data, "parents": parents, "children": children}, f, indent=2, ensure_ascii=False)
    print(f"\n  Raw JSON saved to: {output_file}")
    print("  Done!\n")


if __name__ == "__main__":
    main()
