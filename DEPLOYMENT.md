# SpaceBox — Production Deployment Guide

This application **can be deployed** using Render or any managed Python container host. The steps below are deliberately conservative and designed for one initially deployed service.

## 1. Prepare the launch materials

- Confirm the domain name, logo rights, business legal entity name, public contact number and working email.
- Obtain explicit usage rights for all Manduva/reference photos and other visual assets. **Do not publish an image merely because it appears in the prototype.** Remove any watermarked or third-party images that are not licensed.
- Sign off project descriptions and any testimonials. The site will not invent projects or customer reviews.
- Have Indian counsel review the privacy notice, enquiry consent, retention and marketing communications.
- Choose a team mailbox and outbound SMTP provider to receive enquiry notifications.

## 2. Push the source to a private Git repository

Upload the files in this package to a private GitHub/GitLab repository. Do not commit `.env`, real passwords, local databases, backup exports or private-media files. The included `.gitignore` helps with this.

## 3. Provision hosting

A `render.yaml` example is included. On Render:

1. Connect the repository to a new Blueprint/Web Service.
2. Create a **paid managed PostgreSQL database** with regular backups.
3. Create a persistent disk mounted at `/var/data`, with `MEDIA_DIR=/var/data/uploads`. This starter stores uploads on the disk. **Do not deploy it on ephemeral storage.**
4. Use Python runtime, `pip install -r requirements.txt` as build command and `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` as start command.
5. Set `APP_ENV=production`, `DATABASE_URL` (managed Postgres connection string), `SITE_URL=https://your-approved-domain.example`, `ALLOWED_HOSTS=your-approved-domain.example,www.your-approved-domain.example` (plus the hosting subdomain if you use it), `APP_SECRET` (at least 40 random characters), `MEDIA_DIR=/var/data/uploads`, `CONTACT_EMAIL`, `CONTACT_PHONE`, and SMTP variables if notifications are required.
6. Configure the custom domain DNS, TLS/HTTPS certificate and the intended www/non-www canonical domain, then update `SITE_URL` and `ALLOWED_HOSTS` to match.
7. Set up an independent backup/restore check for both PostgreSQL and uploaded media. Render persistent disks affect deployment behavior and do not offer horizontal scaling by default.

Docs: https://render.com/docs/web-services and https://render.com/docs/disks

Generate `APP_SECRET` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

The app intentionally refuses to start in production if the secret, HTTPS URL, trusted hosts or PostgreSQL connection is missing.

## 4. Create the first admin

After the production database migration, use a secure container/shell command (never in a public web form):

```bash
export BOOTSTRAP_ADMIN_EMAIL="owner@your-approved-domain.example"
export BOOTSTRAP_ADMIN_ROLE="owner"
python scripts/bootstrap_admin.py
```

The script securely prompts for the password. It can also use `BOOTSTRAP_ADMIN_PASSWORD` in a temporary secret environment setting; remove that secret as soon as the admin is created. Repeat with unique credentials for editors and sales staff.

## 5. Set up enquiry notifications

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `NOTIFY_EMAIL` and `SMTP_STARTTLS`. Test with an authorized internal enquiry and verify **both**: (a) the record is stored in the admin and (b) the notification arrives. If SMTP is absent/fails, the record is still stored, but no notification is guaranteed.

Recommended: managed transactional email, SPF/DKIM/DMARC on your authorized domain. Never insert email provider keys into frontend JavaScript.

## 6. Go-live smoke checks

After TLS and DNS are live:

- `/healthz` responds; homepage and all service pages return HTTP 200 over HTTPS.
- Admin login works over a Secure, HttpOnly session cookie.
- A submitted test enquiry appears in `/admin/leads` and sends a notification when configured.
- An image uploaded into a **draft** project cannot be opened by an anonymous visitor.
- After publishing, the public project page and image work and appear in `/sitemap.xml`.
- Publishing/unpublishing and admin roles work; no unauthorized visitor can access admin.
- All reference images, fonts, logo and mobile menus render on real phones.
- Site canonical URLs and `robots.txt` refer to the actual domain.
- Search Console, analytics/cookie governance (if used), uptime alerting, error alerting and backup-restoration tests are configured.

**Important:** This release uses local media on a persistent disk. For high traffic/multiple replicas, plan a migration to object storage and CDN; then load-test that architecture independently.
