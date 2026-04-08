import re       # 正则表达式库用于清洗注释文本
import tree_sitter_rust as tsrust
from tree_sitter import Language, Parser

class RustParser:
    def __init__(self):
        # 初始化 Tree-sitter 的 Rust 语言环境和解析器引擎
        self.language = Language(tsrust.language())
        self.parser = Parser(self.language)

    def parse_file_content(self, file_path, source_code: bytes):
        """解析单段 Rust 代码，并将其映射到语言无关的统一 IR 结构字典中"""
        tree = self.parser.parse(source_code)
        
        # 构建统一的中间表示层 (IR) 结果字典
        result = {
            "file_path": file_path,
            "summary": {},
            "dependencies": [],
            "entities": {
                "macros": [],                # 存放宏定义
                "global_states": [],         # 【新增】存放全局状态 (static, const)
                "data_models": [],           # 存放纯数据结构 (如 struct, enum, union, type)
                "interfaces": [],            # 存放接口契约 (如 trait)
                "behaviors": [],             # 存放操作数据的行为实现 (如 impl 块)
                "standalone_functions": []   # 存放独立的纯过程函数
            }
        }

        # 辅助函数：清理代码块的物理换行符，抹平跨平台差异，且不影响转义字符语义
        def clean_code_block(raw_bytes):
            return raw_bytes.decode('utf-8').replace('\r\n', '\n').strip()

        # 辅助函数：向上回溯抓取紧贴在节点上方的文档注释 (Docstring)
        # 支持常规注释和 Rust 特有的属性宏 (如 #[doc="..."])，属性宏 (attribute_item) 也包含 comment（tree-sitter-rust 定义如此）
        def get_docstring(node):
            docstring_lines = []
            prev_node = node.prev_sibling
            # C++为"comment"，Rust为["line_comment", "block_comment", "attribute_item"]
            while prev_node and prev_node.type in ["line_comment", "block_comment", "attribute_item"]:
                raw_text = prev_node.text.decode('utf-8')
                
                # 1. 统一物理换行符
                clean_text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
                
                # 2. 掐头去尾：完美剥离 C 风格块注释 /* 和 */
                if clean_text.startswith('/*'):
                    clean_text = clean_text[2:]
                if clean_text.endswith('*/'):
                    clean_text = clean_text[:-2]
                    
                # 3. 逐行剥离前导符：清洗行首的 //, ///, 以及块注释中间行的 *
                clean_text = re.sub(r'^\s*(/{2,3}|\*+)\s*', '', clean_text, flags=re.MULTILINE)
                
                # 【优化】特殊处理 #[doc="..."] 属性，完美支持 Rust 官方文档注释机制
                if prev_node.type == "attribute_item" and "doc" in clean_text:
                    match = re.search(r'doc\s*=\s*"([^"]+)"', clean_text)
                    if match:
                        clean_text = match.group(1)
                    else:
                        clean_text = ""
                
                if clean_text.strip():
                    docstring_lines.append(clean_text.strip())
                    
                prev_node = prev_node.prev_sibling
                
            docstring_lines.reverse() # 因为是向上回溯，所以需要反转顺序
            return "\n".join(docstring_lines)

        # 【优化】核心辅助工具：统一的函数详细组件提取逻辑
        # 统一处理 impl 方法、trait 方法签名、独立函数，减少硬编码，提高健壮性
        def extract_function_details(func_node):
            func_body = clean_code_block(func_node.text) # 净化函数体代码物理换行符
            func_name = "未命名函数"
            body_node = None
            
            for child in func_node.children:
                if child.type == "identifier":
                    func_name = child.text.decode('utf-8')
                elif child.type == "block":
                    body_node = child
            
            # 物理切片提取完整的函数签名上下文
            if body_node:
                sig_bytes = source_code[func_node.start_byte : body_node.start_byte]
                full_signature = clean_code_block(sig_bytes)
            else:
                full_signature = clean_code_block(func_node.text) # 对于 trait 中没有 body 的函数签名
                
            return {
                "name": func_name,
                "signature": full_signature,
                "docstring": get_docstring(func_node),
                "body": func_body,
                "referenced_global_states": [],  # 【新增】为阶段 1.5 预留全局变量引用探针
                "is_friend": False  # 【新增】强行对齐 C/C++ 的 JSON Schema
            }

        # 核心递归遍历函数，用于深入语法树挖掘实体
        def traverse(node):
            
            # 1. 匹配并清洗依赖声明 (use 语句与 mod 声明)
            if node.type in ["use_declaration", "mod_item"]:
                raw_text = clean_code_block(node.text)
                # 剔除噪音符号
                clean_dep = raw_text.replace("pub ", "").replace("use ", "").replace("mod ", "").replace(";", "").strip()
                
                # 【防污过滤网】直接拦截系统标准库和核心生态
                if not (clean_dep.startswith("std::") or clean_dep.startswith("core::") or clean_dep.startswith("alloc::")):
                    if clean_dep not in result["dependencies"]:
                        result["dependencies"].append(clean_dep)
                    
            # 2. 匹配并提取宏定义
            elif node.type == "macro_definition":
                macro_name = "未命名宏"
                for child in node.children:
                    if child.type == "identifier":
                        macro_name = child.text.decode('utf-8')
                        break
                result["entities"]["macros"].append({
                    "name": macro_name,
                    "docstring": get_docstring(node),
                    "body": clean_code_block(node.text) # 净化物理换行符
                })

            # 3. 匹配纯数据模型 (Struct / Enum / Union / Type Alias)
            # 在统一抽象层中，数据模型只定义状态，不包含行为
            elif node.type in ["struct_item", "enum_item", "union_item", "type_item"]: # 【优化】扩大了支持范围
                entity_name = "未命名数据结构"
                for child in node.children:
                    if child.type == "type_identifier":
                        entity_name = child.text.decode('utf-8')
                        break
                result["entities"]["data_models"].append({
                    "name": entity_name,
                    "docstring": get_docstring(node),
                    "declaration": clean_code_block(node.text) # 净化物理换行符
                })

            # 4. 匹配接口契约 (Trait)
            # 接口只包含方法的声明/签名，定义了多态的边界
            elif node.type == "trait_item":
                entity_name = "未命名Trait"
                for child in node.children:
                    if child.type == "type_identifier":
                        entity_name = child.text.decode('utf-8')
                        break
                
                methods = []
                for child in node.children:
                    if child.type == "declaration_list": # 进入 trait 内部的 {} 代码块
                        for item in child.children:
                            # 提取 Trait 里的方法签名
                            if item.type in ["function_signature_item", "function_item"]:
                                # 【优化】复用统一提取工具提取方法签名和文档
                                methods.append({
                                    "name": extract_function_details(item)["name"],
                                    "signature": extract_function_details(item)["signature"]
                                })

                result["entities"]["interfaces"].append({
                    "name": entity_name,
                    "docstring": get_docstring(node),
                    "methods": methods
                })
                # 提取完接口整体后，终止该分支的深入遍历
                return 

            # 5. 匹配行为实现 (Impl 块)
            # 解析具体的数据操作逻辑，并明确指出该行为依附的实体和实现的接口
            elif node.type == "impl_item":
                target_entity = "未知实体"
                implemented_interface = None
                body_node = None
                original_impl_signature = "" # 【新增】用于存放原汁原味的完整签名
                
                # 寻找 impl 内部的方法实现块
                for child in node.children:
                    if child.type == "declaration_list":
                        body_node = child
                        break
                
                # 提取并解析 impl 的头部签名，分离目标实体与接口
                if body_node:
                    sig_bytes = source_code[node.start_byte : body_node.start_byte]
                    original_impl_signature = clean_code_block(sig_bytes) # 原汁原味保留！例如 "impl<'a, T: OutputStrategy> Processor<'a, T>"
                    
                    # --- 下面开始对 target_entity 进行“降维清洗”，专门用于图谱连线锚定 ---
                    clean_sig = re.sub(r'^impl\b\s*', '', original_impl_signature).strip()
                    
                    # 1. 剥离 impl 块前置的泛型声明 (例如 <'a, T: OutputStrategy>)
                    if clean_sig.startswith("<"):
                        depth = 0
                        for i, char in enumerate(clean_sig):
                            if char == '<': depth += 1
                            elif char == '>': depth -= 1
                            if depth == 0:
                                clean_sig = clean_sig[i+1:].strip()
                                break
                    
                    # 2. 分离接口与实体，并剥离它们自带的泛型尾巴 (例如 Processor<'a, T> -> Processor)
                    if " for " in clean_sig:
                        parts = clean_sig.split(" for ")
                        implemented_interface = parts[0].split('<')[0].strip()
                        target_entity = parts[1].split('<')[0].strip()
                    else:
                        target_entity = clean_sig.split('<')[0].strip()
                
                methods = []
                if body_node:
                    for item in body_node.children:
                        if item.type == "function_item": # 深入提取 impl 内部的每一个具体方法
                            methods.append(extract_function_details(item))

                result["entities"]["behaviors"].append({
                    "signature": original_impl_signature, # 【关键新增】：保留全量泛型与生命周期，喂给大模型
                    "target_entity": target_entity,       # 【降维锚点】：纯净类名，用于图谱挂载
                    "implemented_interface": implemented_interface,
                    "methods": methods
                })
                # 提取完 impl 整体后，阻断该分支的深入遍历，防止内部方法被重复抓取为全局独立函数
                return

            # 6. 匹配顶层独立函数 (如 main 或全局计算函数)
            # 这些函数不依附于任何数据实体，属于纯粹的过程逻辑
            elif node.type == "function_item":
                # 【优化】复用统一提取工具
                result["entities"]["standalone_functions"].append(extract_function_details(node))
                return # 【优化】阻断深入遍历

            # 7. 【新增】匹配全局状态 (static, const)
            elif node.type in ["static_item", "const_item"]:
                # 由于进入 function 和 impl 块的递归已被阻断，这里抓到的必定是顶层的全局状态
                var_name = "未命名全局状态"
                for child in node.children:
                    if child.type == "identifier":
                        var_name = child.text.decode('utf-8')
                        break
                
                result["entities"]["global_states"].append({
                    "name": var_name,
                    "docstring": get_docstring(node),
                    "declaration": clean_code_block(node.text)
                })
                return # 【优化】阻断深入遍历，防止内部内容重复提取

            # 递归遍历子节点
            for child in node.children:
                traverse(child)

        # 启动语法树遍历
        traverse(tree.root_node)
        
        # 自动计算并填充语言无关的 summary 统计数据
        result["summary"] = {
            "dependencies_count": len(result["dependencies"]),
            "macros_count": len(result["entities"]["macros"]),
            "global_states_count": len(result["entities"]["global_states"]), # 【新增】
            "data_models_count": len(result["entities"]["data_models"]),
            "interfaces_count": len(result["entities"]["interfaces"]),
            "behaviors_count": len(result["entities"]["behaviors"]),
            "standalone_functions_count": len(result["entities"]["standalone_functions"])
        }
        return result