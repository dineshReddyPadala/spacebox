# SpaceBox Concepts — Website Application

**Status:** Tested application source, prepared for production hosting. **Not publicly deployed.**

This is the server-rendered rebuild of the approved SpaceBox customer-facing prototype. It retains the approved color palette, layout language, SpaceBox logo, traditional Manduva visuals, Vastu/wellness message and interactive calculators while adding proper routes, a database, an enquiry workflow and authenticated project-gallery administration.

## Key pages and features

| Customer page | Route |
|---|---|
| Homepage | `/` |
| Apartments | `/apartments` |
| Villas | `/villas` |
| Manduva Homes, planner and gallery | `/manduva-homes` |
| Offices | `/offices` |
| Hotels, restaurants, cafés / commercial spaces | `/commercial-spaces` |
| Wellness+ | `/wellness` |
| Six-stage design and execution journey | `/our-process` |
| Interactive cost guide | `/cost-guide` |
| Published portfolio | `/projects` and `/projects/{slug}` |
| About | `/about` |
| SpaceBox AI (Coming Soon) | `/spacebox-ai` |
| Consultation enquiry form | `/contact` |
| Admin login and workspace | `/admin/login`, `/admin/` |

The public gallery displays only projects expressly **published** in the admin. Projects can be drafted, edited, assigned a category/status, supplied with optimized photos, marked featured, published/unpublished, and archived. Draft photographs cannot be accessed anonymously.

Enquiries are validated, consent-based, CSRF-protected and persisted to the database. Team email notification is available when SMTP credentials are configured. A working admin dashboard stores and exports records even if SMTP isn't configured.

## Recommended production architecture

**FastAPI + Jinja2 + PostgreSQL** with a managed hosting provider (example: Render), managed TLS, secure admin sessions, a persistent encrypted media volume and encrypted backups. The starter deployment is deliberately **one web instance** because its photo storage uses a persistent filesystem. For multi-instance scaling, replace that storage with an S3-compatible object store and CDN, then retest access control and image serving.

Database schema changes are managed using Alembic migrations. Never treat `.db` files or production credentials as files to publish.

## Run on a development computer

Use **Python 3.12 or newer**.

```bash
cd spacebox_production
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env for your local settings.
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Copy this generated value into APP_SECRET in .env.
alembic upgrade head
python scripts/bootstrap_admin.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000**. Admin: **http://localhost:8000/admin/login**.

Running this locally is not equivalent to putting it online. External images and Google Fonts in the marketing design require internet access. Licensed, locally hosted project photography is preferable for the public launch.

## Admin team and roles

Use the bootstrap script to create an account with a strong individual password:

- **Owner** — projects, publishing, enquiries, exports, deletion.
- **Editor** — draft/project creation, upload and publishing; cannot read customer enquiries.
- **Sales** — read/manage enquiries; cannot change projects or view private draft imagery.

For a staff account, set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_ROLE=editor` (or `sales`), then run `python scripts/bootstrap_admin.py` and enter a unique password. The script also securely rotates an existing user's credentials. Do not share admin accounts. Admin passwords use Argon2; session cookies are signed, HTTP-only and marked Secure when `APP_ENV=production`.

## Production readiness and limitations

See **DEPLOYMENT.md**, **QA_REPORT.md** and **LAUNCH_CHECKLIST.md**. Public launch requires a domain/hosting decision, production credentials, SMTP setup, final approved legal/privacy copy, and the rights to publish any illustrative imagery. Actual project photos and testimonials must be genuine, and the 10-year company claim should be confirmed in official content.

No live deployment, purchased domain, paid hosting account, email delivery test or external penetration test has been performed in this handoff.
