#!/usr/bin/env python3
"""
Exécute une action (poweroff / poweron / reboot) sur une instance Scaleway.
Attend la fin de la transition avant de terminer.
"""

import os, sys, json, time, urllib.request, urllib.error

SECRET_KEY  = os.environ["SCALEWAY_SECRET_KEY"]
ACTION      = os.environ["SCW_ACTION"]       # poweroff | poweron | reboot
INSTANCE_ID = os.environ["SCW_INSTANCE_ID"]
ZONE        = os.environ.get("SCW_ZONE", "fr-par-1")

BASE = f"https://api.scaleway.com/instance/v1/zones/{ZONE}/servers/{INSTANCE_ID}"
HDR  = {"X-Auth-Token": SECRET_KEY, "Content-Type": "application/json"}

ACTIONS_VALIDES = ("poweroff", "poweron", "reboot")
ETATS_FINAUX = {
    "poweroff": "stopped",
    "poweron":  "running",
    "reboot":   "running",
}

def req(method, url, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

if ACTION not in ACTIONS_VALIDES:
    print(f"[ERROR] Action invalide : {ACTION}. Valeurs acceptées : {ACTIONS_VALIDES}")
    sys.exit(1)

# Récupérer l'état actuel
server_data, status = req("GET", BASE)
if status != 200:
    print(f"[ERROR] Instance introuvable ({status}): {server_data}")
    sys.exit(1)

server = server_data.get("server", {})
etat_actuel = server.get("state")
nom = server.get("name", INSTANCE_ID)
print(f"Instance : {nom} ({ZONE}) — état actuel : {etat_actuel}")

# Vérifications de cohérence
if ACTION == "poweroff" and etat_actuel == "stopped":
    print("Instance déjà arrêtée. Aucune action nécessaire.")
    sys.exit(0)
if ACTION == "poweron" and etat_actuel == "running":
    print("Instance déjà démarrée. Aucune action nécessaire.")
    sys.exit(0)

# Exécuter l'action
print(f"→ Envoi action : {ACTION}…")
resp, status = req("POST", f"{BASE}/action", {"action": ACTION})
if status not in (200, 202):
    print(f"[ERROR] Échec action ({status}): {resp}")
    sys.exit(1)
print(f"  Action acceptée (HTTP {status})")

# Attendre l'état final (max 5 minutes)
etat_cible = ETATS_FINAUX[ACTION]
print(f"→ Attente état '{etat_cible}'…")
for i in range(60):
    time.sleep(5)
    data, _ = req("GET", BASE)
    etat = data.get("server", {}).get("state", "unknown")
    print(f"  [{i*5}s] état : {etat}")
    if etat == etat_cible:
        ip = data.get("server", {}).get("public_ip", {})
        ip_addr = ip.get("address") if ip else None
        print(f"✅ Instance {nom} → {etat}" + (f" ({ip_addr})" if ip_addr else ""))
        sys.exit(0)
    if etat in ("error", "locked"):
        print(f"[ERROR] État inattendu : {etat}")
        sys.exit(1)

print(f"[WARN] Timeout — état final non atteint après 5 minutes")
sys.exit(1)
