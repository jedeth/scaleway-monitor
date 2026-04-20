#!/usr/bin/env python3
"""
Rapport journalier Scaleway → Telegram
Appelle directement api.scaleway.com, aucun serveur intermédiaire requis.
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Config ─────────────────────────────────────────────────────────────────
SCALEWAY_SECRET_KEY = os.environ["SCALEWAY_SECRET_KEY"]
SCALEWAY_PROJECT_ID = os.environ["SCALEWAY_PROJECT_ID"]
SCALEWAY_ZONE       = os.environ.get("SCALEWAY_DEFAULT_ZONE", "fr-par-1")
TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]

SCW_BASE  = f"https://api.scaleway.com/instance/v1/zones/{SCALEWAY_ZONE}"
SCW_BILL  = "https://api.scaleway.com/billing/v2beta1"
SCW_HDR   = {"X-Auth-Token": SCALEWAY_SECRET_KEY, "Content-Type": "application/json"}

TARIFS = {
    "DEV1-S": 0.012, "DEV1-M": 0.024, "DEV1-L": 0.048, "DEV1-XL": 0.072,
    "GP1-XS": 0.148, "GP1-S": 0.296, "GP1-M": 0.562, "GP1-L": 1.007,
    "GPU-3070-S": 1.290, "RENDER-S": 0.740,
    "PLAY2-NANO": 0.005, "PLAY2-MICRO": 0.010, "PLAY2-PICO": 0.003,
}

# ── Helpers ────────────────────────────────────────────────────────────────

def scw_get(path: str) -> dict:
    url = path if path.startswith("http") else f"{SCW_BASE}{path}"
    req = urllib.request.Request(url, headers=SCW_HDR)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[WARN] GET {url} → {e.code}: {body[:200]}", file=sys.stderr)
        return {}


def send_telegram(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"[ERROR] Telegram: {e}", file=sys.stderr)
        return False


def format_euros(v: float) -> str:
    return f"{v:.2f} €"


def go_short(gb: float) -> str:
    return f"{gb:.0f} Go" if gb >= 1 else f"{int(gb * 1024)} Mo"

# ── Collecte données ───────────────────────────────────────────────────────

def get_instances() -> list[dict]:
    data = scw_get(f"/servers?project={SCALEWAY_PROJECT_ID}&per_page=50")
    return data.get("servers", [])


def get_volumes() -> list[dict]:
    data = scw_get(f"/volumes?project={SCALEWAY_PROJECT_ID}&per_page=50")
    return data.get("volumes", [])


def get_snapshots() -> list[dict]:
    data = scw_get(f"/snapshots?project={SCALEWAY_PROJECT_ID}&per_page=50")
    return data.get("snapshots", [])


def get_images() -> list[dict]:
    data = scw_get(f"/images?project={SCALEWAY_PROJECT_ID}&per_page=50")
    return data.get("images", [])


def get_cout_mensuel() -> float:
    now = datetime.now(timezone.utc)
    mois = now.strftime("%Y-%m")
    data = scw_get(f"{SCW_BILL}/consumptions?project_id={SCALEWAY_PROJECT_ID}")
    total = 0.0
    for item in data.get("consumptions", []):
        val = item.get("value", {})
        if isinstance(val, dict):
            total += float(val.get("units", 0)) + float(val.get("nanos", 0)) / 1e9
        elif isinstance(val, (int, float)):
            total += float(val)
    return total

# ── Construction du rapport ────────────────────────────────────────────────

def build_rapport() -> str:
    now = datetime.now(timezone.utc)
    date_fr = now.strftime("%d/%m/%Y")
    PRIX_GO_MOIS = 0.04  # €/Go/mois Scaleway

    instances  = get_instances()
    volumes    = get_volumes()
    snapshots  = get_snapshots()
    images     = get_images()
    cout_mois  = get_cout_mensuel()

    # ── Instances ──────────────────────────────────────────────────────────
    running = [s for s in instances if s.get("state") == "running"]
    stopped = [s for s in instances if s.get("state") != "running"]
    cout_horaire_actuel = sum(
        TARIFS.get(s.get("commercial_type", ""), 0) for s in running
    )

    lignes_instances = []
    for s in sorted(instances, key=lambda x: x.get("state", "")):
        etat  = "🟢" if s.get("state") == "running" else "🔴"
        nom   = s.get("name", "?")
        ctype = s.get("commercial_type", "?")
        tarif = TARIFS.get(ctype, 0)
        if s.get("state") == "running":
            lignes_instances.append(f"  {etat} {nom} ({ctype}) — {tarif:.3f} €/h en cours")
        else:
            lignes_instances.append(f"  {etat} {nom} ({ctype}) — arrêtée")

    # ── Stockage ───────────────────────────────────────────────────────────
    vol_go   = sum(v.get("size", 0) for v in volumes) / 1e9
    snap_go  = sum(s.get("size", 0) for s in snapshots) / 1e9
    img_go   = sum(i.get("root_volume", {}).get("size", 0) for i in images) / 1e9

    # Volumes attachés (non comptés séparément si liés à une instance)
    vol_libres = [v for v in volumes if not v.get("server")]

    cout_vol  = vol_go  * PRIX_GO_MOIS
    cout_snap = snap_go * PRIX_GO_MOIS
    cout_img  = img_go  * PRIX_GO_MOIS
    cout_stockage = cout_vol + cout_snap + cout_img

    # ── Alertes ────────────────────────────────────────────────────────────
    alertes = []
    if running:
        alertes.append(f"⚡ {len(running)} instance(s) en cours → {cout_horaire_actuel:.3f} €/h")
    if len(snapshots) >= 5:
        alertes.append(f"📸 {len(snapshots)} snapshots → penser à nettoyer les anciens")
    if cout_stockage > 5:
        alertes.append(f"💾 Stockage total > 5 €/mois — vérifier les volumes libres")
    if len(vol_libres) > 0:
        alertes.append(f"📦 {len(vol_libres)} volume(s) non attaché(s) — facturés inutilement")

    # ── Assemblage ─────────────────────────────────────────────────────────
    lignes = [
        f"☀️ <b>Rapport Scaleway — {date_fr}</b>",
        "",
        f"💰 <b>Coût du mois en cours : {format_euros(cout_mois)}</b>",
        "",
        f"🖥️ <b>Instances ({len(instances)})</b>",
    ]
    lignes += lignes_instances if lignes_instances else ["  Aucune instance enregistrée"]

    lignes += [
        "",
        f"💾 <b>Stockage permanent</b>",
        f"  • Volumes     : {go_short(vol_go)} → {format_euros(cout_vol)}/mois",
        f"  • Snapshots   : {go_short(snap_go)} ({len(snapshots)}) → {format_euros(cout_snap)}/mois",
        f"  • Images      : {go_short(img_go)} ({len(images)}) → {format_euros(cout_img)}/mois",
        f"  <b>Total stockage : {format_euros(cout_stockage)}/mois</b>",
    ]

    if alertes:
        lignes += ["", "🔔 <b>Alertes</b>"] + [f"  {a}" for a in alertes]
    else:
        lignes += ["", "✅ Aucune alerte"]

    lignes += [
        "",
        f"<i>Zone : {SCALEWAY_ZONE} — {now.strftime('%H:%Mh UTC')}</i>",
    ]

    return "\n".join(lignes)


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Collecte des données Scaleway...", file=sys.stderr)
    rapport = build_rapport()
    print(rapport, file=sys.stderr)
    print("Envoi Telegram...", file=sys.stderr)
    ok = send_telegram(rapport)
    if ok:
        print("✅ Rapport envoyé avec succès", file=sys.stderr)
    else:
        print("❌ Échec envoi Telegram", file=sys.stderr)
        sys.exit(1)
