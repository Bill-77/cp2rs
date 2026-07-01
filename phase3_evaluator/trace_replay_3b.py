import json
import hashlib
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path

from phase3_evaluator.prompts import (
    PROMPT_3B_ADAPTER_SYNTHESIS,
    PROMPT_3B_ADAPTER_CASE_GENERATION,
    PROMPT_3B_REPLAY_REPAIR,
)
from phase3_evaluator.function_uid import iter_function_records, strip_overload_suffix


class TraceReplay3B:
    """
    Phase 3B public-first trace replay evaluator.

    The default layer is public behavior. Function-boundary replay is kept as a
    diagnostic surface and is not executed unless explicitly requested.
    """

    TEST_SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
    SKIP_DIRS = {
        ".git", ".github", "target", "build", "out", "cmake-build-debug",
        "third_party", "vendor", "deps", "node_modules", "unity", "googletest",
        "gtest"
    }
    ADAPTER_DIR = Path(__file__).resolve().parent / "adapters"
    GENERATED_ADAPTER_CACHE_DIR = Path("output") / "phase3_3b" / "adapters"

    def __init__(
        self,
        src_name,
        tgt_name,
        src_repo_path,
        tgt_repo_path,
        alignment_report_path,
        src_db_path,
        tgt_db_path,
        adapter_path=None,
        adapter_mode="existing",
        synthesis_attempts=3,
        replay_repair_attempts=3,
        completion_iterations=0,
        completion_batch_size=10,
        agent_iterations=None,
        agent_batch_size=None,
        keep_debug_artifacts=False,
        llm_client=None,
        work_root=None,
    ):
        self.src_name = src_name
        self.tgt_name = tgt_name
        self.src_repo_path = Path(src_repo_path) if src_repo_path else None
        self.tgt_repo_path = Path(tgt_repo_path) if tgt_repo_path else None
        self.alignment_report_path = Path(alignment_report_path)
        self.src_db_path = Path(src_db_path)
        self.tgt_db_path = Path(tgt_db_path)
        self.adapter_path = Path(adapter_path) if adapter_path else None
        self.adapter_mode = adapter_mode
        self.synthesis_attempts = max(1, int(synthesis_attempts or 1))
        self.replay_repair_attempts = max(0, int(replay_repair_attempts or 0))
        if agent_iterations is not None:
            completion_iterations = agent_iterations
        if agent_batch_size is not None:
            completion_batch_size = agent_batch_size
        self.completion_iterations = max(-1, int(completion_iterations if completion_iterations is not None else 0))
        self.completion_batch_size = max(1, int(completion_batch_size or 1))
        self.initial_synthesis_batch_size = min(self.completion_batch_size, 10)
        self.keep_debug_artifacts = bool(keep_debug_artifacts)
        self.llm_client = llm_client
        self.work_root = Path(work_root) if work_root else None
        self._last_synthesis_context = None
        self._last_synthesis_prompt = None
        self._initial_prompt_case_ids = []
        self._public_replay_eligibility = None
        self._synthesis_attempts_used = 0
        self._case_conversion_attempts = {}
        self._adapter_generation_unresolved_case_ids = []
        self._replay_infrastructure_unresolved_case_ids = []
        self._run_started_at = None
        self._active_artifacts_path = None
        self._llm_usage = {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 0,
            "elapsed_seconds": 0.0,
            "usage_source": "api_reported_when_available",
            "calls_by_stage": {},
            "call_records": [],
        }
        self._last_completion_budget = {
            "mode": "disabled" if self.completion_iterations < 0 else ("auto" if self.completion_iterations == 0 else "fixed"),
        }

    def run(self, mode="run", layer="public", artifacts_dir=None):
        self._run_started_at = time.monotonic()
        self._progress("START", f"mode={mode}, layer={layer}, adapter_mode={self.adapter_mode}")
        if mode not in {"inventory", "record", "replay", "run"}:
            raise ValueError(f"Unsupported 3B mode: {mode}")
        if layer not in {"public", "function", "both"}:
            raise ValueError(f"Unsupported 3B layer: {layer}")
        if self.adapter_mode not in {"existing", "auto", "synthesize", "prompt-only"}:
            raise ValueError(f"Unsupported 3B adapter mode: {self.adapter_mode}")

        self._progress("INPUT", "检查 3A、parsed DB 和仓库路径")
        self._check_required_paths(mode)
        alignment = self._load_alignment()
        src_index = self._index_functions(self.src_db_path, repo_path=self.src_repo_path)
        tgt_index = self._index_functions(self.tgt_db_path, repo_path=self.tgt_repo_path)
        alignment_stats = self._summarize_alignment(alignment, src_index, tgt_index)
        self._progress(
            "ALIGN",
            f"aligned source={len(alignment_stats.get('unique_aligned_source_functions', []))}, "
            f"public eligible source={len(alignment_stats.get('public_eligible_source_functions', []))}",
        )
        artifacts_path = Path(artifacts_dir) if artifacts_dir else None
        self._active_artifacts_path = artifacts_path
        self._progress("INVENTORY", "开始发现和解析 src 测试")
        inventory = self.discover_tests(alignment_stats)
        inventory_summary = inventory.get("summary", {})
        self._progress(
            "INVENTORY",
            f"完成: files={inventory_summary.get('test_files', 0)}, "
            f"cases={inventory_summary.get('test_cases', 0)}, "
            f"aligned_cases={inventory_summary.get('aligned_test_cases', 0)}",
        )
        self._progress("ELIGIBILITY", "开始 public replay eligibility 筛选")
        self._public_replay_eligibility = self._build_public_replay_eligibility(
            alignment_stats,
            inventory,
        )
        eligibility_summary = self._public_replay_eligibility.get("summary", {})
        self._progress(
            "ELIGIBILITY",
            f"完成: public_eligible={eligibility_summary.get('public_replay_eligible_cases', 0)}, "
            f"unresolved_binding={eligibility_summary.get('cases_unresolved_after_exact_function_binding', 0)}, "
            f"structurally_ineligible={eligibility_summary.get('structurally_ineligible_for_public_replay_cases', 0)}",
        )
        if mode == "inventory":
            self._prime_adapter_context(alignment_stats, inventory, artifacts_path)
            adapter = {
                "adapter_schema_version": "3b.adapter.v1",
                "name": "inventory_only",
                "status": "not_required",
                "generation_status": "not_run_in_inventory_mode",
                "public_operations": {},
                "trace_events": [],
            }
            replay_plan = self._empty_replay_plan("three_b_mode_inventory")
        else:
            self._progress("ADAPTER", "解析或生成 repository-specific adapter")
            adapter = self._resolve_adapter(alignment_stats, inventory, artifacts_path)
            if (
                self.adapter_mode in {"auto", "synthesize"}
                and self.llm_client is not None
                and self.completion_iterations >= 0
            ):
                adapter = self._generate_remaining_adapter_cases(
                    adapter=adapter,
                    inventory=inventory,
                    alignment_stats=alignment_stats,
                    artifacts_path=artifacts_path,
                )
            self._progress(
                "ADAPTER",
                f"status={adapter.get('status')}, generation={adapter.get('generation_status', '')}, "
                f"operations={len(adapter.get('public_operations', {}))}, events={len(adapter.get('trace_events', []))}",
            )
            if artifacts_path:
                with open(artifacts_path / "effective_adapter.json", "w", encoding="utf-8") as f:
                    json.dump(adapter, f, indent=2, ensure_ascii=False)
            if mode == "replay" and artifacts_path and (artifacts_path / "replay_plan.json").exists():
                replay_plan = self._load_json(artifacts_path / "replay_plan.json")
            else:
                replay_plan = self.build_replay_plan(inventory, alignment_stats, adapter)
        replay_plan = self._ensure_replay_plan_alignment_validation(replay_plan, alignment_stats, adapter)
        self._progress(
            "REPLAY-PLAN",
            f"status={replay_plan.get('status')}, events={replay_plan.get('summary', {}).get('events', 0)}, "
            f"alignment={replay_plan.get('summary', {}).get('alignment_status_counts', {})}",
        )
        if artifacts_path:
            with open(artifacts_path / "replay_plan.json", "w", encoding="utf-8") as f:
                json.dump(replay_plan, f, indent=2, ensure_ascii=False)
        self._progress("REPLAY", "开始执行当前 Rust replay plan")
        replay_result = self.replay_public_plan(
            replay_plan,
            adapter,
            mode,
            work_root=self._resolve_work_root(artifacts_path),
        )
        self._progress(
            "REPLAY",
            f"status={replay_result.get('status')}, executed={replay_result.get('summary', {}).get('executed', 0)}, "
            f"passed={replay_result.get('summary', {}).get('passed', 0)}, "
            f"failed={replay_result.get('summary', {}).get('failed', 0)}",
        )
        if artifacts_path:
            with open(artifacts_path / "replay_result.json", "w", encoding="utf-8") as f:
                json.dump(replay_result, f, indent=2, ensure_ascii=False)
        if (
            mode in {"replay", "run"}
            and self._has_replay_infrastructure_failures(replay_result)
            and self.llm_client is not None
            and self.replay_repair_attempts > 0
        ):
            adapter, replay_plan, replay_result = self._repair_synthesized_adapter_after_replay_failure(
                adapter=adapter,
                replay_plan=replay_plan,
                replay_result=replay_result,
                alignment_stats=alignment_stats,
                artifacts_path=artifacts_path,
                mode=mode,
            )
            if artifacts_path:
                with open(artifacts_path / "effective_adapter.json", "w", encoding="utf-8") as f:
                    json.dump(adapter, f, indent=2, ensure_ascii=False)
                with open(artifacts_path / "replay_plan.json", "w", encoding="utf-8") as f:
                    json.dump(replay_plan, f, indent=2, ensure_ascii=False)
                with open(artifacts_path / "replay_result.json", "w", encoding="utf-8") as f:
                    json.dump(replay_result, f, indent=2, ensure_ascii=False)
        if self._has_replay_infrastructure_failures(replay_result):
            infra_events = [
                event for event in replay_result.get("events", [])
                if isinstance(event, dict) and event.get("status") == "infrastructure_failed"
            ]
            source_events = infra_events or replay_plan.get("events", [])
            self._replay_infrastructure_unresolved_case_ids = sorted({
                case_id
                for event in source_events
                if isinstance(event, dict)
                for case_id in event.get("source_case_ids", [])
                if case_id
            })
        function_boundary = self._function_boundary_status(layer, alignment_stats)

        if artifacts_dir:
            adapter["_adapter_source_path"] = self._display_path(
                Path(artifacts_dir) / "effective_adapter.json"
            )
            self._write_artifacts(
                Path(artifacts_dir),
                inventory,
                replay_plan,
                replay_result,
                adapter,
                alignment_stats,
                self._public_replay_eligibility,
            )
            self._cleanup_runtime_worktree(Path(artifacts_dir))

        report = self._build_report(
            mode=mode,
            layer=layer,
            alignment_stats=alignment_stats,
            adapter=adapter,
            inventory=inventory,
            replay_plan=replay_plan,
            replay_result=replay_result,
            function_boundary=function_boundary,
            artifacts_path=artifacts_path,
        )

        self._progress(
            "DONE",
            f"3B 完成; LLM calls={self._llm_usage['calls']}, total_tokens={self._llm_usage['total_tokens']}, "
            f"elapsed={self._elapsed_since_start():.1f}s",
        )

        return report

    def _elapsed_since_start(self):
        if self._run_started_at is None:
            return 0.0
        return time.monotonic() - self._run_started_at

    def _progress(self, stage, message):
        print(f"[3B +{self._elapsed_since_start():7.1f}s] [{stage}] {message}", flush=True)

    def _call_llm(self, stage, prompt, max_tokens=16000):
        prompt = prompt or ""
        call_number = self._llm_usage["calls"] + 1
        estimated_prompt_tokens = max(1, (len(prompt) + 3) // 4)
        self._progress(
            "LLM",
            f"call #{call_number} {stage} start; prompt≈{estimated_prompt_tokens} tok, max_out={max_tokens}",
        )
        started = time.monotonic()
        try:
            reply = self.llm_client.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            self._progress(
                "LLM",
                f"call #{call_number} stage={stage} 失败; elapsed={time.monotonic() - started:.1f}s; error={exc}",
            )
            raise
        elapsed = time.monotonic() - started
        usage = dict(getattr(self.llm_client, "last_usage", {}) or {})
        reported = bool(usage.get("reported_by_api"))
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0)
        if not reported:
            prompt_tokens = estimated_prompt_tokens
            completion_tokens = max(1, (len(reply or "") + 3) // 4)
            total_tokens = prompt_tokens + completion_tokens
        elif not total_tokens:
            total_tokens = prompt_tokens + completion_tokens
        self._llm_usage["calls"] += 1
        self._llm_usage["prompt_tokens"] += prompt_tokens
        self._llm_usage["completion_tokens"] += completion_tokens
        self._llm_usage["total_tokens"] += total_tokens
        self._llm_usage["cache_hit_tokens"] += int(usage.get("cache_hit_tokens", 0) or 0)
        self._llm_usage["cache_miss_tokens"] += int(usage.get("cache_miss_tokens", 0) or 0)
        self._llm_usage["elapsed_seconds"] = round(self._llm_usage["elapsed_seconds"] + elapsed, 3)
        stage_stats = self._llm_usage["calls_by_stage"].setdefault(stage, {
            "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        })
        stage_stats["calls"] += 1
        stage_stats["prompt_tokens"] += prompt_tokens
        stage_stats["completion_tokens"] += completion_tokens
        stage_stats["total_tokens"] += total_tokens
        source_label = "API" if reported else "估算"
        self._llm_usage["call_records"].append({
            "call": call_number,
            "stage": stage,
            "prompt_chars": len(prompt),
            "output_chars": len(reply or ""),
            "max_output_tokens": max_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "completion_hit_max_output": completion_tokens >= max_tokens,
            "total_tokens": total_tokens,
            "cache_hit_tokens": int(usage.get("cache_hit_tokens", 0) or 0),
            "cache_miss_tokens": int(usage.get("cache_miss_tokens", 0) or 0),
            "elapsed_seconds": round(elapsed, 3),
            "usage_source": source_label,
        })
        self._write_llm_usage_snapshot()
        self._progress(
            "LLM",
            f"call #{call_number} done; {elapsed:.1f}s, tokens({source_label})={total_tokens}, "
            f"total={self._llm_usage['total_tokens']}",
        )
        return reply

    def _write_llm_usage_snapshot(self):
        if not self._active_artifacts_path:
            return
        self._active_artifacts_path.mkdir(parents=True, exist_ok=True)
        with open(self._active_artifacts_path / "llm_usage.json", "w", encoding="utf-8") as f:
            json.dump(self._llm_usage, f, indent=2, ensure_ascii=False)

    def _cleanup_runtime_worktree(self, artifacts_path):
        if self.keep_debug_artifacts or self.adapter_mode == "prompt-only":
            return
        work_dir = artifacts_path / "work"
        if work_dir.exists():
            shutil.rmtree(work_dir)

    def _resolve_work_root(self, artifacts_path):
        if self.work_root:
            return self.work_root
        if artifacts_path:
            return artifacts_path / "work"
        return Path("output") / "phase3_3b" / "_work" / f"{self.src_name}_vs_{self.tgt_name}"

    def _display_path(self, path):
        if path is None:
            return ""
        path_text = str(path)
        if not path_text or path_text == "builtin":
            return path_text
        candidate = Path(path_text)
        try:
            return candidate.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except (OSError, ValueError):
            return candidate.as_posix()

    def _artifact_paths(self, artifacts_path):
        if not artifacts_path:
            return {}
        paths = {
            "effective_adapter": self._display_path(artifacts_path / "effective_adapter.json"),
            "test_inventory": self._display_path(artifacts_path / "test_inventory.json"),
            "replay_plan": self._display_path(artifacts_path / "replay_plan.json"),
            "replay_result": self._display_path(artifacts_path / "replay_result.json"),
            "public_replay_eligibility": self._display_path(
                artifacts_path / "public_replay_eligibility.json"
            ),
        }
        optional_artifact_paths = {
            "llm_usage": artifacts_path / "llm_usage.json",
            "adapter_synthesis_attempts": artifacts_path / "adapter_synthesis_attempts.json",
        }
        for name, path in optional_artifact_paths.items():
            if path.exists():
                paths[name] = self._display_path(path)
        generated_test_path = artifacts_path / "generated_public_replay.rs"
        if generated_test_path.exists():
            paths["generated_test_file"] = self._display_path(generated_test_path)
        if self.keep_debug_artifacts:
            paths["work_dir"] = self._display_path(artifacts_path / "work" / "latest")
        context_path = artifacts_path / "adapter_synthesis_context.json"
        if context_path.exists():
            paths["adapter_synthesis_context"] = self._display_path(context_path)
        if self.adapter_mode in {"auto", "synthesize", "prompt-only"}:
            optional_paths = {
                "adapter_synthesis_prompt": artifacts_path / "adapter_synthesis_prompt.md",
                "adapter_synthesis_raw_response": artifacts_path / "adapter_synthesis_raw_response.txt",
                "adapter_synthesis_validation_errors": artifacts_path / "adapter_synthesis_validation_errors.json",
                "synthesized_adapter": artifacts_path / "synthesized_adapter.json",
            }
            paths.update({
                name: self._display_path(path)
                for name, path in optional_paths.items()
                if path.exists()
            })
        return paths

    def _resolve_adapter(self, alignment_stats, inventory, artifacts_path):
        if self.adapter_mode == "existing":
            adapter = self._load_adapter()
            if adapter.get("status") == "loaded":
                self._prime_adapter_context(alignment_stats, inventory, artifacts_path)
                self._refresh_loaded_adapter_validation(adapter)
            return adapter

        if self.adapter_mode == "auto":
            adapter = self._load_adapter()
            if adapter.get("status") == "loaded":
                adapter.setdefault("generation_status", "reused_existing_adapter")
                adapter["_auto_resolution"] = "existing_adapter"
                self._prime_adapter_context(alignment_stats, inventory, artifacts_path)
                self._refresh_loaded_adapter_validation(adapter)
                return adapter

        context = self._build_adapter_synthesis_context(alignment_stats, inventory)
        self._last_synthesis_context = context
        if artifacts_path:
            artifacts_path.mkdir(parents=True, exist_ok=True)
            with open(artifacts_path / "adapter_synthesis_context.json", "w", encoding="utf-8") as f:
                json.dump(context, f, indent=2, ensure_ascii=False)

        if self.adapter_mode == "prompt-only":
            prompt = self._build_adapter_synthesis_prompt(context)
            self._last_synthesis_prompt = prompt
            self._write_adapter_synthesis_inputs(artifacts_path, context, prompt)
            return {
                "adapter_schema_version": "3b.adapter.v1",
                "name": "adapter_synthesis_prompt_only",
                "status": "adapter_synthesis_prompt_ready",
                "adapter_role": "repo_specific_behavior_recipe",
                "generation_status": "prompt_only",
                "generation_inputs": self._synthesis_generation_inputs(),
                "public_operations": {},
                "_adapter_source_path": self._display_path(artifacts_path / "adapter_synthesis_prompt.md") if artifacts_path else "",
            }

        if self.llm_client is None:
            raise ValueError("3B adapter synthesis requires llm_client; set DEEPSEEK_API_KEY and use synthesize/auto mode.")

        adapter = {}
        self._apply_synthesized_adapter_defaults(adapter)
        adapter["generation_status"] = "llm_case_generation_pending"
        adapter["rust_test_harness"] = ""
        adapter["trace_events"] = []
        adapter["excluded_behavior_cases"] = []
        return adapter

    def _prime_adapter_context(self, alignment_stats, inventory, artifacts_path):
        if self._last_synthesis_context is not None:
            return
        context = self._build_adapter_synthesis_context(alignment_stats, inventory)
        self._last_synthesis_context = context
        if artifacts_path:
            artifacts_path.mkdir(parents=True, exist_ok=True)
            with open(artifacts_path / "adapter_synthesis_context.json", "w", encoding="utf-8") as f:
                json.dump(context, f, indent=2, ensure_ascii=False)

    def _refresh_loaded_adapter_validation(self, adapter):
        if not isinstance(adapter, dict) or self._last_synthesis_context is None:
            return
        self._apply_synthesized_adapter_defaults(adapter)
        errors = self._validate_synthesized_adapter(adapter)
        adapter["_validation_errors"] = errors
        adapter["_validation_status"] = "passed" if not errors else "failed"

    def _apply_synthesized_adapter_defaults(self, adapter):
        adapter.setdefault("adapter_schema_version", "3b.adapter.v1")
        adapter.setdefault("name", f"llm_synthesized_{self.src_name}_to_{self.tgt_name}_public_v1")
        adapter.setdefault("status", "loaded")
        adapter.setdefault("adapter_role", "repo_specific_behavior_recipe")
        adapter.setdefault("generation_status", "llm_synthesized_v1")
        adapter.setdefault("generation_inputs", self._synthesis_generation_inputs())
        adapter.setdefault("recorder", "adapter_declared_trace_events_v1")
        adapter.setdefault("replay_generator", "rust_inline_harness_v1")
        adapter.setdefault("target_language", "rust")
        adapter.setdefault("target_test_command", ["cargo", "test", "--test", "cp2rs_3b_public"])
        adapter.setdefault("public_operations", {})
        self._normalize_expected_behavior_field_names(adapter)
        self._normalize_behavior_case_exclusions(adapter)

    def _normalize_expected_behavior_field_names(self, adapter):
        if not isinstance(adapter, dict):
            return
        events = adapter.get("trace_events", [])
        if not isinstance(events, list):
            return
        for event in events:
            if not isinstance(event, dict):
                continue
            if "expected_behavior_source" not in event and "oracle_source" in event:
                event["expected_behavior_source"] = event.pop("oracle_source")
            else:
                event.pop("oracle_source", None)
            if "expected_behavior_confidence" not in event and "oracle_confidence" in event:
                event["expected_behavior_confidence"] = event.pop("oracle_confidence")
            else:
                event.pop("oracle_confidence", None)
            for key in ("evidence", "input", "expected", "normalization"):
                if key in event:
                    event[key] = self._clean_expected_behavior_text(event[key])
        operations = adapter.get("public_operations", {})
        if isinstance(operations, dict):
            for operation in operations.values():
                if not isinstance(operation, dict):
                    continue
                for key in ("description", "normalization", "evidence"):
                    if key in operation:
                        operation[key] = self._clean_expected_behavior_text(operation[key])

    def _clean_expected_behavior_text(self, value):
        if isinstance(value, str):
            replacements = {
                "oracle_source": "expected_behavior_source",
                "oracle_confidence": "expected_behavior_confidence",
                "oracle_hint": "expected_behavior_hint",
                "equality_oracle": "equality_expected_behavior",
                "non_null_oracle": "non_null_expected_behavior",
                "null_oracle": "null_expected_behavior",
                "truth_oracle": "truth_expected_behavior",
                "falsehood_oracle": "falsehood_expected_behavior",
                "oracle": "expected behavior",
                "Oracle": "Expected behavior",
            }
            for old, new in replacements.items():
                value = value.replace(old, new)
            return value
        if isinstance(value, list):
            return [self._clean_expected_behavior_text(item) for item in value]
        if isinstance(value, dict):
            return {
                self._clean_expected_behavior_text(key): self._clean_expected_behavior_text(item)
                for key, item in value.items()
            }
        return value

    def _sanitize_generated_adapter(self, adapter):
        """Drop structurally unusable generated pieces; unresolved cases remain completion obligations."""
        events = adapter.get("trace_events")
        operations = adapter.get("public_operations")
        if not isinstance(events, list) or not isinstance(operations, dict):
            return
        context_cases = {
            case.get("case_id"): case
            for case in (self._last_synthesis_context or {}).get("source_evidence", {}).get("behavior_cases", [])
            if isinstance(case, dict) and case.get("case_id")
        }
        has_case_obligations = bool(context_cases)
        retained_events = []
        removed_event_ids = []
        replayed_case_ids = set()
        for event in events:
            if not isinstance(event, dict):
                continue
            source_case_ids = event.get("source_case_ids")
            if has_case_obligations and (not isinstance(source_case_ids, list) or not source_case_ids):
                if event.get("id"):
                    removed_event_ids.append(event.get("id"))
                continue
            retained_events.append(event)
            replayed_case_ids.update(source_case_ids or [])

        removed_exclusions = []
        retained_exclusions = []
        for exclusion in adapter.get("excluded_behavior_cases") or []:
            if not isinstance(exclusion, dict):
                retained_exclusions.append(exclusion)
                continue
            case_id = exclusion.get("case_id")
            case = context_cases.get(case_id, {})
            if case_id in replayed_case_ids:
                removed_exclusions.append(case_id)
                continue
            if (
                exclusion.get("reason") == "cannot_public_replay_internal_state_transition"
                and not case.get("has_mixed_public_internal_calls")
            ):
                removed_exclusions.append(case_id)
                continue
            retained_exclusions.append(exclusion)

        referenced_operations = {
            event.get("operation")
            for event in retained_events
            if event.get("operation")
        }
        removed_operations = sorted(set(operations) - referenced_operations)
        adapter["trace_events"] = retained_events
        adapter["excluded_behavior_cases"] = retained_exclusions
        adapter["public_operations"] = {
            name: operation
            for name, operation in operations.items()
            if name in referenced_operations
        }
        if removed_event_ids:
            adapter["rust_test_harness"] = self._remove_rust_test_functions(
                adapter.get("rust_test_harness", ""),
                set(removed_event_ids),
            )
        if removed_event_ids or removed_exclusions or removed_operations:
            adapter["_generated_adapter_sanitization"] = {
                "removed_events_without_source_case_ids": sorted(removed_event_ids),
                "removed_invalid_or_conflicting_exclusions": sorted(
                    case_id for case_id in removed_exclusions if case_id
                ),
                "removed_unreferenced_operations": removed_operations,
                "policy": "Removed generated fragments are not counted as completed; their source cases remain unresolved.",
            }

    def _remove_rust_test_functions(self, harness, test_names):
        if not isinstance(harness, str) or not test_names:
            return harness
        spans = []
        pattern = r"#\s*\[\s*test\s*\]\s*(?:\n\s*#\s*\[[^\]]+\]\s*)*\n?\s*fn\s+([A-Za-z_]\w*)\s*\("
        for match in re.finditer(pattern, harness):
            if match.group(1) not in test_names:
                continue
            open_brace = harness.find("{", match.end())
            close_brace = self._find_matching_brace(harness, open_brace) if open_brace >= 0 else -1
            if close_brace >= 0:
                spans.append((match.start(), close_brace + 1))
        for start, end in reversed(spans):
            harness = harness[:start] + harness[end:]
        return harness

    def _normalize_behavior_case_exclusions(self, adapter):
        """Deduplicate explicit exclusions without inferring their semantic reason."""
        exclusions = adapter.get("excluded_behavior_cases")
        if not isinstance(exclusions, list):
            return
        normalized_exclusions = []
        by_case_id = {}
        for item in exclusions:
            if not isinstance(item, dict):
                normalized_exclusions.append(item)
                continue
            case_id = item.get("case_id")
            if item.get("reason") == "oracle_not_precise":
                item["reason"] = "expected_behavior_not_precise"
            if "details" in item:
                item["details"] = self._clean_expected_behavior_text(item.get("details", ""))
            if not case_id or case_id not in by_case_id:
                normalized_exclusions.append(item)
                if case_id:
                    by_case_id[case_id] = item
                continue
            existing = by_case_id[case_id]
            existing_details = str(existing.get("details", "")).strip()
            duplicate_details = str(item.get("details", "")).strip()
            if duplicate_details and duplicate_details not in existing_details:
                existing["details"] = "; ".join(filter(None, [existing_details, duplicate_details]))
        adapter["excluded_behavior_cases"] = normalized_exclusions

    def _write_synthesized_adapter(self, artifacts_path, adapter, attempt_number):
        if artifacts_path:
            if self.keep_debug_artifacts:
                synthesized_path = artifacts_path / "synthesized_adapter.json"
                with open(synthesized_path, "w", encoding="utf-8") as f:
                    json.dump(adapter, f, indent=2, ensure_ascii=False)
                attempt_path = artifacts_path / f"synthesized_adapter_attempt_{attempt_number}.json"
                with open(attempt_path, "w", encoding="utf-8") as f:
                    json.dump(adapter, f, indent=2, ensure_ascii=False)
                adapter["_adapter_source_path"] = self._display_path(synthesized_path)
            else:
                adapter["_adapter_source_path"] = self._display_path(artifacts_path / "effective_adapter.json")
        else:
            adapter["_adapter_source_path"] = "llm_synthesized"

    def _write_synthesis_attempts(self, artifacts_path, attempts):
        if not artifacts_path:
            return
        artifacts_path.mkdir(parents=True, exist_ok=True)
        with open(artifacts_path / "adapter_synthesis_attempts.json", "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "3b.adapter_synthesis_attempts.v2",
                "source_repository": self.src_name,
                "target_repository": self.tgt_name,
                "attempt_count": len(attempts),
                "attempts": attempts,
            }, f, indent=2, ensure_ascii=False)

    def _repair_synthesized_adapter_after_replay_failure(
        self,
        adapter,
        replay_plan,
        replay_result,
        alignment_stats,
        artifacts_path,
        mode,
    ):
        attempts = self._read_synthesis_attempts(artifacts_path)
        current_adapter = adapter
        current_replay_plan = replay_plan
        current_replay_result = replay_result

        for repair_index in range(1, self.replay_repair_attempts + 1):
            attempt_number = len(attempts) + 1
            total_infra_failed_tests = len(self._infrastructure_failed_test_context(
                self._rust_inline_harness_from_adapter(current_adapter),
                current_replay_result,
                max_tests=10000,
            ))
            infra_failed_tests = self._infrastructure_failed_test_context(
                self._rust_inline_harness_from_adapter(current_adapter),
                current_replay_result,
                max_tests=self._replay_repair_batch_size(),
            )
            if not infra_failed_tests:
                break
            self._progress(
                "REPLAY-REPAIR",
                (
                    f"attempt {repair_index}/{self.replay_repair_attempts}: "
                    f"infrastructure_failed_tests={len(infra_failed_tests)}/{total_infra_failed_tests}, "
                    f"current_status={current_replay_result.get('status')}"
                ),
            )
            prompt = self._build_replay_repair_prompt(
                adapter=current_adapter,
                replay_plan=current_replay_plan,
                replay_result=current_replay_result,
                failed_test_context=infra_failed_tests,
            )
            if artifacts_path and self.keep_debug_artifacts:
                repair_prompt_path = artifacts_path / f"adapter_replay_repair_prompt_attempt_{attempt_number}.md"
                repair_prompt_path.write_text(prompt, encoding="utf-8")

            raw_reply = self._call_llm(
                f"replay_infrastructure_repair_attempt_{repair_index}",
                prompt,
            )
            if artifacts_path and self.keep_debug_artifacts:
                raw_path = artifacts_path / f"adapter_replay_repair_raw_response_attempt_{attempt_number}.txt"
                raw_path.write_text(raw_reply or "", encoding="utf-8")

            repaired_adapter = None
            errors = []
            try:
                candidate = self._extract_json_from_llm_reply(raw_reply)
                if not isinstance(candidate, dict):
                    errors.append("LLM did not return a JSON object")
                    repaired_adapter = None
                else:
                    repaired_adapter = self._merge_replay_repair_patch(current_adapter, candidate)
                    self._apply_synthesized_adapter_defaults(repaired_adapter)
                    repaired_adapter["generation_status"] = "llm_synthesized_repaired_v1"
                    errors.extend(self._validate_synthesized_adapter(repaired_adapter))
            except Exception as exc:
                errors.append(f"JSON extraction failed: {exc}")

            attempts.append({
                "attempt": attempt_number,
                "stage": "replay_infrastructure_repair",
                "status": "failed" if errors else "schema_passed",
                "errors": errors,
                "input_infrastructure_failed_tests": len(infra_failed_tests),
                "total_infrastructure_failed_tests_before_attempt": total_infra_failed_tests,
            })
            self._write_synthesis_attempts(artifacts_path, attempts)

            if repaired_adapter is None or errors:
                self._progress(
                    "REPLAY-REPAIR",
                    f"attempt {repair_index}: patch rejected before rerun; errors={len(errors)}",
                )
                continue

            self._progress("REPLAY-REPAIR", f"attempt {repair_index}: patch accepted; rerun replay")
            self._write_synthesized_adapter(artifacts_path, repaired_adapter, attempt_number)
            repaired_replay_plan = self.build_replay_plan(
                inventory={},
                alignment_stats=alignment_stats,
                adapter=repaired_adapter,
            )
            repaired_replay_plan = self._ensure_replay_plan_alignment_validation(
                repaired_replay_plan,
                alignment_stats,
                repaired_adapter,
            )
            repair_event_ids = [
                item.get("event_id") or item.get("test_name")
                for item in infra_failed_tests
                if isinstance(item, dict) and (item.get("event_id") or item.get("test_name"))
            ]
            repaired_subset_result = self.replay_public_plan_event_subset(
                repaired_replay_plan,
                repaired_adapter,
                mode,
                event_ids=repair_event_ids,
                work_root=self._resolve_work_root(artifacts_path),
                run_label=f"repair_attempt_{repair_index}",
            )
            repaired_replay_result = self._merge_replay_subset_result(
                current_replay_result,
                repaired_subset_result,
            )
            attempts[-1]["status"] = (
                "passed"
                if not self._has_replay_infrastructure_failures(repaired_replay_result)
                else "failed"
            )
            attempts[-1]["replay_status"] = repaired_replay_result.get("status")
            attempts[-1]["replay_reason"] = repaired_replay_result.get("reason", "")
            attempts[-1]["rerun_event_count"] = len(repair_event_ids)
            attempts[-1]["remaining_infrastructure_failures"] = (
                repaired_replay_result.get("summary", {}) or {}
            ).get("infrastructure_failures", 0)
            self._write_synthesis_attempts(artifacts_path, attempts)
            self._progress(
                "REPLAY-REPAIR",
                (
                    f"attempt {repair_index}: rerun status={repaired_replay_result.get('status')}, "
                    f"executed={(repaired_replay_result.get('summary', {}) or {}).get('executed', 0)}, "
                    f"passed={(repaired_replay_result.get('summary', {}) or {}).get('passed', 0)}, "
                    f"failed={(repaired_replay_result.get('summary', {}) or {}).get('failed', 0)}, "
                    f"infra={(repaired_replay_result.get('summary', {}) or {}).get('infrastructure_failures', 0)}"
                ),
            )

            current_adapter = repaired_adapter
            current_replay_plan = repaired_replay_plan
            current_replay_result = repaired_replay_result
            if not self._has_replay_infrastructure_failures(repaired_replay_result):
                break

        return current_adapter, current_replay_plan, current_replay_result

    def _generate_remaining_adapter_cases(
        self,
        adapter,
        inventory,
        alignment_stats,
        artifacts_path,
    ):
        """Generate additive adapter fragments before replay, retaining each valid case."""
        attempts = []
        if artifacts_path:
            stale_attempts_path = artifacts_path / "adapter_synthesis_attempts.json"
            if stale_attempts_path.exists():
                stale_attempts_path.unlink()
        current_adapter = adapter
        case_attempt_counts = {}
        coverage = self._adapter_behavior_case_coverage(current_adapter)
        initial_missing = list(coverage.get("missing_behavior_case_ids") or [])
        max_attempts_per_case = self.synthesis_attempts
        if self.completion_iterations > 0:
            iteration_limit = self.completion_iterations
            budget_mode = "fixed_iteration_limit"
        else:
            iteration_limit = (
                (len(initial_missing) * max_attempts_per_case + self.completion_batch_size - 1)
                // self.completion_batch_size
            )
            budget_mode = "per_case_attempt_limit"
        self._last_completion_budget = {
            "mode": budget_mode,
            "max_attempts_per_case": max_attempts_per_case,
            "initial_unresolved_behavior_cases": len(initial_missing),
            "batch_size": self.completion_batch_size,
            "generation_unit": "eligible_source_behavior_case",
        }
        self._progress(
            "ADAPTER-GENERATION",
            f"worklist={len(initial_missing)}, batch={self.completion_batch_size}, "
            f"max_attempts_per_case={max_attempts_per_case}, max_iterations={iteration_limit}",
        )

        retry_case_ids = []
        split_retry_batches = []
        iteration = 0
        while iteration < iteration_limit:
            iteration += 1
            coverage = self._adapter_behavior_case_coverage(current_adapter)
            total_missing_ids = list(coverage.get("missing_behavior_case_ids", []))
            missing_ids = [
                case_id for case_id in total_missing_ids
                if case_attempt_counts.get(case_id, 0) < max_attempts_per_case
            ]
            if not missing_ids and not split_retry_batches:
                break
            current_missing = set(missing_ids)
            retry_case_ids = [case_id for case_id in retry_case_ids if case_id in current_missing]
            split_retry_batches = [
                [case_id for case_id in batch if case_id in current_missing]
                for batch in split_retry_batches
            ]
            split_retry_batches = [batch for batch in split_retry_batches if batch]
            if split_retry_batches:
                scheduling = "split_retry_after_output_limit"
                scheduled_ids = split_retry_batches.pop(0)
                effective_batch_size = len(scheduled_ids)
            else:
                scheduling = "immediate_retry" if retry_case_ids else "new_batch"
                scheduled_ids = retry_case_ids or missing_ids
                effective_batch_size = self.completion_batch_size
            scope = {"missing_behavior_case_ids": scheduled_ids}
            targeted_scope = self._targeted_adapter_generation_scope(
                scope=scope,
                alignment_stats=alignment_stats,
                inventory=inventory,
                iteration=iteration,
                batch_size=effective_batch_size,
                behavior_case_attempt_counts=case_attempt_counts,
            )
            targeted_ids = targeted_scope.get("targeted_missing_behavior_case_ids", [])
            targeted_attempts_before = targeted_scope.get("targeted_case_attempt_counts_before", {})
            exhausted_after_batch = [
                case_id for case_id in targeted_ids
                if targeted_attempts_before.get(case_id, 0) + 1 >= max_attempts_per_case
            ]
            attempt_values = list(targeted_attempts_before.values())
            if attempt_values:
                attempt_summary = f"{min(attempt_values)}-{max(attempt_values)}"
            else:
                attempt_summary = "n/a"
            self._progress(
                "ADAPTER-GENERATION",
                f"batch {iteration}/{iteration_limit} {scheduling}: unresolved={len(total_missing_ids)}, "
                f"retryable={len(missing_ids)}, targeted={len(targeted_ids)}, "
                f"attempts_before={attempt_summary}, exhaust_if_failed={len(exhausted_after_batch)}, "
                f"sample={targeted_ids[:3]}",
            )
            for case_id in targeted_ids:
                case_attempt_counts[case_id] = case_attempt_counts.get(case_id, 0) + 1

            prompt = self._build_adapter_case_generation_prompt(
                adapter=current_adapter,
                inventory=inventory,
                alignment_stats=alignment_stats,
                scope=targeted_scope,
                iteration=iteration,
            )
            attempt_number = len(attempts) + 1
            if artifacts_path and self.keep_debug_artifacts:
                prompt_path = artifacts_path / f"behavior_case_conversion_prompt_attempt_{attempt_number}.md"
                prompt_path.write_text(prompt, encoding="utf-8")

            raw_reply = self._call_llm(
                f"behavior_case_conversion_batch_{iteration}",
                prompt,
                max_tokens=self._adapter_generation_max_output_tokens(len(targeted_ids)),
            )
            self._synthesis_attempts_used += 1
            if artifacts_path and self.keep_debug_artifacts:
                raw_path = artifacts_path / f"behavior_case_conversion_raw_response_attempt_{attempt_number}.txt"
                raw_path.write_text(raw_reply or "", encoding="utf-8")

            errors = []
            accepted_case_ids = []
            try:
                candidate = self._extract_json_from_llm_reply(raw_reply)
                if not isinstance(candidate, dict):
                    errors.append("LLM did not return a JSON object")
                else:
                    current_adapter, accepted_case_ids, fragment_errors = self._accept_valid_case_fragments(
                        current_adapter,
                        candidate,
                        targeted_ids,
                        scoped_pairs=targeted_scope.get("targeted_alignment_pairs", []),
                    )
                    errors.extend(fragment_errors)
            except Exception as exc:
                errors.append(f"JSON extraction failed: {exc}")

            if self._should_split_adapter_generation_batch_after_output_limit(errors, targeted_ids):
                for case_id in targeted_ids:
                    case_attempt_counts[case_id] = max(0, case_attempt_counts.get(case_id, 0) - 1)
                split_batches = self._split_case_batch(targeted_ids)
                split_retry_batches = split_batches + split_retry_batches
                iteration_limit += max(0, len(split_batches) - 1)
                attempts.append({
                    "attempt": attempt_number,
                    "stage": "behavior_case_conversion",
                    "iteration": iteration,
                    "scheduling": scheduling,
                    "status": "split_due_output_limit",
                    "targeted_case_ids": targeted_ids,
                    "accepted_case_ids": [],
                    "replay_generated_case_ids": [],
                    "excluded_case_ids": [],
                    "unresolved_case_ids": targeted_ids,
                    "errors": errors,
                    "split_retry_batches": split_batches,
                    "llm_output_limit": (self._llm_usage.get("call_records") or [{}])[-1].get("max_output_tokens"),
                })
                self._write_synthesis_attempts(artifacts_path, attempts)
                self._progress(
                    "ADAPTER-GENERATION",
                    f"batch {iteration}: JSON output likely truncated; split targeted={len(targeted_ids)} "
                    f"into {[len(batch) for batch in split_batches]} and retry without consuming case attempts",
                )
                retry_case_ids = []
                continue

            post_coverage = self._adapter_behavior_case_coverage(current_adapter)
            replayed_case_ids = sorted(
                set(targeted_ids) & set(post_coverage.get("replayed_behavior_case_ids", []))
            )
            excluded_case_ids = sorted(
                set(targeted_ids) & set(post_coverage.get("excluded_behavior_case_ids", []))
            )
            unresolved_case_ids = sorted(set(targeted_ids) - set(accepted_case_ids))
            retry_case_ids = [
                case_id for case_id in unresolved_case_ids
                if case_attempt_counts.get(case_id, 0) < max_attempts_per_case
            ]
            attempts.append({
                "attempt": attempt_number,
                "stage": "behavior_case_conversion",
                "iteration": iteration,
                "scheduling": scheduling,
                "status": "partial" if accepted_case_ids and errors else ("accepted" if accepted_case_ids else "failed"),
                "targeted_case_ids": targeted_ids,
                "accepted_case_ids": accepted_case_ids,
                "replay_generated_case_ids": replayed_case_ids,
                "excluded_case_ids": excluded_case_ids,
                "unresolved_case_ids": unresolved_case_ids,
                "errors": errors,
            })
            for case_id in targeted_ids:
                if case_id in replayed_case_ids:
                    outcome = "replay_generated"
                elif case_id in excluded_case_ids:
                    outcome = "excluded_with_valid_reason"
                else:
                    outcome = "unresolved"
                self._note_case_conversion_attempts(
                    [case_id],
                    stage="behavior_case_conversion",
                    outcome=outcome,
                    errors=errors if case_id not in accepted_case_ids else [],
                )
            self._write_synthesis_attempts(artifacts_path, attempts)
            self._progress(
                "ADAPTER-GENERATION",
                f"batch {iteration}: replay_generated={len(replayed_case_ids)}, "
                f"excluded={len(excluded_case_ids)}, unresolved_in_batch={len(unresolved_case_ids)}, "
                f"retry_next={len(retry_case_ids)}",
            )
            if accepted_case_ids:
                self._write_synthesized_adapter(artifacts_path, current_adapter, attempt_number)

        final_coverage = self._adapter_behavior_case_coverage(current_adapter)
        self._adapter_generation_unresolved_case_ids = sorted(
            final_coverage.get("missing_behavior_case_ids", [])
        )
        current_adapter["generation_status"] = "llm_synthesized_case_generation_v1"
        current_adapter["adapter_generation"] = {
            "max_attempts_per_case": max_attempts_per_case,
            "batch_size": self.completion_batch_size,
            "unresolved_case_count": len(self._adapter_generation_unresolved_case_ids),
            "unresolved_case_ids": self._adapter_generation_unresolved_case_ids,
            "unresolved_cases": [
                {"case_id": case_id, "status": "unresolved_adapter_generation"}
                for case_id in self._adapter_generation_unresolved_case_ids
            ],
        }
        final_validation_errors = self._validate_synthesized_adapter(current_adapter)
        current_adapter["_validation_errors"] = final_validation_errors
        current_adapter["_validation_status"] = "passed" if not final_validation_errors else "failed"
        return current_adapter

    def _case_generation_feedback_for_ids(self, case_ids, max_errors_per_case=4):
        feedback = {}
        for case_id in case_ids or []:
            entry = self._case_conversion_attempts.get(case_id)
            if not entry:
                continue
            recent_errors = []
            for attempt in reversed(entry.get("attempts", [])):
                for error in attempt.get("errors", []):
                    if error and error not in recent_errors:
                        recent_errors.append(error)
                    if len(recent_errors) >= max_errors_per_case:
                        break
                if len(recent_errors) >= max_errors_per_case:
                    break
            feedback[case_id] = {
                "attempt_count": entry.get("attempt_count", 0),
                "last_outcome": (entry.get("attempts") or [{}])[-1].get("outcome", ""),
                "recent_errors": recent_errors,
            }
        return feedback

    def _adapter_generation_max_output_tokens(self, targeted_case_count):
        targeted_case_count = max(1, int(targeted_case_count or 1))
        # Most per-case fragments are compact. Smaller retry batches should not
        # reserve a 16k completion budget because the API may spend more time
        # exploring unnecessary prose/variants.
        return min(16000, max(4000, targeted_case_count * 1800))

    def _should_split_adapter_generation_batch_after_output_limit(self, errors, targeted_ids):
        if len(targeted_ids or []) <= 1:
            return False
        if not any("JSON extraction failed" in str(error) for error in errors or []):
            return False
        call_records = self._llm_usage.get("call_records") or []
        if not call_records:
            return False
        last_call = call_records[-1]
        return bool(last_call.get("completion_hit_max_output"))

    def _split_case_batch(self, case_ids):
        case_ids = list(dict.fromkeys(case_ids or []))
        if len(case_ids) <= 1:
            return [case_ids] if case_ids else []
        midpoint = (len(case_ids) + 1) // 2
        return [case_ids[:midpoint], case_ids[midpoint:]]

    def _merge_adapter_generation_patch(self, current_adapter, candidate):
        """Merge generated additions without allowing accepted cases to disappear."""
        if candidate.get("adapter_patch_version") != "3b.adapter_patch.v1":
            return candidate

        merged = json.loads(json.dumps(current_adapter))
        operations = merged.setdefault("public_operations", {})
        for name, operation in (candidate.get("public_operations_add") or {}).items():
            if name in operations and operations[name] != operation:
                raise ValueError(f"adapter generation patch attempts to replace existing operation: {name}")
            operations[name] = operation

        events = merged.setdefault("trace_events", [])
        existing_events = {
            event.get("id"): event
            for event in events
            if isinstance(event, dict) and event.get("id")
        }
        for event in candidate.get("trace_events_add") or []:
            event_id = event.get("id") if isinstance(event, dict) else None
            if event_id in existing_events:
                if existing_events[event_id] != event:
                    raise ValueError(f"adapter generation patch attempts to replace existing trace event: {event_id}")
                continue
            events.append(event)

        exclusions = merged.setdefault("excluded_behavior_cases", [])
        exclusions.extend(candidate.get("excluded_behavior_cases_add") or [])

        harness_append = candidate.get("rust_test_harness_append") or ""
        if harness_append.strip():
            existing_harness = merged.get("rust_test_harness", "")
            existing_lines = {line.strip() for line in existing_harness.splitlines() if line.strip()}
            append_lines = [
                line for line in harness_append.strip().splitlines()
                if not (
                    line.strip().startswith(("use ", "extern crate "))
                    and line.strip() in existing_lines
                )
            ]
            merged["rust_test_harness"] = (
                existing_harness.rstrip() + "\n\n" + "\n".join(append_lines).strip() + "\n"
            ).lstrip()
            merged["rust_test_harness"] = self._sanitize_rust_harness(merged["rust_test_harness"])

        self._normalize_behavior_case_exclusions(merged)
        return merged

    def _accept_valid_case_fragments(self, current_adapter, candidate, targeted_case_ids, scoped_pairs=None):
        """Accept independently valid event/exclusion fragments from one LLM batch."""
        targeted = set(targeted_case_ids or [])
        case_result_feedback = self._case_result_feedback_by_id(candidate, targeted)
        if candidate.get("adapter_case_generation_version") in {"3b.case_results.v1", "3b.case_results.v2"}:
            candidate = self._case_results_to_adapter_patch(candidate, targeted_case_ids)

        if candidate.get("adapter_patch_version") == "3b.adapter_patch.v1":
            operations = candidate.get("public_operations_add") or {}
            events = candidate.get("trace_events_add") or []
            exclusions = candidate.get("excluded_behavior_cases_add") or []
            harness = candidate.get("rust_test_harness_append") or ""
        else:
            operations = candidate.get("public_operations") or {}
            events = candidate.get("trace_events") or []
            exclusions = candidate.get("excluded_behavior_cases") or []
            harness = candidate.get("rust_test_harness") or ""

        if not isinstance(operations, dict) or not isinstance(events, list):
            return current_adapter, [], ["adapter generation response has invalid operation/event containers"]

        test_blocks = self._rust_test_blocks_by_name(harness)
        import_lines = self._rust_import_lines(harness)
        accepted = set()
        errors = []
        current = json.loads(json.dumps(current_adapter))
        allowed_source_uuids, allowed_target_uuids = self._adapter_case_generation_allowed_uuids(
            scoped_pairs or [],
        )

        for event in events:
            if not isinstance(event, dict):
                errors.append("trace event fragment must be an object")
                continue
            case_ids = set(event.get("source_case_ids") or []) & targeted
            if not case_ids:
                continue
            event_id = event.get("id")
            operation_name = event.get("operation")
            operation = operations.get(operation_name) or current.get("public_operations", {}).get(operation_name)
            test_block = test_blocks.get(event_id)
            if not operation or not test_block:
                errors.append(
                    f"case fragment {sorted(case_ids)} is missing operation {operation_name!r} "
                    f"or Rust test {event_id!r}"
                )
                continue
            source_outside_batch = sorted(set(operation.get("source_functions") or []) - allowed_source_uuids)
            target_outside_batch = sorted(set(operation.get("target_functions") or []) - allowed_target_uuids)
            if source_outside_batch:
                errors.extend(
                    f"case {case_id}: operation source_functions outside current batch allowed source UUIDs: "
                    f"{source_outside_batch[:8]}"
                    for case_id in sorted(case_ids)
                )
                continue
            if target_outside_batch:
                errors.extend(
                    f"case {case_id}: operation target_functions outside current batch allowed target API UUIDs: "
                    f"{target_outside_batch[:8]}"
                    for case_id in sorted(case_ids)
                )
                continue
            harness_append = "\n".join(import_lines + [test_block])
            patch = {
                "adapter_patch_version": "3b.adapter_patch.v1",
                "public_operations_add": {operation_name: operation},
                "trace_events_add": [event],
                "excluded_behavior_cases_add": [],
                "rust_test_harness_append": harness_append,
            }
            try:
                trial = self._merge_adapter_generation_patch(current, patch)
                self._apply_synthesized_adapter_defaults(trial)
                trial_errors = self._validate_synthesized_adapter(trial)
            except Exception as exc:
                trial_errors = [str(exc)]
            if trial_errors:
                errors.extend(
                    f"case {case_id}: {error}"
                    for case_id in sorted(case_ids)
                    for error in trial_errors[:3]
                )
                continue
            current = trial
            accepted.update(case_ids)

        for exclusion in exclusions if isinstance(exclusions, list) else []:
            if not isinstance(exclusion, dict) or exclusion.get("case_id") not in targeted:
                continue
            case_id = exclusion.get("case_id")
            errors.append(
                f"case {case_id}: adapter generation may not exclude eligible cases; "
                "return replay_generated or unresolved_adapter_generation"
            )

        for case_id in sorted(targeted - accepted):
            if not any(error.startswith(f"case {case_id}:") for error in errors):
                feedback = case_result_feedback.get(case_id)
                if feedback:
                    errors.append(f"case {case_id}: {feedback}")
                else:
                    errors.append(f"case {case_id}: no independently valid replay event or unresolved status was returned")

        return current, sorted(accepted), errors

    def _case_result_feedback_by_id(self, candidate, targeted):
        feedback = {}
        if not isinstance(candidate, dict):
            return feedback
        results = candidate.get("case_results")
        if not isinstance(results, list):
            return feedback
        for result in results:
            if not isinstance(result, dict):
                continue
            case_id = result.get("case_id")
            if case_id not in targeted:
                continue
            status = result.get("status", "")
            if status == "replay_generated":
                continue
            reason = result.get("reason") or result.get("error") or ""
            details = result.get("details") or result.get("message") or ""
            text = f"model returned status={status or 'missing'}"
            if reason:
                text += f", reason={self._truncate_text(str(reason), max_chars=220)}"
            if details:
                text += f", details={self._truncate_text(str(details), max_chars=300)}"
            feedback[case_id] = text
        return feedback

    def _case_results_to_adapter_patch(self, candidate, targeted_case_ids):
        targeted = set(targeted_case_ids or [])
        operations = {}
        events = []
        harness_parts = []
        errors_as_exclusions = []
        for result in candidate.get("case_results") or []:
            if not isinstance(result, dict):
                continue
            case_id = result.get("case_id")
            if case_id not in targeted:
                continue
            status = result.get("status", "")
            if status != "replay_generated":
                # Keep unresolved statuses out of the adapter. The caller will
                # mark the case unresolved because no accepted event is present.
                continue

            compact_event = result.get("event") or result.get("replay_event") or {}
            operation = result.get("operation") or result.get("public_operation") or {}
            event = result.get("trace_event") or {}
            if compact_event and not operation:
                operation = {
                    "id": compact_event.get("operation") or compact_event.get("operation_id") or compact_event.get("id"),
                    "description": compact_event.get("description", ""),
                    "source_functions": compact_event.get("source_functions", []),
                    "target_functions": compact_event.get("target_functions", []),
                    "normalization": compact_event.get("normalization", ""),
                    "evidence": compact_event.get("evidence", []),
                }
            if compact_event and not event:
                event = {
                    "id": compact_event.get("id"),
                    "operation": compact_event.get("operation") or compact_event.get("operation_id") or compact_event.get("id"),
                    "evidence": compact_event.get("evidence", ""),
                    "source_case_ids": compact_event.get("source_case_ids", [case_id]),
                    "input": compact_event.get("input", {}),
                    "expected": compact_event.get("expected", {}),
                    "expected_behavior_source": compact_event.get("expected_behavior_source", ""),
                    "expected_behavior_confidence": compact_event.get("expected_behavior_confidence", ""),
                }
            if not isinstance(operation, dict) or not isinstance(event, dict):
                errors_as_exclusions.append({
                    "case_id": case_id,
                    "reason": "invalid_case_result_shape",
                    "details": "replay_generated result must include operation and trace_event objects",
                })
                continue

            operation_id = (
                operation.get("id")
                or operation.get("name")
                or event.get("operation")
                or self._safe_identifier(f"operation_{case_id}")
            )
            operation_id = self._safe_identifier(operation_id)
            event_id = event.get("id") or self._safe_identifier(f"replay_{case_id}")
            event_id = self._safe_identifier(event_id)

            normalized_operation = self._normalize_generated_operation(
                operation,
                operation_id,
                case_id,
            )
            normalized_event = self._normalize_generated_event(
                event,
                event_id,
                operation_id,
                case_id,
            )
            rust_test = (
                result.get("rust_test_body")
                or result.get("rust_test_harness_append")
                or result.get("rust_test")
                or ""
            )
            rust_test = self._normalize_case_rust_test(rust_test, event_id)
            operations[operation_id] = normalized_operation
            events.append(normalized_event)
            if rust_test.strip():
                harness_parts.append(rust_test)

        return {
            "adapter_patch_version": "3b.adapter_patch.v1",
            "public_operations_add": operations,
            "trace_events_add": events,
            "excluded_behavior_cases_add": errors_as_exclusions,
            "rust_test_harness_append": "\n\n".join(harness_parts),
        }

    def _normalize_generated_operation(self, operation, operation_id, case_id):
        operation = json.loads(json.dumps(operation)) if isinstance(operation, dict) else {}
        operation.pop("id", None)
        operation.pop("name", None)
        case = (getattr(self, "_last_behavior_case_details", {}) or {}).get(case_id, {})
        source_functions = list(operation.get("source_functions") or [])
        if not source_functions:
            source_functions = list(case.get("aligned_source_functions") or [])
        source_functions = sorted(dict.fromkeys(source_functions))
        expected_targets = self._synthesis_expected_targets_by_source()
        target_functions = list(operation.get("target_functions") or [])
        for src_uuid in source_functions:
            target_functions.extend(sorted(expected_targets.get(src_uuid, set())))
        for substitution in case.get("required_internal_public_substitutions", []) or []:
            if isinstance(substitution, dict):
                target_functions.extend(substitution.get("target_public_functions", []) or [])
        operation["source_functions"] = source_functions
        operation["target_functions"] = sorted(dict.fromkeys(target_functions))
        operation.setdefault("description", f"Public replay operation for source behavior case {case_id}")
        operation.setdefault("normalization", "Compare source-test observable behavior through target public APIs.")
        evidence = operation.get("evidence")
        if isinstance(evidence, str) and evidence.strip():
            operation["evidence"] = [evidence.strip()]
            evidence = operation["evidence"]
        if not isinstance(evidence, list) or not evidence:
            operation["evidence"] = [self._case_evidence_label(case_id)]
        return operation

    def _normalize_generated_event(self, event, event_id, operation_id, case_id):
        event = json.loads(json.dumps(event)) if isinstance(event, dict) else {}
        event["id"] = event_id
        event["operation"] = operation_id
        source_case_ids = event.get("source_case_ids")
        if not isinstance(source_case_ids, list) or case_id not in source_case_ids:
            event["source_case_ids"] = [case_id]
        event.setdefault("evidence", self._case_evidence_label(case_id))
        event.setdefault("input", {"case": case_id})
        event.setdefault("expected", {"observable_behavior": "source-test-derived behavior"})
        event.setdefault(
            "expected_behavior_source",
            event.pop("oracle_source", "source_test_assertion"),
        )
        event.setdefault(
            "expected_behavior_confidence",
            event.pop("oracle_confidence", "medium"),
        )
        return event

    def _normalize_case_rust_test(self, rust_test, event_id):
        rust_test = self._strip_markdown_fence(rust_test or "").strip()
        if not rust_test:
            return ""
        if "#[test]" in rust_test and re.search(rf"\bfn\s+{re.escape(event_id)}\s*\(", rust_test):
            return rust_test
        if "#[test]" in rust_test:
            return re.sub(
                r"(#\s*\[\s*test\s*\]\s*(?:#\s*\[[^\]]+\]\s*)*fn\s+)([A-Za-z_][A-Za-z0-9_]*)(\s*\()",
                rf"\g<1>{event_id}\g<3>",
                rust_test,
                count=1,
            )
        body = rust_test
        if not body.startswith("{"):
            body = "{\n" + body.rstrip() + "\n}"
        return f"#[test]\nfn {event_id}() {body}\n"

    def _case_evidence_label(self, case_id):
        case = (getattr(self, "_last_behavior_case_details", {}) or {}).get(case_id, {})
        path = case.get("path", "")
        name = case.get("name", "")
        line = case.get("start_line")
        label = f"{path}:{line} {name}".strip()
        return label or case_id

    def _safe_identifier(self, value):
        value = str(value or "").strip()
        value = re.sub(r"[^A-Za-z0-9_]", "_", value)
        value = re.sub(r"_+", "_", value).strip("_")
        if not value:
            value = "cp2rs_3b_replay"
        if not re.match(r"^[A-Za-z_]", value):
            value = f"case_{value}"
        return value

    def _rust_test_blocks_by_name(self, harness):
        return {
            name: block
            for name, (_start, _end, block) in self._rust_test_block_spans_by_name(harness).items()
        }

    def _rust_test_block_spans_by_name(self, harness):
        if not isinstance(harness, str):
            return {}
        starts = list(re.finditer(
            r"#\s*\[\s*test\s*\]\s*(?:#\s*\[[^\]]+\]\s*)*fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            harness,
        ))
        blocks = {}
        for match in starts:
            body_start = harness.find("{", match.end())
            if body_start < 0:
                continue
            body_end = self._find_matching_rust_brace(harness, body_start)
            if body_end < 0:
                continue
            end = body_end + 1
            while end < len(harness) and harness[end] in " \t\r\n":
                end += 1
            blocks[match.group(1)] = (match.start(), end, harness[match.start():end].strip())
        return blocks

    def _find_matching_rust_brace(self, text, open_index):
        if open_index < 0 or open_index >= len(text) or text[open_index] != "{":
            return -1
        depth = 0
        index = open_index
        state = "code"
        raw_hashes = ""
        block_comment_depth = 0
        while index < len(text):
            ch = text[index]
            nxt = text[index + 1] if index + 1 < len(text) else ""

            if state == "line_comment":
                if ch == "\n":
                    state = "code"
                index += 1
                continue
            if state == "block_comment":
                if ch == "/" and nxt == "*":
                    block_comment_depth += 1
                    index += 2
                    continue
                if ch == "*" and nxt == "/":
                    block_comment_depth -= 1
                    index += 2
                    if block_comment_depth <= 0:
                        state = "code"
                    continue
                index += 1
                continue
            if state == "string":
                if ch == "\\":
                    index += 2
                    continue
                if ch == '"':
                    state = "code"
                index += 1
                continue
            if state == "char":
                if ch == "\\":
                    index += 2
                    continue
                if ch == "'":
                    state = "code"
                index += 1
                continue
            if state == "raw_string":
                if ch == '"' and text.startswith(raw_hashes, index + 1):
                    index += 1 + len(raw_hashes)
                    state = "code"
                    raw_hashes = ""
                    continue
                index += 1
                continue

            if ch == "/" and nxt == "/":
                state = "line_comment"
                index += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block_comment"
                block_comment_depth = 1
                index += 2
                continue
            raw_match = re.match(r"b?r(#{0,16})\"", text[index:])
            if raw_match:
                raw_hashes = raw_match.group(1)
                state = "raw_string"
                index += raw_match.end()
                continue
            if ch == '"':
                state = "string"
                index += 1
                continue
            if ch == "'":
                state = "char"
                index += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return index
            index += 1
        return -1

    def _rust_harness_support_source(self, harness):
        if not isinstance(harness, str):
            return ""
        spans = self._rust_test_block_spans_by_name(harness)
        if not spans:
            return harness
        pieces = []
        cursor = 0
        for _test_name, (start, end, _block) in sorted(spans.items(), key=lambda item: item[1][0]):
            pieces.append(harness[cursor:start])
            cursor = end
        pieces.append(harness[cursor:])
        return "".join(pieces).strip()

    def _rust_import_lines(self, harness):
        if not isinstance(harness, str):
            return []
        first_test = re.search(r"#\s*\[\s*test\s*\]", harness)
        prelude = harness[:first_test.start()] if first_test else harness
        return list(dict.fromkeys(
            line.strip()
            for line in prelude.splitlines()
            if line.strip().startswith(("use ", "extern crate ")) and line.strip().endswith(";")
        ))

    def _current_eligible_behavior_case_ids(self):
        if self._initial_prompt_case_ids:
            return list(self._initial_prompt_case_ids)
        context = self._last_synthesis_context or {}
        return [
            case.get("case_id")
            for case in context.get("source_evidence", {}).get("behavior_cases", [])
            if isinstance(case, dict) and case.get("case_id")
        ]

    def _note_case_conversion_attempts(self, case_ids, stage, outcome, errors=None, count_attempt=True):
        compact_errors = [self._truncate_text(error, max_chars=600) for error in (errors or [])[:5]]
        for case_id in sorted(set(case_ids or [])):
            entry = self._case_conversion_attempts.setdefault(case_id, {
                "attempt_count": 0,
                "attempts": [],
            })
            if count_attempt:
                entry["attempt_count"] += 1
            entry["attempts"].append({
                "stage": stage,
                "outcome": outcome,
                "errors": compact_errors,
            })
            entry["attempts"] = entry["attempts"][-6:]

    def _targeted_adapter_generation_scope(
        self,
        scope,
        alignment_stats,
        inventory,
        iteration,
        batch_size=3,
        behavior_case_attempt_counts=None,
    ):
        missing_cases = list(scope.get("missing_behavior_case_ids") or [])
        if not missing_cases:
            return scope
        batch_size = max(1, int(batch_size or 1))
        behavior_case_attempt_counts = behavior_case_attempt_counts or {}

        case_pool = sorted(
            dict.fromkeys(missing_cases),
            key=lambda case_id: behavior_case_attempt_counts.get(case_id, 0),
        )
        focused_cases = case_pool[: min(batch_size, len(case_pool))]
        focused_case_evidence = self._behavior_case_evidence_for_ids(
            focused_cases,
            max_cases=len(focused_cases),
        )
        case_source_functions = sorted({
            src_uuid
            for case in focused_case_evidence
            for src_uuid in case.get("aligned_source_functions", [])
            if src_uuid
        })

        targeted = dict(scope)
        targeted["targeting_strategy"] = "unattempted_first_eligible_behavior_cases_v1"
        targeted["targeted_missing_behavior_case_count"] = len(focused_cases)
        targeted["targeted_missing_behavior_case_ids"] = focused_cases
        targeted["targeted_case_attempt_counts_before"] = {
            case_id: behavior_case_attempt_counts.get(case_id, 0)
            for case_id in focused_cases
        }
        targeted["previous_generation_feedback"] = self._case_generation_feedback_for_ids(
            focused_cases,
        )
        targeted["targeted_alignment_pairs"] = self._alignment_pairs_for_sources(
            alignment_stats,
            case_source_functions,
        )
        targeted["missing_behavior_case_evidence"] = focused_case_evidence
        return targeted

    def _adapter_coverage_scope(self, alignment_stats, inventory, adapter, replay_plan, compact=False):
        public_eligible_src = set(alignment_stats.get("public_eligible_source_functions", []))
        tested_public_src = self._source_functions_with_test_evidence(
            inventory,
            public_eligible_src,
            require_precise_behavior=True,
        )
        adapter_src = set()
        for operation in adapter.get("public_operations", {}).values():
            if isinstance(operation, dict):
                adapter_src.update(operation.get("source_functions", []) or [])
        replay_plan_summary = replay_plan.get("summary", {})
        planned_src = set(replay_plan_summary.get("validated_aligned_source_function_ids", []))
        missing_src = sorted(tested_public_src - planned_src)
        unplanned_src = sorted(tested_public_src - planned_src)
        behavior_coverage = self._adapter_behavior_case_coverage(adapter)
        scope = {
            "source_functions_with_src_test_evidence_count": len(tested_public_src),
            "adapter_source_function_count": len(adapter_src),
            "validated_replay_plan_source_function_count": len(planned_src),
            "adapter_missing_source_function_count": len(missing_src),
            "adapter_missing_source_functions": missing_src,
            "unplanned_source_function_count": len(unplanned_src),
            "unplanned_source_functions": unplanned_src,
            "replay_plan_alignment_status_counts": replay_plan_summary.get("alignment_status_counts", {}),
            "covered_aligned_pairs": replay_plan_summary.get("covered_aligned_pairs", 0),
            "required_behavior_case_count": behavior_coverage.get("required_behavior_case_count", 0),
            "available_behavior_case_count": behavior_coverage.get("available_behavior_case_count", 0),
            "initial_context_behavior_case_count": behavior_coverage.get("initial_context_behavior_case_count", 0),
            "initial_context_unlisted_behavior_case_count": behavior_coverage.get("initial_context_unlisted_behavior_case_count", 0),
            "unresolved_unlisted_behavior_case_count": behavior_coverage.get("unresolved_unlisted_behavior_case_count", 0),
            "behavior_case_context_truncated": behavior_coverage.get("behavior_case_context_truncated", False),
            "replayed_behavior_case_count": behavior_coverage.get("replayed_behavior_case_count", 0),
            "excluded_behavior_case_count": behavior_coverage.get("excluded_behavior_case_count", 0),
            "missing_behavior_case_count": behavior_coverage.get("missing_behavior_case_count", 0),
            "missing_behavior_case_ids": behavior_coverage.get("missing_behavior_case_ids", []),
            "replayed_behavior_case_ids": behavior_coverage.get("replayed_behavior_case_ids", []),
            "excluded_behavior_case_ids": behavior_coverage.get("excluded_behavior_case_ids", []),
            "accounted_behavior_case_ids": behavior_coverage.get("accounted_behavior_case_ids", []),
        }
        if compact:
            return scope
        scope["missing_alignment_pairs"] = self._alignment_pairs_for_sources(alignment_stats, missing_src)
        scope["missing_source_test_evidence"] = self._source_function_test_evidence(
            inventory,
            set(missing_src),
            max_functions=20,
            max_entries_per_function=3,
            max_chars_per_snippet=1400,
            max_total_chars=26000,
        )
        return scope

    def _alignment_pairs_for_sources(self, alignment_stats, source_uuids):
        source_uuids = set(source_uuids or [])
        pairs = []
        for pair in self._alignment_pairs_by_source(alignment_stats).values():
            if pair.get("src_uuid") not in source_uuids:
                continue
            pairs.append({
                "src_uuid": pair.get("src_uuid"),
                "src_signature": pair.get("src_signature", ""),
                "tgt_uuids": pair.get("tgt_uuids", []),
                "target_signatures": pair.get("target_signatures", []),
                "confidence": pair.get("confidence", ""),
                "is_public_eligible": pair.get("is_public_eligible", False),
            })
        return pairs

    def _alignment_pairs_by_source(self, alignment_stats):
        pairs_by_src = {}
        for pair in alignment_stats.get("pairs", []):
            src_uuid = pair.get("src_uuid")
            if not src_uuid:
                continue
            entry = pairs_by_src.setdefault(src_uuid, {
                "src_uuid": src_uuid,
                "src_signature": pair.get("src_signature", ""),
                "tgt_uuids": [],
                "target_signatures": [],
                "confidence_values": [],
                "is_public_eligible": True,
            })
            if not entry.get("src_signature") and pair.get("src_signature"):
                entry["src_signature"] = pair.get("src_signature")
            if pair.get("confidence") and pair.get("confidence") not in entry["confidence_values"]:
                entry["confidence_values"].append(pair.get("confidence"))
            entry["is_public_eligible"] = bool(entry["is_public_eligible"] and pair.get("is_public_eligible", False))

            signatures_by_uuid = {
                item.get("tgt_uuid"): item
                for item in entry.get("target_signatures", [])
                if item.get("tgt_uuid")
            }
            for tgt_uuid in pair.get("tgt_uuids", []):
                if not tgt_uuid:
                    continue
                if tgt_uuid not in entry["tgt_uuids"]:
                    entry["tgt_uuids"].append(tgt_uuid)
                for signature_item in pair.get("target_signatures", []):
                    if signature_item.get("tgt_uuid") == tgt_uuid:
                        signatures_by_uuid[tgt_uuid] = signature_item
                        break
                else:
                    signatures_by_uuid.setdefault(tgt_uuid, {"tgt_uuid": tgt_uuid, "signature": ""})
            entry["target_signatures"] = [
                signatures_by_uuid.get(tgt_uuid, {"tgt_uuid": tgt_uuid, "signature": ""})
                for tgt_uuid in entry["tgt_uuids"]
            ]

        for entry in pairs_by_src.values():
            entry["confidence"] = ",".join(entry.pop("confidence_values", []))
        return pairs_by_src

    def _build_adapter_case_generation_prompt(
        self,
        adapter,
        inventory,
        alignment_stats,
        scope,
        iteration,
    ):
        scoped_pairs = scope.get("targeted_alignment_pairs", [])
        target_context = self._target_aligned_api_context(scoped_pairs, max_items=30, max_body_chars=180)
        target_public_api_signatures = self._target_public_api_signatures_for_synthesis(scoped_pairs, max_items=24)
        allowed_source_uuids, allowed_target_uuids = self._adapter_case_generation_allowed_uuids(
            scoped_pairs,
            target_context=target_context,
            target_public_api_signatures=target_public_api_signatures,
        )
        repair_context = {
            "iteration": iteration,
            "objective": (
                "Convert every targeted eligible source behavior case into an executable Rust public replay. "
                "Cases that cannot be converted in this attempt must be returned as unresolved_adapter_generation, "
                "not excluded."
            ),
            "preferred_output_schema": "3b.case_results.v2 compact event; Python expands event into operation + trace_event",
            "rules": [
                "Return one 3b.case_results JSON object only.",
                "Prefer adapter_case_generation_version=3b.case_results.v2 with compact event objects.",
                "Do not repeat or modify existing operations, events, or Rust tests.",
                "Process every targeted_behavior_case_id; function coverage alone is not completion.",
                "For every declared source function, include all targets from targeted_alignment_pairs.",
                "Do not invent expected behavior or use target tests/examples as expected behavior evidence.",
                "Do not exclude eligible behavior differences. Replay callable target public APIs and let runtime failures expose differences.",
                "Use only allowed_source_function_uuids_for_this_batch for event.source_functions.",
                "Use only allowed_target_api_uuids_for_this_batch for event.target_functions and Rust public API calls.",
            ],
            "targeted_behavior_case_ids": scope.get("targeted_missing_behavior_case_ids", []),
            "targeted_behavior_cases": scope.get("missing_behavior_case_evidence", []),
            "previous_generation_feedback": scope.get("previous_generation_feedback", {}),
            "targeted_alignment_pairs": scoped_pairs,
            "allowed_source_function_uuids_for_this_batch": sorted(allowed_source_uuids),
            "allowed_target_api_uuids_for_this_batch": sorted(allowed_target_uuids),
            "source_aligned_api_context": self._source_aligned_api_context(scoped_pairs, max_items=30, max_body_chars=220),
            "target_aligned_api_context": target_context,
            "target_api_scope": self._target_api_scope(scoped_pairs),
            "allowed_target_public_api_signatures": target_public_api_signatures,
            "target_crate_import_hint": self._target_crate_import_hint(),
            "rust_integration_test_contract": self._rust_integration_test_contract(),
            "current_adapter_index": self._adapter_state_for_generation_prompt(
                adapter,
                scoped_pairs=scoped_pairs,
                targeted_case_ids=scope.get("targeted_missing_behavior_case_ids", []),
            ),
        }
        return PROMPT_3B_ADAPTER_CASE_GENERATION.format(
            repair_context_json=json.dumps(repair_context, ensure_ascii=False, separators=(",", ":")),
        )

    def _adapter_case_generation_allowed_uuids(
        self,
        scoped_pairs,
        target_context=None,
        target_public_api_signatures=None,
    ):
        allowed_source_uuids = {
            pair.get("src_uuid")
            for pair in scoped_pairs or []
            if isinstance(pair, dict) and pair.get("src_uuid")
        }
        allowed_target_uuids = {
            tgt_uuid
            for pair in scoped_pairs or []
            if isinstance(pair, dict)
            for tgt_uuid in pair.get("tgt_uuids", [])
            if tgt_uuid
        }
        if target_public_api_signatures is None:
            target_public_api_signatures = self._target_public_api_signatures_for_synthesis(scoped_pairs, max_items=24)
        if target_context is None:
            target_context = self._target_aligned_api_context(scoped_pairs, max_items=30, max_body_chars=180)
        allowed_target_uuids.update({
            item.get("uuid")
            for item in target_public_api_signatures or []
            if isinstance(item, dict) and item.get("uuid")
        })
        allowed_target_uuids.update({
            item.get("uuid")
            for item in target_context or []
            if isinstance(item, dict) and item.get("uuid")
        })
        return allowed_source_uuids, allowed_target_uuids

    def _adapter_state_for_generation_prompt(self, adapter, scoped_pairs=None, targeted_case_ids=None):
        """Index existing coverage without resending the complete generated harness."""
        scoped_sources = {
            pair.get("src_uuid")
            for pair in scoped_pairs or []
            if isinstance(pair, dict) and pair.get("src_uuid")
        }
        scoped_targets = {
            tgt_uuid
            for pair in scoped_pairs or []
            if isinstance(pair, dict)
            for tgt_uuid in pair.get("tgt_uuids", [])
            if tgt_uuid
        }
        targeted_case_ids = set(targeted_case_ids or [])
        all_operations = adapter.get("public_operations") or {}
        all_events = adapter.get("trace_events") or []
        operations = []
        selected_operation_names = set()
        for name, operation in all_operations.items():
            if not isinstance(operation, dict):
                continue
            op_sources = set(operation.get("source_functions", []) or [])
            op_targets = set(operation.get("target_functions", []) or [])
            is_relevant = (
                not scoped_sources
                or bool(op_sources & scoped_sources)
                or bool(op_targets & scoped_targets)
            )
            if not is_relevant:
                continue
            selected_operation_names.add(name)
            operations.append({
                "name": name,
                "source_functions": operation.get("source_functions", []),
                "target_functions": operation.get("target_functions", []),
            })
        events = []
        omitted_relevant_events = 0
        for event in all_events:
            if not isinstance(event, dict):
                continue
            event_case_ids = set(event.get("source_case_ids", []) or [])
            is_relevant = (
                event.get("operation") in selected_operation_names
                or bool(event_case_ids & targeted_case_ids)
            )
            if not is_relevant:
                continue
            if len(events) >= 40:
                omitted_relevant_events += 1
                continue
            events.append({
                "id": event.get("id"),
                "operation": event.get("operation"),
                "source_case_ids": event.get("source_case_ids", []),
            })
        exclusions = []
        for exclusion in adapter.get("excluded_behavior_cases") or []:
            if isinstance(exclusion, dict):
                exclusions.append({
                    "case_id": exclusion.get("case_id"),
                    "reason": exclusion.get("reason"),
                })
        return {
            "total_operation_count": len(all_operations),
            "total_event_count": len(all_events),
            "relevant_operation_count": len(operations),
            "relevant_event_count": len(events),
            "omitted_relevant_event_count": omitted_relevant_events,
            "operation_index": operations,
            "event_index": events,
            "exclusion_index": exclusions,
            "rust_harness_present": bool(str(adapter.get("rust_test_harness", "")).strip()),
            "instruction": (
                "This is only a compact relevant index. The full adapter remains in Python and will be merged "
                "with your additive patch. Use unique operation and test ids."
            ),
        }

    def _compact_behavior_cases_for_prompt(self, behavior_cases, max_cases=120, include_snippets=False):
        compact = []
        for case in behavior_cases[:max_cases] if isinstance(behavior_cases, list) else []:
            if not isinstance(case, dict):
                continue
            assertions = []
            for assertion in case.get("assertions", [])[:4]:
                if not isinstance(assertion, dict):
                    continue
                assertions.append(self._compact_report_dict({
                    "line": assertion.get("line"),
                    "macro": assertion.get("macro", ""),
                    "expression": assertion.get("expression", assertion.get("text", ""))[:320],
                    "expected_behavior_hint": self._clean_expected_behavior_text(
                        assertion.get(
                            "expected_behavior_hint",
                            assertion.get("oracle_hint", ""),
                        )
                    ),
                    "literal_samples": assertion.get("literal_samples", [])[:8],
                    "mentions_aligned_functions": assertion.get("mentions_aligned_functions", False),
                }))
            item = {
                "case_id": case.get("case_id", ""),
                "name": case.get("name", ""),
                "path": case.get("path", ""),
                "start_line": case.get("start_line"),
                "aligned_source_functions": case.get("aligned_source_functions", []),
                "call_names": case.get("call_names", []),
                "non_public_aligned_call_names": case.get("non_public_aligned_call_names", []),
                "has_mixed_public_internal_calls": case.get("has_mixed_public_internal_calls", False),
                "eligibility_status": case.get("eligibility_status", ""),
                "required_internal_public_substitutions": case.get(
                    "required_internal_public_substitutions",
                    [],
                ),
                "assertions": assertions,
                "literal_samples": case.get("literal_samples", [])[:10],
            }
            if include_snippets:
                item["relevant_snippet"] = case.get("relevant_snippet", "")[:700]
            compact.append(self._compact_report_dict(item))
        return compact

    def _behavior_case_evidence_for_ids(self, case_ids, max_cases=5):
        detail_index = getattr(self, "_last_behavior_case_details", {}) or {}
        if detail_index:
            selected = [
                detail_index[case_id]
                for case_id in case_ids or []
                if case_id in detail_index
            ]
            return self._compact_behavior_cases_for_prompt(selected, max_cases=max_cases, include_snippets=True)

        context = self._last_synthesis_context or {}
        behavior_cases = context.get("source_evidence", {}).get("behavior_cases", [])
        wanted = set(case_ids or [])
        selected = [
            case for case in behavior_cases
            if isinstance(case, dict) and case.get("case_id") in wanted
        ]
        return self._compact_behavior_cases_for_prompt(selected, max_cases=max_cases, include_snippets=True)

    def _read_synthesis_attempts(self, artifacts_path):
        if not artifacts_path:
            return []
        path = artifacts_path / "adapter_synthesis_attempts.json"
        if not path.exists():
            return []
        try:
            data = self._load_json(path)
        except (OSError, json.JSONDecodeError):
            return []
        return list(data.get("attempts", []))

    def _replay_repair_batch_size(self):
        # Keep repair prompts small enough that the model returns structured
        # replacements instead of an empty/prose-only patch. With the default
        # three attempts this still covers the common 20-30 event infra bursts.
        return 12

    def _build_replay_repair_prompt(self, adapter, replay_plan, replay_result, failed_test_context=None):
        replay_summary = replay_result.get("summary", {})
        generated_harness = self._rust_inline_harness_from_adapter(adapter)
        if failed_test_context is None:
            failed_test_context = self._infrastructure_failed_test_context(
                generated_harness,
                replay_result,
                max_tests=self._replay_repair_batch_size(),
            )
        failed_adapter_context = self._repair_failed_event_adapter_context(
            adapter,
            failed_test_context,
        )
        required_test_names = [
            item.get("test_name") or item.get("event_id")
            for item in failed_test_context or []
            if isinstance(item, dict) and (item.get("test_name") or item.get("event_id"))
        ]
        repair_context = {
            "required_output_contract": {
                "patch_version": "3b.replay_repair_patch.v2",
                "required_test_names": required_test_names,
                "minimum_rust_test_replacements": 1,
                "rust_test_replacements_rule": (
                    "Return at least one replacement object. Each replacement.test_name must be one of "
                    "required_test_names and each replacement.rust_test_body must be a complete #[test] function."
                ),
            },
            "rust_harness_support_source": self._rust_harness_support_source(generated_harness),
            "replay_plan_summary": replay_plan.get("summary", {}),
            "replay_status": replay_result.get("status"),
            "replay_reason": replay_result.get("reason", ""),
            "generated_test_file": replay_summary.get("generated_test_file", ""),
            "failed_event_adapter_context": failed_adapter_context,
            "infrastructure_failed_tests": failed_test_context,
            "failure_reason": self._truncate_text(replay_summary.get("failure_reason", ""), max_chars=6000),
            "compiler_error_test_context": self._compiler_error_test_context(
                generated_harness,
                replay_summary.get("stderr_tail", ""),
            ),
            "rust_integration_test_contract": self._rust_integration_test_contract(),
            "target_repair_context": self._target_repair_context(
                adapter,
                target_functions=failed_adapter_context.get("target_functions", []),
            ),
        }
        return PROMPT_3B_REPLAY_REPAIR.format(
            repair_context_json=json.dumps(repair_context, ensure_ascii=False, separators=(",", ":")),
        )

    def _repair_failed_event_adapter_context(self, adapter, failed_test_context):
        failed_event_ids = {
            item.get("event_id") or item.get("test_name")
            for item in failed_test_context or []
            if isinstance(item, dict) and (item.get("event_id") or item.get("test_name"))
        }
        all_events = [
            event for event in adapter.get("trace_events", [])
            if isinstance(event, dict) and event.get("id") in failed_event_ids
        ]
        operation_names = {
            event.get("operation")
            for event in all_events
            if event.get("operation")
        }
        operations = []
        target_functions = set()
        for name, operation in (adapter.get("public_operations") or {}).items():
            if name not in operation_names or not isinstance(operation, dict):
                continue
            op_target_functions = operation.get("target_functions", []) or []
            target_functions.update(op_target_functions)
            operations.append(self._compact_report_dict({
                "name": name,
                "description": operation.get("description", ""),
                "source_functions": operation.get("source_functions", []),
                "target_functions": op_target_functions,
                "normalization": operation.get("normalization", ""),
            }))

        events = []
        for event in all_events:
            events.append(self._compact_report_dict({
                "id": event.get("id"),
                "operation": event.get("operation"),
                "source_case_ids": event.get("source_case_ids", []),
                "input": event.get("input", {}),
                "expected": event.get("expected", {}),
                "expected_behavior_source": self._expected_behavior_source(event),
                "expected_behavior_confidence": self._expected_behavior_confidence(event),
                "evidence": event.get("evidence", ""),
            }))

        return {
            "failed_event_ids": sorted(failed_event_ids),
            "operations": operations,
            "trace_events": events,
            "target_functions": sorted(target_functions),
            "instruction": (
                "This is the adapter subset for infrastructure-failed tests only. "
                "Do not change expected behavior; repair Rust API usage/import/build issues."
            ),
        }

    def _merge_replay_repair_patch(self, current_adapter, candidate):
        candidate = self._normalize_replay_repair_candidate(candidate)
        patch_version = candidate.get("replay_repair_patch_version")
        if patch_version == "3b.replay_repair_patch.v2":
            repaired = json.loads(json.dumps(current_adapter))
            current_harness = self._rust_inline_harness_from_adapter(current_adapter)
            repaired["rust_test_harness"] = self._apply_replay_repair_patch_v2(
                current_harness,
                candidate,
            )
            return repaired
        if patch_version != "3b.replay_repair_patch.v1":
            return candidate
        harness = candidate.get("rust_test_harness_replacement")
        if not isinstance(harness, str) or not harness.strip():
            raise ValueError("replay repair patch requires rust_test_harness_replacement")
        repaired = json.loads(json.dumps(current_adapter))
        repaired["rust_test_harness"] = self._sanitize_rust_harness(harness)
        return repaired

    def _normalize_replay_repair_candidate(self, candidate):
        if not isinstance(candidate, dict):
            return candidate
        normalized = json.loads(json.dumps(candidate))
        patch_version = normalized.get("replay_repair_patch_version")

        replacements = normalized.get("rust_test_replacements")
        if replacements is None:
            replacements = (
                normalized.get("test_replacements")
                or normalized.get("replacements")
                or normalized.get("tests")
                or normalized.get("rust_tests")
            )
        if isinstance(replacements, dict):
            replacements = [
                {"test_name": test_name, "rust_test_body": body}
                for test_name, body in replacements.items()
            ]
        if isinstance(replacements, list):
            normalized["rust_test_replacements"] = replacements

        if not normalized.get("rust_test_replacements"):
            test_name = normalized.get("test_name") or normalized.get("event_id")
            body = (
                normalized.get("rust_test_body")
                or normalized.get("test_body")
                or normalized.get("replacement")
            )
            if isinstance(test_name, str) and isinstance(body, str):
                normalized["rust_test_replacements"] = [{
                    "test_name": test_name,
                    "rust_test_body": body,
                }]

        if patch_version is None and normalized.get("rust_test_replacements"):
            normalized["replay_repair_patch_version"] = "3b.replay_repair_patch.v2"
        return normalized

    def _apply_replay_repair_patch_v2(self, current_harness, patch):
        replacements = patch.get("rust_test_replacements", [])
        if not isinstance(replacements, list) or not replacements:
            raise ValueError("replay repair patch v2 requires non-empty rust_test_replacements")
        spans = self._rust_test_block_spans_by_name(current_harness)
        if not spans:
            raise ValueError("current Rust harness has no replaceable #[test] functions")

        replacement_by_name = {}
        for item in replacements:
            if not isinstance(item, dict):
                raise ValueError("rust_test_replacements items must be objects")
            test_name = item.get("test_name")
            body = item.get("rust_test_body")
            if not isinstance(test_name, str) or not test_name.strip():
                raise ValueError("rust_test_replacements item missing test_name")
            test_name = test_name.strip()
            if test_name not in spans:
                raise ValueError(f"rust_test_replacements references unknown test_name: {test_name}")
            if not isinstance(body, str) or not body.strip():
                raise ValueError(f"rust_test_replacements[{test_name}] missing rust_test_body")
            replacement_by_name[test_name] = self._normalize_case_rust_test(body, test_name).strip()

        support_replacement = patch.get("shared_support_source_replacement")
        if isinstance(support_replacement, str) and support_replacement.strip():
            support_source = self._strip_markdown_fence(support_replacement).strip() + "\n\n"
            blocks = []
            for test_name, (start, end, original_block) in sorted(spans.items(), key=lambda item: item[1][0]):
                blocks.append(replacement_by_name.get(test_name, original_block.strip()))
            merged = support_source + "\n\n".join(blocks) + "\n"
            return self._sanitize_rust_harness(merged)

        pieces = []
        cursor = 0
        for test_name, (start, end, original_block) in sorted(spans.items(), key=lambda item: item[1][0]):
            pieces.append(current_harness[cursor:start])
            pieces.append(replacement_by_name.get(test_name, original_block).rstrip())
            cursor = end
        pieces.append(current_harness[cursor:])
        return self._sanitize_rust_harness("".join(pieces))

    def _target_repair_context(self, adapter, target_functions=None):
        if target_functions is None:
            target_functions = sorted({
                target
                for operation in (adapter.get("public_operations") or {}).values()
                if isinstance(operation, dict)
                for target in operation.get("target_functions", [])
                if target
            })
        else:
            target_functions = sorted({target for target in target_functions if target})
        scoped_pairs = [{"tgt_uuids": target_functions}]
        return {
            "adapter_declared_target_functions": target_functions,
            "target_crate_import_hint": self._target_crate_import_hint(),
            "rust_integration_test_contract": self._rust_integration_test_contract(),
            "target_public_api_signatures": self._target_public_api_signatures_for_synthesis(
                scoped_pairs,
                max_items=100,
            ),
            "target_aligned_api_context": self._target_aligned_api_context(
                scoped_pairs,
                max_items=80,
                max_body_chars=700,
            ),
        }

    def _compiler_error_test_context(self, harness, stderr, max_locations=12, max_tests=8):
        if not isinstance(harness, str) or not harness.strip() or not isinstance(stderr, str):
            return {
                "error_locations": [],
                "affected_tests": [],
                "note": "No compiler line mapping was available.",
            }
        line_refs = []
        for match in re.finditer(r"-->\s+[^\n]*cp2rs_3b_public\.rs:(\d+):(\d+)", stderr):
            item = {"line": int(match.group(1)), "column": int(match.group(2))}
            if item not in line_refs:
                line_refs.append(item)
            if len(line_refs) >= max_locations:
                break

        test_ranges = self._rust_test_line_ranges(harness)
        lines = harness.splitlines()
        affected = {}
        for ref in line_refs:
            test = self._test_range_for_line(test_ranges, ref["line"])
            if not test:
                continue
            name = test["name"]
            affected.setdefault(name, {
                "test_name": name,
                "start_line": test["start_line"],
                "end_line": test["end_line"],
                "error_lines": [],
            })
            affected[name]["error_lines"].append(ref)

        affected_tests = []
        for item in list(affected.values())[:max_tests]:
            start = max(1, item["start_line"])
            end = min(len(lines), item["end_line"])
            item["test_source_excerpt"] = "\n".join(lines[start - 1:end])[:4000]
            affected_tests.append(item)

        return {
            "error_locations": line_refs,
            "affected_tests": affected_tests,
            "note": (
                "Line numbers are mapped from compiler diagnostics to generated Rust #[test] functions. "
                "Use this to repair relevant test fragments or shared imports without changing expected behavior."
            ),
        }

    def _infrastructure_failed_test_context(self, harness, replay_result, max_tests=16):
        if not isinstance(harness, str):
            harness = ""
        blocks = self._rust_test_blocks_by_name(harness)
        infra_failures = (
            (replay_result.get("summary", {}) or {}).get("per_event_infrastructure_failures", [])
            if isinstance(replay_result, dict)
            else []
        )
        if not infra_failures and isinstance(replay_result, dict) and replay_result.get("status") == "infrastructure_failed":
            compiler_context = self._compiler_error_test_context(
                harness,
                (replay_result.get("summary", {}) or {}).get("stderr_tail", ""),
            )
            affected = []
            for item in compiler_context.get("affected_tests", [])[:max_tests]:
                test_name = item.get("test_name", "")
                affected.append(self._compact_report_dict({
                    "test_name": test_name,
                    "event_id": test_name,
                    "test_source": blocks.get(test_name, item.get("test_source_excerpt", "")),
                    "stderr_tail": (replay_result.get("summary", {}) or {}).get("stderr_tail", "")[-4000:],
                    "stdout_tail": (replay_result.get("summary", {}) or {}).get("stdout_tail", "")[-2000:],
                }))
            return affected

        context = []
        for item in infra_failures[:max_tests]:
            if not isinstance(item, dict):
                continue
            test_name = item.get("test_name") or item.get("event_id") or ""
            context.append(self._compact_report_dict({
                "test_name": test_name,
                "event_id": item.get("event_id", test_name),
                "operation": item.get("operation", ""),
                "source_case_ids": item.get("source_case_ids", []),
                "test_source": blocks.get(test_name, ""),
                "command": " ".join(item.get("command", [])) if isinstance(item.get("command"), list) else item.get("command", ""),
                "returncode": item.get("returncode"),
                "stdout_tail": self._truncate_text(item.get("stdout_tail", ""), max_chars=3000),
                "stderr_tail": self._truncate_text(item.get("stderr_tail", ""), max_chars=5000),
                "failure_reason": item.get("failure_reason", ""),
            }))
        return context

    def _rust_test_line_ranges(self, harness):
        if not isinstance(harness, str):
            return []
        starts = list(re.finditer(
            r"#\s*\[\s*test\s*\]\s*(?:\n\s*#\s*\[[^\]]+\]\s*)*\n?\s*fn\s+([A-Za-z_]\w*)\s*\(",
            harness,
        ))
        ranges = []
        for index, match in enumerate(starts):
            start_pos = match.start()
            end_pos = starts[index + 1].start() if index + 1 < len(starts) else len(harness)
            ranges.append({
                "name": match.group(1),
                "start_line": harness[:start_pos].count("\n") + 1,
                "end_line": harness[:end_pos].count("\n") + 1,
            })
        return ranges

    def _test_range_for_line(self, test_ranges, line):
        for item in test_ranges:
            if item["start_line"] <= line <= item["end_line"]:
                return item
        return None

    def _truncate_text(self, text, max_chars=12000):
        if not isinstance(text, str):
            text = "" if text is None else str(text)
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        head_chars = max_chars // 2
        tail_chars = max_chars - head_chars
        return (
            text[:head_chars]
            + f"\n...<truncated {len(text) - max_chars} chars>...\n"
            + text[-tail_chars:]
        )

    def _validate_synthesized_adapter(self, adapter):
        errors = []
        allowed_source_uuids = self._synthesis_scoped_source_uuids()
        known_source_uuids = self._synthesis_known_source_uuids()
        allowed_target_uuids = self._synthesis_target_public_uuids()
        expected_targets_by_source = self._synthesis_expected_targets_by_source()
        context = self._last_synthesis_context or {}
        behavior_cases = context.get("source_evidence", {}).get("behavior_cases", [])
        has_behavior_case_obligations = isinstance(behavior_cases, list) and bool(behavior_cases)
        if adapter.get("target_language") != "rust":
            errors.append("target_language must be rust for v1 synthesis")
        if adapter.get("recorder") != "adapter_declared_trace_events_v1":
            errors.append("recorder must be adapter_declared_trace_events_v1")
        if adapter.get("replay_generator") != "rust_inline_harness_v1":
            errors.append("replay_generator must be rust_inline_harness_v1")
        operations = adapter.get("public_operations")
        if not isinstance(operations, dict) or not operations:
            errors.append("public_operations must be a non-empty object")
        events = adapter.get("trace_events")
        if not isinstance(events, list) or not events:
            errors.append("trace_events must be a non-empty list")
        target_replay_harness = adapter.get("target_replay_harness", {})
        if not isinstance(target_replay_harness, dict):
            target_replay_harness = {}
        harness = adapter.get("rust_test_harness") or target_replay_harness.get("rust_test_file", "")
        test_names = self._extract_rust_test_function_names(harness) if isinstance(harness, str) else []
        if not isinstance(harness, str) or "#[test]" not in harness:
            errors.append("rust_test_harness must be Rust source containing at least one #[test]")
        elif isinstance(events, list) and events:
            test_count = len(re.findall(r"#\s*\[\s*test\s*\]", harness))
            if test_count > len(events):
                errors.append(
                    "rust_test_harness defines more #[test] functions than trace_events; "
                    "remove undeclared tests or declare matching operations/trace_events"
                )
            event_ids = [
                event.get("id")
                for event in events
                if isinstance(event, dict) and event.get("id")
            ]
            duplicate_event_ids = sorted({event_id for event_id in event_ids if event_ids.count(event_id) > 1})
            if duplicate_event_ids:
                errors.append(f"trace_events contain duplicate ids: {duplicate_event_ids}")
            for index, event_id in enumerate(event_ids):
                if not self._is_rust_identifier(event_id):
                    errors.append(f"trace_events[{index}].id must be a valid Rust test function identifier")
            missing_tests = sorted(set(event_ids) - set(test_names))
            extra_tests = sorted(set(test_names) - set(event_ids))
            if missing_tests:
                errors.append(
                    "rust_test_harness must define one #[test] fn for every trace_events[].id; "
                    f"missing tests: {missing_tests[:10]}"
                )
            if extra_tests:
                errors.append(
                    "rust_test_harness contains #[test] functions without matching trace_events[].id; "
                    f"extra tests: {extra_tests[:10]}"
                )
        if isinstance(operations, dict) and isinstance(events, list):
            operation_names = set(operations.keys())
            for index, event in enumerate(events):
                if not isinstance(event, dict):
                    errors.append(f"trace_events[{index}] must be an object")
                    continue
                operation = event.get("operation")
                if operation not in operation_names:
                    errors.append(f"trace_events[{index}].operation is missing from public_operations")
                op_for_event = operations.get(operation, {}) if operation in operation_names else {}
                event_source_functions = op_for_event.get("source_functions", []) if isinstance(op_for_event, dict) else []
                event_has_l1_source = not allowed_source_uuids or bool(set(event_source_functions or []) & allowed_source_uuids)
                if not event.get("evidence"):
                    if event_has_l1_source:
                        errors.append(f"trace_events[{index}].evidence must cite source test evidence")
                if not event.get("expected"):
                    errors.append(f"trace_events[{index}].expected must describe observable behavior")
                source_case_ids = event.get("source_case_ids", [])
                if source_case_ids and not isinstance(source_case_ids, list):
                    errors.append(f"trace_events[{index}].source_case_ids must be a list when present")
                elif has_behavior_case_obligations and not source_case_ids:
                    errors.append(
                        f"trace_events[{index}].source_case_ids must list covered source_evidence.behavior_cases; "
                        "events without source_case_ids do not count as behavior coverage"
                    )
                for case_id in source_case_ids if isinstance(source_case_ids, list) else []:
                    case = next(
                        (
                            item for item in behavior_cases
                            if isinstance(item, dict) and item.get("case_id") == case_id
                        ),
                        {},
                    )
                    required_substitutions = case.get("required_internal_public_substitutions", [])
                    required_targets = {
                        target_uuid
                        for substitution in required_substitutions
                        if isinstance(substitution, dict)
                        for target_uuid in substitution.get("target_public_functions", [])
                        if target_uuid
                    }
                    declared_targets = set(op_for_event.get("target_functions", [])) if isinstance(op_for_event, dict) else set()
                    missing_required_targets = sorted(required_targets - declared_targets)
                    if missing_required_targets:
                        errors.append(
                            f"trace_events[{index}] case {case_id} requires target public substitutions missing "
                            f"from operation target_functions: {missing_required_targets}"
                        )
                expected_behavior_confidence = (
                    event.get("expected_behavior_confidence")
                    or event.get("oracle_confidence")
                    or "medium"
                )
                if expected_behavior_confidence not in {"high", "medium", "low"}:
                    errors.append(
                        f"trace_events[{index}].expected_behavior_confidence must be one of high|medium|low"
                    )
                if not (event.get("expected_behavior_source") or event.get("oracle_source")):
                    errors.append(f"trace_events[{index}].expected_behavior_source is required")
            for name, op in operations.items():
                if not isinstance(op, dict):
                    errors.append(f"public_operations.{name} must be an object")
                    continue
                source_functions = op.get("source_functions")
                target_functions = op.get("target_functions")
                if not isinstance(source_functions, list) or not source_functions:
                    errors.append(f"public_operations.{name}.source_functions must be non-empty")
                if not isinstance(target_functions, list) or not target_functions:
                    errors.append(f"public_operations.{name}.target_functions must be non-empty")
                if not op.get("normalization"):
                    errors.append(f"public_operations.{name}.normalization must explain observable behavior")
                if known_source_uuids:
                    unknown_sources = sorted(set(source_functions or []) - known_source_uuids)
                    if unknown_sources:
                        errors.append(
                            f"public_operations.{name}.source_functions include unknown source functions: "
                            f"{unknown_sources[:10]}"
                        )
                if allowed_source_uuids and source_functions:
                    outside_l1_sources = sorted(set(source_functions) - allowed_source_uuids)
                    if outside_l1_sources:
                        errors.append(
                            f"public_operations.{name}.source_functions are outside the eligible L1 scope: "
                            f"{outside_l1_sources[:20]}"
                        )
                if allowed_target_uuids:
                    unknown_targets = sorted(set(target_functions or []) - allowed_target_uuids)
                    if unknown_targets:
                        errors.append(
                            f"public_operations.{name}.target_functions include unknown/non-public target APIs: "
                            f"{unknown_targets[:10]}"
                        )
                if expected_targets_by_source and source_functions and target_functions:
                    declared_targets = set(target_functions)
                    missing_expected_targets = []
                    for source_function in source_functions:
                        for expected_target in sorted(expected_targets_by_source.get(source_function, set())):
                            if expected_target not in declared_targets:
                                missing_expected_targets.append({
                                    "src_uuid": source_function,
                                    "missing_tgt_uuid": expected_target,
                                })
                    if missing_expected_targets:
                        errors.append(
                            f"public_operations.{name}.target_functions omit 3A target functions required by "
                            f"declared source_functions: {missing_expected_targets[:10]}"
                        )
            behavior_coverage = self._adapter_behavior_case_coverage(adapter)
            adapter["_behavior_case_coverage"] = behavior_coverage
            if behavior_coverage.get("unknown_source_case_ids"):
                errors.append(
                    "trace_events/excluded_behavior_cases reference unknown source case ids: "
                    f"{behavior_coverage.get('unknown_source_case_ids', [])[:20]}"
                )
            if behavior_coverage.get("invalid_excluded_behavior_cases"):
                errors.append(
                    "excluded_behavior_cases contain invalid or unsupported exclusions: "
                    f"{behavior_coverage.get('invalid_excluded_behavior_cases', [])[:20]}"
                )
            if behavior_coverage.get("invalid_event_case_bindings"):
                errors.append(
                    "trace_events contain invalid source behavior-case bindings: "
                    f"{behavior_coverage.get('invalid_event_case_bindings', [])[:20]}"
                )
            if behavior_coverage.get("replayed_and_excluded_case_ids"):
                errors.append(
                    "source behavior cases cannot be both replayed and excluded: "
                    f"{behavior_coverage.get('replayed_and_excluded_case_ids', [])[:20]}"
                )
            # Missing behavior cases are an explicit generation outcome, not
            # an adapter schema error.
        return errors

    def _adapter_behavior_case_coverage(self, adapter):
        context = self._last_synthesis_context or {}
        behavior_cases = context.get("source_evidence", {}).get("behavior_cases", [])
        if not isinstance(behavior_cases, list):
            behavior_cases = []
        source_evidence = context.get("source_evidence", {}) if isinstance(context.get("source_evidence", {}), dict) else {}
        source_summary = source_evidence.get("summary", {}) if isinstance(source_evidence.get("summary", {}), dict) else {}
        quality_checks = source_evidence.get("quality_checks", {}) if isinstance(source_evidence.get("quality_checks", {}), dict) else {}
        available_behavior_case_count = int(
            source_summary.get(
                "available_behavior_case_candidates",
                quality_checks.get("available_behavior_case_candidates", len(behavior_cases)),
            )
            or 0
        )
        context_case_by_id = {
            case.get("case_id"): case
            for case in behavior_cases
            if isinstance(case, dict) and case.get("case_id")
        }
        all_case_details = getattr(self, "_last_behavior_case_details", {}) or {}
        case_by_id = {
            case_id: case
            for case_id, case in all_case_details.items()
            if case_id and isinstance(case, dict)
        } or context_case_by_id
        required_ids = set(case_by_id)
        context_ids = set(context_case_by_id)
        available_behavior_case_count = max(available_behavior_case_count, len(required_ids))
        operations = adapter.get("public_operations", {}) if isinstance(adapter.get("public_operations"), dict) else {}
        trace_events = adapter.get("trace_events", []) if isinstance(adapter.get("trace_events"), list) else []
        covered_ids = set()
        unknown_ids = set()
        events_without_source_case_ids = []
        invalid_event_case_bindings = []

        for event_index, event in enumerate(trace_events):
            if not isinstance(event, dict):
                continue
            explicit_ids = event.get("source_case_ids", [])
            if not isinstance(explicit_ids, list) or not explicit_ids:
                event_id = event.get("id")
                if event_id:
                    events_without_source_case_ids.append(event_id)
                continue
            event_id = event.get("id", "")
            operation = operations.get(event.get("operation"), {})
            operation_sources = set(operation.get("source_functions", [])) if isinstance(operation, dict) else set()
            if len(explicit_ids) != len(set(explicit_ids)):
                invalid_event_case_bindings.append({
                    "event_index": event_index,
                    "event_id": event_id,
                    "reason": "duplicate_source_case_ids",
                })
                continue
            if len(explicit_ids) > 1 and not str(event.get("case_grouping_rationale", "")).strip():
                invalid_event_case_bindings.append({
                    "event_index": event_index,
                    "event_id": event_id,
                    "source_case_ids": explicit_ids,
                    "reason": "multiple_cases_require_case_grouping_rationale",
                })
                continue
            for case_id in explicit_ids:
                if case_id not in required_ids:
                    if case_id:
                        unknown_ids.add(case_id)
                    continue
                case_sources = set(case_by_id.get(case_id, {}).get("aligned_source_functions", []))
                if not operation_sources or not case_sources or not (operation_sources & case_sources):
                    invalid_event_case_bindings.append({
                        "event_index": event_index,
                        "event_id": event_id,
                        "case_id": case_id,
                        "reason": "case_source_functions_do_not_match_operation",
                        "case_source_functions": sorted(case_sources),
                        "operation_source_functions": sorted(operation_sources),
                    })
                    continue
                if case_id:
                    covered_ids.add(case_id)

        excluded_ids = set()
        invalid_exclusions = []
        allowed_exclusion_reasons = self._behavior_case_exclusion_reasons()
        expected_targets_by_source = self._synthesis_expected_targets_by_source()
        public_target_uuids = self._synthesis_target_public_uuids()
        excluded_cases = adapter.get("excluded_behavior_cases", [])
        if isinstance(excluded_cases, list):
            for index, item in enumerate(excluded_cases):
                if not isinstance(item, dict):
                    invalid_exclusions.append({"index": index, "reason": "entry_must_be_object"})
                    continue
                case_id = item.get("case_id")
                exclusion_reason = item.get("reason")
                details = str(item.get("details", "")).strip()
                if not case_id:
                    invalid_exclusions.append({"index": index, "reason": "case_id_missing"})
                    continue
                if exclusion_reason not in allowed_exclusion_reasons:
                    invalid_exclusions.append({
                        "index": index,
                        "case_id": case_id,
                        "reason": "unsupported_exclusion_reason",
                        "provided_reason": exclusion_reason,
                    })
                    continue
                if not details:
                    invalid_exclusions.append({
                        "index": index,
                        "case_id": case_id,
                        "reason": "details_missing",
                    })
                    continue
                if exclusion_reason == "target_missing_public_api" and case_id in required_ids:
                    case_sources = set(case_by_id.get(case_id, {}).get("aligned_source_functions", []))
                    aligned_public_targets = {
                        target_uuid
                        for source_uuid in case_sources
                        for target_uuid in expected_targets_by_source.get(source_uuid, set())
                        if target_uuid in public_target_uuids
                    }
                    if aligned_public_targets:
                        invalid_exclusions.append({
                            "index": index,
                            "case_id": case_id,
                            "reason": "aligned_target_public_api_available",
                            "aligned_public_target_functions": sorted(aligned_public_targets),
                            "policy": (
                                "A callable aligned public target must be replayed even when its behavior or "
                                "feature range differs from the source."
                            ),
                        })
                        continue
                if case_id in excluded_ids:
                    invalid_exclusions.append({
                        "index": index,
                        "case_id": case_id,
                        "reason": "duplicate_exclusion",
                    })
                    continue
                if case_id in required_ids:
                    excluded_ids.add(case_id)
                elif case_id:
                    unknown_ids.add(case_id)

        replayed_and_excluded_ids = sorted(covered_ids & excluded_ids)
        excluded_ids -= covered_ids
        missing_id_set = required_ids - covered_ids - excluded_ids
        missing_ids = sorted(missing_id_set)
        initial_context_unlisted_ids = required_ids - context_ids
        unresolved_unlisted_ids = sorted(initial_context_unlisted_ids & missing_id_set)
        return {
            "required_behavior_case_count": len(required_ids),
            "available_behavior_case_count": available_behavior_case_count,
            "initial_context_behavior_case_count": len(context_ids),
            "initial_context_unlisted_behavior_case_count": len(initial_context_unlisted_ids),
            "unresolved_unlisted_behavior_case_count": len(unresolved_unlisted_ids),
            "unresolved_unlisted_behavior_case_ids": unresolved_unlisted_ids,
            "behavior_case_context_truncated": bool(initial_context_unlisted_ids),
            "replayed_behavior_case_count": len(covered_ids),
            "replayed_behavior_case_ids": sorted(covered_ids),
            "excluded_behavior_case_count": len(excluded_ids),
            "excluded_behavior_case_ids": sorted(excluded_ids),
            "accounted_behavior_case_ids": sorted(covered_ids | excluded_ids),
            "missing_behavior_case_count": len(missing_ids),
            "missing_behavior_case_ids": missing_ids,
            "unknown_source_case_ids": sorted(unknown_ids),
            "replayed_and_excluded_case_ids": replayed_and_excluded_ids,
            "invalid_event_case_bindings": invalid_event_case_bindings,
            "invalid_excluded_behavior_cases": invalid_exclusions,
            "events_without_source_case_ids": sorted(events_without_source_case_ids),
            "event_source_case_id_policy": (
                "Only explicit trace_events[].source_case_ids count as behavior-case replay coverage. "
                "Function-name fallback is intentionally not used because one function can have many source test behavior variants."
            ),
        }

    def _behavior_case_exclusion_reasons(self):
        return {
            "target_missing_public_api",
            "cannot_public_replay_internal_state_transition",
            "expected_behavior_not_precise",
            "requires_function_boundary_or_adapter_wrapper",
            "source_test_requires_device",
        }

    def _synthesis_scoped_source_uuids(self):
        context = self._last_synthesis_context or {}
        scope = context.get("alignment_scope", {})
        return {
            pair.get("src_uuid")
            for pair in scope.get("public_eligible_pairs_with_src_test_evidence", [])
            if pair.get("src_uuid")
        }

    def _synthesis_known_source_uuids(self):
        try:
            return set(self._index_functions(self.src_db_path, repo_path=self.src_repo_path))
        except Exception:
            return set()

    def _synthesis_expected_targets_by_source(self):
        context = self._last_synthesis_context or {}
        scope = context.get("alignment_scope", {})
        mapping = {}
        for pair in scope.get("public_eligible_pairs_with_src_test_evidence", []):
            src_uuid = pair.get("src_uuid")
            if not src_uuid:
                continue
            mapping.setdefault(src_uuid, set()).update(
                tgt_uuid
                for tgt_uuid in pair.get("tgt_uuids", [])
                if tgt_uuid
            )
        return mapping

    def _synthesis_target_public_uuids(self):
        return {
            item.get("uuid")
            for item in self._target_public_api_signatures(max_items=None)
            if item.get("uuid")
        }

    def _synthesis_source_evidence_tokens(self):
        context = self._last_synthesis_context or {}
        tokens = set()

        def add_token(value):
            if not isinstance(value, str) or not value:
                return
            tokens.add(value)

        def add_path(value):
            if not isinstance(value, str) or not value:
                return
            tokens.add(value)
            tokens.add(Path(value).name)

        source_evidence = context.get("source_evidence", {})
        for item in source_evidence.get("behavior_cases", []):
            add_path(item.get("path"))
            add_token(item.get("case_id"))
            add_token(item.get("name"))
        for item in source_evidence.get("fixtures", []):
            add_path(item.get("path"))
            add_token(item.get("name"))
        for item in source_evidence.get("test_files", []):
            add_path(item.get("path"))
            add_token(item.get("framework"))
        for item in source_evidence.get("function_index", {}).values():
            for path in item.get("evidence_paths", []):
                add_path(path)
            for ref in item.get("case_refs", []):
                add_token(ref.get("case_id"))
                add_token(ref.get("name"))
                add_path(ref.get("path"))
            for assertion in item.get("direct_assertions", []):
                add_path(assertion.get("path"))
        for item in context.get("source_test_evidence", []):
            add_path(item.get("path"))
            add_token(item.get("name"))
        for item in context.get("source_test_case_evidence", []):
            add_path(item.get("path"))
            add_token(item.get("case_id"))
            add_token(item.get("name"))
        for item in context.get("source_assertion_evidence", []):
            add_path(item.get("path"))
            add_token(item.get("case_id"))
            add_token(item.get("name"))
        for entries in context.get("source_function_test_evidence", {}).values():
            for item in entries:
                add_path(item.get("path"))
                add_token(item.get("case_id"))
                add_token(item.get("name"))
        return tokens

    def _evidence_mentions_known_token(self, evidence, known_tokens):
        if not isinstance(evidence, str) or not evidence:
            return False
        evidence_lower = evidence.lower()
        return any(token.lower() in evidence_lower for token in known_tokens if token)

    def _uuid_leaf_name(self, uuid_value):
        if not isinstance(uuid_value, str) or not uuid_value:
            return ""
        return strip_overload_suffix(uuid_value.rsplit("::", 1)[-1])

    def _rust_code_mentions_identifier(self, code, identifier):
        if not identifier:
            return False
        code = self._strip_rust_comments_and_strings(code)
        return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(identifier)}(?![A-Za-z0-9_])", code))

    def _strip_rust_comments_and_strings(self, code):
        if not isinstance(code, str):
            return ""
        code = re.sub(r"//.*", "", code)
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
        code = re.sub(r"r#+\".*?\"#+", '""', code, flags=re.S)
        code = re.sub(r"r\".*?\"", '""', code, flags=re.S)
        code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)
        code = re.sub(r"'(?:\\.|[^'\\])*'", "''", code)
        return code

    def _extract_rust_test_function_names(self, harness):
        names = []
        if not isinstance(harness, str):
            return names
        pattern = r"#\s*\[\s*test\s*\]\s*(?:\n\s*#\s*\[[^\]]+\]\s*)*\n?\s*fn\s+([A-Za-z_]\w*)\s*\("
        for match in re.finditer(pattern, harness):
            names.append(match.group(1))
        return names

    def _is_rust_identifier(self, value):
        return bool(isinstance(value, str) and re.match(r"^[A-Za-z_]\w*$", value))

    def _synthesis_generation_inputs(self):
        return [
            self._display_path(self.alignment_report_path),
            self._display_path(self.src_repo_path),
            self._display_path(self.src_db_path),
            self._display_path(self.tgt_db_path),
        ]

    def _write_adapter_synthesis_inputs(self, artifacts_path, context, prompt):
        if not artifacts_path:
            return
        artifacts_path.mkdir(parents=True, exist_ok=True)
        with open(artifacts_path / "adapter_synthesis_context.json", "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2, ensure_ascii=False)
        (artifacts_path / "adapter_synthesis_prompt.md").write_text(prompt, encoding="utf-8")

    def _build_adapter_synthesis_context(self, alignment_stats, inventory):
        scoped_pairs, source_evidence = self._derive_synthesis_scope(alignment_stats, inventory)
        source_evidence = self._apply_public_replay_eligibility_to_source_evidence(source_evidence)
        scoped_source_uuids = {
            src_uuid
            for case in source_evidence.get("behavior_cases", [])
            for src_uuid in case.get("aligned_source_functions", [])
            if src_uuid
        }
        scoped_pairs = [
            pair for pair in scoped_pairs
            if pair.get("src_uuid") in scoped_source_uuids
        ]
        source_evidence["function_index"] = self._source_function_evidence_index(
            inventory,
            scoped_source_uuids,
            source_evidence.get("behavior_cases", []),
        )
        source_evidence["summary"]["indexed_source_functions"] = len(scoped_source_uuids)
        source_evidence["quality_checks"] = self._source_evidence_quality_checks(
            scoped_source_uuids,
            source_evidence.get("behavior_cases", []),
            source_evidence.get("function_index", {}),
            len(source_evidence.get("behavior_cases", [])),
        )
        public_pairs = [
            pair for pair in alignment_stats.get("pairs", [])
            if pair.get("is_public_eligible")
        ]
        return {
            "schema_version": "3b.adapter_synthesis_context.v5",
            "source_repository": self.src_name,
            "target_repository": self.tgt_name,
            "objective": (
                "Generate a repository-specific 3B public-first adapter for cases that passed "
                "public replay eligibility screening."
            ),
            "constraints": [
                "Do not compare ABI, raw pointer values, memory ownership, or raw return types when languages differ.",
                "Derive observable behavior from source tests, fixtures, expected files, and assertion intent.",
                "Use only public target APIs for L1 replay.",
                "Every behavior case in source_evidence.behavior_cases already passed structural public replay screening.",
                "Required target substitutions for mixed public/internal cases must be called explicitly in the Rust harness.",
                "Adapter generation should convert eligible cases into replay events; generation failures remain unresolved_adapter_generation rather than semantic exclusions.",
                "The LLM generates a replay hypothesis; correctness is decided only by compiling and running target replay.",
            ],
            "generation_policy": {
                "public_first": True,
                "default_layer": "public_behavior",
                "adapter_is_repo_specific": True,
                "eligibility_artifact": "public_replay_eligibility.json",
                "expected_behavior_rule": (
                    "Every executable assertion must be grounded in source test evidence, fixtures, or a direct "
                    "public API property implied by that evidence. Use expected_behavior_confidence=high only when the "
                    "source test/fixture gives a concrete expected result."
                ),
                "coverage_rule": (
                    "Cover every eligible source behavior case listed in source_evidence.behavior_cases when it "
                    "can be converted into a reliable Rust replay. Cases that cannot be converted by the adapter "
                    "generator are reported as unresolved_adapter_generation; behavior differences should be "
                    "replayed rather than hidden as exclusions."
                ),
            },
            "alignment_scope": {
                "public_eligible_pairs_with_src_test_evidence": scoped_pairs,
                "public_eligible_pair_count": len(public_pairs),
                "scoped_pair_count": len(scoped_pairs),
            },
            "test_inventory_summary": inventory.get("summary", {}),
            "public_replay_eligibility_summary": (
                self._public_replay_eligibility or {}
            ).get("summary", {}),
            "source_language_context": self._source_language_context(),
            "source_evidence": source_evidence,
            "source_aligned_api_context": self._source_aligned_api_context(scoped_pairs),
            "target_project_context": self._target_project_context(),
            "target_crate_import_hint": self._target_crate_import_hint(),
            "rust_integration_test_contract": self._rust_integration_test_contract(),
            "target_api_scope": self._target_api_scope(scoped_pairs),
            "target_public_api_signatures": self._target_public_api_signatures_for_synthesis(scoped_pairs),
            "target_aligned_api_context": self._target_aligned_api_context(scoped_pairs),
            "required_adapter_shape": self._adapter_synthesis_schema_hint(),
        }

    def _derive_synthesis_scope(self, alignment_stats, inventory):
        public_pairs = [
            {
                "src_uuid": pair.get("src_uuid"),
                "src_signature": pair.get("src_signature", ""),
                "tgt_uuids": pair.get("tgt_uuids", []),
                "confidence": pair.get("confidence", ""),
            }
            for pair in alignment_stats.get("pairs", [])
            if pair.get("is_public_eligible")
        ]
        called_names = {
            call
            for entry in inventory.get("test_files", [])
            for call in entry.get("calls_aligned_public_functions", [])
        }
        scoped_pairs = [
            pair for pair in public_pairs
            if self._uuid_leaf_name(pair.get("src_uuid", "")) in called_names
        ]
        scoped_source_uuids = {
            pair.get("src_uuid")
            for pair in scoped_pairs
            if pair.get("src_uuid")
        }
        source_evidence = self._source_evidence_bundle(inventory, scoped_source_uuids)
        precise_scoped_source_uuids = self._source_functions_with_precise_behavior_evidence_from_index(
            scoped_source_uuids,
            source_evidence.get("function_index", {}),
        )
        if precise_scoped_source_uuids:
            scoped_source_uuids = precise_scoped_source_uuids
            scoped_pairs = [
                pair for pair in scoped_pairs
                if pair.get("src_uuid") in scoped_source_uuids
            ]
            source_evidence = self._source_evidence_bundle(inventory, scoped_source_uuids)
        return scoped_pairs, source_evidence

    def _build_public_replay_eligibility(self, alignment_stats, inventory):
        scoped_pairs, source_evidence = self._derive_synthesis_scope(alignment_stats, inventory)
        candidate_ids = {
            case.get("case_id")
            for case in source_evidence.get("behavior_cases", [])
            if case.get("case_id")
        }
        detail_index = getattr(self, "_last_behavior_case_details", {}) or {}
        eligible_cases = []
        excluded_cases = []

        for case_id in sorted(candidate_ids):
            case = dict(detail_index.get(case_id, {}))
            if not case:
                continue
            assessment = self._assess_mixed_case_public_replay(case, alignment_stats)
            if assessment.get("eligible"):
                case["eligibility_status"] = "eligible_for_adapter_conversion"
                case["required_internal_public_substitutions"] = assessment.get("substitutions", [])
                eligible_cases.append(case)
            else:
                excluded_cases.append({
                    "case_id": case_id,
                    "name": case.get("name", ""),
                    "path": case.get("path", ""),
                    "start_line": case.get("start_line"),
                    "stage": "public_replay_structural_screen",
                    "reason": assessment.get("reason", "public_replay_structurally_unavailable"),
                    "details": assessment.get("details", ""),
                    "non_public_aligned_call_names": case.get("non_public_aligned_call_names", []),
                })

        precise_case_keys = {
            (case.get("path", ""), case.get("name", ""))
            for case in detail_index.values()
            if isinstance(case, dict)
        }
        unresolved_aligned_cases = []
        scoped_leaf_names = {
            self._uuid_leaf_name(pair.get("src_uuid", ""))
            for pair in scoped_pairs
            if pair.get("src_uuid")
        }
        for entry in inventory.get("test_files", []):
            for case in entry.get("aligned_test_cases", []):
                key = (case.get("path", entry.get("path", "")), case.get("name", ""))
                if key in precise_case_keys:
                    continue
                public_calls = case.get("calls_aligned_public_functions", [])
                intersects_scope = bool(set(public_calls) & scoped_leaf_names)
                unresolved_aligned_cases.append({
                    "name": case.get("name", ""),
                    "path": key[0],
                    "start_line": case.get("start_line"),
                    "stage": "exact_alignment_binding",
                    "reason": (
                        "ambiguous_or_unresolved_cpp_call_binding"
                        if intersects_scope
                        else "outside_precise_l1_function_scope"
                    ),
                    "public_aligned_call_names": public_calls,
                    "details": (
                        "A public aligned leaf-name call was found, but owner/overload resolution could not bind it "
                        "to one exact L1 source UUID."
                        if intersects_scope
                        else "The test calls a public aligned leaf name that is not in the final precise L1 function scope."
                    ),
                })

        mixed_candidates = [
            case for case in detail_index.values()
            if isinstance(case, dict) and case.get("has_mixed_public_internal_calls")
        ]
        return {
            "schema_version": "3b.public_replay_eligibility.v1",
            "source_repository": self.src_name,
            "target_repository": self.tgt_name,
            "summary": {
                "discovered_source_test_cases": max(
                    inventory.get("summary", {}).get("test_cases", 0),
                    inventory.get("summary", {}).get("aligned_test_cases", 0)
                    + inventory.get("summary", {}).get("non_public_aligned_test_cases", 0),
                ),
                "aligned_public_test_candidates": inventory.get("summary", {}).get("aligned_test_cases", 0),
                "cases_unresolved_after_exact_function_binding": len(unresolved_aligned_cases),
                "public_replay_eligible_cases": len(eligible_cases),
                "structurally_ineligible_for_public_replay_cases": len(excluded_cases),
                "mixed_public_internal_candidates": len(mixed_candidates),
                "mixed_cases_eligible_with_public_substitution": len([
                    case for case in eligible_cases
                    if case.get("has_mixed_public_internal_calls")
                ]),
            },
            "policy": {
                "stage_1": "Keep source tests that call exact 3A-aligned source functions in the public L1 scope.",
                "stage_2": (
                    "For mixed public/internal tests, every explicit aligned internal call must map through 3A to "
                    "public target API functions. The adapter must call those substitutions explicitly. Otherwise "
                    "the case is excluded before adapter synthesis."
                ),
                "post_screen_conversion": (
                    "Eligible cases are adapter conversion obligations. A conversion that cannot produce a valid "
                    "Rust replay must remain recorded as excluded during conversion or missing after finite attempts."
                ),
            },
            "eligible_cases": self._compact_behavior_cases_for_prompt(
                eligible_cases,
                max_cases=len(eligible_cases),
                include_snippets=False,
            ),
            "structurally_ineligible_for_public_replay_cases": excluded_cases,
            "cases_unresolved_after_exact_function_binding": unresolved_aligned_cases,
        }

    def _assess_mixed_case_public_replay(self, case, alignment_stats):
        internal_names = sorted(set(case.get("non_public_aligned_call_names", [])))
        if not internal_names:
            return {"eligible": True, "substitutions": []}
        pairs_by_leaf = {}
        for pair in alignment_stats.get("pairs", []):
            leaf = self._uuid_leaf_name(pair.get("src_uuid", ""))
            if leaf:
                pairs_by_leaf.setdefault(leaf, []).append(pair)
        substitutions = []
        body = case.get("relevant_snippet", "") or ""
        for call_name in internal_names:
            candidates = list(pairs_by_leaf.get(call_name, []))
            if not candidates:
                return {
                    "eligible": False,
                    "reason": "internal_call_without_3a_alignment",
                    "details": f"Mixed-scope call `{call_name}` has no exact source pair in the 3A report.",
                }
            candidate_uuids = [pair.get("src_uuid") for pair in candidates if pair.get("src_uuid")]
            resolved_uuids = self._resolve_source_call_uuids_from_case(body, call_name, candidate_uuids)
            if not resolved_uuids:
                if len(candidate_uuids) == 1:
                    resolved_uuids = candidate_uuids
                else:
                    return {
                        "eligible": False,
                        "reason": "ambiguous_internal_call_alignment",
                        "details": (
                            f"Internal call `{call_name}` matches multiple 3A source functions and cannot be "
                            "resolved to one exact function from the source case."
                        ),
                    }
            for src_uuid in resolved_uuids:
                pair = next((item for item in candidates if item.get("src_uuid") == src_uuid), None)
                if not pair:
                    continue
                target_flags = pair.get("target_public_flags", [])
                target_uuids = pair.get("tgt_uuids", [])
                if not target_uuids:
                    return {
                        "eligible": False,
                        "reason": "internal_call_missing_target_alignment",
                        "details": f"Internal source function `{src_uuid}` has no target function in 3A.",
                    }
                if not target_flags or not all(item.get("is_public") for item in target_flags):
                    return {
                        "eligible": False,
                        "reason": "internal_call_target_not_public",
                        "details": (
                            f"Internal source function `{src_uuid}` maps to target functions that are not all public: "
                            f"{target_uuids}."
                        ),
                    }
                substitutions.append({
                    "source_internal_function": src_uuid,
                    "target_public_functions": list(target_uuids),
                    "handling": "explicit_target_public_substitution_required",
                })
        return {"eligible": True, "substitutions": substitutions}

    def _apply_public_replay_eligibility_to_source_evidence(self, source_evidence):
        eligibility = self._public_replay_eligibility or {}
        eligible_items = eligibility.get("eligible_cases", [])
        if not eligibility:
            return source_evidence
        eligible_by_id = {
            item.get("case_id"): item
            for item in eligible_items
            if isinstance(item, dict) and item.get("case_id")
        }
        original_cases = source_evidence.get("behavior_cases", [])
        filtered_cases = []
        for case in original_cases:
            case_id = case.get("case_id")
            eligibility_case = eligible_by_id.get(case_id)
            if not eligibility_case:
                continue
            merged = dict(case)
            merged.update({
                "eligibility_status": "eligible_for_adapter_conversion",
                "required_internal_public_substitutions": eligibility_case.get(
                    "required_internal_public_substitutions",
                    [],
                ),
            })
            filtered_cases.append(merged)
        source_evidence = dict(source_evidence)
        source_evidence["behavior_cases"] = filtered_cases
        summary = dict(source_evidence.get("summary", {}))
        summary["pre_screen_behavior_case_candidates"] = len(original_cases)
        summary["behavior_cases"] = len(filtered_cases)
        summary["available_behavior_case_candidates"] = len(filtered_cases)
        summary["structurally_ineligible_for_public_replay_cases"] = len(
            eligibility.get("structurally_ineligible_for_public_replay_cases", [])
        )
        summary["behavior_case_selection_policy"] = (
            "Only cases that passed exact-alignment and structural public-replay eligibility screening are adapter "
            "conversion obligations. Mixed cases include required target public substitutions."
        )
        source_evidence["summary"] = summary
        allowed_ids = set(eligible_by_id)
        details = getattr(self, "_last_behavior_case_details", {}) or {}
        filtered_details = {}
        for case_id, case in details.items():
            if case_id not in allowed_ids:
                continue
            merged = dict(case)
            merged["eligibility_status"] = "eligible_for_adapter_conversion"
            merged["required_internal_public_substitutions"] = eligible_by_id[case_id].get(
                "required_internal_public_substitutions",
                [],
            )
            filtered_details[case_id] = merged
        self._last_behavior_case_details = filtered_details
        return source_evidence

    def _source_evidence_bundle(self, inventory, scoped_source_uuids):
        behavior_cases, behavior_case_candidates = self._source_behavior_cases(inventory, scoped_source_uuids)
        all_behavior_cases = getattr(self, "_all_source_behavior_cases", behavior_cases)
        self._last_behavior_case_details = {
            case.get("case_id"): case
            for case in all_behavior_cases
            if isinstance(case, dict) and case.get("case_id")
        }
        function_index = self._source_function_evidence_index(
            inventory,
            scoped_source_uuids,
            behavior_cases,
        )
        mixed_behavior_cases = [
            case for case in behavior_cases
            if case.get("has_mixed_public_internal_calls")
        ]
        mixed_public_internal_cases = self._mixed_public_internal_cases(inventory)
        return {
            "schema_version": "3b.source_evidence_bundle.v1",
            "summary": {
                "purpose": (
                    "Compact source-test evidence for adapter synthesis. behavior_cases carry expected-behavior evidence; "
                    "function_index maps every source-tested public 3A source function to concrete case ids."
                ),
                "behavior_cases": len(behavior_cases),
                "available_behavior_case_candidates": behavior_case_candidates,
                "mixed_public_internal_behavior_cases": len(mixed_behavior_cases),
                "mixed_public_internal_case_candidates": len(mixed_public_internal_cases),
                "mixed_public_internal_l1_policy": "public_equivalent_required",
                "behavior_case_selection_policy": (
                    "Include all eligible source behavior cases up to the context budget. These are behavior "
                    "coverage obligations for adapter synthesis: each case should either be replayed through "
                    "trace_events[].source_case_ids or remain unresolved_adapter_generation after bounded "
                    "conversion attempts. Mixed public/internal cases may support L1 only when the internal "
                    "state transition is naturally included in the target public API behavior or can be expressed "
                    "through an explicit target public equivalent."
                ),
                "indexed_source_functions": len(scoped_source_uuids),
            },
            "quality_checks": self._source_evidence_quality_checks(
                scoped_source_uuids,
                behavior_cases,
                function_index,
                behavior_case_candidates,
            ),
            "field_guide": {
                "behavior_cases": (
                    "Primary evidence for operation/expected-behavior design. Each case has concrete source assertions, "
                    "literals, and aligned source function UUIDs. Full snippets are intentionally omitted from "
                    "the initial context to keep all eligible cases visible; targeted agent passes receive "
                    "snippets for the specific missing cases they are asked to cover. Mixed cases expose "
                    "non_public_aligned_call_names so adapter generation can avoid dropping explicit internal "
                    "state transitions that affect final observable behavior."
                ),
                "function_index": (
                    "Coverage index keyed by source UUID. case_refs point back to behavior_cases.case_id; "
                    "direct_assertions are only a quick per-function hint, not a replacement for behavior_cases."
                ),
                "fixtures": "Input or expected-output files referenced by source tests when available.",
                "mixed_public_internal_cases": (
                    "All public L1 candidate cases that also explicitly call non-public aligned functions. "
                    "These are risk cases: use them for L1 only when the adapter can preserve the internal "
                    "effect through target public behavior; otherwise leave them unresolved for L1 replay."
                ),
            },
            "behavior_cases": self._compact_behavior_cases_for_prompt(
                behavior_cases,
                max_cases=len(behavior_cases),
                include_snippets=False,
            ),
            "function_index": function_index,
            "mixed_public_internal_cases": mixed_public_internal_cases[:20],
            "fixtures": self._source_fixture_evidence(inventory, max_files=12, max_chars_per_file=1200),
        }

    def _source_evidence_quality_checks(self, scoped_source_uuids, behavior_cases, function_index, behavior_case_candidates=None):
        scoped = set(scoped_source_uuids)
        behavior_case_candidates = int(behavior_case_candidates or 0)
        case_ids = {
            case.get("case_id")
            for case in behavior_cases
            if case.get("case_id")
        }
        case_sources = {
            src_uuid
            for case in behavior_cases
            for src_uuid in case.get("aligned_source_functions", [])
            if src_uuid
        }
        indexed = set(function_index)
        ref_ids = {
            ref.get("case_id")
            for item in function_index.values()
            for ref in item.get("case_refs", [])
            if ref.get("case_id")
        }
        return {
            "scoped_source_functions": len(scoped),
            "function_index_entries": len(indexed),
            "source_functions_with_behavior_case_evidence": len(scoped & case_sources),
            "missing_function_index_entries": sorted(scoped - indexed),
            "missing_behavior_case_evidence": sorted(scoped - case_sources),
            "dangling_case_refs": sorted(ref_ids - case_ids),
            "selected_behavior_cases": len(behavior_cases),
            "available_behavior_case_candidates": behavior_case_candidates,
            "unlisted_behavior_case_candidates": max(0, behavior_case_candidates - len(behavior_cases)),
            "behavior_case_context_truncated": behavior_case_candidates > len(behavior_cases),
        }

    def _target_public_api_signatures(self, max_items=180):
        items = []
        for uid, func in self._index_functions(self.tgt_db_path, repo_path=self.tgt_repo_path).items():
            if self._is_target_public(func):
                items.append({
                    "uuid": uid,
                    "signature": func.get("signature", ""),
                    "trait_name": func.get("_rust_trait_name", ""),
                })
        items = sorted(items, key=lambda item: item["uuid"])
        if max_items is None:
            return items
        return items[:max_items]

    def _target_api_scope(self, scoped_pairs):
        all_public = self._target_public_api_signatures(max_items=None)
        selected = self._target_public_api_signatures_for_synthesis(scoped_pairs)
        aligned_target_uuids = sorted({
            tgt_uuid
            for pair in scoped_pairs
            for tgt_uuid in pair.get("tgt_uuids", [])
            if tgt_uuid
        })
        selected_uuids = {item.get("uuid") for item in selected}
        return {
            "all_public_api_count": len(all_public),
            "selected_public_api_count": len(selected),
            "aligned_target_api_count": len(aligned_target_uuids),
            "missing_aligned_targets_from_selected": sorted(set(aligned_target_uuids) - selected_uuids),
            "selection_policy": (
                "target_public_api_signatures is a synthesis-focused candidate list: all 3A aligned target APIs "
                "plus public APIs from nearby owners/files and common support names. Validation still checks "
                "against the full target public API set parsed from the repository."
            ),
        }

    def _target_public_api_signatures_for_synthesis(self, scoped_pairs, max_items=120):
        all_public = self._target_public_api_signatures(max_items=None)
        by_uuid = {item.get("uuid"): item for item in all_public if item.get("uuid")}
        aligned_target_uuids = []
        seen = set()
        for pair in scoped_pairs:
            for tgt_uuid in pair.get("tgt_uuids", []):
                if tgt_uuid and tgt_uuid not in seen:
                    seen.add(tgt_uuid)
                    aligned_target_uuids.append(tgt_uuid)

        selected = []
        selected_uuids = set()

        def add_uuid(uuid_value):
            if not uuid_value or uuid_value in selected_uuids:
                return
            item = by_uuid.get(uuid_value)
            if not item:
                return
            selected.append(item)
            selected_uuids.add(uuid_value)

        for tgt_uuid in aligned_target_uuids:
            add_uuid(tgt_uuid)

        aligned_files = {
            tgt_uuid.split("::", 1)[0]
            for tgt_uuid in aligned_target_uuids
            if "::" in tgt_uuid
        }
        aligned_owners = {
            self._rust_owner_type_from_uuid(tgt_uuid)
            for tgt_uuid in aligned_target_uuids
            if self._rust_owner_type_from_uuid(tgt_uuid)
        }
        support_name_pattern = re.compile(
            r"^(new|from|default|empty|len|size|get|set|insert|remove|delete|clear|"
            r"push|pop|append|extend|iter|as_|is_|to_|into_|has_|contains)"
        )
        scored = []
        for item in all_public:
            uuid_value = item.get("uuid", "")
            if not uuid_value or uuid_value in selected_uuids:
                continue
            leaf = self._uuid_leaf_name(uuid_value)
            owner = self._rust_owner_type_from_uuid(uuid_value)
            file_path = uuid_value.split("::", 1)[0] if "::" in uuid_value else ""
            score = 0
            if owner and owner in aligned_owners:
                score += 5
            if file_path in aligned_files:
                score += 3
            if support_name_pattern.search(leaf):
                score += 2
            if leaf in {"from", "new", "default", "len", "size"}:
                score += 2
            if score:
                scored.append((score, uuid_value, item))
        for _, uuid_value, _ in sorted(scored, key=lambda value: (-value[0], value[1])):
            if len(selected) >= max_items:
                break
            add_uuid(uuid_value)

        return selected

    def _source_behavior_cases(self, inventory, scoped_source_uuids, max_cases=120, max_chars_per_case=650):
        scoped_names_to_uuids = {}
        for src_uuid in sorted(scoped_source_uuids or []):
            leaf = self._uuid_leaf_name(src_uuid)
            if leaf:
                scoped_names_to_uuids.setdefault(leaf, []).append(src_uuid)
        cases = []
        for entry in inventory.get("test_files", []):
            for case in entry.get("aligned_test_cases", []):
                calls = []
                aligned_source_functions = []
                ambiguous_calls = []
                body = case.get("body_excerpt", "") or ""
                for call in case.get("calls_aligned_public_functions", []):
                    candidate_uuids = scoped_names_to_uuids.get(call, [])
                    if not candidate_uuids:
                        continue
                    resolved = self._resolve_source_call_uuids_from_case(body, call, candidate_uuids)
                    if resolved:
                        calls.append(call)
                        aligned_source_functions.extend(resolved)
                    else:
                        ambiguous_calls.append(call)
                if not calls:
                    continue
                aligned_source_functions = sorted(dict.fromkeys(aligned_source_functions))
                assertions = self._assertion_evidence_items(body, calls, max_items=10)
                item = {
                    "case_id": self._source_case_id(case.get("path", entry.get("path", "")), case.get("name", "")),
                    "path": case.get("path", entry.get("path", "")),
                    "start_line": case.get("start_line"),
                    "framework": case.get("framework", ""),
                    "name": case.get("name", ""),
                    "aligned_source_functions": aligned_source_functions,
                    "call_names": calls,
                    "ambiguous_call_names": sorted(dict.fromkeys(ambiguous_calls)),
                    "all_aligned_call_names": case.get("calls_aligned_functions", []),
                    "public_aligned_call_names": case.get("calls_aligned_public_functions", []),
                    "non_public_aligned_call_names": case.get("calls_aligned_non_public_functions", []),
                    "has_mixed_public_internal_calls": bool(case.get("has_mixed_public_internal_calls")),
                    "mixed_internal_call_policy": (
                        "If non_public_aligned_call_names is non-empty, do not silently drop those explicit "
                        "source calls when designing a replay. Either express their state transition through "
                        "target public APIs, prove the effect is naturally covered by the selected target public "
                        "calls, or omit the case/function from L1 replay."
                    ) if case.get("has_mixed_public_internal_calls") else "",
                    "case_complexity": self._test_case_complexity(calls),
                    "assertions": assertions,
                    "literal_samples": case.get("literal_samples", [])[:14],
                    "relevant_snippet": self._relevant_case_snippet(body, calls, max_chars=max_chars_per_case),
                }
                cases.append(item)
        cases.sort(key=self._source_behavior_case_sort_key, reverse=True)
        self._all_source_behavior_cases = list(cases)
        return self._select_source_behavior_cases(cases, scoped_source_uuids, max_cases), len(cases)

    def _resolve_source_call_uuids_from_case(self, body, call_name, candidate_uuids):
        candidate_uuids = sorted(uuid_value for uuid_value in candidate_uuids if uuid_value)
        if len(candidate_uuids) <= 1:
            return candidate_uuids
        body = body or ""

        owner_candidates = {}
        for uuid_value in candidate_uuids:
            owner = self._cpp_owner_from_uuid(uuid_value)
            if owner:
                owner_candidates.setdefault(owner, []).append(uuid_value)

        explicit_owner_matches = []
        for owner, uuids in owner_candidates.items():
            if re.search(rf"\b{re.escape(owner)}\s*::\s*{re.escape(call_name)}\s*\(", body):
                explicit_owner_matches.extend(uuids)
        resolved = self._resolve_cpp_overload_by_constness(explicit_owner_matches, is_const_receiver=None)
        if resolved:
            return resolved

        receiver_hints = self._cpp_receiver_type_hints(body)
        receiver_matches = []
        for match in re.finditer(rf"\b([A-Za-z_]\w*)\s*(?:->|\.)\s*{re.escape(call_name)}\s*\(", body):
            receiver = match.group(1)
            hint = receiver_hints.get(receiver, {})
            owner = hint.get("owner", "")
            if not owner:
                continue
            candidates = owner_candidates.get(owner, [])
            arg_count = self._cpp_call_arg_count_after_open_paren(body, match.end() - 1)
            candidates = self._filter_cpp_candidates_by_arg_count(candidates, arg_count)
            resolved = self._resolve_cpp_overload_by_constness(
                candidates,
                is_const_receiver=hint.get("is_const"),
            )
            if resolved:
                receiver_matches.extend(resolved)
            elif len(candidates) == 1:
                receiver_matches.extend(candidates)
        receiver_matches = sorted(set(receiver_matches))
        if receiver_matches:
            return receiver_matches

        return []

    def _filter_cpp_candidates_by_arg_count(self, candidate_uuids, arg_count):
        candidate_uuids = sorted(set(candidate_uuids or []))
        if arg_count is None or len(candidate_uuids) <= 1:
            return candidate_uuids
        matches = []
        for uuid_value in candidate_uuids:
            min_args, max_args = self._cpp_signature_arg_range(self._source_signature_for_uuid(uuid_value))
            if min_args is None:
                continue
            if min_args <= arg_count <= max_args:
                matches.append(uuid_value)
        return matches or candidate_uuids

    def _cpp_signature_arg_range(self, signature):
        if not isinstance(signature, str) or "(" not in signature:
            return (None, None)
        start = signature.find("(")
        end = self._matching_paren_index(signature, start)
        if end < 0:
            return (None, None)
        params_text = signature[start + 1:end].strip()
        if not params_text or params_text == "void":
            return (0, 0)
        params = self._split_cpp_top_level_args(params_text)
        if len(params) == 1 and params[0].strip() == "void":
            return (0, 0)
        max_args = len(params)
        min_args = sum(1 for param in params if "=" not in param)
        return (min_args, max_args)

    def _cpp_call_arg_count_after_open_paren(self, text, open_paren_index):
        if not isinstance(text, str) or open_paren_index < 0:
            return None
        end = self._matching_paren_index(text, open_paren_index)
        if end < 0:
            return None
        args_text = text[open_paren_index + 1:end].strip()
        if not args_text:
            return 0
        return len(self._split_cpp_top_level_args(args_text))

    def _matching_paren_index(self, text, open_paren_index):
        if open_paren_index < 0 or open_paren_index >= len(text) or text[open_paren_index] != "(":
            return -1
        depth = 0
        quote = ""
        escaped = False
        for index in range(open_paren_index, len(text)):
            char = text[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in {'"', "'"}:
                quote = char
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index
        return -1

    def _split_cpp_top_level_args(self, text):
        args = []
        current = []
        paren_depth = bracket_depth = brace_depth = angle_depth = 0
        quote = ""
        escaped = False
        for char in text:
            if quote:
                current.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in {'"', "'"}:
                quote = char
                current.append(char)
                continue
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth = max(0, paren_depth - 1)
            elif char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth = max(0, bracket_depth - 1)
            elif char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth = max(0, brace_depth - 1)
            elif char == "<":
                angle_depth += 1
            elif char == ">":
                angle_depth = max(0, angle_depth - 1)
            if char == "," and not any((paren_depth, bracket_depth, brace_depth, angle_depth)):
                arg = "".join(current).strip()
                if arg:
                    args.append(arg)
                current = []
                continue
            current.append(char)
        arg = "".join(current).strip()
        if arg:
            args.append(arg)
        return args

    def _resolve_cpp_overload_by_constness(self, candidate_uuids, is_const_receiver=None):
        candidate_uuids = sorted(set(candidate_uuids or []))
        if len(candidate_uuids) <= 1:
            return candidate_uuids
        if is_const_receiver is None:
            return []
        matches = []
        for uuid_value in candidate_uuids:
            signature = self._source_signature_for_uuid(uuid_value)
            is_const_method = bool(re.search(r"\)\s*const\b|const\s*;", signature or ""))
            if bool(is_const_method) == bool(is_const_receiver):
                matches.append(uuid_value)
        return matches if len(matches) == 1 else []

    def _cpp_receiver_type_hints(self, body):
        hints = {}
        if not isinstance(body, str):
            return hints
        declaration_pattern = re.compile(
            r"\b(const\s+)?(?:Json::)?([A-Z]\w+)\s*(?:<[^;=(){}>]+>\s*)?(?:[*&]\s*)?([A-Za-z_]\w*)\b"
        )
        for match in declaration_pattern.finditer(body):
            is_const, owner, receiver = match.groups()
            if owner in {"if", "for", "while", "return", "EXPECT", "ASSERT"}:
                continue
            hints[receiver] = {
                "owner": owner,
                "is_const": bool(is_const),
            }
        for match in re.finditer(r"\b(?:auto|CharReaderPtr|std::unique_ptr\s*<\s*(?:Json::)?CharReader\s*>)\s+([A-Za-z_]\w*)\b[^;]*newCharReader", body):
            receiver = match.group(1)
            hints[receiver] = {"owner": "CharReader", "is_const": False}
        for match in re.finditer(
            r"\bstd::unique_ptr\s*<\s*(?:Json::)?([A-Z]\w*)\s*>\s+([A-Za-z_]\w*)\b",
            body,
        ):
            owner, receiver = match.groups()
            hints[receiver] = {"owner": owner, "is_const": False}
        return hints

    def _cpp_fixture_member_context(self, content, fixture_name, max_chars=4000):
        if not content or not fixture_name:
            return ""
        match = re.search(
            rf"\b(?:struct|class)\s+{re.escape(fixture_name)}\b[^{{;]*\{{",
            content,
        )
        if not match:
            return ""
        block = self._extract_braced_block_from_open_brace(content, match.end() - 1)
        if not block:
            return ""
        declarations = []
        patterns = [
            r"\bstd::unique_ptr\s*<\s*(?:Json::)?[A-Z]\w*\s*>\s+[A-Za-z_]\w*\b[^;]*;",
            r"\b(?:const\s+)?(?:Json::)?[A-Z]\w*(?:\s*[*&])?\s+[A-Za-z_]\w*\s*(?:\{[^;]*\})?\s*;",
        ]
        for pattern in patterns:
            declarations.extend(item.group(0).strip() for item in re.finditer(pattern, block))
        return "\n".join(dict.fromkeys(declarations))[:max_chars]

    def _cpp_owner_from_uuid(self, uuid_value):
        if not isinstance(uuid_value, str):
            return ""
        parts = uuid_value.split("::")
        if len(parts) < 3:
            return ""
        owner = strip_overload_suffix(parts[-2])
        if "/" in owner or owner.endswith((".c", ".cc", ".cpp", ".h", ".hpp")):
            return ""
        return owner

    def _source_signature_for_uuid(self, uuid_value):
        if not hasattr(self, "_source_signature_cache"):
            try:
                self._source_signature_cache = {
                    uid: func.get("signature", "")
                    for uid, func in self._index_functions(self.src_db_path, repo_path=self.src_repo_path).items()
                }
            except Exception:
                self._source_signature_cache = {}
        return self._source_signature_cache.get(uuid_value, "")

    def _select_source_behavior_cases(self, cases, scoped_source_uuids, max_cases):
        if max_cases is None or max_cases <= 0:
            return list(cases)
        selected = []
        selected_ids = set()
        uncovered_sources = set(scoped_source_uuids or [])

        # Preserve at least one concrete case per aligned source function when
        # the context budget permits, then fill the remaining slots by the
        # existing evidence-quality ordering.
        for case in cases:
            case_id = case.get("case_id")
            case_sources = set(case.get("aligned_source_functions", []))
            if not case_id or case_id in selected_ids or not (case_sources & uncovered_sources):
                continue
            selected.append(case)
            selected_ids.add(case_id)
            uncovered_sources -= case_sources
            if len(selected) >= max_cases or not uncovered_sources:
                break

        if len(selected) < max_cases:
            for case in cases:
                case_id = case.get("case_id")
                if not case_id or case_id in selected_ids:
                    continue
                selected.append(case)
                selected_ids.add(case_id)
                if len(selected) >= max_cases:
                    break
        return selected

    def _source_case_id(self, path, name):
        base = f"{Path(path or 'test').stem}_{name or 'case'}"
        value = re.sub(r"[^A-Za-z0-9_]+", "_", base).strip("_").lower()
        if not value:
            return "source_test_case"
        if re.match(r"^[0-9]", value):
            value = f"case_{value}"
        return value[:96]

    def _source_behavior_case_sort_key(self, item):
        assertions = item.get("assertions", [])
        direct_assertions = sum(
            1 for assertion in assertions
            if assertion.get("mentions_aligned_functions")
        )
        call_count = len(item.get("aligned_source_functions", []))
        assertion_count = len(assertions)
        complexity = item.get("case_complexity", "")
        focused_bonus = {"focused": 6, "moderate": 3, "broad": 0}.get(complexity, 0)
        return (
            direct_assertions * 4 + min(assertion_count, 6) + focused_bonus - max(0, call_count - 8),
            -call_count,
            len(item.get("literal_samples", [])),
        )

    def _source_function_evidence_index(
        self,
        inventory,
        scoped_source_uuids,
        behavior_cases,
        max_case_refs_per_function=8,
        max_direct_assertions_per_function=3,
    ):
        cases_by_source = {src_uuid: [] for src_uuid in sorted(scoped_source_uuids)}
        direct_assertions_by_source = {src_uuid: [] for src_uuid in sorted(scoped_source_uuids)}
        paths_by_source = {src_uuid: set() for src_uuid in sorted(scoped_source_uuids)}

        for case in behavior_cases:
            for src_uuid in case.get("aligned_source_functions", []):
                if src_uuid not in cases_by_source:
                    continue
                paths_by_source[src_uuid].add(case.get("path", ""))
                if len(cases_by_source[src_uuid]) < max_case_refs_per_function:
                    cases_by_source[src_uuid].append({
                        "case_id": case.get("case_id", ""),
                        "path": case.get("path", ""),
                    })
                source_name = self._uuid_leaf_name(src_uuid)
                for assertion in case.get("assertions", []):
                    if source_name not in assertion.get("mentions_aligned_functions", []):
                        continue
                    direct_assertions = direct_assertions_by_source[src_uuid]
                    expression = assertion.get("expression", "")
                    if expression and expression not in [item.get("expression", "") for item in direct_assertions]:
                        direct_assertions.append({
                            "case_id": case.get("case_id", ""),
                            "expression": expression,
                            "expected_behavior_hint": self._clean_expected_behavior_text(
                                assertion.get(
                                    "expected_behavior_hint",
                                    assertion.get("oracle_hint", ""),
                                )
                            ),
                            "literal_samples": assertion.get("literal_samples", [])[:6],
                        })
                    if len(direct_assertions_by_source[src_uuid]) >= max_direct_assertions_per_function:
                        break

        scoped_names = {}
        for src_uuid in sorted(scoped_source_uuids or []):
            leaf = self._uuid_leaf_name(src_uuid)
            if leaf:
                scoped_names.setdefault(leaf, []).append(src_uuid)
        for entry in inventory.get("test_files", []):
            rel_path = entry.get("path", "")
            content = self._read_text(self.src_repo_path / rel_path) if self.src_repo_path else ""
            for call in entry.get("calls_aligned_public_functions", []):
                candidate_uuids = scoped_names.get(call, [])
                if len(candidate_uuids) != 1:
                    continue
                src_uuid = candidate_uuids[0]
                if src_uuid in paths_by_source and self._rust_code_mentions_identifier(content, call):
                    paths_by_source[src_uuid].add(rel_path)

        return {
            src_uuid: {
                "source_name": self._uuid_leaf_name(src_uuid),
                "evidence_paths": sorted(path for path in paths_by_source.get(src_uuid, set()) if path),
                "case_refs": cases_by_source.get(src_uuid, []),
                "direct_assertions": direct_assertions_by_source.get(src_uuid, []),
            }
            for src_uuid in sorted(scoped_source_uuids)
        }

    def _test_case_complexity(self, calls):
        count = len(calls or [])
        if count <= 3:
            return "focused"
        if count <= 8:
            return "moderate"
        return "broad"

    def _relevant_call_snippet(self, content, calls, max_chars=4200):
        if not content:
            return ""
        lines = content.splitlines()
        selected = set()
        for index, line in enumerate(lines):
            if any(re.search(rf"\b{re.escape(call)}\s*\(", line) for call in calls):
                start = max(0, index - 8)
                end = min(len(lines), index + 14)
                selected.update(range(start, end))
        if not selected:
            return content[:max_chars]
        chunks = []
        last = None
        for index in sorted(selected):
            if last is not None and index > last + 1:
                chunks.append("...")
            chunks.append(f"{index + 1}: {lines[index]}")
            last = index
        snippet = "\n".join(chunks)
        return snippet[:max_chars]

    def _relevant_case_snippet(self, content, calls, max_chars=900):
        if not content:
            return ""
        lines = content.splitlines()
        selected = set()
        for index, line in enumerate(lines):
            if any(re.search(rf"\b{re.escape(call)}\s*\(", line) for call in calls):
                start = max(0, index - 5)
                end = min(len(lines), index + 9)
                selected.update(range(start, end))
        if not selected:
            return content[:max_chars]
        content_is_numbered = sum(
            1 for line in lines[: min(len(lines), 12)]
            if re.match(r"^\s*\d+:\s+", line)
        ) >= 2
        chunks = []
        last = None
        for index in sorted(selected):
            if last is not None and index > last + 1:
                chunks.append("...")
            if content_is_numbered:
                chunks.append(lines[index])
            else:
                chunks.append(f"{index + 1}: {lines[index]}")
            last = index
        return "\n".join(chunks)[:max_chars]

    def _source_function_test_evidence(
        self,
        inventory,
        source_uuids,
        max_functions=40,
        max_entries_per_function=3,
        max_chars_per_snippet=1600,
        max_total_chars=36000,
    ):
        evidence_by_function = {}
        used_chars = 0
        for src_uuid in sorted(source_uuids)[:max_functions]:
            source_name = self._uuid_leaf_name(src_uuid)
            entries = []
            for entry in inventory.get("test_files", []):
                calls = entry.get("calls_aligned_public_functions", [])
                if source_name not in calls:
                    continue
                rel_path = entry.get("path", "")
                path = self.src_repo_path / rel_path
                content = self._read_text(path)
                snippet = self._relevant_call_snippet(content, [source_name], max_chars=max_chars_per_snippet)
                if used_chars + len(snippet) > max_total_chars and entries:
                    break
                entries.append({
                    "path": rel_path,
                    "frameworks": entry.get("frameworks", []),
                    "candidate_test_cases": entry.get("test_cases", [])[:12],
                    "snippet": snippet,
                    "assertion_lines": self._assertion_lines(snippet),
                    "literal_samples": self._literal_samples(snippet),
                })
                used_chars += len(snippet)
                if len(entries) >= max_entries_per_function:
                    break
            if entries:
                evidence_by_function[src_uuid] = entries
            if used_chars >= max_total_chars:
                break
        return evidence_by_function

    def _assertion_lines(self, text, max_items=18):
        if not text:
            return []
        patterns = [
            r"\b(JSONTEST_ASSERT|TEST_ASSERT|CU_ASSERT|ASSERT|EXPECT|REQUIRE|CHECK)\w*\b",
            r"\bassert\s*\(",
            r"\bASSERT_[A-Z0-9_]+\b",
            r"\bEXPECT_[A-Z0-9_]+\b",
            r"\bHWTEST_[A-Z0-9_]+\b",
        ]
        lines = []
        for line in text.splitlines():
            if any(re.search(pattern, line) for pattern in patterns):
                cleaned = line.strip()
                if cleaned and cleaned not in lines:
                    lines.append(cleaned)
            if len(lines) >= max_items:
                break
        return lines

    def _assertion_evidence_items(self, text, aligned_call_names=None, max_items=12):
        aligned_call_names = aligned_call_names or []
        items = []
        for line in self._assertion_lines(text, max_items=max_items * 2):
            stripped = line.strip()
            expression = re.sub(r"^\d+:\s*", "", stripped)
            macro = ""
            macro_match = re.search(
                r"\b([A-Z_]*(?:ASSERT|EXPECT|REQUIRE|CHECK|TEST_ASSERT|CU_ASSERT)[A-Z0-9_]*)\s*\(",
                expression,
            )
            if macro_match:
                macro = macro_match.group(1)
            else:
                assert_match = re.search(r"\b(assert)\s*\(", expression)
                if assert_match:
                    macro = assert_match.group(1)
            mentioned_calls = [
                name for name in aligned_call_names
                if re.search(rf"\b{re.escape(name)}\s*\(", expression)
            ]
            items.append({
                "macro": macro,
                "expression": expression,
                "mentions_aligned_functions": mentioned_calls,
                "literal_samples": self._literal_samples(expression, max_items=10),
                "expected_behavior_hint": self._expected_behavior_hint_from_assertion(expression),
            })
            if len(items) >= max_items:
                break
        return items

    def _expected_behavior_hint_from_assertion(self, assertion_line):
        line = assertion_line.strip()
        if re.search(r"\b(JSONTEST_ASSERT|TEST_ASSERT|ASSERT|EXPECT).*_NOT_NULL", line):
            return "non_null_expected_behavior"
        if re.search(r"\b(JSONTEST_ASSERT|TEST_ASSERT|ASSERT|EXPECT).*_NULL", line):
            return "null_expected_behavior"
        if re.search(r"\b(EXPECT|ASSERT|TEST_ASSERT|JSONTEST_ASSERT).*_EQUAL", line) or re.search(r"\bEXPECT_EQ\s*\(|\bASSERT_EQ\s*\(", line):
            return "equality_expected_behavior"
        if re.search(r"\b(EXPECT|ASSERT|TEST_ASSERT|JSONTEST_ASSERT).*_TRUE", line) or re.search(r"\bEXPECT_TRUE\s*\(|\bASSERT_TRUE\s*\(", line):
            return "truth_expected_behavior"
        if re.search(r"\b(EXPECT|ASSERT|TEST_ASSERT|JSONTEST_ASSERT).*_FALSE", line) or re.search(r"\bEXPECT_FALSE\s*\(|\bASSERT_FALSE\s*\(", line):
            return "falsehood_expected_behavior"
        if re.search(r"\b(assert|CU_ASSERT)\s*\(", line):
            return "source_assert_expression"
        return "assertion_line"

    def _literal_samples(self, text, max_items=28):
        if not text:
            return []
        samples = []
        for match in re.finditer(r'"(?:\\.|[^"\\]){0,160}"', text):
            value = match.group(0)
            if value not in samples:
                samples.append(value)
            if len(samples) >= max_items:
                return samples
        for match in re.finditer(r"(?<![A-Za-z_])[-+]?(?:\d+\.\d+|\d+)(?![A-Za-z_])", text):
            value = match.group(0)
            if value not in samples:
                samples.append(value)
            if len(samples) >= max_items:
                break
        return samples

    def _source_fixture_evidence(self, inventory, max_files=20, max_chars_per_file=1800):
        if not self.src_repo_path:
            return []
        likely_dirs = set()
        for entry in inventory.get("test_files", []):
            rel_path = entry.get("path", "")
            if not rel_path:
                continue
            if not self._looks_like_test_source_path(rel_path):
                continue
            parent = Path(rel_path).parent
            if parent.as_posix() in {"", "."}:
                continue
            likely_dirs.add(parent)
            likely_dirs.add(parent / "inputs")
            likely_dirs.add(parent / "fixtures")
            likely_dirs.add(parent / "data")
        fixture_exts = {
            ".json", ".txt", ".expected", ".golden", ".out", ".in", ".input",
            ".yaml", ".yml", ".toml", ".csv",
        }
        evidence = []
        seen = set()
        for rel_dir in sorted(likely_dirs, key=lambda item: item.as_posix()):
            root = self.src_repo_path / rel_dir
            if not root.exists() or not root.is_dir():
                continue
            for path in sorted(root.iterdir()):
                if not path.is_file() or path.name in seen:
                    continue
                rel_fixture_path = path.relative_to(self.src_repo_path).as_posix()
                if self._looks_like_build_or_ci_file(rel_fixture_path):
                    continue
                suffix = path.suffix.lower()
                if suffix not in fixture_exts and not any(path.name.endswith(ext) for ext in fixture_exts):
                    continue
                text = self._read_text(path, max_chars=max_chars_per_file)
                if not text:
                    continue
                seen.add(path.name)
                evidence.append({
                    "path": rel_fixture_path,
                    "size_bytes": path.stat().st_size if path.exists() else 0,
                    "content_excerpt": text,
                })
                if len(evidence) >= max_files:
                    return evidence
        return evidence

    def _looks_like_test_source_path(self, rel_path):
        path = Path(rel_path)
        suffix = path.suffix.lower()
        parts = {part.lower() for part in path.parts}
        if suffix not in self.TEST_SOURCE_EXTENSIONS:
            return False
        return bool(parts & {"test", "tests", "unittest", "unittests"})

    def _looks_like_build_or_ci_file(self, rel_path):
        name = Path(rel_path).name.lower()
        if name in {
            "cmakelists.txt",
            "cargo.toml",
            "cargo.lock",
            "makefile",
            ".travis.yml",
            ".github",
        }:
            return True
        parts = {part.lower() for part in Path(rel_path).parts}
        return bool(parts & {".github", ".circleci", "cmake", "build"})

    def _target_project_context(self):
        cargo_toml = self._read_text(self.tgt_repo_path / "Cargo.toml", max_chars=2500) if self.tgt_repo_path else ""
        lib_rs = self._read_text(self.tgt_repo_path / "src" / "lib.rs", max_chars=20000) if self.tgt_repo_path else ""
        public_surface = self._rust_public_surface_excerpt(lib_rs, max_chars=5000)
        return {
            "cargo_toml": cargo_toml,
            "src_lib_rs_public_surface": public_surface,
            "note": (
                "Use Cargo.toml package/lib names and src/lib.rs public exports when writing Rust integration tests. "
                "This context intentionally omits most docs/comments and keeps public surface declarations."
            ),
        }

    def _target_crate_import_hint(self):
        cargo_toml = self._read_text(self.tgt_repo_path / "Cargo.toml", max_chars=8000) if self.tgt_repo_path else ""
        package_name = self._toml_section_value(cargo_toml, "package", "name")
        lib_name = self._toml_section_value(cargo_toml, "lib", "name")
        crate_name = (lib_name or package_name or self.tgt_name or "").replace("-", "_")
        return {
            "package_name": package_name,
            "lib_name": lib_name,
            "crate_name_for_rust_code": crate_name,
            "integration_test_note": (
                f"In tests/cp2rs_3b_public.rs, import the target crate as `{crate_name}` "
                "unless Cargo.toml/lib.rs evidence shows a different public crate name."
            ) if crate_name else "",
        }

    def _rust_public_surface_excerpt(self, text, max_chars=5000):
        if not isinstance(text, str) or not text:
            return ""
        kept = []
        pending_doc = []
        public_line_re = re.compile(
            r'^\s*(?:'
            r'pub\s+(?:use|mod|type|fn|struct|enum|trait|const|static)\b|'
            r'pub\s+macro\b|'
            r'#\s*\[\s*macro_export\s*\]|'
            r'macro_rules!\s*[A-Za-z_][A-Za-z0-9_]*'
            r')'
        )
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("///"):
                doc_text = stripped.lstrip("/").strip()
                if doc_text:
                    pending_doc.append(doc_text)
                    pending_doc = pending_doc[-2:]
                continue
            if not public_line_re.match(line):
                if stripped and not stripped.startswith(("#[", "//")):
                    pending_doc = []
                continue
            if pending_doc:
                kept.extend(f"// {item}" for item in pending_doc)
                pending_doc = []
            kept.append(line.rstrip())
            if sum(len(item) + 1 for item in kept) >= max_chars:
                break
        result = "\n".join(kept)
        if result:
            return result[:max_chars]
        non_doc_lines = [
            line.rstrip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith(("//!","///","//"))
        ]
        return "\n".join(non_doc_lines)[:max_chars]

    def _rust_integration_test_contract(self):
        crate_hint = self._target_crate_import_hint()
        crate_name = crate_hint.get("crate_name_for_rust_code", "")
        return self._compact_report_dict({
            "test_file": "tests/cp2rs_3b_public.rs",
            "crate_name_for_rust_code": crate_name,
            "crate_import_rule": (
                f"Target public items must be called as `{crate_name}::item` or imported from `{crate_name}`."
                if crate_name else
                "Target public items must be called through the target integration-test crate name."
            ),
            "fragment_merge_rule": (
                "Adapter case generation merges each rust_test_body independently into one integration test file. "
                "Do not rely on imports emitted by a different case fragment."
            ),
            "import_scope_rule": (
                "A Rust `use` inside one #[test] function is scoped only to that function. "
                "Put shared imports at file top level, or include imports inside every test body that uses them, "
                "or use fully qualified crate paths."
            ),
            "repair_rule": (
                "Replay repair may fix imports, Rust syntax, borrow/API-call shape, and integration-test build issues, "
                "but must not change source-test-derived expected behavior."
            ),
        })

    def _toml_section_value(self, text, section, key):
        if not text:
            return ""
        in_section = False
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            section_match = re.match(r"\[([^\]]+)\]", stripped)
            if section_match:
                in_section = section_match.group(1).strip() == section
                continue
            if not in_section:
                continue
            match = re.match(rf"{re.escape(key)}\s*=\s*\"([^\"]+)\"", stripped)
            if match:
                return match.group(1)
        return ""

    def _source_language_context(self):
        db = self._load_json(self.src_db_path)
        languages = set()
        cpp_files = 0
        c_files = 0
        for file_path, file_data in db.get("files", {}).items():
            language = self._db_language(db, file_path)
            if language:
                languages.add(language)
            suffix = Path(file_path).suffix.lower()
            if suffix in {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}:
                cpp_files += 1
            elif suffix in {".c", ".h"}:
                c_files += 1
        primary = (
            "cpp"
            if ("cpp" in languages or "c++" in languages or cpp_files)
            else ("c" if c_files else (sorted(languages)[0] if languages else "unknown"))
        )
        notes = []
        if primary in {"cpp", "c++"}:
            notes.extend([
                "Source is treated as C++ for 3B inventory and adapter synthesis.",
                "C++ tests may call class/struct methods through obj.method(...), Class::method(...), or namespace-qualified functions.",
                "For gtest/HWTEST fixtures, SetUp/TearDown/member state are source evidence, but L1 replay should still use target public Rust APIs only.",
                "Overloads/templates/operators can make leaf-name matching ambiguous; use signatures, owner names, and test snippets before declaring coverage.",
            ])
        else:
            notes.append("Source is treated as C-style function API for 3B inventory and adapter synthesis.")
        return {
            "primary_source_language": primary,
            "detected_languages": sorted(languages),
            "cpp_file_count": cpp_files,
            "c_file_count": c_files,
            "notes": notes,
        }

    def _source_aligned_api_context(self, scoped_pairs, max_items=90, max_body_chars=900):
        source_uuids = []
        seen = set()
        for pair in scoped_pairs:
            src_uuid = pair.get("src_uuid")
            if src_uuid and src_uuid not in seen:
                seen.add(src_uuid)
                source_uuids.append(src_uuid)
        source_index = self._index_functions(self.src_db_path, repo_path=self.src_repo_path)
        context = []
        for src_uuid in source_uuids[:max_items]:
            func = source_index.get(src_uuid)
            if not func:
                context.append({
                    "uuid": src_uuid,
                    "status": "missing_from_source_parse_db",
                })
                continue
            body = func.get("body", "")
            context.append({
                "uuid": src_uuid,
                "name": func.get("name", ""),
                "language": func.get("_language", ""),
                "decl_kind": func.get("_decl_kind", ""),
                "owner": func.get("_owner_name", ""),
                "owner_kind": func.get("_owner_kind", ""),
                "cpp_visibility": func.get("_cpp_visibility", ""),
                "is_public_for_l1": self._is_source_public(func),
                "signature": func.get("signature", ""),
                "body_excerpt": body[:max_body_chars],
                "call_hint": self._source_call_hint_from_function(src_uuid, func),
            })
        return context

    def _source_call_hint_from_function(self, uuid_value, func):
        name = self._uuid_leaf_name(uuid_value)
        language = str(func.get("_language") or "").lower()
        owner = func.get("_owner_name", "")
        if language in {"cpp", "c++"}:
            if func.get("_decl_kind") == "class_method":
                owner_hint = owner or "OwnerType"
                return (
                    f"C++ method evidence may appear as instance.{name}(...) or {owner_hint}::{name}(...); "
                    "use owner/signature to disambiguate overloads and same-name functions."
                )
            return (
                f"C++ free-function evidence may appear as {name}(...) or namespace-qualified calls such as ns::{name}(...)."
            )
        return f"C function evidence usually appears as {name}(...)."

    def _target_aligned_api_context(self, scoped_pairs, max_items=90, max_body_chars=900):
        target_uuids = []
        seen = set()
        for pair in scoped_pairs:
            for tgt_uuid in pair.get("tgt_uuids", []):
                if tgt_uuid and tgt_uuid not in seen:
                    seen.add(tgt_uuid)
                    target_uuids.append(tgt_uuid)
        target_index = self._index_functions(self.tgt_db_path, repo_path=self.tgt_repo_path)
        context = []
        for tgt_uuid in target_uuids[:max_items]:
            func = target_index.get(tgt_uuid)
            if not func:
                context.append({
                    "uuid": tgt_uuid,
                    "status": "missing_from_target_parse_db",
                })
                continue
            body = func.get("body", "")
            context.append({
                "uuid": tgt_uuid,
                "name": func.get("name", ""),
                "owner_type": self._rust_owner_type_from_uuid(tgt_uuid),
                "signature": func.get("signature", ""),
                "body_excerpt": body[:max_body_chars],
                "call_hint": self._rust_call_hint_from_signature(tgt_uuid, func.get("signature", "")),
            })
        return context

    def _rust_call_hint_from_signature(self, uuid_value, signature):
        name = self._uuid_leaf_name(uuid_value)
        owner = self._rust_owner_type_from_uuid(uuid_value)
        suffix = ""
        if "Into<" in signature:
            suffix = " For generic Into<T> parameters, pass a concrete value directly when possible instead of pre-calling .into()."
        if not signature:
            return ""
        if "&mut self" in signature:
            return f"Call as a mutable method on a mutable {owner or 'receiver'} value, e.g. value.{name}(...).{suffix}"
        if "&self" in signature:
            return f"Call as a method on a {owner or 'receiver'} value/reference, e.g. value.{name}(...).{suffix}"
        if "self" in signature:
            return f"Call as a consuming method on a {owner or 'receiver'} value if the type exports it, e.g. value.{name}(...).{suffix}"
        if owner:
            return f"Call as an associated function if exported, e.g. {owner}::{name}(...).{suffix}"
        return f"Call as a free function if exported, e.g. {name}(...).{suffix}"

    def _rust_owner_type_from_uuid(self, uuid_value):
        if not isinstance(uuid_value, str):
            return ""
        parts = uuid_value.split("::")
        if len(parts) < 3:
            return ""
        owner = parts[-2]
        if owner.endswith(".rs") or "/" in owner:
            return ""
        return owner

    def _adapter_synthesis_schema_hint(self):
        return {
            "adapter_schema_version": "3b.adapter.v1",
            "name": "llm_synthesized_<src>_to_<tgt>_public_v1",
            "status": "loaded",
            "adapter_role": "repo_specific_behavior_recipe",
            "generation_status": "llm_synthesized_v1",
            "recorder": "adapter_declared_trace_events_v1",
            "replay_generator": "rust_inline_harness_v1",
            "target_language": "rust",
            "target_test_command": ["cargo", "test", "--test", "cp2rs_3b_public"],
            "public_operations": {
                "operation_name": {
                    "description": "Behavior scenario derived from source tests.",
                    "source_functions": ["source uuid from 3A"],
                    "target_functions": ["target uuid from 3A or support public target uuid"],
                    "normalization": "Observable behavior comparison rule grounded in source test evidence.",
                    "evidence": ["source test path or fixture"],
                }
            },
            "trace_events": [
                {
                    "id": "stable_trace_id_that_is_also_a_valid_rust_test_fn_name",
                    "operation": "operation_name",
                    "evidence": "source test or fixture evidence",
                    "source_case_ids": [
                        "required: explicit case_id values from source_evidence.behavior_cases covered by this replay; events without source_case_ids do not count toward behavior-case coverage"
                    ],
                    "case_grouping_rationale": "required only when source_case_ids contains more than one case: explain why their normalized inputs and expected observable behavior are equivalent",
                    "input": {"case": "short description"},
                    "expected": {"observable_behavior": "short expected behavior summary"},
                    "expected_behavior_source": "source_test_assertion|source_fixture|source_test_property",
                    "expected_behavior_confidence": "high|medium|low"
                }
            ],
            "excluded_behavior_cases": [
                {
                    "case_id": "case_id from source_evidence.behavior_cases",
                    "reason": "target_missing_public_api|cannot_public_replay_internal_state_transition|expected_behavior_not_precise|requires_function_boundary_or_adapter_wrapper|source_test_requires_device",
                    "details": "required: concrete source/target evidence explaining why public replay is not possible",
                }
            ],
            "rust_test_harness": "Complete Rust integration test source for tests/cp2rs_3b_public.rs. It must define exactly one #[test] fn for each trace_events[].id, using the id as the function name.",
        }

    def _build_adapter_synthesis_prompt(self, context):
        prompt_context = self._initial_synthesis_prompt_context(context)
        context_json = json.dumps(prompt_context, ensure_ascii=False, separators=(",", ":"))
        return PROMPT_3B_ADAPTER_SYNTHESIS.format(context_json=context_json)

    def _initial_synthesis_prompt_context(self, context):
        """Send a representative first batch; later coverage passes receive targeted cases."""
        prompt_context = json.loads(json.dumps(context))
        source_evidence = prompt_context.get("source_evidence", {})
        cases = source_evidence.get("behavior_cases", []) if isinstance(source_evidence, dict) else []
        if not isinstance(cases, list) or len(cases) <= self.initial_synthesis_batch_size:
            self._initial_prompt_case_ids = [
                case.get("case_id") for case in cases
                if isinstance(case, dict) and case.get("case_id")
            ]
            return prompt_context

        selected = []
        selected_ids = set()
        covered_sources = set()
        for case in cases:
            if not isinstance(case, dict):
                continue
            sources = set(case.get("aligned_source_functions", []))
            if sources - covered_sources:
                selected.append(case)
                selected_ids.add(case.get("case_id"))
                covered_sources.update(sources)
            if len(selected) >= self.initial_synthesis_batch_size:
                break
        if len(selected) < self.initial_synthesis_batch_size:
            for case in cases:
                if not isinstance(case, dict) or case.get("case_id") in selected_ids:
                    continue
                selected.append(case)
                selected_ids.add(case.get("case_id"))
                if len(selected) >= self.initial_synthesis_batch_size:
                    break

        source_evidence["behavior_cases"] = selected
        selected_sources = {
            source
            for case in selected
            for source in case.get("aligned_source_functions", [])
        }
        function_index = source_evidence.get("function_index", [])
        if isinstance(function_index, list):
            source_evidence["function_index"] = [
                item for item in function_index
                if isinstance(item, dict) and item.get("src_uuid") in selected_sources
            ]
        source_evidence["initial_batch"] = {
            "selected_case_count": len(selected),
            "total_eligible_case_count": len(cases),
            "remaining_cases_are_handled_by": "behavior_case_conversion_batches",
        }
        alignment_scope = prompt_context.get("alignment_scope", {})
        selected_pairs = [
            pair for pair in alignment_scope.get("public_eligible_pairs_with_src_test_evidence", [])
            if isinstance(pair, dict) and pair.get("src_uuid") in selected_sources
        ]
        alignment_scope["public_eligible_pairs_with_src_test_evidence"] = selected_pairs
        alignment_scope["scoped_pair_count"] = len(selected_pairs)
        source_context = prompt_context.get("source_aligned_api_context", [])
        if isinstance(source_context, list):
            prompt_context["source_aligned_api_context"] = [
                item for item in source_context
                if isinstance(item, dict) and item.get("uuid") in selected_sources
            ]
        prompt_context["target_api_scope"] = self._target_api_scope(selected_pairs)
        prompt_context["target_public_api_signatures"] = self._target_public_api_signatures_for_synthesis(
            selected_pairs,
            max_items=80,
        )
        prompt_context["target_aligned_api_context"] = self._target_aligned_api_context(
            selected_pairs,
            max_items=50,
            max_body_chars=700,
        )
        self._initial_prompt_case_ids = [case.get("case_id") for case in selected if case.get("case_id")]
        return prompt_context

    def _extract_json_from_llm_reply(self, reply):
        text = (reply or "").strip()
        output_match = re.search(r"<output>\s*(.*?)\s*</output>", text, flags=re.S)
        if output_match:
            text = output_match.group(1).strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S)
        if fence_match:
            text = fence_match.group(1).strip()
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]
        text = re.sub(r"(?<!\\)\\u(?![0-9a-fA-F]{4})", r"\\\\u", text)
        text = re.sub(r"(?<!\\)\\([^\"\\/bfnrtu])", r"\\\\\\1", text)
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError as original_error:
            value, end = json.JSONDecoder(strict=False).raw_decode(text)
            trailing = text[end:].strip()
            if trailing and not re.fullmatch(r"[}\]]+", trailing):
                raise original_error
            return value

    def _check_required_paths(self, mode):
        missing = []
        for path in [self.alignment_report_path, self.src_db_path, self.tgt_db_path]:
            if not path.exists():
                missing.append(str(path))
        if self.src_repo_path is None or not self.src_repo_path.exists():
            missing.append(str(self.src_repo_path or "<source repo path>"))
        if mode in {"replay", "run"} and (self.tgt_repo_path is None or not self.tgt_repo_path.exists()):
            missing.append(str(self.tgt_repo_path or "<target repo path>"))
        if missing:
            raise FileNotFoundError("3B requires existing paths: " + ", ".join(missing))

    def _load_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_alignment(self):
        return self._load_json(self.alignment_report_path)

    def _index_functions(self, db_path, repo_path=None):
        db = self._load_json(db_path)
        index = {}
        for file_path, file_data in db.get("files", {}).items():
            for uid, func in iter_function_records(file_path, file_data, definitions_only=False):
                func = dict(func)
                func.setdefault("_file_path", file_path)
                func.setdefault("_language", self._db_language(db, file_path))
                if uid.count("::") >= 2 and file_data.get("classes"):
                    owner_name = uid.split("::", 2)[1]
                    owner = next((cls for cls in file_data.get("classes", []) if cls.get("name") == owner_name), None)
                    if owner:
                        func.setdefault("_decl_kind", "class_method")
                        func.setdefault("_owner_name", owner.get("name", ""))
                        func.setdefault("_owner_kind", owner.get("kind", "class"))
                        func.setdefault("_owner_has_internal_linkage", owner.get("has_internal_linkage", False))
                        func.setdefault(
                            "_cpp_visibility",
                            self._infer_cpp_method_visibility(file_path, owner, func, repo_path),
                        )
                    else:
                        func.setdefault("_decl_kind", "standalone_function")
                elif uid.count("::") >= 2 and file_data.get("impl_blocks"):
                    owner_name = uid.split("::", 2)[1]
                    owner = next((
                        impl for impl in file_data.get("impl_blocks", [])
                        if impl.get("target_type") == owner_name
                        and any(
                            method.get("name") == func.get("name")
                            and (
                                not method.get("start_line")
                                or not func.get("start_line")
                                or method.get("start_line") == func.get("start_line")
                            )
                            for method in impl.get("methods", [])
                        )
                    ), None)
                    if owner:
                        func.setdefault("_decl_kind", "rust_impl_method")
                        func.setdefault("_owner_name", owner.get("target_type", ""))
                        func.setdefault("_owner_kind", "impl")
                        func.setdefault("_rust_trait_name", owner.get("trait_name", ""))
                    else:
                        func.setdefault("_decl_kind", "standalone_function")
                else:
                    func.setdefault("_decl_kind", "standalone_function")
                index[uid] = func
        return index

    def _db_language(self, db, file_path=""):
        language = (
            db.get("metadata", {}).get("language")
            or db.get("language")
            or ""
        )
        language = str(language).lower()
        if language:
            return language
        suffix = Path(file_path).suffix.lower()
        if suffix in {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}:
            return "cpp"
        if suffix in {".c", ".h"}:
            return "c"
        if suffix == ".rs":
            return "rust"
        return ""

    def _infer_cpp_method_visibility(self, file_path, cls, method, repo_path=None):
        owner_kind = (cls.get("kind") or "class").lower()
        default_visibility = "public" if owner_kind == "struct" else "private"
        explicit = method.get("access") or method.get("visibility")
        if explicit in {"public", "private", "protected"}:
            return explicit
        if not repo_path:
            return default_visibility

        source_path = Path(repo_path) / file_path
        content = self._read_text(source_path)
        if not content:
            return default_visibility

        lines = content.splitlines()
        class_location = cls.get("location") or {}
        class_start = max(1, int(class_location.get("start_line") or 1))
        class_end = max(class_start, int(class_location.get("end_line") or len(lines)))
        method_line = int(method.get("start_line") or 0)
        method_name = str(method.get("name") or "").split("::")[-1]
        class_block = lines[class_start - 1: min(class_end, len(lines))]

        if class_start <= method_line <= class_end:
            relative_line = method_line - class_start + 1
            return self._cpp_visibility_before_line(class_block, relative_line, default_visibility)

        if method_name:
            pattern = re.compile(rf"(?<![\w:~])(?:~)?{re.escape(method_name)}\s*\(")
            visibility = default_visibility
            for line in class_block:
                access_match = re.match(r"\s*(public|private|protected)\s*:\s*(?://.*)?$", line)
                if access_match:
                    visibility = access_match.group(1)
                    continue
                if pattern.search(line):
                    return visibility
        return default_visibility

    def _cpp_visibility_before_line(self, class_block_lines, relative_line, default_visibility):
        visibility = default_visibility
        for line in class_block_lines[:max(0, relative_line)]:
            access_match = re.match(r"\s*(public|private|protected)\s*:\s*(?://.*)?$", line)
            if access_match:
                visibility = access_match.group(1)
        return visibility

    def _split_target_uuids(self, tgt_uuid):
        if not tgt_uuid:
            return []
        return [item.strip() for item in str(tgt_uuid).split(",") if item.strip()]

    def _is_source_public(self, func):
        if not func:
            return False
        signature = func.get("signature", "")
        if "CJSON_PUBLIC" in signature:
            return True
        language = str(func.get("_language") or "").lower()
        if language in {"cpp", "c++"}:
            return self._is_cpp_source_public(func)
        return not func.get("is_static", False)

    def _is_cpp_source_public(self, func):
        if not func:
            return False
        signature = func.get("signature", "") or ""
        if func.get("_owner_has_internal_linkage") or func.get("has_internal_linkage"):
            return False
        if func.get("is_static", False) and func.get("_decl_kind") != "class_method":
            return False
        if "static " in signature and func.get("_decl_kind") != "class_method":
            return False
        if func.get("_decl_kind") == "class_method":
            visibility = func.get("_cpp_visibility") or func.get("access") or func.get("visibility")
            return visibility == "public"
        return True

    def _is_target_public(self, func):
        if not func:
            return False
        signature = func.get("signature", "")
        if "pub fn " in signature or signature.strip().startswith("pub "):
            return True
        trait_name = str(func.get("_rust_trait_name") or "").strip()
        trait_root = trait_name.split("<", 1)[0].rsplit("::", 1)[-1]
        return trait_root in {
            "AsMut", "AsRef", "Borrow", "BorrowMut", "Default", "Deref", "DerefMut",
            "From", "FromIterator", "Index", "IndexMut", "Into", "IntoIterator", "TryFrom",
            "TryInto", "PartialEq", "Eq", "PartialOrd", "Ord", "Hash", "Display", "Debug",
        }

    def _summarize_alignment(self, alignment, src_index, tgt_index):
        pairs_by_src = {}
        unique_src = set()
        unique_tgt = set()
        public_eligible_src = set()
        public_eligible_tgt = set()
        skipped_private_internal = []

        for module in alignment.get("aligned_modules", []):
            for item in module.get("aligned_functions") or []:
                src_uuid = item.get("src_uuid")
                tgt_uuids = self._split_target_uuids(item.get("tgt_uuid", ""))
                if not src_uuid:
                    continue

                unique_src.add(src_uuid)
                unique_tgt.update(tgt_uuids)

                src_func = src_index.get(src_uuid)
                entry = pairs_by_src.setdefault(src_uuid, {
                    "src_uuid": src_uuid,
                    "tgt_uuids": [],
                    "confidence_values": [],
                    "src_func": src_func,
                    "src_public": self._is_source_public(src_func),
                    "target_public_by_uuid": {},
                    "target_signature_by_uuid": {},
                })
                if item.get("confidence") and item.get("confidence") not in entry["confidence_values"]:
                    entry["confidence_values"].append(item.get("confidence"))
                for tgt_uuid in tgt_uuids:
                    if tgt_uuid not in entry["tgt_uuids"]:
                        entry["tgt_uuids"].append(tgt_uuid)
                    tgt_func = tgt_index.get(tgt_uuid)
                    entry["target_public_by_uuid"][tgt_uuid] = self._is_target_public(tgt_func)
                    entry["target_signature_by_uuid"][tgt_uuid] = tgt_func.get("signature", "") if tgt_func else ""

        pairs = []
        for src_uuid, entry in pairs_by_src.items():
            tgt_uuids = entry["tgt_uuids"]
            target_public_flags = [entry["target_public_by_uuid"].get(tgt_uuid, False) for tgt_uuid in tgt_uuids]
            src_public = entry["src_public"]
            is_public_eligible = src_public and bool(tgt_uuids) and all(target_public_flags)
            if is_public_eligible:
                public_eligible_src.add(src_uuid)
                public_eligible_tgt.update(tgt_uuids)
            else:
                if not src_public:
                    skip_reason = "source_private_internal_api"
                elif not tgt_uuids:
                    skip_reason = "missing_target_alignment_uuid"
                elif not all(target_public_flags):
                    skip_reason = "target_private_internal_api"
                else:
                    skip_reason = "skipped_private_internal_api"
                skipped_private_internal.append({
                    "src_uuid": src_uuid,
                    "tgt_uuid": ",".join(tgt_uuids),
                    "reason": skip_reason,
                    "source_public": src_public,
                    "target_public": all(target_public_flags) if target_public_flags else False,
                    "target_public_flags": [
                        {"tgt_uuid": tgt_uuid, "is_public": is_public}
                        for tgt_uuid, is_public in zip(tgt_uuids, target_public_flags)
                    ],
                })

            src_func = entry["src_func"]
            pairs.append({
                "src_uuid": src_uuid,
                "tgt_uuids": tgt_uuids,
                "confidence": ",".join(entry["confidence_values"]),
                "is_public_eligible": is_public_eligible,
                "source_public": src_public,
                "target_public_flags": [
                    {
                        "tgt_uuid": tgt_uuid,
                        "is_public": entry["target_public_by_uuid"].get(tgt_uuid, False),
                    }
                    for tgt_uuid in tgt_uuids
                ],
                "public_target_uuids": [
                    tgt_uuid
                    for tgt_uuid in tgt_uuids
                    if entry["target_public_by_uuid"].get(tgt_uuid, False)
                ],
                "src_signature": src_func.get("signature", "") if src_func else "",
                "target_signatures": [
                    {
                        "tgt_uuid": tgt_uuid,
                        "signature": entry["target_signature_by_uuid"].get(tgt_uuid, ""),
                    }
                    for tgt_uuid in tgt_uuids
                ],
            })

        return {
            "pairs": pairs,
            "unique_aligned_source_functions": sorted(unique_src),
            "unique_aligned_target_functions": sorted(unique_tgt),
            "public_eligible_source_functions": sorted(public_eligible_src),
            "public_eligible_target_functions": sorted(public_eligible_tgt),
            "skipped_private_internal": skipped_private_internal,
        }

    def _load_adapter(self):
        if self.adapter_path:
            if not self.adapter_path.exists():
                return {
                    "name": self._display_path(self.adapter_path),
                    "status": "adapter_file_missing",
                    "public_operations": {},
                }
            data = self._load_json(self.adapter_path)
            data.setdefault("status", "loaded")
            data.setdefault("public_operations", {})
            data["_adapter_source_path"] = self._display_path(self.adapter_path)
            data["_adapter_resolution"] = "explicit_adapter"
            self._normalize_expected_behavior_field_names(data)
            return data

        default_adapter = self._load_default_adapter()
        if default_adapter:
            return default_adapter

        return {
            "name": "none",
            "status": "adapter_missing",
            "public_operations": {},
        }

    def _load_default_adapter(self):
        for path in self.default_adapter_candidates(self.src_name, self.tgt_name):
            if not path.exists():
                continue
            is_cache = self._is_generated_adapter_cache_path(path)
            try:
                data = self._load_json(path)
            except (OSError, json.JSONDecodeError):
                if is_cache:
                    continue
                return {
                    "name": self._display_path(path),
                    "status": "adapter_file_invalid",
                    "public_operations": {},
                }
            if is_cache and not self._is_reusable_generated_adapter_cache(data):
                continue
            data.setdefault("status", "loaded")
            data.setdefault("public_operations", {})
            data["_adapter_source_path"] = self._display_path(path)
            data["_adapter_resolution"] = "generated_adapter_cache" if is_cache else "static_adapter"
            self._normalize_expected_behavior_field_names(data)
            return data
        return None

    @classmethod
    def default_adapter_candidates(cls, src_name, tgt_name):
        base_names = cls._adapter_base_names(src_name, tgt_name)
        return [
            *[cls.ADAPTER_DIR / f"{base_name}.json" for base_name in base_names],
            *[cls.GENERATED_ADAPTER_CACHE_DIR / f"{base_name}.json" for base_name in base_names],
        ]

    @classmethod
    def generated_adapter_cache_path(cls, src_name, tgt_name):
        return cls.GENERATED_ADAPTER_CACHE_DIR / f"{src_name}_vs_{tgt_name}.json"

    @classmethod
    def _adapter_base_names(cls, src_name, tgt_name):
        exact = f"{src_name}_vs_{tgt_name}"
        lower = f"{src_name.lower()}_vs_{tgt_name.lower()}"
        return [exact] if exact == lower else [exact, lower]

    @classmethod
    def has_reusable_default_adapter(cls, src_name, tgt_name):
        for path in cls.default_adapter_candidates(src_name, tgt_name):
            if not path.exists():
                continue
            if cls._is_generated_adapter_cache_path_static(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
                if not cls._is_reusable_generated_adapter_cache_static(data):
                    continue
            return True
        return False

    def _is_generated_adapter_cache_path(self, path):
        return self._is_generated_adapter_cache_path_static(path)

    @classmethod
    def _is_generated_adapter_cache_path_static(cls, path):
        try:
            Path(path).resolve().relative_to(cls.GENERATED_ADAPTER_CACHE_DIR.resolve())
            return True
        except (OSError, ValueError):
            return False

    def _is_reusable_generated_adapter_cache(self, adapter):
        if not self._is_reusable_generated_adapter_cache_static(adapter):
            return False
        current_fingerprint = self._public_replay_eligibility_fingerprint()
        return bool(current_fingerprint) and adapter.get("_eligibility_case_fingerprint") == current_fingerprint

    @classmethod
    def _is_reusable_generated_adapter_cache_static(cls, adapter):
        if adapter.get("_adapter_cache_status") != "reusable_after_validated_replay":
            return False
        if adapter.get("_eligibility_schema_version") != "3b.public_replay_eligibility.v1":
            return False
        if not adapter.get("_eligibility_case_fingerprint"):
            return False
        if adapter.get("_last_replay_status") != "passed":
            return False
        if adapter.get("_validation_errors"):
            return False
        status_counts = adapter.get("_replay_plan_alignment_status_counts") or {}
        disallowed = set(status_counts) - {"fully_aligned"}
        if disallowed:
            return False
        if not status_counts.get("fully_aligned", 0):
            return False
        coverage_scope = adapter.get("_cache_coverage_scope") or {}
        if not coverage_scope:
            return False
        required_behavior_keys = {
            "required_behavior_case_count",
            "replayed_behavior_case_count",
            "excluded_behavior_case_count",
            "missing_behavior_case_count",
            "unresolved_unlisted_behavior_case_count",
        }
        if not required_behavior_keys.issubset(set(coverage_scope)):
            return False
        if coverage_scope.get("required_behavior_case_count", 0) <= 0:
            return False
        if coverage_scope.get("missing_behavior_case_count", 0) != 0:
            return False
        if coverage_scope.get("unresolved_unlisted_behavior_case_count", 0) != 0:
            return False
        required_behavior_cases = coverage_scope.get("required_behavior_case_count", 0)
        accounted_behavior_cases = (
            coverage_scope.get("replayed_behavior_case_count", 0)
            + coverage_scope.get("excluded_behavior_case_count", 0)
        )
        if required_behavior_cases and accounted_behavior_cases != required_behavior_cases:
            return False
        return True

    def discover_tests(self, alignment_stats):
        aligned_names = {
            self._uuid_leaf_name(uuid)
            for uuid in alignment_stats.get("unique_aligned_source_functions", [])
        }
        public_names = {
            self._uuid_leaf_name(uuid)
            for uuid in alignment_stats.get("public_eligible_source_functions", [])
        }
        test_files = []
        build_targets = []

        for root, dirs, files in os.walk(self.src_repo_path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS and not d.startswith(".")]
            for filename in files:
                path = Path(root) / filename
                rel_path = path.relative_to(self.src_repo_path).as_posix()
                ext = path.suffix.lower()

                if filename == "CMakeLists.txt":
                    content = self._read_text(path)
                    targets = self._extract_cmake_targets(content, rel_path)
                    build_targets.extend(targets)
                    if targets:
                        test_files.append(self._build_file_inventory_entry(rel_path, "cmake", content, public_names, aligned_names))
                    continue

                if filename == "BUILD.gn" or ext == ".gn":
                    content = self._read_text(path)
                    targets = self._extract_gn_targets(content, rel_path)
                    build_targets.extend(targets)
                    if targets:
                        test_files.append(self._build_file_inventory_entry(rel_path, "gn", content, public_names, aligned_names))
                    continue

                if ext not in self.TEST_SOURCE_EXTENSIONS:
                    continue

                looks_like_test = (
                    "test" in rel_path.lower()
                    or "RUN_TEST" in self._read_text(path, max_chars=4000)
                    or "HWTEST" in self._read_text(path, max_chars=4000)
                    or "TEST_F" in self._read_text(path, max_chars=4000)
                    or "TEST(" in self._read_text(path, max_chars=4000)
                    or "JSONTEST_FIXTURE" in self._read_text(path, max_chars=4000)
                    or "JSONTEST_ASSERT" in self._read_text(path, max_chars=4000)
                )
                if not looks_like_test:
                    continue

                content = self._read_text(path)
                entry = self._build_file_inventory_entry(rel_path, "source_test", content, public_names, aligned_names)
                if entry["frameworks"] or entry["test_cases"] or entry["calls_aligned_functions"]:
                    test_files.append(entry)

        frameworks = {}
        test_case_count = 0
        aligned_test_case_count = 0
        non_public_aligned_test_case_count = 0
        mixed_public_internal_test_case_count = 0
        device_required_count = 0
        for entry in test_files:
            for framework in entry.get("frameworks", []):
                frameworks[framework] = frameworks.get(framework, 0) + 1
            test_case_count += len(entry.get("test_cases", []))
            aligned_test_case_count += len(entry.get("aligned_test_cases", []))
            non_public_aligned_test_case_count += len(entry.get("non_public_aligned_test_cases", []))
            mixed_public_internal_test_case_count += len([
                case for case in entry.get("aligned_test_cases", [])
                if case.get("has_mixed_public_internal_calls")
            ])
            if entry.get("device_required"):
                device_required_count += 1

        return {
            "source_repository": self.src_name,
            "source_repo_path": self._display_path(self.src_repo_path),
            "test_files": test_files,
            "build_targets": build_targets,
            "summary": {
                "test_files": len(test_files),
                "test_cases": test_case_count,
                "aligned_test_cases": aligned_test_case_count,
                "non_public_aligned_test_cases": non_public_aligned_test_case_count,
                "mixed_public_internal_aligned_test_cases": mixed_public_internal_test_case_count,
                "build_targets": len(build_targets),
                "framework_files": frameworks,
                "device_required_files": device_required_count,
            },
        }

    def _read_text(self, path, max_chars=None):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(max_chars) if max_chars else f.read()
        except OSError:
            return ""
        return text

    def _build_file_inventory_entry(self, rel_path, kind, content, public_names, aligned_names=None):
        aligned_names = aligned_names or set(public_names or [])
        frameworks = self._detect_frameworks(content, rel_path)
        test_cases = self._extract_test_cases(content)
        all_calls = sorted(name for name in aligned_names if re.search(rf"\b{re.escape(name)}\s*\(", content))
        calls = sorted(name for name in public_names if re.search(rf"\b{re.escape(name)}\s*\(", content))
        aligned_test_cases = self._extract_aligned_test_case_evidence(
            content=content,
            rel_path=rel_path,
            public_names=public_names,
            aligned_names=aligned_names,
            require_public=True,
            frameworks=frameworks,
        )
        non_public_aligned_test_cases = self._extract_aligned_test_case_evidence(
            content=content,
            rel_path=rel_path,
            public_names=public_names,
            aligned_names=aligned_names,
            require_public=False,
            frameworks=frameworks,
        )
        non_public_aligned_test_cases = [
            case for case in non_public_aligned_test_cases
            if case.get("calls_aligned_non_public_functions") and not case.get("calls_aligned_public_functions")
        ]
        device_required = self._is_device_required(content, rel_path)
        return {
            "path": rel_path,
            "kind": kind,
            "frameworks": frameworks,
            "test_cases": test_cases,
            "aligned_test_cases": aligned_test_cases,
            "non_public_aligned_test_cases": non_public_aligned_test_cases,
            "calls_aligned_functions": all_calls,
            "calls_aligned_public_functions": calls,
            "calls_aligned_non_public_functions": sorted(set(all_calls) - set(calls)),
            "device_required": device_required,
            "skip_reason": "skipped_device_required" if device_required else "",
        }

    def _detect_frameworks(self, content, rel_path):
        frameworks = []
        if "RUN_TEST" in content or "unity.h" in content:
            frameworks.append("unity")
        if re.search(r"\bTEST(_F|_P)?\s*\(", content):
            frameworks.append("gtest")
        if re.search(r"\bHWTEST(_F|_P)?\s*\(", content):
            frameworks.append("openharmony_hwtest")
        if re.search(r"\bJSONTEST_FIXTURE(?:_LOCAL)?\s*\(", content) or "JSONTEST_ASSERT" in content:
            frameworks.append("jsoncpp_jsontest")
        if "ohos_unittest" in content or "ohos_rust_unittest" in content:
            frameworks.append("openharmony_gn_unittest")
        if rel_path.endswith("CMakeLists.txt") and ("add_test" in content or "enable_testing" in content):
            frameworks.append("cmake_ctest")
        return sorted(set(frameworks))

    def _extract_test_cases(self, content):
        cases = []
        for match in re.finditer(r"\bRUN_TEST\s*\(\s*([A-Za-z_]\w*)", content):
            cases.append({"framework": "unity", "name": match.group(1)})

        test_regex = r"\b(TEST(?:_F|_P)?|HWTEST(?:_F|_P)?)\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)"
        for match in re.finditer(test_regex, content):
            macro, suite, name = match.groups()
            framework = "openharmony_hwtest" if macro.startswith("HWTEST") else "gtest"
            cases.append({"framework": framework, "name": f"{suite}.{name}"})

        jsoncpp_test_regex = r"(?m)^\s*(?!#)\s*(JSONTEST_FIXTURE(?:_LOCAL)?)\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)"
        for match in re.finditer(jsoncpp_test_regex, content):
            _, suite, name = match.groups()
            cases.append({"framework": "jsoncpp_jsontest", "name": f"{suite}.{name}"})

        seen = set()
        unique_cases = []
        for case in cases:
            key = (case["framework"], case["name"])
            if key not in seen:
                seen.add(key)
                unique_cases.append(case)
        return unique_cases

    def _extract_aligned_test_case_evidence(
        self,
        content,
        rel_path,
        public_names,
        aligned_names=None,
        require_public=True,
        frameworks=None,
    ):
        aligned_names = aligned_names or set(public_names or [])
        if not content or not aligned_names:
            return []
        frameworks = frameworks or []
        cases = []
        seen = set()
        helper_blocks = self._aligned_test_helper_blocks(content, aligned_names)

        for match in re.finditer(r"\bRUN_TEST\s*\(\s*([A-Za-z_]\w*)", content):
            name = match.group(1)
            block = self._extract_named_c_function_block(content, name)
            case = self._build_aligned_test_case(
                rel_path,
                "unity",
                name,
                block or "",
                public_names,
                aligned_names=aligned_names,
                require_public=require_public,
                helper_blocks=helper_blocks,
                start_line=self._line_number_for_offset(content, match.start()),
            )
            if case:
                key = (case["framework"], case["name"], case.get("start_line", 0))
                if key not in seen:
                    seen.add(key)
                    cases.append(case)

        test_regex = r"\b(TEST(?:_F|_P)?|HWTEST(?:_F|_P)?)\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)"
        for match in re.finditer(test_regex, content):
            macro, suite, name = match.groups()
            framework = "openharmony_hwtest" if macro.startswith("HWTEST") else "gtest"
            block = self._extract_braced_block_after(content, match.end())
            case = self._build_aligned_test_case(
                rel_path,
                framework,
                f"{suite}.{name}",
                block or "",
                public_names,
                aligned_names=aligned_names,
                require_public=require_public,
                helper_blocks=helper_blocks,
                start_line=self._line_number_for_offset(content, match.start()),
            )
            if case:
                key = (case["framework"], case["name"], case.get("start_line", 0))
                if key not in seen:
                    seen.add(key)
                    cases.append(case)

        jsoncpp_test_regex = r"(?m)^\s*(?!#)\s*(JSONTEST_FIXTURE(?:_LOCAL)?)\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)"
        for match in re.finditer(jsoncpp_test_regex, content):
            _, suite, name = match.groups()
            block = self._extract_braced_block_after(content, match.end())
            fixture_context = self._cpp_fixture_member_context(content, suite)
            if fixture_context:
                block = (block or "") + "\n/* cp2rs fixture member type evidence */\n" + fixture_context
            case = self._build_aligned_test_case(
                rel_path,
                "jsoncpp_jsontest",
                f"{suite}.{name}",
                block or "",
                public_names,
                aligned_names=aligned_names,
                require_public=require_public,
                helper_blocks=helper_blocks,
                start_line=self._line_number_for_offset(content, match.start()),
            )
            if case:
                key = (case["framework"], case["name"], case.get("start_line", 0))
                if key not in seen:
                    seen.add(key)
                    cases.append(case)

        for match in re.finditer(
            r"(?m)^\s*(?:static\s+)?(?:void|int|bool|auto)\s+(test_[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
            content,
        ):
            name = match.group(1)
            block = self._extract_braced_block_from_open_brace(content, match.end() - 1)
            case = self._build_aligned_test_case(
                rel_path,
                "function_test",
                name,
                block or "",
                public_names,
                aligned_names=aligned_names,
                require_public=require_public,
                helper_blocks=helper_blocks,
                start_line=self._line_number_for_offset(content, match.start()),
            )
            if case:
                key = (case["framework"], case["name"], case.get("start_line", 0))
                if key not in seen:
                    seen.add(key)
                    cases.append(case)

        return cases

    def _build_aligned_test_case(
        self,
        rel_path,
        framework,
        name,
        block,
        public_names,
        aligned_names=None,
        require_public=True,
        max_chars=1800,
        helper_blocks=None,
        start_line=None,
    ):
        if not block:
            return None
        block = self._expand_test_case_with_helpers(block, helper_blocks or {})
        aligned_names = aligned_names or set(public_names or [])
        all_calls = sorted(name for name in aligned_names if re.search(rf"\b{re.escape(name)}\s*\(", block))
        public_calls = sorted(name for name in public_names if re.search(rf"\b{re.escape(name)}\s*\(", block))
        non_public_calls = sorted(set(all_calls) - set(public_calls))
        if require_public and not public_calls:
            return None
        if not require_public and not all_calls:
            return None
        excerpt = self._numbered_excerpt(block, max_chars=max_chars)
        return {
            "framework": framework,
            "name": name,
            "path": rel_path,
            "start_line": start_line or self._line_number_for_offset(block, 0),
            "calls_aligned_functions": all_calls,
            "calls_aligned_public_functions": public_calls,
            "calls_aligned_non_public_functions": non_public_calls,
            "has_mixed_public_internal_calls": bool(public_calls and non_public_calls),
            "assertion_lines": self._assertion_lines(block),
            "literal_samples": self._literal_samples(block),
            "body_excerpt": excerpt,
        }

    def _aligned_test_helper_blocks(self, content, aligned_names, max_helpers=80):
        helpers = {}
        if not content or not aligned_names:
            return helpers
        pattern = re.compile(
            r"(?m)^\s*(?:static\s+)?(?:inline\s+)?"
            r"(?:void|bool|int|unsigned|auto|Json::[A-Za-z_]\w*|[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)"
            r"(?:\s*[*&])?\s+([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*\([^;{}]*\)\s*\{"
        )
        for match in pattern.finditer(content):
            qualified_name = match.group(1)
            name = qualified_name.split("::")[-1]
            if name.startswith("test_") or name in {"main"}:
                continue
            block = self._extract_braced_block_from_open_brace(content, match.end() - 1)
            if not block:
                continue
            has_aligned_call = any(
                re.search(rf"\b{re.escape(aligned_name)}\s*\(", block)
                for aligned_name in aligned_names
            )
            if not has_aligned_call or not self._assertion_lines(block):
                continue
            helpers[name] = block
            if len(helpers) >= max_helpers:
                break
        return helpers

    def _expand_test_case_with_helpers(self, block, helper_blocks, max_helpers=6):
        if not block or not helper_blocks:
            return block
        expanded = [block]
        added = set()
        for helper_name, helper_block in sorted(helper_blocks.items()):
            if helper_name in added:
                continue
            if not re.search(rf"\b{re.escape(helper_name)}\s*\(", block):
                continue
            expanded.append(f"\n/* cp2rs source test helper evidence: {helper_name} */\n{helper_block}")
            added.add(helper_name)
            if len(added) >= max_helpers:
                break
        return "\n".join(expanded)

    def _extract_named_c_function_block(self, content, function_name):
        pattern = rf"(?m)^\s*(?:static\s+)?(?:void|int|bool|auto)\s+{re.escape(function_name)}\s*\([^;{{}}]*\)\s*\{{"
        match = re.search(pattern, content)
        if not match:
            return ""
        return self._extract_braced_block_from_open_brace(content, match.end() - 1)

    def _extract_braced_block_after(self, content, start_index):
        open_index = content.find("{", start_index)
        if open_index == -1:
            return ""
        return self._extract_braced_block_from_open_brace(content, open_index)

    def _extract_braced_block_from_open_brace(self, content, open_index):
        if open_index < 0 or open_index >= len(content) or content[open_index] != "{":
            return ""
        close_index = self._find_matching_brace(content, open_index)
        if close_index == -1:
            close_index = len(content) - 1
        prefix_start = max(0, content.rfind("\n", 0, open_index) + 1)
        return content[prefix_start:close_index + 1]

    def _find_matching_brace(self, content, open_index):
        depth = 0
        i = open_index
        in_string = None
        escape = False
        while i < len(content):
            ch = content[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch in {'"', "'"}:
                in_string = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    def _numbered_excerpt(self, text, max_chars=1800):
        lines = text.splitlines()
        excerpt = "\n".join(f"{index + 1}: {line}" for index, line in enumerate(lines))
        if len(excerpt) <= max_chars:
            return excerpt
        head_size = max_chars // 2
        tail_size = max_chars - head_size
        return (
            excerpt[:head_size]
            + "\n...<cp2rs excerpt middle omitted>...\n"
            + excerpt[-tail_size:]
        )

    def _line_number_for_offset(self, text, offset):
        return text.count("\n", 0, max(0, offset)) + 1

    def _extract_cmake_targets(self, content, rel_path):
        targets = []
        for match in re.finditer(r"add_test\s*\(\s*(?:NAME\s+)?\"?([A-Za-z0-9_\-${}]+)\"?", content):
            targets.append({"path": rel_path, "kind": "cmake_add_test", "name": match.group(1)})
        for match in re.finditer(r"set\s*\(\s*([A-Za-z0-9_]*tests?)\s+(.*?)\)", content, flags=re.S | re.I):
            variable, body = match.groups()
            names = re.findall(r"[A-Za-z0-9_][A-Za-z0-9_\-]*", body)
            for name in names:
                if name not in {"if", "endif", "foreach"}:
                    targets.append({"path": rel_path, "kind": f"cmake_set_{variable}", "name": name})
        return targets

    def _extract_gn_targets(self, content, rel_path):
        targets = []
        patterns = [
            (r"\bohos_unittest\s*\(\s*\"([^\"]+)\"", "ohos_unittest"),
            (r"\bohos_rust_unittest\s*\(\s*\"([^\"]+)\"", "ohos_rust_unittest"),
            (r"\bgroup\s*\(\s*\"unittest\"", "gn_unittest_group"),
            (r"\bunittest\s*\(\s*\"([^\"]+)\"", "gn_unittest"),
        ]
        for pattern, kind in patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1) if match.groups() else "unittest"
                targets.append({"path": rel_path, "kind": kind, "name": name})
        return targets

    def _is_device_required(self, content, rel_path):
        haystack = f"{rel_path}\n{content}".lower()
        return any(marker in haystack for marker in ["xdevice", "hdc", "device_test", "deviceonly", "hats"])

    def build_replay_plan(self, inventory, alignment_stats, adapter):
        if adapter.get("status") != "loaded":
            return self._empty_replay_plan("adapter_missing")

        if adapter.get("recorder") == "adapter_declared_trace_events_v1":
            allowed_source_functions = self._adapter_replay_source_scope(alignment_stats, inventory)
            return self._build_replay_plan_from_adapter_events(adapter, allowed_source_functions=allowed_source_functions)

        return self._empty_replay_plan("adapter_has_no_recorder")

    def _empty_replay_plan(self, reason):
        return {
            "schema_version": "3b.replay_plan.v1",
            "status": "empty",
            "recording_strategy": "public_first",
            "skip_reason": reason,
            "events": [],
            "summary": {
                "events": 0,
                "planned_source_functions": 0,
                "planned_target_functions": 0,
                "validated_aligned_source_functions": 0,
                "validated_aligned_target_functions": 0,
                "covered_aligned_pairs": 0,
                "alignment_status_counts": {},
            },
        }

    def _operation_available(self, adapter, operation):
        return operation in adapter.get("public_operations", {})

    def _adapter_replay_source_scope(self, alignment_stats, inventory):
        public_eligible_src = set(alignment_stats.get("public_eligible_source_functions", []))
        return self._source_functions_with_test_evidence(
            inventory,
            public_eligible_src,
            require_precise_behavior=True,
        )

    def _build_replay_plan_from_adapter_events(self, adapter, allowed_source_functions=None):
        events = []
        skipped_scope_events = []
        allowed_source_functions = set(allowed_source_functions or [])
        declared_events = adapter.get("trace_events") or []
        if declared_events:
            for declared in declared_events:
                operation = declared.get("operation")
                if not operation or not self._operation_available(adapter, operation):
                    continue
                scoped_source_functions = self._operation_scoped_source_functions(
                    adapter,
                    operation,
                    allowed_source_functions,
                )
                if allowed_source_functions and not scoped_source_functions:
                    skipped_scope_events.append(declared.get("id") or operation)
                    continue
                events.append(self._replay_plan_event_from_adapter_event(
                    adapter,
                    declared,
                    scoped_source_functions=scoped_source_functions,
                ))
        else:
            for operation, op in adapter.get("public_operations", {}).items():
                scoped_source_functions = self._operation_scoped_source_functions(
                    adapter,
                    operation,
                    allowed_source_functions,
                )
                if allowed_source_functions and not scoped_source_functions:
                    skipped_scope_events.append(operation)
                    continue
                events.append(self._replay_plan_event_from_adapter_event(adapter, {
                    "operation": operation,
                    "evidence": "; ".join(op.get("evidence", [])) if isinstance(op.get("evidence"), list) else op.get("evidence", ""),
                    "input": {"case": operation},
                    "expected": {"observable_behavior": op.get("normalization", "")},
                }, scoped_source_functions=scoped_source_functions))

        if not events:
            return self._empty_replay_plan("adapter_declared_no_trace_events")

        return {
            "schema_version": "3b.replay_plan.v1",
            "status": "recorded",
            "recording_strategy": "adapter_declared_trace_events_v1",
            "note": "Replay plan events were derived from effective adapter trace_events generated from source test evidence.",
            "skipped_scope_events": skipped_scope_events[:100],
            "skipped_scope_event_count": len(skipped_scope_events),
            "events": events,
            "summary": self._build_replay_plan_summary(events),
        }

    def _operation_scoped_source_functions(self, adapter, operation, allowed_source_functions):
        op = adapter.get("public_operations", {}).get(operation, {})
        source_functions = op.get("source_functions", []) if isinstance(op, dict) else []
        if not source_functions:
            return []
        if not allowed_source_functions:
            return list(source_functions)
        return [src_uuid for src_uuid in source_functions if src_uuid in allowed_source_functions]

    def _replay_plan_event_from_adapter_event(self, adapter, declared, scoped_source_functions=None):
        operation = declared["operation"]
        op = adapter["public_operations"][operation]
        event_id = declared.get("id") or f"trace_{operation}_{uuid.uuid4().hex[:8]}"
        source_functions = scoped_source_functions if scoped_source_functions is not None else op.get("source_functions", [])
        omitted_source_functions = [
            src_uuid for src_uuid in op.get("source_functions", [])
            if src_uuid not in set(source_functions)
        ]
        return {
            "id": event_id,
            "layer": "public_behavior",
            "operation": operation,
            "evidence": declared.get("evidence", ""),
            "source_functions": source_functions,
            "target_functions": op.get("target_functions", []),
            "operation_metadata": {
                "description": op.get("description", ""),
                "normalization": op.get("normalization", ""),
                "normalization_status": "adapter_declared_v1",
                "adapter_generation_status": adapter.get("generation_status", ""),
                "scope_filtered_source_functions": bool(omitted_source_functions),
                "omitted_source_functions_outside_l1_scope": omitted_source_functions,
            },
            "input": declared.get("input", {}),
            "expected": declared.get("expected", {}),
            "source_case_ids": declared.get("source_case_ids", []),
            "expected_behavior_source": (
                declared.get("expected_behavior_source")
                or declared.get("oracle_source")
                or "adapter_declared_from_source_test_evidence"
            ),
            "expected_behavior_confidence": (
                declared.get("expected_behavior_confidence")
                or declared.get("oracle_confidence")
                or "medium"
            ),
        }

    def _ensure_replay_plan_alignment_validation(self, replay_plan, alignment_stats, adapter):
        if replay_plan.get("status") != "recorded":
            return replay_plan

        for event in replay_plan.get("events", []):
            operation = event.get("operation")
            op = adapter.get("public_operations", {}).get(operation)
            if op is None:
                event["alignment_validation"] = {
                    "status": "adapter_operation_missing",
                    "covered_pairs": [],
                    "covered_source_functions": [],
                    "covered_target_functions": [],
                    "missing_source_alignments": event.get("source_functions", []),
                    "non_public_alignments": [],
                    "missing_target_recipe": [],
                    "support_target_functions": event.get("target_functions", []),
                }
                continue

            event["alignment_validation"] = self._validate_operation_alignment(
                operation,
                {
                    **op,
                    "source_functions": event.get("source_functions", []),
                    "target_functions": event.get("target_functions", op.get("target_functions", [])),
                },
                alignment_stats,
            )

        replay_plan["summary"] = self._build_replay_plan_summary(replay_plan.get("events", []))
        replay_plan["schema_version"] = "3b.replay_plan.v1"
        return replay_plan

    def _validate_operation_alignment(self, operation, op, alignment_stats):
        pair_by_src = self._alignment_pairs_by_source(alignment_stats)
        source_functions = op.get("source_functions", [])
        recipe_targets = set(op.get("target_functions", []))
        expected_targets = set()
        covered_pairs = []
        covered_source_functions = set()
        covered_target_functions = set()
        missing_source_alignments = []
        non_public_alignments = []
        missing_target_recipe = []

        for src_uuid in source_functions:
            pair = pair_by_src.get(src_uuid)
            if not pair or not pair.get("tgt_uuids"):
                missing_source_alignments.append(src_uuid)
                continue

            if not pair.get("is_public_eligible"):
                non_public_alignments.append({
                    "src_uuid": src_uuid,
                    "tgt_uuids": pair.get("tgt_uuids", []),
                    "reason": "not_public_eligible",
                })
                continue

            expected_targets.update(pair.get("tgt_uuids", []))
            missing_for_src = []
            for tgt_uuid in pair.get("tgt_uuids", []):
                if tgt_uuid in recipe_targets:
                    covered_pairs.append({"src_uuid": src_uuid, "tgt_uuid": tgt_uuid})
                    covered_source_functions.add(src_uuid)
                    covered_target_functions.add(tgt_uuid)
                else:
                    missing_for_src.append(tgt_uuid)

            if missing_for_src:
                missing_target_recipe.append({
                    "src_uuid": src_uuid,
                    "expected_tgt_uuids": pair.get("tgt_uuids", []),
                    "missing_tgt_uuids": missing_for_src,
                })

        support_targets = sorted(recipe_targets - expected_targets)
        if not source_functions:
            status = "adapter_operation_empty"
        elif missing_source_alignments or non_public_alignments or missing_target_recipe:
            status = "partial_alignment" if covered_pairs else "missing_alignment"
        else:
            status = "fully_aligned"
        mapping_shape = self._mapping_shape(covered_source_functions, covered_target_functions)

        return {
            "operation": operation,
            "status": status,
            "mapping_shape": mapping_shape,
            "covered_pairs": covered_pairs,
            "covered_source_functions": sorted(covered_source_functions),
            "covered_target_functions": sorted(covered_target_functions),
            "missing_source_alignments": missing_source_alignments,
            "non_public_alignments": non_public_alignments,
            "missing_target_recipe": missing_target_recipe,
            "support_target_functions": support_targets,
        }

    def _mapping_shape(self, source_functions, target_functions):
        source_count = len(source_functions)
        target_count = len(target_functions)
        if source_count == 0 or target_count == 0:
            return "unvalidated"
        if source_count == 1 and target_count == 1:
            return "one_to_one"
        if source_count == 1:
            return "one_to_many"
        if target_count == 1:
            return "many_to_one"
        return "many_to_many"

    def _build_replay_plan_summary(self, events):
        planned_src = sorted({fn for event in events for fn in event.get("source_functions", [])})
        planned_tgt = sorted({fn for event in events for fn in event.get("target_functions", [])})
        validated_src = set()
        validated_tgt = set()
        covered_pair_keys = set()
        alignment_status_counts = {}
        mapping_shape_counts = {}
        support_targets = set()

        for event in events:
            validation = event.get("alignment_validation", {})
            status = validation.get("status", "not_validated")
            alignment_status_counts[status] = alignment_status_counts.get(status, 0) + 1
            mapping_shape = validation.get("mapping_shape", "not_validated")
            mapping_shape_counts[mapping_shape] = mapping_shape_counts.get(mapping_shape, 0) + 1
            validated_src.update(validation.get("covered_source_functions", []))
            validated_tgt.update(validation.get("covered_target_functions", []))
            support_targets.update(validation.get("support_target_functions", []))
            for pair in validation.get("covered_pairs", []):
                covered_pair_keys.add(f"{pair.get('src_uuid')}->{pair.get('tgt_uuid')}")

        return {
            "events": len(events),
            "planned_source_functions": len(planned_src),
            "planned_target_functions": len(planned_tgt),
            "planned_source_function_ids": planned_src,
            "planned_target_function_ids": planned_tgt,
            "validated_aligned_source_functions": len(validated_src),
            "validated_aligned_target_functions": len(validated_tgt),
            "validated_aligned_source_function_ids": sorted(validated_src),
            "validated_aligned_target_function_ids": sorted(validated_tgt),
            "covered_aligned_pairs": len(covered_pair_keys),
            "alignment_status_counts": alignment_status_counts,
            "mapping_shape_counts": mapping_shape_counts,
            "support_target_functions": sorted(support_targets),
        }

    def replay_public_plan(self, replay_plan, adapter, mode, work_root=None):
        if mode in {"inventory", "record"}:
            return {
                "status": "not_run",
                "reason": f"three_b_mode_{mode}",
                "events": [],
                "summary": self._empty_replay_summary(),
            }
        if replay_plan.get("status") != "recorded":
            return {
                "status": "not_run",
                "reason": replay_plan.get("skip_reason", "replay_plan_empty"),
                "events": [],
                "summary": self._empty_replay_summary(),
            }
        if adapter.get("status") != "loaded":
            return {
                "status": "not_run",
                "reason": adapter.get("status", "adapter_missing"),
                "events": [],
                "summary": self._empty_replay_summary(),
            }
        if adapter.get("target_language") != "rust":
            return {
                "status": "not_run",
                "reason": "target_language_not_supported_for_replay",
                "events": [],
                "summary": self._empty_replay_summary(),
            }

        base_work_root = Path(work_root) if work_root else self._resolve_work_root(None)
        run_dir = base_work_root / "latest"
        target_copy = run_dir / "target_repo"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        target_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.tgt_repo_path, target_copy, ignore=self._copy_ignore)

        tests_dir = target_copy / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_file = tests_dir / "cp2rs_3b_public.rs"
        harness = self._rust_public_test_from_adapter(adapter)
        test_file.write_text(harness, encoding="utf-8")

        cmd = adapter.get("target_test_command") or ["cargo", "test", "--test", "cp2rs_3b_public"]
        started = datetime.utcnow().isoformat() + "Z"
        cargo_started = time.monotonic()
        self._progress(
            "CARGO",
            f"执行 {' '.join(cmd)}; replay_plan_events={len(replay_plan.get('events', []))}; cwd={self._display_path(target_copy)}",
        )
        try:
            completed = subprocess.run(
                cmd,
                cwd=target_copy,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
            )
            returncode = completed.returncode
            full_stdout = completed.stdout or ""
            full_stderr = completed.stderr or ""
            stdout = full_stdout[-12000:]
            stderr = full_stderr[-12000:]
        except FileNotFoundError as exc:
            self._progress("CARGO", f"启动失败: {exc}")
            return self._infrastructure_replay_failure(str(exc), str(target_copy), str(test_file))
        except subprocess.TimeoutExpired as exc:
            self._progress("CARGO", f"超时: {exc}")
            return self._infrastructure_replay_failure(f"timeout: {exc}", str(target_copy), str(test_file))

        self._progress(
            "CARGO",
            f"结束: returncode={returncode}, elapsed={time.monotonic() - cargo_started:.1f}s",
        )

        if returncode != 0 and self._looks_like_infrastructure_failure(stdout, stderr):
            self._progress(
                "REPLAY-TRIAGE",
                f"整文件 replay 编译/环境失败，开始逐 event 隔离运行: events={len(replay_plan.get('events', []))}",
            )
            full_failure_summary = {
                "generated_test_file": self._display_path(test_file),
                "target_worktree": self._display_path(target_copy),
                "command": cmd,
                "started_at": started,
                "returncode": returncode,
                "failure_reason": "target_replay_build_or_environment_failure",
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            }
            return self._replay_public_plan_per_event(
                replay_plan=replay_plan,
                adapter=adapter,
                target_copy=target_copy,
                tests_dir=tests_dir,
                harness=harness,
                full_failure_summary=full_failure_summary,
            )

        events = []
        semantic_failures = []
        overall_status = "passed" if returncode == 0 else "failed"
        test_statuses = self._parse_rust_test_statuses(full_stdout)
        failed_test_names = self._parse_rust_failed_test_names(full_stdout)
        result_counts = self._parse_rust_test_result_counts(full_stdout)
        for event in replay_plan.get("events", []):
            event_status = self._status_for_replay_plan_event(
                event,
                test_statuses,
                overall_status,
                failed_test_names=failed_test_names,
                result_counts=result_counts,
                event_count=len(replay_plan.get("events", [])),
            )
            replay_event = {
                "id": event["id"],
                "operation": event["operation"],
                "status": event_status,
                "source_functions": event["source_functions"],
                "target_functions": event["target_functions"],
                "source_case_ids": event.get("source_case_ids", []),
                "alignment_validation": event.get("alignment_validation", {}),
                "expected_behavior_source": self._expected_behavior_source(event),
                "expected_behavior_confidence": self._expected_behavior_confidence(event),
                "expected": event.get("expected", {}),
            }
            events.append(replay_event)
            if event_status != "passed":
                semantic_failures.append(replay_event)

        summary = {
            "generated_test_file": self._display_path(test_file),
            "target_worktree": self._display_path(target_copy),
            "command": cmd,
            "started_at": started,
            "returncode": returncode,
            "executed": len(events),
            "passed": len([event for event in events if event.get("status") == "passed"]),
            "failed": len([event for event in events if event.get("status") != "passed"]),
            "infrastructure_failures": 0,
            "semantic_failures": len(semantic_failures),
            "parsed_test_statuses": test_statuses,
            "parsed_failed_test_names": sorted(failed_test_names),
            "parsed_test_result_counts": result_counts,
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        }
        return {"status": overall_status, "events": events, "summary": summary}

    def _replay_public_plan_per_event(
        self,
        replay_plan,
        adapter,
        target_copy,
        tests_dir,
        harness,
        full_failure_summary,
    ):
        spans = self._rust_test_block_spans_by_name(harness)
        support_source = self._rust_harness_support_source(harness)
        events = []
        per_event_infra = []
        per_event_outputs = {}
        started = datetime.utcnow().isoformat() + "Z"

        plan_events = [event for event in replay_plan.get("events", []) if isinstance(event, dict)]
        for index, plan_event in enumerate(plan_events, start=1):
            event_id = plan_event.get("id", "")
            block_info = spans.get(event_id)
            if not block_info:
                replay_event = self._replay_event_from_plan_event(
                    plan_event,
                    "infrastructure_failed",
                    extra={
                        "infrastructure_failure_reason": "generated_test_block_missing",
                    },
                )
                events.append(replay_event)
                per_event_infra.append({
                    "event_id": event_id,
                    "test_name": event_id,
                    "operation": plan_event.get("operation", ""),
                    "source_case_ids": plan_event.get("source_case_ids", []),
                    "failure_reason": "generated_test_block_missing",
                })
                continue

            test_stem = self._safe_replay_test_stem(event_id)
            event_test_file = tests_dir / f"{test_stem}.rs"
            event_test_source = (support_source.strip() + "\n\n" if support_source.strip() else "") + block_info[2].strip() + "\n"
            event_test_file.write_text(event_test_source, encoding="utf-8")
            cmd = ["cargo", "test", "--test", test_stem]
            started_event = time.monotonic()
            try:
                completed = subprocess.run(
                    cmd,
                    cwd=target_copy,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    check=False,
                )
                returncode = completed.returncode
                stdout = completed.stdout or ""
                stderr = completed.stderr or ""
            except FileNotFoundError as exc:
                returncode = 127
                stdout = ""
                stderr = str(exc)
            except subprocess.TimeoutExpired as exc:
                returncode = 124
                stdout = exc.stdout or ""
                stderr = str(exc)

            stdout_tail = stdout[-8000:]
            stderr_tail = stderr[-8000:]
            if returncode == 0:
                status = "passed"
            elif self._looks_like_infrastructure_failure(stdout_tail, stderr_tail) or returncode in {124, 127}:
                status = "infrastructure_failed"
            else:
                status = "failed"

            replay_event = self._replay_event_from_plan_event(plan_event, status)
            events.append(replay_event)
            per_event_outputs[event_id] = {
                "test_name": event_id,
                "test_file": self._display_path(event_test_file),
                "command": cmd,
                "returncode": returncode,
                "elapsed_seconds": round(time.monotonic() - started_event, 3),
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
            }
            if status == "infrastructure_failed":
                per_event_infra.append({
                    "event_id": event_id,
                    "test_name": event_id,
                    "operation": plan_event.get("operation", ""),
                    "source_case_ids": plan_event.get("source_case_ids", []),
                    "test_file": self._display_path(event_test_file),
                    "command": cmd,
                    "returncode": returncode,
                    "failure_reason": "isolated_event_build_or_environment_failure",
                    "stdout_tail": stdout_tail,
                    "stderr_tail": stderr_tail,
                })

            if index == len(plan_events) or index % 10 == 0:
                passed = len([event for event in events if event.get("status") == "passed"])
                failed = len([event for event in events if event.get("status") == "failed"])
                infra = len([event for event in events if event.get("status") == "infrastructure_failed"])
                self._progress(
                    "REPLAY-TRIAGE",
                    f"{index}/{len(plan_events)} passed={passed}, failed={failed}, infra={infra}",
                )

        passed = len([event for event in events if event.get("status") == "passed"])
        failed = len([event for event in events if event.get("status") == "failed"])
        infrastructure_failures = len(per_event_infra)
        executed = passed + failed
        if infrastructure_failures == len(events) and events:
            status = "infrastructure_failed"
        elif infrastructure_failures:
            status = "partial_infrastructure_failed"
        elif failed:
            status = "failed"
        else:
            status = "passed"

        summary = {
            "generated_test_file": full_failure_summary.get("generated_test_file", ""),
            "target_worktree": self._display_path(target_copy),
            "command": full_failure_summary.get("command", []),
            "started_at": started,
            "returncode": 0 if status == "passed" else 101,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "infrastructure_failures": infrastructure_failures,
            "semantic_failures": failed,
            "per_event_replay_used": True,
            "full_replay_failure": full_failure_summary,
            "per_event_infrastructure_failures": per_event_infra,
            "per_event_outputs": per_event_outputs,
            "stdout_tail": full_failure_summary.get("stdout_tail", ""),
            "stderr_tail": full_failure_summary.get("stderr_tail", ""),
        }
        return {
            "status": status,
            "reason": "isolated_event_replay_after_full_harness_infrastructure_failure",
            "events": events,
            "summary": summary,
        }

    def replay_public_plan_event_subset(
        self,
        replay_plan,
        adapter,
        mode,
        event_ids,
        work_root=None,
        run_label="repair_subset",
    ):
        wanted = {event_id for event_id in (event_ids or []) if event_id}
        if not wanted:
            return {
                "status": "not_run",
                "reason": "empty_repair_event_subset",
                "events": [],
                "summary": self._empty_replay_summary(),
            }
        subset_events = [
            event for event in replay_plan.get("events", [])
            if isinstance(event, dict) and event.get("id") in wanted
        ]
        subset_plan = json.loads(json.dumps(replay_plan))
        subset_plan["events"] = subset_events
        subset_plan.setdefault("summary", {})
        subset_plan["summary"]["events"] = len(subset_events)

        if not subset_events:
            return {
                "status": "not_run",
                "reason": "repair_event_subset_not_found_in_replay_plan",
                "events": [],
                "summary": self._empty_replay_summary(),
            }
        if mode in {"inventory", "record"}:
            return {
                "status": "not_run",
                "reason": f"three_b_mode_{mode}",
                "events": [],
                "summary": self._empty_replay_summary(),
            }

        base_work_root = Path(work_root) if work_root else self._resolve_work_root(None)
        run_dir = base_work_root / run_label
        target_copy = run_dir / "target_repo"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        target_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.tgt_repo_path, target_copy, ignore=self._copy_ignore)

        tests_dir = target_copy / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_file = tests_dir / "cp2rs_3b_public.rs"
        harness = self._rust_public_test_from_adapter(adapter)
        test_file.write_text(harness, encoding="utf-8")

        self._progress(
            "REPLAY-REPAIR",
            f"rerun repaired subset: events={len(subset_events)}, run_label={run_label}",
        )
        return self._replay_public_plan_per_event(
            replay_plan=subset_plan,
            adapter=adapter,
            target_copy=target_copy,
            tests_dir=tests_dir,
            harness=harness,
            full_failure_summary={
                "generated_test_file": self._display_path(test_file),
                "target_worktree": self._display_path(target_copy),
                "command": ["cargo", "test", "--test", "<per-event-repair-subset>"],
                "started_at": datetime.utcnow().isoformat() + "Z",
                "returncode": 101,
                "failure_reason": "targeted_repair_subset_replay",
                "stdout_tail": "",
                "stderr_tail": "",
            },
        )

    def _merge_replay_subset_result(self, previous_result, subset_result):
        previous_events = [
            event for event in (previous_result.get("events", []) if isinstance(previous_result, dict) else [])
            if isinstance(event, dict) and event.get("id")
        ]
        subset_events = [
            event for event in (subset_result.get("events", []) if isinstance(subset_result, dict) else [])
            if isinstance(event, dict) and event.get("id")
        ]
        merged_by_id = {event["id"]: event for event in previous_events}
        for event in subset_events:
            merged_by_id[event["id"]] = event
        ordered_ids = [event["id"] for event in previous_events]
        for event in subset_events:
            if event["id"] not in ordered_ids:
                ordered_ids.append(event["id"])
        merged_events = [merged_by_id[event_id] for event_id in ordered_ids if event_id in merged_by_id]

        previous_summary = dict((previous_result.get("summary", {}) or {}) if isinstance(previous_result, dict) else {})
        previous_infra = {
            item.get("event_id"): item
            for item in previous_summary.get("per_event_infrastructure_failures", []) or []
            if isinstance(item, dict) and item.get("event_id")
        }
        subset_infra = {
            item.get("event_id"): item
            for item in (subset_result.get("summary", {}) or {}).get("per_event_infrastructure_failures", []) or []
            if isinstance(item, dict) and item.get("event_id")
        }
        for event in subset_events:
            previous_infra.pop(event.get("id"), None)
        previous_infra.update(subset_infra)

        passed = len([event for event in merged_events if event.get("status") == "passed"])
        semantic_failed = len([
            event for event in merged_events
            if event.get("status") not in {"passed", "infrastructure_failed"}
        ])
        infrastructure_failures = len([
            event for event in merged_events if event.get("status") == "infrastructure_failed"
        ])
        executed = passed + semantic_failed
        if infrastructure_failures == len(merged_events) and merged_events:
            status = "infrastructure_failed"
        elif infrastructure_failures:
            status = "partial_infrastructure_failed"
        elif semantic_failed:
            status = "failed"
        else:
            status = "passed"

        merged_summary = previous_summary
        merged_summary.update({
            "executed": executed,
            "passed": passed,
            "failed": semantic_failed,
            "semantic_failures": semantic_failed,
            "infrastructure_failures": infrastructure_failures,
            "per_event_infrastructure_failures": list(previous_infra.values()),
            "last_repair_subset_summary": subset_result.get("summary", {}) if isinstance(subset_result, dict) else {},
            "per_event_replay_used": True,
        })
        return {
            "status": status,
            "reason": "merged_replay_result_after_targeted_repair_subset",
            "events": merged_events,
            "summary": merged_summary,
        }

    def _safe_replay_test_stem(self, event_id):
        safe = self._safe_identifier(event_id).lower()
        digest = hashlib.sha1(str(event_id).encode("utf-8")).hexdigest()[:8]
        if len(safe) > 48:
            safe = safe[:48].rstrip("_")
        return f"cp2rs_3b_{safe}_{digest}"

    def _replay_event_from_plan_event(self, event, status, extra=None):
        replay_event = {
            "id": event["id"],
            "operation": event["operation"],
            "status": status,
            "source_functions": event["source_functions"],
            "target_functions": event["target_functions"],
            "source_case_ids": event.get("source_case_ids", []),
            "alignment_validation": event.get("alignment_validation", {}),
            "expected_behavior_source": self._expected_behavior_source(event),
            "expected_behavior_confidence": self._expected_behavior_confidence(event),
            "expected": event.get("expected", {}),
        }
        if extra:
            replay_event.update(extra)
        return replay_event

    def _parse_rust_test_statuses(self, stdout):
        statuses = {}
        for match in re.finditer(r"^\s*test\s+([A-Za-z_][\w:]*)\s+\.\.\.\s+([A-Z]+|ok|ignored)\s*$", stdout or "", flags=re.M):
            raw_name, raw_status = match.groups()
            normalized = "passed" if raw_status == "ok" else raw_status.lower()
            statuses[raw_name] = normalized
            statuses[raw_name.rsplit("::", 1)[-1]] = normalized
        return statuses

    def _parse_rust_failed_test_names(self, stdout):
        failed = set()
        in_failures = False
        for line in (stdout or "").splitlines():
            if line.strip() == "failures:":
                in_failures = True
                continue
            if not in_failures:
                continue
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("test result:"):
                break
            if re.match(r"^[A-Za-z_][A-Za-z0-9_:]*$", stripped):
                failed.add(stripped)
                failed.add(stripped.rsplit("::", 1)[-1])
        return failed

    def _parse_rust_test_result_counts(self, stdout):
        match = re.search(
            r"test result:\s+(\w+)\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored",
            stdout or "",
        )
        if not match:
            return {}
        status, passed, failed, ignored = match.groups()
        return {
            "status": status,
            "passed": int(passed),
            "failed": int(failed),
            "ignored": int(ignored),
        }

    def _status_for_replay_plan_event(
        self,
        event,
        test_statuses,
        overall_status,
        failed_test_names=None,
        result_counts=None,
        event_count=0,
    ):
        event_id = event.get("id", "")
        if event_id in test_statuses:
            status = test_statuses[event_id]
            return "passed" if status == "passed" else "failed"
        failed_test_names = failed_test_names or set()
        if event_id in failed_test_names:
            return "failed"
        result_counts = result_counts or {}
        if (
            overall_status == "failed"
            and failed_test_names
            and result_counts.get("failed") == len({name for name in failed_test_names if "::" not in name})
            and result_counts.get("passed", 0) + result_counts.get("failed", 0) == event_count
        ):
            return "passed"
        return "passed" if overall_status == "passed" else "failed_unmapped"

    def _looks_like_infrastructure_failure(self, stdout, stderr):
        combined = f"{stdout}\n{stderr}".lower()
        compile_or_environment_markers = [
            "could not compile",
            "compilation failed",
            "failed to resolve",
            "no such file or directory",
            "could not find",
            "error: failed",
        ]
        if any(marker in combined for marker in compile_or_environment_markers):
            return True
        return "error[" in combined and "running tests" not in combined

    def _copy_ignore(self, dirname, names):
        ignored = {".git", "target"}
        return [name for name in names if name in ignored]

    def _infrastructure_replay_failure(self, reason, target_copy, test_file):
        summary = self._empty_replay_summary()
        summary.update({
            "target_worktree": self._display_path(target_copy),
            "generated_test_file": self._display_path(test_file),
            "infrastructure_failures": 1,
            "failure_reason": reason,
        })
        return {
            "status": "infrastructure_failed",
            "reason": reason,
            "events": [],
            "summary": summary,
        }

    def _has_replay_infrastructure_failures(self, replay_result):
        if not isinstance(replay_result, dict):
            return False
        summary = replay_result.get("summary", {}) or {}
        return (
            replay_result.get("status") in {"infrastructure_failed", "partial_infrastructure_failed"}
            or int(summary.get("infrastructure_failures", 0) or 0) > 0
            or any(
                isinstance(event, dict) and event.get("status") == "infrastructure_failed"
                for event in replay_result.get("events", [])
            )
        )

    def _empty_replay_summary(self):
        return {
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "semantic_failures": 0,
            "infrastructure_failures": 0,
        }

    def _rust_public_test_from_adapter(self, adapter):
        if adapter and adapter.get("replay_generator") == "rust_inline_harness_v1":
            return self._rust_inline_harness_from_adapter(adapter)
        return """#[test]
fn cp2rs_3b_missing_generated_harness() {
    panic!("3B requires replay_generator=rust_inline_harness_v1");
}
"""

    def _rust_inline_harness_from_adapter(self, adapter):
        harness = adapter.get("rust_test_harness", "")
        if not harness and isinstance(adapter.get("target_replay_harness"), dict):
            harness = adapter.get("target_replay_harness", {}).get("rust_test_file", "")
        harness = self._strip_markdown_fence(harness)
        if not harness.strip():
            return """#[test]
fn cp2rs_3b_missing_generated_harness() {
    panic!("3B adapter replay_generator=rust_inline_harness_v1 but rust_test_harness is empty");
}
"""
        return self._sanitize_rust_harness(harness)

    def _sanitize_rust_harness(self, harness):
        if not isinstance(harness, str) or not harness:
            return harness or ""
        sanitized = self._strip_markdown_fence(harness)
        sanitized = self._fix_rust_adjacent_string_literals(sanitized)
        sanitized = self._fix_rust_string_literal_syntax(sanitized)
        sanitized = self._fix_rust_index_mut_alias_borrows(sanitized)
        sanitized = self._fix_rust_index_mut_assignment(sanitized)
        sanitized = self._inject_rust_trait_imports(sanitized)
        return sanitized

    def _fix_rust_index_mut_alias_borrows(self, code):
        lines = code.splitlines()
        fixed_lines = []
        aliases = {}
        alias_decl_re = re.compile(
            r'^(\s*)let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*'
            r'([A-Za-z_][A-Za-z0-9_]*)\.index_mut\(([^;]+)\);\s*$'
        )
        method_use_template = r'\b{var}\s*\.'
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#[test]") or re.match(r'fn\s+[A-Za-z_][A-Za-z0-9_]*\s*\(', stripped):
                aliases = {}
            match = alias_decl_re.match(line)
            if match:
                indent, var_name, receiver, index_expr = match.groups()
                key_name = f"{var_name}_cp2rs_index_key"
                aliases[var_name] = (receiver, key_name)
                fixed_lines.append(f"{indent}let {key_name} = {index_expr};")
                continue
            fixed = line
            for var_name, (receiver, key_name) in aliases.items():
                fixed = re.sub(
                    method_use_template.format(var=re.escape(var_name)),
                    f"{receiver}.index_mut({key_name}).",
                    fixed,
                )
            fixed_lines.append(fixed)
        return "\n".join(fixed_lines) + ("\n" if code.endswith("\n") else "")

    def _fix_rust_index_mut_assignment(self, code):
        fixed_lines = []
        assignment_re = re.compile(r'^(\s*)([^=;]+\.index_mut\([^;]+\))\s*=\s*([^;]+;\s*)$')
        for line in code.splitlines():
            match = assignment_re.match(line)
            if match and not match.group(2).lstrip().startswith("*"):
                fixed_lines.append(f"{match.group(1)}*{match.group(2).strip()} = {match.group(3)}")
            else:
                fixed_lines.append(line)
        return "\n".join(fixed_lines) + ("\n" if code.endswith("\n") else "")

    def _inject_rust_trait_imports(self, code):
        if not isinstance(code, str) or not code.strip():
            return code
        if "CP2RS replay harness imports" in code:
            return code

        top_level_prefix = code.split("#[test]", 1)[0]
        existing_use_block = "\n".join(
            line.strip()
            for line in top_level_prefix.splitlines()
            if line.strip().startswith("use ")
        )
        if not (
            re.search(r'\.index(?:_mut)?\s*\(', code)
            and "std::ops::Index" not in existing_use_block
            and "std::ops::{Index" not in existing_use_block
        ):
            return code

        imports = "\n".join([
            "// CP2RS replay harness imports: Rust trait imports only.",
            "use std::ops::{Index, IndexMut};",
        ])
        return f"{imports}\n\n{code.lstrip()}"

    def _fix_rust_adjacent_string_literals(self, code):
        lines = code.splitlines()
        fixed = []
        i = 0
        literal = r'(?:r#+".*?"#+|r".*?"|"(?:\\.|[^"\\])*")'
        assign_re = re.compile(
            rf'^(\s*let\s+(?:mut\s+)?[A-Za-z_][A-Za-z0-9_]*(?:\s*:\s*[^=]+)?\s*=\s*)({literal})\s*$'
        )
        cont_re = re.compile(rf'^(\s*)({literal})(\s*;\s*)$|^(\s*)({literal})\s*$')
        while i < len(lines):
            line = lines[i]
            match = assign_re.match(line)
            if not match:
                fixed.append(line)
                i += 1
                continue
            prefix, first_literal = match.groups()
            parts = [first_literal]
            j = i + 1
            end_semicolon = False
            while j < len(lines):
                cont = cont_re.match(lines[j])
                if not cont:
                    break
                literal_part = cont.group(2) or cont.group(5)
                semicolon = cont.group(3)
                parts.append(literal_part)
                j += 1
                if semicolon:
                    end_semicolon = True
                    break
            if len(parts) <= 1 or not end_semicolon:
                fixed.append(line)
                i += 1
                continue
            indent = re.match(r'^(\s*)', line).group(1)
            fixed.append(f"{prefix}concat!(")
            for part in parts:
                fixed.append(f"{indent}    {part},")
            fixed.append(f"{indent});")
            i = j
        return "\n".join(fixed) + ("\n" if code.endswith("\n") else "")

    def _fix_rust_string_literal_syntax(self, code):
        fixed_lines = []
        raw_re = re.compile(r'^(?P<prefix>\s*(?:let\s+(?:mut\s+)?[A-Za-z_][A-Za-z0-9_]*(?:\s*:\s*[^=]+)?\s*=\s*|[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*)?)r"(?P<body>.*)"(?P<suffix>\s*[),;]\s*)$')
        for line in code.splitlines():
            fixed = line
            raw_match = raw_re.match(fixed)
            if raw_match and '"' in raw_match.group("body") and "#\"" not in fixed:
                fixed = (
                    f'{raw_match.group("prefix")}r#"{raw_match.group("body")}"#'
                    f'{raw_match.group("suffix")}'
                )
            fixed = fixed.replace(r'"\b"', r'"\x08"')
            fixed = fixed.replace(r'"\f"', r'"\x0c"')
            fixed_lines.append(fixed)
        return "\n".join(fixed_lines) + ("\n" if code.endswith("\n") else "")

    def _strip_markdown_fence(self, text):
        text = (text or "").strip()
        match = re.search(r"```(?:rust|rs)?\s*(.*?)\s*```", text, flags=re.S)
        if match:
            return match.group(1).strip() + "\n"
        return text + ("\n" if text else "")

    def _function_boundary_status(self, layer, alignment_stats):
        skipped = alignment_stats.get("skipped_private_internal", [])
        if layer == "public":
            return {
                "status": "skipped_by_default",
                "reason": "public_first_layer_selected",
                "skipped_private_internal_count": len(skipped),
                "skipped_private_internal": skipped[:50],
            }
        return {
            "status": "not_implemented",
            "reason": "function_boundary_replay_requires_explicit wrappers/adapters",
            "skipped_private_internal_count": len(skipped),
            "skipped_private_internal": skipped[:50],
        }

    def _build_report(
        self,
        mode,
        layer,
        alignment_stats,
        adapter,
        inventory,
        replay_plan,
        replay_result,
        function_boundary,
        artifacts_path=None,
    ):
        replay_plan_summary = replay_plan.get("summary", {})
        public_plan_src = set(replay_plan_summary.get("validated_aligned_source_function_ids", []))
        public_plan_tgt = set(replay_plan_summary.get("validated_aligned_target_function_ids", []))
        aligned_src = set(alignment_stats.get("unique_aligned_source_functions", []))
        public_eligible_src = set(alignment_stats.get("public_eligible_source_functions", []))
        public_eligible_tgt = set(alignment_stats.get("public_eligible_target_functions", []))
        tested_aligned_src = self._source_functions_with_test_evidence(
            inventory,
            aligned_src,
            call_field="calls_aligned_functions",
        )
        public_leaf_tested_src = self._source_functions_with_test_evidence(inventory, public_eligible_src)
        tested_public_src = self._source_functions_with_test_evidence(
            inventory,
            public_eligible_src,
            require_precise_behavior=True,
        )
        if self._source_functions_with_precise_behavior_evidence(public_eligible_src) is None:
            tested_public_src = tested_public_src | (tested_aligned_src & public_eligible_src)
        tested_public_tgt = self._target_functions_for_sources(alignment_stats, tested_public_src)
        excluded_no_src_test = sorted(aligned_src - tested_aligned_src)
        excluded_public_no_src_test = sorted(public_eligible_src - tested_public_src)
        excluded_public_no_observed_src_test = sorted(public_eligible_src - public_leaf_tested_src)
        excluded_public_no_precise_behavior = sorted(public_leaf_tested_src - tested_public_src)
        source_tested_non_public_internal = sorted(tested_aligned_src - public_eligible_src)
        mixed_public_internal_cases = self._mixed_public_internal_cases(inventory)
        adapter_src = set()
        for operation in adapter.get("public_operations", {}).values():
            adapter_src.update(operation.get("source_functions", []))

        adapter_missing_src = sorted(tested_public_src - public_plan_src)
        adapter_missing_count = len(adapter_missing_src)
        replay_summary = replay_result.get("summary", {})
        semantic_failures = [
            event for event in replay_result.get("events", [])
            if event.get("status") not in {"passed", "infrastructure_failed"}
        ]
        semantic_failure_reviews = self._semantic_failure_reviews(semantic_failures, adapter)
        infrastructure_failures = list(replay_summary.get("per_event_infrastructure_failures", []) or [])
        if replay_result.get("status") == "infrastructure_failed" and not infrastructure_failures:
            infrastructure_failures.append(replay_summary)
        behavior_case_coverage = self._adapter_behavior_case_coverage(adapter)
        adapter_conversion_unresolved = self._adapter_conversion_unresolved_cases(
            behavior_case_coverage.get("missing_behavior_case_ids", []),
        )
        metrics = self._build_metrics(
            replay_summary=replay_summary,
            public_plan_src=public_plan_src,
            public_plan_tgt=public_plan_tgt,
            public_eligible_src=public_eligible_src,
            public_eligible_tgt=public_eligible_tgt,
            tested_public_src=tested_public_src,
            public_leaf_tested_src=public_leaf_tested_src,
            tested_public_tgt=tested_public_tgt,
            excluded_no_src_test=excluded_no_src_test,
            aligned_src=aligned_src,
            tested_aligned_src=tested_aligned_src,
            excluded_public_no_src_test=excluded_public_no_src_test,
            excluded_public_no_observed_src_test=excluded_public_no_observed_src_test,
            excluded_public_no_precise_behavior=excluded_public_no_precise_behavior,
            source_tested_non_public_internal=source_tested_non_public_internal,
            mixed_public_internal_case_count=len(mixed_public_internal_cases),
            adapter_missing_count=adapter_missing_count,
            skipped_private_internal_count=len(alignment_stats.get("skipped_private_internal", [])),
            replay_plan_summary=replay_plan_summary,
            semantic_failure_reviews=semantic_failure_reviews,
        )
        metrics.setdefault("basic_counts", {}).update({
            "source_behavior_cases_available": behavior_case_coverage.get("available_behavior_case_count", 0),
            "source_behavior_cases_eligible_for_replay": behavior_case_coverage.get("required_behavior_case_count", 0),
            "source_behavior_cases_replayed": behavior_case_coverage.get("replayed_behavior_case_count", 0),
            "source_behavior_cases_excluded_by_adapter_conversion": behavior_case_coverage.get("excluded_behavior_case_count", 0),
            "source_behavior_cases_unresolved_after_conversion": behavior_case_coverage.get("missing_behavior_case_count", 0),
        })
        eligibility = self._public_replay_eligibility or {}
        eligibility_summary = eligibility.get("summary", {})
        metrics.setdefault("ratio_metrics", {})["behavior_case_accounting_rate"] = self._ratio(
            behavior_case_coverage.get("replayed_behavior_case_count", 0)
            + behavior_case_coverage.get("excluded_behavior_case_count", 0),
            behavior_case_coverage.get("required_behavior_case_count", 0),
            "eligible source behavior cases 中，已 replay 或经有效原因排除的比例",
        )
        metrics.setdefault("ratio_metrics", {})["behavior_case_replay_coverage"] = self._ratio(
            behavior_case_coverage.get("replayed_behavior_case_count", 0),
            behavior_case_coverage.get("required_behavior_case_count", 0),
            "eligible source behavior cases 中，成功转换为 replay event 并进入 Rust replay plan 的比例",
        )
        automation_readiness = self._automation_readiness(
            mode=mode,
            adapter=adapter,
            replay_result=replay_result,
            metrics=metrics,
            semantic_failure_reviews=semantic_failure_reviews,
            replay_plan_summary=replay_plan_summary,
        )
        replay_event_summaries = self._public_replay_event_summaries(adapter, replay_result)
        target_replay_summary = self._target_replay_summary(adapter, replay_plan, replay_result)
        key_findings = self._key_findings(
            failed_replay_event_reviews=semantic_failure_reviews,
            replay_event_summaries=replay_event_summaries,
            unresolved_conversion_cases=adapter_conversion_unresolved,
            infrastructure_failures=infrastructure_failures,
        )
        source_test_selection = self._compact_report_dict({
            "summary": self._compact_report_dict({
                "test_files_discovered": inventory.get("summary", {}).get("test_files", 0),
                "source_test_cases_discovered": eligibility_summary.get("discovered_source_test_cases", 0),
                "aligned_public_test_candidates": eligibility_summary.get("aligned_public_test_candidates", 0),
                "cases_unresolved_after_exact_function_binding": len(
                    eligibility.get("cases_unresolved_after_exact_function_binding", []) or []
                ),
                "structurally_ineligible_for_public_replay_cases": eligibility_summary.get(
                    "structurally_ineligible_for_public_replay_cases", 0
                ),
                "public_replay_eligible_cases": behavior_case_coverage.get("required_behavior_case_count", 0),
                "cases_excluded_by_adapter_conversion": behavior_case_coverage.get("excluded_behavior_case_count", 0),
                "unresolved_after_conversion_attempts": behavior_case_coverage.get("missing_behavior_case_count", 0),
                "replayed_cases": behavior_case_coverage.get("replayed_behavior_case_count", 0),
                "mixed_public_internal_candidates": eligibility_summary.get("mixed_public_internal_candidates", 0),
                "mixed_cases_eligible_with_public_substitution": eligibility_summary.get(
                    "mixed_cases_eligible_with_public_substitution", 0
                ),
                "case_conversion_attempt_mode": self._last_completion_budget.get("mode", ""),
            }),
            "adapter_event_binding_checks": self._adapter_event_binding_checks(behavior_case_coverage),
            "details": {
                "test_inventory": "artifact_paths.test_inventory",
                "public_replay_eligibility": "artifact_paths.public_replay_eligibility",
                "failed_replay_source_cases": "key_findings.failed_replay_events[].source_cases",
                "unresolved_behavior_cases": "key_findings.unresolved_behavior_cases",
            },
        })
        infrastructure_repair = self._compact_report_dict({
            "max_attempts": self.replay_repair_attempts,
            "unresolved_case_count": len(self._replay_infrastructure_unresolved_case_ids),
            "unresolved_source_behavior_case_ids": self._replay_infrastructure_unresolved_case_ids,
            "details": "Only present when replay infrastructure failures remain after repair attempts.",
        })
        target_replay = self._compact_report_dict({
            "summary": target_replay_summary,
            "infrastructure_failures": infrastructure_failures,
            "infrastructure_repair": (
                infrastructure_repair
                if self._replay_infrastructure_unresolved_case_ids
                or infrastructure_failures
                else {}
            ),
            "details": {
                "failed_replay_events": "key_findings.failed_replay_events",
                "full_replay_result": "artifact_paths.replay_result",
                "full_replay_plan": "artifact_paths.replay_plan",
                "generated_rust_tests": "artifact_paths.generated_test_file",
            },
        })

        return {
            "evaluation_type": "Phase 3B - Trace Replay Public-First",
            "schema_version": "3b.report.v32",
            "source_repository": self.src_name,
            "target_repository": self.tgt_name,
            "mode": mode,
            "layer": layer,
            "artifact_paths": self._artifact_paths(artifacts_path),
            "automation_readiness": automation_readiness,
            "key_findings": key_findings,
            "source_test_selection": source_test_selection,
            "target_replay": target_replay,
            "adapter": self._compact_report_dict({
                "schema_version": adapter.get("adapter_schema_version", ""),
                "name": adapter.get("name", ""),
                "status": adapter.get("status", ""),
                "generation_status": adapter.get("generation_status", ""),
                "resolution": adapter.get("_adapter_resolution", ""),
                "validation_status": adapter.get("_validation_status", ""),
                "validation_errors": adapter.get("_validation_errors", []),
                "summary": self._adapter_summary(adapter),
                "path": self._display_path(
                    adapter.get("_adapter_source_path", str(self.adapter_path) if self.adapter_path else "")
                ),
            }),
            "llm_usage": self._report_llm_usage(),
            "metrics": metrics,
        }

    def _adapter_summary(self, adapter):
        operations = adapter.get("public_operations", {})
        if not isinstance(operations, dict):
            operations = {}
        events = adapter.get("trace_events", [])
        if not isinstance(events, list):
            events = []
        referenced_operations = {
            event.get("operation")
            for event in events
            if isinstance(event, dict) and event.get("operation")
        }
        return {
            "public_operation_count": len(operations),
            "trace_event_count": len(events),
            "referenced_operation_count": len(referenced_operations),
            "unreferenced_operation_count": len(set(operations) - referenced_operations),
        }

    def _adapter_event_binding_checks(self, behavior_case_coverage):
        checks = {
            "unknown_source_behavior_case_ids": behavior_case_coverage.get("unknown_source_case_ids", []),
            "replayed_and_excluded_source_behavior_case_ids": behavior_case_coverage.get("replayed_and_excluded_case_ids", []),
            "invalid_event_case_bindings": behavior_case_coverage.get("invalid_event_case_bindings", []),
            "invalid_excluded_behavior_cases": behavior_case_coverage.get("invalid_excluded_behavior_cases", []),
            "events_without_source_behavior_case_ids": behavior_case_coverage.get("events_without_source_case_ids", []),
        }
        return self._compact_report_dict(checks)

    def _report_llm_usage(self):
        usage = self._rename_report_terms(json.loads(json.dumps(self._llm_usage)))
        return self._compact_report_dict({
            "calls": usage.get("calls", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "elapsed_seconds": usage.get("elapsed_seconds", 0.0),
            "usage_source": usage.get("usage_source", ""),
            "calls_by_stage": usage.get("calls_by_stage", {}),
            "full_usage_artifact": "artifact_paths.llm_usage",
        })

    def _rename_report_terms(self, value):
        if isinstance(value, str):
            replacements = {
                "adapter_case_generation": "behavior_case_conversion",
                "unresolved_adapter_generation": "unresolved_behavior_case_conversion",
            }
            for old, new in replacements.items():
                value = value.replace(old, new)
            return value
        if isinstance(value, list):
            return [self._rename_report_terms(item) for item in value]
        if isinstance(value, dict):
            return {
                self._rename_report_terms(key): self._rename_report_terms(item)
                for key, item in value.items()
            }
        return value

    def _key_findings(
        self,
        failed_replay_event_reviews,
        replay_event_summaries,
        unresolved_conversion_cases,
        infrastructure_failures,
    ):
        reviews_by_event = {
            item.get("replay_event_id"): item
            for item in failed_replay_event_reviews or []
            if isinstance(item, dict) and item.get("replay_event_id")
        }
        failed_events = [
            event for event in replay_event_summaries or []
            if isinstance(event, dict) and event.get("status") != "passed"
        ]
        return self._compact_report_dict({
            "failed_replay_events": [
                self._failed_replay_event_finding(event, reviews_by_event.get(event.get("replay_event_id"), {}))
                for event in failed_events
            ],
            "unresolved_behavior_cases": [
                self._unresolved_behavior_case_finding(item)
                for item in unresolved_conversion_cases or []
            ],
            "infrastructure_failures": infrastructure_failures,
        })

    def _failed_replay_event_finding(self, event, review):
        source_cases = self._source_case_briefs_for_event(event, max_cases=4)
        return self._compact_report_dict({
            "replay_event_id": event.get("replay_event_id", ""),
            "operation": event.get("operation", ""),
            "status": event.get("status", ""),
            "review_status": review.get("review_status", ""),
            "review_reason": review.get("reason", ""),
            "source_cases": source_cases,
            "aligned_source_functions": event.get("aligned_source_functions", []),
            "aligned_target_functions": event.get("aligned_target_functions", []),
            "support_target_functions_used": event.get("support_target_functions_used", []),
            "mapping_shape": event.get("mapping_shape", ""),
            "expected_behavior_source": event.get("expected_behavior_source") or review.get("expected_behavior_source", ""),
            "expected_behavior_confidence": event.get("expected_behavior_confidence") or review.get("expected_behavior_confidence", ""),
            "input": event.get("input", {}),
            "expected": event.get("expected") or review.get("expected", {}),
            "normalization": event.get("normalization", ""),
            "evidence": event.get("evidence", ""),
        })

    def _source_case_briefs_for_event(self, event, max_cases=4):
        context = self._last_synthesis_context or {}
        behavior_cases = context.get("source_evidence", {}).get("behavior_cases", [])
        if not isinstance(behavior_cases, list):
            behavior_cases = []
        return [
            self._source_case_brief(case)
            for case in self._source_cases_for_replay_event(event, behavior_cases, max_cases=max_cases)
        ]

    def _source_case_brief(self, case):
        return self._compact_report_dict({
            "source_behavior_case_id": case.get("case_id", ""),
            "name": case.get("name", ""),
            "source_location": self._source_location(case),
            "details_artifact": "artifact_paths.adapter_synthesis_context",
        })

    def _unresolved_behavior_case_finding(self, item):
        return self._compact_report_dict({
            "source_behavior_case_id": item.get("source_behavior_case_id", ""),
            "name": item.get("name", ""),
            "source_location": self._source_location(item),
            "aligned_source_functions": item.get("aligned_source_functions", []),
            "reason": item.get("reason", ""),
            "attempt_count": item.get("attempt_count", 0),
            "last_attempt_stage": item.get("last_attempt_stage", ""),
            "last_attempt_outcome": item.get("last_attempt_outcome", ""),
            "last_errors": item.get("last_errors", [])[:5],
            "details_artifact": "artifact_paths.adapter_synthesis_context",
        })

    def _adapter_conversion_unresolved_cases(self, missing_case_ids):
        detail_index = getattr(self, "_last_behavior_case_details", {}) or {}
        unresolved = []
        for case_id in missing_case_ids or []:
            case = detail_index.get(case_id, {})
            attempt = self._case_conversion_attempts.get(case_id, {})
            attempts = attempt.get("attempts", [])
            last_attempt = attempts[-1] if attempts else {}
            unresolved.append({
                "source_behavior_case_id": case_id,
                "name": case.get("name", ""),
                "path": case.get("path", ""),
                "start_line": case.get("start_line"),
                "aligned_source_functions": case.get("aligned_source_functions", []),
                "reason": (
                    "unresolved_behavior_case_conversion"
                    if attempts
                    else "not_covered_by_existing_adapter"
                ),
                "attempt_count": attempt.get("attempt_count", 0),
                "last_attempt_stage": last_attempt.get("stage", ""),
                "last_attempt_outcome": last_attempt.get("outcome", ""),
                "last_errors": last_attempt.get("errors", []),
            })
        return unresolved

    def _public_replay_event_summaries(self, adapter, replay_result):
        trace_events = {
            event.get("id"): event
            for event in adapter.get("trace_events", [])
            if isinstance(event, dict) and event.get("id")
        }
        operations = adapter.get("public_operations", {}) if isinstance(adapter.get("public_operations"), dict) else {}
        summaries = []
        for event in replay_result.get("events", []):
            event_id = event.get("id", "")
            trace_event = trace_events.get(event_id, {})
            operation_name = event.get("operation") or trace_event.get("operation", "")
            operation = operations.get(operation_name, {}) if isinstance(operations, dict) else {}
            alignment = event.get("alignment_validation", {}) or {}
            adapter_source_functions = event.get("source_functions", [])
            adapter_target_recipe_functions = event.get("target_functions", [])
            summary = {
                "replay_event_id": event_id,
                "operation": operation_name,
                "status": event.get("status", ""),
                "aligned_source_functions": alignment.get("covered_source_functions", []),
                "aligned_target_functions": alignment.get("covered_target_functions", []),
                "mapping_shape": alignment.get("mapping_shape", ""),
                "alignment_status": alignment.get("status", ""),
                "source_behavior_case_ids": event.get("source_case_ids") or trace_event.get("source_case_ids", []),
            }
            if event.get("status") != "passed":
                summary.update({
                    "support_target_functions_used": alignment.get("support_target_functions", []),
                    "operation_source_functions": adapter_source_functions,
                    "operation_target_functions": adapter_target_recipe_functions,
                    "evidence": trace_event.get("evidence", operation.get("evidence", [])),
                    "input": trace_event.get("input", {}),
                    "expected": event.get("expected") or trace_event.get("expected", {}),
                    "expected_behavior_source": (
                        self._expected_behavior_source(event)
                        or self._expected_behavior_source(trace_event)
                    ),
                    "expected_behavior_confidence": (
                        self._expected_behavior_confidence(event)
                        or self._expected_behavior_confidence(trace_event)
                    ),
                    "normalization": operation.get("normalization", ""),
                })
            summaries.append(self._compact_report_dict(summary))
        return summaries

    def _source_cases_for_replay_event(self, event, behavior_cases, max_cases=8):
        exact = []
        fallback = []
        event_case_ids = {
            str(case_id).lower()
            for case_id in (
                event.get("source_behavior_case_ids")
                or event.get("source_case_ids")
                or []
            )
            if case_id
        }
        event_haystack = " ".join([
            str(event.get("replay_event_id", event.get("id", ""))),
            str(event.get("operation", "")),
            str(event.get("evidence", "")),
            json.dumps(event.get("input", {}), ensure_ascii=False),
            json.dumps(event.get("expected", {}), ensure_ascii=False),
        ]).lower()
        event_sources = set(event.get("aligned_source_functions", []))
        for case in behavior_cases:
            if not isinstance(case, dict):
                continue
            case_name = str(case.get("name", "")).lower()
            case_id = str(case.get("case_id", "")).lower()
            if case_id and case_id in event_case_ids:
                exact.append(case)
                continue
            if (case_name and case_name in event_haystack) or (case_id and case_id in event_haystack):
                exact.append(case)
                continue
            if event_sources and event_sources & set(case.get("aligned_source_functions", [])):
                fallback.append(case)
        return (exact or fallback)[:max_cases]

    def _compact_report_dict(self, data):
        compacted = {}
        for key, value in data.items():
            if value is None or value == "" or value == [] or value == {} or value is False:
                continue
            compacted[key] = value
        return compacted

    def _source_location(self, case):
        path = case.get("path", "")
        line = case.get("start_line")
        return f"{path}:{line}" if path and line else path

    def _target_replay_summary(self, adapter, replay_plan, replay_result):
        replay_summary = replay_result.get("summary", {}) or {}
        replay_plan_event_ids = [
            str(event.get("id", ""))
            for event in replay_plan.get("events", [])
            if isinstance(event, dict) and event.get("id")
        ]
        operations = [
            str(event.get("operation", ""))
            for event in replay_plan.get("events", [])
            if isinstance(event, dict) and event.get("operation")
        ]
        fingerprint_payload = {
            "adapter_generation_status": adapter.get("generation_status", ""),
            "event_ids": replay_plan_event_ids,
            "operations": operations,
            "replay_plan_alignment_status_counts": replay_plan.get("summary", {}).get("alignment_status_counts", {}),
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]

        command = replay_summary.get("command", [])
        if isinstance(command, list):
            command = " ".join(str(part) for part in command)

        return self._compact_report_dict({
            "status": replay_result.get("status"),
            "replay_plan_fingerprint": fingerprint,
            "replay_events_in_plan": len(replay_plan_event_ids),
            "adapter_generation_status": adapter.get("generation_status", ""),
            "command": command,
            "returncode": replay_summary.get("returncode"),
            "replay_events_executed": replay_summary.get("executed", 0),
            "replay_events_passed": replay_summary.get("passed", 0),
            "replay_events_failed": replay_summary.get("failed", 0),
            "infrastructure_failures": replay_summary.get("infrastructure_failures", 0),
            "note": (
                "public_replay_pass_rate only describes this replay plan; compare "
                "replay_plan_fingerprint across runs before comparing pass rates."
            ),
        })

    def _mixed_public_internal_cases(self, inventory):
        cases = []
        for entry in inventory.get("test_files", []):
            for case in entry.get("aligned_test_cases", []):
                if not case.get("has_mixed_public_internal_calls"):
                    continue
                cases.append({
                    "path": case.get("path", entry.get("path", "")),
                    "framework": case.get("framework", ""),
                    "name": case.get("name", ""),
                    "calls_aligned_public_functions": case.get("calls_aligned_public_functions", []),
                    "calls_aligned_non_public_functions": case.get("calls_aligned_non_public_functions", []),
                })
        return cases

    def _automation_readiness(
        self,
        mode,
        adapter,
        replay_result,
        metrics,
        semantic_failure_reviews,
        replay_plan_summary,
    ):
        counts = metrics.get("basic_counts", {})
        reasons = []
        review_items = []
        coverage_gaps = []
        positive_evidence = []

        executed = counts.get("replay_events_executed", 0)
        passed = counts.get("replay_events_passed", 0)
        infrastructure_failures = counts.get("infrastructure_failures", 0)
        failed_replay_events = counts.get("replay_events_failed", 0)
        expected_behavior_review_required = len([
            item for item in semantic_failure_reviews
            if item.get("review_status") == "expected_behavior_review_required"
        ])
        target_semantic_candidates = len([
            item for item in semantic_failure_reviews
            if item.get("review_status") == "target_semantic_failure_candidate"
        ])
        adapter_missing = counts.get("source_tested_public_functions_not_replayed", 0)
        missing_behavior_cases = counts.get("source_behavior_cases_unresolved_after_conversion", 0)
        alignment_status_counts = replay_plan_summary.get("alignment_status_counts", {})
        partial_alignment = alignment_status_counts.get("partial_alignment", 0)
        missing_alignment = alignment_status_counts.get("missing_alignment", 0)
        scoped_sources = counts.get("public_source_functions_with_precise_behavior_evidence_l1_scope", 0)
        planned_sources = counts.get("validated_aligned_source_functions_replayed", 0)

        if adapter.get("status") != "loaded":
            reasons.append(f"adapter_status={adapter.get('status', 'unknown')}")
        if mode in {"inventory", "record"} or replay_result.get("status") == "not_run":
            reasons.append("target_replay_not_executed")
        if infrastructure_failures:
            reasons.append("target_replay_infrastructure_failed")
        if executed == 0:
            reasons.append("no_public_replay_events_executed")
        if missing_alignment:
            reasons.append("adapter_operations_missing_3a_alignment")

        if executed > 0 and passed < executed:
            review_items.append("public_replay_failures_present")
        if expected_behavior_review_required:
            review_items.append("llm_expected_behavior_review_required")
        if target_semantic_candidates:
            review_items.append("target_semantic_failure_candidate")
        if adapter.get("_validation_errors"):
            review_items.append("adapter_validation_errors_present")

        if adapter_missing:
            coverage_gaps.append("some_source_tested_public_functions_not_replayed")
        if missing_behavior_cases:
            coverage_gaps.append("not_all_eligible_source_behavior_cases_replayed_or_excluded")
        if partial_alignment:
            coverage_gaps.append("some_operations_cover_only_part_of_3a_target_recipe")
        if scoped_sources and planned_sources < scoped_sources:
            coverage_gaps.append("not_all_source_tested_public_functions_traced")

        if executed > 0 and passed == executed:
            positive_evidence.append("all_executed_public_replay_events_passed")
        if replay_plan_summary.get("covered_aligned_pairs", 0) > 0:
            positive_evidence.append("at_least_one_3a_atomic_pair_replay_covered")
        if not failed_replay_events:
            positive_evidence.append("no_failed_replay_events")
        if not infrastructure_failures:
            positive_evidence.append("no_replay_infrastructure_failures")

        if reasons:
            status = "not_ready"
        elif review_items:
            status = "review_required"
        elif coverage_gaps:
            status = "partial"
        else:
            status = "ready"

        if status == "ready":
            summary = "3B public replay is automated and passed for the current source-tested public scope."
        elif status == "partial":
            summary = (
                "3B public replay passed for generated events, but adapter coverage/alignment gaps remain; "
                "treat results as scoped to covered operations."
            )
        elif status == "review_required":
            summary = (
            "3B replay produced results, but one or more failures require expected-behavior or semantic review "
                "before treating the result as automated correctness evidence."
            )
        else:
            summary = "3B automation is not ready for correctness judgment because replay did not execute cleanly."

        return {
            "status": status,
            "summary": summary,
            "positive_evidence": positive_evidence,
            "blocking_reasons": reasons,
            "review_items": review_items,
            "coverage_gaps": coverage_gaps,
        }

    def _semantic_failure_reviews(self, semantic_failures, adapter):
        reviews = []
        is_llm_adapter = str(adapter.get("generation_status", "")).startswith("llm_synthesized")
        for failure in semantic_failures:
            expected_behavior_confidence = self._expected_behavior_confidence(failure)
            if is_llm_adapter and expected_behavior_confidence != "high":
                status = "expected_behavior_review_required"
                reason = (
                    "LLM-synthesized adapter produced a failing executable expected-behavior check with non-high "
                    "confidence; review source test evidence before treating this as target semantic error."
                )
            else:
                status = "target_semantic_failure_candidate"
                reason = "Replay compiled and ran; failing expected-behavior check is a candidate target semantic mismatch."
            reviews.append({
                "replay_event_id": failure.get("id", ""),
                "operation": failure.get("operation", ""),
                "review_status": status,
                "reason": reason,
                "expected_behavior_source": self._expected_behavior_source(failure),
                "expected_behavior_confidence": expected_behavior_confidence,
                "expected": failure.get("expected", {}),
            })
        return reviews

    def _expected_behavior_source(self, event):
        return event.get("expected_behavior_source") or event.get("oracle_source", "")

    def _expected_behavior_confidence(self, event):
        return event.get("expected_behavior_confidence") or event.get("oracle_confidence", "")

    def _source_functions_with_test_evidence(
        self,
        inventory,
        source_uuids,
        call_field="calls_aligned_public_functions",
        require_precise_behavior=False,
    ):
        if require_precise_behavior:
            precise = self._source_functions_with_precise_behavior_evidence(source_uuids)
            if precise is not None:
                return precise
        called_names = set()
        for entry in inventory.get("test_files", []):
            called_names.update(entry.get(call_field, []))
        return {
            src_uuid for src_uuid in source_uuids
            if self._uuid_leaf_name(src_uuid) in called_names
        }

    def _source_functions_with_precise_behavior_evidence(self, source_uuids):
        source_uuids = set(source_uuids or [])
        context = self._last_synthesis_context or {}
        function_index = context.get("source_evidence", {}).get("function_index", {})
        return self._source_functions_with_precise_behavior_evidence_from_index(source_uuids, function_index)

    def _source_functions_with_precise_behavior_evidence_from_index(self, source_uuids, function_index):
        source_uuids = set(source_uuids or [])
        if not source_uuids or not isinstance(function_index, dict) or not function_index:
            return None

        leaf_counts = {}
        for src_uuid in source_uuids:
            leaf = self._uuid_leaf_name(src_uuid)
            if leaf:
                leaf_counts[leaf] = leaf_counts.get(leaf, 0) + 1

        precise = set()
        for src_uuid in source_uuids:
            evidence = function_index.get(src_uuid)
            if not isinstance(evidence, dict):
                continue
            has_case_or_assertion = bool(evidence.get("case_refs") or evidence.get("direct_assertions"))
            has_path_evidence = bool(evidence.get("evidence_paths"))
            leaf = self._uuid_leaf_name(src_uuid)
            leaf_is_ambiguous = leaf_counts.get(leaf, 0) > 1
            if has_case_or_assertion or (has_path_evidence and not leaf_is_ambiguous):
                precise.add(src_uuid)
        return precise

    def _target_functions_for_sources(self, alignment_stats, source_uuids):
        targets = set()
        for pair in self._alignment_pairs_by_source(alignment_stats).values():
            if pair.get("is_public_eligible") and pair.get("src_uuid") in source_uuids:
                targets.update(pair.get("tgt_uuids", []))
        return targets

    def _build_metrics(
        self,
        replay_summary,
        public_plan_src,
        public_plan_tgt,
        public_eligible_src,
        public_eligible_tgt,
        tested_public_src,
        public_leaf_tested_src,
        tested_public_tgt,
        excluded_no_src_test,
        aligned_src,
        tested_aligned_src,
        excluded_public_no_src_test,
        excluded_public_no_observed_src_test,
        excluded_public_no_precise_behavior,
        source_tested_non_public_internal,
        mixed_public_internal_case_count,
        adapter_missing_count,
        skipped_private_internal_count,
        replay_plan_summary,
        semantic_failure_reviews,
    ):
        executed = replay_summary.get("executed", 0)
        passed = replay_summary.get("passed", 0)
        scoped_src_total = len(tested_public_src)
        scoped_tgt_total = len(tested_public_tgt)
        adapter_denominator = max(scoped_src_total, 1)
        basic_counts = {
            "aligned_source_functions_total": len(aligned_src),
            "aligned_source_functions_with_src_test_evidence": len(tested_aligned_src),
            "aligned_source_functions_excluded_no_src_test_evidence": len(excluded_no_src_test),
            "source_tested_non_public_or_internal_functions_excluded_l1": len(source_tested_non_public_internal),
            "public_source_functions_with_leaf_name_test_evidence": len(public_leaf_tested_src),
            "public_source_functions_excluded_no_precise_behavior_evidence": len(excluded_public_no_precise_behavior),
            "public_source_functions_with_precise_behavior_evidence_l1_scope": scoped_src_total,
            "public_target_functions_in_l1_scope": scoped_tgt_total,
            "mixed_public_internal_aligned_test_cases": mixed_public_internal_case_count,
            "source_tested_public_functions_not_replayed": adapter_missing_count,
            "replay_events_executed": executed,
            "replay_events_passed": passed,
            "replay_events_failed": replay_summary.get("failed", 0),
            "failed_replay_events_requiring_expected_behavior_review": len([
                item for item in semantic_failure_reviews
                if item.get("review_status") == "expected_behavior_review_required"
            ]),
            "target_semantic_failure_candidates": len([
                item for item in semantic_failure_reviews
                if item.get("review_status") == "target_semantic_failure_candidate"
            ]),
            "infrastructure_failures": replay_summary.get("infrastructure_failures", 0),
            "validated_aligned_source_functions_replayed": len(public_plan_src),
            "validated_aligned_target_functions_replayed": len(public_plan_tgt),
            "covered_aligned_pairs": replay_plan_summary.get("covered_aligned_pairs", 0),
        }

        ratio_metrics = {
            "source_test_evidence_coverage": self._ratio(
                len(tested_aligned_src),
                len(aligned_src),
                "3A aligned source 函数中，有 src 测试证据的比例",
            ),
            "precise_behavior_evidence_rate": self._ratio(
                scoped_src_total,
                len(public_leaf_tested_src),
                "public source 函数中，从 leaf-name 测试证据进一步确认有精确行为证据的比例",
            ),
            "source_tested_public_function_replay_gap_rate": self._ratio(
                adapter_missing_count,
                adapter_denominator,
                "L1 scope 中有精确 src 测试证据但 adapter 未 replay 的 source 函数比例",
            ),
            "public_replay_pass_rate": self._ratio(
                passed,
                executed,
                (
                    "当前已生成 replay plan 内，public replay 通过的 event 数 / public replay 实际执行的 event 数；"
                    "这是 scoped pass rate，不代表全部 eligible source behavior cases 的全局通过率"
                ),
            ),
            "aligned_source_replay_coverage": self._ratio(
                len(public_plan_src),
                scoped_src_total,
                "L1 source scope 中被 replay 覆盖且通过 3A 对齐验证的 source 函数比例",
            ),
            "aligned_target_replay_coverage": self._ratio(
                len(public_plan_tgt),
                scoped_tgt_total,
                "L1 target scope 中被 replay 触达且通过 3A 对齐验证的 target 函数比例",
            ),
        }

        return {
            "basic_counts": basic_counts,
            "ratio_metrics": ratio_metrics,
        }

    def _ratio(self, numerator, denominator, description=""):
        if denominator <= 0:
            return {
                "value": "0.00%",
                "raw_fraction": f"{numerator} / {denominator}",
                "description": description,
            }
        return {
            "value": f"{(numerator / denominator) * 100:.2f}%",
            "raw_fraction": f"{numerator} / {denominator}",
            "description": description,
        }

    def _write_artifacts(
        self,
        artifacts_dir,
        inventory,
        replay_plan,
        replay_result,
        adapter,
        alignment_stats=None,
        public_replay_eligibility=None,
    ):
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "effective_adapter.json": adapter,
            "test_inventory.json": inventory,
            "replay_plan.json": replay_plan,
            "replay_result.json": replay_result,
            "public_replay_eligibility.json": public_replay_eligibility or {},
        }
        for filename, data in files.items():
            with open(artifacts_dir / filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        generated_harness = self._rust_inline_harness_from_adapter(adapter)
        if generated_harness.strip() and replay_plan.get("status") == "recorded":
            (artifacts_dir / "generated_public_replay.rs").write_text(
                generated_harness,
                encoding="utf-8",
            )
        self._write_generated_adapter_cache_if_reusable(
            artifacts_dir,
            inventory,
            replay_plan,
            replay_result,
            adapter,
            alignment_stats,
        )

    def _normalize_failure_text(self, text):
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    def _failure_cause_features(self, event, include_source_hints=True):
        input_payload = self._dict_or_wrapped_text(event.get("input", {}), "input")
        expected = self._dict_or_wrapped_text(event.get("expected", {}), "observable_behavior")
        metadata = self._dict_or_wrapped_text(event.get("operation_metadata", {}), "description")
        evidence = event.get("evidence", "")

        text_parts = [
            evidence,
            metadata.get("description", ""),
            metadata.get("normalization", ""),
            expected.get("observable_behavior", ""),
        ]
        text_parts.extend(self._flatten_text_values(input_payload))
        text_parts.extend(
            str(value)
            for key, value in expected.items()
            if key != "observable_behavior"
        )
        combined_text = "\n".join(str(part) for part in text_parts if part is not None)

        json_literals = self._extract_json_like_literals(input_payload)
        feature_text = "\n".join([combined_text, *json_literals])
        options = sorted(set(re.findall(r"\ballow[A-Za-z0-9_]+", feature_text)))
        syntax_features = self._json_syntax_features(feature_text, json_literals)
        syntax_features = self._syntax_features_from_options(options, syntax_features)
        if options:
            syntax_features = [
                feature for feature in syntax_features
                if feature not in {"json_input", "parse_should_accept", "parse_should_reject"}
            ]
        structured_expected = self._stable_expected_features(expected)

        features = {
            "options": options,
            "json_syntax_features": syntax_features,
            "structured_expected": structured_expected,
        }
        if include_source_hints:
            features["source_test_hints"] = self._source_test_hints(evidence)

        # Keep literals only as a fallback discriminator. If an explicit option
        # or syntax class exists, two differently named events for the same
        # cause should still group together.
        if not options and not syntax_features:
            features["input_literals"] = sorted(json_literals)[:8]
        return self._compact_report_dict(features)

    def _dict_or_wrapped_text(self, value, key):
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return {key: str(value)}

    def _syntax_features_from_options(self, options, syntax_features):
        features = set(syntax_features or [])
        option_map = {
            "allowDroppedNullPlaceholders": "dropped_null_placeholder",
            "allowSingleQuotes": "single_quoted_json",
            "allowNumericKeys": "numeric_object_keys",
            "allowTrailingCommas": "trailing_comma",
            "allowComments": "comments",
            "allowSpecialFloats": "special_floats",
        }
        for option in options or []:
            feature = option_map.get(option)
            if feature:
                features.add(feature)
        return sorted(features)

    def _flatten_text_values(self, value):
        if isinstance(value, dict):
            values = []
            for key, item in value.items():
                values.append(str(key))
                values.extend(self._flatten_text_values(item))
            return values
        if isinstance(value, list):
            values = []
            for item in value:
                values.extend(self._flatten_text_values(item))
            return values
        if value is None:
            return []
        return [str(value)]

    def _extract_json_like_literals(self, value):
        literals = []
        for text in self._flatten_text_values(value):
            stripped = text.strip()
            if len(stripped) < 2:
                continue
            if stripped[0] in "[{\"'" or re.search(r"[\{\[][^;\n]{0,300}[\}\]]", stripped):
                literals.append(self._normalize_failure_text(stripped)[:500])
        return sorted(set(literals))

    def _json_syntax_features(self, text, literals):
        combined = self._normalize_failure_text(text)
        features = set()
        if ",," in combined:
            features.add("dropped_null_placeholder")
        if re.search(r"[\{\[,]\s*'", combined) or re.search(r"'\s*:", combined):
            features.add("single_quoted_json")
        if re.search(r"[\{,]\s*-?\d+(?:\.\d+)?\s*:", combined):
            features.add("numeric_object_keys")
        if re.search(r",\s*[\}\]]", combined):
            features.add("trailing_comma")
        if "//" in combined or "/*" in combined:
            features.add("comments")
        if "\\t" in combined or "\t" in combined:
            features.add("tab_escape")
        if "\\u" in combined:
            features.add("unicode_escape")
        if "iterator" in combined or "begin" in combined:
            if "object" in combined or "key" in combined or "entries" in combined:
                features.add("object_iteration")
            if "array" in combined or "members" in combined:
                features.add("array_iteration")
        if literals and any(literal.startswith("[") or literal.startswith("{") for literal in literals):
            features.add("json_input")
        return sorted(features)

    def _stable_expected_features(self, expected):
        if not isinstance(expected, dict):
            return {}
        stable = {}
        for key, value in expected.items():
            if key == "observable_behavior":
                continue
            stable[key] = value
        return stable

    def _source_test_hints(self, evidence):
        hints = []
        for piece in re.split(r"[;,]\s*", str(evidence or "")):
            piece = piece.strip()
            if not piece:
                continue
            hints.append(re.sub(r"\s+", " ", piece)[:160])
        return sorted(set(hints))[:8]


    def _write_generated_adapter_cache_if_reusable(
        self,
        artifacts_dir,
        inventory,
        replay_plan,
        replay_result,
        adapter,
        alignment_stats=None,
    ):
        cache_summary = self._generated_adapter_cache_summary(
            inventory=inventory,
            replay_plan=replay_plan,
            replay_result=replay_result,
            adapter=adapter,
            alignment_stats=alignment_stats,
            artifacts_dir=artifacts_dir,
        )
        if not cache_summary.get("reusable"):
            return

        cache_path = self.generated_adapter_cache_path(self.src_name, self.tgt_name)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cached_adapter = dict(adapter)
        cached_adapter["_adapter_cache_status"] = "reusable_after_validated_replay"
        cached_adapter["_cached_from_artifact_dir"] = self._display_path(artifacts_dir)
        cached_adapter["_cached_at"] = datetime.utcnow().isoformat() + "Z"
        cached_adapter["_last_replay_status"] = replay_result.get("status", "")
        cached_adapter["_replay_plan_alignment_status_counts"] = cache_summary.get("alignment_status_counts", {})
        cached_adapter["_cache_coverage_scope"] = cache_summary.get("coverage_scope", {})
        cached_adapter["_eligibility_schema_version"] = (
            self._public_replay_eligibility or {}
        ).get("schema_version", "")
        cached_adapter["_eligibility_case_fingerprint"] = self._public_replay_eligibility_fingerprint()
        cached_adapter.pop("_adapter_resolution", None)
        self._write_json_atomic(cache_path, cached_adapter)

    def _public_replay_eligibility_fingerprint(self):
        eligibility = self._public_replay_eligibility or {}
        case_ids = sorted(
            case.get("case_id")
            for case in eligibility.get("eligible_cases", [])
            if isinstance(case, dict) and case.get("case_id")
        )
        if not case_ids:
            return ""
        payload = {
            "schema_version": eligibility.get("schema_version", ""),
            "case_ids": case_ids,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:20]

    def _generated_adapter_cache_summary(
        self,
        inventory,
        replay_plan,
        replay_result,
        adapter,
        alignment_stats=None,
        artifacts_dir=None,
    ):
        cache_path = self.generated_adapter_cache_path(self.src_name, self.tgt_name)
        reasons = []
        generation_status = str(adapter.get("generation_status", ""))
        if not generation_status.startswith("llm_synthesized"):
            reasons.append("adapter_not_llm_synthesized")
        if adapter.get("status") != "loaded":
            reasons.append(f"adapter_status={adapter.get('status', 'unknown')}")
        if replay_result.get("status") != "passed":
            reasons.append(f"replay_status={replay_result.get('status', 'unknown')}")
        if adapter.get("_validation_errors"):
            reasons.append("adapter_validation_errors_present")
        alignment_status_counts = self._replay_alignment_status_counts(replay_result)
        if not alignment_status_counts:
            reasons.append("no_replay_alignment_status_counts")
        elif set(alignment_status_counts) != {"fully_aligned"}:
            reasons.append("replay_plan_alignment_not_all_fully_aligned")
        coverage_scope = {}
        if alignment_stats is None:
            reasons.append("alignment_stats_missing")
        else:
            coverage_scope = self._adapter_coverage_scope(
                alignment_stats,
                inventory,
                adapter,
                replay_plan,
                compact=True,
            )
            if coverage_scope.get("required_behavior_case_count", 0) <= 0:
                reasons.append("no_eligible_behavior_cases_in_scope")
            if coverage_scope.get("missing_behavior_case_count", 0) != 0:
                reasons.append("missing_behavior_cases")
            if coverage_scope.get("unresolved_unlisted_behavior_case_count", 0) != 0:
                reasons.append("unresolved_behavior_cases_not_in_initial_context")
            required_behavior_cases = coverage_scope.get("required_behavior_case_count", 0)
            accounted_behavior_cases = (
                coverage_scope.get("replayed_behavior_case_count", 0)
                + coverage_scope.get("excluded_behavior_case_count", 0)
            )
            if required_behavior_cases and accounted_behavior_cases != required_behavior_cases:
                reasons.append("behavior_case_accounting_incomplete")
        return {
            "cache_path": self._display_path(cache_path),
            "reusable": not reasons,
            "status": "reusable_after_validated_replay" if not reasons else "not_cached",
            "not_cached_reasons": reasons,
            "alignment_status_counts": alignment_status_counts,
            "coverage_scope": coverage_scope,
            "cached_from_artifact_dir": self._display_path(artifacts_dir) if artifacts_dir else "",
        }

    def _replay_alignment_status_counts(self, replay_result):
        counts = {}
        for event in replay_result.get("events", []):
            status = event.get("alignment_validation", {}).get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _write_json_atomic(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
