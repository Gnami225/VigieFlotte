# VigieFlotte — Gestion des pièces administratives de flotte

Application **Streamlit + Neon (PostgreSQL)** pour le suivi documentaire d'une
flotte de camions et d'engins : carte grise, carte de transport, stationnement,
visite technique, patente, assurance, autorisations porte-chars et papiers de
douane. Édition type Excel, alertes d'expiration (in-app et **e-mail
automatique**), tableaux de bord, **suivi des coûts**, **pièces jointes
scannées**, **journal d'audit**, **rôles/authentification** et **exports
Excel/PDF**.

---

## 1. Aperçu fonctionnel

- **Tableau de bord** : KPI (conformité, pièces expirées, à renouveler, alertes
  porte-chars), répartition des états (donut), état par type de pièce (barres
  empilées), **carte de conformité** véhicules × pièces (heatmap), conformité par
  catégorie, et liste des échéances imminentes.
- **Camions / Engins** : **tableau de gestion éditable** (modification des cellules
  en place, ajout de lignes via « + », suppression, puis bouton *Enregistrer* qui
  écrit en base) avec recherche instantanée ; possession en liste Oui/Non/— et
  échéances au calendrier ; renouvellement rapide qui calcule la prochaine
  échéance selon la règle. Un second onglet « Vue conformité » offre la lecture
  colorée avec filtres par colonne (AgGrid).
- **Porte-chars** : **tableau éditable** des couples (ajout/modification/suppression
  de lignes), état calculé affiché, renouvellement +6 mois.
- **Alertes** : horizon paramétrable, export CSV.
- **Import / Admin** : import d'une feuille Excel/CSV de mise à jour, état de la
  base, réinitialisation depuis les fichiers fournis.

### Règles métier des pièces

| Pièce | Catégorie | Logique | Alerte |
|---|---|---|---|
| Carte grise | Camion | Possession (sans échéance) | — |
| Carte de transport | Camion | Échéance datée (cycle 2 ans) | 2 mois |
| Carte de stationnement | Camion | Annuelle, échéance 31 janvier | 2 mois |
| Patente | Camion | Annuelle, échéance 31 janvier | 2 mois |
| Visite technique | Camion | Échéance datée (cycle 1 an) | 2 mois |
| Assurance | Camion + Engin | Échéance datée (cycle 1 an) | 2 mois |
| Douanes | Engin | Possession (sans échéance) | — |
| Autorisation porte-chars | Couple | Échéance datée (cycle 6 mois) | **1 mois** |

---

## 1bis. Nouvelles fonctionnalités de gestion

- **Authentification & rôles** : trois rôles — *admin* (tout + journal d'audit +
  réinitialisation), *editeur* (édition des données), *lecteur* (consultation et
  exports seuls). Configurés dans les secrets ; sans configuration, l'app démarre
  en mode ouvert (admin) pour le développement.
- **Journal d'audit** : chaque création, modification, suppression et paiement est
  tracé (utilisateur, horodatage, cible, ancienne → nouvelle valeur). Page réservée
  à l'admin, exportable en CSV.
- **Coûts & budget** : enregistrement du montant de chaque renouvellement, avec
  dépense par mois, par type de pièce, total annuel et historique exportable.
- **Pièces jointes** : rattachement de scans (PDF/images) à chaque véhicule et
  chaque type de pièce, stockés en base, téléchargeables lors d'un contrôle.
