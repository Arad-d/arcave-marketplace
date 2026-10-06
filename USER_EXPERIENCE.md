# User experience and portfolio

## Checklist

- [x] Check mobile layouts, Persian text direction, and accessibility basics.
- [x] Improve form errors, empty states, and checkout confirmation.
- [x] Add fictional demo products and screenshots.
- [x] Prepare a portfolio case study explaining the project and improvements.
- [ ] Publish the Django demo on a selected hosting account and verify it over HTTPS.
- [ ] Add the case study to the owner's portfolio once its URL or project is supplied.

## Implemented

Visitors can browse and search the catalog before signing in. Cart changes and purchases still require customer authentication. Search filters can be cleared from the empty state; pagination safely encodes search text.

The interface keeps Persian RTL and English LTR. Navigation wraps on small screens, long order references wrap, and tables retain their headers inside keyboard-focusable horizontal scroll regions. Buttons use darker colors for readable text. Keyboard users have a skip link and visible focus indicators. Reduced-motion preferences disable decorative movement. Search, quantity and review controls have accessible names; table headers declare their scope. These are targeted accessibility improvements, not a full WCAG certification or assistive-technology audit.

Registration and product forms render bound Django controls: public values survive invalid submissions, field errors are associated with controls, and an error summary links to the fields. Passwords and recovery answers stay blank after rejection. Selecting a cart quantity no longer unexpectedly submits the page; an explicit Update button applies it. Cart review explains that stock is checked at submission and that no payment is collected. The receipt confirms the recorded order and links to purchase history. Existing signed checkout confirmations, locks, stock checks and duplicate protection remain in place.

## Fictional demo

Use a separate PostgreSQL database whose name starts with `demo_` and differs from `DB_NAME`. The demo settings retain all normal production checks when debug is off, use separate session/CSRF/language cookies, and isolate media under `.demo-media/`. Never copy real customer data into a public demo.

With the normal PostgreSQL connection configured, create an **empty** demo database using your database administrator, then run:

```bash
cd django_project
export DEMO_DB_NAME=demo_arcave
export DJANGO_DEBUG=True  # Local preview only
python manage.py migrate --settings=arcave.demo_settings
python manage.py seed_demo --settings=arcave.demo_settings
python manage.py runserver 127.0.0.1:8002 --settings=arcave.demo_settings
```

The seed command refuses normal settings and any database with existing customer, seller or product records. It never resets or overwrites existing data. To restart a showcase, create another empty isolated database and seed it. It creates six fictional products, one non-staff buyer, one seller, a service-generated purchase, a buyer review and seller reply. Product artwork is original repository-authored SVG; it is copied only by the seed command. Public image uploads still accept only validated JPEG/PNG/WebP.

Shared fictional sign-ins (also displayed in the demo banner):

| Role | Account | Password |
| --- | --- | --- |
| Customer | `demo-buyer` | `Arcave-Demo-2026!` |
| Seller | `demo-seller` | `Arcave-Demo-2026!` |

These are public demonstration credentials, never production credentials. Shared accounts can change listings, stock and their own profiles, so a public interactive demo needs an agreed reset schedule and abuse controls. No payment or shipment takes place. The email uses the reserved `.invalid` domain; no real address or phone is seeded.

## Publishing handoff

Hosting has not been selected or provisioned. The app needs a Python/Django process, PostgreSQL, HTTPS, collected static files and persistent media serving. A static-only host cannot run its checkout or authentication. Follow [SECURITY.md](SECURITY.md) for the actual domain, proxy, cookies, request limits and production checks. Keep the demo database and secret separate from the existing development installation. Do not use Django's development server as the public server.

After hosting is configured, verify language switching, both fictional sign-ins, image loading, one complete checkout, duplicate-submission behavior, and the receipt through the public HTTPS domain. Publish only then. The case study and screenshots are in [docs/portfolio](docs/portfolio/README.md); the actual portfolio integration is waiting for its destination.

## Verification

Five new regression tests cover public browsing with protected cart mutations, retained invalid form values with blank secrets, accessible field-error references, refusal to seed an ordinary database, and one-time fictional seeding through the real checkout service. Run the complete suite as described in [MAINTENANCE.md](MAINTENANCE.md).

Browser checks covered the English/Persian catalog, customer purchase history, product details, cart update and order receipt, seller dashboard and invalid product form. Checked 390-pixel layouts and a 320-pixel Persian receipt for page overflow, plus the normal desktop layout. Screenshots contain only the isolated fictional data. Further screen-reader testing and a broader device matrix remain useful follow-ups.
