#!/usr/bin/env python3
"""
Collecte les données des deux projets Scaleway (multi-zones) et sort un JSON sur stdout.
Appelé par GitHub Actions toutes les heures.
"""

import os, sys, json, urllib.request
from datetime import datetime, timezone

SCALEWAY_SECRET_KEY = os.environ["SCALEWAY_SECRET_KEY"]
ORG_ID   = "3373abc8-dccd-4529-9dc7-cfd185632ac5"
HDR      = {"X-Auth-Token": SCALEWAY_SECRET_KEY}

# Zones à surveiller par projet
PROJETS = {
    "etabl-ia.fr": {
        "id":    "3a6a9f92-bf5b-4ee9-9c8a-9ee7f48b18bd",
        "zones": ["fr-par-1"],
    },
    "TESTPROD": {
        "id":    "3373abc8-dccd-4529-9dc7-cfd185632ac5",
        "zones": ["fr-par-1", "fr-par-2"],
    },
}

TARIFS = {
    "DEV1-S": 0.012, "DEV1-M": 0.024, "DEV1-L": 0.048, "DEV1-XL": 0.072,
    "GP1-XS": 0.148, "GP1-S": 0.296, "GP1-M": 0.562, "GP1-L": 1.007,
    "GPU-3070-S": 1.290, "RENDER-S": 0.740,
    "PLAY2-NANO": 0.005, "PLAY2-MICRO": 0.010, "PLAY2-PICO": 0.003,
}

PRIX_GO       = 0.04    # €/Go/mois
PRIX_IP_LIBRE = 0.002   # €/h par IP flexible non attachée → ~1,44€/mois

def get(url):
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[WARN] {url}: {e}", file=sys.stderr)
        return {}

def go(octets):
    return round(octets / 1e9, 2)

def collect_zone(pid, zone):
    base = f"https://api.scaleway.com/instance/v1/zones/{zone}"
    return {
        "servers":         get(f"{base}/servers?project={pid}&per_page=50").get("servers", []),
        "volumes":         get(f"{base}/volumes?project={pid}&per_page=50").get("volumes", []),
        "snapshots":       get(f"{base}/snapshots?project={pid}&per_page=50").get("snapshots", []),
        "images":          get(f"{base}/images?project={pid}&per_page=50").get("images", []),
        "ips":             get(f"{base}/ips?project={pid}&per_page=50").get("ips", []),
        "security_groups": get(f"{base}/security_groups?project={pid}&per_page=50").get("security_groups", []),
    }

def collect_projet(nom, cfg):
    pid   = cfg["id"]
    zones = cfg["zones"]

    # Agréger toutes les zones
    all_servers, all_volumes, all_snaps, all_images = [], [], [], []
    all_ips, all_sgs = [], []

    for zone in zones:
        print(f"[INFO]   zone {zone}…", file=sys.stderr)
        z = collect_zone(pid, zone)
        # Injecter la zone dans chaque objet pour l'affichage
        for s in z["servers"]:   s["_zone"] = zone
        for v in z["volumes"]:   v["_zone"] = zone
        for s in z["snapshots"]: s["_zone"] = zone
        for ip in z["ips"]:      ip["_zone"] = zone
        for sg in z["security_groups"]: sg["_zone"] = zone
        all_servers  += z["servers"]
        all_volumes  += z["volumes"]
        all_snaps    += z["snapshots"]
        all_images   += z["images"]
        all_ips      += z["ips"]
        all_sgs      += z["security_groups"]

    instances_data = [{
        "id":          s.get("id"),
        "nom":         s.get("name"),
        "type":        s.get("commercial_type"),
        "etat":        s.get("state"),
        "ip":          s.get("public_ip", {}).get("address") if s.get("public_ip") else None,
        "zone":        s.get("_zone"),
        "tarif_heure": TARIFS.get(s.get("commercial_type", ""), 0),
    } for s in all_servers]

    volumes_data = [{
        "id":        v.get("id"),
        "nom":       v.get("name"),
        "taille_go": go(v.get("size", 0)),
        "zone":      v.get("_zone"),
        "serveur":   v.get("server", {}).get("name") if v.get("server") else None,
        "cout_mois": round(go(v.get("size", 0)) * PRIX_GO, 3),
    } for v in all_volumes]

    snaps_data = [{
        "id":        s.get("id"),
        "nom":       s.get("name"),
        "taille_go": go(s.get("size", 0)),
        "zone":      s.get("_zone"),
        "date":      s.get("creation_date", "")[:10],
        "cout_mois": round(go(s.get("size", 0)) * PRIX_GO, 3),
    } for s in all_snaps]

    ips_data = [{
        "id":        ip.get("id"),
        "adresse":   ip.get("address"),
        "zone":      ip.get("_zone"),
        "attachee":  ip.get("server") is not None,
        "serveur":   ip.get("server", {}).get("name") if ip.get("server") else None,
        "cout_mois": 0 if ip.get("server") else round(PRIX_IP_LIBRE * 24 * 30, 2),
    } for ip in all_ips]

    sgs_data = [{
        "id":          sg.get("id"),
        "nom":         sg.get("name"),
        "zone":        sg.get("_zone"),
        "stateful":    sg.get("stateful", False),
        "par_defaut":  sg.get("project_default", False),
    } for sg in all_sgs]

    vol_go  = sum(v.get("size", 0) for v in all_volumes) / 1e9
    snap_go = sum(s.get("size", 0) for s in all_snaps) / 1e9
    img_go  = sum(i.get("root_volume", {}).get("size", 0) for i in all_images) / 1e9
    cout_ip_libres = sum(ip["cout_mois"] for ip in ips_data if not ip["attachee"])

    return {
        "id":               pid,
        "zones":            zones,
        "instances":        instances_data,
        "volumes":          volumes_data,
        "snapshots":        snaps_data,
        "ips_flexibles":    ips_data,
        "groupes_securite": sgs_data,
        "stockage": {
            "volumes_go": round(vol_go, 2),
            "snaps_go":   round(snap_go, 2),
            "images_go":  round(img_go, 2),
            "cout_total": round((vol_go + snap_go + img_go) * PRIX_GO, 2),
        },
        "cout_ips_libres": round(cout_ip_libres, 2),
    }

def get_cout_mensuel():
    data = get(f"https://api.scaleway.com/billing/v2beta1/consumptions?organization_id={ORG_ID}")
    total = 0.0
    for item in data.get("consumptions", []):
        val = item.get("value", {})
        if isinstance(val, dict):
            total += float(val.get("units", 0)) + float(val.get("nanos", 0)) / 1e9
        elif isinstance(val, (int, float)):
            total += float(val)
    return round(total, 2)

# ── Collecte ─────────────────────────────────────────────────────────────
now = datetime.now(timezone.utc)
projets_data = {}
for nom, cfg in PROJETS.items():
    print(f"[INFO] Collecte projet {nom}…", file=sys.stderr)
    projets_data[nom] = collect_projet(nom, cfg)

cout_mois = get_cout_mensuel()

print(json.dumps({
    "mis_a_jour": now.isoformat(),
    "cout_mois":  cout_mois,
    "projets":    projets_data,
}, ensure_ascii=False, indent=2))
