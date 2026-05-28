# 介绍一下你的沙箱sandbox

答案:
```
我项目里的 sandbox 是 Agent Runtime 的受控执行层。它通过 Sandbox 抽象统一了命令执行和文件操作，通过 SandboxProvider 管理实例。当前实现是 LocalSandbox，Agent 看到的是 /mnt/user-data/... 这样的虚拟路径，底层会映射到每个 thread 独立的本地工作目录。工具层把它封装成 bash/read_file/write_file/grep/glob 等 LangChain tools。执行命令时会经过 bash 审计、路径校验、虚拟路径替换、工作目录绑定、输出脱敏和长度截断。需要强调的是，当前 LocalSandbox 是本地受控执行环境，不是强隔离安全容器；真正生产环境可以替换 Provider 为 Docker/VM 沙箱。
```

详细介绍:
```
我的项目里 sandbox 主要负责给 Agent 提供一个受控的文件和命令执行环境。它不是直接让模型操作宿主机，而是把执行能力抽象成统一的 Sandbox 接口，比如 execute_command、read_file、write_file、list_dir、grep、glob 等。

第一层是抽象层。
Sandbox 定义沙箱具备哪些能力，SandboxProvider 负责创建、获取和释放沙箱实例。这样上层 Agent 不关心底层到底是本地执行、Docker 容器，还是未来的远程沙箱，只依赖统一接口。

第二层是当前实现层。
我现在实现的是 LocalSandboxProvider 和 LocalSandbox。LocalSandboxProvider 会根据配置创建一个本地 sandbox 实例，LocalSandbox 内部通过路径映射把 Agent 看到的虚拟路径，比如 /mnt/user-data/workspace，映射到宿主机真实路径，比如 .deer-flow/threads/<thread_id>/user-data/workspace。这样每个会话都有自己的 workspace、uploads、outputs 目录。

第三层是工具层。
backend/sandbox/tools.py 把 sandbox 能力包装成 LangChain tools，比如 bash、read_file、write_file、str_replace、ls、grep、glob。Agent 真正调用的是这些工具，工具内部再通过 ensure_sandbox_initialized() 获取 sandbox 实例，然后执行对应操作。

```

流程大概是:
```
用户提出任务
  -> Agent 判断需要调用工具
  -> ToolNode 调用 sandbox tool
  -> ensure_sandbox_initialized 获取 sandbox
  -> 校验路径和权限
  -> 虚拟路径替换成本地真实路径
  -> LocalSandbox 执行文件操作或命令
  -> 输出结果脱敏，把真实路径替换回虚拟路径
  -> 返回给 Agent
```

如果是执行脚本:
```
Agent 调用 bash 工具
  -> SandboxAuditMiddleware 先审计命令
  -> bash_tool 检查是否允许 host bash
  -> 校验命令里的绝对路径
  -> 将 /mnt/user-data/... 替换成宿主机路径
  -> 给命令加上 workspace cwd
  -> LocalSandbox.execute_command()
  -> subprocess.run() 在本机 shell 中执行
  -> 返回 stdout / stderr / exit code
```


```
LLM 决定调用工具
  -> LangChain ToolNode 执行工具
  -> sandbox.tools 里的 bash/read_file/write_file
  -> SandboxProvider 获取 Sandbox 实例
  -> LocalSandbox 执行真实文件/命令操作
```

# 整体结构：
## 抽象层
核心思想是：先不关心底层是本机、Docker、远程容器，统一抽象成一个 Sandbox。

```text
execute_command()
read_file()
list_dir()
write_file()
glob()
grep()
update_file()
```

所以这里的设计思路是：
```
Agent 不直接操作 OS
Agent 调用工具
工具调用 Sandbox 抽象
具体 Sandbox 再决定如何执行
```


## 2. Provider 层
真正使用哪个 provider 由 config.yaml 决定, 负责创建和管理 Sandbox。当前是 LocalSandboxProvider。

```
config.yaml
  sandbox.use: sandbox.local:LocalSandboxProvider

get_sandbox_provider()
  -> resolve_class("sandbox.local:LocalSandboxProvider")
  -> 创建 LocalSandboxProvider 单例
```




## 3.当前实现：LocalSandboxProvider
把 sandbox 能力包装成 LangChain tools

