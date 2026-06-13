import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from phase3_evaluator.prompts import (
    PROMPT_3B_ADAPTER_SCHEMA_REPAIR,
    PROMPT_3B_ADAPTER_SYNTHESIS,
    PROMPT_3B_AGENT_COVERAGE_EXPANSION,
    PROMPT_3B_REPLAY_REPAIR,
)


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
        synthesis_attempts=2,
        replay_repair_attempts=1,
        agent_iterations=2,
        agent_batch_size=5,
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
        self.agent_iterations = max(0, int(agent_iterations or 0))
        self.agent_batch_size = max(1, int(agent_batch_size or 1))
        self.llm_client = llm_client
        self.work_root = Path(work_root) if work_root else None
        self._last_synthesis_context = None
        self._last_synthesis_prompt = None
        self._synthesis_attempts_used = 0

    def run(self, mode="run", layer="public", artifacts_dir=None):
        if mode not in {"inventory", "record", "replay", "run"}:
            raise ValueError(f"Unsupported 3B mode: {mode}")
        if layer not in {"public", "function", "both"}:
            raise ValueError(f"Unsupported 3B layer: {layer}")
        if self.adapter_mode not in {"existing", "auto", "synthesize", "prompt-only"}:
            raise ValueError(f"Unsupported 3B adapter mode: {self.adapter_mode}")

        self._check_required_paths(mode)
        alignment = self._load_alignment()
        src_index = self._index_functions(self.src_db_path)
        tgt_index = self._index_functions(self.tgt_db_path)
        alignment_stats = self._summarize_alignment(alignment, src_index, tgt_index)
        artifacts_path = Path(artifacts_dir) if artifacts_dir else None
        inventory = self.discover_tests(alignment_stats)
        adapter = self._resolve_adapter(alignment_stats, inventory, artifacts_path)
        if mode == "inventory":
            trace_corpus = self._empty_trace_corpus("three_b_mode_inventory")
        elif mode == "replay" and artifacts_path and (artifacts_path / "trace_corpus.json").exists():
            trace_corpus = self._load_json(artifacts_path / "trace_corpus.json")
        else:
            trace_corpus = self.record_public_traces(inventory, alignment_stats, adapter)
        trace_corpus = self._ensure_trace_alignment_validation(trace_corpus, alignment_stats, adapter)
        replay_result = self.replay_public_traces(
            trace_corpus,
            adapter,
            mode,
            work_root=self._resolve_work_root(artifacts_path),
        )
        if (
            self.adapter_mode in {"auto", "synthesize"}
            and self._synthesis_attempts_used > 0
            and mode in {"replay", "run"}
            and replay_result.get("status") == "infrastructure_failed"
            and self.llm_client is not None
            and self.replay_repair_attempts > 0
        ):
            adapter, trace_corpus, replay_result = self._repair_synthesized_adapter_after_replay_failure(
                adapter=adapter,
                trace_corpus=trace_corpus,
                replay_result=replay_result,
                alignment_stats=alignment_stats,
                artifacts_path=artifacts_path,
                mode=mode,
            )
        if (
            self.adapter_mode in {"auto", "synthesize"}
            and self._synthesis_attempts_used > 0
            and mode in {"replay", "run"}
            and self.llm_client is not None
            and self.agent_iterations > 0
        ):
            adapter, trace_corpus, replay_result = self._agent_expand_synthesized_adapter(
                adapter=adapter,
                inventory=inventory,
                trace_corpus=trace_corpus,
                replay_result=replay_result,
                alignment_stats=alignment_stats,
                artifacts_path=artifacts_path,
                mode=mode,
            )
        function_boundary = self._function_boundary_status(layer, alignment_stats)

        report = self._build_report(
            mode=mode,
            layer=layer,
            alignment_stats=alignment_stats,
            adapter=adapter,
            inventory=inventory,
            trace_corpus=trace_corpus,
            replay_result=replay_result,
            function_boundary=function_boundary,
            artifacts_path=artifacts_path,
        )

        if artifacts_dir:
            self._write_artifacts(
                Path(artifacts_dir),
                inventory,
                trace_corpus,
                replay_result,
                adapter,
                alignment_stats,
            )

        return report

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
            "trace_corpus": self._display_path(artifacts_path / "trace_corpus.json"),
            "replay_result": self._display_path(artifacts_path / "replay_result.json"),
            "work_dir": self._display_path(artifacts_path / "work" / "latest"),
            "generated_test_file": self._display_path(
                artifacts_path / "work" / "latest" / "target_repo" / "tests" / "cp2rs_3b_public.rs"
            ),
        }
        if self.adapter_mode in {"auto", "synthesize", "prompt-only"}:
            optional_paths = {
                "adapter_synthesis_context": artifacts_path / "adapter_synthesis_context.json",
                "adapter_synthesis_prompt": artifacts_path / "adapter_synthesis_prompt.md",
                "adapter_synthesis_raw_response": artifacts_path / "adapter_synthesis_raw_response.txt",
                "adapter_synthesis_validation_errors": artifacts_path / "adapter_synthesis_validation_errors.json",
                "synthesized_adapter": artifacts_path / "synthesized_adapter.json",
                "adapter_synthesis_attempts": artifacts_path / "adapter_synthesis_attempts.json",
            }
            paths.update({
                name: self._display_path(path)
                for name, path in optional_paths.items()
                if path.exists()
            })
        return paths

    def _resolve_adapter(self, alignment_stats, inventory, artifacts_path):
        if self.adapter_mode == "existing":
            return self._load_adapter()

        if self.adapter_mode == "auto":
            adapter = self._load_adapter()
            if adapter.get("status") == "loaded":
                adapter.setdefault("generation_status", "reused_existing_adapter")
                adapter["_auto_resolution"] = "existing_adapter"
                return adapter

        context = self._build_adapter_synthesis_context(alignment_stats, inventory)
        prompt = self._build_adapter_synthesis_prompt(context)
        self._last_synthesis_context = context
        self._last_synthesis_prompt = prompt
        self._write_adapter_synthesis_inputs(artifacts_path, context, prompt)

        if self.adapter_mode == "prompt-only":
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

        adapter = self._synthesize_adapter_with_schema_repair(prompt, artifacts_path)
        return adapter

    def _synthesize_adapter_with_schema_repair(self, initial_prompt, artifacts_path):
        attempts = []
        prompt = initial_prompt
        last_errors = []
        for attempt_number in range(1, self.synthesis_attempts + 1):
            raw_reply = self.llm_client.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=16000,
            )
            if artifacts_path:
                artifacts_path.mkdir(parents=True, exist_ok=True)
                raw_path = artifacts_path / f"adapter_synthesis_raw_response_attempt_{attempt_number}.txt"
                raw_path.write_text(raw_reply or "", encoding="utf-8")
                if attempt_number == 1:
                    (artifacts_path / "adapter_synthesis_raw_response.txt").write_text(raw_reply or "", encoding="utf-8")

            adapter = None
            errors = []
            try:
                adapter = self._extract_json_from_llm_reply(raw_reply)
                if not isinstance(adapter, dict):
                    errors.append("LLM did not return a JSON object")
                    adapter = None
                else:
                    self._apply_synthesized_adapter_defaults(adapter)
                    errors.extend(self._validate_synthesized_adapter(adapter))
            except Exception as exc:
                errors.append(f"JSON extraction failed: {exc}")

            attempts.append({
                "attempt": attempt_number,
                "stage": "schema_validation",
                "status": "failed" if errors else "passed",
                "errors": errors,
                "warnings": adapter.get("_validation_warnings", []) if adapter else [],
            })
            self._synthesis_attempts_used = attempt_number
            self._write_synthesis_attempts(artifacts_path, attempts)

            if adapter is not None and not errors:
                self._write_synthesized_adapter(artifacts_path, adapter, attempt_number)
                return adapter

            last_errors = errors
            if attempt_number < self.synthesis_attempts:
                prompt = self._build_adapter_schema_repair_prompt(
                    previous_reply=raw_reply,
                    validation_errors=errors,
                )

        if artifacts_path:
            with open(artifacts_path / "adapter_synthesis_validation_errors.json", "w", encoding="utf-8") as f:
                json.dump({"errors": last_errors, "attempts": attempts}, f, indent=2, ensure_ascii=False)
        raise ValueError("3B adapter synthesis returned an invalid adapter: " + "; ".join(last_errors[:5]))

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

    def _write_synthesized_adapter(self, artifacts_path, adapter, attempt_number):
        if artifacts_path:
            synthesized_path = artifacts_path / "synthesized_adapter.json"
            with open(synthesized_path, "w", encoding="utf-8") as f:
                json.dump(adapter, f, indent=2, ensure_ascii=False)
            attempt_path = artifacts_path / f"synthesized_adapter_attempt_{attempt_number}.json"
            with open(attempt_path, "w", encoding="utf-8") as f:
                json.dump(adapter, f, indent=2, ensure_ascii=False)
            adapter["_adapter_source_path"] = self._display_path(synthesized_path)
        else:
            adapter["_adapter_source_path"] = "llm_synthesized"

    def _write_synthesis_attempts(self, artifacts_path, attempts):
        if not artifacts_path:
            return
        artifacts_path.mkdir(parents=True, exist_ok=True)
        with open(artifacts_path / "adapter_synthesis_attempts.json", "w", encoding="utf-8") as f:
            json.dump({"attempts": attempts}, f, indent=2, ensure_ascii=False)

    def _build_adapter_schema_repair_prompt(self, previous_reply, validation_errors):
        repair_context = self._adapter_schema_repair_context(
            previous_reply=previous_reply,
            validation_errors=validation_errors,
        )
        return PROMPT_3B_ADAPTER_SCHEMA_REPAIR.format(
            repair_context_json=json.dumps(repair_context, ensure_ascii=False, separators=(",", ":")),
        )

    def _adapter_schema_repair_context(self, previous_reply, validation_errors):
        synthesis_context = self._last_synthesis_context or {}
        source_evidence = synthesis_context.get("source_evidence", {})
        return {
            "validation_errors": validation_errors,
            "previous_response": previous_reply or "",
            "repair_rules": [
                "Return one complete compact JSON adapter object only.",
                "Keep behavior grounded in source evidence already reflected by evidence paths/case ids.",
                "For every declared source function, include all required 3A target functions from alignment_scope.",
                "Every target API used in rust_test_harness must be declared in public_operations.*.target_functions.",
                "Every trace event id must have exactly one matching #[test] fn in rust_test_harness.",
                "If validation_errors include JSON extraction failures, simplify rust_test_harness string literals first.",
                "Avoid nested escaped JSON text in rust_test_harness; prefer constructing JsonValue objects/arrays with public APIs.",
            ],
            "harness_api_audit_help": {
                "declared_but_not_mentioned": (
                    "If validation says a declared target function is not mentioned, the Rust harness must "
                    "visibly call that function's leaf identifier. Example: Object::get requires `.get(...)`; "
                    "JsonValue::array_remove requires `.array_remove(...)`. Do not satisfy it with indexing or "
                    "an equivalent helper call."
                ),
                "mentioned_but_not_declared": (
                    "If validation says a target API name is used but undeclared, add the matching public UUID "
                    "from target_public_api_signatures to the operation's target_functions, unless that API call "
                    "is unnecessary and can be removed."
                ),
                "missing_required_3a_target": (
                    "If validation says an operation omits required 3A target functions, copy every missing_tgt_uuid "
                    "into that operation's target_functions and make sure rust_test_harness visibly uses it."
                ),
            },
            "required_adapter_shape": synthesis_context.get("required_adapter_shape", {}),
            "alignment_scope": synthesis_context.get("alignment_scope", {}),
            "source_evidence_repair_summary": {
                "quality_checks": source_evidence.get("quality_checks", {}),
                "field_guide": source_evidence.get("field_guide", {}),
                "function_index": source_evidence.get("function_index", {}),
                "fixture_paths": [
                    item.get("path")
                    for item in source_evidence.get("fixtures", [])
                    if item.get("path")
                ],
            },
            "target_crate_import_hint": synthesis_context.get("target_crate_import_hint", {}),
            "target_api_scope": synthesis_context.get("target_api_scope", {}),
            "target_public_api_signatures": synthesis_context.get("target_public_api_signatures", []),
            "target_aligned_api_context": synthesis_context.get("target_aligned_api_context", []),
        }

    def _repair_synthesized_adapter_after_replay_failure(
        self,
        adapter,
        trace_corpus,
        replay_result,
        alignment_stats,
        artifacts_path,
        mode,
    ):
        attempts = self._read_synthesis_attempts(artifacts_path)
        current_adapter = adapter
        current_trace_corpus = trace_corpus
        current_replay_result = replay_result

        for repair_index in range(1, self.replay_repair_attempts + 1):
            attempt_number = len(attempts) + 1
            prompt = self._build_replay_repair_prompt(
                adapter=current_adapter,
                trace_corpus=current_trace_corpus,
                replay_result=current_replay_result,
            )
            if artifacts_path:
                repair_prompt_path = artifacts_path / f"adapter_replay_repair_prompt_attempt_{attempt_number}.md"
                repair_prompt_path.write_text(prompt, encoding="utf-8")

            raw_reply = self.llm_client.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=16000,
            )
            if artifacts_path:
                raw_path = artifacts_path / f"adapter_replay_repair_raw_response_attempt_{attempt_number}.txt"
                raw_path.write_text(raw_reply or "", encoding="utf-8")

            repaired_adapter = None
            errors = []
            try:
                repaired_adapter = self._extract_json_from_llm_reply(raw_reply)
                if not isinstance(repaired_adapter, dict):
                    errors.append("LLM did not return a JSON object")
                    repaired_adapter = None
                else:
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
                "warnings": repaired_adapter.get("_validation_warnings", []) if repaired_adapter else [],
            })
            self._write_synthesis_attempts(artifacts_path, attempts)

            if repaired_adapter is None or errors:
                continue

            self._write_synthesized_adapter(artifacts_path, repaired_adapter, attempt_number)
            repaired_trace_corpus = self.record_public_traces(
                inventory={},
                alignment_stats=alignment_stats,
                adapter=repaired_adapter,
            )
            repaired_trace_corpus = self._ensure_trace_alignment_validation(
                repaired_trace_corpus,
                alignment_stats,
                repaired_adapter,
            )
            repaired_replay_result = self.replay_public_traces(
                repaired_trace_corpus,
                repaired_adapter,
                mode,
                work_root=self._resolve_work_root(artifacts_path),
            )
            attempts[-1]["status"] = "passed" if repaired_replay_result.get("status") != "infrastructure_failed" else "failed"
            attempts[-1]["replay_status"] = repaired_replay_result.get("status")
            attempts[-1]["replay_reason"] = repaired_replay_result.get("reason", "")
            self._write_synthesis_attempts(artifacts_path, attempts)

            current_adapter = repaired_adapter
            current_trace_corpus = repaired_trace_corpus
            current_replay_result = repaired_replay_result
            if repaired_replay_result.get("status") != "infrastructure_failed":
                break

        return current_adapter, current_trace_corpus, current_replay_result

    def _agent_expand_synthesized_adapter(
        self,
        adapter,
        inventory,
        trace_corpus,
        replay_result,
        alignment_stats,
        artifacts_path,
        mode,
    ):
        attempts = self._read_synthesis_attempts(artifacts_path)
        current_adapter = adapter
        current_trace_corpus = trace_corpus
        current_replay_result = replay_result

        for iteration in range(1, self.agent_iterations + 1):
            scope = self._adapter_coverage_scope(alignment_stats, inventory, current_adapter, current_trace_corpus)
            if (
                current_replay_result.get("status") == "passed"
                and not scope.get("adapter_missing_source_functions")
                and not current_trace_corpus.get("summary", {}).get("alignment_status_counts", {}).get("partial_alignment", 0)
                and not current_trace_corpus.get("summary", {}).get("alignment_status_counts", {}).get("missing_alignment", 0)
            ):
                break
            if current_replay_result.get("status") not in {"passed", "infrastructure_failed"}:
                break
            if (
                current_replay_result.get("status") == "passed"
                and not scope.get("adapter_missing_source_functions")
            ):
                break
            targeted_scope = self._targeted_coverage_scope(
                scope=scope,
                alignment_stats=alignment_stats,
                inventory=inventory,
                iteration=iteration,
                batch_size=self.agent_batch_size,
            )

            prompt = self._build_coverage_expansion_prompt(
                adapter=current_adapter,
                inventory=inventory,
                trace_corpus=current_trace_corpus,
                replay_result=current_replay_result,
                alignment_stats=alignment_stats,
                scope=targeted_scope,
                iteration=iteration,
            )
            attempt_number = len(attempts) + 1
            if artifacts_path:
                prompt_path = artifacts_path / f"adapter_agent_coverage_prompt_attempt_{attempt_number}.md"
                prompt_path.write_text(prompt, encoding="utf-8")

            raw_reply = self.llm_client.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=16000,
            )
            if artifacts_path:
                raw_path = artifacts_path / f"adapter_agent_coverage_raw_response_attempt_{attempt_number}.txt"
                raw_path.write_text(raw_reply or "", encoding="utf-8")

            expanded_adapter = None
            errors = []
            try:
                expanded_adapter = self._extract_json_from_llm_reply(raw_reply)
                if not isinstance(expanded_adapter, dict):
                    errors.append("LLM did not return a JSON object")
                    expanded_adapter = None
                else:
                    self._apply_synthesized_adapter_defaults(expanded_adapter)
                    expanded_adapter["generation_status"] = "llm_synthesized_agent_expanded_v1"
                    errors.extend(self._validate_synthesized_adapter(expanded_adapter))
            except Exception as exc:
                errors.append(f"JSON extraction failed: {exc}")

            attempts.append({
                "attempt": attempt_number,
                "stage": "agent_coverage_expansion",
                "iteration": iteration,
                "status": "failed" if errors else "schema_passed",
                "adapter_missing_before": scope.get("adapter_missing_source_functions", []),
                "targeted_missing_source_functions": targeted_scope.get("targeted_missing_source_functions", []),
                "errors": errors,
                "warnings": expanded_adapter.get("_validation_warnings", []) if expanded_adapter else [],
            })
            self._write_synthesis_attempts(artifacts_path, attempts)
            if expanded_adapter is None or errors:
                continue

            self._write_synthesized_adapter(artifacts_path, expanded_adapter, attempt_number)
            expanded_trace_corpus = self.record_public_traces(
                inventory=inventory,
                alignment_stats=alignment_stats,
                adapter=expanded_adapter,
            )
            expanded_trace_corpus = self._ensure_trace_alignment_validation(
                expanded_trace_corpus,
                alignment_stats,
                expanded_adapter,
            )
            expanded_replay_result = self.replay_public_traces(
                expanded_trace_corpus,
                expanded_adapter,
                mode,
                work_root=self._resolve_work_root(artifacts_path),
            )
            before_coverage = self._adapter_coverage_scope(
                alignment_stats,
                inventory,
                current_adapter,
                current_trace_corpus,
                compact=True,
            )
            after_coverage = self._adapter_coverage_scope(
                alignment_stats,
                inventory,
                expanded_adapter,
                expanded_trace_corpus,
                compact=True,
            )
            attempts[-1]["replay_status"] = expanded_replay_result.get("status")
            attempts[-1]["replay_reason"] = expanded_replay_result.get("reason", "")
            attempts[-1]["coverage_after"] = after_coverage
            attempts[-1]["coverage_improved"] = self._coverage_improved(before_coverage, after_coverage)
            attempts[-1]["coverage_regressed"] = self._coverage_regressed(before_coverage, after_coverage)
            if expanded_replay_result.get("status") == "infrastructure_failed":
                attempts[-1]["status"] = "failed"
            elif attempts[-1]["coverage_regressed"]:
                attempts[-1]["status"] = "coverage_regressed"
            elif scope.get("adapter_missing_source_functions") and not attempts[-1]["coverage_improved"]:
                attempts[-1]["status"] = "coverage_unchanged"
            else:
                attempts[-1]["status"] = "passed"
            self._write_synthesis_attempts(artifacts_path, attempts)

            if attempts[-1]["status"] in {"coverage_regressed", "coverage_unchanged"}:
                continue

            current_adapter = expanded_adapter
            current_trace_corpus = expanded_trace_corpus
            current_replay_result = expanded_replay_result

            if (
                expanded_replay_result.get("status") == "infrastructure_failed"
                and self.replay_repair_attempts > 0
            ):
                current_adapter, current_trace_corpus, current_replay_result = self._repair_synthesized_adapter_after_replay_failure(
                    adapter=current_adapter,
                    trace_corpus=current_trace_corpus,
                    replay_result=current_replay_result,
                    alignment_stats=alignment_stats,
                    artifacts_path=artifacts_path,
                    mode=mode,
                )
                attempts = self._read_synthesis_attempts(artifacts_path)

        return current_adapter, current_trace_corpus, current_replay_result

    def _targeted_coverage_scope(self, scope, alignment_stats, inventory, iteration, batch_size=3):
        missing_src = list(scope.get("adapter_missing_source_functions") or [])
        if not missing_src:
            return scope
        batch_size = max(1, min(int(batch_size or 1), len(missing_src)))
        start = ((max(1, iteration) - 1) * batch_size) % len(missing_src)
        focused_src = missing_src[start:start + batch_size]
        if len(focused_src) < batch_size:
            focused_src.extend(missing_src[:batch_size - len(focused_src)])
        focused_src = sorted(dict.fromkeys(focused_src))

        targeted = dict(scope)
        targeted["targeting_strategy"] = "small_batch_missing_source_functions_v1"
        targeted["targeted_missing_source_function_count"] = len(focused_src)
        targeted["targeted_missing_source_functions"] = focused_src
        targeted["missing_alignment_pairs"] = self._alignment_pairs_for_sources(alignment_stats, focused_src)
        targeted["missing_source_test_evidence"] = self._source_function_test_evidence(
            inventory,
            set(focused_src),
            max_functions=len(focused_src),
            max_entries_per_function=4,
            max_chars_per_snippet=1800,
            max_total_chars=12000,
        )
        return targeted

    def _coverage_improved(self, before, after):
        return (
            after.get("adapter_missing_source_function_count", 0)
            < before.get("adapter_missing_source_function_count", 0)
            or after.get("untraced_source_function_count", 0)
            < before.get("untraced_source_function_count", 0)
            or after.get("covered_aligned_pairs", 0)
            > before.get("covered_aligned_pairs", 0)
            or after.get("validated_traced_source_function_count", 0)
            > before.get("validated_traced_source_function_count", 0)
        )

    def _coverage_regressed(self, before, after):
        return (
            after.get("adapter_missing_source_function_count", 0)
            > before.get("adapter_missing_source_function_count", 0)
            or after.get("untraced_source_function_count", 0)
            > before.get("untraced_source_function_count", 0)
            or after.get("covered_aligned_pairs", 0)
            < before.get("covered_aligned_pairs", 0)
            or after.get("validated_traced_source_function_count", 0)
            < before.get("validated_traced_source_function_count", 0)
        )

    def _adapter_coverage_scope(self, alignment_stats, inventory, adapter, trace_corpus, compact=False):
        public_eligible_src = set(alignment_stats.get("public_eligible_source_functions", []))
        tested_public_src = self._source_functions_with_test_evidence(inventory, public_eligible_src)
        adapter_src = set()
        for operation in adapter.get("public_operations", {}).values():
            if isinstance(operation, dict):
                adapter_src.update(operation.get("source_functions", []) or [])
        trace_summary = trace_corpus.get("summary", {})
        traced_src = set(trace_summary.get("validated_aligned_source_function_ids", []))
        missing_src = sorted(tested_public_src - adapter_src)
        untraced_src = sorted(tested_public_src - traced_src)
        scope = {
            "source_functions_with_src_test_evidence_count": len(tested_public_src),
            "adapter_source_function_count": len(adapter_src),
            "validated_traced_source_function_count": len(traced_src),
            "adapter_missing_source_function_count": len(missing_src),
            "adapter_missing_source_functions": missing_src,
            "untraced_source_function_count": len(untraced_src),
            "untraced_source_functions": untraced_src,
            "trace_alignment_status_counts": trace_summary.get("alignment_status_counts", {}),
            "covered_aligned_pairs": trace_summary.get("covered_aligned_pairs", 0),
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

    def _build_coverage_expansion_prompt(
        self,
        adapter,
        inventory,
        trace_corpus,
        replay_result,
        alignment_stats,
        scope,
        iteration,
    ):
        scoped_pairs = scope.get("missing_alignment_pairs", [])
        target_context = self._target_aligned_api_context(scoped_pairs, max_items=50, max_body_chars=500)
        repair_context = {
            "iteration": iteration,
            "objective": (
                "Expand the existing 3B adapter to cover the targeted missing source-tested public 3A "
                "source functions while preserving already passing replay behavior."
            ),
            "rules": [
                "Return one complete compact JSON adapter object only.",
                "Keep existing passing operations/tests unless a build/API fix is required.",
                "Focus first on targeted_missing_source_functions; do not rewrite unrelated passing operations.",
                "Add or merge operations for targeted missing functions when source test evidence gives a reliable public observable behavior.",
                "For every added source function, include all 3A target functions from missing_alignment_pairs in target_functions.",
                "Do not invent behavior; if a missing function cannot be replayed reliably through public Rust APIs, leave it omitted.",
                "Do not use target tests or examples. Use source tests, 3A pairs, target signatures/body excerpts, and cargo feedback only.",
            ],
            "coverage_scope_before": {
                key: value for key, value in scope.items()
                if key not in {"missing_source_test_evidence"}
            },
            "missing_source_test_evidence": scope.get("missing_source_test_evidence", {}),
            "target_aligned_api_context_for_missing": target_context,
            "target_api_scope_for_missing": self._target_api_scope(scoped_pairs),
            "target_public_api_signatures": self._target_public_api_signatures_for_synthesis(scoped_pairs, max_items=80),
            "target_project_context": self._target_project_context(),
            "target_crate_import_hint": self._target_crate_import_hint(),
            "current_trace_summary": trace_corpus.get("summary", {}),
            "current_replay_summary": self._report_replay_summary(replay_result),
            "current_adapter": self._adapter_for_prompt(adapter),
        }
        return PROMPT_3B_AGENT_COVERAGE_EXPANSION.format(
            repair_context_json=json.dumps(repair_context, ensure_ascii=False, separators=(",", ":")),
        )

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

    def _build_replay_repair_prompt(self, adapter, trace_corpus, replay_result):
        replay_summary = replay_result.get("summary", {})
        repair_context = {
            "previous_adapter": self._adapter_for_prompt(adapter),
            "trace_summary": trace_corpus.get("summary", {}),
            "replay_status": replay_result.get("status"),
            "replay_reason": replay_result.get("reason", ""),
            "generated_test_file": replay_summary.get("generated_test_file", ""),
            "stdout_tail": self._truncate_text(replay_summary.get("stdout_tail", ""), max_chars=12000),
            "stderr_tail": self._truncate_text(replay_summary.get("stderr_tail", ""), max_chars=18000),
            "failure_reason": self._truncate_text(replay_summary.get("failure_reason", ""), max_chars=6000),
            "target_repair_context": self._target_repair_context(),
        }
        return PROMPT_3B_REPLAY_REPAIR.format(
            repair_context_json=json.dumps(repair_context, ensure_ascii=False, separators=(",", ":")),
        )

    def _adapter_for_prompt(self, adapter):
        if not isinstance(adapter, dict):
            return {}
        keep_keys = [
            "adapter_schema_version",
            "name",
            "status",
            "adapter_role",
            "generation_status",
            "recorder",
            "replay_generator",
            "target_language",
            "target_test_command",
            "public_operations",
            "trace_events",
            "rust_test_harness",
            "target_replay_harness",
        ]
        compact = {
            key: adapter.get(key)
            for key in keep_keys
            if key in adapter
        }
        compact["_prompt_note"] = (
            "Prompt copy omits generated audit/cache metadata. Return a complete adapter with public_operations, "
            "trace_events, and rust_test_harness preserved or minimally extended."
        )
        return compact

    def _target_repair_context(self):
        synthesis_context = self._last_synthesis_context or {}
        return {
            "required_adapter_shape": synthesis_context.get("required_adapter_shape", {}),
            "alignment_scope": synthesis_context.get("alignment_scope", {}),
            "target_crate_import_hint": synthesis_context.get("target_crate_import_hint", {}),
            "target_api_scope": synthesis_context.get("target_api_scope", {}),
            "target_public_api_signatures": synthesis_context.get("target_public_api_signatures", []),
            "target_aligned_api_context": synthesis_context.get("target_aligned_api_context", []),
        }

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
        warnings = []
        adapter["_validation_warnings"] = []
        allowed_source_uuids = self._synthesis_scoped_source_uuids()
        allowed_target_uuids = self._synthesis_target_public_uuids()
        expected_targets_by_source = self._synthesis_expected_targets_by_source()
        target_public_name_to_uuids = self._synthesis_target_public_name_to_uuids()
        source_evidence_paths = self._synthesis_source_evidence_paths()
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
                if not event.get("evidence"):
                    errors.append(f"trace_events[{index}].evidence must cite source test evidence")
                elif source_evidence_paths and not self._evidence_mentions_known_path(event.get("evidence"), source_evidence_paths):
                    warnings.append(
                        f"trace_events[{index}].evidence does not clearly cite a known source test path: "
                        f"{event.get('evidence')}"
                    )
                if not event.get("expected"):
                    errors.append(f"trace_events[{index}].expected must describe observable behavior")
                oracle_confidence = event.get("oracle_confidence", "medium")
                if oracle_confidence not in {"high", "medium", "low"}:
                    errors.append(
                        f"trace_events[{index}].oracle_confidence must be one of high|medium|low"
                    )
                if not event.get("oracle_source"):
                    warnings.append(
                        f"trace_events[{index}].oracle_source is missing; defaulting to adapter_declared_from_source_test_evidence"
                    )
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
                evidence = op.get("evidence", [])
                if isinstance(evidence, str):
                    evidence_values = [evidence]
                elif isinstance(evidence, list):
                    evidence_values = [item for item in evidence if isinstance(item, str)]
                else:
                    evidence_values = []
                if source_evidence_paths and not any(
                    self._evidence_mentions_known_path(value, source_evidence_paths)
                    for value in evidence_values
                ):
                    warnings.append(
                        f"public_operations.{name}.evidence does not clearly cite a known source test path"
                    )
                if allowed_source_uuids:
                    unknown_sources = sorted(set(source_functions or []) - allowed_source_uuids)
                    if unknown_sources:
                        errors.append(
                            f"public_operations.{name}.source_functions include functions outside "
                            f"public 3A pairs with source-test evidence: {unknown_sources[:10]}"
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
            if isinstance(harness, str) and target_public_name_to_uuids:
                audit = self._harness_api_audit(
                    adapter,
                    harness,
                    target_public_name_to_uuids=target_public_name_to_uuids,
                )
                adapter["_harness_api_audit"] = audit
                for missing in audit.get("declared_but_not_mentioned", []):
                    errors.append(
                        f"public_operations target_functions declares {missing.get('target_function')}, "
                        f"but rust_test_harness does not appear to call/use `{missing.get('leaf_name')}`"
                    )
                undeclared_used_names = audit.get("mentioned_but_not_declared", [])
                if undeclared_used_names:
                    errors.append(
                        "rust_test_harness appears to use target public API names not declared in "
                        f"public_operations.*.target_functions: {undeclared_used_names[:20]}"
                    )
        adapter["_validation_warnings"] = warnings
        return errors

    def _synthesis_scoped_source_uuids(self):
        context = self._last_synthesis_context or {}
        scope = context.get("alignment_scope", {})
        return {
            pair.get("src_uuid")
            for pair in scope.get("public_eligible_pairs_with_src_test_evidence", [])
            if pair.get("src_uuid")
        }

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

    def _synthesis_target_public_name_to_uuids(self):
        mapping = {}
        for item in self._target_public_api_signatures(max_items=None):
            uuid_value = item.get("uuid")
            name = self._uuid_leaf_name(uuid_value)
            if not name:
                continue
            mapping.setdefault(name, set()).add(uuid_value)
        return mapping

    def _target_public_name_to_uuids_from_db(self):
        mapping = {}
        for item in self._target_public_api_signatures(max_items=None):
            uuid_value = item.get("uuid")
            name = self._uuid_leaf_name(uuid_value)
            if not name:
                continue
            mapping.setdefault(name, set()).add(uuid_value)
        return mapping

    def _harness_api_audit(self, adapter, harness, target_public_name_to_uuids=None):
        if not isinstance(harness, str) or not harness.strip():
            return {
                "status": "not_applicable",
                "reason": "rust_test_harness_missing",
            }
        operations = adapter.get("public_operations", {}) if isinstance(adapter, dict) else {}
        target_public_name_to_uuids = target_public_name_to_uuids or self._target_public_name_to_uuids_from_db()
        declared_target_functions = []
        declared_leaf_names = set()
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            for target_function in operation.get("target_functions", []) or []:
                if target_function not in declared_target_functions:
                    declared_target_functions.append(target_function)
                leaf_name = self._uuid_leaf_name(target_function)
                if leaf_name:
                    declared_leaf_names.add(leaf_name)

        mentioned_target_api_names = sorted(
            name
            for name in target_public_name_to_uuids
            if self._rust_code_mentions_identifier(harness, name)
        )
        declared_but_not_mentioned = []
        for target_function in declared_target_functions:
            leaf_name = self._uuid_leaf_name(target_function)
            if leaf_name and not self._rust_code_mentions_identifier(harness, leaf_name):
                declared_but_not_mentioned.append({
                    "target_function": target_function,
                    "leaf_name": leaf_name,
                })

        mentioned_but_not_declared = sorted(set(mentioned_target_api_names) - declared_leaf_names)
        return {
            "status": "audited",
            "heuristic": (
                "Identifier-level Rust harness audit. This is not receiver-aware Rust name resolution; "
                "mentioned_but_not_declared is an audit signal, while declared_but_not_mentioned is treated "
                "as a stronger adapter consistency problem during LLM synthesis."
            ),
            "declared_target_functions": sorted(declared_target_functions),
            "declared_target_api_names": sorted(declared_leaf_names),
            "mentioned_target_api_names": mentioned_target_api_names,
            "declared_but_not_mentioned": declared_but_not_mentioned,
            "mentioned_but_not_declared": mentioned_but_not_declared,
            "mentioned_target_api_uuids_by_name": {
                name: sorted(target_public_name_to_uuids.get(name, []))
                for name in mentioned_target_api_names
            },
        }

    def _synthesis_source_evidence_paths(self):
        context = self._last_synthesis_context or {}
        paths = set()
        source_evidence = context.get("source_evidence", {})
        for item in source_evidence.get("behavior_cases", []):
            path = item.get("path")
            if path:
                paths.add(path)
                paths.add(Path(path).name)
        for item in source_evidence.get("fixtures", []):
            path = item.get("path")
            if path:
                paths.add(path)
                paths.add(Path(path).name)
        for item in source_evidence.get("test_files", []):
            path = item.get("path")
            if path:
                paths.add(path)
                paths.add(Path(path).name)
        for item in source_evidence.get("function_index", {}).values():
            for path in item.get("evidence_paths", []):
                if path:
                    paths.add(path)
                    paths.add(Path(path).name)
        for item in context.get("source_test_evidence", []):
            path = item.get("path")
            if path:
                paths.add(path)
                paths.add(Path(path).name)
        for item in context.get("source_test_case_evidence", []):
            path = item.get("path")
            if path:
                paths.add(path)
                paths.add(Path(path).name)
        for item in context.get("source_assertion_evidence", []):
            path = item.get("path")
            if path:
                paths.add(path)
                paths.add(Path(path).name)
        for entries in context.get("source_function_test_evidence", {}).values():
            for item in entries:
                path = item.get("path")
                if path:
                    paths.add(path)
                    paths.add(Path(path).name)
        return paths

    def _evidence_mentions_known_path(self, evidence, known_paths):
        if not isinstance(evidence, str) or not evidence:
            return False
        evidence_lower = evidence.lower()
        return any(path.lower() in evidence_lower for path in known_paths if path)

    def _uuid_leaf_name(self, uuid_value):
        if not isinstance(uuid_value, str) or not uuid_value:
            return ""
        return uuid_value.rsplit("::", 1)[-1]

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
            if pair.get("src_uuid", "").rsplit("::", 1)[-1] in called_names
        ]
        scoped_source_uuids = {
            pair.get("src_uuid")
            for pair in scoped_pairs
            if pair.get("src_uuid")
        }
        return {
            "schema_version": "3b.adapter_synthesis_context.v4",
            "source_repository": self.src_name,
            "target_repository": self.tgt_name,
            "objective": (
                "Generate a repository-specific 3B public-first adapter. "
                "Use source test evidence and 3A alignments to create replayable public behavior operations."
            ),
            "constraints": [
                "Do not compare ABI, raw pointer values, memory ownership, or raw return types when languages differ.",
                "Derive observable behavior from source tests, fixtures, expected files, and assertion intent.",
                "Use only public target APIs for L1 replay.",
                "If an aligned function has test evidence but no reliable replay recipe, omit it so adapter_missing can report it.",
                "The LLM generates a replay hypothesis; correctness is decided only by compiling and running target replay.",
            ],
            "generation_policy": {
                "public_first": True,
                "default_layer": "public_behavior",
                "adapter_is_repo_specific": True,
                "oracle_rule": (
                    "Every executable assertion must be grounded in source test evidence, fixtures, or a direct "
                    "public API property implied by that evidence. Use oracle_confidence=high only when the "
                    "source test/fixture gives a concrete expected result."
                ),
                "coverage_rule": (
                    "Maximize reliable coverage of source-tested public 3A pairs. Group functions by concrete "
                    "source test cases when needed, and omit a function only when its observable behavior cannot "
                    "be replayed through public target APIs without speculation."
                ),
            },
            "alignment_scope": {
                "public_eligible_pairs_with_src_test_evidence": scoped_pairs,
                "public_eligible_pair_count": len(public_pairs),
                "scoped_pair_count": len(scoped_pairs),
            },
            "test_inventory_summary": inventory.get("summary", {}),
            "source_evidence": self._source_evidence_bundle(inventory, scoped_source_uuids),
            "target_project_context": self._target_project_context(),
            "target_crate_import_hint": self._target_crate_import_hint(),
            "target_api_scope": self._target_api_scope(scoped_pairs),
            "target_public_api_signatures": self._target_public_api_signatures_for_synthesis(scoped_pairs),
            "target_aligned_api_context": self._target_aligned_api_context(scoped_pairs),
            "required_adapter_shape": self._adapter_synthesis_schema_hint(),
        }

    def _source_evidence_bundle(self, inventory, scoped_source_uuids):
        behavior_cases, behavior_case_candidates = self._source_behavior_cases(inventory, scoped_source_uuids)
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
                    "Compact source-test evidence for adapter synthesis. behavior_cases carry oracle evidence; "
                    "function_index maps every source-tested public 3A source function to concrete case ids."
                ),
                "behavior_cases": len(behavior_cases),
                "available_behavior_case_candidates": behavior_case_candidates,
                "mixed_public_internal_behavior_cases": len(mixed_behavior_cases),
                "mixed_public_internal_case_candidates": len(mixed_public_internal_cases),
                "mixed_public_internal_l1_policy": "public_equivalent_required",
                "behavior_case_selection_policy": (
                    "Keep cases that add source-function coverage or contain assertions directly mentioning "
                    "aligned source functions; drop lower-signal duplicates. Mixed public/internal cases may "
                    "support L1 only when the internal state transition is naturally included in the target "
                    "public API behavior or can be expressed through an explicit target public equivalent."
                ),
                "indexed_source_functions": len(scoped_source_uuids),
            },
            "quality_checks": self._source_evidence_quality_checks(
                scoped_source_uuids,
                behavior_cases,
                function_index,
            ),
            "field_guide": {
                "behavior_cases": (
                    "Primary evidence for operation/oracle design. Each case has concrete source assertions, "
                    "literals, aligned source function UUIDs, and a compact relevant snippet. Mixed cases expose "
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
                    "effect through target public behavior; otherwise omit them with a non-public replay reason."
                ),
            },
            "behavior_cases": behavior_cases,
            "function_index": function_index,
            "mixed_public_internal_cases": mixed_public_internal_cases[:20],
            "fixtures": self._source_fixture_evidence(inventory, max_files=12, max_chars_per_file=1200),
        }

    def _source_evidence_quality_checks(self, scoped_source_uuids, behavior_cases, function_index):
        scoped = set(scoped_source_uuids)
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
        }

    def _target_public_api_signatures(self, max_items=180):
        db = self._load_json(self.tgt_db_path)
        items = []
        for file_path, file_data in db.get("files", {}).items():
            for func in file_data.get("functions", []) + file_data.get("standalone_functions", []):
                signature = func.get("signature", "")
                if self._is_target_public(func):
                    items.append({
                        "uuid": f"{file_path}::{func.get('name')}",
                        "signature": signature,
                    })
            for cls in file_data.get("classes", []):
                for method in cls.get("methods", []):
                    if self._is_target_public(method):
                        items.append({
                            "uuid": f"{file_path}::{cls.get('name')}::{method.get('name')}",
                            "signature": method.get("signature", ""),
                        })
            for impl in file_data.get("impl_blocks", []):
                for method in impl.get("methods", []):
                    if self._is_target_public(method):
                        items.append({
                            "uuid": f"{file_path}::{impl.get('target_type')}::{method.get('name')}",
                            "signature": method.get("signature", ""),
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
            r"^(new|from|default|empty|len|get|insert|remove|push|pop|parse|stringify|"
            r"stringify_pretty|dump|pretty|as_|is_|to_|into_|has_)"
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
            if leaf in {"from", "parse", "stringify", "stringify_pretty", "new", "len"}:
                score += 2
            if score:
                scored.append((score, uuid_value, item))
        for _, uuid_value, _ in sorted(scored, key=lambda value: (-value[0], value[1])):
            if len(selected) >= max_items:
                break
            add_uuid(uuid_value)

        return selected

    def _source_test_evidence_snippets(self, inventory, max_files=14, max_chars_per_file=4200):
        evidence = []
        scored_entries = sorted(
            inventory.get("test_files", []),
            key=lambda entry: (len(entry.get("calls_aligned_public_functions", [])), len(entry.get("test_cases", []))),
            reverse=True,
        )
        for entry in scored_entries:
            calls = entry.get("calls_aligned_public_functions", [])
            if not calls:
                continue
            rel_path = entry.get("path", "")
            path = self.src_repo_path / rel_path
            content = self._read_text(path)
            snippet = self._relevant_call_snippet(content, calls, max_chars=max_chars_per_file)
            evidence.append({
                "path": rel_path,
                "frameworks": entry.get("frameworks", []),
                "test_cases": entry.get("test_cases", [])[:20],
                "calls_aligned_public_functions": calls,
                "snippet": snippet,
                "assertion_lines": self._assertion_lines(snippet),
                "literal_samples": self._literal_samples(snippet),
            })
            if len(evidence) >= max_files:
                break
        return evidence

    def _source_behavior_cases(self, inventory, scoped_source_uuids, max_cases=45, max_chars_per_case=900):
        scoped_names_to_uuids = {
            src_uuid.rsplit("::", 1)[-1]: src_uuid
            for src_uuid in scoped_source_uuids
            if src_uuid
        }
        cases = []
        for entry in inventory.get("test_files", []):
            for case in entry.get("aligned_test_cases", []):
                calls = [
                    call for call in case.get("calls_aligned_public_functions", [])
                    if call in scoped_names_to_uuids
                ]
                if not calls:
                    continue
                body = case.get("body_excerpt", "") or ""
                assertions = self._assertion_evidence_items(body, calls, max_items=10)
                item = {
                    "case_id": self._source_case_id(case.get("path", entry.get("path", "")), case.get("name", "")),
                    "path": case.get("path", entry.get("path", "")),
                    "framework": case.get("framework", ""),
                    "name": case.get("name", ""),
                    "aligned_source_functions": [scoped_names_to_uuids[call] for call in calls],
                    "call_names": calls,
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
        return self._select_source_behavior_cases(cases, scoped_source_uuids, max_cases), len(cases)

    def _select_source_behavior_cases(self, cases, scoped_source_uuids, max_cases):
        scoped_source_uuids = set(scoped_source_uuids or [])
        selected = []
        selected_ids = set()
        covered = set()

        def add_case(case):
            case_id = case.get("case_id", "")
            if not case_id or case_id in selected_ids:
                return
            selected.append(case)
            selected_ids.add(case_id)
            covered.update(case.get("aligned_source_functions", []))

        for case in cases:
            case_sources = set(case.get("aligned_source_functions", []))
            direct_assertions = sum(
                1 for assertion in case.get("assertions", [])
                if assertion.get("mentions_aligned_functions")
            )
            adds_new_coverage = bool(case_sources - covered)
            if adds_new_coverage or direct_assertions > 0:
                add_case(case)
            if len(selected) >= max_cases and scoped_source_uuids <= covered:
                break

        if not scoped_source_uuids <= covered:
            for case in cases:
                if set(case.get("aligned_source_functions", [])) - covered:
                    add_case(case)
                if scoped_source_uuids <= covered:
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
                source_name = src_uuid.rsplit("::", 1)[-1]
                for assertion in case.get("assertions", []):
                    if source_name not in assertion.get("mentions_aligned_functions", []):
                        continue
                    direct_assertions = direct_assertions_by_source[src_uuid]
                    expression = assertion.get("expression", "")
                    if expression and expression not in [item.get("expression", "") for item in direct_assertions]:
                        direct_assertions.append({
                            "case_id": case.get("case_id", ""),
                            "expression": expression,
                            "oracle_hint": assertion.get("oracle_hint", ""),
                            "literal_samples": assertion.get("literal_samples", [])[:6],
                        })
                    if len(direct_assertions_by_source[src_uuid]) >= max_direct_assertions_per_function:
                        break

        scoped_names = {
            src_uuid.rsplit("::", 1)[-1]: src_uuid
            for src_uuid in scoped_source_uuids
            if src_uuid
        }
        for entry in inventory.get("test_files", []):
            rel_path = entry.get("path", "")
            for call in entry.get("calls_aligned_public_functions", []):
                src_uuid = scoped_names.get(call)
                if src_uuid in paths_by_source:
                    paths_by_source[src_uuid].add(rel_path)

        return {
            src_uuid: {
                "source_name": src_uuid.rsplit("::", 1)[-1],
                "evidence_paths": sorted(path for path in paths_by_source.get(src_uuid, set()) if path),
                "case_refs": cases_by_source.get(src_uuid, []),
                "direct_assertions": direct_assertions_by_source.get(src_uuid, []),
            }
            for src_uuid in sorted(scoped_source_uuids)
        }

    def _source_test_case_evidence(self, inventory, max_cases=60, max_chars_per_case=1600):
        cases = []
        for entry in inventory.get("test_files", []):
            for case in entry.get("aligned_test_cases", []):
                calls = case.get("calls_aligned_public_functions", [])
                if not calls:
                    continue
                item = {
                    "path": case.get("path", entry.get("path", "")),
                    "framework": case.get("framework", ""),
                    "name": case.get("name", ""),
                    "calls_aligned_functions": case.get("calls_aligned_functions", []),
                    "calls_aligned_public_functions": calls,
                    "calls_aligned_non_public_functions": case.get("calls_aligned_non_public_functions", []),
                    "has_mixed_public_internal_calls": bool(case.get("has_mixed_public_internal_calls")),
                    "case_complexity": self._test_case_complexity(calls),
                    "assertion_lines": case.get("assertion_lines", []),
                    "assertion_evidence": self._assertion_evidence_items(
                        case.get("body_excerpt", "") or "",
                        calls,
                    ),
                    "literal_samples": case.get("literal_samples", []),
                    "body_excerpt": (case.get("body_excerpt", "") or "")[:max_chars_per_case],
                }
                cases.append(item)
        cases.sort(
            key=self._test_case_evidence_sort_key,
            reverse=True,
        )
        return cases[:max_cases]

    def _source_assertion_evidence(self, inventory, max_cases=80, max_assertions_per_case=8):
        evidence = []
        for entry in inventory.get("test_files", []):
            for case in entry.get("aligned_test_cases", []):
                calls = case.get("calls_aligned_public_functions", [])
                if not calls:
                    continue
                assertions = self._assertion_evidence_items(
                    case.get("body_excerpt", "") or "",
                    calls,
                    max_items=max_assertions_per_case,
                )
                if not assertions:
                    continue
                evidence.append({
                    "path": case.get("path", entry.get("path", "")),
                    "framework": case.get("framework", ""),
                    "test_name": case.get("name", ""),
                    "calls_aligned_functions": case.get("calls_aligned_functions", []),
                    "calls_aligned_public_functions": calls,
                    "calls_aligned_non_public_functions": case.get("calls_aligned_non_public_functions", []),
                    "has_mixed_public_internal_calls": bool(case.get("has_mixed_public_internal_calls")),
                    "assertions": assertions,
                })
        evidence.sort(
            key=lambda item: (
                sum(len(assertion.get("mentions_aligned_functions", [])) for assertion in item.get("assertions", [])) > 0,
                sum(len(assertion.get("mentions_aligned_functions", [])) for assertion in item.get("assertions", [])),
                min(len(item.get("assertions", [])), 8),
                -len(item.get("calls_aligned_public_functions", [])),
            ),
            reverse=True,
        )
        return evidence[:max_cases]

    def _test_case_complexity(self, calls):
        count = len(calls or [])
        if count <= 3:
            return "focused"
        if count <= 8:
            return "moderate"
        return "broad"

    def _test_case_evidence_sort_key(self, item):
        call_count = len(item.get("calls_aligned_public_functions", []))
        assertion_count = len(item.get("assertion_lines", []))
        complexity = item.get("case_complexity", "")
        focused_bonus = {"focused": 5, "moderate": 3, "broad": 0}.get(complexity, 0)
        broad_penalty = max(0, call_count - 8) * 2
        return (
            focused_bonus + min(assertion_count, 5) + min(call_count, 4) - broad_penalty,
            -call_count,
            assertion_count,
        )

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
            source_name = src_uuid.rsplit("::", 1)[-1]
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
            r"\b(TEST_ASSERT|CU_ASSERT|ASSERT|EXPECT|REQUIRE|CHECK)\w*\b",
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
                "oracle_hint": self._oracle_hint_from_assertion(expression),
            })
            if len(items) >= max_items:
                break
        return items

    def _oracle_hint_from_assertion(self, assertion_line):
        line = assertion_line.strip()
        if re.search(r"\b(TEST_ASSERT|ASSERT|EXPECT).*_NOT_NULL", line):
            return "non_null_oracle"
        if re.search(r"\b(TEST_ASSERT|ASSERT|EXPECT).*_NULL", line):
            return "null_oracle"
        if re.search(r"\b(EXPECT|ASSERT|TEST_ASSERT).*_EQUAL", line) or re.search(r"\bEXPECT_EQ\s*\(|\bASSERT_EQ\s*\(", line):
            return "equality_oracle"
        if re.search(r"\b(EXPECT|ASSERT|TEST_ASSERT).*_TRUE", line) or re.search(r"\bEXPECT_TRUE\s*\(|\bASSERT_TRUE\s*\(", line):
            return "truth_oracle"
        if re.search(r"\b(EXPECT|ASSERT|TEST_ASSERT).*_FALSE", line) or re.search(r"\bEXPECT_FALSE\s*\(|\bASSERT_FALSE\s*\(", line):
            return "falsehood_oracle"
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
        lib_rs = self._read_text(self.tgt_repo_path / "src" / "lib.rs", max_chars=3200) if self.tgt_repo_path else ""
        return {
            "cargo_toml": cargo_toml,
            "src_lib_rs": lib_rs,
            "note": "Use Cargo.toml package/lib names and public exports when writing Rust integration tests.",
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

    def _target_aligned_api_context(self, scoped_pairs, max_items=90, max_body_chars=900):
        target_uuids = []
        seen = set()
        for pair in scoped_pairs:
            for tgt_uuid in pair.get("tgt_uuids", []):
                if tgt_uuid and tgt_uuid not in seen:
                    seen.add(tgt_uuid)
                    target_uuids.append(tgt_uuid)
        target_index = self._index_functions(self.tgt_db_path)
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
                    "input": {"case": "short description"},
                    "expected": {"observable_behavior": "short oracle summary"},
                    "oracle_source": "source_test_assertion|source_fixture|source_test_property",
                    "oracle_confidence": "high|medium|low"
                }
            ],
            "rust_test_harness": "Complete Rust integration test source for tests/cp2rs_3b_public.rs. It must define exactly one #[test] fn for each trace_events[].id, using the id as the function name.",
        }

    def _build_adapter_synthesis_prompt(self, context):
        context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        return PROMPT_3B_ADAPTER_SYNTHESIS.format(context_json=context_json)

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
        return json.loads(text, strict=False)

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

    def _index_functions(self, db_path):
        db = self._load_json(db_path)
        index = {}
        for file_path, file_data in db.get("files", {}).items():
            for func in file_data.get("functions", []) + file_data.get("standalone_functions", []):
                uid = f"{file_path}::{func.get('name')}"
                index[uid] = func
            for cls in file_data.get("classes", []):
                for method in cls.get("methods", []):
                    uid = f"{file_path}::{cls.get('name')}::{method.get('name')}"
                    index[uid] = method
            for impl in file_data.get("impl_blocks", []):
                for method in impl.get("methods", []):
                    uid = f"{file_path}::{impl.get('target_type')}::{method.get('name')}"
                    index[uid] = method
        return index

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
        return not func.get("is_static", False)

    def _is_target_public(self, func):
        if not func:
            return False
        signature = func.get("signature", "")
        return "pub fn " in signature or signature.strip().startswith("pub ")

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
            return data

        default_adapter = self._load_default_adapter()
        if default_adapter:
            return default_adapter

        src_key = self.src_name.lower()
        tgt_key = self.tgt_name.lower()
        if src_key == "cjson" and tgt_key == "json-rust":
            data = self._builtin_cjson_json_rust_adapter()
            data["_adapter_source_path"] = "builtin"
            return data

        return {
            "name": "none",
            "status": "adapter_missing",
            "public_operations": {},
        }

    def _find_default_adapter_path(self):
        for path in self.default_adapter_candidates(self.src_name, self.tgt_name):
            if not path.exists():
                continue
            if self._is_generated_adapter_cache_path(path):
                try:
                    data = self._load_json(path)
                except (OSError, json.JSONDecodeError):
                    continue
                if not self._is_reusable_generated_adapter_cache(data):
                    continue
            return path
        return None

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
        return self._is_reusable_generated_adapter_cache_static(adapter)

    @classmethod
    def _is_reusable_generated_adapter_cache_static(cls, adapter):
        if adapter.get("_adapter_cache_status") != "reusable_after_validated_replay":
            return False
        if adapter.get("_last_replay_status") != "passed":
            return False
        if adapter.get("_validation_warnings"):
            return False
        audit = adapter.get("_harness_api_audit") or {}
        if audit.get("mentioned_but_not_declared"):
            return False
        status_counts = adapter.get("_trace_alignment_status_counts") or {}
        disallowed = set(status_counts) - {"fully_aligned"}
        if disallowed:
            return False
        if not status_counts.get("fully_aligned", 0):
            return False
        coverage_scope = adapter.get("_cache_coverage_scope") or {}
        if not coverage_scope:
            return False
        scoped_sources = coverage_scope.get("source_functions_with_src_test_evidence_count", 0)
        if scoped_sources <= 0:
            return False
        if coverage_scope.get("adapter_missing_source_function_count", 0) != 0:
            return False
        if coverage_scope.get("untraced_source_function_count", 0) != 0:
            return False
        if coverage_scope.get("validated_traced_source_function_count", 0) != scoped_sources:
            return False
        return True

    def _builtin_cjson_json_rust_adapter(self):
        return {
            "name": "builtin_cjson_to_json_rust_public_v1",
            "status": "loaded",
            "description": "Public JSON parse/dump replay for cJSON -> json-rust.",
            "target_language": "rust",
            "target_test_command": ["cargo", "test", "--test", "cp2rs_3b_public"],
            "public_operations": {
                "json_parse_dump_roundtrip": {
                    "description": "Parse a JSON text and dump it back to parseable JSON.",
                    "source_functions": [
                        "cJSON.c::cJSON_Parse",
                        "cJSON.c::cJSON_PrintUnformatted",
                    ],
                    "target_functions": [
                        "src/parser.rs::parse",
                        "src/value/mod.rs::JsonValue::dump",
                    ],
                },
                "json_parse_should_fail": {
                    "description": "Invalid JSON should fail to parse.",
                    "source_functions": [
                        "cJSON.c::cJSON_Parse",
                    ],
                    "target_functions": [
                        "src/parser.rs::parse",
                    ],
                },
                "json_parse_with_opts_roundtrip": {
                    "description": "cJSON_ParseWithOpts success cases normalized to json::parse success.",
                    "source_functions": [
                        "cJSON.c::cJSON_ParseWithOpts",
                    ],
                    "target_functions": [
                        "src/parser.rs::parse",
                    ],
                },
                "json_parse_with_opts_should_fail": {
                    "description": "cJSON_ParseWithOpts failure cases normalized to json::parse error.",
                    "source_functions": [
                        "cJSON.c::cJSON_ParseWithOpts",
                    ],
                    "target_functions": [
                        "src/parser.rs::parse",
                    ],
                },
                "json_array_len": {
                    "description": "Array size observable normalized to JsonValue::len.",
                    "source_functions": [
                        "cJSON.c::cJSON_GetArraySize",
                    ],
                    "target_functions": [
                        "src/value/mod.rs::JsonValue::len",
                    ],
                },
            },
        }

    def discover_tests(self, alignment_stats):
        aligned_names = {
            uuid.rsplit("::", 1)[-1]
            for uuid in alignment_stats.get("unique_aligned_source_functions", [])
        }
        public_names = {
            uuid.rsplit("::", 1)[-1]
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
    ):
        if not block:
            return None
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
            "start_line": self._line_number_for_offset(block, 0),
            "calls_aligned_functions": all_calls,
            "calls_aligned_public_functions": public_calls,
            "calls_aligned_non_public_functions": non_public_calls,
            "has_mixed_public_internal_calls": bool(public_calls and non_public_calls),
            "assertion_lines": self._assertion_lines(block),
            "literal_samples": self._literal_samples(block),
            "body_excerpt": excerpt,
        }

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
        return excerpt[:max_chars]

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

    def record_public_traces(self, inventory, alignment_stats, adapter):
        if adapter.get("status") != "loaded":
            return self._empty_trace_corpus("adapter_missing")

        if (
            adapter.get("recorder") == "cjson_json_public_fixture_v1"
            or adapter.get("name") == "builtin_cjson_to_json_rust_public_v1"
        ):
            return self._record_builtin_cjson_json_traces(inventory, adapter)
        if adapter.get("recorder") == "adapter_declared_trace_events_v1":
            return self._record_adapter_declared_traces(adapter)

        return self._empty_trace_corpus("adapter_has_no_recorder")

    def _empty_trace_corpus(self, reason):
        return {
            "schema_version": "3b.trace_corpus.v2",
            "status": "empty",
            "recording_strategy": "public_first",
            "skip_reason": reason,
            "events": [],
            "summary": {
                "events": 0,
                "traced_source_functions": 0,
                "traced_target_functions": 0,
                "validated_aligned_source_functions": 0,
                "validated_aligned_target_functions": 0,
                "covered_aligned_pairs": 0,
                "alignment_status_counts": {},
            },
        }

    def _record_builtin_cjson_json_traces(self, inventory, adapter):
        events = []
        inputs_dir = self.src_repo_path / "tests" / "inputs"
        if inputs_dir.exists():
            for expected_path in sorted(inputs_dir.glob("*.expected")):
                if not self._operation_available(adapter, "json_parse_dump_roundtrip"):
                    break
                input_path = expected_path.with_suffix("")
                if not input_path.exists():
                    continue
                source_text = self._read_text(input_path)
                events.append(self._trace_event(
                    operation="json_parse_dump_roundtrip",
                    evidence=f"tests/inputs/{input_path.name} + {expected_path.name}",
                    json_text=source_text,
                    expect_parse_ok=True,
                    adapter=adapter,
                ))

            for input_path in sorted(inputs_dir.iterdir()):
                if not self._operation_available(adapter, "json_parse_should_fail"):
                    break
                if input_path.suffix == ".expected" or not input_path.is_file():
                    continue
                if input_path.with_suffix(input_path.suffix + ".expected").exists():
                    continue
                if (inputs_dir / f"{input_path.name}.expected").exists():
                    continue
                source_text = self._read_text(input_path)
                events.append(self._trace_event(
                    operation="json_parse_should_fail",
                    evidence=f"tests/inputs/{input_path.name}",
                    json_text=source_text,
                    expect_parse_ok=False,
                    adapter=adapter,
                ))

        events.extend(self._builtin_parse_with_opts_events(adapter))
        events.extend(self._builtin_array_len_events(adapter))
        events.extend(self._builtin_container_creation_events(adapter))
        events.extend(self._builtin_array_push_len_events(adapter))
        events.extend(self._builtin_object_insert_get_has_events(adapter))
        events.extend(self._builtin_type_predicate_events(adapter))
        events.extend(self._builtin_object_remove_replace_events(adapter))
        events.extend(self._builtin_array_remove_events(adapter))

        if not events:
            return self._empty_trace_corpus("no_cjson_input_fixtures_found")

        return {
            "schema_version": "3b.trace_corpus.v2",
            "status": "recorded",
            "recording_strategy": "public_fixture_trace_v1",
            "note": "Public-first V1 uses source test fixtures as stable trace inputs; it does not translate test code.",
            "events": events,
            "summary": self._build_trace_summary(events),
        }

    def _operation_available(self, adapter, operation):
        return operation in adapter.get("public_operations", {})

    def _record_adapter_declared_traces(self, adapter):
        events = []
        declared_events = adapter.get("trace_events") or []
        if declared_events:
            for declared in declared_events:
                operation = declared.get("operation")
                if not operation or not self._operation_available(adapter, operation):
                    continue
                events.append(self._trace_event_from_adapter_declaration(adapter, declared))
        else:
            for operation, op in adapter.get("public_operations", {}).items():
                events.append(self._trace_event_from_adapter_declaration(adapter, {
                    "operation": operation,
                    "evidence": "; ".join(op.get("evidence", [])) if isinstance(op.get("evidence"), list) else op.get("evidence", ""),
                    "input": {"case": operation},
                    "expected": {"observable_behavior": op.get("normalization", "")},
                }))

        if not events:
            return self._empty_trace_corpus("adapter_declared_no_trace_events")

        return {
            "schema_version": "3b.trace_corpus.v2",
            "status": "recorded",
            "recording_strategy": "adapter_declared_trace_events_v1",
            "note": "Trace events were declared by the effective adapter generated from source test evidence.",
            "events": events,
            "summary": self._build_trace_summary(events),
        }

    def _trace_event_from_adapter_declaration(self, adapter, declared):
        operation = declared["operation"]
        op = adapter["public_operations"][operation]
        event_id = declared.get("id") or f"trace_{operation}_{uuid.uuid4().hex[:8]}"
        return {
            "id": event_id,
            "layer": "public_behavior",
            "operation": operation,
            "evidence": declared.get("evidence", ""),
            "source_functions": op.get("source_functions", []),
            "target_functions": op.get("target_functions", []),
            "operation_metadata": {
                "description": op.get("description", ""),
                "normalization": op.get("normalization", ""),
                "normalization_status": "adapter_declared_v1",
                "adapter_generation_status": adapter.get("generation_status", ""),
            },
            "input": declared.get("input", {}),
            "expected": declared.get("expected", {}),
            "oracle_source": declared.get("oracle_source", "adapter_declared_from_source_test_evidence"),
            "oracle_confidence": declared.get("oracle_confidence", "medium"),
        }

    def _builtin_parse_with_opts_events(self, adapter):
        if not (
            self._operation_available(adapter, "json_parse_with_opts_roundtrip")
            and self._operation_available(adapter, "json_parse_with_opts_should_fail")
        ):
            return []
        return [
            self._trace_event(
                operation="json_parse_with_opts_roundtrip",
                evidence="tests/parse_with_opts.c::parse_with_opts_should_require_null_if_requested",
                json_text="{}",
                expect_parse_ok=True,
                adapter=adapter,
            ),
            self._trace_event(
                operation="json_parse_with_opts_roundtrip",
                evidence="tests/parse_with_opts.c::parse_with_opts_should_require_null_if_requested",
                json_text="{} \n",
                expect_parse_ok=True,
                adapter=adapter,
            ),
            self._trace_event(
                operation="json_parse_with_opts_should_fail",
                evidence="tests/parse_with_opts.c::parse_with_opts_should_require_null_if_requested",
                json_text="{}x",
                expect_parse_ok=False,
                adapter=adapter,
            ),
            self._trace_event(
                operation="json_parse_with_opts_should_fail",
                evidence="tests/parse_with_opts.c::parse_with_opts_should_handle_incomplete_json",
                json_text="{",
                expect_parse_ok=False,
                adapter=adapter,
            ),
        ]

    def _builtin_array_len_events(self, adapter):
        if not self._operation_available(adapter, "json_array_len"):
            return []
        return [
            self._trace_event(
                operation="json_array_len",
                evidence="tests/misc_tests.c::cJSON_GetArraySize",
                json_text="[]",
                expect_parse_ok=True,
                adapter=adapter,
                extra_expected={"array_len": 0},
            ),
            self._trace_event(
                operation="json_array_len",
                evidence="tests/misc_tests.c::cJSON_GetArraySize",
                json_text="[1]",
                expect_parse_ok=True,
                adapter=adapter,
                extra_expected={"array_len": 1},
            ),
            self._trace_event(
                operation="json_array_len",
                evidence="tests/misc_tests.c::cJSON_GetArraySize",
                json_text="[1,2,3]",
                expect_parse_ok=True,
                adapter=adapter,
                extra_expected={"array_len": 3},
            ),
        ]

    def _builtin_container_creation_events(self, adapter):
        operation = "json_container_creation"
        if not self._operation_available(adapter, operation):
            return []
        return [
            self._trace_event(
                operation=operation,
                evidence="tests/misc_tests.c::cjson_should_not_parse_to_deeply_nested_jsons + tests/cjson_add.c",
                adapter=adapter,
                input_payload={"case": "empty_object_and_array"},
                extra_expected={"object_len": 0, "array_len": 0},
            ),
        ]

    def _builtin_array_push_len_events(self, adapter):
        operation = "json_array_push_len"
        if not self._operation_available(adapter, operation):
            return []
        return [
            self._trace_event(
                operation=operation,
                evidence="tests/readme_examples.c::create_monitor + tests/misc_tests.c::cJSON_AddItemToArray",
                adapter=adapter,
                input_payload={"case": "push_number_string_object"},
                extra_expected={"array_len": 3},
            ),
        ]

    def _builtin_object_insert_get_has_events(self, adapter):
        operation = "json_object_insert_get_has"
        if not self._operation_available(adapter, operation):
            return []
        return [
            self._trace_event(
                operation=operation,
                evidence="tests/cjson_add.c + tests/misc_tests.c::cJSON_GetObjectItemCaseSensitive",
                adapter=adapter,
                input_payload={"case": "insert_number_string_bool_array_object"},
                extra_expected={"has_name": True, "number": 42, "string": "Hello World!"},
            ),
        ]

    def _builtin_type_predicate_events(self, adapter):
        operation = "json_type_predicates"
        if not self._operation_available(adapter, operation):
            return []
        return [
            self._trace_event(
                operation=operation,
                evidence="tests/misc_tests.c::type predicates + tests/readme_examples.c",
                adapter=adapter,
                input_payload={"case": "valid_value_type_predicates"},
                extra_expected={"valid_predicates": True},
            ),
        ]

    def _builtin_object_remove_replace_events(self, adapter):
        operation = "json_object_remove_replace"
        if not self._operation_available(adapter, operation):
            return []
        return [
            self._trace_event(
                operation=operation,
                evidence="tests/misc_tests.c::cJSON_ReplaceItemInObject + null_pointer_should_not_crash",
                adapter=adapter,
                input_payload={"case": "remove_then_replace_object_member"},
                extra_expected={"removed": "old", "replacement": "new"},
            ),
        ]

    def _builtin_array_remove_events(self, adapter):
        operation = "json_array_remove"
        if not self._operation_available(adapter, operation):
            return []
        return [
            self._trace_event(
                operation=operation,
                evidence="tests/misc_tests.c::cJSON_DetachItemFromArray + cJSON_DeleteItemFromArray",
                adapter=adapter,
                input_payload={"case": "remove_first_item"},
                extra_expected={"removed": "first", "remaining_len": 1},
            ),
        ]

    def _trace_event(
        self,
        operation,
        evidence,
        adapter,
        json_text=None,
        expect_parse_ok=None,
        input_payload=None,
        extra_expected=None,
    ):
        op = adapter["public_operations"][operation]
        event_id = f"trace_{operation}_{uuid.uuid4().hex[:8]}"
        expected = {}
        if expect_parse_ok is not None:
            expected["parse_ok"] = expect_parse_ok
            expected["dump_reparse_ok"] = expect_parse_ok and operation == "json_parse_dump_roundtrip"
        if extra_expected:
            expected.update(extra_expected)
        if input_payload is None:
            input_payload = {"json_text": json_text}
        return {
            "id": event_id,
            "layer": "public_behavior",
            "operation": operation,
            "evidence": evidence,
            "source_functions": op["source_functions"],
            "target_functions": op["target_functions"],
            "operation_metadata": {
                "description": op.get("description", ""),
                "normalization": op.get("normalization", ""),
                "normalization_status": "documentation_only_v1",
                "adapter_generation_status": adapter.get("generation_status", ""),
            },
            "input": input_payload,
            "expected": expected,
            "oracle_source": "source_test_fixture",
            "oracle_confidence": "high",
        }

    def _ensure_trace_alignment_validation(self, trace_corpus, alignment_stats, adapter):
        if trace_corpus.get("status") != "recorded":
            return trace_corpus

        for event in trace_corpus.get("events", []):
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

            event["alignment_validation"] = self._validate_operation_alignment(operation, op, alignment_stats)

        trace_corpus["summary"] = self._build_trace_summary(trace_corpus.get("events", []))
        trace_corpus["schema_version"] = "3b.trace_corpus.v2"
        return trace_corpus

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

    def _build_trace_summary(self, events):
        traced_src = sorted({fn for event in events for fn in event.get("source_functions", [])})
        traced_tgt = sorted({fn for event in events for fn in event.get("target_functions", [])})
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
            "traced_source_functions": len(traced_src),
            "traced_target_functions": len(traced_tgt),
            "traced_source_function_ids": traced_src,
            "traced_target_function_ids": traced_tgt,
            "validated_aligned_source_functions": len(validated_src),
            "validated_aligned_target_functions": len(validated_tgt),
            "validated_aligned_source_function_ids": sorted(validated_src),
            "validated_aligned_target_function_ids": sorted(validated_tgt),
            "covered_aligned_pairs": len(covered_pair_keys),
            "alignment_status_counts": alignment_status_counts,
            "mapping_shape_counts": mapping_shape_counts,
            "support_target_functions": sorted(support_targets),
        }

    def replay_public_traces(self, trace_corpus, adapter, mode, work_root=None):
        if mode in {"inventory", "record"}:
            return {
                "status": "not_run",
                "reason": f"three_b_mode_{mode}",
                "events": [],
                "summary": self._empty_replay_summary(),
            }
        if trace_corpus.get("status") != "recorded":
            return {
                "status": "not_run",
                "reason": trace_corpus.get("skip_reason", "trace_corpus_empty"),
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
        test_file.write_text(self._generate_rust_public_test(trace_corpus, adapter), encoding="utf-8")

        cmd = adapter.get("target_test_command") or ["cargo", "test", "--test", "cp2rs_3b_public"]
        started = datetime.utcnow().isoformat() + "Z"
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
            stdout = completed.stdout[-12000:]
            stderr = completed.stderr[-12000:]
        except FileNotFoundError as exc:
            return self._infrastructure_replay_failure(str(exc), str(target_copy), str(test_file))
        except subprocess.TimeoutExpired as exc:
            return self._infrastructure_replay_failure(f"timeout: {exc}", str(target_copy), str(test_file))

        if returncode != 0 and self._looks_like_infrastructure_failure(stdout, stderr):
            summary = self._empty_replay_summary()
            summary.update({
                "generated_test_file": self._display_path(test_file),
                "target_worktree": self._display_path(target_copy),
                "command": cmd,
                "started_at": started,
                "returncode": returncode,
                "infrastructure_failures": 1,
                "failure_reason": "target_replay_build_or_environment_failure",
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            })
            return {
                "status": "infrastructure_failed",
                "reason": "target_replay_build_or_environment_failure",
                "events": [],
                "summary": summary,
            }

        events = []
        semantic_failures = []
        overall_status = "passed" if returncode == 0 else "failed"
        test_statuses = self._parse_rust_test_statuses(stdout)
        for event in trace_corpus.get("events", []):
            event_status = self._status_for_trace_event(event, test_statuses, overall_status)
            replay_event = {
                "id": event["id"],
                "operation": event["operation"],
                "status": event_status,
                "source_functions": event["source_functions"],
                "target_functions": event["target_functions"],
                "alignment_validation": event.get("alignment_validation", {}),
                "oracle_source": event.get("oracle_source", ""),
                "oracle_confidence": event.get("oracle_confidence", ""),
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
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        }
        return {"status": overall_status, "events": events, "summary": summary}

    def _parse_rust_test_statuses(self, stdout):
        statuses = {}
        for match in re.finditer(r"^\s*test\s+([A-Za-z_][\w:]*)\s+\.\.\.\s+([A-Z]+|ok|ignored)\s*$", stdout or "", flags=re.M):
            raw_name, raw_status = match.groups()
            normalized = "passed" if raw_status == "ok" else raw_status.lower()
            statuses[raw_name] = normalized
            statuses[raw_name.rsplit("::", 1)[-1]] = normalized
        return statuses

    def _status_for_trace_event(self, event, test_statuses, overall_status):
        event_id = event.get("id", "")
        if event_id in test_statuses:
            status = test_statuses[event_id]
            return "passed" if status == "passed" else "failed"
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

    def _empty_replay_summary(self):
        return {
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "semantic_failures": 0,
            "infrastructure_failures": 0,
        }

    def _generate_rust_public_test(self, trace_corpus, adapter=None):
        if adapter and adapter.get("replay_generator") == "rust_inline_harness_v1":
            return self._rust_inline_harness_from_adapter(adapter)

        success_cases = []
        failure_cases = []
        array_len_cases = []
        operation_case_ids = {
            "json_container_creation": [],
            "json_array_push_len": [],
            "json_object_insert_get_has": [],
            "json_type_predicates": [],
            "json_object_remove_replace": [],
            "json_array_remove": [],
        }
        for event in trace_corpus.get("events", []):
            operation = event["operation"]
            if operation == "json_array_len":
                array_len_cases.append((
                    event["id"],
                    event["input"]["json_text"],
                    event["expected"]["array_len"],
                ))
                continue

            if operation in operation_case_ids:
                operation_case_ids[operation].append(event["id"])
                continue

            case = (event["id"], event["input"].get("json_text", ""))
            if event["expected"].get("parse_ok") is True:
                success_cases.append(case)
            elif event["expected"].get("parse_ok") is False:
                failure_cases.append(case)

        success_body = self._rust_case_array(success_cases)
        failure_body = self._rust_case_array(failure_cases)
        array_len_body = self._rust_array_len_case_array(array_len_cases)
        container_body = self._rust_name_array(operation_case_ids["json_container_creation"])
        array_push_body = self._rust_name_array(operation_case_ids["json_array_push_len"])
        object_insert_body = self._rust_name_array(operation_case_ids["json_object_insert_get_has"])
        type_predicate_body = self._rust_name_array(operation_case_ids["json_type_predicates"])
        object_remove_body = self._rust_name_array(operation_case_ids["json_object_remove_replace"])
        array_remove_body = self._rust_name_array(operation_case_ids["json_array_remove"])

        return f"""extern crate json;

use json::JsonValue;
use json::object::Object;

#[test]
fn cp2rs_public_parse_success_traces() {{
    let cases: &[(&str, &str)] = &{success_body};
    for (name, source) in cases {{
        let parsed = json::parse(source).unwrap_or_else(|err| panic!("{{}} parse failed: {{:?}}", name, err));
        let dumped = parsed.dump();
        json::parse(&dumped).unwrap_or_else(|err| panic!("{{}} dump reparse failed: {{:?}}; dump={{}}", name, err, dumped));
    }}
}}

#[test]
fn cp2rs_public_parse_failure_traces() {{
    let cases: &[(&str, &str)] = &{failure_body};
    for (name, source) in cases {{
        assert!(json::parse(source).is_err(), "{{}} unexpectedly parsed successfully", name);
    }}
}}

#[test]
fn cp2rs_public_array_len_traces() {{
    let cases: &[(&str, &str, usize)] = &{array_len_body};
    for (name, source, expected_len) in cases {{
        let parsed = json::parse(source).unwrap_or_else(|err| panic!("{{}} parse failed: {{:?}}", name, err));
        assert_eq!(parsed.len(), *expected_len, "{{}} array length mismatch", name);
    }}
}}

#[test]
fn cp2rs_public_container_creation_traces() {{
    let cases: &[&str] = &{container_body};
    for name in cases {{
        let object = JsonValue::new_object();
        assert!(object.is_object(), "{{}} expected object", name);
        assert_eq!(object.len(), 0, "{{}} expected empty object", name);

        let array = JsonValue::new_array();
        assert!(array.is_array(), "{{}} expected array", name);
        assert_eq!(array.len(), 0, "{{}} expected empty array", name);
    }}
}}

#[test]
fn cp2rs_public_array_push_len_traces() {{
    let cases: &[&str] = &{array_push_body};
    for name in cases {{
        let mut array = JsonValue::new_array();
        array.push(1).unwrap_or_else(|err| panic!("{{}} push number failed: {{:?}}", name, err));
        array.push("two").unwrap_or_else(|err| panic!("{{}} push string failed: {{:?}}", name, err));
        array.push(JsonValue::new_object()).unwrap_or_else(|err| panic!("{{}} push object failed: {{:?}}", name, err));

        assert_eq!(array.len(), 3, "{{}} array length after push mismatch", name);
        assert_eq!(array[0].as_f64(), Some(1.0), "{{}} first array item mismatch", name);
        assert_eq!(array[1].as_str(), Some("two"), "{{}} second array item mismatch", name);
        assert!(array[2].is_object(), "{{}} third array item should be object", name);
    }}
}}

#[test]
fn cp2rs_public_object_insert_get_has_traces() {{
    let cases: &[&str] = &{object_insert_body};
    for name in cases {{
        let mut object = Object::new();
        object.insert("number", JsonValue::from(42));
        object.insert("string", JsonValue::from("Hello World!"));
        object.insert("flag", JsonValue::from(true));
        object.insert("array", JsonValue::new_array());
        object.insert("object", JsonValue::new_object());

        assert_eq!(object.get("number").and_then(|value| value.as_f64()), Some(42.0), "{{}} number member mismatch", name);
        assert_eq!(object.get("string").and_then(|value| value.as_str()), Some("Hello World!"), "{{}} string member mismatch", name);
        assert!(object.get("flag").map(|value| value.is_boolean()).unwrap_or(false), "{{}} flag member missing", name);
        assert!(object.get("array").map(|value| value.is_array()).unwrap_or(false), "{{}} array member missing", name);
        assert!(object.get("object").map(|value| value.is_object()).unwrap_or(false), "{{}} object member missing", name);

        let mut value = JsonValue::new_object();
        value.insert("name", "Ada").unwrap_or_else(|err| panic!("{{}} JsonValue::insert failed: {{:?}}", name, err));
        assert!(value.has_key("name"), "{{}} JsonValue::has_key should find inserted key", name);
        assert_eq!(value["name"].as_str(), Some("Ada"), "{{}} inserted JsonValue member mismatch", name);
    }}
}}

#[test]
fn cp2rs_public_type_predicate_traces() {{
    let cases: &[&str] = &{type_predicate_body};
    for name in cases {{
        assert!(JsonValue::from("text").is_string(), "{{}} string predicate failed", name);
        assert!(JsonValue::from(42).is_number(), "{{}} number predicate failed", name);
        assert!(JsonValue::from(true).is_boolean(), "{{}} boolean predicate failed", name);
        assert!(JsonValue::Null.is_null(), "{{}} null predicate failed", name);
        assert!(JsonValue::new_array().is_array(), "{{}} array predicate failed", name);
        assert!(JsonValue::new_object().is_object(), "{{}} object predicate failed", name);
    }}
}}

#[test]
fn cp2rs_public_object_remove_replace_traces() {{
    let cases: &[&str] = &{object_remove_body};
    for name in cases {{
        let mut object = Object::new();
        object.insert("item", JsonValue::from("old"));
        let removed = object.remove("item").unwrap_or_else(|| panic!("{{}} expected removed object member", name));
        assert_eq!(removed.as_str(), Some("old"), "{{}} removed object member mismatch", name);
        assert!(object.get("item").is_none(), "{{}} object member should be absent after remove", name);

        object.insert("item", JsonValue::from("old"));
        object.insert("item", JsonValue::from("new"));
        assert_eq!(object.get("item").and_then(|value| value.as_str()), Some("new"), "{{}} replacement through Object::insert mismatch", name);

        let mut value = JsonValue::new_object();
        value.insert("item", "old").unwrap_or_else(|err| panic!("{{}} initial JsonValue::insert failed: {{:?}}", name, err));
        value.insert("item", "new").unwrap_or_else(|err| panic!("{{}} replacement JsonValue::insert failed: {{:?}}", name, err));
        assert_eq!(value["item"].as_str(), Some("new"), "{{}} replacement through JsonValue::insert mismatch", name);
    }}
}}

#[test]
fn cp2rs_public_array_remove_traces() {{
    let cases: &[&str] = &{array_remove_body};
    for name in cases {{
        let mut array = JsonValue::new_array();
        array.push("first").unwrap_or_else(|err| panic!("{{}} first push failed: {{:?}}", name, err));
        array.push("second").unwrap_or_else(|err| panic!("{{}} second push failed: {{:?}}", name, err));

        let removed = array.array_remove(0);
        assert_eq!(removed.as_str(), Some("first"), "{{}} removed array item mismatch", name);
        assert_eq!(array.len(), 1, "{{}} array length after remove mismatch", name);
        assert_eq!(array[0].as_str(), Some("second"), "{{}} remaining array item mismatch", name);
    }}
}}
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
        return harness

    def _adapter_harness_api_audit(self, adapter):
        if adapter.get("_harness_api_audit"):
            return adapter.get("_harness_api_audit")
        if adapter.get("replay_generator") != "rust_inline_harness_v1":
            return {
                "status": "not_applicable",
                "reason": "replay_generator_is_not_rust_inline_harness_v1",
            }
        harness = adapter.get("rust_test_harness", "")
        if not harness and isinstance(adapter.get("target_replay_harness"), dict):
            harness = adapter.get("target_replay_harness", {}).get("rust_test_file", "")
        harness = self._strip_markdown_fence(harness)
        return self._harness_api_audit(adapter, harness)

    def _strip_markdown_fence(self, text):
        text = (text or "").strip()
        match = re.search(r"```(?:rust|rs)?\s*(.*?)\s*```", text, flags=re.S)
        if match:
            return match.group(1).strip() + "\n"
        return text + ("\n" if text else "")

    def _rust_case_array(self, cases):
        if not cases:
            return "[]"
        rendered = []
        for name, text in cases:
            rendered.append(f"({self._rust_raw_string(name)}, {self._rust_raw_string(text)})")
        return "[\n        " + ",\n        ".join(rendered) + "\n    ]"

    def _rust_array_len_case_array(self, cases):
        if not cases:
            return "[]"
        rendered = []
        for name, text, expected_len in cases:
            rendered.append(
                f"({self._rust_raw_string(name)}, {self._rust_raw_string(text)}, {int(expected_len)}usize)"
            )
        return "[\n        " + ",\n        ".join(rendered) + "\n    ]"

    def _rust_name_array(self, names):
        if not names:
            return "[]"
        rendered = [self._rust_raw_string(name) for name in names]
        return "[\n        " + ",\n        ".join(rendered) + "\n    ]"

    def _rust_raw_string(self, text):
        hashes = ""
        while f'"{hashes}' in text:
            hashes += "#"
        return f'r{hashes}"{text}"{hashes}'

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
        trace_corpus,
        replay_result,
        function_boundary,
        artifacts_path=None,
    ):
        trace_summary = trace_corpus.get("summary", {})
        public_trace_src = set(trace_summary.get("validated_aligned_source_function_ids", []))
        public_trace_tgt = set(trace_summary.get("validated_aligned_target_function_ids", []))
        aligned_src = set(alignment_stats.get("unique_aligned_source_functions", []))
        public_eligible_src = set(alignment_stats.get("public_eligible_source_functions", []))
        public_eligible_tgt = set(alignment_stats.get("public_eligible_target_functions", []))
        tested_aligned_src = self._source_functions_with_test_evidence(
            inventory,
            aligned_src,
            call_field="calls_aligned_functions",
        )
        tested_public_src = self._source_functions_with_test_evidence(inventory, public_eligible_src)
        tested_public_src = tested_public_src | (tested_aligned_src & public_eligible_src)
        tested_public_tgt = self._target_functions_for_sources(alignment_stats, tested_public_src)
        excluded_no_src_test = sorted(aligned_src - tested_aligned_src)
        excluded_public_no_src_test = sorted(public_eligible_src - tested_public_src)
        source_tested_non_public_internal = sorted(tested_aligned_src - public_eligible_src)
        mixed_public_internal_cases = self._mixed_public_internal_cases(inventory)
        adapter_src = set()
        for operation in adapter.get("public_operations", {}).values():
            adapter_src.update(operation.get("source_functions", []))

        adapter_missing_src = sorted(tested_public_src - adapter_src)
        adapter_missing_count = len(adapter_missing_src)
        replay_summary = replay_result.get("summary", {})
        report_replay_summary = self._report_replay_summary(replay_result)
        semantic_failures = [
            event for event in replay_result.get("events", []) if event.get("status") != "passed"
        ]
        semantic_failure_reviews = self._semantic_failure_reviews(semantic_failures, adapter)
        infrastructure_failures = []
        if replay_result.get("status") == "infrastructure_failed":
            infrastructure_failures.append(replay_result.get("summary", {}))
        harness_api_audit = self._adapter_harness_api_audit(adapter)
        adapter["_harness_api_audit"] = harness_api_audit
        metrics = self._build_metrics(
            replay_summary=replay_summary,
            public_trace_src=public_trace_src,
            public_trace_tgt=public_trace_tgt,
            public_eligible_src=public_eligible_src,
            public_eligible_tgt=public_eligible_tgt,
            tested_public_src=tested_public_src,
            tested_public_tgt=tested_public_tgt,
            excluded_no_src_test=excluded_no_src_test,
            aligned_src=aligned_src,
            tested_aligned_src=tested_aligned_src,
            excluded_public_no_src_test=excluded_public_no_src_test,
            source_tested_non_public_internal=source_tested_non_public_internal,
            mixed_public_internal_case_count=len(mixed_public_internal_cases),
            adapter_missing_count=adapter_missing_count,
            skipped_private_internal_count=len(alignment_stats.get("skipped_private_internal", [])),
            trace_summary=trace_summary,
            semantic_failure_reviews=semantic_failure_reviews,
        )
        automation_readiness = self._automation_readiness(
            mode=mode,
            adapter=adapter,
            replay_result=replay_result,
            metrics=metrics,
            semantic_failure_reviews=semantic_failure_reviews,
            trace_summary=trace_summary,
        )

        return {
            "evaluation_type": "Phase 3B - Trace Replay Public-First",
            "schema_version": "3b.report.v4",
            "source_repository": self.src_name,
            "target_repository": self.tgt_name,
            "mode": mode,
            "layer": layer,
            "framework_contract": self._framework_contract(adapter),
            "artifact_paths": self._artifact_paths(artifacts_path),
            "automation_readiness": automation_readiness,
            "adapter": {
                "schema_version": adapter.get("adapter_schema_version", ""),
                "name": adapter.get("name", ""),
                "status": adapter.get("status", ""),
                "adapter_role": adapter.get("adapter_role", ""),
                "generation_status": adapter.get("generation_status", ""),
                "resolution": adapter.get("_adapter_resolution", ""),
                "generation_inputs": adapter.get("generation_inputs", []),
                "recorder": adapter.get("recorder", ""),
                "replay_generator": adapter.get("replay_generator", ""),
                "validation_warnings": adapter.get("_validation_warnings", []),
                "harness_api_audit": harness_api_audit,
                "path": self._display_path(
                    adapter.get("_adapter_source_path", str(self.adapter_path) if self.adapter_path else "")
                ),
            },
            "test_inventory_summary": inventory.get("summary", {}),
            "scope_filtering": {
                "aligned_source_functions_total": len(aligned_src),
                "aligned_source_functions": sorted(aligned_src)[:100],
                "excluded_no_src_test": {
                    "count": len(excluded_no_src_test),
                    "functions": excluded_no_src_test[:100],
                    "meaning": "3A aligned source functions not observed in discovered src test evidence; excluded before public/function-boundary filtering.",
                },
                "has_src_test_evidence": {
                    "count": len(tested_aligned_src),
                    "functions": sorted(tested_aligned_src)[:100],
                },
                "excluded_non_public_after_src_test": {
                    "count": len(source_tested_non_public_internal),
                    "functions": source_tested_non_public_internal[:100],
                    "details": [
                        item for item in alignment_stats.get("skipped_private_internal", [])
                        if item.get("src_uuid") in set(source_tested_non_public_internal)
                    ][:100],
                    "meaning": "3A aligned source functions observed in src tests but excluded from L1 because source or target is not public eligible.",
                },
                "mixed_public_internal_aligned_test_cases": {
                    "count": len(mixed_public_internal_cases),
                    "cases": mixed_public_internal_cases[:100],
                    "meaning": "Public L1 candidate source test cases that also explicitly call non-public aligned functions. Adapter synthesis must not silently drop those internal state transitions.",
                },
                "l1_public_replay_scope": {
                    "count": len(tested_public_src),
                    "functions": sorted(tested_public_src)[:100],
                },
            },
            "public_behavior": {
                "status": replay_result.get("status"),
                "trace_summary": trace_corpus.get("summary", {}),
                "replay_summary": report_replay_summary,
                "semantic_failures": semantic_failures,
                "semantic_failure_reviews": semantic_failure_reviews,
                "infrastructure_failures": infrastructure_failures,
                "scope": {
                    "source_functions_with_src_test_evidence": sorted(tested_public_src),
                    "target_functions_in_src_test_scope": sorted(tested_public_tgt),
                    "excluded_no_src_test_count": len(excluded_public_no_src_test),
                    "excluded_no_src_test": excluded_public_no_src_test[:50],
                    "adapter_missing_source_function_count": len(adapter_missing_src),
                    "adapter_missing_source_functions": adapter_missing_src[:50],
                },
                "operation_alignment_summary": {
                    "alignment_status_counts": trace_summary.get("alignment_status_counts", {}),
                    "mapping_shape_counts": trace_summary.get("mapping_shape_counts", {}),
                    "covered_aligned_pairs": trace_summary.get("covered_aligned_pairs", 0),
                    "support_target_functions": trace_summary.get("support_target_functions", []),
                },
            },
            "function_boundary": function_boundary,
            "metrics": metrics,
        }

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

    def _framework_contract(self, adapter):
        operation_count = len(adapter.get("public_operations", {}))
        return {
            "summary": (
                "3B fixed framework executes repository-specific behavior recipes. "
                "The framework does not infer observable behavior by itself; operation recipes "
                "must be provided by an adapter generator or a handcrafted adapter."
            ),
            "fixed_framework_components": [
                {
                    "name": "test_inventory",
                    "responsibility": "Discover source test files/frameworks and record which tests call 3A public aligned source functions.",
                },
                {
                    "name": "alignment_scope_filter",
                    "responsibility": "Load 3A atomic alignments, classify public-eligible pairs, and keep private/internal pairs out of the default L1 score.",
                },
                {
                    "name": "operation_alignment_validation",
                    "responsibility": "Check each adapter operation against 3A atomic pairs, classify fully_aligned/partial_alignment/missing_alignment, and record one-to-one/one-to-many/many-to-one/many-to-many operation shape.",
                },
                {
                    "name": "replay_runner",
                    "responsibility": "Generate target-side replay harness from the selected replay generator, run target tests, and classify semantic vs infrastructure failures.",
                },
                {
                    "name": "agent_coverage_loop",
                    "responsibility": "In LLM synthesize/auto mode, observe replay and adapter coverage gaps, ask the LLM to expand the adapter, then revalidate and replay automatically.",
                },
                {
                    "name": "metrics_and_reporting",
                    "responsibility": "Compute pass rates, coverage, adapter gaps, skipped private/internal counts, and write layered artifacts under output/.",
                },
            ],
            "repo_specific_generated_components": [
                {
                    "name": "effective_adapter",
                    "artifact": "artifact_paths.effective_adapter",
                    "responsibility": "Declare operations, source_functions, target_functions, normalization notes, recorder, and replay generator.",
                },
                {
                    "name": "operation_set",
                    "count": operation_count,
                    "responsibility": "Represent behavior scenarios derived from 3A alignments plus source test evidence.",
                },
                {
                    "name": "trace_corpus",
                    "artifact": "artifact_paths.trace_corpus",
                    "responsibility": "Materialize replayable behavior cases from source tests/fixtures through the adapter recorder.",
                },
                {
                    "name": "target_replay_harness",
                    "artifact": "artifact_paths.generated_test_file",
                    "responsibility": "Executable target assertions generated from operation recipes by the replay generator.",
                },
            ],
            "current_generation_status": adapter.get("generation_status", "unknown"),
            "synthesis_attempts_limit": self.synthesis_attempts,
            "replay_repair_attempts_limit": self.replay_repair_attempts,
            "agent_coverage_iterations_limit": self.agent_iterations,
            "agent_coverage_batch_size": self.agent_batch_size,
            "repair_policy": (
                "In synthesize/auto mode, schema-invalid adapters can be sent back to the LLM for repair. "
                "If target replay fails before semantic comparison, cargo/build feedback can be sent back for harness repair "
                "using the separate replay_repair_attempts budget. After replay succeeds, agent coverage iterations can ask "
                "the LLM to add missing source-tested public aligned functions and replay again. "
                "Semantic failures are not repaired by LLM because they may indicate real target behavior mismatch."
            ),
            "automation_boundary": (
                "The fixed framework is generic over inventory, alignment validation, artifact writing, and replay execution. "
                "Repository-specific semantics live in the effective_adapter. For arbitrary C/C++ -> Rust public replay, "
                "adapter_mode=auto reuses a repository adapter when present and otherwise asks the LLM to generate "
                "adapter_declared trace events and a rust_inline_harness. adapter_mode=synthesize always asks the LLM. "
                "Specialized handcrafted adapters/replay generators remain optional baselines."
            ),
        }

    def _report_replay_summary(self, replay_result):
        summary = dict(replay_result.get("summary", {}))
        if replay_result.get("status") == "passed":
            summary.pop("stdout_tail", None)
            summary.pop("stderr_tail", None)
        return summary

    def _automation_readiness(
        self,
        mode,
        adapter,
        replay_result,
        metrics,
        semantic_failure_reviews,
        trace_summary,
    ):
        atomic = metrics.get("atomic_counts", {})
        ratios = metrics.get("derived_ratio_metrics", {})
        reasons = []
        review_items = []
        coverage_gaps = []
        positive_evidence = []

        executed = atomic.get("public_replay_executed", 0)
        passed = atomic.get("public_replay_passed", 0)
        infrastructure_failures = atomic.get("infrastructure_failures", 0)
        semantic_failures = atomic.get("semantic_failures", 0)
        oracle_review_required = atomic.get("semantic_failures_requiring_oracle_review", 0)
        target_semantic_candidates = atomic.get("target_semantic_failure_candidates", 0)
        adapter_missing = atomic.get("adapter_missing_count", 0)
        partial_alignment = atomic.get("trace_operations_partial_alignment", 0)
        missing_alignment = atomic.get("trace_operations_missing_alignment", 0)
        scoped_sources = atomic.get("public_source_functions_with_src_tests", 0)
        traced_sources = atomic.get("traced_public_source_functions", 0)

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
        if oracle_review_required:
            review_items.append("llm_oracle_review_required")
        if target_semantic_candidates:
            review_items.append("target_semantic_failure_candidate")
        if adapter.get("_validation_warnings"):
            review_items.append("adapter_validation_warnings_present")
        harness_api_audit = adapter.get("_harness_api_audit", {})
        if harness_api_audit.get("declared_but_not_mentioned"):
            review_items.append("declared_target_api_not_seen_in_harness")
        if harness_api_audit.get("mentioned_but_not_declared"):
            review_items.append("harness_mentions_undeclared_target_api_names")

        if adapter_missing:
            coverage_gaps.append("adapter_missing_for_some_source_tested_public_functions")
        if partial_alignment:
            coverage_gaps.append("some_operations_cover_only_part_of_3a_target_recipe")
        if scoped_sources and traced_sources < scoped_sources:
            coverage_gaps.append("not_all_source_tested_public_functions_traced")

        if executed > 0 and passed == executed:
            positive_evidence.append("all_executed_public_replay_events_passed")
        if trace_summary.get("covered_aligned_pairs", 0) > 0:
            positive_evidence.append("at_least_one_3a_atomic_pair_replay_covered")
        if not semantic_failures:
            positive_evidence.append("no_semantic_replay_failures")
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
                "3B replay produced results, but one or more failures/warnings require oracle or semantic review "
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
            "scorecard": {
                "public_replay_pass_rate": ratios.get("public_replay_pass_rate", {}),
                "aligned_source_public_trace_coverage": ratios.get("aligned_source_public_trace_coverage", {}),
                "aligned_target_public_replay_coverage": ratios.get("aligned_target_public_replay_coverage", {}),
                "adapter_missing_rate": ratios.get("adapter_missing_rate", {}),
                "covered_aligned_pairs": trace_summary.get("covered_aligned_pairs", 0),
                "executed_events": executed,
                "passed_events": passed,
            },
            "interpretation": {
                "ready": "All generated public replay events passed with no known review or coverage gaps in the current source-tested public scope.",
                "partial": "Replay passed, but results only cover the adapter-expressed subset of source-tested public aligned behavior.",
                "review_required": "Replay outcomes need human review because oracle confidence, warnings, or semantic failures prevent automatic judgment.",
                "not_ready": "Replay did not execute or infrastructure/schema prerequisites failed.",
            },
        }

    def _semantic_failure_reviews(self, semantic_failures, adapter):
        reviews = []
        is_llm_adapter = str(adapter.get("generation_status", "")).startswith("llm_synthesized")
        for failure in semantic_failures:
            oracle_confidence = failure.get("oracle_confidence", "")
            if is_llm_adapter and oracle_confidence != "high":
                status = "oracle_review_required"
                reason = (
                    "LLM-synthesized adapter produced a failing executable oracle with non-high "
                    "oracle confidence; review source test evidence before treating this as target semantic error."
                )
            else:
                status = "target_semantic_failure_candidate"
                reason = "Replay compiled and ran; failing oracle is a candidate target semantic mismatch."
            reviews.append({
                "id": failure.get("id", ""),
                "operation": failure.get("operation", ""),
                "review_status": status,
                "reason": reason,
                "oracle_source": failure.get("oracle_source", ""),
                "oracle_confidence": oracle_confidence,
                "expected": failure.get("expected", {}),
            })
        return reviews

    def _source_functions_with_test_evidence(self, inventory, source_uuids, call_field="calls_aligned_public_functions"):
        called_names = set()
        for entry in inventory.get("test_files", []):
            called_names.update(entry.get(call_field, []))
        return {
            src_uuid for src_uuid in source_uuids
            if src_uuid.rsplit("::", 1)[-1] in called_names
        }

    def _target_functions_for_sources(self, alignment_stats, source_uuids):
        targets = set()
        for pair in self._alignment_pairs_by_source(alignment_stats).values():
            if pair.get("is_public_eligible") and pair.get("src_uuid") in source_uuids:
                targets.update(pair.get("tgt_uuids", []))
        return targets

    def _build_metrics(
        self,
        replay_summary,
        public_trace_src,
        public_trace_tgt,
        public_eligible_src,
        public_eligible_tgt,
        tested_public_src,
        tested_public_tgt,
        excluded_no_src_test,
        aligned_src,
        tested_aligned_src,
        excluded_public_no_src_test,
        source_tested_non_public_internal,
        mixed_public_internal_case_count,
        adapter_missing_count,
        skipped_private_internal_count,
        trace_summary,
        semantic_failure_reviews,
    ):
        executed = replay_summary.get("executed", 0)
        passed = replay_summary.get("passed", 0)
        scoped_src_total = len(tested_public_src)
        scoped_tgt_total = len(tested_public_tgt)
        adapter_denominator = max(scoped_src_total, 1)
        oracle_review_required = len([
            item for item in semantic_failure_reviews
            if item.get("review_status") == "oracle_review_required"
        ])
        target_semantic_failure_candidates = len([
            item for item in semantic_failure_reviews
            if item.get("review_status") == "target_semantic_failure_candidate"
        ])
        skipped_private_internal_with_src_test = len(source_tested_non_public_internal)
        skipped_private_internal_without_src_test = max(
            skipped_private_internal_count - skipped_private_internal_with_src_test,
            0,
        )

        return {
            "atomic_counts": {
                "public_replay_executed": executed,
                "public_replay_passed": passed,
                "public_replay_failed": replay_summary.get("failed", 0),
                "semantic_failures": replay_summary.get("semantic_failures", 0),
                "semantic_failures_requiring_oracle_review": oracle_review_required,
                "target_semantic_failure_candidates": target_semantic_failure_candidates,
                "infrastructure_failures": replay_summary.get("infrastructure_failures", 0),
                "aligned_source_functions_total": len(aligned_src),
                "aligned_source_functions_with_src_test_evidence": len(tested_aligned_src),
                "aligned_source_functions_excluded_no_src_test": len(excluded_no_src_test),
                "public_eligible_source_functions": len(public_eligible_src),
                "public_eligible_target_functions": len(public_eligible_tgt),
                "public_source_functions_with_src_tests": scoped_src_total,
                "public_target_functions_in_src_test_scope": scoped_tgt_total,
                "public_source_functions_excluded_no_src_test": len(excluded_public_no_src_test),
                "source_tested_public_eligible_functions": scoped_src_total,
                "source_tested_non_public_internal_functions": len(source_tested_non_public_internal),
                "mixed_public_internal_aligned_test_cases": mixed_public_internal_case_count,
                "traced_public_source_functions": len(public_trace_src),
                "replayed_public_target_functions": len(public_trace_tgt),
                "trace_operations_fully_aligned": trace_summary.get("alignment_status_counts", {}).get("fully_aligned", 0),
                "trace_operations_partial_alignment": trace_summary.get("alignment_status_counts", {}).get("partial_alignment", 0),
                "trace_operations_missing_alignment": trace_summary.get("alignment_status_counts", {}).get("missing_alignment", 0),
                "trace_operations_one_to_one": trace_summary.get("mapping_shape_counts", {}).get("one_to_one", 0),
                "trace_operations_one_to_many": trace_summary.get("mapping_shape_counts", {}).get("one_to_many", 0),
                "trace_operations_many_to_one": trace_summary.get("mapping_shape_counts", {}).get("many_to_one", 0),
                "trace_operations_many_to_many": trace_summary.get("mapping_shape_counts", {}).get("many_to_many", 0),
                "covered_aligned_pairs": trace_summary.get("covered_aligned_pairs", 0),
                "adapter_missing_count": adapter_missing_count,
                "skipped_private_internal_count": skipped_private_internal_count,
                "skipped_private_internal_with_src_test_count": skipped_private_internal_with_src_test,
                "skipped_private_internal_without_src_test_count": skipped_private_internal_without_src_test,
            },
            "derived_ratio_metrics": {
                "aligned_source_test_evidence_rate": self._ratio(
                    len(tested_aligned_src),
                    len(aligned_src),
                    "aligned_source_functions_with_src_test_evidence",
                    "aligned_source_functions_total",
                    "有 src 测试证据的 3A aligned source 函数数 / 3A aligned source 函数总数",
                ),
                "public_replay_pass_rate": self._ratio(
                    passed,
                    executed,
                    "public_replay_passed",
                    "public_replay_executed",
                    "public replay 通过的 trace event 数 / public replay 实际执行的 trace event 数",
                ),
                "aligned_source_public_trace_coverage": self._ratio(
                    len(public_trace_src),
                    scoped_src_total,
                    "traced_public_source_functions",
                    "public_source_functions_with_src_tests",
                    "adapter trace 覆盖且通过 3A 对齐验证的 source 函数数 / 有 src 测试证据的 public eligible source 函数数",
                ),
                "aligned_target_public_replay_coverage": self._ratio(
                    len(public_trace_tgt),
                    scoped_tgt_total,
                    "replayed_public_target_functions",
                    "public_target_functions_in_src_test_scope",
                    "adapter replay 触达且通过 3A 对齐验证的 target 函数数 / 有 src 测试证据范围内的 public target 函数数",
                ),
                "adapter_missing_rate": self._ratio(
                    adapter_missing_count,
                    adapter_denominator,
                    "adapter_missing_count",
                    "public_source_functions_with_src_tests",
                    "有 src 测试证据但 adapter 没有 replay recipe 的 source 函数数 / 有 src 测试证据的 public eligible source 函数数",
                ),
            },
        }

    def _ratio(self, numerator, denominator, numerator_name="", denominator_name="", description=""):
        if denominator <= 0:
            return {
                "value": "0.00%",
                "raw_fraction": f"{numerator} / {denominator}",
                "numerator": numerator_name,
                "denominator": denominator_name,
                "description": description,
            }
        return {
            "value": f"{(numerator / denominator) * 100:.2f}%",
            "raw_fraction": f"{numerator} / {denominator}",
            "numerator": numerator_name,
            "denominator": denominator_name,
            "description": description,
        }

    def _write_artifacts(self, artifacts_dir, inventory, trace_corpus, replay_result, adapter, alignment_stats=None):
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "effective_adapter.json": adapter,
            "test_inventory.json": inventory,
            "trace_corpus.json": trace_corpus,
            "replay_result.json": replay_result,
        }
        for filename, data in files.items():
            with open(artifacts_dir / filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        self._write_generated_adapter_cache_if_reusable(
            artifacts_dir,
            inventory,
            trace_corpus,
            replay_result,
            adapter,
            alignment_stats,
        )

    def _write_generated_adapter_cache_if_reusable(
        self,
        artifacts_dir,
        inventory,
        trace_corpus,
        replay_result,
        adapter,
        alignment_stats=None,
    ):
        generation_status = str(adapter.get("generation_status", ""))
        if not generation_status.startswith("llm_synthesized"):
            return
        if adapter.get("status") != "loaded":
            return
        if replay_result.get("status") != "passed":
            return
        if adapter.get("_validation_warnings"):
            return
        audit = adapter.get("_harness_api_audit") or {}
        if audit.get("mentioned_but_not_declared"):
            return
        alignment_status_counts = self._replay_alignment_status_counts(replay_result)
        if not alignment_status_counts or set(alignment_status_counts) != {"fully_aligned"}:
            return
        if alignment_stats is None:
            return
        coverage_scope = self._adapter_coverage_scope(
            alignment_stats,
            inventory,
            adapter,
            trace_corpus,
            compact=True,
        )
        if coverage_scope.get("source_functions_with_src_test_evidence_count", 0) <= 0:
            return
        if coverage_scope.get("adapter_missing_source_function_count", 0) != 0:
            return
        if coverage_scope.get("untraced_source_function_count", 0) != 0:
            return
        if (
            coverage_scope.get("validated_traced_source_function_count", 0)
            != coverage_scope.get("source_functions_with_src_test_evidence_count", 0)
        ):
            return

        cache_path = self.generated_adapter_cache_path(self.src_name, self.tgt_name)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cached_adapter = dict(adapter)
        cached_adapter["_adapter_cache_status"] = "reusable_after_validated_replay"
        cached_adapter["_cached_from_artifact_dir"] = self._display_path(artifacts_dir)
        cached_adapter["_cached_at"] = datetime.utcnow().isoformat() + "Z"
        cached_adapter["_last_replay_status"] = replay_result.get("status", "")
        cached_adapter["_trace_alignment_status_counts"] = alignment_status_counts
        cached_adapter["_cache_coverage_scope"] = coverage_scope
        cached_adapter.pop("_adapter_resolution", None)
        self._write_json_atomic(cache_path, cached_adapter)

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
