import re       # 正则表达式库用于清洗注释文本
import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser

class CppParser:
    def __init__(self):
        # 初始化 Tree-sitter 的 C/C++ 语言环境和解析器引擎
        self.language = Language(tscpp.language())
        self.parser = Parser(self.language)

    def parse_file_content(self, file_path, source_code: bytes):
        """解析单段 C/C++ 代码，并将其解构映射到语言无关的统一 IR 结构字典中"""
        tree = self.parser.parse(source_code)
        
        # 构建统一的中间表示层 (IR) 结果字典
        result = {
            "file_path": file_path,
            "summary": {},
            "dependencies": [],
            "entities": {
                "macros": [],                # 存放宏定义
                "global_states": [],         # 【新增】存放全局变量与跨文件共享状态
                "data_models": [],           # 存放从 class/struct 中剥离出的纯数据模型
                "interfaces": [],            # 存放接口抽象 (可用于未来存放纯虚类，目前留空兼容)
                "behaviors": [],             # 存放从 class 内/外部剥离出的具体方法实现
                "standalone_functions": []   # 存放独立的纯过程函数
            }
        }

        # 辅助函数：清理代码块的物理换行符，抹平跨平台差异，且不影响转义字符语义
        def clean_code_block(raw_bytes):
            return raw_bytes.decode('utf-8').replace('\r\n', '\n').strip()

        # 辅助函数：向上回溯抓取紧贴在节点上方的注释 (Docstring)
        def get_docstring(node):
            docstring_lines = []
            prev_node = node.prev_sibling
            # C/C++为"comment"，Rust为["line_comment", "block_comment", "attribute_item"]
            while prev_node and "comment" in prev_node.type: 
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
                
                if clean_text.strip():
                    docstring_lines.append(clean_text.strip())
                    
                prev_node = prev_node.prev_sibling
                
            docstring_lines.reverse()
            return "\n".join(docstring_lines)

        # 核心辅助工具：提取单个函数的详细组件 (深度支持析构函数、重载符及指针返回类型的解析)
        def extract_function_details(func_node, parent_node=None): # 【修改】增加 parent_node 参数，最终目的是能够处理模板
            func_body = clean_code_block(func_node.text)
            func_name = "未命名函数"
            body_node = None
            
            # 递归挖掘真实的函数名节点，穿透修饰符的包裹
            def extract_real_name(n):
                # 但遇到带有作用域的标识符（如 Class::method）或运算符，直接返回完整文本，不再向下拆解
                if n.type in ["scoped_identifier", "operator_name"]:
                    return clean_code_block(n.text)
                if n.type in ["identifier", "field_identifier", "destructor_name"]:
                    return n.text.decode('utf-8')
                for c in n.children:
                    res = extract_real_name(c)
                    if res: return res
                return None

            for child in func_node.children:
                if child.type == "compound_statement":
                    body_node = child
                elif "declarator" in child.type: 
                    extracted = extract_real_name(child)
                    if extracted:
                        func_name = extracted
            
            # 物理切片提取完整的函数签名上下文
            if body_node:
                sig_bytes = source_code[func_node.start_byte : body_node.start_byte]
                full_signature = clean_code_block(sig_bytes)
            else:
                # 如果没有 body，整个 node 的文本就是完整的签名 (与 Rust 也保持一致)
                full_signature = clean_code_block(func_node.text)
            
            # 【核心修复】如果父节点是模板声明，把模板头拼回到函数的签名上方
            if parent_node and parent_node.type == "template_declaration":
                template_prefix = clean_code_block(parent_node.text).replace(clean_code_block(func_node.text), "").strip()
                full_signature = f"{template_prefix}\n{full_signature}"
            
            return {
                "name": func_name,
                "signature": full_signature,
                "docstring": get_docstring(func_node),
                "body": func_body,
                "referenced_global_states": [],  # 【新增】为阶段 1.5 预留透视探针空列表
                "is_friend": False  # 【新增】默认标记为非友元
            }

        # 【新增】辅助函数：专门对抗深层嵌套的 typedef 函数指针别名及变量名提取
        def extract_name_from_declarator(n):
            if n.type in ['type_identifier', 'identifier']:
                return n.text.decode('utf-8')
            for c in n.children:
                if c.type in ['function_declarator', 'parenthesized_declarator', 'pointer_declarator', 'init_declarator', 'array_declarator']:
                    res = extract_name_from_declarator(c)
                    if res: return res
                elif c.type in ['type_identifier', 'identifier']:
                    return c.text.decode('utf-8')
            return None

        # 【新增】辅助函数：判断 declaration 是否为函数原型声明（避免把 void foo(); 误抓为全局变量）
        def is_function_prototype(n):
            def check_node(current):
                if current.type == "function_declarator":
                    for c in current.children:
                        # 如果包含括号，说明是函数指针变量，不是原型
                        if c.type == "parenthesized_declarator":
                            return False 
                    return True
                # 只要带有 declarator 外壳，就继续深入扒皮寻找 function_declarator
                if "declarator" in current.type:
                    for c in current.children:
                        if check_node(c): 
                            return True
                return False
                
            for c in n.children:
                if check_node(c): return True
            return False

        # 核心递归遍历函数
        def traverse(node, parent_node=None):
            
            # 1. 匹配并提取 #include 依赖，区分本地头文件与系统/三方库
            if node.type == "preproc_include":
                for child in node.children:
                    if child.type == "string_literal":
                        # 本地依赖 (e.g., #include "models/task.h")
                        path_str = child.text.decode('utf-8') # 保留双引号，帮助 LLM 识别
                        entry = f"local: {path_str}"
                        if entry not in result["dependencies"]:
                            result["dependencies"].append(entry)
                    elif child.type == "system_lib_string":
                        # 系统或三方库依赖 (e.g., #include <vector>, #include <openssl/ssl.h>)
                        path_str = child.text.decode('utf-8') # 保留尖括号，帮助 LLM 识别
                        entry = f"system/3rd-party: {path_str}"
                        if entry not in result["dependencies"]:
                            result["dependencies"].append(entry)
            
            # 2. 匹配并提取宏定义 (#define)
            elif node.type in ["preproc_def", "preproc_function_def"]:
                macro_name = "未命名宏"
                for child in node.children:
                    if child.type == "identifier":
                        macro_name = child.text.decode('utf-8')
                        break
                result["entities"]["macros"].append({
                    "name": macro_name,
                    "docstring": get_docstring(node),
                    "body": clean_code_block(node.text)
                })

            # 3. 匹配 Class, Struct 以及 C 风格的 typedef struct / 函数指针
            elif node.type in ["class_specifier", "struct_specifier", "type_definition"]:
                if node.type in ["class_specifier", "struct_specifier"] and parent_node and parent_node.type == "type_definition":
                    pass 
                else:
                    entity_name = "未命名结构"
                    methods = []
                    field_list_node = None
                    
                    # 【核心修复】捕获外层的模板前缀
                    template_prefix = ""
                    if parent_node and parent_node.type == "template_declaration":
                        template_prefix = clean_code_block(parent_node.text).replace(clean_code_block(node.text), "").strip()

                    for child in node.children:
                        if child.type in ["type_identifier", "identifier"]:
                            entity_name = child.text.decode('utf-8')
                        elif child.type == "field_declaration_list":
                            field_list_node = child
                            for field in child.children:
                                # 1. 常规类成员函数实现 (带有 body 的 function_definition)
                                if field.type == "function_definition":
                                    methods.append(extract_function_details(field))
                                
                                # 2. 【新增】常规类成员函数声明 (头文件中的纯 declaration)
                                elif field.type == "declaration":
                                    # 利用之前写的函数原型判断防御，避免把类的成员变量也当成函数抓进来
                                    if is_function_prototype(field):
                                        method_details = extract_function_details(field)
                                        method_details["body"] = "" # 纯声明没有体，覆盖掉避免脏数据
                                        methods.append(method_details)
                                
                                # 3. 【新增】拦截友元函数 (friend_declaration)
                                elif field.type == "friend_declaration":
                                    # 剥开 friend_declaration 的壳子，看里面包的是定义还是声明
                                    for friend_child in field.children:
                                        if friend_child.type in ["function_definition", "declaration"]:
                                            friend_details = extract_function_details(friend_child)
                                            friend_details["is_friend"] = True # 【核心】强行打上友元标记
                                            
                                            if friend_child.type == "declaration":
                                                friend_details["body"] = ""
                                                
                                            methods.append(friend_details)
                    
                    # 【修改】针对 typedef 的别名提取处理 (包含普通别名和深层嵌套的函数指针“未命名结构”的解决)
                    if node.type == "type_definition":
                        extracted_name = extract_name_from_declarator(node)
                        if extracted_name:
                            entity_name = extracted_name
                    
                    # 【核心修复】组装 data_models 时，补上模板头
                    declaration_text = clean_code_block(node.text)
                    if template_prefix:
                        declaration_text = f"{template_prefix}\n{declaration_text}"

                    result["entities"]["data_models"].append({
                        "name": entity_name,
                        "docstring": get_docstring(node),
                        "declaration": clean_code_block(node.text)
                    })
                    
                    if methods:
                        result["entities"]["behaviors"].append({
                            "signature": template_prefix, # 对齐 Rust 的统一字段，填入 template <...>
                            "target_entity": entity_name,
                            "implemented_interface": None,
                            "methods": methods
                        })
                    
                    if field_list_node:
                        return 

            # 4. 匹配外部函数定义
            elif node.type == "function_definition":
                func_details = extract_function_details(node, parent_node)
                if "::" in func_details["name"]:
                    target = func_details["name"].split("::")[0]
                    result["entities"]["behaviors"].append({
                        "signature": "", # 类外实现保持为空，对齐统一格式
                        "target_entity": target,
                        "implemented_interface": None,
                        "methods": [func_details]
                    })
                else:
                    result["entities"]["standalone_functions"].append(func_details)
                return 

            # 5. 【新增】匹配顶层全局变量声明(包含 extern, static 以及普通全局变量)
            elif node.type == "declaration":
                # 由于深入函数体的递归已被 return 阻断，走到这里的 declaration 必定在全局或命名空间级
                if not is_function_prototype(node):
                    var_name = extract_name_from_declarator(node)
                    if var_name:
                        result["entities"]["global_states"].append({
                            "name": var_name,
                            "docstring": get_docstring(node),
                            "declaration": clean_code_block(node.text)
                        })
                return 

            for child in node.children:
                traverse(child, parent_node=node)

        traverse(tree.root_node)
        
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