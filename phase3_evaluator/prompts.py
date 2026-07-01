PROMPT_MACRO_ALIGNMENT = r"""
# Role & Objective
你是一个世界顶级的跨语言代码仓库重构与架构等价性评估专家（C/C++ to Rust）。
你的核心任务是执行“宏观架构拓扑对齐 (Macro Architectural Topology Alignment)”。
你需要跨越不同编程语言的范式鸿沟，通过分析两个仓库的高维系统图谱 (RPG)，找出它们在逻辑上的“等价子系统”，并输出精确的映射关系。

# Context: The Input RPGs
以下是分别提取自 Source 代码仓库和 Target 代码仓库的 RPG (Repository Planning Graph) 拓扑图谱：
【RPG 结构说明】：
1. 下面两个RPG图谱表示的可能是两个不同语言的代码仓库，但RPG图谱本身是高度抽象的语言无关的系统级视图，包含了 Nodes 和 Edges 两个部分。它并不直接包含函数级别的细节，而是通过 Root Nodes 的语义描述和 Edges 的拓扑关系来体现架构设计。
1. **Nodes(节点)** 包括：**Root Nodes (根节点)**，代表由大模型抽象出的高层级子系统模块（如“解析引擎模块”），它包含了该子系统的语义描述，以及它下属的中间节点(文件)；**Intermediate Nodes (中间节点)**，对应代码仓库中的文件，也有语义描述的字段。
2. **Edges (拓扑边)** 包括：**inter_module_edges(模块间边)**，代表 root 模块间的数据流向或依赖关系，指出模块 A 调用或依赖了模块 B；**intra_module_edges(模块内边)**，代表模块内文件的执行顺序。两种边的信息也可以作为判断功能对齐性和架构一致性的参考信息。

[Source 架构拓扑]
{src_summaries}

[Target 架构拓扑]
{tgt_summaries}

# Workflow: Dynamic Alignment Reasoning
请在脑海中按照以下“防御性对齐”原则进行推演：

1. **【特征嗅探与粒度不对称判定】**：浏览两个RPG的 Root 节点及其下属 intermediate 节点的语义判断功能对齐性。注意：由于语言特性（如 C 语言的单文件堆砌 vs Rust 的精细化模块拆分），源端和目标端的模块粒度可能是不对称的！你需要做好 root 节点 `1-to-1`、`1-to-N` 或 `N-to-M` 映射的准备。
2. **【拓扑同构交叉验证】**：如果 Source 中“模块A”依赖了“模块B”，并且 Target 中你认为“模块A'”对应“模块A”，那么“模块A'”也可能在 Edges 列表中体现出对“模块B'”的依赖，可以利用边 (Edges) 来证实或证伪你的猜想。
3. **【Rust 承载位置迁移】**：C/C++ 的一个实现子系统在 Rust 中常被拆成“内部实现模块 + 核心类型上的方法 + crate 根 public/facade API”。例如 Source 的序列化/解析模块，不一定只对应 Target 的 codegen/parser root；如果 Target 的核心类型 root 或 public API root 暴露了同一行为的入口，并通过 Edges 调用内部实现模块，你必须把这些 root 一起纳入 `tgt_root_id`，形成 `1-to-N` 或 `N-to-M` 映射。不要只因为某个 Target root 名字更像实现模块，就忽略 public/facade 或 core-method 承载的行为入口。
4. **【结构性聚合/门面模块】**：纯聚合头文件、crate 根 re-export、facade/public API root 可以参与宏观对齐，但如果它不包含真实行为函数，应在 justification 中说明它是结构性入口，不要把它当作功能实现模块强行制造函数对齐。
5. **【宁缺毋滥 (The Golden Rule)】**：Source 和 Target 并不一定是完全对等的！有些独立模块（如 Fuzzing, Benchmark, 示例代码）在另一个仓库中可能根本不存在。**如果在 Target 中找不到功能明确对等的模块，请直接忽略该 Source 模块，绝对禁止强行配对。**

# Output Constraints
在完整的 `<thinking>` 推理结束后，请在 `<output>` 标签内输出合法的 JSON 字符串。你必须严格遵循下方的 JSON Schema，不要输出包含思考过程的文字，不要输出 Markdown 的 ```json 代码块标记。

<output>
[
  {{
    "src_root_id": "Source中对应的Root_ID (如果是N对M，可用逗号分隔)", 
    "tgt_root_id": "Target中对应的Root_ID (如果是N对M，可用逗号分隔)", 
    "mapping_topology": "1-to-1 / 1-to-N / N-to-1 / N-to-M",
    "confidence": "High / Medium", 
    "justification": "结合【语义描述】与【Edges 拓扑连边】进行逻辑论证。"
  }}
]
</output>
"""

