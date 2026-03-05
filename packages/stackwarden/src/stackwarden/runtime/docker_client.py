"""Docker SDK wrapper — SDK only, no build operations.

All image inspect/list/pull/tag operations go through this client.
Build operations use the buildx CLI wrapper instead.
"""

from __future__ import annotations

import logging
from typing import Any

import docker
from docker.errors import APIError, ImageNotFound, DockerException

log = logging.getLogger(__name__)


def _split_image_ref(ref: str) -> tuple[str, str]:
    """Split a Docker image reference into (repository, tag).

    Handles registries with ports (e.g. ``myregistry:5000/image:tag``).
    """
    at_idx = ref.find("@")
    if at_idx != -1:
        return ref[:at_idx], ref[at_idx:]

    last_colon = ref.rfind(":")
    last_slash = ref.rfind("/")
    if last_colon > last_slash:
        return ref[:last_colon], ref[last_colon + 1:]
    return ref, "latest"


class DockerClient:
    """Thin abstraction over the Docker SDK for read/pull/tag operations."""

    def __init__(self) -> None:
        try:
            self._client = docker.from_env()
            self._client.ping()
        except DockerException as exc:
            raise RuntimeError(
                "Cannot connect to Docker daemon. Is Docker running?\n"
                f"  Detail: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def image_exists(self, tag: str) -> bool:
        try:
            self._client.images.get(tag)
            return True
        except ImageNotFound:
            return False

    def inspect_image(self, tag: str) -> dict[str, Any]:
        img = self._client.images.get(tag)
        return img.attrs

    def get_image_digest(self, tag: str) -> str | None:
        """Return the first RepoDigest for *tag*, or ``None``."""
        try:
            img = self._client.images.get(tag)
            digests = img.attrs.get("RepoDigests", [])
            return digests[0] if digests else None
        except ImageNotFound:
            return None

    def get_image_labels(self, tag: str) -> dict[str, str]:
        try:
            img = self._client.images.get(tag)
            config = img.attrs.get("Config", {})
            return config.get("Labels", {}) or {}
        except ImageNotFound:
            return {}

    def get_image_id(self, tag: str) -> str | None:
        try:
            img = self._client.images.get(tag)
            return img.id
        except ImageNotFound:
            return None

    def list_images(self, name_filter: str | None = None) -> list[dict[str, Any]]:
        filters = {}
        if name_filter:
            filters["reference"] = name_filter
        images = self._client.images.list(filters=filters)
        return [img.attrs for img in images]

    # ------------------------------------------------------------------
    # Mutating (non-build)
    # ------------------------------------------------------------------

    def pull_image(self, repository: str, tag: str = "latest", *, timeout: int = 1800) -> str:
        """Pull an image and return its id.

        *timeout* is in seconds (default 30 minutes).
        """
        log.info("Pulling %s:%s ...", repository, tag)
        try:
            old_timeout = self._client.api.timeout
            self._client.api.timeout = timeout
            try:
                img = self._client.images.pull(repository, tag=tag)
            finally:
                self._client.api.timeout = old_timeout
            log.info("Pulled %s (id=%s)", repository, img.short_id)
            return img.id
        except APIError as exc:
            raise RuntimeError(f"Failed to pull {repository}:{tag}: {exc}") from exc

    def remove_image(self, tag: str, force: bool = False) -> None:
        """Remove an image by tag."""
        try:
            self._client.images.remove(tag, force=force)
            log.info("Removed image %s", tag)
        except ImageNotFound:
            log.debug("Image %s not found for removal", tag)
        except APIError as exc:
            log.warning("Failed to remove %s: %s", tag, exc)

    def tag_image(self, source: str, target: str) -> None:
        """Tag *source* image as *target* (repository:tag format)."""
        try:
            img = self._client.images.get(source)
            repo, tag_part = _split_image_ref(target)
            img.tag(repo, tag=tag_part)
            log.info("Tagged %s -> %s", source, target)
        except (ImageNotFound, APIError) as exc:
            raise RuntimeError(f"Failed to tag {source} as {target}: {exc}") from exc

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def info(self) -> dict[str, Any]:
        return self._client.info()

    def server_arch(self) -> str:
        """Return the architecture reported by the Docker daemon."""
        return self._client.info().get("Architecture", "unknown")
