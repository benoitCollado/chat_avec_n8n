# Chat Auto n8n

Application full-stack combinant **FastAPI + SQLite** et **Vue 3 + TypeScript (Vite)** pour envoyer des messages à un webhook n8n tout en conservant l’historique localement.

## Structure

- `backend/` – API FastAPI, base SQLite, venv local `.venv`
- `frontend/` – SPA Vue 3 via Vite

## Démarrage Backend

```bash
cd /Users/benoitcollado/cursor_projects/chat_auto_n8n/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # créez le fichier si besoin
uvicorn app.main:app --reload
```

Variables disponibles :

- `N8N_WEBHOOK_URL` – URL complète du webhook n8n attendu.
- `FRONTEND_ORIGIN` – Origine autorisée pour le CORS (ex. `http://localhost:5173`), séparez par une virgule pour plusieurs valeurs.
- `JWT_SECRET_KEY` – Clé secrète utilisée pour signer les tokens.
- `ACCESS_TOKEN_EXP_MINUTES` / `REFRESH_TOKEN_EXP_MINUTES` – Durées de vie des tokens.

## Démarrage Frontend

```bash
cd /Users/benoitcollado/cursor_projects/chat_auto_n8n/frontend
npm install
npm run dev
```

Copiez `env.example` en `.env` si besoin et définissez `VITE_API_BASE_URL` (ex. `http://localhost:8000`) pour pointer vers l’API.

Identifiez-vous via l’UI : inscription (création utilisateur) ou connexion renvoient un couple `access/refresh token`. Les requêtes chat nécessitent un utilisateur authentifié.

> ⚠️ En cas de changement de schéma (ajout des utilisateurs/messages reliés), supprimez `backend/chat.db` pour repartir sur une base saine.

Toutes les routes FastAPI sont exposées sous le préfixe `/api` (ex. `http://localhost:8000/api/messages`, `/api/chat`, `/api/auth/login`, etc.). Ajustez vos appels externes ou vos workflows n8n en conséquence.

## Flux

1. L’utilisateur envoie un message depuis l’UI.
2. Le backend l’enregistre dans SQLite puis transmet au webhook n8n.
3. La réponse du webhook est stockée et renvoyée au frontend qui met à jour l’historique.

