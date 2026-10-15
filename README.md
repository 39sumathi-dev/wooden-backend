# SK Wood Turnery — FastAPI Backend

A lightweight, performant API backend serving product catalogs, Cloudflare R2 image pipeline, MongoDB Atlas persistence, and custom turning inquiries for the SK Wood Turnery digital flagship.

## 🚀 Quickstart

### 1. Set Up Virtual Environment (Optional but recommended)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # macOS / Linux
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file based on `.env.example`:
```bash
copy .env.example .env
```
Ensure your MongoDB URI and Cloudflare R2 credentials are configured in `.env`.

### 4. Run Development Server
```bash
uvicorn main:app --reload --port 8000
```

The API will be available at:
- **Interactive API Docs (Swagger UI):** http://localhost:8000/docs
- **ReDoc Documentation:** http://localhost:8000/redoc
- **API Root:** http://localhost:8000/

---

## 📦 Pushing Backend to Its Own Repository

If you want to maintain and deploy the backend in its own separate GitHub/GitLab repository:

> **Important**: The `.env` file is listed in `.gitignore` so your secrets (database password, Cloudflare keys) will **not** be uploaded to GitHub.

```bash
# 1. Open the backend folder
cd d:\woodturnery\backend

# 2. Initialize Git
git init

# 3. Add files and make your initial commit
git add .
git commit -m "feat: initial backend fastapi commit"

# 4. Set default branch to main
git branch -M main

# 5. Link to your new backend GitHub repository
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_BACKEND_REPO>.git

# 6. Push to GitHub
git push -u origin main
```
