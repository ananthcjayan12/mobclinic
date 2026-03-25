from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DATABASE_FILE_RE = re.compile(
	r"^(?P<stamp>\d{8}_\d{6})-(?P<site_slug>.+?)(?P<partial>-partial)?-database(?P<encrypted>-enc)?\.sql\.gz$"
)


CONFIG_KEYS = {
	"bucket": "mob_clinic_r2_restore_bucket",
	"endpoint_url": "mob_clinic_r2_restore_endpoint_url",
	"access_key_id": "mob_clinic_r2_restore_access_key_id",
	"secret_access_key": "mob_clinic_r2_restore_secret_access_key",
	"prefix": "mob_clinic_r2_restore_prefix",
	"source_site_slug": "mob_clinic_r2_restore_source_site_slug",
}


ENV_KEYS = {
	"bucket": "MOB_CLINIC_R2_RESTORE_BUCKET",
	"endpoint_url": "MOB_CLINIC_R2_RESTORE_ENDPOINT_URL",
	"access_key_id": "MOB_CLINIC_R2_RESTORE_ACCESS_KEY_ID",
	"secret_access_key": "MOB_CLINIC_R2_RESTORE_SECRET_ACCESS_KEY",
	"prefix": "MOB_CLINIC_R2_RESTORE_PREFIX",
	"source_site_slug": "MOB_CLINIC_R2_RESTORE_SOURCE_SITE_SLUG",
}


@dataclass(frozen=True)
class BackupObject:
	key: str
	last_modified: datetime | None = None

	@property
	def filename(self) -> str:
		return Path(self.key).name


@dataclass(frozen=True)
class BackupBundle:
	stamp: str
	site_slug: str
	folder: str
	database_key: str
	site_config_key: str | None
	public_files_key: str | None
	private_files_key: str | None
	encrypted: bool


@dataclass(frozen=True)
class RestoreConfig:
	bucket: str
	endpoint_url: str
	access_key_id: str
	secret_access_key: str
	prefix: str = ""
	source_site_slug: str | None = None


def get_bench_root() -> Path:
	return Path(__file__).resolve().parents[3]


def get_site_config_path(site: str) -> Path:
	return get_bench_root() / "sites" / site / "site_config.json"


def load_site_config(site: str) -> dict[str, Any]:
	site_config_path = get_site_config_path(site)
	if not site_config_path.exists():
		raise FileNotFoundError(f"Site config not found for {site}: {site_config_path}")

	with site_config_path.open() as f:
		return json.load(f)


def normalise_prefix(prefix: str | None) -> str:
	if not prefix:
		return ""

	prefix = prefix.strip().strip("/")
	return f"{prefix}/" if prefix else ""


def resolve_restore_config(
	*,
	site_config: dict[str, Any],
	cli_values: dict[str, str | None],
	environ: dict[str, str] | None = None,
) -> RestoreConfig:
	environ = environ or os.environ
	resolved: dict[str, str] = {}

	for key, config_key in CONFIG_KEYS.items():
		value = cli_values.get(key) or site_config.get(config_key) or environ.get(ENV_KEYS[key])
		if isinstance(value, str):
			value = value.strip()
		if value:
			resolved[key] = value

	missing = [key for key in ("bucket", "endpoint_url", "access_key_id", "secret_access_key") if key not in resolved]
	if missing:
		missing_text = ", ".join(CONFIG_KEYS[key] for key in missing)
		raise ValueError(f"Missing restore configuration: {missing_text}")

	return RestoreConfig(
		bucket=resolved["bucket"],
		endpoint_url=resolved["endpoint_url"],
		access_key_id=resolved["access_key_id"],
		secret_access_key=resolved["secret_access_key"],
		prefix=normalise_prefix(resolved.get("prefix", "")),
		source_site_slug=resolved.get("source_site_slug") or None,
	)


def select_latest_backup_bundle(
	objects: list[BackupObject],
	source_site_slug: str | None = None,
) -> BackupBundle:
	candidates: list[tuple[float, re.Match[str], BackupObject]] = []

	for obj in objects:
		match = DATABASE_FILE_RE.match(obj.filename)
		if not match or match.group("partial"):
			continue
		if source_site_slug and match.group("site_slug") != source_site_slug:
			continue

		stamp = datetime.strptime(match.group("stamp"), "%Y%m%d_%H%M%S")
		sort_value = obj.last_modified.timestamp() if obj.last_modified else stamp.timestamp()
		candidates.append((sort_value, match, obj))

	if not candidates:
		filter_text = f" for site slug {source_site_slug}" if source_site_slug else ""
		raise ValueError(f"No database backup found{filter_text}.")

	candidates.sort(key=lambda row: (row[0], row[1].group("stamp"), row[2].key), reverse=True)
	_, match, database_object = candidates[0]

	stamp = match.group("stamp")
	site_slug = match.group("site_slug")
	bundle_prefix = f"{stamp}-{site_slug}"
	folder = database_object.key.rsplit("/", 1)[0] if "/" in database_object.key else ""

	def matching_key(kind: str) -> str | None:
		for obj in objects:
			if folder and not obj.key.startswith(f"{folder}/"):
				continue
			name = obj.filename
			if kind == "site_config" and (
				name == f"{bundle_prefix}-site_config_backup.json"
				or name == f"{bundle_prefix}-site_config_backup-enc.json"
			):
				return obj.key
			if kind == "public" and (
				name == f"{bundle_prefix}-files.tar"
				or name == f"{bundle_prefix}-files.tgz"
				or name == f"{bundle_prefix}-files-enc.tar"
				or name == f"{bundle_prefix}-files-enc.tgz"
			):
				return obj.key
			if kind == "private" and (
				name == f"{bundle_prefix}-private-files.tar"
				or name == f"{bundle_prefix}-private-files.tgz"
				or name == f"{bundle_prefix}-private-files-enc.tar"
				or name == f"{bundle_prefix}-private-files-enc.tgz"
			):
				return obj.key
		return None

	return BackupBundle(
		stamp=stamp,
		site_slug=site_slug,
		folder=folder,
		database_key=database_object.key,
		site_config_key=matching_key("site_config"),
		public_files_key=matching_key("public"),
		private_files_key=matching_key("private"),
		encrypted=bool(match.group("encrypted")),
	)


def ensure_empty_download_dir(path: Path) -> None:
	if path.exists():
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


def parse_site_config_backup(path: Path) -> dict[str, Any]:
	with path.open() as f:
		return json.load(f)
