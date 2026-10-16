# ABOUTME: Retry and wait utilities for async Kubernetes operations.
# ABOUTME: All wait functions print progress to stderr so rehearsals stay observable.

from __future__ import annotations

import sys
import time
from collections.abc import Callable


def wait_for_condition[T](
    description: str,
    check_fn: Callable[[], T],
    timeout: int = 120,
    interval: int = 5,
) -> T:
    """Poll a check function until it returns a truthy value or timeout.

    Args:
        description: Human-readable description of what we are waiting for.
        check_fn: Callable that returns a truthy value on success, falsy on retry.
        timeout: Maximum seconds to wait.
        interval: Seconds between retries.

    Returns:
        The truthy return value from check_fn.

    Raises:
        TimeoutError: If the condition is not met within the timeout.
    """
    start = time.time()
    elapsed = 0.0
    attempt = 0

    while elapsed < timeout:
        attempt += 1
        print(
            f"[wait] {description}... {elapsed:.0f}s/{timeout}s (attempt {attempt})",
            file=sys.stderr,
        )
        try:
            result = check_fn()
            if result:
                print(
                    f"[wait] {description}... done in {elapsed:.0f}s",
                    file=sys.stderr,
                )
                return result
        except Exception as exc:  # noqa: BLE001 — we re-raise via TimeoutError
            print(
                f"[wait] {description}... error: {exc} ({elapsed:.0f}s/{timeout}s)",
                file=sys.stderr,
            )

        time.sleep(interval)
        elapsed = time.time() - start

    raise TimeoutError(f"Timed out after {timeout}s waiting for: {description}")


def wait_for_pod_ready(
    k8s_core_v1,
    name: str,
    namespace: str,
    timeout: int = 120,
) -> bool:
    """Wait for a specific pod to reach Ready condition."""

    def _check() -> bool:
        pods = k8s_core_v1.list_namespaced_pod(
            namespace=namespace,
            field_selector=f"metadata.name={name}",
        )
        for pod in pods.items:
            if pod.status and pod.status.conditions:
                for condition in pod.status.conditions:
                    if condition.type == "Ready" and condition.status == "True":
                        return True
        return False

    return wait_for_condition(
        description=f"pod {name} ready in {namespace}",
        check_fn=_check,
        timeout=timeout,
    )


def wait_for_pods_by_label(
    k8s_core_v1,
    label_selector: str,
    namespace: str,
    min_ready: int = 1,
    timeout: int = 120,
) -> bool:
    """Wait for pods matching a label selector to reach Running phase."""

    def _check() -> bool:
        pods = k8s_core_v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
        )
        running = sum(
            1
            for pod in pods.items
            if pod.status and pod.status.phase == "Running"
        )
        print(
            f"[wait]   {running}/{min_ready} pods running for {label_selector}",
            file=sys.stderr,
        )
        return running >= min_ready

    return wait_for_condition(
        description=f"{min_ready}+ pods with {label_selector} in {namespace}",
        check_fn=_check,
        timeout=timeout,
    )
