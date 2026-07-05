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

PROMPT_3B_ADAPTER_SYNTHESIS = """# CP2RS Phase 3B Replay Adapter Synthesis

You generate a repository-specific 3B public-first replay adapter.

Important rules:
- Return a single valid JSON object only. No Markdown fences. No explanations outside JSON.
- Use the adapter shape shown in `required_adapter_shape`.
- The adapter schema is `3b.replay_adapter.v2`.
- The only executable replay units are `replay_events[]`. Do not output separate behavior maps, event maps, or a top-level Rust harness.
- Each `replay_events[]` item must describe one concrete source-test-derived behavior and include its own complete `rust_test_body`.
- `rust_test_body` must be a complete `#[test] fn <event.id>() { ... }` function. The function name must exactly equal `event.id`.
- `rust_support_source` is optional shared Rust support code outside tests. Prefer empty unless several event bodies need the same helper.
- Read `source_language_context` first. For C++ sources, use owner/signature/body snippets to disambiguate methods, overloads, constructors, and fixtures.
- Treat `source_evidence.behavior_cases` as behavior coverage obligations. For every listed eligible case, try to produce a replay event; otherwise list it in `unresolved_behavior_cases`.
- Do not hide semantic differences as exclusions. If callable target public APIs exist, replay the source input and expected observable behavior so runtime results expose differences.
- For mixed public/internal source cases, preserve required public substitutions listed in the case evidence. If the state transition cannot be expressed through public target APIs, mark that case unresolved.
- Every `replay_event.source_functions` entry must be grounded in 3A aligned source UUIDs and source test evidence.
- Every declared source function requires all corresponding 3A target UUIDs in `replay_event.target_functions`. Add UUID-bearing support public APIs in `support_target_functions` when they are used only for setup/checking.
- Use only public Rust APIs. Use `target_aligned_api_context`, `allowed_target_public_api_signatures`, owner_type, signatures, and `integration_test_call_hint` to write callable integration-test code.
- Use `target_rust_usage_capabilities` before declaring a target API missing. UUID-bearing public functions go in `target_functions`/`support_target_functions`; `non_uuid_public_constructs` such as enum variants, constants, macros, and trait/operator behavior may be used in `rust_test_body` but must not be listed as UUID functions.
- Each event body is compiled as Rust integration-test code. Use fully qualified crate paths or imports inside that same test body; imports in one event do not apply to another.
- Expected behavior must be grounded in source assertions, fixtures, literals, or source snippets. Do not use target tests/examples as expected behavior evidence.
- Avoid brittle exact string-format checks unless source evidence provides exact expected text. Prefer structural/property checks when source only requires normalized behavior.
- If one event covers multiple source case ids, they must have equivalent normalized behavior and include `case_grouping_rationale`.

Context:
{context_json}
"""

PROMPT_3B_REPLAY_REPAIR = """# CP2RS Phase 3B Replay Event Repair

The previous replay adapter was schema-valid, but some generated Rust replay event tests failed before semantic comparison.

Repair only infrastructure/build/API usage issues in the listed event `rust_test_body` values. Do not change source-test-derived expected behavior. Return one compact JSON patch only, with no Markdown fences and no explanations.
Return exactly this patch shape:
{{"replay_repair_patch_version":"3b.replay_repair_patch.v2","shared_support_source_replacement":"optional complete Rust support code outside #[test] functions, or omit","rust_test_replacements":[{{"test_name":"existing_event_id","rust_test_body":"complete corrected #[test] function"}}]}}
Python will replace only listed `replay_events[].rust_test_body` values plus optional shared support code.
Do not rewrite tests that are not listed in infrastructure_failed_tests. Do not add extra `#[test]` functions.
The patch is invalid if `rust_test_replacements` is missing or empty. Use `required_output_contract.required_test_names`; every replacement.test_name must be copied exactly from that list.
Use the target API owner_type/signature information from target_repair_context.
- Call each method on a value of the supplied owner_type.
- For generic Into<...> parameters, pass concrete values directly when possible.
- Check target_repair_context.target_rust_usage_capabilities for public constructors, conversions, trait impls, macros, enum variants, constants, accessors, and builders before changing behavior. Non-UUID public constructs may be used in Rust code but must not be listed as UUID functions.
- Use `rust_integration_test_contract` and `target_crate_import_hint`; compiled code is an integration test, so target crate public items must be imported or crate-qualified.
- Use `infrastructure_failed_tests` first. Each item gives one generated test body and its compile/runtime infrastructure error.
- Rust does not concatenate adjacent string literals like C/C++. Use one raw string literal or concat!(...).
- Any value passed to a `&mut self` method must be declared `mut`.

Replay repair context:
{repair_context_json}
"""