PROMPT_MICRO_ALIGNMENT = r"""
# Role & Objective
你是一位极度严谨的代码审计与微观对齐专家。
你的任务是在已经对齐的宏观模块内部，进行“函数级别”的绝对源码对齐。

# Context: Source Codes
以下是从 Source 模块 (C/C++) 和 Target 模块 (Rust) 中提取出的【真实源代码】。
每个函数都绑定了一个全局唯一的 UUID（包含了文件名和函数名，格式如 `file.c::func_name`）。

[Source 函数源码]
{src_code_blocks}

[Target 函数源码]
{tgt_code_blocks}

# Workflow: Micro Alignment Reasoning
请务必在脑海内完成代码对比推演：
1. **源码逻辑等价性分析**：仔细阅读代码体（绝不能只看函数名）。注意语言范式的差异，例如 C 的一个大函数可能被拆分为 Rust 的多个小函数，或者 C 的独立函数变成了 Rust 的 `impl` 方法。
2. **Target 候选范围说明**：Target 函数池来自已经完成的宏观映射边界。该边界可能包含初始目标 root，也可能包含由 RPG Edges 校验后补全的 public/facade/core-method support root，用来处理 Rust 把行为入口放到核心类型方法或 crate 根 API 的情况。你只能选择真正语义等价的函数，不能因为函数在候选池里就强行配对。
3. **宁缺毋滥原则**：只连线你确信功能逻辑对应的函数。对于在 Target 中找不到实现的 Source 函数，或者 Target 中为了适应 Rust 特性而新增的辅助函数，请直接忽略，不要强行配对，【绝对不要】放到 `<output>` 输出的 JSON 数组中。

# Output Constraints
在推理结束后，请在 `<output>` 标签内严格输出合法的 JSON 数组字符串。
请注意：
1. **千万不要**输出`<thinking>`的内容
2. 只输出 JSON 数据，不要输出 Markdown 的 ```json 标记。
3. **JSON 安全转义**：在撰写 `reason` 字段时，如果必须提到代码中的反斜杠或 Unicode 字符（例如 \ u 或 \ x），**你必须使用双反斜杠进行安全转义（例如写成 \\u 或 \\x），绝对禁止在 JSON 值中输出非法的单反斜杠转义，否则会导致解析崩溃！**

输出格式要求：

<output>
[
  {{
    "src_uuid": "Source的完整UUID", 
    "tgt_uuid": "Target的完整UUID (如果1个C函数对应多个Rust函数，可用逗号分隔)", 
    "confidence": "High / Medium", 
    "reason": "简短说明代码是如何对齐的（指出关键变量或底层逻辑的等价性）"
  }}
]
</output>
"""

# 翻译分析 Prompt
PROMPT_STRATEGY_ANALYSIS = """
# Role & Objective
你是一位顶级的 Rust 架构师与代码重构专家。
你的任务是对比【机器自动翻译生成的 Rust 代码 (Target)】与【人类专家手写的 Rust 代码 (Answer)】，并输出一份深度的“翻译分析报告 (Translation Analysis)”。

# Context: The 3A Alignment Data
以下是我们通过底层的架构与源码对齐引擎，提取出的 Target 与 Answer 之间的微观对齐映射关系，以及两者全局的量化指标数据：

[Target vs Answer 3A 量化指标]
{quantitative_metrics}

[Target vs Answer 核心架构对齐映射]
{aligned_modules_summary}

# Workflow: Strategic Evaluation
请仔细分析上述数据，并在脑海中思考以下问题：
1. **架构分歧 (Architectural Divergence)**：从模块的碎片化指数和映射关系来看，机器翻译 (Target) 是否优先保持了原始 C/C++ 的文件结构？人类专家 (Answer) 是否进行了更大胆、更符合 Rust 习惯的模块拆分？
2. **特性利用率与惯用语 (Idiomatic Rust & Feature Utilization)**：从接口膨胀率、原生函数率 (Native Rate) 和 Unsafe 依赖率来看，机器翻译是否在“用 Rust 语法写 C 代码”（强行裸奔）？人类是否充分利用了 Enum, Trait, 迭代器和生命周期管理？

# Output Constraints
请直接输出合法的 JSON 字符串，严格遵守以下 Schema。不要输出 Markdown 代码块标记，不要输出任何多余的解释文字。

{{
  "architecture_strategy_diff": "分析机器与人类在模块拆分、目录组织和架构解耦上的策略差异",
  "idiomatic_rust_utilization": "分析两者在 Rust 高级特性（如所有权、Trait、错误处理）使用上的差距，特别要结合 Unsafe 率和接口膨胀率进行点评",
  "overall_translation_verdict": "基于以上数据，给出一个最终的定性结论，比如：Target 代码是属于'机械式逐行机翻'、'带安全检查的增强代码'，还是'接近人类水平的重构'？（一句话总结）"
}}
"""