- **Exports** : bouton Excel (synthèse, échéances, véhicules, porte-chars, coûts)
  et PDF (synthèse d'une page) depuis le tableau de bord.
- **Alertes e-mail** : envoi manuel (bouton) ou automatique (cron / GitHub Actions)
  de la liste des pièces à traiter aux responsables.
- **Complétude & rapprochement** : indicateur de complétude des données, et
  détection des couples porte-chars référençant une immatriculation absente de la
  base camions.

## 1ter. Configuration des secrets

Copiez `.streamlit/secrets.toml.example` en `.streamlit/secrets.toml` (ou collez
les blocs dans *Settings → Secrets* sur Streamlit Cloud). Trois sections :

- `[neon]` — connexion PostgreSQL (obligatoire pour le cloud).
- `[auth]` — comptes et rôles (JSON). Mots de passe en clair ou `sha256:<hash>`.
  Générer un hash : `python -c "import hashlib;print('sha256:'+hashlib.sha256('MONMDP'.encode()).hexdigest())"`.
- `[email]` — paramètres SMTP pour les alertes (hôte, port, identifiants,
  expéditeur, destinataires séparés par des virgules, seuil en jours).

## 1quater. Alertes e-mail automatiques

Trois options :

1. **Depuis l'app** : page *Alertes* → bouton « Envoyer l'alerte maintenant ».
2. **GitHub Actions** (fourni : `.github/workflows/alertes.yml`) : envoi
   hebdomadaire. Renseignez les *repository secrets* `NEON_URL`, `SMTP_HOST`,
   `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`.
3. **Cron serveur** : `python alertes_mail.py` avec les mêmes variables
   d'environnement.

---

## 2. Installation locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sans secret configuré, l'application bascule automatiquement sur une base
**SQLite locale** (`fleet_local.db`) et charge les bases fournies au premier
lancement — pratique pour un essai immédiat.

---

## 3. Connexion à Neon (PostgreSQL cloud)

1. Créez un projet sur [neon.tech](https://neon.tech) (offre gratuite suffisante).
2. Dans le dashboard Neon, bouton **Connect** → récupérez la chaîne de connexion.
3. Adaptez-la au format SQLAlchemy + psycopg2 (gardez `sslmode=require`) :

   ```
   postgresql+psycopg2://UTILISATEUR:MOTDEPASSE@HOTE.neon.tech/NOMBASE?sslmode=require
   ```

4. Copiez `.streamlit/secrets.toml.example` en `.streamlit/secrets.toml` et
   collez votre URL :

   ```toml
   [neon]
   url = "postgresql+psycopg2://...:...@...neon.tech/...?sslmode=require"
   ```

Au premier démarrage, le schéma (`vehicles`, `documents`, `porte_chars_couples`)
est créé et les bases initiales sont chargées automatiquement.

---

## 4. Déploiement sur Streamlit Community Cloud

1. Poussez le dossier sur un dépôt GitHub.
2. Sur [share.streamlit.io](https://share.streamlit.io), créez une app pointant
   sur `app.py`.
3. Dans **Settings → Secrets**, collez :

   ```toml
   [neon]
   url = "postgresql+psycopg2://...:...@...neon.tech/...?sslmode=require"
   ```

4. Déployez. Neon conserve les données entre les redémarrages de l'app.

---

## 5. Structure du projet

```
fleet_app/
├── app.py                      # Application Streamlit (navigation + pages)
├── auth.py                     # Authentification & rôles
├── db.py                       # Neon/SQLite : schéma, CRUD, audit, coûts, scans
├── rules.py                    # Moteur métier : états, échéances (sans dépendance)
├── seed.py                     # Chargement initial des bases
├── ui.py                       # Helpers : tableau Excel (AgGrid), badges, états
├── exports.py                  # Générateurs Excel et PDF
├── alertes_mail.py             # Alertes e-mail (script cron + appel in-app)
├── requirements.txt
├── data/                       # engins.psv (80), camions.psv (61), couples.psv (4)
├── .streamlit/
│   ├── config.toml             # Thème olive/blanc clair
│   └── secrets.toml.example     # Gabarit : [neon], [auth], [email]
├── .github/workflows/
│   └── alertes.yml             # Envoi e-mail hebdomadaire (GitHub Actions)
└── README.md
```

---

## 6. Mises à jour ultérieures

Deux voies pour maintenir les données à jour :

- **Dans l'application** : pages Camions/Engins/Porte-chars → modification pièce
  par pièce, bouton Renouveler, ajout/suppression.
- **Par import** : page Import/Admin → chargez une feuille Excel/CSV contenant une
  colonne `immatriculation` (ou `code_interne`) ; les colonnes reconnues
  (carte grise, carte de transport, assurance, expiration assurance, etc.) mettent
  à jour ou créent les pièces. Les véhicules inconnus sont créés.

---

## 7. Notes techniques

- Le moteur d'états (`rules.py`) est isolé et testable unitairement.
- Le tableau « confort Excel » utilise `streamlit-aggrid`; en cas d'absence, repli
  automatique sur `st.dataframe` (l'app reste fonctionnelle).
- Écritures encadrées par transactions ; caches de lecture invalidés après chaque
  mutation. Upsert idempotent sur `(vehicle_id, type_doc)`.
