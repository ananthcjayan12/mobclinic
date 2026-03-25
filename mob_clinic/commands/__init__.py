from __future__ import annotations

import shutil
from pathlib import Path

import click

import frappe
from botocore.config import Config
from botocore.exceptions import ClientError
from frappe.commands import get_site, pass_context

from mob_clinic.r2_restore import (
	BackupObject,
	ensure_empty_download_dir,
	get_bench_root,
	get_site_config_path,
	load_site_config,
	parse_site_config_backup,
	resolve_restore_config,
	select_latest_backup_bundle,
)


@click.command(
	"restore-from-r2",
	help="Download the latest backup set from Cloudflare R2 / S3 and restore it into the selected site.",
)
@click.option("--bucket", help="R2 bucket name")
@click.option("--endpoint-url", help="R2 endpoint URL, for example https://<ACCOUNT_ID>.r2.cloudflarestorage.com")
@click.option("--access-key-id", help="R2 access key ID")
@click.option("--secret-access-key", help="R2 secret access key")
@click.option("--prefix", help="Optional object prefix inside the bucket")
@click.option("--source-site-slug", help="Optional backup site slug filter, for example cue360_localhost")
@click.option("--download-dir", help="Optional directory for downloaded backup files")
@click.option("--db-root-username", help="MariaDB/Postgres root username, if restore needs it")
@click.option("--db-root-password", help="MariaDB/Postgres root password, if restore needs it")
@click.option("--keep-downloads", is_flag=True, default=False, help="Keep downloaded backup files after success")
@click.option("--dry-run", is_flag=True, default=False, help="Show the chosen backup bundle without restoring")
@click.option("--yes", is_flag=True, default=False, help="Skip the overwrite confirmation")
@click.option("--force", is_flag=True, default=False, help="Pass force through to Frappe restore")
@pass_context
def restore_from_r2(
	context,
	bucket=None,
	endpoint_url=None,
	access_key_id=None,
	secret_access_key=None,
	prefix=None,
	source_site_slug=None,
	download_dir=None,
	db_root_username=None,
	db_root_password=None,
	keep_downloads=False,
	dry_run=False,
	yes=False,
	force=False,
):
	from boto3 import client as boto3_client
	from frappe.commands.site import _restore
	from frappe.installer import update_site_config

	target_site = get_site(context)
	if not target_site:
		raise frappe.SiteNotSpecifiedError

	site_config = load_site_config(target_site)
	restore_config = resolve_restore_config(
		site_config=site_config,
		cli_values={
			"bucket": bucket,
			"endpoint_url": endpoint_url,
			"access_key_id": access_key_id,
			"secret_access_key": secret_access_key,
			"prefix": prefix,
			"source_site_slug": source_site_slug,
		},
	)

	s3_client = boto3_client(
		"s3",
		aws_access_key_id=restore_config.access_key_id,
		aws_secret_access_key=restore_config.secret_access_key,
		endpoint_url=restore_config.endpoint_url,
		region_name="auto",
		config=Config(signature_version="s3v4"),
	)

	objects: list[BackupObject] = []
	continuation_token = None
	while True:
		params = {"Bucket": restore_config.bucket, "Prefix": restore_config.prefix}
		if continuation_token:
			params["ContinuationToken"] = continuation_token
		try:
			response = s3_client.list_objects_v2(**params)
		except ClientError as exc:
			error_code = exc.response.get("Error", {}).get("Code")
			message = exc.response.get("Error", {}).get("Message") or str(exc)
			if error_code == "SignatureDoesNotMatch":
				raise click.ClickException(
					"R2 rejected the request signature. Re-check the endpoint URL and credentials. "
					"For Cloudflare R2 the endpoint should look like "
					"https://<ACCOUNT_ID>.r2.cloudflarestorage.com, or the EU/FedRAMP variant if the bucket "
					"uses a jurisdiction-specific endpoint."
				) from exc
			raise click.ClickException(f"Failed to list backups from R2: {message}") from exc
		for entry in response.get("Contents", []):
			objects.append(BackupObject(key=entry["Key"], last_modified=entry.get("LastModified")))
		if not response.get("IsTruncated"):
			break
		continuation_token = response.get("NextContinuationToken")

	bundle = select_latest_backup_bundle(objects, source_site_slug=restore_config.source_site_slug)

	click.echo(f"Target site: {target_site}")
	click.echo(f"Selected backup: {bundle.database_key}")
	if bundle.public_files_key:
		click.echo(f"Public files: {bundle.public_files_key}")
	if bundle.private_files_key:
		click.echo(f"Private files: {bundle.private_files_key}")
	if bundle.site_config_key:
		click.echo(f"Site config: {bundle.site_config_key}")

	if dry_run:
		return

	if not yes:
		click.confirm(
			f"This will overwrite the site {target_site} using backup {bundle.database_key}. Continue?",
			abort=True,
		)

	download_root = Path(download_dir) if download_dir else (
		get_bench_root() / "sites" / ".mob_clinic_restore" / target_site / bundle.stamp
	)
	ensure_empty_download_dir(download_root)

	def download(key: str | None) -> Path | None:
		if not key:
			return None
		destination = download_root / Path(key).name
		click.echo(f"Downloading {key} -> {destination}")
		s3_client.download_file(restore_config.bucket, key, str(destination))
		return destination

	downloaded_db = download(bundle.database_key)
	downloaded_site_config = download(bundle.site_config_key)
	downloaded_public = download(bundle.public_files_key)
	downloaded_private = download(bundle.private_files_key)

	if not downloaded_db:
		raise click.ClickException("Database backup download failed.")

	production_site_config: dict[str, object] = {}
	if downloaded_site_config:
		production_site_config = parse_site_config_backup(downloaded_site_config)

	backup_encryption_key = production_site_config.get("backup_encryption_key")
	if bundle.encrypted and not backup_encryption_key:
		raise click.ClickException(
			"Backup files are encrypted but backup_encryption_key was not found in the downloaded site config backup."
		)

	click.echo("Restoring backup into staging site...")
	try:
		frappe.init(site=target_site)
		_restore(
			site=target_site,
			sql_file_path=str(downloaded_db),
			encryption_key=backup_encryption_key,
			db_root_username=db_root_username,
			db_root_password=db_root_password,
			verbose=context.verbose,
			install_app=(),
			admin_password=None,
			force=force,
			with_public_files=str(downloaded_public) if downloaded_public else None,
			with_private_files=str(downloaded_private) if downloaded_private else None,
		)
	finally:
		frappe.destroy()

	target_site_config_path = get_site_config_path(target_site)
	try:
		frappe.init(site=target_site)
		for key in ("encryption_key", "backup_encryption_key"):
			value = production_site_config.get(key)
			if value:
				update_site_config(key, value, site_config_path=str(target_site_config_path))
				click.echo(f"Updated {key} on {target_site}")
	finally:
		frappe.destroy()

	try:
		from frappe.utils import scheduler as scheduler_utils

		frappe.init(site=target_site)
		frappe.connect()
		scheduler_utils.disable_scheduler()
		frappe.db.commit()
		click.echo(f"Scheduler disabled for {target_site}")
	finally:
		frappe.destroy()

	if keep_downloads:
		click.echo(f"Downloaded files kept at {download_root}")
	else:
		shutil.rmtree(download_root, ignore_errors=True)
		click.echo("Temporary downloaded files removed")

	click.echo(
		"Staging refresh complete. Review outbound email, webhooks, and payment integrations before using the site."
	)


commands = [restore_from_r2]
