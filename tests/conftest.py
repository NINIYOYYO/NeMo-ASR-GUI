"""pytest 公共桩。

在导入业务代码前，为缺失的重依赖（gradio / torch / nemo / pydub /
openai / httpx / pandas）注入轻量假模块，使核心逻辑测试无需
GPU、NeMo 或完整依赖环境即可运行（CI 友好）。

注意：仅在真实依赖 **未安装** 时才注入桩；本机已安装真实依赖时
使用真实模块，并通过钩子保持测试断言兼容。
"""

import importlib.util
import sys
import types
from pathlib import Path

# 保证可以从仓库根目录导入业务模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _missing(name: str) -> bool:
    """检查依赖模块是否存在且能安全导入。"""
    if name in sys.modules:
        return False
    try:
        if importlib.util.find_spec(name) is None:
            return True
        __import__(name)
        return False
    except Exception:
        return True


# ---------- torch ----------
class FakeDevice:
    """模拟 torch.device 对象的最小桩实现。"""

    def __init__(self, t: str) -> None:
        self.type = t.split(":")[0]

    def __repr__(self) -> str:
        return self.type


if _missing("torch"):
    torch = types.ModuleType("torch")
    torch.device = lambda t: FakeDevice(t)  # type: ignore[attr-defined]
    torch.cuda = types.SimpleNamespace(  # type: ignore[attr-defined]
        is_available=lambda: False,
        empty_cache=lambda: None,
        ipc_collect=lambda: None,
    )
    sys.modules["torch"] = torch

# ---------- nemo ----------
if _missing("nemo"):
    nemo = types.ModuleType("nemo")
    nemo_c = types.ModuleType("nemo.collections")
    nemo_a = types.ModuleType("nemo.collections.asr")
    nemo_a.models = types.SimpleNamespace(  # type: ignore[attr-defined]
        ASRModel=types.SimpleNamespace(from_pretrained=None, restore_from=None)
    )
    sys.modules.update({"nemo": nemo, "nemo.collections": nemo_c, "nemo.collections.asr": nemo_a})

# ---------- pydub ----------
if _missing("pydub"):
    pydub = types.ModuleType("pydub")
    pydub.AudioSegment = type("AudioSegment", (), {})  # type: ignore[attr-defined]
    sys.modules["pydub"] = pydub

# ---------- openai / httpx ----------
if _missing("openai"):
    openai_m = types.ModuleType("openai")
    openai_m.AsyncOpenAI = type("AsyncOpenAI", (), {})  # type: ignore[attr-defined]
    sys.modules["openai"] = openai_m

if _missing("httpx"):
    httpx_m = types.ModuleType("httpx")
    httpx_m.AsyncClient = type("AsyncClient", (), {})  # type: ignore[attr-defined]
    httpx_m.AsyncHTTPTransport = type("AsyncHTTPTransport", (), {})  # type: ignore[attr-defined]
    sys.modules["httpx"] = httpx_m


# ---------- pandas ----------
class FakeDataFrame:
    """具备完整迭代与表格协议支持的 DataFrame 桩实现。"""

    def __init__(self, rows: list | None = None, columns: list | None = None) -> None:
        self._rows: list = list(rows) if rows is not None else []
        self.columns: list = columns if columns is not None else []
        self.values = types.SimpleNamespace(tolist=lambda: self._rows)

    def __iter__(self):
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, item):
        return self._rows[item]

    def to_dict(self, *args, **kwargs):
        return self._rows


if _missing("pandas"):
    pd = types.ModuleType("pandas")
    pd.DataFrame = FakeDataFrame  # type: ignore[attr-defined]
    sys.modules["pandas"] = pd

# ---------- yaml ----------
if _missing("yaml"):
    yaml_m = types.ModuleType("yaml")
    yaml_m.safe_load = lambda f: {}  # type: ignore[attr-defined]
    sys.modules["yaml"] = yaml_m

# ---------- gradio ----------
GR_BOUND: list = []  # 记录 (fn, inputs, outputs) 事件绑定，供 UI 冒烟测试断言

if not _missing("gradio"):
    import gradio as gr
    import gradio.events as ge
    from gradio.blocks import Block
    from gradio.components.base import Component

    def _patch_events(cls):
        for event_name in ge.all_events:
            if hasattr(cls, event_name):
                orig_method = getattr(cls, event_name)
                if callable(orig_method) and not getattr(orig_method, "_is_gr_patched", False):

                    def _make_wrapped(m):
                        def _wrapped(self, fn=None, inputs=None, outputs=None, **kwargs):
                            if fn is not None and fn != "decorator":
                                GR_BOUND.append((fn, inputs, outputs))
                            res = m(self, fn=fn, inputs=inputs, outputs=outputs, **kwargs)
                            if hasattr(res, "then"):
                                orig_then = res.then

                                def _wrapped_then(fn=None, inputs=None, outputs=None, **k):
                                    if fn is not None and fn != "decorator":
                                        GR_BOUND.append((fn, inputs, outputs))
                                    return orig_then(fn=fn, inputs=inputs, outputs=outputs, **k)

                                res.then = _wrapped_then
                            return res

                        _wrapped._is_gr_patched = True
                        return _wrapped

                    setattr(cls, event_name, _make_wrapped(orig_method))

    for name in dir(gr):
        obj = getattr(gr, name)
        if isinstance(obj, type) and (issubclass(obj, Block) or issubclass(obj, Component)):
            _patch_events(obj)
else:
    gr = types.ModuleType("gradio")

    class _Comp:
        def __init__(self, *a, **k) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def _bind(self, fn=None, inputs=None, outputs=None, **k):
            GR_BOUND.append((fn, inputs, outputs))
            return self

        click = change = upload = submit = _bind

        def then(self, fn=None, *a, **k):
            GR_BOUND.append((fn, None, None))
            return self

    for _name in [
        "Blocks",
        "Markdown",
        "Dropdown",
        "Textbox",
        "Button",
        "Slider",
        "Tab",
        "Row",
        "Column",
        "Accordion",
        "File",
        "CheckboxGroup",
        "Checkbox",
        "Dataframe",
        "Info",
    ]:
        setattr(gr, _name, type(_name, (_Comp,), {}))
    gr.themes = types.SimpleNamespace(Soft=lambda: None)  # type: ignore[attr-defined]
    gr.update = lambda **k: dict(k)  # type: ignore[attr-defined]
    sys.modules["gradio"] = gr