PROMPT_3B_ADAPTER_SYNTHESIS = """# CP2RS Phase 3B Adapter Synthesis

You generate a repository-specific 3B public-first adapter.

Important rules:
- Return a single valid JSON object only. No Markdown fences. No explanations outside JSON.
- Return compact JSON when possible; avoid long comments or duplicated prose so the response is not truncated.
- Use the adapter shape shown in `required_adapter_shape`.
- Generate public behavior operations from source test evidence and 3A aligned function pairs.
- Read `source_language_context` first. For C sources, source calls are usually free functions; for C++ sources, source calls may be namespace-qualified functions, class/struct methods, constructors, fixture helper calls, or overloaded APIs.
- For C++ source APIs, use `source_aligned_api_context` owner/signature/visibility/body excerpts to disambiguate same-name methods and overloads before claiming a `source_functions` entry is covered.
- For C++ gtest/HWTEST fixtures, treat SetUp/TearDown/member state as evidence for the source scenario, but the executable L1 replay must still use target public Rust APIs and compare only final observable behavior from source assertions.
- Prefer `source_evidence.behavior_cases` when designing operations: one operation should reflect a concrete source test case or a tight group of source tests with the same observable behavior.
- Prefer `source_evidence.behavior_cases[].assertions` when deciding executable expected behavior values: they list source assertion expressions, literals, and aligned functions mentioned by each assertion.
- Treat `source_evidence.behavior_cases` as behavior coverage obligations, not optional examples. For every listed case whose aligned source functions are L1 public-eligible, try to replay it via one or more `trace_events[].source_case_ids`. Cases that cannot be converted by the generator should remain unresolved for adapter generation, not hidden as semantic exclusions.
- Process each behavior case in two ordered steps inside the adapter response: first decide whether its complete source behavior can be expressed through target public APIs, including every required internal public substitution; then generate trace events and Rust tests for convertible cases. Runtime feature differences should be replayed so failures are visible.
- Function coverage alone is not enough: if several source tests exercise different behavior variants of the same aligned public function, include each reusable behavior variant instead of covering the function once with an easier case.
- Review `source_evidence.mixed_public_internal_cases` before writing operations. These cases are L1 risk cases because the source test explicitly calls non-public aligned functions alongside public calls.
- Cases that passed the structural mixed-call screen may contain `required_internal_public_substitutions`. Include all listed target public UUIDs in the operation target_functions and preserve the source state transition in the Rust test. Never silently omit it.
- For mixed public/internal source cases, use this three-way policy: (1) if the target public API naturally includes the internal effect, replay the public API and explain that in `normalization`; (2) if the target has an explicit public equivalent for the internal state transition, include that public call in the replay; (3) if the internal state transition cannot be preserved through target public APIs, leave the case unresolved for L1 adapter generation.
- Never silently drop an explicit source internal call and replay only the surrounding public calls when that internal call may affect the final observable result.
- Use `source_evidence.function_index` to ground every `source_functions` entry and to check which source functions still need coverage.
- Treat `source_evidence.quality_checks` as a context integrity signal. If it reports missing evidence, omit unsupported functions instead of guessing.
- Use `target_aligned_api_context` and the selected public target API candidates to write Rust calls that actually exist.
- Read `target_api_scope.selection_policy`: the candidate list is intentionally compact, but validation checks against the full parsed public API set.
- Use `target_crate_import_hint.crate_name_for_rust_code` when importing the Rust crate in integration tests.
- Rust integration-test imports are lexical. A `use` inside one `#[test]` function does not apply to other tests. Each `rust_test_body` must either use fully qualified target crate paths or include every needed `use` inside that same test body. Do not rely on imports emitted by another case fragment.
- Do not rely on target repository tests or examples; the target may have no tests. Infer target API usage from Cargo.toml/lib.rs, parsed public signatures, owner_type, call_hint, and body excerpts only.
- For every source function listed in a `public_operations.*.source_functions` entry, copy every corresponding `tgt_uuid` from `alignment_scope.public_eligible_pairs_with_src_test_evidence` into that operation's `target_functions`. You may add support public target APIs too, but do not omit the 3A target recipe for a declared source function.
- Use `source_evidence.fixtures` when source tests rely on input/expected files rather than inline literals.
- Pay attention to each target API `owner_type`, signature, and `call_hint`; call methods on values of their declared owner type.
- For target signatures with generic `Into<...>` parameters, pass concrete values directly when possible instead of adding unnecessary `.into()` calls.
- The `normalization` field is an audit note. The actual executable expected behavior check must appear in `rust_test_harness`.
- Do not invent target behavior that is not grounded in source tests or fixtures.
- Maximize reliable coverage of `alignment_scope.public_eligible_pairs_with_src_test_evidence`; do not stop after a few examples if more source-tested public functions have clear assertions or fixtures.
- Broad coverage is welcome only when each operation is still grounded in concrete source test evidence. Omit a function only when replay would require speculation or non-public target APIs.
- Do not omit source behavior variants merely because they may expose target feature-scope differences. If the aligned target public API is callable, replay the source input and source expected behavior so runtime results can reveal accepted-input differences, configuration-dependent behavior, container/traversal differences, formatting differences, or narrower target behavior.
- Avoid brittle exact string-format assertions unless the source test/fixture explicitly provides that exact expected string. For printing/pretty output without exact expected fixtures, prefer parseability, structural checks, or clearly grounded substring/property checks.
- For every trace event, set `expected_behavior_source` and `expected_behavior_confidence`. Use `high` only for concrete assertions or expected fixtures. Use `medium` for normalized behavior properties inferred from source tests.
- For every trace event, set `source_case_ids` to the `case_id` values from `source_evidence.behavior_cases` that the event replays. If one Rust test covers a tight group of equivalent source cases, list all covered case ids.
- Prefer one source behavior case per trace event. If one event claims multiple `source_case_ids`, they must have the same aligned source-function scope and genuinely equivalent normalized inputs/expected behavior; add a concrete `case_grouping_rationale`. Do not attach unrelated case ids merely to increase coverage.
- Use only public Rust APIs in `rust_test_harness`.
- Every `trace_events[].id` must be a valid Rust function identifier.
- The Rust harness must define exactly one `#[test] fn <trace_event_id>()` for each trace event id.
- Do not add extra `#[test]` functions without a matching trace event id.
- If you want to test another behavior, declare a matching `public_operations` entry and `trace_events` entry.
- If a source aligned function is too hard to replay reliably, omit it; the framework will count it as adapter_missing.
- The `evidence` fields should cite concrete source test paths/names from the context.
- Every declared target function should appear in the Rust harness through the actual target API call.
- The Rust integration test must compile as tests/cp2rs_3b_public.rs inside the target crate.
- Keep `rust_test_harness` JSON encoding valid. Use ordinary Rust syntax appropriate to the target API and avoid unnecessarily complex escaped literals.

Context:
{context_json}
"""

