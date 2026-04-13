import re
import tree_sitter
import tree_sitter_cpp
from enum import Enum, auto
from typing import List, Optional, Dict, Any

# 1. 初始化 Tree-sitter C++ 语法引擎
CPP_LANGUAGE = tree_sitter.Language(tree_sitter_cpp.language())
parser = tree_sitter.Parser()
parser.language = CPP_LANGUAGE

class ScopeType(Enum):
    GLOBAL = auto()
    NAMESPACE = auto()
    ANONYMOUS_NAMESPACE = auto()
    CLASS = auto()
    STRUCT = auto()

class Scope:
    """单个作用域节点的数据结构"""
    def __init__(self, name: str, scope_type: ScopeType):
        self.name = name
        self.scope_type = scope_type
        self.using_directives: List[str] = []
        
    def is_linkage_barrier(self) -> bool:
        """判断当前作用域是否会阻断外部链接 (即内部链接属性)"""
        return self.scope_type == ScopeType.ANONYMOUS_NAMESPACE

class ScopeTracker:
    """
    核心大脑：作用域栈管理器
    负责追踪当前所处的 Namespace 和 Class，智能拼接 FQN，并判定链接属性。
    """
    def __init__(self):
        # 初始化时默认压入一个全局作用域
        self._stack: List[Scope] = [Scope("::", ScopeType.GLOBAL)]
        self._anonymous_counter = 0

    def push_namespace(self, name: Optional[str]) -> Scope:
        """压入命名空间。处理真实 C++ 中的匿名命名空间"""
        if not name:
            self._anonymous_counter += 1
            scope = Scope(f"anonymous_namespace_{self._anonymous_counter}", ScopeType.ANONYMOUS_NAMESPACE)
        else:
            scope = Scope(name, ScopeType.NAMESPACE)
        self._stack.append(scope)
        return scope

    def push_class_or_struct(self, name: str, is_struct: bool = False) -> Scope:
        """压入类或结构体"""
        scope_type = ScopeType.STRUCT if is_struct else ScopeType.CLASS
        scope = Scope(name, scope_type)
        self._stack.append(scope)
        return scope

    def pop(self):
        """弹出当前作用域 (出栈)"""
        if len(self._stack) > 1: # 保护全局作用域不被弹出
            self._stack.pop()

    @property
    def current_scope(self) -> Scope:
        return self._stack[-1]

    def add_using_directive(self, directive: str):
        """将 using 声明挂载到当前作用域"""
        self.current_scope.using_directives.append(directive)

    def is_internal_linkage(self) -> bool:
        """
        深度扫描：只要作用域栈中存在任意一个匿名命名空间，
        当前节点必定具有内部链接属性 (Internal Linkage)。
        """
        return any(scope.is_linkage_barrier() for scope in self._stack)

    def get_current_fqn(self) -> str:
        """
        获取当前绝对正确的 FQN (完全限定名)
        处理逻辑：过滤全局伪节点，用 '::' 拼接所有合法的命名空间和类名。
        """
        parts = []
        for scope in self._stack:
            if scope.scope_type == ScopeType.GLOBAL:
                continue
            parts.append(scope.name)
        
        return "::".join(parts) if parts else ""

    def resolve_entity_fqn(self, entity_name: str) -> str:
        """
        智能 FQN 解析器 (应对 C++ 最恶心的类外实现)
        真实案例：
        1. 物理层在 namespace net 里，entity_name 是 "TcpSocket" -> "net::TcpSocket"
        2. 物理层在顶层，entity_name 是 "net::TcpSocket::connect" -> 本身已经是 FQN，直接返回
        """
        if "::" in entity_name:
            # 如果名字自身已经携带了作用域标识，通常说明它是一个类外定义，或者已经是 FQN 了
            # (在更严谨的实现中，我们可以比对前缀，但目前直接返回自身是最安全且防抖的策略)
            return entity_name
        
        current_context = self.get_current_fqn()
        if current_context:
            return f"{current_context}::{entity_name}"
        return entity_name

