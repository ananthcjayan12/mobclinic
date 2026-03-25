import unittest
from datetime import datetime

from mob_clinic.r2_restore import BackupObject, resolve_restore_config, select_latest_backup_bundle


class TestR2RestoreHelpers(unittest.TestCase):
	def test_select_latest_backup_bundle_prefers_newest_matching_bundle(self):
		objects = [
			BackupObject(
				key="20260324_020000/20260324_020000-cue360_localhost-database.sql.gz",
				last_modified=datetime(2026, 3, 24, 2, 0, 0),
			),
			BackupObject(
				key="20260324_020000/20260324_020000-cue360_localhost-files.tar",
				last_modified=datetime(2026, 3, 24, 2, 0, 0),
			),
			BackupObject(
				key="20260324_020000/20260324_020000-cue360_localhost-private-files.tar",
				last_modified=datetime(2026, 3, 24, 2, 0, 0),
			),
			BackupObject(
				key="20260324_020000/20260324_020000-cue360_localhost-site_config_backup.json",
				last_modified=datetime(2026, 3, 24, 2, 0, 0),
			),
			BackupObject(
				key="20260325_020000/20260325_020000-cue360_localhost-database-enc.sql.gz",
				last_modified=datetime(2026, 3, 25, 2, 0, 0),
			),
			BackupObject(
				key="20260325_020000/20260325_020000-cue360_localhost-files-enc.tar",
				last_modified=datetime(2026, 3, 25, 2, 0, 0),
			),
			BackupObject(
				key="20260325_020000/20260325_020000-cue360_localhost-private-files-enc.tar",
				last_modified=datetime(2026, 3, 25, 2, 0, 0),
			),
			BackupObject(
				key="20260325_020000/20260325_020000-cue360_localhost-site_config_backup-enc.json",
				last_modified=datetime(2026, 3, 25, 2, 0, 0),
			),
		]

		bundle = select_latest_backup_bundle(objects, source_site_slug="cue360_localhost")

		self.assertEqual(bundle.stamp, "20260325_020000")
		self.assertTrue(bundle.encrypted)
		self.assertEqual(
			bundle.site_config_key,
			"20260325_020000/20260325_020000-cue360_localhost-site_config_backup-enc.json",
		)
		self.assertEqual(
			bundle.public_files_key,
			"20260325_020000/20260325_020000-cue360_localhost-files-enc.tar",
		)

	def test_select_latest_backup_bundle_ignores_partial_backups(self):
		objects = [
			BackupObject(
				key="20260325_020000/20260325_020000-cue360_localhost-partial-database.sql.gz",
				last_modified=datetime(2026, 3, 25, 2, 0, 0),
			),
			BackupObject(
				key="20260324_020000/20260324_020000-cue360_localhost-database.sql.gz",
				last_modified=datetime(2026, 3, 24, 2, 0, 0),
			),
		]

		bundle = select_latest_backup_bundle(objects, source_site_slug="cue360_localhost")

		self.assertEqual(bundle.database_key, "20260324_020000/20260324_020000-cue360_localhost-database.sql.gz")

	def test_resolve_restore_config_prefers_cli_then_site_config_then_env(self):
		config = resolve_restore_config(
			site_config={
				"mob_clinic_r2_restore_bucket": "bucket-from-site",
				"mob_clinic_r2_restore_endpoint_url": "https://example.r2.cloudflarestorage.com",
				"mob_clinic_r2_restore_access_key_id": "site-key",
				"mob_clinic_r2_restore_secret_access_key": "site-secret",
				"mob_clinic_r2_restore_prefix": "daily/backups",
			},
			cli_values={
				"bucket": "bucket-from-cli",
				"endpoint_url": None,
				"access_key_id": None,
				"secret_access_key": None,
				"prefix": None,
				"source_site_slug": "cue360_localhost",
			},
			environ={
				"MOB_CLINIC_R2_RESTORE_BUCKET": "bucket-from-env",
				"MOB_CLINIC_R2_RESTORE_SECRET_ACCESS_KEY": "env-secret",
			},
		)

		self.assertEqual(config.bucket, "bucket-from-cli")
		self.assertEqual(config.access_key_id, "site-key")
		self.assertEqual(config.secret_access_key, "site-secret")
		self.assertEqual(config.prefix, "daily/backups/")
		self.assertEqual(config.source_site_slug, "cue360_localhost")


if __name__ == "__main__":
	unittest.main()
