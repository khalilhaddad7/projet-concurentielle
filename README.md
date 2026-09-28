# Veille Concurrentielle — IA

Plateforme de **veille stratégique** sur les principaux acteurs de l'intelligence
artificielle : **Mistral AI, Hugging Face, OpenAI, Anthropic** et **Google DeepMind**.
L'application collecte automatiquement des articles de presse (NewsAPI), les analyse
avec une chaîne NLP (entités, sentiment, catégorie d'alerte, montants, résumé), les
rend interrogeables via un **chatbot RAG**, et présente le tout dans un **dashboard**
avec graphiques, comparatifs, alertes et exports. Backend **FastAPI**, frontend
**React/Vite**, stockage **PostgreSQL** + **ChromaDB**.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Structure du projet](#structure-du-projet)
- [Prérequis](#prérequis)
- [Installation pas à pas](#installation-pas-à-pas)
- [Lancement](#lancement)
- [Premier démarrage](#premier-démarrage)
- [Utilisation](#utilisation)
- [API](#api)
- [Migrations Alembic](#migrations-alembic)
- [Dépannage](#dépannage)
- [Limites connues et pistes d'amélioration](#limites-connues-et-pistes-damélioration)
- [Sécurité](#sécurité)

---

## Fonctionnalités

- **Collecte d'articles** via NewsAPI pour les 5 concurrents suivis, manuelle ou
  **planifiée** (APScheduler, cycle collecte → NLP → indexation toutes les X heures).
- **Pipeline NLP** : extraction d'entités (spaCy), analyse de sentiment (CamemBERT),
  **catégorie d'alerte via LLM** (Groq, 7 catégories), extraction de montants
  financiers, et **résumé** automatique (LLM local via Ollama).
- **Chatbot RAG** avec **historique des conversations**, **feedback** 👍/👎 par réponse,
  **suggestions** de questions et affichage des **sources** citées.
- **Dashboard** : évolution du sentiment par concurrent, volume d'articles par catégorie,
  scorecard comparatif et frise des **événements critiques**.
- **Alertes** email (SMTP) et/ou webhook **Slack/Discord** sur les articles critiques.
- **Exports** : articles en **CSV / Excel**, et **rapports PDF** (par concurrent et
  hebdomadaire).
- **Authentification JWT** avec rôles **admin** / **lecteur**.

---

## Architecture

```mermaid
flowchart LR
    U[Utilisateur] --> R["Frontend React / Vite<br/>(port 5173)"]
    R -->|"HTTP + JWT"| A["Backend FastAPI<br/>(port 8001)"]

    A --> PG[("PostgreSQL<br/>articles, users,<br/>conversations, logs…")]
    A --> CH[("ChromaDB<br/>base vectorielle")]
    A -->|"embeddings + résumés (local)"| OL["Ollama<br/>nomic-embed-text · llama3.2:3b"]
    A -->|"chatbot + classification des catégories (cloud)"| GR["Groq<br/>openai/gpt-oss-120b"]
    A -->|"collecte d'articles"| NA["NewsAPI"]
```

- **Frontend (React/Vite)** — interface web : dashboard, liste d'articles, chatbot,
  pages de connexion/inscription. Communique avec l'API via Axios en envoyant le JWT.
- **Backend (FastAPI)** — API REST, authentification, orchestration du pipeline
  (collecte, NLP, indexation), scheduler, alertes et exports.
- **PostgreSQL** — stockage relationnel (articles et leurs métadonnées NLP,
  utilisateurs, conversations/messages, journaux d'actions, exécutions planifiées,
  configuration des alertes).
- **ChromaDB** — base vectorielle locale : stocke les embeddings des articles pour la
  recherche sémantique du RAG.
- **Ollama (local)** — génère les **embeddings** (`nomic-embed-text`) et les **résumés**
  d'articles (`llama3.2:3b`). Tourne sur votre machine, aucune donnée envoyée au cloud.
- **Groq (cloud)** — génère les **réponses du chatbot** et **classe la catégorie
  d'alerte** des articles (`openai/gpt-oss-120b`, repli `openai/gpt-oss-20b`), pour la
  rapidité et la fiabilité. Le titre et le contenu de l'article y transitent pour la
  classification ; pour le chatbot, la question et le contexte récupéré.
- **NewsAPI** — source des articles collectés.

---

## Stack technique

| Couche | Technologies (versions) |
|---|---|
| Frontend | React 19.2, React Router 7.18, Recharts 3.10, Axios 1.19, Vite 8.2 |
| API / Web | FastAPI 0.141, Uvicorn 0.52, Pydantic 2.13 |
| Base de données | PostgreSQL, SQLAlchemy 2.0, Alembic 1.18, psycopg2-binary 2.9 |
| NLP | spaCy 3.8 (`fr_core_news_md`), Transformers 5.14, PyTorch 2.13, SentencePiece 0.2 |
| RAG | ChromaDB 1.5, Ollama 0.6, Groq 1.6 |
| Auth | python-jose 3.3, bcrypt 5.0, email-validator 2.2 |
| Planification | APScheduler 3.11 |
| Export | ReportLab 4.2, openpyxl 3.1 |

Les versions backend proviennent de `backend/requirements.txt`, les versions frontend de
`frontend/package.json`.

---

## Structure du projet

```
veille-concurrentielle/
├─ backend/
│  ├─ app/
│  │  ├─ main.py            # Point d'entrée FastAPI (lifespan, routes articles/collecte/NLP)
│  │  ├─ config.py          # Chargement/validation des variables d'environnement
│  │  ├─ database.py        # Moteur SQLAlchemy et session
│  │  ├─ models.py          # Modèles ORM (tables)
│  │  ├─ schemas.py         # Schémas Pydantic (validation entrées/sorties)
│  │  ├─ auth/              # Sécurité : hachage bcrypt, JWT, dépendances get_current_user/require_admin
│  │  ├─ routers/           # Endpoints : auth, chat, stats, scheduler, alerts, export
│  │  └─ services/          # Logique métier : collecte NewsAPI, NLP, RAG, notifications, scheduler, pipeline
│  ├─ alembic/              # Migrations de base de données
│  ├─ scripts/              # Scripts ponctuels (ex : nettoyage de cohérence des données)
│  ├─ requirements.txt      # Dépendances Python
│  └─ .env.example          # Modèle de configuration backend
└─ frontend/
   ├─ src/
   │  ├─ pages/             # Dashboard, Articles, Chatbot, Login, Register
   │  ├─ components/        # Navbar, ProtectedRoute
   │  ├─ context/           # AuthContext (gestion du token et de la session)
   │  ├─ services/          # api.js (client Axios + endpoints)
   │  └─ utils/             # download.js (téléchargement des exports)
   └─ .env.example          # Modèle de configuration frontend
```

---

## Prérequis

- **Python 3.13** (version utilisée pour ce projet).
- **Node.js 20+** (LTS recommandée) et npm.
- **PostgreSQL** (serveur local).
- **Ollama** installé et lancé, avec les modèles `llama3.2:3b` et `nomic-embed-text`.
- Un compte **NewsAPI** (clé API) et un compte **Groq** (clé API).

> **RAM recommandée : au moins 8 Go libres pendant le traitement NLP.** Le modèle
> CamemBERT (via PyTorch) et les modèles Ollama sont gourmands en mémoire.
> Sur une machine trop juste, le traitement NLP peut échouer (voir la section
> [Dépannage](#dépannage) : « fichier de pagination insuffisant » / Ollama qui plante).

---

## Installation pas à pas

Commandes **PowerShell (Windows)**. Adaptez les chemins à votre machine.

### 1. Cloner le dépôt

```powershell
git clone <URL_DU_DEPOT> veille-concurrentielle
cd veille-concurrentielle
```

### 2. Backend — environnement Python

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Modèle spaCy français — INDISPENSABLE, il n'est pas dans requirements.txt :
python -m spacy download fr_core_news_md
```

### 3. Ollama — modèles locaux

```powershell
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### 4. PostgreSQL — base et utilisateur

Dans `psql` (session ouverte avec un rôle administrateur, ex. `postgres`) :

```bash
CREATE USER veille_user WITH PASSWORD 'un_mot_de_passe_exemple';
CREATE DATABASE veille_db OWNER veille_user;
```

### 5. Configuration backend (`.env`)

```powershell
Copy-Item .env.example .env
```

Éditez `backend/.env`. Variables (valeurs d'exemple uniquement, **jamais de vraie clé**) :

```env
# Connexion PostgreSQL (OBLIGATOIRE) — doit correspondre à l'étape 4
DATABASE_URL=postgresql+psycopg2://veille_user:un_mot_de_passe_exemple@localhost:5432/veille_db

# Clés API (OBLIGATOIRES)
GROQ_API_KEY=votre_cle_groq_ici
NEWSAPI_KEY=votre_cle_newsapi_ici

# URL du serveur Ollama local (optionnel, valeur par défaut ci-dessous)
OLLAMA_BASE_URL=http://localhost:11434

# JWT : laisser vide => un secret fort est généré et ajouté à .env au 1er démarrage
JWT_SECRET_KEY=
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30      # durée de l'access token (minutes)
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7         # durée du refresh token (jours)

# Compte admin créé automatiquement au démarrage (changez le mot de passe)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=un_mot_de_passe_admin_exemple

# Collecte planifiée : intervalle en heures entre deux cycles automatiques (défaut 6)
COLLECT_INTERVAL_HOURS=6

# Alertes : "email", "slack", "both" ou "none" (défaut "none" = aucune alerte)
ALERT_CHANNEL=none

# Email SMTP (laisser SMTP_HOST vide pour désactiver l'email)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=          # pour Gmail : un "mot de passe d'application", pas le mot de passe habituel
ALERT_EMAIL_TO=

# Webhook Slack ou Discord (laisser vide pour désactiver ce canal)
SLACK_WEBHOOK_URL=
```

### 6. Appliquer les migrations

```powershell
alembic upgrade head
```

### 7. Frontend

```powershell
cd ..\frontend
npm install
Copy-Item .env.example .env
```

`frontend/.env` contient l'URL de l'API (par défaut `VITE_API_URL=http://127.0.0.1:8001`).

---

## Lancement

### Backend (terminal 1)

```powershell
cd "D:\stage dete projet\veille-concurrentielle\backend"
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8001
```

- API : http://127.0.0.1:8001
- Documentation interactive (Swagger) : http://127.0.0.1:8001/docs

### Frontend (terminal 2)

```powershell
cd "D:\stage dete projet\veille-concurrentielle\frontend"
npm run dev
```

- Interface : http://localhost:5173

### Pourquoi le port 8001 ?

Sur ce PC Windows, le port **8000 est bloqué** (`WinError 10013 — accès à un socket
refusé par ses autorisations`), à cause d'une réservation dynamique de ports par
Hyper-V / WSL2. Le backend tourne donc sur le port **8001**. L'URL de l'API est
centralisée côté frontend dans `frontend/.env` (`VITE_API_URL`) et utilisée partout via
`import.meta.env.VITE_API_URL` (voir `frontend/src/services/api.js`). Pour revenir au
port 8000 (ou tout autre), changez la valeur dans `frontend/.env` **et** le `--port` au
lancement — aucune URL n'est codée en dur. Pensez aussi à l'origine autorisée par le
CORS du backend (voir [Dépannage](#dépannage)).

---

## Premier démarrage

Au démarrage du backend, un **compte admin** est créé automatiquement à partir des
variables `ADMIN_EMAIL` / `ADMIN_PASSWORD` de `backend/.env` (si elles sont définies).
Connectez-vous sur http://localhost:5173 avec ces identifiants.

Ordre d'utilisation recommandé (les 3 premières actions sont réservées aux **admins**) :

1. **Collecter** — récupère les nouveaux articles via NewsAPI.
2. **NLP** — analyse les articles (entités, sentiment, catégorie, résumé). Le traitement
   se fait **par lots** : il faut parfois **cliquer plusieurs fois** pour tout traiter.
3. **Indexer** — pousse les articles traités dans ChromaDB (embeddings) pour le RAG.
4. **Chatbot** — posez vos questions ; les réponses s'appuient sur les articles indexés.

---

## Utilisation

- **Dashboard** — vue d'ensemble : évolution du sentiment par concurrent (sélecteur
  7/30/90 jours), volume d'articles par catégorie, scorecard comparatif, et frise des
  événements critiques. Boutons d'export : **rapport hebdomadaire** (haut de page) et
  **rapport PDF par concurrent** (par ligne du scorecard).
- **Articles** — tableau des articles collectés, avec filtres (concurrent, catégorie,
  sentiment) et menu **Exporter** (CSV / Excel) appliquant les filtres affichés. Les
  boutons **Collecter / NLP / Indexer** ne sont visibles que pour les admins.
- **Chatbot** — conversation avec l'assistant RAG : historique des conversations
  (barre latérale), nouvelle conversation, suppression, boutons **👍/👎** sous chaque
  réponse, **suggestions** de questions et **sources** citées.

### Configurer les alertes (Slack / email)

Les alertes se déclenchent quand un article est classé **critique** pendant le NLP.
Elles se règlent dans `backend/.env` :

- **Canal** : `ALERT_CHANNEL=email`, `slack`, `both` ou `none`.
- **Email (Gmail)** : renseignez `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
  `SMTP_USER`, `SMTP_PASSWORD` (un **mot de passe d'application** Gmail, généré depuis
  votre compte Google avec la validation en 2 étapes activée) et `ALERT_EMAIL_TO`.
- **Slack / Discord** : créez un *Incoming Webhook* (Slack) ou un webhook de salon
  (Discord) et collez son URL dans `SLACK_WEBHOOK_URL`.

Testez sans attendre un vrai article critique via `POST /alerts/test` (rôle admin).
L'activation/désactivation par catégorie se gère via `GET`/`PUT /alert-config` (admin).

---

## API

Documentation interactive complète : **`/docs`** (Swagger). Rôle : *public* (sans
authentification), *connecté* (`get_current_user`), *admin* (`require_admin`).

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/auth/register` | public |
| POST | `/auth/login` | public |
| POST | `/auth/refresh` | public |
| GET | `/auth/me` | connecté |
| GET | `/articles` | connecté |
| POST | `/articles` | admin |
| POST | `/collect` | admin |
| POST | `/process-nlp` | admin |
| POST | `/index-articles` | admin |
| POST | `/chat` | connecté |
| GET | `/conversations` | connecté |
| GET | `/conversations/{id}` | connecté |
| DELETE | `/conversations/{id}` | connecté |
| POST | `/messages/{id}/feedback` | connecté |
| GET | `/chat/suggestions` | connecté |
| GET | `/stats/timeline` | connecté |
| GET | `/stats/comparison` | connecté |
| GET | `/stats/critical-timeline` | connecté |
| GET | `/scheduler/status` | connecté |
| POST | `/scheduler/trigger` | admin |
| GET | `/alert-config` | admin |
| PUT | `/alert-config/{category}` | admin |
| POST | `/alerts/test` | admin |
| GET | `/export/articles` | connecté |
| GET | `/export/report/{competitor}` | connecté |
| GET | `/export/weekly-report` | connecté |

---

## Migrations Alembic

Le schéma PostgreSQL est géré par **Alembic** (et non par `create_all()`). La
configuration lit `DATABASE_URL` depuis `backend/.env`, et les modèles suivis
(dans `backend/app/models.py`) sont `Article`, `User`, `ActionLog`, `SchedulerRun`,
`AlertConfig`, `Conversation` et `Message`. Toutes les commandes se lancent depuis le
dossier `backend/`.

### Appliquer les migrations (mettre la base à jour)

```powershell
cd "D:\stage dete projet\veille-concurrentielle\backend"
alembic upgrade head
```

### Créer une nouvelle migration après avoir modifié un modèle

```powershell
# 1. Générer la migration (Alembic compare les modèles à la base et écrit un fichier
#    dans alembic/versions/). Choisissez un message court et explicite.
alembic revision --autogenerate -m "ajout colonne X sur articles"

# 2. RELISEZ le fichier généré dans alembic/versions/ avant de l'appliquer :
#    vérifiez qu'il ne contient aucune suppression involontaire (drop_table /
#    drop_column) et qu'il correspond bien au changement voulu.

# 3. Appliquer la migration à la base
alembic upgrade head
```

Commandes utiles :

- `alembic current` — révision actuellement appliquée en base.
- `alembic history` — liste des migrations.
- `alembic downgrade -1` — annuler la dernière migration.
- `alembic check` — vérifie si les modèles diffèrent de la base (utile en CI).

> **Note sur la baseline.** La première migration
> (`baseline: etat initial du schema`) capture l'état initial (tables `articles`,
> `users`, `action_logs`). Comme ces tables **existaient déjà** en base, elle y a été
> enregistrée via `alembic stamp head` (marque la révision comme appliquée **sans**
> ré-exécuter les `CREATE TABLE`), afin de ne rien casser ni dupliquer. Sur une base
> **neuve et vide**, un simple `alembic upgrade head` recrée tout le schéma.

---

## Dépannage

| Problème | Cause / Solution |
|---|---|
| **`WinError 10013` sur le port 8000** | Port réservé par Hyper-V / WSL2 sous Windows. Lancez le backend sur le port **8001** (`--port 8001`) et vérifiez que `frontend/.env` pointe vers ce port. |
| **Ollama plante (`llama-server` terminé) ou « fichier de pagination insuffisant »** | Manque de RAM : le modèle NLP CamemBERT et Ollama saturent la mémoire. Fermez des applications, augmentez le fichier de pagination Windows, ou traitez moins d'articles à la fois. Prévoyez ≥ 8 Go libres. |
| **PostgreSQL arrêté au démarrage** | Démarrez le service (PowerShell en **administrateur**), par ex. `Start-Service postgresql-x64-16` (adaptez le nom au vôtre : `Get-Service *postgres*`). Le backend démarre quand même mais les routes utilisant la base renvoient une erreur claire tant que le service est arrêté. |
| **Erreur CORS dans le navigateur** | Le frontend appelle une origine non autorisée. Le backend n'autorise que l'origine du frontend Vite (`http://localhost:5173`) ; utilisez cette adresse et vérifiez que `frontend/.env` pointe vers le **bon port** du backend (8001). |
| **Résumés manquants** | Ollama était indisponible au moment du NLP : l'article reste marqué non traité (`is_processed=false`) et sera **repris automatiquement** au prochain `/process-nlp` une fois Ollama relancé. Vérifiez qu'Ollama tourne et que `llama3.2:3b` est bien téléchargé. |

---

## Limites connues et pistes d'amélioration

- **Classification des catégories dépendante de Groq** : la catégorie d'alerte est
  désormais déterminée par un LLM distant (Groq). C'est bien plus fiable que l'ancien
  *zero-shot* local, mais cela requiert une connexion et la clé `GROQ_API_KEY` ; en cas
  d'échec, l'article retombe en **« Non classé »** (repli sûr, le pipeline continue).
- **Contenu tronqué par NewsAPI** : le plan gratuit ne renvoie qu'un extrait du corps
  des articles, ce qui limite la qualité des résumés et de la recherche.
- **Refresh token en `localStorage`** côté frontend (risque XSS assumé) ; un cookie
  httpOnly serait plus sûr mais impose HTTPS et un ajustement du setup cross-origin.
- **Pas encore de conteneurisation** (Docker) ni de **tests automatisés**.

---

## Sécurité

- **Ne jamais committer le fichier `.env`** (backend ou frontend) : il contient vos clés
  et identifiants. Seuls les `.env.example` sont versionnés.
- **Changez les identifiants par défaut** : en particulier `ADMIN_PASSWORD`, et le mot
  de passe PostgreSQL.
- **Régénérez immédiatement toute clé exposée** (GROQ_API_KEY, NEWSAPI_KEY,
  `JWT_SECRET_KEY`, mots de passe SMTP) si elle a pu fuiter (commit, capture, partage).

---

## Captures d'écran

<!-- ajouter la capture ici -->
![Dashboard](docs/screenshots/dashboard.png)

<!-- ajouter la capture ici -->
![Articles](docs/screenshots/articles.png)

<!-- ajouter la capture ici -->
![Chatbot](docs/screenshots/chatbot.png)

<!-- ajouter la capture ici -->
![Connexion](docs/screenshots/login.png)