# 包含所有核心逻辑的 CppParser 类，重命名为 _CppFileWorker
class _CppFileWorker:
    """
    C++ AST 全量语素提取解析器
    基于 Tree-sitter 与 Schema 4.5
    """
    def __init__(self, source_code: bytes, file_path: str):
        self.file_path = file_path
        
        # 1. 智能正则清道夫
        clean_code_str = source_code.decode('utf-8', errors='ignore')
        clean_code_str = re.sub(r'\b[A-Z0-9_]+_(API|EXPORT|IMPORT|CORE)\b', '', clean_code_str)
        clean_code_str = re.sub(r'__attribute__\s*\(\([^)]+\)\)', '', clean_code_str)
        clean_code_str = re.sub(r'__declspec\s*\([^)]+\)', '', clean_code_str)
        
        # 将清洗后的代码重新编码，并覆盖 self.source_code
        self.source_code = clean_code_str.encode('utf-8')
        
        self.tree = parser.parse(self.source_code)
        self.scope_tracker = ScopeTracker()

        # 2. Schema 4.5 终极版初始骨架
        self.schema = {
            "metadata": {
                "language": "cpp",
                "file_path": file_path,
                # 动态判断是头文件还是源文件
                "file_type": "source" if file_path.endswith(('.cpp', '.cc', '.cxx', '.c')) else "header",
                "companion_header": None,
                "ast_health": "healthy",
                "error_node_count": 0
            },
            "dependencies": {"local_includes": []},
            "namespaces": [],
            "global_states": [],
            "explicit_instantiations": [],
            "classes": [],
            "standalone_functions": [],
            "types": []
        }

        # 核心架构设计：逻辑类收纳盒 (Class Registry)
        # 为什么需要它？在 .cpp 文件中遇到 A::func() 时，当前文件可能根本没有 class A 的定义。
        # 我们用这个字典按 FQN 临时存放所有的 class 对象，最后统一塞入 self.schema["classes"]
        self._class_registry: Dict[str, dict] = {}

    def _get_text(self, node: tree_sitter.Node) -> str:
        """安全提取节点文本的工具方法"""
        if not node:
            return ""
        return self.source_code[node.start_byte:node.end_byte].decode('utf8', errors='ignore')

    def parse(self) -> dict:
        """解析引擎主入口"""
        # 从根节点开始深度遍历
        self._walk(self.tree.root_node)
        
        # 遍历结束后，进行健康度结算和类收纳盒合并
        self._finalize_schema()
        return self.schema

    def _handle_namespace(self, node: tree_sitter.Node):
        """
        处理 Namespace (包括极其致命的匿名命名空间)
        """
        # 1. 嗅探命名空间名称
        identifier_node = node.child_by_field_name('name')
        namespace_name = self._get_text(identifier_node) if identifier_node else None

        # 2. 压入作用域栈 (ScopeTracker 会自动处理匿名逻辑)
        scope = self.scope_tracker.push_namespace(namespace_name)
        is_anonymous = (namespace_name is None)

        # 3. 构建 Schema 中的 Namespace 对象 (仅记录根级或具名的，避免嵌套污染)
        # 这里我们在顶层记录，方便大模型查看，但内部链接属性会通过栈向下渗透
        ns_data = {
            "name": scope.name,
            "is_anonymous": is_anonymous,
            "using_directives": []
        }
        
        # 4. 遍历命名空间内部的代码块 (declaration_list)
        body_node = node.child_by_field_name('body')
        if body_node:
            for child in body_node.children:
                # 全面拦截 C++ 中所有的命名空间与别名引入机制
                if child.type in ('using_declaration', 'using_directive', 'alias_declaration'):
                    using_code = self._get_text(child).strip()
                    ns_data["using_directives"].append(using_code)
                    scope.using_directives.append(using_code)
                else:
                    # 递归遍历其他子节点
                    self._walk(child)

        # 将有价值的命名空间保存到 schema
        if ns_data["using_directives"] or is_anonymous or namespace_name:
            # 为了保持输出整洁，只在全局级别记录大的 namespace 结构
            if len(self.scope_tracker._stack) == 2: # [GLOBAL, THIS_NAMESPACE]
                self.schema["namespaces"].append(ns_data)

        # 5. 极其关键：离开节点前必须出栈，维持作用域平衡！
        self.scope_tracker.pop()

    def _finalize_schema(self):
        """收尾工作：合并数据，计算最终状态"""
        # 引入 Tree-sitter 全局错误探针兜底
        root_has_error = self.tree.root_node.has_error
        # 计算 AST 健康度
        if self.schema["metadata"]["error_node_count"] > 5:
            self.schema["metadata"]["ast_health"] = "degraded"
            
        # 将 registry 中的类转换回列表，并存入 schema
        self.schema["classes"] = list(self._class_registry.values())

    def _walk(self, node: tree_sitter.Node, is_extern_c_context: bool = False):
        """核心路由：AST 深度遍历器"""
        if node.type == 'ERROR' or node.is_missing:
            self.schema["metadata"]["error_node_count"] += 1

        # 【新增：拦截 ABI 边界】
        if node.type == 'linkage_specification':
            val_node = node.child_by_field_name('value')
            if val_node and self._get_text(val_node) == '"C"':
                # 带着 C 链接上下文遍历内部的代码块
                body_node = node.child_by_field_name('body')
                if body_node:
                    for child in body_node.children:
                        self._walk(child, is_extern_c_context=True)
                return

        # 1. 命名空间
        if node.type == 'namespace_definition':
            self._handle_namespace(node)
            return 

        # 2. 类与结构体
        elif node.type in ('class_specifier', 'struct_specifier'):
            self._handle_class(node)
            return

        # 3. 函数体定义 (有 {} 的函数)
        elif node.type == 'function_definition':
            self._handle_function(node, has_body=True, is_extern_c=is_extern_c_context)
            return

        # 4. 常规声明 (无 {} 的函数原型、=delete 契约、全局/静态变量初始化)
        elif node.type == 'declaration':
            self._handle_declaration(node)
            return

        # 5. 模板实例化 (防范链接器幻觉)
        elif node.type == 'template_instantiation_declaration':
            self.schema["explicit_instantiations"].append(self._get_text(node).strip())
            return

        # 默认回退：继续深度遍历子节点
        for child in node.children:
            self._walk(child, is_extern_c_context)

    def _handle_class(self, node: tree_sitter.Node):
        """
        核心逻辑：处理类与结构体
        完美解决 Schema 4.5 中的 is_physical_definition 和 is_forward_declaration
        """
        name_node = node.child_by_field_name('name')
        if not name_node:
            return  # 忽略完全匿名的内部类 (对宏观 RPG 无价值)

        class_name = self._get_text(name_node)
        body_node = node.child_by_field_name('body')
        
        # 判定物理状态：没有 body 就是前向声明 (class TcpSocket;)
        is_forward_decl = (body_node is None)

        # 获取绝对正确的 FQN (如 core::network::TcpSocket)
        fqn = self.scope_tracker.resolve_entity_fqn(class_name)

        # --- 物理与逻辑二象性处理 ---
        if fqn not in self._class_registry:
            # 场景 A：第一次遇到这个类
            self._class_registry[fqn] = {
                "name": fqn,
                "kind": "struct" if node.type == 'struct_specifier' else "class",
                "is_physical_definition": not is_forward_decl,
                "is_forward_declaration": is_forward_decl,
                "has_internal_linkage": self.scope_tracker.is_internal_linkage(),
                "location": {"start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1} if not is_forward_decl else None,
                "base_classes": [],
                "friends": [],
                "using_declarations": [],
                "out_of_line_static_initializers": [],
                "methods": []
            }
        else:
            # 场景 B：这个类之前已经被创建过了 (比如在 .cpp 顶层先解析到了它的类外方法)
            # 我们需要把那个虚无的“逻辑收纳盒”升级为“物理定义”
            if not is_forward_decl:
                cls_data = self._class_registry[fqn]
                cls_data["is_physical_definition"] = True
                cls_data["is_forward_declaration"] = False
                cls_data["location"] = {"start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1}
                cls_data["has_internal_linkage"] = self.scope_tracker.is_internal_linkage()

        # 如果是物理定义，不再依赖 field_name，直接靠类型嗅探基类列表
        if not is_forward_decl:
            for child in node.children:
                if child.type == 'base_class_clause':
                    base_text = self._get_text(child).replace(':', '', 1).strip()
                    self._class_registry[fqn]["base_classes"].append(base_text)
                    break

        # --- 作用域压栈与深度遍历 ---
        self.scope_tracker.push_class_or_struct(class_name, node.type == 'struct_specifier')

        if body_node:
            for child in body_node.children:
                # 【防线】：嗅探类内部是否有 AST 解析断层
                if child.type == 'ERROR':
                    self._class_registry[fqn]["has_parse_errors"] = True
                
                # 拦截类内的 using 隐式接口拉取 (补丁 4.2)
                elif child.type == 'using_declaration':
                    self._class_registry[fqn]["using_declarations"].append(self._get_text(child).strip())
                
                else:
                    self._walk(child)

        # 🚨 必须出栈！
        self.scope_tracker.pop()

    def _handle_declaration(self, node: tree_sitter.Node):
        """
        处理常规声明：函数原型、变量声明、现代 C++ 契约
        """
        # 提取节点的纯文本
        text = self._get_text(node).strip()

        # 1. 无视空格、换行、及尾部注释的契约拦截 (= delete, = default)
        # 匹配模式：等号 + 任意空白 + delete/default + 任意空白 + 分号 + (可选的尾部空白或注释)
        contract_match = re.search(r'=\s*(delete|default)\s*;\s*(//.*|/\*.*\*/\s*)*$', text, re.DOTALL)
        if contract_match:
            self._handle_function(node, has_body=False, is_contract=True)
            return

        # 2. AST 级别的防误报类外静态成员嗅探
        # 【精准修复 1】：解决“鸡和蛋”的孤儿状态拦截
        if self.scope_tracker.current_scope.scope_type in (ScopeType.GLOBAL, ScopeType.NAMESPACE):
            for child in node.children:
                if child.type == 'init_declarator':
                    decl_node = child.child_by_field_name('declarator')
                    # 剥离指针和引用的外衣，直达本质
                    while decl_node and decl_node.type in ('pointer_declarator', 'reference_declarator'):
                        decl_node = decl_node.child_by_field_name('declarator')
                    if decl_node and decl_node.type == 'scoped_identifier':
                        scope_node = decl_node.child_by_field_name('scope')
                        if scope_node:
                            class_fqn = self.scope_tracker.resolve_entity_fqn(self._get_text(scope_node))
                            
                            # 如果收纳盒里没有这个类，强行创建一个逻辑壳！
                            if class_fqn not in self._class_registry:
                                self._class_registry[class_fqn] = {
                                    "name": class_fqn,
                                    "kind": "class", # 默认当成 class
                                    "is_physical_definition": False,
                                    "is_forward_declaration": False,
                                    "has_internal_linkage": self.scope_tracker.is_internal_linkage(),
                                    "location": None, "base_classes": [], "friends": [], "using_declarations": [], 
                                    "out_of_line_static_initializers": [], "methods": []
                                }
                            self._class_registry[class_fqn]["out_of_line_static_initializers"].append(text)
                            return
        
        # 3. 如果是普通的函数原型声明 (比如 void func();)
        # 可以通过查找内部是否有 function_declarator 来判断
        for child in node.children:
            if child.type == 'function_declarator':
                self._handle_function(node, has_body=False)
                return

        # 其他未命中情况（如普通局部变量、typedef等），继续下钻
        for child in node.children:
            self._walk(child)

        # 如果既不是契约、不是类外静态、不是函数，且在全局/命名空间下，那它就是全局状态！
        if self.scope_tracker.current_scope.scope_type in (ScopeType.GLOBAL, ScopeType.NAMESPACE, ScopeType.ANONYMOUS_NAMESPACE):
            # 提取 is_static, has_internal_linkage 等，然后加入 self.schema["global_states"]
            pass
            
    # ==========================================
    # 第四部分：核心函数解析引擎
    # ==========================================
    def _handle_function(self, node: tree_sitter.Node, has_body: bool, is_contract: bool = False, is_extern_c: bool = False):
        """处理所有形态的函数：类方法、独立函数、类外实现、契约"""
        # 不依赖 'body' 字段名，直接遍历子节点寻找契约(= delete/default)的 AST 特征进行拦截
        for child in node.children:
            if child.type == 'delete_method_clause':
                is_deleted = True
                has_body = False
                is_contract = True
                break
            elif child.type == 'default_method_clause':
                is_defaulted = True
                has_body = False
                is_contract = True
                break

        # 1. 深度挖掘真实的 identifier (扒开指针、引用的外衣)
        declarator_node = node.child_by_field_name('declarator')
        if not declarator_node:
            for child in node.children:
                if child.type in ('function_declarator', 'reference_declarator', 'pointer_declarator'):
                    declarator_node = child
                    break
        if not declarator_node:
            return

# ========================================================
        # 【新增】：在继续下钻之前，先把函数的参数列表提取出来
        # 原因：参数本质上也是局部变量，绝不能作为外部依赖连线！
        # ========================================================
        parameters = set()
        
        # 【精准修复】：必须先剥去返回值的指针/引用外衣，找到真正的 function_declarator
        func_decl_node = declarator_node
        while func_decl_node and func_decl_node.type in ('pointer_declarator', 'reference_declarator'):
            func_decl_node = func_decl_node.child_by_field_name('declarator')
            
        # 只有在真正的 function_declarator 下，才能安全地取到 'parameters'
        if func_decl_node and func_decl_node.type == 'function_declarator':
            params_node = func_decl_node.child_by_field_name('parameters')
            if params_node:
                for p in params_node.children:
                    if p.type in ('parameter_declaration', 'optional_parameter_declaration'):
                        p_decl = p.child_by_field_name('declarator')
                        # 扒开参数自身的指针/引用外衣 (如 const Task* t -> t)
                        while p_decl and p_decl.type in ('pointer_declarator', 'reference_declarator', 'array_declarator'):
                            p_decl = p_decl.child_by_field_name('declarator')
                        if p_decl and p_decl.type == 'identifier':
                            parameters.add(self._get_text(p_decl))
        # ========================================================

        curr = declarator_node
        while curr and curr.type not in ('identifier', 'scoped_identifier', 'field_identifier', 'operator_name', 'destructor_name'):
            curr_child = curr.child_by_field_name('declarator')
            if curr_child:
                curr = curr_child
            else:
                break
        
        raw_name = self._get_text(curr) if curr else "unknown_func"
        
        # 2. 判定是否为类外定义 (Out-of-line)
        is_out_of_line = (curr and curr.type == 'scoped_identifier')
        
        # 3. 提取脱水签名 (剥离函数体)
        signature = ""
        for child in node.children:
            if child.type == 'compound_statement':
                break
            signature += self._get_text(child) + " "
        signature = re.sub(r'\s+', ' ', signature).strip() # 压缩空格

        # 4. 路由与归属判定
        target_class_fqn = None
        func_name_only = raw_name

        if is_out_of_line:
            # 形如 core::network::TcpSocket::connect
            parts = raw_name.split('::')
            func_name_only = parts[-1]
            class_part = '::'.join(parts[:-1])
            target_class_fqn = self.scope_tracker.resolve_entity_fqn(class_part)
        elif self.scope_tracker.current_scope.scope_type in (ScopeType.CLASS, ScopeType.STRUCT):
            # 类内定义
            target_class_fqn = self.scope_tracker.get_current_fqn()

        # 5. 组装 Schema 数据 (严格遵守 Schema 4.5 减法原则)
        func_data = {
            "name": func_name_only,
            "signature": signature,
            "is_out_of_line_definition": is_out_of_line,
            "has_body": has_body,
            "is_extern_c": is_extern_c
        }

        if has_body or is_contract:
            func_data["location"] = {"start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1}

        # 6. 数据流引擎挂载 (仅有 body 时挂载，空数据将在 finalize 阶段剥离)
        if has_body:
            # 从语法树节点中真正把函数体提取出来
            body_node = node.child_by_field_name('body')
            # 嗅探构造函数初始化列表
            init_list_node = node.child_by_field_name('initializers')
            if not init_list_node:
                for child in node.children:
                    if child.type == 'field_initializer_list':
                        init_list_node = child
                        break
            if init_list_node:
                func_data["initializer_list_snapshot"] = self._get_text(init_list_node)

            # 准备数据流容器
            func_data["data_flow"] = {
                "reads_globals": [], "writes_globals": [],
                "reads_members": [], "writes_members": [],
                "unresolved_reads": [], "unresolved_writes": [], 
                "local_statics": []
            }
            func_data["control_flow"] = {
                "direct_calls": [], "indirect_calls": [], "throws": []
            }
            
            self._analyze_function_body(body_node, func_data, parameters)

        # 7. 归档
        if target_class_fqn:
            if target_class_fqn not in self._class_registry:
                self._class_registry[target_class_fqn] = {
                    "name": target_class_fqn,
                    "kind": "class",
                    "is_physical_definition": False,
                    "is_forward_declaration": False,
                    "has_internal_linkage": self.scope_tracker.is_internal_linkage(),
                    "location": None, "base_classes": [], "friends": [], "using_declarations": [], "out_of_line_static_initializers": [],
                    "methods": []
                }
            self._class_registry[target_class_fqn]["methods"].append(func_data)
        else:
            func_data["name"] = self.scope_tracker.resolve_entity_fqn(raw_name)
            self.schema["standalone_functions"].append(func_data)

    def _analyze_function_body(self, body_node: tree_sitter.Node, func_data: dict, parameters: set):
        if not body_node: return

        direct_calls, local_statics, writes, all_identifiers, local_vars = set(), set(), set(), set(), set()

        def _traverse_body(node: tree_sitter.Node):
            # 登记局部变量
            if node.type == 'declaration':
                is_static = any(c.type == 'storage_class_specifier' and self._get_text(c) == 'static' for c in node.children)
                for child in node.children:
                    if child.type == 'init_declarator':
                        decl = child.child_by_field_name('declarator')
                        while decl and decl.type in ('pointer_declarator', 'reference_declarator', 'array_declarator'):
                            decl = decl.child_by_field_name('declarator')
                        if decl and decl.type == 'identifier':
                            (local_statics if is_static else local_vars).add(self._get_text(decl))
                    elif child.type == 'identifier':
                        (local_statics if is_static else local_vars).add(self._get_text(child))

            # 调用
            elif node.type == 'call_expression':
                func_node = node.child_by_field_name('function')
                if func_node:
                    if func_node.type in ('identifier', 'scoped_identifier'):
                        direct_calls.add(self._get_text(func_node))
                    elif func_node.type == 'field_expression':
                        field_node = func_node.child_by_field_name('field')
                        if field_node: direct_calls.add(self._get_text(field_node))
                    else:
                        func_data["control_flow"]["indirect_calls"].append(self._get_text(func_node))
            # 赋值写
            elif node.type == 'assignment_expression':
                left_node = node.child_by_field_name('left')
                if left_node: writes.add(self._get_text(left_node))
            # 更新写
            elif node.type == 'update_expression':
                for child in node.children:
                    if child.type in ('identifier', 'scoped_identifier', 'field_expression', 'subscript_expression'):
                        writes.add(self._get_text(child))
                        break

            # 抓取所有可能被读写的标识符
            elif node.type in ('identifier', 'scoped_identifier', 'field_identifier'):
                all_identifiers.add(self._get_text(node))
                    
            for child in node.children:
                _traverse_body(child)

        _traverse_body(body_node)

        if direct_calls: func_data["control_flow"]["direct_calls"] = list(direct_calls)
        if local_statics: func_data["data_flow"]["local_statics"] = list(local_statics)

        # 核心逻辑：物理遮蔽减法！
        true_writes = writes - local_vars - parameters
        true_reads = all_identifiers - writes - direct_calls - local_statics - local_vars - parameters

        def _classify_and_append(var_name: str, target_dict: dict, is_write: bool):
            clean_name = var_name
            is_explicit_member = False
            if clean_name.startswith('this->'):
                is_explicit_member = True
                clean_name = clean_name.replace('this->', '', 1)
            if '::' in clean_name:
                clean_name = clean_name.split('::')[-1]

            if is_explicit_member or clean_name.startswith('m_') or clean_name.endswith('_'):
                target_dict["writes_members" if is_write else "reads_members"].append(var_name)
            elif clean_name.startswith('g_') or clean_name.startswith('s_') or clean_name.startswith('t_'):
                target_dict["writes_globals" if is_write else "reads_globals"].append(var_name)
            else:
                # 幸存者装入 unresolved 桶！
                target_dict["unresolved_writes" if is_write else "unresolved_reads"].append(var_name)

        for w in true_writes: _classify_and_append(w, func_data["data_flow"], is_write=True)
        for r in true_reads: _classify_and_append(r, func_data["data_flow"], is_write=False)

# 对外暴露无状态的 CppParser
class CppParser:
    """
    无状态接口适配器：为了兼容 main.py 的批量调用
    """
    def __init__(self):
        # 初始化时只加载一次 Tree-sitter Language，避免内存泄露
        self.language = tree_sitter.Language(tree_sitter_cpp.language())

    def parse_file(self, file_path: str, source_code: bytes) -> dict:
        """每次处理新文件时，实例化一个全新的工作空间，防止数据污染"""
        worker = _CppFileWorker(source_code, file_path)
        return worker.parse()