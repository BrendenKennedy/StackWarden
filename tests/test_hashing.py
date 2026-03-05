"""Tests for deterministic fingerprinting and tag generation."""

from stacksmith.domain.hashing import canonicalize, fingerprint, generate_tag
from stacksmith.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    PipDep,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)


def _profile(**kw) -> Profile:
    defaults = dict(
        id="test_profile",
        display_name="Test",
        arch="arm64",
        cuda=CudaSpec(major=12, minor=5, variant="cuda12.5"),
        gpu=GpuSpec(vendor="nvidia", family="test"),
        base_candidates=[BaseCandidate(name="pytorch", tags=["latest"])],
    )
    defaults.update(kw)
    return Profile.model_validate(defaults)


def _stack(**kw) -> StackSpec:
    defaults = dict(
        id="test_stack",
        display_name="Test",
        task="diffusion",
        serve="python_api",
        api="fastapi",
        build_strategy="overlay",
        components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="fastapi", version="==0.115.*")],
            apt=["git", "curl"],
        ),
        env=["PYTHONUNBUFFERED=1"],
        ports=[8000],
        entrypoint=StackEntrypoint(cmd=["python", "main.py"]),
    )
    defaults.update(kw)
    return StackSpec.model_validate(defaults)


class TestFingerprint:
    def test_same_inputs_same_hash(self):
        p, s = _profile(), _stack()
        fp1 = fingerprint(p, s, "base:latest")
        fp2 = fingerprint(p, s, "base:latest")
        assert fp1 == fp2

    def test_different_base_different_hash(self):
        p, s = _profile(), _stack()
        fp1 = fingerprint(p, s, "base:v1")
        fp2 = fingerprint(p, s, "base:v2")
        assert fp1 != fp2

    def test_different_digest_different_hash(self):
        p, s = _profile(), _stack()
        fp1 = fingerprint(p, s, "base:latest", base_digest="sha256:aaa")
        fp2 = fingerprint(p, s, "base:latest", base_digest="sha256:bbb")
        assert fp1 != fp2

    def test_template_hash_affects_fingerprint(self):
        p, s = _profile(), _stack()
        fp1 = fingerprint(p, s, "base:latest", template_hash="v1")
        fp2 = fingerprint(p, s, "base:latest", template_hash="v2")
        assert fp1 != fp2

    def test_wheelhouse_settings_affect_fingerprint(self):
        p = _profile()
        s1 = _stack(components=StackComponents(base_role="pytorch", pip_install_mode="index"))
        s2 = _stack(
            components=StackComponents(
                base_role="pytorch",
                pip_install_mode="wheelhouse_only",
                pip_wheelhouse_path="wheels",
            )
        )
        fp1 = fingerprint(p, s1, "base:latest")
        fp2 = fingerprint(p, s2, "base:latest")
        assert fp1 != fp2

    def test_tuple_policy_override_affects_fingerprint(self):
        p = _profile()
        s1 = _stack(policy_overrides={})
        s2 = _stack(policy_overrides={"tuple_id": "arm_nvidia_cuda124_ubuntu2204"})
        fp1 = fingerprint(p, s1, "base:latest")
        fp2 = fingerprint(p, s2, "base:latest")
        assert fp1 != fp2

    def test_npm_and_apt_modes_affect_fingerprint(self):
        p = _profile()
        s1 = _stack(
            components=StackComponents(
                base_role="pytorch",
                npm_install_mode="spec",
                apt_install_mode="repo",
            )
        )
        s2 = _stack(
            components=StackComponents(
                base_role="pytorch",
                npm_install_mode="lock_only",
                apt_install_mode="pin_only",
                apt=["curl"],
                apt_constraints={"curl": "=8.5.0-1ubuntu1"},
            ),
            files={"copy": [{"src": "apps/web/package-lock.json", "dst": "/app/package-lock.json"}]},
        )
        fp1 = fingerprint(p, s1, "base:latest")
        fp2 = fingerprint(p, s2, "base:latest")
        assert fp1 != fp2


class TestCanonicalization:
    def test_sorted_pip_order_independent(self):
        """pip deps in different order must produce same canonical form."""
        p = _profile()
        s1 = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="b", version="1"), PipDep(name="a", version="2")],
        ))
        s2 = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="a", version="2"), PipDep(name="b", version="1")],
        ))
        assert canonicalize(p, s1, "base") == canonicalize(p, s2, "base")

    def test_sorted_apt_order_independent(self):
        p = _profile()
        s1 = _stack(components=StackComponents(base_role="pytorch", apt=["curl", "git"]))
        s2 = _stack(components=StackComponents(base_role="pytorch", apt=["git", "curl"]))
        assert canonicalize(p, s1, "base") == canonicalize(p, s2, "base")

    def test_sorted_env_order_independent(self):
        p = _profile()
        s1 = _stack(env=["B=1", "A=2"])
        s2 = _stack(env=["A=2", "B=1"])
        assert canonicalize(p, s1, "base") == canonicalize(p, s2, "base")

    def test_sorted_ports_order_independent(self):
        p = _profile()
        s1 = _stack(ports=[8080, 8000])
        s2 = _stack(ports=[8000, 8080])
        assert canonicalize(p, s1, "base") == canonicalize(p, s2, "base")

    def test_whitespace_in_version_normalized(self):
        p = _profile()
        s1 = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="pkg", version=">= 1.0")],
        ))
        s2 = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="pkg", version=">=1.0")],
        ))
        assert canonicalize(p, s1, "base") == canonicalize(p, s2, "base")

    def test_apt_constraints_order_independent(self):
        p = _profile()
        s1 = _stack(components=StackComponents(
            base_role="pytorch",
            apt=["curl", "git"],
            apt_constraints={"git": "=1:2.34.1-1ubuntu1.11", "curl": "=8.5.0-1ubuntu1"},
        ))
        s2 = _stack(components=StackComponents(
            base_role="pytorch",
            apt=["git", "curl"],
            apt_constraints={"curl": "=8.5.0-1ubuntu1", "git": "=1:2.34.1-1ubuntu1.11"},
        ))
        assert canonicalize(p, s1, "base") == canonicalize(p, s2, "base")


class TestTagGeneration:
    def test_tag_format(self):
        p, s = _profile(), _stack()
        fp = fingerprint(p, s, "base:latest")
        tag = generate_tag(s, p, fp)
        assert tag.startswith("local/stacksmith:")
        parts = tag.split(":")[1].split("-")
        assert parts[0] == "test_stack"
        assert parts[1] == "test_profile"
        assert parts[2] == "cuda12.5"
        assert parts[3] == "python_api"
        assert parts[4] == "fastapi"
        assert len(parts[5]) == 12  # h12

    def test_tag_deterministic(self):
        p, s = _profile(), _stack()
        fp = fingerprint(p, s, "base:latest")
        tag1 = generate_tag(s, p, fp)
        tag2 = generate_tag(s, p, fp)
        assert tag1 == tag2
