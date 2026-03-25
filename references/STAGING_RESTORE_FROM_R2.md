# Restore Staging From Production R2 Backup

## One-time setup

Save the R2 connection values on the staging site once:

```bash
cd /workspace/development/frappe-bench

bench --site dev1.localhost set-config mob_clinic_r2_restore_bucket cue360-prod-backups
bench --site dev1.localhost set-config mob_clinic_r2_restore_endpoint_url https://<ACCOUNT_ID>.r2.cloudflarestorage.com
bench --site dev1.localhost set-config mob_clinic_r2_restore_access_key_id <ACCESS_KEY_ID>
bench --site dev1.localhost set-config mob_clinic_r2_restore_secret_access_key <SECRET_ACCESS_KEY>
```

Optional, only if the bucket contains backups for more than one production site:

```bash
bench --site dev1.localhost set-config mob_clinic_r2_restore_source_site_slug cue360_localhost
```

Optional, only if backups live under a bucket prefix:

```bash
bench --site dev1.localhost set-config mob_clinic_r2_restore_prefix backups
```

## Refresh staging

Dry run first:

```bash
bench --site dev1.localhost restore-from-r2 --dry-run
```

Real restore:

```bash
bench --site dev1.localhost restore-from-r2 --yes
```

## What the command does

- Finds the newest database backup in the configured R2 bucket
- Downloads the matching database, files, private files, and site config backup
- Restores them into the selected staging site
- Copies `encryption_key` and `backup_encryption_key` from production backup config into staging
- Disables the scheduler after restore

## Notes

- The command overwrites the selected site.
- Keep outbound email and external integrations disabled on staging.
- If your database restore needs explicit DB root credentials, pass them on the command:

```bash
bench --site dev1.localhost restore-from-r2 --yes \
  --db-root-username root \
  --db-root-password '<password>'
```