```python
_singleton: LocalSandbox | None = None

class LocalSandboxProvider(SandboxProvider):
    def __init__(self):
        self._path_mappings = self._setup_path_mappings()

    def acquire(self, thread_id: str | None = None) -> str:
        global _singleton
        if _singleton is None:
            _singleton = LocalSandbox("local", path_mappings=self._path_mappings)
        return _singleton.id

    def get(self, sandbox_id: str) -> Sandbox | None:
        if sandbox_id == "local":
            if _singleton is None:
                self.acquire()
            return _singleton
        return None
```
重点:
```
LocalSandboxProvider 不会为每个 thread 创建一个独立进程/容器
它只有一个 LocalSandbox 单例
sandbox_id 固定是 "local"
隔离主要靠路径规则，不靠 OS 容器隔离
```

路径映射在 _setup_path_mappings() 里做，比如：
```
/mnt/skills -> 本地 skills 目录，只读
自定义 mounts -> config.yaml 里的 sandbox.mounts
```

## 4. LocalSandbox：真正执行命令和文件操作
它做两件核心事情：
1. 虚拟路径和本地路径互转
```python
def _resolve_path(self, path: str) -> str:
    for mapping in sorted(self.path_mappings, key=lambda m: len(m.container_path), reverse=True):
        if path_str == mapping.container_path or path_str.startswith(mapping.container_path + "/"):
            relative = path_str[len(mapping.container_path):].lstrip("/")
            return str(Path(mapping.local_path) / relative)
    return path_str
```
2. 执行命令。
```python
def execute_command(self, command: str) -> str:
    resolved_command = self._resolve_paths_in_command(command)
    shell = self._get_shell()

    if os.name == "nt":
        if self._is_powershell(shell):
            args = [shell, "-NoProfile", "-Command", resolved_command]
        elif self._is_cmd_shell(shell):
            args = [shell, "/c", resolved_command]
        else:
            args = [shell, "-c", resolved_command]

        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
    else:
        result = subprocess.run(
            resolved_command,
            executable=shell,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
```

## 5.  Agent 怎么拿到 sandbox？
入口在中间件: ```middlewares = [ThreadDataMiddleware(lazy_init=lazy_init),SandboxMiddleware(lazy_init=lazy_init),...]```; lazy_init=True，所以 before_agent() 不立刻创建 sandbox。

真正创建时:
文件：tools.py (line 817)

```python
def ensure_sandbox_initialized(runtime):
    sandbox_state = runtime.state.get("sandbox")

    if sandbox_state is not None:
        sandbox_id = sandbox_state.get("sandbox_id")
        sandbox = get_sandbox_provider().get(sandbox_id)
        if sandbox is not None:
            return sandbox

    thread_id = runtime.context.get("thread_id")
    provider = get_sandbox_provider()
    sandbox_id = provider.acquire(thread_id)

    runtime.state["sandbox"] = {"sandbox_id": sandbox_id}

    sandbox = provider.get(sandbox_id)
    return sandbox
```

执行逻辑
```text
第一次工具调用
  -> runtime.state 里还没有 sandbox
  -> get_sandbox_provider()
  -> provider.acquire(thread_id)
  -> 得到 sandbox_id = "local"
  -> runtime.state["sandbox"] = {"sandbox_id": "local"}

后续工具调用
  -> 直接复用 runtime.state 里的 sandbox_id
```

## 6.bash 工具的完整运行链路

核心代码:
```python
@tool("bash", parse_docstring=True)
def bash_tool(runtime, description: str, command: str) -> str:
    sandbox = ensure_sandbox_initialized(runtime)

    if is_local_sandbox(runtime):
        if not is_host_bash_allowed():
            return "Error: Host bash execution is disabled..."

        ensure_thread_directories_exist(runtime)

        thread_data = get_thread_data(runtime)

        validate_local_bash_command_paths(command, thread_data)

        command = replace_virtual_paths_in_command(command, thread_data)

        command = _apply_cwd_prefix(command, thread_data)

        output = sandbox.execute_command(command)

        return _truncate_bash_output(
            mask_local_paths_in_output(output, thread_data),
            max_chars,
        )

    return sandbox.execute_command(command)
```

运行流程:
```
1. 初始化/获取 sandbox
2. 判断是不是 LocalSandbox
3. 检查是否允许本机 bash
4. 确保 workspace/uploads/outputs 目录存在
5. 校验命令里的绝对路径是否合法
6. 把 /mnt/user-data/... 替换成本机真实路径
7. 在 workspace 目录下执行命令
8. subprocess.run 执行
9. 输出里的本机路径替换回 /mnt/user-data/...
10. 截断过长输出
```

