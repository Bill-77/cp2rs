import os
import re
import tree_sitter
import tree_sitter_c as tsc

class CParser:
    """
    工业级 C 语言抽象语法树解析器 (专为宏观架构 RPG 构建设计)
    """
    def __init__(self):
        # 适配 tree-sitter v0.22.0+ 最新的初始化 API
        self.C_LANGUAGE = tree_sitter.Language(tsc.language())
        self.parser = tree_sitter.Parser(self.C_LANGUAGE)

    def parse_file(self, file_path: str, source_code: bytes) -> dict:
        """解析单文件并输出符合 Schema 3.1 规范的 JSON 字典"""
        tree = self.parser.parse(source_code)
        root_node = tree.root_node

        self.source_code = source_code
        
        # Schema 3.1 核心骨架
        self.result = {
            "metadata": {
                "language": "c",
                "file_path": file_path,
                "file_type": "header" if file_path.endswith('.h') else "source"
            },
            "dependencies": {"system_includes": [], "local_includes": []},
            "macros": [],
            "global_states": [],
            "types": [],
            "functions": []
        }

        # 第一遍扫描：提取全局预处理、类型、全局变量和函数
        self._traverse_top_level(root_node)
        
        return self.result

    # ==========================================
    # 核心工具函数
    # ==========================================
    def _get_text(self, node) -> str:
        """安全提取节点对应的源码纯文本"""
        if not node: return ""
        return self.source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore').strip()

    def _get_doc_comment(self, node) -> str:
        """
        向上寻找紧邻当前节点的注释节点
        """
        curr = node.prev_sibling
        comments = []
        # 向上查找所有连续的注释节点
        while curr and curr.type == 'comment':
            comments.insert(0, self._get_text(curr))
            curr = curr.prev_sibling
        
        return "\n".join(comments) if comments else None

    def _extract_attributes_and_modifiers(self, node):
        """提取节点中的修饰符(static, extern, const)和编译器属性(__attribute__)"""
        is_static, is_extern, is_const = False, False, False
        attributes = []
        
        # 遍历修饰符节点
        for child in node.children:
            if child.type == 'storage_class_specifier':
                text = self._get_text(child)
                if text == 'static': is_static = True
                if text == 'extern': is_extern = True
            elif child.type == 'type_qualifier':
                if self._get_text(child) == 'const': is_const = True
            elif child.type in ('attribute_specifier', 'gnu_attribute', 'attribute_declaration'):
                attributes.append(self._get_text(child))
                
        return is_static, is_extern, is_const, attributes

    def _get_base_identifier(self, node):
        """递归寻找表达式或声明符的最底层标识符 (终极抗压版)"""
        if not node: return None
        if node.type == 'identifier': 
            return self._get_text(node)
            
        # 1. 穿透执行层面的表达式 (Expressions)
        if node.type in ('pointer_expression', 'parenthesized_expression'):
            return self._get_base_identifier(node.child_by_field_name('argument') or node.children[1])
        if node.type == 'cast_expression':
            return self._get_base_identifier(node.child_by_field_name('value'))
        if node.type in ('field_expression', 'subscript_expression'):
            return self._get_base_identifier(node.child_by_field_name('argument'))
            
        # 2. 穿透声明层面的声明符 (Declarators)
        # 囊括：指针、数组、函数指针、初始化、以及 __attribute__ 包装
        if 'declarator' in node.type or node.type == 'type_definition':
            # 暴力 DFS 往下找真正的 identifier
            def find_id(n):
                if n.type in ('identifier', 'type_identifier'):
                    return self._get_text(n)
                for child in n.children:
                    # 只顺着 declarator 相关的路径或者直接找标识符，防止跑到别的分支
                    if 'declarator' in child.type or child.type in ('identifier', 'type_identifier'):
                        res = find_id(child)
                        if res: return res
                return None
            
            return find_id(node)
            
        return None

    # ==========================================
    # 顶层 AST 遍历
    # ==========================================
    def _traverse_top_level(self, root_node, compile_guards=None):
        for node in root_node.children:
            if node.type == 'preproc_include':
                self._parse_include(node)
            elif node.type in ('preproc_def', 'preproc_function_def'):
                self._parse_macro(node)
            elif node.type == 'declaration':
                # 【修改点】：增加参数透传
                self._parse_top_level_declaration(node, compile_guards=compile_guards)
            elif node.type == 'type_definition':
                self._parse_typedef(node)
            elif node.type == 'function_definition':
                # 【修改点】：增加参数透传
                self._parse_function(node, has_body=True, compile_guards=compile_guards)
            elif node.type in ('preproc_ifdef', 'preproc_if', 'preproc_else', 'preproc_elif'):
                # 【核心逻辑重构】：直接在 top_level 处理条件编译
                self._traverse_conditional_block(node, compile_guards)

    def _traverse_conditional_block(self, block_node, parent_guards):
        """处理被 #ifdef 等包裹的代码块 (支持常见嵌套与全类型提取)"""
        # 提取当前块的 guard 名 (例如 ENABLE_DEBUG)
        # 注意：preproc_else 没有 name 字段，需做安全处理
        name_node = block_node.child_by_field_name('name')
        current_guard = self._get_text(name_node) if name_node else None
        
        # 组合 guard 列表 (针对常见仓库，通常只有 1-2 层嵌套)
        new_guards = list(parent_guards) if parent_guards else []
        if current_guard:
            new_guards.append(current_guard)
        elif block_node.type == 'preproc_else':
            # 语义化标记，方便大模型理解这是互斥分支
            last_guard = parent_guards[-1] if parent_guards else "UNKNOWN"
            new_guards.append(f"NOT_{last_guard}")

        # 【关键修改】：复用顶层遍历逻辑，确保块内的 typedef 等节点不再丢失
        self._traverse_top_level(block_node, compile_guards=new_guards)

    # ==========================================
    # 细节解析器：宏与依赖
    # ==========================================
    def _parse_include(self, node):
        path_node = node.child_by_field_name('path')
        if not path_node: return
        path_str = self._get_text(path_node)
        if path_node.type == 'system_lib_string':
            self.result["dependencies"]["system_includes"].append(path_str)
        else:
            self.result["dependencies"]["local_includes"].append(path_str)

    def _parse_macro(self, node):
        name_node = node.child_by_field_name('name')
        if not name_node: return
        
        macro_info = {
            "name": self._get_text(name_node),
            "is_function_like": node.type == 'preproc_function_def',
            "definition": self._get_text(node.child_by_field_name('value'))
        }
        if macro_info["is_function_like"]:
            # 截取宏的签名部分：从名字开始到参数列表结束
            params = node.child_by_field_name('parameters')
            if params:
                macro_info["signature"] = self.source_code[name_node.start_byte:params.end_byte].decode('utf-8')
        
        self.result["macros"].append(macro_info)

    # ==========================================
    # 细节解析器：类型与全局变量
    # ==========================================
    def _parse_top_level_declaration(self, node, compile_guards=None):
        if self._is_function_declaration(node):
            self._parse_function(node, has_body=False, compile_guards=compile_guards)
            return

        is_static, is_extern, is_const, attrs = self._extract_attributes_and_modifiers(node)
        
        # 如果包含 struct/enum/union 定义
        type_node = node.child_by_field_name('type')
        if type_node and type_node.type in ('struct_specifier', 'enum_specifier', 'union_specifier'):
            self._parse_struct_union_enum(type_node, attrs)
        # 【补丁 3：应对逗号表达式 (int a=1, b=2)，遍历提取所有同级声明】
        for child in node.children:
            if child.type in ('init_declarator', 'identifier', 'pointer_declarator', 'array_declarator'):
                var_name = self._get_base_identifier(child)
                if not var_name: continue

                init_symbols = []
                if child.type == 'init_declarator':
                    val_node = child.child_by_field_name('value')
                    if val_node and val_node.type == 'initializer_list':
                        init_symbols = self._extract_initialization_symbols(val_node)

                state_info = {
                    "name": var_name,
                    "type": self._get_text(type_node) if type_node else "unknown",
                    "doc_comment": self._get_doc_comment(node),
                    "is_static": is_static,
                    "is_extern": is_extern,
                    "is_const": is_const,
                    "attributes": attrs,
                    "compile_guards": compile_guards or [],
                    "contains_function_pointers": "(*" in self._get_text(child),
                    "declaration": self._get_text(node)
                }
                if init_symbols:
                    state_info["initialization_symbols"] = init_symbols
                    
                self.result["global_states"].append(state_info)

    def _extract_initialization_symbols(self, initializer_list_node):
        """深度挖掘初始化列表中的独立标识符，过滤掉字面量"""
        symbols = []
        def walk(n):
            if n.type == 'identifier':
                symbols.append(self._get_text(n))
            for child in n.children:
                walk(child)
        walk(initializer_list_node)
        return list(set(symbols))

    def _parse_struct_union_enum(self, node, inherited_attrs=None, forced_name=None):
        kind = node.type.replace('_specifier', '') # struct, enum, union
        name_node = node.child_by_field_name('name')
        body_node = node.child_by_field_name('body')
        
        if forced_name:
            name = forced_name
        elif name_node:
            name = self._get_text(name_node)
        else:
            name = "anonymous"
        
        type_info = {
            "kind": kind,
            "name": name,
            "doc_comment": self._get_doc_comment(node),
            "attributes": inherited_attrs or []
        }
        
        if not body_node:
            type_info["kind"] = "forward_declaration"
            self.result["types"].append(type_info)
            return

        if kind == 'enum':
            variants = []
            for child in body_node.children:
                if child.type == 'enumerator':
                    variants.append(self._get_text(child.child_by_field_name('name')))
            type_info["variants"] = variants
        else:
            fields = []
            func_ptrs = []
            for child in body_node.children:
                if child.type == 'field_declaration':
                    decl = child.child_by_field_name('declarator')
                    field_text = self._get_text(child)
                    if decl and decl.type in ('pointer_declarator', 'parenthesized_declarator'):
                        if '(*' in field_text or ')' in field_text:
                            func_ptrs.append(field_text)
                            continue
                    fields.append(field_text)
            type_info["fields_summary"] = fields
            if func_ptrs: type_info["function_pointers"] = func_ptrs

        self.result["types"].append(type_info)

    def _parse_typedef(self, node):
        type_node = node.child_by_field_name('type')
        declarator = node.child_by_field_name('declarator')
        typedef_name = self._get_base_identifier(declarator) if declarator else None
        
        if not typedef_name:
            for child in reversed(node.children):
                if child.type in ('identifier', 'type_identifier'):
                    typedef_name = self._get_text(child)
                    break
                    
        if type_node and type_node.type in ('struct_specifier', 'enum_specifier', 'union_specifier'):
            # 检查结构体是否有原本的名字
            inner_name_node = type_node.child_by_field_name('name')
            if not inner_name_node:
                # 【补丁 5：完美缝合匿名结构体与 Typedef】
                # 把 typedef 的名字作为属性传给匿名结构体，直接解析为具名类型，阻止脱节！
                self._parse_struct_union_enum(type_node, forced_name=typedef_name)
                return # 既然已经合体，就不再单独生成一个 typedef 实体了
            else:
                self._parse_struct_union_enum(type_node)
            
        type_info = {
            "kind": "typedef",
            "name": typedef_name,
            "underlying_type": self._get_text(type_node),
            "declaration": self._get_text(node)
        }
        self.result["types"].append(type_info)

    # ==========================================
    # 终极武器：函数与数据流探针
    # ==========================================
    def _is_function_declaration(self, node):
        decl = node.child_by_field_name('declarator')
        if not decl: return False
        # 剥离可能存在的指针 *
        while decl.type == 'pointer_declarator':
            decl = decl.child_by_field_name('declarator')
        return decl.type == 'function_declarator'

    def _parse_function(self, node, has_body=True, compile_guards=None):
        decl = node.child_by_field_name('declarator') if not has_body else node.child_by_field_name('declarator')
        while decl and decl.type == 'pointer_declarator':
            decl = decl.child_by_field_name('declarator')
            
        if not decl or decl.type != 'function_declarator': return
        
        name = self._get_base_identifier(decl.child_by_field_name('declarator'))
        params_node = decl.child_by_field_name('parameters')
        
        # 提取参数列表，为参数突变(Out-Params)打地基
        params_names = []
        is_variadic = False
        if params_node:
            for p in params_node.children:
                if p.type == 'parameter_declaration':
                    p_name = self._get_base_identifier(p.child_by_field_name('declarator'))
                    if p_name: params_names.append(p_name)
                elif p.type == 'variadic_parameter':
                    is_variadic = True

        is_static, _, _, attrs = self._extract_attributes_and_modifiers(node)
        signature = self.source_code[node.start_byte:params_node.end_byte if params_node else decl.end_byte].decode('utf-8')

        func_info = {
            "name": name,
            "doc_comment": self._get_doc_comment(node),
            "signature": signature,
            "has_body": has_body,
            "is_static": is_static,
            "is_variadic": is_variadic,
            "attributes": attrs,
            "compile_guards": compile_guards or []
        }

        # 如果有函数体，启动大杀器：Def-Use 数据流与作用域引擎！
        if has_body:
            body_node = node.child_by_field_name('body')
            analyzer = FunctionDataFlowAnalyzer(self, params_names)
            analyzer.analyze(body_node)
            
            func_info["data_flow"] = {
                "reads": list(analyzer.reads),
                "writes": list(analyzer.writes),
                "mutates_parameters": list(analyzer.mutates_params)
            }
            func_info["control_flow"] = {
                "direct_calls": list(analyzer.direct_calls),
                "indirect_calls": list(analyzer.indirect_calls),
                "has_unstructured_jumps": analyzer.has_unstructured_jumps
            }
            # 【此处新增】：将解析错误探针加入输出字典
            func_info["has_parse_errors"] = analyzer.has_parse_errors

            func_info["body"] = self._get_text(body_node)

        self.result["functions"].append(func_info)