PROMPT_3B_ADAPTER_CASE_GENERATION = """# CP2RS Phase 3B Replay Event Generation

You are generating independently valid replay events that convert eligible source behavior cases into executable Rust public replay tests.
Every case in `targeted_behavior_cases` has already passed structural public-replay eligibility screening. Process every targeted case independently. Function coverage is only a derived metric; do not stop after one case happens to cover a function.

Return one compact JSON object only. No Markdown fences. No explanations outside JSON.
Return this shape:
{{"adapter_case_generation_version":"3b.replay_events.v1","case_results":[{{"case_id":"case id from targeted_behavior_cases","status":"replay_generated","replay_event":{{"id":"valid_rust_test_function_name","source_case_ids":["covered case id"],"source_functions":["source UUIDs from allowed_source_function_uuids_for_this_batch"],"target_functions":["target UUIDs from allowed_target_api_uuids_for_this_batch"],"support_target_functions":["optional support target UUIDs used by the test"],"description":"short behavior scenario","normalization":"observable comparison rule","evidence":"source path/name/assertion summary","input":{{"case":"short input summary"}},"expected":{{"observable_behavior":"source-test-derived expected behavior"}},"expected_behavior_source":"source_test_assertion|source_fixture|source_test_property","expected_behavior_confidence":"high|medium|low","rust_test_body":"complete Rust #[test] function whose name equals id"}}}}]}}

For a targeted case that you cannot convert, return `status:"unresolved_behavior_case_conversion"` with `reason` and `details`. Do not output exclusions; this stage is not allowed to hide semantic differences.

For every replay-generated case:
- Treat `allowed_source_function_uuids_for_this_batch` and `allowed_target_api_uuids_for_this_batch` as closed sets. Do not use source or target UUIDs outside them.
- `replay_event.source_functions` must be a non-empty subset of `allowed_source_function_uuids_for_this_batch`.
- `replay_event.target_functions` must be a non-empty subset of `allowed_target_api_uuids_for_this_batch`.
- `replay_event.id` must be a valid Rust function identifier and the Rust test function must use exactly that name.
- Every UUID-bearing Rust public API visibly used by the test must be declared in `replay_event.target_functions` or `support_target_functions` using full UUIDs from the provided target API context.
- Non-UUID public constructs listed in `target_rust_usage_capabilities.non_uuid_public_constructs` may be used in `rust_test_body` but must not be placed in `target_functions` or `support_target_functions`.
- For each source function listed in `replay_event.source_functions`, include all of its 3A `tgt_uuids` from `targeted_alignment_pairs` in `replay_event.target_functions`.
- If a targeted behavior case contains `required_internal_public_substitutions`, preserve and explicitly call every listed target public function in the Rust test.
- The executable expected behavior check must be grounded in `targeted_behavior_cases[].assertions`, fixtures, literals, or source snippets. Do not invent target behavior.
- Prefer `integration_test_call_hint` over bare call examples when writing Rust integration-test code.
- Use `target_rust_usage_capabilities` to find generic Rust construction and observation routes, including public trait impls, macros, enum variants, constants, and support APIs that may not appear as ordinary aligned functions.
- If a targeted case references fixture files, use `source_fixture_access`: either embed provided content when sufficient or read the copied fixture path from the replay worktree. Entries with `fixture_role=expected_output_candidate` are source-side expected-output evidence, not target-generated behavior. Do not use paths that are not listed or present in the source evidence.
- Each `rust_test_body` must include needed imports inside that `#[test]` function or use fully qualified target crate paths.

Generation context:
{repair_context_json}
"""