PROMPT_3B_REPLAY_REPAIR = """# CP2RS Phase 3B Replay Repair

The previous 3B adapter was schema-valid, but some generated Rust replay tests failed before semantic comparison.

Repair only infrastructure/build/API usage issues in rust_test_harness. Do not change source-test-derived observable behavior. Return one compact JSON patch only, with no Markdown fences and no explanations.
Return exactly this patch shape:
{{"replay_repair_patch_version":"3b.replay_repair_patch.v2","shared_support_source_replacement":"optional complete Rust code outside #[test] functions, or omit","rust_test_replacements":[{{"test_name":"existing_test_function_name","rust_test_body":"complete corrected #[test] function"}}]}}
Python retains public_operations and trace_events and will replace only listed test blocks plus optional shared support/import code.
Do not rewrite tests that are not listed in infrastructure_failed_tests. Do not add extra `#[test]` functions.
The patch is invalid if `rust_test_replacements` is missing or empty. Use `required_output_contract.required_test_names`; every replacement.test_name must be copied exactly from that list.
Use the target API owner_type/signature information from target_repair_context. In particular:
- Call each method on a value of the `owner_type` supplied in target_repair_context.
- For generic Into<...> parameters, pass concrete values directly when possible; avoid unnecessary .into() calls that create type inference failures.
- Every declared target function should still appear in the repaired Rust harness through the actual API call.
- Use `rust_integration_test_contract` and `target_crate_import_hint` to fix unresolved imports/symbols. The repaired source is compiled as an integration test, so target crate public items must be imported from the crate name or called through fully qualified crate paths.
- Use `infrastructure_failed_tests` first. Each item gives one generated #[test] function and the compile/runtime infrastructure error for that isolated test. Repair those tests/imports, then preserve all other trace-event tests unless a shared import/scope fix is required.
- Rust does not concatenate adjacent string literals like C/C++. Use one raw string literal or `concat!(...)` for multi-part strings.
- Rust string literals do not support C/C++ `\\b` or `\\f`; use `\\x08` and `\\x0c`. Rust strings also cannot contain surrogate Unicode escapes such as `\\u{{D806}}`.
- Do not assume iterator item shape. Use target signatures and owner types to determine whether an iterator yields values, references, pairs, or custom items before destructuring it.
- Avoid borrowing from a mutable receiver and then reading from the same value again unless the Rust ownership/lifetime shape is clear. Prefer owned values for intermediate collections when that preserves the same expected behavior.
- Any value passed to a `&mut self` method must be declared `mut`.

Replay repair context:
{repair_context_json}
"""