## 7. 文件读写不是通过 bash，而是直接 Python 操作

```python
read_file_tool:

sandbox = ensure_sandbox_initialized(runtime)
validate_local_tool_path(path, thread_data, read_only=True)
path = _resolve_and_validate_user_data_path(path, thread_data)
content = sandbox.read_file(path)

write_file_tool:

sandbox = ensure_sandbox_initialized(runtime)
validate_local_tool_path(path, thread_data)
path = _resolve_and_validate_user_data_path(path, thread_data)

with get_file_operation_lock(sandbox, path):
    sandbox.write_file(path, content, append)
```

```
读文件/写文件不需要 shell
直接走 LocalSandbox.read_file/write_file
底层就是 open(...).read() / open(...).write()
写文件还加了锁，避免并发写同一个文件。
```

## 8. 可以执行代码
比如agent运行: ```python /mnt/user-data/workspace/demo.py```
实际过程:
```
/mnt/user-data/workspace/demo.py
  -> 替换成
C:\Users\BAI\Desktop\project\.deer-flow\threads\<thread_id>\user-data\workspace\demo.py

再加 cwd：
cd <workspace> && python <真实路径>
最后：
subprocess.run([...])

在window大概是:
subprocess.run(
    ["powershell.exe", "-NoProfile", "-Command", resolved_command],
    shell=False,
    capture_output=True,
    text=True,
    timeout=600,
)
```

# 设计理念

```
先抽象统一执行接口
再用 Provider 支持不同执行后端
当前用 LocalSandbox 适配本地开发
通过虚拟路径限制 Agent 的文件视野
通过 middleware 审计危险 bash
通过 config 控制是否暴露 bash

Sandbox 抽象层：统一能力
Provider 层：可替换执行后端
Tools 层：把能力暴露给 Agent
Middleware 层：做审计、注入、生命周期管理
Path 层：用 /mnt/user-data 屏蔽宿主机真实路径
```
当前实现更准确的名字其实是：```本地受控执行环境```, 而不是```真正安全隔离沙箱```

# 真正的sandbox是什么样子的?

当前:
```
Agent -> bash_tool -> LocalSandbox.execute_command()
      -> subprocess.run()
      -> 在宿主机执行
```
真正的:
```
Agent -> bash_tool -> IsolatedSandbox.execute_command()
      -> 容器 / VM / microVM / 远程 worker 内执行
      -> 只挂载允许目录
      -> 限制 CPU/内存/网络/权限/生命周期
```

典型架构:
```
Backend 主进程
  |
  | 1. 创建隔离环境
  v
Sandbox Provider
  |
  | 2. 启动 container / VM / microVM
  v
Isolated Runtime
  - 独立文件系统
  - 非 root 用户
  - 只读基础镜像
  - 只挂载 /mnt/user-data
  - 限制网络
  - 限制 CPU / 内存 / 进程数
  - 超时自动销毁
  |
  | 3. 在里面执行命令
  v
python test.py / npm test / bash script
```
命令执行不是宿主机```subprocess.run("python xxx")```, 而是```docker exec <container> python /mnt/user-data/workspace/test.py```

## 本质区别

![alt text](image-6.png)

命令仍是当前机器执行,
```
防护措施:
validate_local_bash_command_paths()
SandboxAuditMiddleware
allow_host_bash
/mnt/user-data 路径映射

但都属于应用层防护,应用层防护的问题是：只要某个命令形式没被识别、某个路径绕过没覆盖、某个工具行为超出预期，就可能碰到宿主机。
```

## 真正sandbx具备的能力
- 文件系统隔离:容器内只能看到自己的 rootfs 和挂载目录。
- 权限降级: 容器内进程不应该是宿主机高权限用户。
- 资源限制: 防止死循环、内存打爆、fork bomb。
- 网络隔离: 默认禁网，或者只允许特定域名/代理。
- 生命周期隔离: 每个 thread 可以复用一个容器，但要有 idle timeout 和最终销毁。
- 挂载控制: 只把该会话的数据目录挂进去。
- 输出脱敏和审计:  即使有强隔离，也仍然需要审计和日志：