class FunctionDataFlowAnalyzer:
    """
    负责执行函数内部的 AST 遍历。
    维护 Scope Stack 过滤局部变量，提取精确的 Read/Write/Mutate 与调用图。
    """
    def __init__(self, parser: CParser, parameters: list):
        self.parser = parser
        self.parameters = set(parameters)
        
        # 核心防御1：嵌套块作用域栈 (The Scope Stack)
        self.local_scopes = [] 
        
        self.reads = set()
        self.writes = set()
        self.mutates_params = set()
        self.direct_calls = set()
        self.indirect_calls = set()
        self.has_unstructured_jumps = False
        self.has_parse_errors = False

    def enter_scope(self): self.local_scopes.append(set())
    def exit_scope(self): self.local_scopes.pop()
    def add_local(self, name): 
        if self.local_scopes: self.local_scopes[-1].add(name)

    def is_local_or_param(self, name):
        """检查标识符是否被局部作用域遮蔽，或属于函数参数"""
        if name in self.parameters: return True
        for scope in reversed(self.local_scopes):
            if name in scope: return True
        return False

    def analyze(self, body_node):
        self.visit(body_node, context='read')

    def visit(self, node, context='read'):
        if not node: return

        # 【补丁 ：只拦截宏名称，不拦截内部代码块！】
        if node.type.startswith('preproc_'):
            # 对于宏定义直接跳过，不读写
            if node.type in ('preproc_def', 'preproc_function_def'):
                return
            # 对于条件编译块，继续遍历内部代码，但显式避开作为条件的宏名称
            for child in node.children:
                if child == node.child_by_field_name('name') or child.type == 'identifier':
                    continue # 这是开关名字 (如 DEBUG_MODE)，跳过
                self.visit(child, context) # 正常遍历内部代码 (如 engine_panic)
            return

        # 【补丁 3：屏蔽编译期求值的假阳性读写】
        if node.type in ('sizeof_expression', 'alignof_expression', 'offsetof_expression'):
            return

        # 【补丁 4：敏锐嗅探 AST 解析断层，警告大模型】
        if node.type == 'ERROR':
            self.has_parse_errors = True

        # 1. 作用域边界管理
        # 【补丁 2：防御 C99 for 循环作用域泄漏】
        if node.type in ('compound_statement', 'for_statement'):
            self.enter_scope()
            for child in node.children: self.visit(child, context)
            self.exit_scope()
            return

        # 2. 局部变量声明注册
        if node.type == 'declaration':
            # 【补丁 1：嗅探函数内部的 static 变量】
            is_static = any(c.type == 'storage_class_specifier' and self.parser._get_text(c) == 'static' for c in node.children)
            if is_static:
                # 移交给顶层解析器，将其正式注册为 global_states
                self.parser._parse_top_level_declaration(node)
                # 遍历它的初始化右值，提取可能的数据流依赖 (例如 static int a = g_SystemState;)
                for child in node.children:
                    if child.type == 'init_declarator':
                        self.visit(child.child_by_field_name('value'), 'read')
                return # 拦截：坚决不能将它放入 add_local()！
            
            # 正常的局部变量注册逻辑，将变量加入当前作用域
            for child in node.children:
                if child.type == 'init_declarator':
                    decl = child.child_by_field_name('declarator')
                    var_name = self.parser._get_base_identifier(decl)
                    if var_name: self.add_local(var_name)
                    # 赋值语句的右侧作为 'read' 遍历
                    self.visit(child.child_by_field_name('value'), 'read')
                elif child.type in ('identifier', 'pointer_declarator'):
                    var_name = self.parser._get_base_identifier(child)
                    if var_name: self.add_local(var_name)
            return

        # 【补丁 1：取地址逃逸拦截 (Address-of Escape)】
        if node.type == 'unary_expression':
            operator_node = node.child_by_field_name('operator')
            if operator_node and self.parser._get_text(operator_node) == '&':
                argument = node.child_by_field_name('argument')
                # 交出地址意味着极高的突变风险，将其视为内存突变操作！
                self.visit(argument, 'mutate_memory')
                return
            # 对于其他一元操作符 (如 ! - ~)，正常按原上下文向下遍历

        # 3. 极其关键的赋值表达式拆解 (LHS vs RHS)
        if node.type in ('assignment_expression', 'update_expression'):
            lhs = node.child_by_field_name('left') or node.child_by_field_name('argument')
            rhs = node.child_by_field_name('right')
            
            # 右值处理：如果有右值（赋值表达式），永远是读取
            if rhs:
                self.visit(rhs, 'read')
            
            # 【补丁 2：补全自增/自减的先读后写 (Read-Modify-Write) 语义】
            if node.type == 'update_expression':
                self.visit(lhs, 'read')
            
            # 左值判断：是简单重写，还是指针数据突变？
            if lhs.type == 'identifier':
                # 简单变量赋值
                self.visit(lhs, 'write')
            elif lhs.type in ('pointer_expression', 'field_expression', 'subscript_expression'):
                # 修改指针指向的内存 / 修改结构体字段
                self.visit(lhs, 'mutate_memory')
            return

        # 4. 提取标识符 (过滤掉局部变量，暴露全局本质)
        if node.type == 'identifier':
            name = self.parser._get_text(node)
            if not self.is_local_or_param(name):
                if context == 'read': self.reads.add(name)
                elif context == 'write': self.writes.add(name)
            return

        # 5. 核心防御2 & 参数突变：隔离结构体陷阱，提取底层修改
        if context == 'mutate_memory':
            # 【补丁 2：防止数组下标在 mutate_memory 截断中丢失 read 语义】
            if node.type == 'subscript_expression':
                index_node = node.child_by_field_name('index')
                self.visit(index_node, 'read')

            base_name = self.parser._get_base_identifier(node)
            if base_name:
                if base_name in self.parameters:
                    # 发现 Out-Parameter 突变！
                    self.mutates_params.add(base_name)
                elif not self.is_local_or_param(base_name):
                    # 修改了全局指针指向的内存，等同于修改了全局状态
                    self.writes.add(base_name)
            return

        # 6. 函数调用嗅探 (控制流与动态路由)
        if node.type == 'call_expression':
            func_node = node.child_by_field_name('function')
            if func_node:
                if func_node.type == 'identifier':
                    # 直接调用
                    func_name = self.parser._get_text(func_node)
                    if func_name in ('setjmp', 'longjmp'):
                        self.has_unstructured_jumps = True
                    else:
                        self.direct_calls.add(func_name)
                else:
                    # 间接调用 (如 task->execute())
                    self.indirect_calls.add(self.parser._get_text(func_node))
            
            # 别忘了遍历参数列表作为 'read'
            self.visit(node.child_by_field_name('arguments'), 'read')
            return

        # 7. 捕获危险跳转
        if node.type == 'goto_statement':
            self.has_unstructured_jumps = True
            return

        # 继续递归遍历其他结构
        for child in node.children:
            self.visit(child, context)