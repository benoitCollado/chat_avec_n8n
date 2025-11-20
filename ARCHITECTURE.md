# Architecture fonctionnelle & technique

## Vue d’ensemble

```
┌──────────────┐        HTTP (JSON)        ┌────────────────────┐
│  Frontend    │  ───────────────────────▶ │  Backend FastAPI    │
│  Vue 3 + TS  │ ◀───────────────────────  │  + SQLite + n8n     │
└──────────────┘         Webhooks          └─────────┬──────────┘
       ▲                                             │
       │                                             ▼
       │                                    ┌────────────────┐
       │     Workflow automatisé            │  Webhook n8n   │
       └────────────────────────────────────┴────────────────┘
```

| Couche      | Techno / Librairies               | Rôle principal                                            |
|-------------|-----------------------------------|-----------------------------------------------------------|
| Frontend    | Vue 3, TypeScript, Vite           | Authentification, chat UI, appels API sécurisés          |
| Backend API | FastAPI, SQLAlchemy, HTTPX        | Auth JWT/Refresh, persistance SQLite, relai vers n8n     |
| Sécurité    | JWT (PyJWT), bcrypt               | Hashage mots de passe, génération/validation des tokens  |
| Base de données | SQLite (SQLAlchemy ORM)      | Tables `users` et `messages` liées, historique isolé     |

## Backend FastAPI

### Structure des fichiers principaux

```
backend/
├─ app/
│  ├─ main.py          # Déclaration FastAPI + routes /api
│  ├─ config.py        # Paramètres (env, CORS, JWT…)
│  ├─ database.py      # Engine, SessionLocal, Base
│  ├─ models.py        # ORM User & Message
│  ├─ schemas.py       # Pydantic (User, Message, Tokens…)
│  ├─ crud.py          # Opérations DB (users, messages)
│  ├─ security.py      # Hash, JWT, dépendance get_current_user
│  └─ __init__.py
├─ env.example
└─ requirements.txt
```

### Parcours algorithmique des endpoints (`/api/*`)

#### 1. Auth

| Endpoint | Algorithme clé |
|----------|----------------|
| `POST /auth/register` | 1) Valider payload `schemas.UserCreate`. 2) `get_user_by_email`; si existe → 400. 3) `hash_password` (bcrypt). 4) `create_user` (commit SQLite). 5) `issue_tokens` (`create_access_token` + `create_refresh_token`). |
| `POST /auth/login` | 1) Valider `schemas.UserLogin`. 2) `authenticate_user` (email + `verify_password`). 3) Si échec → 401. 4) `issue_tokens`. |
| `POST /auth/refresh` | 1) Valider `schemas.RefreshRequest`. 2) `decode_token(refresh)`. 3) `session.get(User, sub)` sinon 401. 4) `issue_tokens`. |
| `GET /auth/me` | 1) Dépendance `get_current_user`: lire header Bearer, `decode_token(access)`, `session.get`. 2) Retourner `schemas.UserOut`. |

#### 2. Chat & historique

| Endpoint | Algorithme clé |
|----------|----------------|
| `GET /messages` | 1) `get_current_user`. 2) `crud.list_messages(user, limit)` (SELECT filtré). 3) `reversed()` pour ordre chronologique. 4) `schemas.MessageOut`. |
| `POST /chat` | 1) Valider `schemas.ChatRequest` (`content`, `user_id`). 2) `get_current_user` + `payload.user_id == current_user.id` sinon 403. 3) `create_message(...)` (direction user). 4) `forward_to_n8n(payload.model_dump())`. 5) Extraire `reply_text` (`reply` > `message` > `text` > JSON complet). 6) `create_message` pour la réponse bot. 7) Retourner `schemas.ChatResponse`. |

#### 3. Health

`GET /health` → renvoie simplement `{"status": "ok"}` (utile pour probes).

### Détails techniques

- **Config** (`config.py`) : centralise `N8N_WEBHOOK_URL`, `FRONTEND_ORIGIN`, secrets JWT, durées des tokens, chemin SQLite…
- **Base de données**
  - `User`: `id`, `email` (unique), `full_name`, `hashed_password`, `created_at`.
  - `Message`: `id`, `author`, `content`, `direction`, `created_at`, `user_id` (FK vers `users`).
