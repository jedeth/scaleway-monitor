# ☁️ Scaleway Monitor

> Surveillance de l'infrastructure Scaleway depuis un smartphone — sans serveur permanent.

![PWA](https://img.shields.io/badge/PWA-installable-blue)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-automatisé-green)
![Telegram](https://img.shields.io/badge/Telegram-rapport_quotidien-blue)
![Coût](https://img.shields.io/badge/coût_mensuel-0_€-brightgreen)

---

## Pourquoi ce projet ?

L'infrastructure Scaleway tourne même quand le serveur principal (Établi) est éteint.
Snapshots, IPs flexibles, volumes non attachés — tout continue d'être facturé silencieusement.

Ce projet résout trois problèmes :

1. **Visibilité** — voir en temps réel ce qui coûte quoi, depuis son téléphone
2. **Alertes proactives** — recevoir un rapport chaque matin sur Telegram
3. **Contrôle** — démarrer ou éteindre une instance directement depuis la PWA

Aucun serveur requis. Tout fonctionne via GitHub Actions + GitHub Pages.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions (cron horaire)                              │
│    └── scripts/fetch_data.py → data/scaleway.json          │
│                                                             │
│  GitHub Actions (cron 8h/matin)                            │
│    └── rapport_daily.py → message Telegram                 │
│                                                             │
│  GitHub Actions (workflow_dispatch)                        │
│    └── scripts/action_instance.py → API Scaleway          │
└─────────────────────────────────────────────────────────────┘
         ↓ GitHub Pages (statique)
┌─────────────────────────────────────────────────────────────┐
│  PWA → https://jedeth.github.io/scaleway-monitor/          │
│    ├── Tableau de bord (coûts, alertes)                    │
│    ├── Instances (statut + boutons action)                  │
│    ├── Stockage (volumes, snapshots, IPs)                  │
│    └── Config (token GitHub)                               │
└─────────────────────────────────────────────────────────────┘
         ↑ installable sur écran d'accueil Android/iOS
```

**Pourquoi pas d'appels directs depuis le navigateur ?**
L'API Scaleway ne supporte pas le CORS — un navigateur ne peut pas l'appeler directement.
Solution : les données sont collectées par GitHub Actions et servies en JSON statique.
Les actions (éteindre/démarrer) transitent par GitHub Actions qui appelle Scaleway côté serveur.

---

## Fonctionnalités

### 📊 Tableau de bord
- Coût du mois en cours (API Billing Scaleway)
- Projection fin de mois (extrapolation linéaire)
- Instances actuellement en cours avec coût horaire
- Alertes automatiques : IPs non attachées, volumes orphelins

### 🖥️ Instances
- Liste de toutes les instances des deux projets Scaleway
- Statut temps réel (running / stopped / transition)
- Coût horaire par instance
- **Bouton ⏻ Éteindre** (instance running)
- **Bouton ▶ Démarrer** (instance stopped)
- **Bouton ↺ Redémarrer** (instance running)
- Modale de confirmation avant chaque action

### 💾 Stockage
- Volumes avec taille, instance attachée, coût mensuel
- Snapshots avec date de création, taille, coût mensuel
- IPs flexibles : attachées vs **libres** (facturées inutilement ~1,44 €/mois chacune)
- Alerte visuelle sur les IPs non attachées

### ⚙️ Configuration
- Saisie du token GitHub PAT (stocké en localStorage, jamais dans le code)
- Bouton de test du token
- Informations sur la fréquence de mise à jour

### 📱 Telegram
Rapport automatique chaque matin à 8h (heure de Paris) :
```
☀️ Rapport Scaleway — 20/04/2026

💰 Coût du mois en cours : 36.17 €

🖥️ Instances (1)
  🟢 scw-gracious-wilbur (DEV1-L) — 0.048 €/h en cours

💾 Stockage permanent
  • Volumes     : 40 Go → 1.60 €/mois
  • Snapshots   : 40 Go (1) → 1.60 €/mois
  Total stockage : 3.20 €/mois

🔔 Alertes
  ⚡ 1 instance(s) en cours → 0.048 €/h
```

---

## Projets Scaleway surveillés

| Projet | ID | Zones |
|---|---|---|
| `etabl-ia.fr` | `3a6a9f92-bf5b-4ee9-9c8a-9ee7f48b18bd` | fr-par-1 |
| `TESTPROD` | `3373abc8-dccd-4529-9dc7-cfd185632ac5` | fr-par-1, fr-par-2 |

---

## Structure du repo

```
scaleway-monitor/
│
├── index.html                          ← PWA (HTML/CSS/JS vanilla)
├── manifest.json                       ← Manifest PWA (installable)
├── sw.js                               ← Service Worker (offline)
├── icon-192.png / icon-512.png         ← Icônes PWA
│
├── data/
│   └── scaleway.json                   ← Données générées automatiquement
│
├── scripts/
│   ├── fetch_data.py                   ← Collecte toutes les ressources Scaleway
│   └── action_instance.py             ← Exécute une action sur une instance
│
├── rapport_daily.py                    ← Rapport Telegram quotidien
│
└── .github/workflows/
    ├── refresh-data.yml                ← Cron horaire → data/scaleway.json
    ├── scaleway-rapport-daily.yml      ← Cron 8h → Telegram
    └── action-instance.yml            ← Workflow déclenché par la PWA
```

---

## Workflows GitHub Actions

### `refresh-data.yml` — Mise à jour horaire des données
- **Déclencheur :** cron `0 6-22 * * *` (toutes les heures de 6h à 22h UTC)
- **Actions :** `scripts/fetch_data.py` → commit `data/scaleway.json`
- **Quota GitHub Actions :** ~500 min/mois (plan gratuit = 2000 min/mois)

### `scaleway-rapport-daily.yml` — Rapport Telegram matinal
- **Déclencheur :** cron `0 7 * * *` (8h heure Paris)
- **Actions :** `rapport_daily.py` → envoi message Telegram
- Peut aussi être déclenché manuellement depuis l'onglet Actions de GitHub

### `action-instance.yml` — Actions sur instances
- **Déclencheur :** `workflow_dispatch` (déclenché par la PWA via l'API GitHub)
- **Inputs :** `action` (poweroff/poweron/reboot), `instance_id`, `zone`
- **Actions :** `scripts/action_instance.py` → attend l'état final → rafraîchit `data/scaleway.json`
- **Durée :** ~1-2 minutes (attente transition + commit)

---

## Installation

### Prérequis
- Compte GitHub
- Compte Scaleway avec clé API
- Bot Telegram (optionnel, pour les rapports matinaux)

### 1. Cloner le repo
```bash
git clone https://github.com/jedeth/scaleway-monitor.git
cd scaleway-monitor
```

### 2. Configurer les secrets GitHub
Dans **Settings → Secrets and variables → Actions**, créer ces secrets :

| Secret | Description | Exemple |
|---|---|---|
| `SCALEWAY_SECRET_KEY` | Clé secrète API Scaleway | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `SCALEWAY_PROJECT_ID` | ID du projet principal | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `SCALEWAY_DEFAULT_ZONE` | Zone par défaut | `fr-par-1` |
| `TELEGRAM_BOT_TOKEN` | Token du bot Telegram | `123456789:AAF_xxx` |
| `TELEGRAM_CHAT_ID` | Ton Chat ID Telegram | `123456789` |

**Obtenir les clés Scaleway :**
1. console.scaleway.com → IAM → API Keys → Générer une clé
2. Permissions recommandées : `InstancesReadOnly` + `BillingRead` pour la lecture
3. Pour les actions (éteindre/démarrer) : ajouter `InstancesReadWrite`

**Obtenir le token Telegram :**
1. Ouvrir Telegram → chercher `@BotFather`
2. `/newbot` → suivre les instructions
3. Copier le token fourni
4. Envoyer un message au bot → `https://api.telegram.org/bot{TOKEN}/getUpdates` → noter le `chat.id`

### 3. Activer GitHub Pages
Dans **Settings → Pages** :
- Source : `Deploy from a branch`
- Branch : `main` / `/ (root)`

La PWA sera accessible sur `https://{username}.github.io/scaleway-monitor/`

### 4. Adapter les projets Scaleway surveillés
Dans `scripts/fetch_data.py`, modifier le dictionnaire `PROJETS` :
```python
PROJETS = {
    "mon-projet": {
        "id":    "uuid-de-mon-projet",
        "zones": ["fr-par-1"],
    },
}
```
Et `ORG_ID` pour le coût mensuel global.

### 5. Premier lancement
Déclencher manuellement le workflow `refresh-data.yml` depuis l'onglet **Actions** de GitHub pour générer les premières données.

### 6. Installer la PWA sur Android
1. Ouvrir `https://jedeth.github.io/scaleway-monitor/` dans Chrome
2. Menu ⋮ → **"Ajouter à l'écran d'accueil"**
3. L'app s'installe comme une application native

### 7. Configurer le token pour les actions
Dans la PWA → onglet **⚙️ Config** → coller un token GitHub PAT avec le scope `workflow`.

**Créer un token GitHub PAT :**
GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
Cocher : ✅ `repo` + ✅ `workflow`

---

## Modèle de coûts Scaleway (référence)

| Ressource | Facturation | Arrêt avec l'instance ? |
|---|---|---|
| Instance (started) | à l'heure, selon type | Oui |
| Instance (stopped) | 0 € | — |
| Volume attaché | ~0,04 €/Go/mois | **Non** |
| Snapshot | ~0,04 €/Go/mois | **Non** |
| IP flexible non attachée | ~0,002 €/h ≈ 1,44 €/mois | **Non** |

### Tarifs horaires (extrait)
| Type | €/h | €/jour | €/mois (30j) |
|---|---|---|---|
| DEV1-S | 0,012 | 0,29 | 8,64 |
| DEV1-M | 0,024 | 0,58 | 17,28 |
| DEV1-L | 0,048 | 1,15 | 34,56 |
| GP1-S | 0,296 | 7,10 | 213,12 |
| GPU-3070-S | 1,290 | 30,96 | 928,80 |

> ⚠️ Un snapshot de 40 Go = 1,60 €/mois en permanence, même instance éteinte.
> 3 IPs flexibles non attachées = 4,32 €/mois facturés inutilement.

---

## Sécurité

- Les clés Scaleway sont dans **GitHub Secrets** — jamais dans le code ni dans les fichiers du repo
- Le token GitHub PAT est stocké dans **localStorage du navigateur** — jamais transmis à un serveur tiers
- Les actions sur instances passent par GitHub Actions (serveur GitHub) → API Scaleway — le token Scaleway ne transite jamais par le navigateur
- Le `data/scaleway.json` ne contient **aucune clé** — uniquement des données de monitoring non sensibles (noms, coûts, statuts)
- Le repo est public uniquement pour GitHub Pages gratuit — aucune donnée confidentielle n'y est exposée

---

## Roadmap

- [ ] **B3 — Instance éphémère GPU** : créer une instance depuis un snapshot → transcrire un audio → supprimer l'instance (garder le snapshot)
- [ ] Graphique historique des coûts sur 30 jours
- [ ] Notification Telegram sur dépassement de seuil
- [ ] Support multi-zones automatique (découverte dynamique)
- [ ] Gestion des Managed Databases Scaleway

---

## Contexte

Ce repo fait partie du projet **[Établi](https://etabl-ia.fr)** — plateforme souveraine de création d'applications augmentée par l'IA, développée pour l'Académie de Paris (DRASI).

Le module `infrastructure-manager` d'Établi gère les instances Scaleway depuis l'interface principale.
Ce repo est la version **standalone** — fonctionne indépendamment d'Établi.