PROMPT_3B_ADAPTER_CASE_GENERATION = """# CP2RS Phase 3B Adapter Case Generation

You are generating independently valid per-case replay fragments that convert eligible source behavior cases into executable Rust public replay tests.
Every case in `targeted_behavior_cases` has already passed structural public-replay eligibility screening. Process every targeted case independently. Function coverage is only a derived metric; do not stop after one case happens to cover a function.

Return one compact JSON object only. No Markdown fences. No explanations outside JSON.
Prefer this compact per-case shape. Python expands each event into the internal operation + trace_event adapter format, so do not duplicate the same information in separate operation and trace_event objects:
{{"adapter_case_generation_version":"3b.case_results.v2","case_results":[{{"case_id":"case id from targeted_behavior_cases","status":"replay_generated","event":{{"id":"valid_rust_test_function_name","source_functions":["source UUIDs from allowed_source_function_uuids_for_this_batch"],"target_functions":["target UUIDs from allowed_target_api_uuids_for_this_batch"],"description":"short behavior scenario","normalization":"observable comparison rule","evidence":"source path/name/assertion summary","input":{{"case":"short input summary"}},"expected":{{"observable_behavior":"source-test-derived expected behavior"}},"expected_behavior_source":"source_test_assertion|source_fixture|source_test_property","expected_behavior_confidence":"high|medium|low"}},"rust_test_body":"complete Rust #[test] function whose name equals event.id"}}]}}

The older `3b.case_results.v1` shape with separate `operation` and `trace_event` is still accepted for compatibility, but the compact v2 shape is preferred because it avoids duplicated prose and reduces truncation risk.

For a targeted case that you cannot convert, return `status:"unresolved_adapter_generation"` with `reason` and `details`. Do not output `excluded_behavior_cases`; this stage is not allowed to hide semantic differences. Configuration-dependent behavior, accepted-input extensions, container/traversal differences, output-format differences, target feature gaps, or narrower target behavior must be replayed when callable public target APIs exist, so the runtime result can expose the difference.

Python validates and retains each case fragment independently. A malformed case must not prevent valid cases in the same response from being accepted. Do not repeat existing operations, events, or Rust tests. Use new operation/event names when behavior differs from an existing operation.
Every targeted case should either produce `status:"replay_generated"` or `status:"unresolved_adapter_generation"`. Function coverage alone is not completion.

For every replay-generated case:
- Treat `allowed_source_function_uuids_for_this_batch` and `allowed_target_api_uuids_for_this_batch` as closed sets. Do not use source or target UUIDs outside them.
- `event.source_functions` must be a non-empty subset of `allowed_source_function_uuids_for_this_batch`.
- `event.target_functions` must be a non-empty subset of `allowed_target_api_uuids_for_this_batch`.
- `event.id` must be a valid Rust function identifier and the Rust test function must use exactly that name.
- Every Rust public API visibly used by the test must be declared in `event.target_functions` using full UUIDs from `targeted_alignment_pairs`, `allowed_target_public_api_signatures`, or `target_aligned_api_context`.
- For each source function listed in `event.source_functions`, include all of its 3A `tgt_uuids` from `targeted_alignment_pairs` in `event.target_functions`.
- If a targeted behavior case contains `required_internal_public_substitutions`, preserve and explicitly call every listed target public function in the Rust test.
- The executable expected behavior check must be grounded in `targeted_behavior_cases[].assertions`, fixtures, literals, or source snippets. Do not invent target behavior or use target tests as expected behavior evidence.
- Each `rust_test_body` is merged independently. Include needed imports inside that `#[test]` function or use fully qualified target crate paths. Do not rely on imports from other generated tests.
- If you use a target public item by its bare Rust name, the same test body must import it from `target_crate_import_hint.crate_name_for_rust_code`.

Generation context:
{repair_context_json}
"""
