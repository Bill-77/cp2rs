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
3. **【宁缺毋滥 (The Golden Rule)】**：Source 和 Target 并不一定是完全对等的！有些独立模块（如 Fuzzing, Benchmark, 示例代码）在另一个仓库中可能根本不存在。**如果在 Target 中找不到功能明确对等的模块，请直接忽略该 Source 模块，绝对禁止强行配对。**

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

PROMPT_MICRO_ALIGNMENT = """
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
2. **宁缺毋滥原则**：只连线你确信功能逻辑对应的函数。对于在 Target 中找不到实现的 Source 函数，或者 Target 中为了适应 Rust 特性而新增的辅助函数，请直接忽略，不要强行配对，【绝对不要】放到 `<output>` 输出的 JSON 数组中。

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

# 战略透视 Prompt
PROMPT_STRATEGY_ANALYSIS = """
# Role & Objective
你是一位顶级的 Rust 架构师与代码重构专家。
你的任务是对比【机器自动翻译生成的 Rust 代码 (Target)】与【人类专家手写的 Rust 代码 (Answer)】，并输出一份深度的“战略透视报告 (Strategy Analysis)”。

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
  "architecture_strategy_diff": "分析机器与人类在模块拆分、目录组织和架构解耦上的策略差异（约150字）",
  "idiomatic_rust_utilization": "分析两者在 Rust 高级特性（如所有权、Trait、错误处理）使用上的差距，特别要结合 Unsafe 率和接口膨胀率进行点评（约150字）",
  "overall_translation_verdict": "基于以上数据，给出一个最终的定性结论：Target 代码是属于'机械式逐行机翻'、'带安全检查的C代码'，还是'接近人类水平的重构'？（一句话总结）"
}}
"""