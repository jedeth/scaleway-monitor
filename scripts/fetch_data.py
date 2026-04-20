#!/usr/bin/env python3
"""
Collecte les données Scaleway et sort un JSON sur stdout.
Appelé par GitHub Actions toutes les heures.
"""

import os, sys, json, urllib.request, urllib.error
from datetime import datetime, timezone

SCALEWAY_SECRET_KEY = os.environ["SCALEWAY_SECRET_KEY"]
SCALEWAY_PROJECT_ID = os.environ["SCALEWAY_PROJECT_ID"]
SCALEWAY_ZONE       = os.environ.get("SCALEWAY_DEFAULT_ZONE", "fr-par-1")

SCW_BASE = f"https://api.scaleway.com/instance/v1/zones/{SCALEWAY_ZONE}"
SCW_BILL = "https://api.scaleway.com/billing/v2beta1"
HDR      = {"X-Auth-Token": SCALEWAY_SECRET_KEY, "Content-Type": "application/json"}

TARIFS = {
    "DEV1-S": 0.012, "DEV1-M": 0.024, "DEV1-L": 0.048, "DEV1-XL": 0.072,
    "GP1-XS": 0.148, "GP1-S": 0.296, "GP1-M": 0.562, "GP1-L": 1.007,
    "GPU-3070-S": 1.290, "RENDER-S": 0.740,
    "PLAY2-NANO": 0.005, "PLAY2-MICRO": 0.010, "PLAY2-PICO": 0.003,
}

def get(path):
    url = path if path.startswith("http") else f"{SCW_BASE}{path}"
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[WARN] {url}: {e}", file=sys.stderr)
        return {}

now     = datetime.now(timezone.utc)
servers = get(f"/servers?project={SCALEWAY_PROJECT_ID}&per_page=50").get("servers", [])
volumes = get(f"/volumes?project={SCALEWAY_PROJECT_ID}&per_page=50").get("volumes", [])
snaps   = get(f"/snapshots?project={SCALEWAY_PROJECT_ID}&per_page=50").get("snapshots", [])
images  = get(f"/images?project={SCALEWAY_PROJECT_ID}&per_page=50").get("images", [])

# Coût mensuel via API Billing
cout_mois = 0.0
bill = get(f"{SCW_BILL}/consumptions?project_id={SCALEWAY_PROJECT_ID}")
for item in bill.get("consumptions", []):
    val = item.get("value", {})
    if isinstance(val, dict):
        cout_mois += float(val.get("units", 0)) + float(val.get("nanos", 0)) / 1e9
    elif isinstance(val, (int, float)):
        cout_mois += float(val)

PRIX_GO = 0.04  # €/Go/mois

def go(octets):
    return round(octets / 1e9, 2)

instances_data = []
for s in servers:
    tarif = TARIFS.get(s.get("commercial_type", ""), 0)
    instances_data.append({
        "id":    s.get("id"),
        "nom":   s.get("name"),
        "type":  s.get("commercial_type"),
        "etat":  s.get("state"),
        "ip":    s.get("public_ip", {}).get("address") if s.get("public_ip") else None,
        "zone":  s.get("zone"),
        "tarif_heure": tarif,
    })

vol_go   = sum(v.get("size", 0) for v in volumes) / 1e9
snap_go  = sum(s.get("size", 0) for s in snaps)   / 1e9
img_go   = sum(i.get("root_volume", {}).get("size", 0) for i in images) / 1e9

volumes_data = [{
    "id":     v.get("id"), "nom": v.get("name"),
    "taille_go": go(v.get("size", 0)),
    "serveur":   v.get("server", {}).get("name") if v.get("server") else None,
    "cout_mois": round(go(v.get("size", 0)) * PRIX_GO, 3),
} for v in volumes]

snaps_data = [{
    "id":     s.get("id"), "nom": s.get("name"),
    "taille_go": go(s.get("size", 0)),
    "date":   s.get("creation_date", "")[:10],
    "cout_mois": round(go(s.get("size", 0)) * PRIX_GO, 3),
} for s in snaps]

result = {
    "mis_a_jour":    now.isoformat(),
    "zone":          SCALEWAY_ZONE,
    "cout_mois":     round(cout_mois, 2),
    "stockage": {
        "volumes_go":  round(vol_go, 2),
        "snaps_go":    round(snap_go, 2),
        "images_go":   round(img_go, 2),
        "cout_total":  round((vol_go + snap_go + img_go) * PRIX_GO, 2),
    },
    "instances":  instances_data,
    "volumes":    volumes_data,
    "snapshots":  snaps_data,
}

print(json.dumps(result, ensure_ascii=False, indent=2))
