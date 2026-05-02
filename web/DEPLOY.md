# Deploying to Railway

## What you're deploying

| Service | What it does |
|---|---|
| **backend** | FastAPI — handles auth, user prefs, episode API |
| **frontend** | React — the web UI your friends use |
| **worker** | Celery — generates episodes in the background |
| **PostgreSQL** | Railway managed DB — stores users & episodes |
| **Redis** | Railway managed Redis — Celery task queue |

---

## Step 1 — Create a Railway account

Go to [railway.app](https://railway.app) and sign up (free tier works to start).

---

## Step 2 — Create a new project

1. Click **New Project** → **Empty project**
2. Name it `daily-news-podcast`

---

## Step 3 — Add PostgreSQL and Redis

In your project dashboard:
1. Click **+ New** → **Database** → **PostgreSQL** — Railway provisions it automatically
2. Click **+ New** → **Database** → **Redis** — same

---

## Step 4 — Deploy the backend

1. Click **+ New** → **GitHub Repo** (connect your GitHub account first)
2. Select this repo, set **Root Directory** to `web/backend`
3. Railway will detect the Dockerfile automatically

**Set these environment variables** in the backend service settings:

```
DATABASE_URL        = (copy from PostgreSQL service → Variables → DATABASE_URL)
REDIS_URL           = (copy from Redis service → Variables → REDIS_URL)
SECRET_KEY          = (generate a random 32-char string)
FRONTEND_URL        = https://your-frontend.up.railway.app  (set after frontend deploys)
BASE_URL            = https://your-backend.up.railway.app
```

For audio storage, either:
- Leave blank to use local `/tmp` (files lost on redeploy — fine for testing)
- Or add S3/R2 credentials:
  ```
  AWS_BUCKET_NAME   = your-bucket
  AWS_REGION        = us-east-1
  AWS_ACCESS_KEY_ID = ...
  AWS_SECRET_ACCESS_KEY = ...
  ```

---

## Step 5 — Deploy the Celery worker

1. Click **+ New** → **GitHub Repo** → same repo, root `web/backend`
2. **Override the start command** to:
   ```
   celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
   ```
3. Add the **same environment variables** as the backend (DATABASE_URL, REDIS_URL, SECRET_KEY, etc.)

---

## Step 6 — Deploy the frontend

1. Click **+ New** → **GitHub Repo** → same repo, root `web/frontend`
2. Add build variable:
   ```
   VITE_API_URL = https://your-backend.up.railway.app
   ```
3. After deploy, copy the frontend URL and set it as `FRONTEND_URL` in the backend service

---

## Step 7 — Share with friends

Send them your frontend URL: `https://your-frontend.up.railway.app`

They register, pick their interests in the onboarding flow, and their first episode
generates automatically. Each user gets their own personalised podcast every day.

---

## Costs

Railway free tier gives $5/month credit. With PostgreSQL + Redis + 2 services
you'll likely need the **Hobby plan ($5/month)** once you have a few active users.
Audio files in `/tmp` are free but ephemeral — add an S3 bucket (~$0.02/GB) for
persistent storage.