- **CRUD**
  - `create_user`, `authenticate_user`, `get_user_by_email`.
  - `create_message` (associe message ↔ utilisateur), `list_messages` (tri descendant, scope utilisateur).
- **Sécurité**
  - `hash_password` / `verify_password` (bcrypt).
  - `create_access_token` / `create_refresh_token` (PyJWT, `HS256`, durées configurables).
  - `decode_token` + `get_current_user` (dépendance FastAPI, rejet si token absent/expiré).
- **Appels n8n** : `forward_to_n8n` utilise HTTPX, gère erreurs et fallback JSON/texte. Si `reply` n’est pas dans la réponse, sérialise le JSON complet.
- **CORS** : origins autorisées configurables (`FRONTEND_ORIGIN` séparées par virgules); middleware autorise méthodes/headers `*`.

## Frontend Vue 3 + TypeScript

### Arborescence pertinente

```
frontend/src/
├─ App.vue              # UI principale (auth + chat)
├─ main.ts              # bootstrap Vue
├─ style.css            # styles globaux (forms, panels…)
├─ services/
│  ├─ authApi.ts        # Register/login/refresh/me
│  └─ chatApi.ts        # Messages + envoi vers /api/chat
└─ types.ts             # Interfaces User, Message, TokenPair…
```

### Fonctionnement UI détaillé

| Étape | Algorithme côté `App.vue` |
|-------|---------------------------|
| Initialisation | 1) Lire tokens dans `localStorage`. 2) Si présents, appeler `authApi.me`. 3) En cas d’échec → `refreshSession` (appel `/auth/refresh`). 4) Si succès → `currentUser` set et `loadHistory`. |
| Formulaire Auth | 1) `authMode` (`login`/`register`). 2) `handleAuthSubmit` construit le payload puis appelle `authApi.register` ou `authApi.login`. 3) `persistSession` stocke tokens + user et déclenche `loadHistory`. |
| `loadHistory` | 1) Vérifie `accessToken`. 2) Utilise `callWithAuth` (wrapper gérant les 401) pour appeler `chatApi.fetchHistory(limit, token)`. 3) Met à jour `messages` ou `errorMessage`. |
| Envoi message | 1) Vérifier champ non vide. 2) `callWithAuth(token => chatApi.sendMessage({ content, user_id }, token))`. 3) Ajoute `response.user` + `response.bot` à la liste. 4) Réinitialise le champ + états. |
| Refresh token auto | 1) `callWithAuth` capture `ApiError(401)`. 2) `refreshSession` appelle `/auth/refresh` puis `persistSession`. 3) Rejoue la requête initiale. |
| Déconnexion | 1) `clearSession` supprime tokens du storage, reset `currentUser` + `messages`. |

### UI/UX

- Un seul composant `App.vue` : sections Auth + Chat affichées conditionnellement.
- Status visuels (`ghost buttons`, bulles colorées selon `direction`).
- Responsive : layout en colonne < 720px, boutons plein écran en mobile.

### Cycle complet utilisateur

```
[Inscription / Connexion] ──► [Tokens stockés] ──► [GET /api/messages]
                                        │
                                        ▼
                                [POST /api/chat]
                                        │
                                   Appel n8n
                                        │
                          [Réponse stockée + renvoyée]
                                        ▼
                                [UI mise à jour]
```

## Paramétrage & exécution

### Backend

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # éditer N8N_WEBHOOK_URL, FRONTEND_ORIGIN, secrets JWT…
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp env.example .env  # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

## Notes & bonnes pratiques

- **SQLite** : casser `chat.db` si le modèle change (pas de migrations automatiques).
- **n8n** : ajouter un nœud “HTTP Response” renvoyant un JSON contenant `reply` pour que la réponse s’affiche côté front. En mode test (`/webhook-test`), cliquer sur “Execute workflow” avant chaque requête.
- **Sécurité** : toujours utiliser HTTPS pour exposer l’API en production, renouveler le `JWT_SECRET_KEY`, réduire la durée des tokens selon vos besoins et envisager un stockage sécurisé pour les refresh tokens.

Ce document couvre les composants livrés, leurs interactions et les étapes pour exécuter/adapter le projet. N’hésitez pas à l’enrichir si l’architecture évolue (multi-tenant, rôles, files d’attente, etc.).

