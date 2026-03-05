"""Registry trust policy — allow/deny list enforcement for base image registries."""

from __future__ import annotations

from dataclasses import dataclass, field

from stacksmith.domain.errors import RegistryPolicyError


@dataclass
class RegistryPolicy:
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)


def _extract_registry(image: str) -> str:
    """Extract the registry hostname (with optional port) from an image reference.

    Examples::

        nvcr.io/nvidia/pytorch:23.10 -> nvcr.io
        ghcr.io/org/image:latest      -> ghcr.io
        localhost:5000/myimg:v1        -> localhost:5000
        ubuntu:22.04                   -> docker.io
        library/python:3.10            -> docker.io
    """
    # Split tag from name; handle the case where the first component has a port
    # e.g. "localhost:5000/myimg:v1" -- the first colon belongs to the port, the
    # second to the tag.  We split on "/" first, then handle the tag.
    parts = image.split("/")
    first = parts[0]

    if len(parts) == 1:
        # bare name like "ubuntu:22.04" — always docker.io
        return "docker.io"

    # A registry component contains a "." or a ":" (port) to distinguish from
    # a docker.io username/org path.
    if "." in first or ":" in first:
        return first

    return "docker.io"


def _matches_pattern(registry: str, image: str, pattern: str) -> bool:
    """Check if *registry* or *image* matches a policy pattern.

    Matching rules:
    - Exact registry match (e.g. pattern ``nvcr.io`` matches registry ``nvcr.io``)
    - Image path prefix match with ``/`` boundary
      (e.g. pattern ``docker.io/library/randomuser`` matches image
      ``docker.io/library/randomuser/bad:latest`` but NOT
      ``docker.io/library/randomusername/img:latest``)
    """
    if registry == pattern:
        return True
    # Strip digest (@sha256:...) and tag (:tag) to get the bare image name
    image_name = image.split("@")[0] if "@" in image else image
    last_colon = image_name.rfind(":")
    last_slash = image_name.rfind("/")
    if last_colon > last_slash:
        image_name = image_name[:last_colon]
    if image_name == pattern or image_name.startswith(pattern + "/"):
        return True
    return False


def check_registry(image: str, policy: RegistryPolicy) -> tuple[bool, str]:
    """Check *image* against *policy*.

    Returns ``(allowed, reason)`` where *allowed* is ``False`` if the image
    is denied.
    """
    if not policy.allow and not policy.deny:
        return True, ""

    registry = _extract_registry(image)

    for pattern in policy.deny:
        if _matches_pattern(registry, image, pattern):
            return False, f"Registry '{registry}' is denied by policy"

    if policy.allow:
        for pattern in policy.allow:
            if _matches_pattern(registry, image, pattern):
                return True, ""
        return False, f"Registry '{registry}' is not in the allow list"

    return True, ""


def assert_registry_allowed(image: str, policy: RegistryPolicy) -> None:
    """Raise RegistryPolicyError when *image* violates *policy*."""
    ok, reason = check_registry(image, policy)
    if not ok:
        raise RegistryPolicyError(f"{reason}: {image}")
