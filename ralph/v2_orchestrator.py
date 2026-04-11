"""
v2_orchestrator.py — Multi-agent Ralph v2 orchestrator.

Spawns parallel RalphWorker subprocesses, one per story, up to max_parallel
at a time.  Workers run in isolated temp directories; the orchestrator
collects results, detects file conflicts, and commits per story.
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .v2_worklist import Story, Worklist
from .v2_model_router import ModelRouter
from .v2_cross_service import detect_cross_service, plan_cross_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WorkerResult:
    story_id: str
    success: bool
    files_changed: list[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    model_used: str = ""
    duration_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "story_id": self.story_id,
            "success": self.success,
            "files_changed": self.files_changed,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "model_used": self.model_used,
            "duration_seconds": round(self.duration_seconds, 2),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class RalphWorker:
    """
    Runs in a subprocess and executes one story end-to-end.

    Steps:
    1. Copy relevant service files to an isolated temp directory.
    2. Select model via ModelRouter.
    3. Generate code with Ollama (via ralph.py prompt_builder / file_writer).
    4. Apply the generated patch to the temp dir.
    5. Run pytest against the temp dir.
    6. Return a WorkerResult.

    File conflict detection: if the target file has been modified since the
    worker started (mtime check), the worker raises ConflictError so the
    orchestrator can retry after the conflicting commit lands.
    """

    class ConflictError(RuntimeError):
        pass

    def __init__(
        self,
        story: Story,
        model_router: ModelRouter,
        work_dir: str,
        repo_root: str,
    ) -> None:
        self.story = story
        self.model_router = model_router
        self.work_dir = Path(work_dir)
        self.repo_root = Path(repo_root)
        self._start_time: float = 0.0
        self._mtimes: dict[str, float] = {}

    def execute(self) -> WorkerResult:
        self._start_time = time.monotonic()
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"ralph_worker_{self.story.id}_"))

        try:
            self._copy_service_files(tmp_dir)
            self._snapshot_mtimes()

            model = self.model_router.route(self.story)
            logger.info("[%s] Using model %s", self.story.id, model)

            patch = self._generate_code(model, tmp_dir)
            self._apply_patch(patch, tmp_dir)

            self._check_conflicts()

            passed, failed = self._run_tests(tmp_dir)
            success = failed == 0

            if success:
                changed = self._copy_back(tmp_dir)
                self.model_router.record_result(
                    model, self.story.language,
                    success=True,
                    duration_seconds=time.monotonic() - self._start_time,
                )
            else:
                changed = []
                self.model_router.record_result(model, self.story.language, success=False)

            return WorkerResult(
                story_id=self.story.id,
                success=success,
                files_changed=changed,
                tests_passed=passed,
                tests_failed=failed,
                model_used=model,
                duration_seconds=time.monotonic() - self._start_time,
            )

        except self.ConflictError as exc:
            return WorkerResult(
                story_id=self.story.id,
                success=False,
                duration_seconds=time.monotonic() - self._start_time,
                error=f"CONFLICT: {exc}",
            )
        except Exception as exc:
            logger.exception("[%s] Worker crashed", self.story.id)
            return WorkerResult(
                story_id=self.story.id,
                success=False,
                duration_seconds=time.monotonic() - self._start_time,
                error=str(exc),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _copy_service_files(self, tmp_dir: Path) -> None:
        """Copy only files belonging to story.service into tmp_dir."""
        service_dir = self.repo_root / self.story.service
        if service_dir.exists():
            shutil.copytree(str(service_dir), str(tmp_dir / self.story.service))
        # Also copy shared proto if needed
        proto_dir = self.repo_root / "proto"
        if proto_dir.exists():
            shutil.copytree(str(proto_dir), str(tmp_dir / "proto"))

    def _snapshot_mtimes(self) -> None:
        """Record current mtimes of all files in the repo service directory."""
        service_dir = self.repo_root / self.story.service
        if not service_dir.exists():
            return
        for p in service_dir.rglob("*"):
            if p.is_file():
                self._mtimes[str(p)] = p.stat().st_mtime

    def _check_conflicts(self) -> None:
        """Raise ConflictError if any tracked file has been modified externally."""
        for path_str, mtime in self._mtimes.items():
            p = Path(path_str)
            if p.exists() and p.stat().st_mtime > mtime + 0.1:
                raise self.ConflictError(
                    f"File {path_str} was modified by another worker"
                )

    def _generate_code(self, model: str, tmp_dir: Path) -> dict:
        """
        Call Ollama to generate code for the story.

        Returns a dict of {relative_path: file_content}.
        """
        prompt = self._build_prompt()
        cmd = [
            "ollama", "run", model,
            "--format", "json",
        ]
        logger.info("[%s] Invoking Ollama model %s", self.story.id, model)
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=300,
            )
            raw = result.stdout.strip()
            if not raw:
                raise RuntimeError(f"Ollama returned empty output: {result.stderr}")
            return json.loads(raw)
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Code generation failed: {exc}") from exc

    def _build_prompt(self) -> str:
        return json.dumps({
            "story_id": self.story.id,
            "title": self.story.title,
            "description": self.story.description,
            "service": self.story.service,
            "language": self.story.language,
            "acceptance_criteria": self.story.acceptance_criteria,
            "instruction": (
                "Generate code changes as a JSON object mapping relative file paths "
                "to their complete new content. Return ONLY valid JSON."
            ),
        })

    def _apply_patch(self, patch: dict, tmp_dir: Path) -> None:
        """Write generated files into the temp directory."""
        for rel_path, content in patch.items():
            target = tmp_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            logger.debug("[%s] Wrote %s", self.story.id, rel_path)

    def _run_tests(self, tmp_dir: Path) -> tuple[int, int]:
        """Run pytest in tmp_dir; return (passed, failed)."""
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q", "--json-report",
             "--json-report-file=/dev/stdout", str(tmp_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        try:
            report = json.loads(result.stdout)
            summary = report.get("summary", {})
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0) + summary.get("error", 0)
        except (json.JSONDecodeError, KeyError):
            # Fallback: count lines
            passed = result.stdout.count(" passed")
            failed = result.stdout.count(" failed") + result.stdout.count(" error")
        return passed, failed

    def _copy_back(self, tmp_dir: Path) -> list[str]:
        """Copy generated files from tmp_dir back to the real repo."""
        changed: list[str] = []
        service_dir = self.repo_root / self.story.service
        tmp_service = tmp_dir / self.story.service
        if not tmp_service.exists():
            return changed

        for src in tmp_service.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(tmp_dir)
            dst = self.repo_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            changed.append(str(rel))

        return changed


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class RalphV2Orchestrator:
    """
    Main loop for Ralph v2.

    Reads stories from a worklist, spawns up to *max_parallel* workers,
    collects results, and commits on success.
    """

    def __init__(
        self,
        worklist_path: str,
        max_parallel: int = 3,
        repo_root: Optional[str] = None,
    ) -> None:
        self.worklist = Worklist(worklist_path)
        self.max_parallel = max_parallel
        self.repo_root = Path(repo_root or os.getcwd())
        self.model_router = ModelRouter()

        # Track which files are being touched by active workers (path → story_id)
        self._active_files: dict[str, str] = {}

        # multiprocessing pool results
        self._pending: list[multiprocessing.pool.AsyncResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main orchestration loop."""
        logger.info("Ralph v2 orchestrator starting — repo=%s", self.repo_root)

        with multiprocessing.Pool(processes=self.max_parallel) as pool:
            while True:
                completed_ids = self.worklist.completed_ids()
                progress = self.worklist.get_progress()

                if progress["pending"] == 0 and progress["in_progress"] == 0:
                    logger.info("All stories complete. Progress: %s", progress)
                    break

                # How many slots are free?
                free_slots = self.max_parallel - len(self._pending)
                if free_slots > 0 and progress["pending"] > 0:
                    new_stories = self.pick_next_stories(free_slots)
                    for story in new_stories:
                        logger.info("Spawning worker for story %s", story.id)
                        self.worklist.mark_in_progress(story.id)
                        worker = self.spawn_worker(story)
                        async_result = pool.apply_async(_worker_execute, (worker,))
                        self._pending.append(async_result)

                self.monitor_workers()
                time.sleep(2)

        logger.info("Orchestrator done. %s", self.worklist.get_progress())

    def pick_next_stories(self, count: int) -> list[Story]:
        """
        Select up to *count* stories that have no dependency conflicts with
        currently running stories.
        """
        completed_ids = self.worklist.completed_ids()
        candidates = self.worklist.next_available(completed_ids)
        selected: list[Story] = []

        for story in candidates:
            if len(selected) >= count:
                break
            if not self._conflicts_with_active(story):
                selected.append(story)
                # Reserve this story's service so subsequent picks avoid it
                self._active_files[story.service] = story.id

        return selected

    def spawn_worker(self, story: Story) -> RalphWorker:
        """Create an isolated RalphWorker for *story*."""
        work_dir = tempfile.mkdtemp(prefix=f"ralph_work_{story.id}_")
        return RalphWorker(
            story=story,
            model_router=self.model_router,
            work_dir=work_dir,
            repo_root=str(self.repo_root),
        )

    def monitor_workers(self) -> None:
        """Check pending async results; collect finished ones."""
        still_running: list[multiprocessing.pool.AsyncResult] = []
        completed_results: list[WorkerResult] = []

        for ar in self._pending:
            if ar.ready():
                try:
                    result: WorkerResult = ar.get(timeout=0)
                    completed_results.append(result)
                except Exception as exc:
                    logger.error("Worker raised exception: %s", exc)
                    # Create a failed WorkerResult (story_id unknown here — best effort)
                    completed_results.append(
                        WorkerResult(story_id="unknown", success=False, error=str(exc))
                    )
            else:
                still_running.append(ar)

        self._pending = still_running
        if completed_results:
            self.commit_results(completed_results)

    def commit_results(self, completed: list[WorkerResult]) -> None:
        """
        For each completed worker result:
        - On success: update worklist and git commit the changed files.
        - On failure: mark failed, free the service slot.
        """
        for result in completed:
            # Free the service slot
            story = self._get_story_by_id(result.story_id)
            if story:
                self._active_files.pop(story.service, None)

            if result.success:
                self._git_commit(result)
                self.worklist.mark_complete(result.story_id)
                logger.info(
                    "Story %s committed. files=%s passed=%d failed=%d model=%s duration=%.1fs",
                    result.story_id,
                    result.files_changed,
                    result.tests_passed,
                    result.tests_failed,
                    result.model_used,
                    result.duration_seconds,
                )
            else:
                error = result.error or "tests failed"
                self.worklist.mark_failed(result.story_id, error)
                logger.warning("Story %s failed: %s", result.story_id, error)

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def _conflicts_with_active(self, candidate: Story) -> bool:
        """
        Return True if *candidate* conflicts with any currently-running story.

        Conflict rules:
        1. Same service → conflict.
        2. Shared proto dependency → conflict (both have proto in labels/deps).
        3. *candidate* is in the dep chain of an active story (or vice versa).
        """
        active_stories = [
            self._get_story_by_id(sid)
            for sid in self._active_files.values()
            if self._get_story_by_id(sid)
        ]

        for active in active_stories:
            if active is None:
                continue

            # Rule 1: same service
            if active.service == candidate.service:
                logger.debug(
                    "Conflict: %s and %s share service %s",
                    candidate.id, active.id, active.service,
                )
                return True

            # Rule 2: shared proto dependency
            if (
                "proto" in candidate.labels
                and "proto" in active.labels
            ):
                logger.debug(
                    "Conflict: %s and %s both have proto dependency",
                    candidate.id, active.id,
                )
                return True

            # Rule 3: explicit dep chain
            if candidate.id in active.deps or active.id in candidate.deps:
                logger.debug(
                    "Conflict: %s and %s are in each other's dep chain",
                    candidate.id, active.id,
                )
                return True

        return False

    def _get_story_by_id(self, story_id: str) -> Optional[Story]:
        try:
            return self.worklist.get_story(story_id)
        except KeyError:
            return None

    def _git_commit(self, result: WorkerResult) -> None:
        """Stage changed files and create a commit."""
        if not result.files_changed:
            return
        try:
            subprocess.run(
                ["git", "add"] + result.files_changed,
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
            )
            msg = (
                f"[ralph-v2] {result.story_id} — "
                f"model={result.model_used} "
                f"passed={result.tests_passed} "
                f"duration={result.duration_seconds:.1f}s"
            )
            subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.error("Git commit failed for %s: %s", result.story_id, exc)


# ---------------------------------------------------------------------------
# Subprocess entry point (must be module-level for multiprocessing)
# ---------------------------------------------------------------------------

def _worker_execute(worker: RalphWorker) -> WorkerResult:
    """Top-level function called in worker subprocess."""
    return worker.execute()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="Ralph v2 multi-agent orchestrator")
    parser.add_argument("worklist", help="Path to worklist.json")
    parser.add_argument("--parallel", type=int, default=3, help="Max parallel workers")
    parser.add_argument("--repo", default=".", help="Repo root directory")
    args = parser.parse_args()

    orchestrator = RalphV2Orchestrator(
        worklist_path=args.worklist,
        max_parallel=args.parallel,
        repo_root=args.repo,
    )
    orchestrator.run()
