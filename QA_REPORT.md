# SpaceBox — Quality Assurance Report

**Scope:** Application source and offline browser tests; current date: 25 October 2026.

## Automated backend tests

**9 integration tests — passed.** Coverage includes:

- Server-rendered routes with descriptive titles, meta descriptions and canonical URLs.
- Persisted enquiry submission, server validation, explicit consent, CSRF protection, bot honeypot and throttling.
- Restricted administrator routes; incorrect-login and CSRF rejection.
- Project creation and draft privacy: private photos cannot be seen without appropriate authentication.
- Image validation/re-encoding: malformed files rejected; valid JPEG uploaded as optimized WebP.
- Publishing and unpublishing, project gallery URLs, media access and sitemap inclusion.
- Customer enquiry status updates and CSV-formula-injection protection.
- Escaping potentially malicious input in project titles/descriptions.
- Distinct owner/editor/sales permission boundaries and owner-only enquiry deletion.

Run: `PYTHONPATH=. pytest -q tests`.

## Browser/responsiveness tests

**52 page/viewport checks — passed after one fix.** Tested **13 customer routes** at desktop 1440px, laptop/tablet 1024px and 768px, and mobile 390px. Included homepage, Apartments, Villas, Manduva Homes, Offices, Commercial Spaces, Wellness, Our Process, Cost Guide, Projects, About, AI and Contact.

- No horizontal overflow after fixing the 768px contact form grid.
- Manduva planner changes update the visible bedroom count.
- Cost guide updates when changing the property type.
- Six-step infographic responds to click interaction.
- Both desktop and mobile screenshots were captured under the offline rendering harness.

The offline visual-test harness replaces externally hosted photo URLs with representative local images, so its screenshots **do not prove remote image/CDN availability**. Existing approved local Manduva assets are retained.

Run (requires Playwright Chromium separately): `PYTHONPATH=. python scripts/browser_qa.py`.

## Route/static-link audit

**14 customer URLs / 70 image references — no unresolved internal URLs, missing local assets or empty image alt text detected.**

Run: `PYTHONPATH=. python scripts/audit_routes.py`.

## Production controls implemented

- Per-route server-rendered pages with sitemap, robots and Open Graph metadata.
- SQLAlchemy data models and initial Alembic migration.
- Argon2 admin passwords; signed HttpOnly cookies; Secure cookie setting for production; CSRF.
- Form validation, escaping, limited uploads, content sniffing, re-encoding, draft media access control, permission checks, audit log.
- Basic request throttling in the DB, restrictive security headers and TrustedHostMiddleware.
- Admin reporting, CSV export and team roles.
- Startup checks that reject obviously insecure production configuration.

## NOT yet verified — release gates

- Live hosted deployment, DNS/TLS, managed PostgreSQL connectivity in the destination environment and database backup restoration.
- Real SMTP sender/recipient deliverability, notification monitoring and spam-rate controls at the hosting/CDN edge.
- Image licensing/release approvals for every marketing image and legal approval for privacy notice.
- Real-device browser coverage (iOS Safari, Android Chrome), external performance measurements (e.g. Lighthouse on deployed domain), screen-reader accessibility audit and external penetration test.
- Load testing, security monitoring, CDN availability, and multi-instance/object-storage behavior.

**Release recommendation:** Deploy initially to a private/staging domain, close the above blockers, run the go-live checklist and then switch the public domain to the tested release. The package is an implementable application, not proof that it is already live or fully security-certified.
