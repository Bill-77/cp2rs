import tree_sitter
import tree_sitter_rust as tsr

class RustParser:
    """
    工业级 Rust 抽象语法树解析器 (专为宏观架构 RPG 构建设计)
    Schema 4.1 终极版
    """
    def __init__(self):
        self.RUST_LANGUAGE = tree_sitter.Language(tsr.language())
        self.parser = tree_sitter.Parser(self.RUST_LANGUAGE)
        self._compile_queries()

    def _compile_queries(self):
        """预编译高频查询，极大地提升解析性能"""
        
        # 1. 依赖与宏 (Layer 1)
        self.q_deps = tree_sitter.Query(self.RUST_LANGUAGE, """
            (use_declaration) @use_decl
            (mod_item name: (identifier) @mod_name) @mod_decl
            (macro_definition name: (identifier) @macro_name) @macro_decl
        """)

        # 2. 全局状态与类型别名 (Layer 2)
        self.q_globals = tree_sitter.Query(self.RUST_LANGUAGE, """
            (static_item name: (identifier) @name) @static_decl
            (const_item name: (identifier) @name) @const_decl
            (type_item name: (type_identifier) @name) @type_alias_decl
        """)

        # 3. 核心数据结构: Struct 与 Enum (Layer 3)
        self.q_types = tree_sitter.Query(self.RUST_LANGUAGE, """
            (struct_item name: (type_identifier) @name) @struct_decl
            (enum_item name: (type_identifier) @name) @enum_decl
        """)

        # 4. 契约与实现 (Layer 4)
        self.q_traits_impls = tree_sitter.Query(self.RUST_LANGUAGE, """
            (trait_item name: (type_identifier) @trait_name) @trait_decl
            (impl_item) @impl_decl
        """)

        # 5. 独立函数 (Layer 5 - 排除 Impl/Trait 内部的函数，只抓模块顶层)
        self.q_funcs = tree_sitter.Query(self.RUST_LANGUAGE, """
            (function_item name: (identifier) @func_name) @func_decl
        """)

    # ==========================================
    # 🛡️ 核心辅助引擎 (防弹打磨版)
    # ==========================================
    def _extract_matches(self, cursor, root_node):
        """兼容新版 API，拉平 Query 返回结果"""
        results = []
        for match in cursor.matches(root_node):
            for tag, nodes in match[1].items():
                if not isinstance(nodes, list): nodes = [nodes]
                for node in nodes: results.append((node, tag))
        return results

    def _get_text(self, node: tree_sitter.Node) -> str:
        if not node: return ""
        return self.source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore').strip()

    def _get_visibility(self, node: tree_sitter.Node) -> str:
        """【修复】：全方位扫描子节点，精准捕捉 pub 和 pub(crate)"""
        # 尝试标准字段获取
        vis_node = node.child_by_field_name('visibility')
        if vis_node: return self._get_text(vis_node)
        
        # 退化为按类型搜索 (应对 AST 树的各种变体)
        for child in node.children:
            if child.type == 'visibility_modifier':
                return self._get_text(child)
        return "private"

    def _get_compile_guards(self, node: tree_sitter.Node) -> list:
        """【修复】：同时拦截内部属性与前置兄弟属性，完美捕捉 #[cfg] 与文件级 #![cfg]"""
        guards = []
        # 1. 扫描内部子节点
        for child in node.children:
            if child.type in ('attribute_item', 'inner_attribute_item'):
                text = self._get_text(child)
                if "cfg(" in text or "cfg_attr(" in text: guards.append(text)
                
        # 2. 向上扫描前置兄弟节点
        prev = node.prev_sibling
        while prev and prev.type in ('attribute_item', 'inner_attribute_item', 'line_comment', 'block_comment'):
            if prev.type in ('attribute_item', 'inner_attribute_item'):
                text = self._get_text(prev)
                if "cfg(" in text or "cfg_attr(" in text:
                    guards.insert(0, text) # 插入头部保持物理顺序
            prev = prev.prev_sibling
            
        return list(dict.fromkeys(guards))

    def _has_attribute(self, node: tree_sitter.Node, attr_name: str) -> bool:
        """通用属性检查器"""
        for child in node.children:
            if child.type in ('attribute_item', 'inner_attribute_item') and attr_name in self._get_text(child): 
                return True
        prev = node.prev_sibling
        while prev and prev.type in ('attribute_item', 'inner_attribute_item', 'line_comment', 'block_comment'):
            if prev.type in ('attribute_item', 'inner_attribute_item') and attr_name in self._get_text(prev): 
                return True
            prev = prev.prev_sibling
        return False

    def _get_generics(self, node: tree_sitter.Node) -> list:
        """纯净提取泛型 <'a, T> -> ["'a", "T"]"""
        gen_node = node.child_by_field_name('type_parameters')
        if not gen_node: return []
        return [self._get_text(c) for c in gen_node.children 
                if c.type in ('type_parameter', 'lifetime', 'constrained_type_parameter')]

    # ==========================================
    # 解析主入口
    # ==========================================
    def parse_file(self, file_path: str, source_code: bytes) -> dict:
        tree = self.parser.parse(source_code)
        self.source_code = source_code
        
        module_path = "crate"
        rel_parts = [p for p in file_path.replace(".rs", "").split('/') if p not in ('src', 'lib', 'main')]
        if rel_parts and rel_parts[-1] == "mod": rel_parts.pop()
        if rel_parts: module_path += "::" + "::".join(rel_parts)

        self.result = {
            "metadata": {"language": "rust", "file_path": file_path, "module_path": module_path, "ast_health": "degraded" if tree.root_node.has_error else "healthy"},
            "dependencies": {"uses": [], "sub_modules": [], "re_exports": []},
            "macros": [], "global_states": [], "type_aliases": [], "types": [],
            "traits": [], "impl_blocks": [], "standalone_functions": []
        }

        # 执行分层提取
        self._parse_layer_1_and_2(tree.root_node)
        self._parse_layer_3_types(tree.root_node)
        
        # 终极解析: Traits, Impls, 及它们内部的函数，以及顶层函数
        self._parse_layer_4_and_5(tree.root_node)

        return self.result

    # ==========================================
    # 提取逻辑: Layer 1 & 2 (拓扑、宏、状态、别名)
    # ==========================================
    def _parse_layer_1_and_2(self, root_node):
        # 1. 依赖与宏
        for node, tag in self._extract_matches(tree_sitter.QueryCursor(self.q_deps), root_node):
            if tag == "use_decl":
                vis = self._get_visibility(node)
                arg_node = node.child_by_field_name('argument')
                if not arg_node: continue
                use_text = self._get_text(arg_node)
                
                if vis.startswith("pub"):
                    alias = self._get_text(arg_node.child_by_field_name('alias')) if arg_node.type == 'use_as_clause' else use_text.split("::")[-1]
                    source = self._get_text(arg_node.child_by_field_name('path')) if arg_node.type == 'use_as_clause' else use_text
                    self.result["dependencies"]["re_exports"].append({"visibility": vis, "source_path": source, "alias": alias})
                else:
                    self.result["dependencies"]["uses"].append(use_text)
                    
            elif tag == "mod_decl":
                if node.child_by_field_name('body') is None:
                    mod_name = self._get_text(node.child_by_field_name('name'))
                    vis = self._get_visibility(node)
                    self.result["dependencies"]["sub_modules"].append(f"{vis} mod {mod_name};".strip() if vis != "private" else f"mod {mod_name};")
                    
            elif tag == "macro_decl":
                self.result["macros"].append({
                    "name": self._get_text(node.child_by_field_name('name')),
                    "visibility": "macro_export" if self._has_attribute(node, "macro_export") else "private",
                    "compile_guards": self._get_compile_guards(node)
                })

        # 2. 全局状态与别名
        for node, tag in self._extract_matches(tree_sitter.QueryCursor(self.q_globals), root_node):
            if tag in ("static_decl", "const_decl"):
                self.result["global_states"].append({
                    "name": self._get_text(node.child_by_field_name('name')),
                    "type": self._get_text(node.child_by_field_name('type')),
                    "kind": "static" if tag == "static_decl" else "const",
                    "visibility": self._get_visibility(node),
                    "is_mut": any(c.type == 'mutable_specifier' for c in node.children),
                    "is_unsafe": any(c.type == 'unsafe' for c in node.children),
                    "compile_guards": self._get_compile_guards(node)
                })
            elif tag == "type_alias_decl":
                self.result["type_aliases"].append({
                    "name": self._get_text(node.child_by_field_name('name')),
                    "generics": self._get_generics(node),
                    "visibility": self._get_visibility(node),
                    "underlying_type": self._get_text(node.child_by_field_name('type')),
                    "compile_guards": self._get_compile_guards(node)
                })

    # ==========================================
    # 提取逻辑: Layer 3 (数据结构 Types)
    # ==========================================
    def _parse_layer_3_types(self, root_node):
        for node, tag in self._extract_matches(tree_sitter.QueryCursor(self.q_types), root_node):
            if tag == "struct_decl":
                self.result["types"].append({
                    "kind": "struct",
                    "name": self._get_text(node.child_by_field_name('name')),
                    "generics": self._get_generics(node),
                    "visibility": self._get_visibility(node),
                    "fields_summary": self._extract_struct_fields(node),
                    "derives": self._extract_derives(node),
                    "compile_guards": self._get_compile_guards(node)
                })
            elif tag == "enum_decl":
                self.result["types"].append({
                    "kind": "enum",
                    "name": self._get_text(node.child_by_field_name('name')),
                    "generics": self._get_generics(node),
                    "visibility": self._get_visibility(node),
                    "variants": self._extract_enum_variants(node), # 深度解构变体
                    "derives": self._extract_derives(node),
                    "compile_guards": self._get_compile_guards(node)
                })

    def _extract_struct_fields(self, struct_node) -> list:
        """提取结构体字段摘要 (格式: name: Type)"""
        fields = []
        body = struct_node.child_by_field_name('body')
        if body and body.type == 'field_declaration_list':
            for child in body.children:
                if child.type == 'field_declaration':
                    fname = self._get_text(child.child_by_field_name('name'))
                    ftype = self._get_text(child.child_by_field_name('type'))
                    fields.append(f"{fname}: {ftype}")
        return fields

    def _extract_enum_variants(self, enum_node) -> list:
        """【精华】彻底结构化 Enum 的数据载荷，利用 AST 彻底消灭正则与 split 陷阱"""
        variants = []
        body = enum_node.child_by_field_name('body')
        if not body: return variants
        
        for child in body.children:
            if child.type == 'enum_variant':
                name = self._get_text(child.child_by_field_name('name'))
                kind = "unit"
                fields = []
                
                # 嗅探内部载荷的数据类型
                for sub in child.children:
                    if sub.type in ('tuple_struct_pattern', 'tuple_type', 'tuple_struct_declaration'):
                        kind = "tuple"
                        # 【终极修复】：直接遍历 Tuple 的内部节点，过滤掉括号和逗号，剩下的全是完整类型！
                        for field_node in sub.children:
                            if field_node.type not in ('(', ')', ','):
                                fields.append(self._get_text(field_node))
                                
                    elif sub.type == 'field_declaration_list':
                        kind = "struct"
                        for field_node in sub.children:
                            if field_node.type == 'field_declaration':
                                fname = self._get_text(field_node.child_by_field_name('name'))
                                ftype = self._get_text(field_node.child_by_field_name('type'))
                                fields.append(f"{fname}: {ftype}")
                                
                variants.append({"name": name, "kind": kind, "fields": [f for f in fields if f]})
        return variants

    def _extract_derives(self, node) -> list:
        """提取 #[derive(Debug, Clone)] 中的特征"""
        derives = []
        for child in node.children:
            if child.type in ('attribute_item', 'inner_attribute_item'):
                text = self._get_text(child)
                if text.startswith("#[derive(") and text.endswith(")]"):
                    inner = text[9:-2]
                    derives.extend([d.strip() for d in inner.split(',')])
                    
        prev = node.prev_sibling
        while prev and prev.type in ('attribute_item', 'inner_attribute_item', 'line_comment', 'block_comment'):
            if prev.type in ('attribute_item', 'inner_attribute_item'):
                text = self._get_text(prev)
                if text.startswith("#[derive(") and text.endswith(")]"):
                    inner = text[9:-2]
                    derives = [d.strip() for d in inner.split(',')] + derives
            prev = prev.prev_sibling
        return list(dict.fromkeys(derives))

    # ==========================================
    # 提取逻辑: Layer 4 & 5 (Traits, Impls & 函数微观引擎)
    # ==========================================
    def _parse_layer_4_and_5(self, root_node):
        # 【新增】：从 Layer 2 的成果中提取全局变量名称字典，查询复杂度 O(1)
        known_globals = {g["name"] for g in self.result["global_states"]}

        # 1. 提取 Traits 和 Impls
        for node, tag in self._extract_matches(tree_sitter.QueryCursor(self.q_traits_impls), root_node):
            if tag == "trait_decl":
                self._handle_trait(node, known_globals)
            elif tag == "impl_decl":
                self._handle_impl(node, known_globals)

        # 2. 提取独立函数 (Standalone Functions)
        # 注意：Query 会抓取所有的 function_item。我们需要过滤掉那些作为 Trait/Impl 子节点的函数
        for node, tag in self._extract_matches(tree_sitter.QueryCursor(self.q_funcs), root_node):
            if tag == "func_decl":
                # 如果它的父级/祖父级是 impl_item 或 trait_item，跳过 (它们已经在上面被处理了)
                parent = node.parent
                is_standalone = True
                while parent:
                    if parent.type in ('impl_item', 'trait_item'):
                        is_standalone = False
                        break
                    parent = parent.parent
                
                if is_standalone:
                    func_data = self._analyze_function_node(node, known_globals)
                    self.result["standalone_functions"].append(func_data)

    def _handle_trait(self, node, known_globals: set):
        trait_name = self._get_text(node.child_by_field_name('name'))
        supertraits = []
        bounds_node = node.child_by_field_name('bounds')
        if bounds_node:
            supertraits = [self._get_text(c) for c in bounds_node.children if c.type == 'type_identifier']

        assoc_consts, assoc_types, req_methods, prov_methods = [], [], [], []
        body = node.child_by_field_name('body')
        if body:
            for child in body.children:
                if child.type == 'const_item':
                    assoc_consts.append({"name": self._get_text(child.child_by_field_name('name')), "type": self._get_text(child.child_by_field_name('type'))})
                elif child.type == 'associated_type':
                    assoc_types.append({"name": self._get_text(child.child_by_field_name('name')), "bounds": []}) # 简化处理边界
                elif child.type == 'function_signature_item':
                    req_methods.append(self._get_text(child))
                elif child.type == 'function_item':
                    prov_methods.append(self._analyze_function_node(child, known_globals))

        self.result["traits"].append({
            "name": trait_name,
            "generics": self._get_generics(node),
            "visibility": self._get_visibility(node),
            "supertraits": supertraits,
            "compile_guards": self._get_compile_guards(node),
            "associated_constants": assoc_consts,
            "associated_types": assoc_types,
            "required_methods": req_methods,
            "provided_methods": prov_methods
        })

    def _handle_impl(self, node, known_globals: set):
        target_type = self._get_text(node.child_by_field_name('type'))
        # 兼容 <'a, T> 被抓取进去的情况，强行剥离主键 ID
        target_clean_name = target_type.split('<')[0].strip()
        
        trait_node = node.child_by_field_name('trait')
        trait_name = self._get_text(trait_node) if trait_node else None

        assoc_const_bindings, assoc_type_bindings, methods = [], [], []
        body = node.child_by_field_name('body')
        if body:
            for child in body.children:
                if child.type == 'const_item':
                    val_node = child.child_by_field_name('value')
                    assoc_const_bindings.append({"name": self._get_text(child.child_by_field_name('name')), "value": self._get_text(val_node) if val_node else ""})
                elif child.type == 'type_item':
                    assoc_type_bindings.append({"name": self._get_text(child.child_by_field_name('name')), "target_type": self._get_text(child.child_by_field_name('type'))})
                elif child.type == 'function_item':
                    methods.append(self._analyze_function_node(child, known_globals))

        self.result["impl_blocks"].append({
            "target_type": target_clean_name,
            "trait_name": trait_name,
            "impl_generics": self._get_generics(node),
            "compile_guards": self._get_compile_guards(node),
            "associated_constant_bindings": assoc_const_bindings,
            "associated_type_bindings": assoc_type_bindings,
            "methods": methods
        })

    # ==========================================
    # ⚙️ 核心：统一微观函数分析引擎 (Function Engine)
    # ==========================================
    def _analyze_function_node(self, node, known_globals: set) -> dict:
        name = self._get_text(node.child_by_field_name('name'))
        
        full_text = self._get_text(node)
        body_node = node.child_by_field_name('body')
        signature = full_text[:full_text.rfind(self._get_text(body_node))].strip() if body_node else full_text
        
        is_unsafe = any(c.type == 'unsafe' for c in node.children)
        is_async = any(c.type == 'async' for c in node.children)
        
        # --- 数据流提取 (Data Flow) ---
        takes_ownership, mutates_borrows, returns_borrowed_from = [], [], []
        params_node = node.child_by_field_name('parameters')
        if params_node:
            for p in params_node.children:
                if p.type == 'self_parameter':
                    # 处理花里胡哨的 self 接收器
                    type_node = p.child_by_field_name('type')
                    if type_node:
                        # 场景 A: 显式类型标注 (如 self: Box<Self>, self: Pin<&mut Self>)
                        t_text = self._get_text(type_node)
                        if "&mut " in t_text: 
                            mutates_borrows.append("self")
                        elif "&" not in t_text: 
                            takes_ownership.append("self")
                    else:
                        # 场景 B: 常规语法糖 (如 self, mut self, &self, &'a mut self)
                        p_text = self._get_text(p)
                        if "&" in p_text and "mut " in p_text: 
                            mutates_borrows.append("self")
                        elif "&" not in p_text: 
                            takes_ownership.append("self")
                            
                elif p.type == 'parameter':
                    pat = self._get_text(p.child_by_field_name('pattern'))
                    typ = self._get_text(p.child_by_field_name('type'))
                    # 兼容类似 arg: Pin<&mut T> 或 arg: &mut T
                    if typ.startswith('&mut ') or "&mut " in typ: 
                        mutates_borrows.append(pat)
                    # 只要类型签名里没有 &, 统统视为按值传递 (Move 语义拿走所有权)
                    elif not typ.startswith('&') and "&" not in typ: 
                        takes_ownership.append(pat)

        # --- 控制流与全局变量探测 ---
        direct_calls, macro_invocations, error_propagation = [], [], []
        reads_globals, writes_globals = [], []
        has_closures = False
        
        if body_node:
            stack = [body_node]
            while stack:
                curr = stack.pop()
                
                # 原有的 call_expression, macro_invocation, try_expression, closure 逻辑保持不变
                if curr.type in ('call_expression', 'method_invocation'):
                    func_name_node = curr.child_by_field_name('function')
                    if not func_name_node: func_name_node = curr.child_by_field_name('name')
                    if func_name_node:
                        fname = self._get_text(func_name_node)
                        if fname in ('unwrap', 'expect'): error_propagation.append(fname)
                        else: direct_calls.append(fname)
                        
                elif curr.type == 'macro_invocation':
                    macro_name_node = curr.child_by_field_name('macro')
                    if macro_name_node:
                        raw_macro_name = self._get_text(macro_name_node)
                        # 兼容带有命名空间的宏调用，比如 std::panic!，剥离出核心名字 panic
                        clean_macro_name = raw_macro_name.split('::')[-1]                         
                        macro_invocations.append(f"{raw_macro_name}!")                        
                        # 精准狙击控制流突变宏
                        ERROR_MACROS = {
                            # 标准库：致命崩溃/未实现
                            'panic', 'unreachable', 'todo', 'unimplemented',
                            # 标准库：断言失败导致崩溃
                            'assert', 'assert_eq', 'assert_ne', 'debug_assert', 'debug_assert_eq',
                            # 生态标准 (anyhow / eyre / custom)：提早抛出 Err
                            'bail', 'ensure', 'abort'
                        }                        
                        if clean_macro_name in ERROR_MACROS:
                            error_propagation.append(f"{clean_macro_name}!")
                        
                elif curr.type == 'try_expression':
                    error_propagation.append("?")
                    
                elif curr.type == 'closure_expression':
                    has_closures = True

                # 【新增核心逻辑】：全局变量读写嗅探雷达
                elif curr.type == 'identifier':
                    ident_name = self._get_text(curr)
                    if ident_name in known_globals:
                        # 命中全局变量！现在判断它是被读还是被写
                        is_write = False
                        parent = curr.parent
                        
                        # 向上嗅探 AST，直到遇到语句块边界
                        while parent and parent.type not in ('function_item', 'block'):
                            # 如果它在赋值表达式里
                            if parent.type == 'assignment_expression':
                                left_node = parent.child_by_field_name('left')
                                # 并且它属于赋值等号的左边 (LHS) -> 判定为写操作！
                                if left_node and ident_name in self._get_text(left_node):
                                    is_write = True
                                    break
                            parent = parent.parent
                            
                        if is_write:
                            writes_globals.append(ident_name)
                        else:
                            reads_globals.append(ident_name)

                # 逆序压栈
                for child in reversed(curr.children): 
                    stack.append(child)

        return {
            "name": name,
            "signature": signature,
            "generics": self._get_generics(node),
            "has_body": body_node is not None,
            "is_unsafe": is_unsafe,
            "is_async": is_async,
            "compile_guards": self._get_compile_guards(node),
            "data_flow": {
                "takes_ownership": takes_ownership,
                "mutates_borrows": mutates_borrows,
                "returns_borrowed_from": returns_borrowed_from,
                "reads_globals": list(dict.fromkeys(reads_globals)),
                "writes_globals": list(dict.fromkeys(writes_globals))
            },
            "control_flow": {
                "direct_calls": list(dict.fromkeys(direct_calls)),
                "indirect_calls": [],
                "macro_invocations": list(dict.fromkeys(macro_invocations)),
                "error_propagation": list(dict.fromkeys(error_propagation)),
                "has_closures": has_closures
            }
        }