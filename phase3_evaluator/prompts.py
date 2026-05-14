PROMPT_3A_MACRO_MAPPER = """
# Role & Objective
你是一个世界顶级的跨语言代码重构与等价性评估专家（C/C++ to Rust）。
你的核心任务是进行“宏观功能架构对齐 (Macro Functional Point Alignment)”。
你将接收原始代码库（Source RPG）和翻译后代码库（Target RPG）的高维索引图谱。
你需要跨越不同编程范式（面向过程 vs 面向对象/代数类型）和物理目录（文件拆分与合并）的鸿沟，找出两个仓库在逻辑上的“等价功能域”，并给出架构对齐度评分。

# Context: The Input RPGs
输入的 JSON 包含 "source_rpg" 和 "target_rpg"。
RPG 中包含 Root（子系统）、Intermediate（物理文件/模块）和 Leaf（函数/方法签名）。
【重要警示】：由于语言特性的天壤之别，源端和目标端的物理层级极可能是不对称的。例如：源端的一个巨型 Intermediate 节点，可能对应目标端的一个包含多个文件的 Root 节点。

# Workflow: Dynamic Alignment Reasoning
请在 <thinking> 标签内进行沙盘推演。你必须利用大语言模型的泛化理解能力，按照以下“自顶向下定性，自底向上定谳”的步骤推演：

1. 【特征指纹嗅探】：浏览两边的 Intermediate 和 Leaf 节点的 `original_signature` 和 `node_subtype`。这些叶子节点是证明功能属性的“指纹”。
2. 【逻辑功能域划分 (Functional Domain Clustering)】：不受物理层级的限制，在脑海中提炼出几个核心的逻辑功能域（例如：“配置解析引擎”、“网络连接池”、“加密算法层”）。
3. 【跨语言实体归拢】：将源端和目标端的节点（可以是 Root，也可以是 Intermediate）分别归拢到你划分的逻辑功能域中。判定它们的映射拓扑（1-to-1, 1-to-N, N-to-M）。
4. 【证据链固化】：从归拢的模块中，挑出几个最具代表性的源端和目标端对齐的 Leaf 节点签名，作为它们确实等价的铁证。
5. 【缺失分析】：严格排查是否有源端的核心逻辑域，在目标端未能找到任何映射（即翻译丢失）。

# Output Constraints
推演结束后，在 <output> 标签内严格输出合法的 JSON 报告。

<output>
{
  "macro_alignment_score": 85, 
  "aligned_functional_domains": [
    {
      "domain_name": "宏观逻辑域的抽象名称（如：Socket Connection Management）",
      "mapping_topology": "1-to-N", 
      "source_nodes": ["源端关联的 Root 或 Intermediate 节点 ID"],
      "target_nodes": ["目标端关联的 Root 或 Intermediate 节点 ID"],
      "confidence": "High/Medium/Low",
      "justification": "简述为什么认为这批节点在宏观架构上等价（跨越了怎样的语言范式差异）。",
      "evidence_signatures": [
        "源端签名示例 -> 目标端签名示例"
      ]
    }
  ],
  "unmapped_source_nodes": [
    {
      "node_id": "源端未找到对应翻译的节点 ID",
      "reason": "简述判断其丢失的理由"
    }
  ]
}
</output>

切记：
1. 不要纠结于具体的 1对1 函数映射，那是微观阶段的任务。本阶段你的目标是划定“功能大区”。
2. 输出必须是纯净的 JSON 对象。
"""

PROMPT_3B_TEST_ADAPTER = """
你是一位顶级的 Rust 测试环境适配专家。
你的任务是将一份【标准答案仓库】的原生 Rust 单元测试，移植并适配到由大模型自动翻译生成的【目标结果仓库】中。

【输入数据】
1. CRATE_NAME: 目标仓库的包名（用于外部导入）。
2. ORIGINAL_TEST_CODE: 标准答案仓库中的原始 #[test] 函数源码。
3. TARGET_SIGNATURE: 目标仓库中对应被测函数的签名。
4. TARGET_DEPENDENCIES: 目标仓库的上下文依赖，包含所使用的结构体、枚举及常量。

【核心任务】
在绝对不改变测试意图的前提下，将原始测试适配为可以在外部 `tests/` 目录下运行的集成测试。

【严格约束规则 - 必须遵守】
1. 严禁偷懒与删减 (FATAL)：你必须原封不动地保留 ORIGINAL_TEST_CODE 中所有复杂的数据初始化逻辑（如长字符串、宏调用、循环构造等），绝不允许擅自将其简化为类似 `let object = JsonValue::Object;` 的空壳代码！
2. 模块作用域 (FATAL)：这段代码将运行在 `tests/` 目录下的外部集成测试文件中。严禁使用 `use super::*;` 或 `use crate::*;`。你必须使用提供的 CRATE_NAME 进行外部导入，例如：`use {crate_name}::xxx;`。
3. 依赖沙盒：仅允许使用 TARGET_DEPENDENCIES 中定义的类型结构进行名称替换。
4. 熔断机制：如果发现两边签名发生维度级的丢失（参数/返回值严重不匹配），导致无法完成原有的断言闭环，请停止生成，仅输出：<status>UNADAPTABLE</status>

【输出格式】
- 如果可以适配，请直接输出修改后的完整的 Rust #[test] 函数源码（不要包含 markdown 标记）。
- 如果无法适配，仅输出 <status>UNADAPTABLE</status>。

====================
[以下为动态注入区域]
CRATE_NAME: {crate_name}

ORIGINAL_TEST_CODE:
{original_test_code}

TARGET_SIGNATURE:
{target_signature}

TARGET_DEPENDENCIES:
{target_dependencies}
"""