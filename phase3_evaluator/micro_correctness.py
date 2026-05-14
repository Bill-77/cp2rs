import json
import os
import subprocess
import shutil
import re
from .test_slicer import discover_physical_tests, extract_precise_dependencies
from rpg_builder.llm_client import LLMClient  # 统一的 LLM 调用接口
from .prompts import PROMPT_3B_TEST_ADAPTER

def evaluate_micro_correctness(target_vs_answer_report, answer_repo_dir, target_schema_path, target_repo_dir):
    """
    SOP 第 3 & 第 4 关：微观正确性裁判与沙盒执行
    """
    # --- 【新增】提取目标仓库的 Crate Name ---
    crate_name = "translated_crate" # 默认 fallback
    cargo_toml_path = os.path.join(target_repo_dir, "Cargo.toml")
    if os.path.exists(cargo_toml_path):
        with open(cargo_toml_path, 'r', encoding='utf-8') as f:
            match = re.search(r'^name\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
            if match:
                crate_name = match.group(1).replace("-", "_") # Rust 包名导入时横杠必须变下划线
    # ------------------------------------------

    with open(target_vs_answer_report, 'r', encoding='utf-8') as f:
        alignment_report = json.load(f)

    results = []

    # 实例化 LLM 客户端
    llm = LLMClient()
    
    # 确保目标仓库的测试目录存在
    test_dir = os.path.join(target_repo_dir, "tests")
    os.makedirs(test_dir, exist_ok=True)
    test_file_path = os.path.join(test_dir, "cp2rs_eval_test.rs")

    domains = alignment_report.get("aligned_functional_domains", [])
    if not domains:
        print("   ⚠️ 警告：大模型生成的报告中没有找到 'aligned_functional_domains' 字段！请检查 3A 报告 JSON。")

    # 遍历 Target VS Answer 的映射表
    for domain in domains:
        signatures = domain.get("evidence_signatures", [])
        if not signatures:
            continue
            
        for sig_mapping in signatures:
            # 提取 'fn' 后面紧跟的函数名，无视 -> 符号的干扰
            # 匹配 "fn 函数名(" 或者 "fn 函数名<"
            matches = re.findall(r'fn\s+([a-zA-Z0-9_]+)\s*[<(]', sig_mapping)
            
            if len(matches) < 2:
                print(f"   ⚠️ 警告：无法从签名中提取到两端函数名: {sig_mapping}")
                continue
            
            # 映射关系中，第一个必然是 target_func，最后一个必然是 answer_func
            target_func = matches[0]
            answer_func = matches[-1]

            print(f"🕵️  正在挖掘测试: {target_func} 🆚 {answer_func}")

            # [SOP 关卡 1]: 测试淘金
            tests = discover_physical_tests(answer_repo_dir, answer_func)
            if not tests:
                print(f"   ⚠️ 答案仓库中未找到针对 {answer_func} 的测试，跳过。")
                continue

            # [SOP 关卡 2]: 依赖精准提纯
            context = extract_precise_dependencies(target_schema_path, target_func)
            if not context["target_signature"]:
                print(f"   ❌ 在目标 Schema 中未找到 {target_func} 的详细定义，跳过。")
                continue

            # 为简单起见，我们取第一个找到的测试用例来适配
            test_source = tests[0]["source_code"]

            # [SOP 关卡 3]: 召唤 LLM 适配工程师
            prompt = PROMPT_3B_TEST_ADAPTER.format(
                crate_name=crate_name,
                original_test_code=test_source,
                target_signature=context["target_signature"],
                target_dependencies=json.dumps(context["dependencies"], indent=2, ensure_ascii=False)
            )
            
            print(f"   🧠 正在让大模型生成适配胶水代码...")
            # 用标准的 messages 和温度调用
            messages = [
                {"role": "user", "content": prompt}
            ]
            llm_reply = llm.chat_completion(messages, temperature=0.1)

            # 熔断检测
            if "<status>UNADAPTABLE</status>" in llm_reply:
                print(f"   💔 发生结构级死局！大模型判定 API 无法适配。计 0 分。")
                print(f"   [LLM 熔断理由]:\n{llm_reply}")
                results.append({"target": target_func, "status": "UNADAPTABLE"})
                continue

            # 清理代码块标记 (去除 markdown 的 ```rust ```)
            adapted_code = llm_reply.replace("```rust", "").replace("```", "").strip()

            # [SOP 关卡 4]: 沙盒处决 (写入文件并执行 cargo test)
            # 强行在文件顶部注入 #[macro_use] 语法，解决外部测试无法找到目标宏的问题
            final_code = f"#[macro_use]\nextern crate {crate_name};\n\n{adapted_code}"
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(final_code)

            print(f"   ⚡ 正在沙盒中执行 cargo test...")
            
            # 智能寻找 cargo 的绝对路径 (兼容 Linux/WSL 默认安装路径)
            cargo_path = shutil.which("cargo")
            if not cargo_path:
                cargo_path = os.path.expanduser("~/.cargo/bin/cargo")

            try:
                result = subprocess.run(
                    [cargo_path, "test", "--test", "cp2rs_eval_test"],
                    cwd=target_repo_dir,
                    capture_output=True,
                    text=True
                )
            except FileNotFoundError:
                print(f"   ❌ 致命环境错误：在 {cargo_path} 找不到 cargo 命令。请确保当前系统已安装 Rust。")
                results.append({"target": target_func, "status": "FAIL_ENV", "error": "Cargo not found"})
                continue

            if result.returncode == 0:
                print(f"   ✅ 测试通过！功能完全等价。")
                results.append({"target": target_func, "status": "PASS"})
            else:
                print(f"   ❌ 测试失败！翻译逻辑存在漏洞。")
                print(f"   [Cargo 详细报错]:\n{result.stderr}\n{result.stdout}") 
                error_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
                results.append({"target": target_func, "status": "FAIL_LOGIC", "error": result.stderr[:200]})

    # 输出最终的分类统计报告
    # (可保存为 micro_correctness_report.json)
    print("\n📊 动态测试评估完成！")
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    print(f"   - 测试总数: {len(results)}")
    print(f"   - 完美通过: {pass_count}")
    print(f"   - 结构熔断: {sum(1 for r in results if r['status'] == 'UNADAPTABLE')}")
    print(f"   - 逻辑报错: {sum(1 for r in results if 'FAIL' in r['status'])}")