# Website security improvements

This document covers the Django website. The original `main.py` terminal prototype is retained for historical reference and should not be used with real account credentials.

## Implemented and tested

- [x] Hash customer and seller recovery answers and migrate existing answers. Answers are normalized consistently; blank legacy answers cannot authorize recovery.
- [x] Require both recovery answers in order. Challenges and reset grants each expire after ten minutes. Five failed answers impose a fifteen-minute account-level recovery lock, including across browser sessions. Login lockouts also apply during recovery.
- [x] Bind reset grants to the account and its current password. Changing the password invalidates outstanding grants. PostgreSQL row locks prevent parallel guesses from bypassing the limit and prevent simultaneous reset redemption.
- [x] Enforce Django's configured password validators in signup, profile changes, and recovery. Passwords are capped at 128 characters. Signup excludes staff, superuser, and seller role fields.
- [x] Require POST and CSRF validation for checkout, cart changes, deletion, comments, replies, and logout. The templates submit protected forms.
- [x] Enforce store ownership and customer cart ownership. Seller sessions require a password-bound authentication hash and are revoked when passwords change. Switching roles clears the previous identity. Product comments require a purchase by the current customer.
- [x] Validate product uploads in both seller and admin forms: JPEG, PNG, or WebP; at most 5 MiB; at most 4096 pixels per dimension and 16 million total pixels. Images are decoded and re-encoded under generated filenames, removing metadata and trailing content. Invalid uploads do not change existing products.
- [x] Protect admin credential fields. Customer administration uses Django's password forms; seller credentials are excluded from direct editing.
- [x] Fail closed on unsafe production secrets or missing/wildcard host configuration. Production defaults enforce HTTPS redirects, secure cookies, HSTS, content-type protection, same-origin referrers, and denied framing.

## Apply to an existing installation

Back up the database with a `pg_dump` version at least as new as the PostgreSQL server, and verify the backup before upgrading. Preserve any existing `.env` file; it contains local credentials and must never be committed.

```bash
cd django_project
python manage.py migrate
python manage.py test accounts shop
```

The database user running the tests needs permission to create a separate test database. The concurrent recovery tests require PostgreSQL; they are skipped on backends without row-level locking.

Existing seller sessions require a fresh login after this update. Hash migrations preserve the user's passwords and answers, but their original plaintext cannot be recovered by reversing the migration. Accounts without usable recovery answers cannot use question-based recovery.

## Deployment configuration

Set these through your hosting environment or private `.env`:

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY`: a newly generated private key of at least 50 characters; never reuse a development key.
- `DJANGO_ALLOWED_HOSTS`: explicit comma-separated production domain names, without URL schemes or wildcards.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: additional trusted HTTPS origins only if your deployment actually needs them; leave empty for a same-origin site.
- `DJANGO_TRUST_PROXY_HTTPS=True` only if the trusted TLS proxy strips client-supplied `X-Forwarded-Proto` and sets it itself. Otherwise keep it false.

HSTS applies to the configured host for one year. Subdomain coverage and preload are deliberately disabled until every affected domain is known to support HTTPS.

Before accepting real users:

- [ ] Configure the real domain and a valid TLS certificate, then test redirects and cookies through the actual proxy.
- [ ] Serve uploaded media from a separate media origin with no script execution and correct content types.
- [ ] Enforce a request-body limit at the reverse proxy, and configure request rate limits for login and recovery. Application-level file validation cannot replace proxy limits on incoming upload traffic.
- [ ] Run `python manage.py check --deploy` against the actual production configuration.
- [ ] Add operational monitoring and a tested backup/restore process.

Question-based recovery still depends on users choosing answers that others cannot guess. A future production version should move to verified, time-limited email recovery or stronger authentication.

## References

- [Django password management](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/)
- [Django security guidance](https://docs.djangoproject.com/en/5.2/topics/security/)
- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
