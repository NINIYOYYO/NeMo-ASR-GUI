"""纯 SVG 矢量图标库与渲染工具模块。

本模块提供系统中所有 UI 组件所使用的纯 SVG 矢量图标定义与渲染辅助函数，
彻底替代 Unicode Emoji 字符，符合 UI 与代码文本规范红线。
"""

import re
from typing import Final

# -----------------------------------------------------------------------------
# 基础 SVG 图标常量定义 (基于 24x24 视口的标准矢量路径)
# -----------------------------------------------------------------------------

SETTINGS_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="3"/>'
    '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06'
    "a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09"
    "A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83"
    "l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09"
    "A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0"
    "l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09"
    "a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83"
    "l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2"
    'h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'
)

CLOUD_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>'
)

FOLDER_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
)

PLAY_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<polygon points="5 3 19 12 5 21 5 3"/></svg>'
)

STOP_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>'
)

ROCKET_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>'
    '<path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>'
    '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>'
    '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>'
)

SAVE_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
    '<polyline points="17 21 17 13 7 13 7 21"/>'
    '<polyline points="7 3 7 8 15 8"/></svg>'
)

REFRESH_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21.5 2v6h-6"/>'
    '<path d="M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>'
)

GLOBE_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="10"/>'
    '<line x1="2" y1="12" x2="22" y2="12"/>'
    '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
)

CUT_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="6" cy="6" r="3"/>'
    '<circle cx="6" cy="18" r="3"/>'
    '<line x1="20" y1="4" x2="8.12" y2="15.88"/>'
    '<line x1="14.47" y1="14.48" x2="20" y2="20"/>'
    '<line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>'
)

WARNING_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
    '<line x1="12" y1="9" x2="12" y2="13"/>'
    '<line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
)

INFO_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="10"/>'
    '<line x1="12" y1="16" x2="12" y2="12"/>'
    '<line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
)

LIGHTBULB_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M9 18h6"/>'
    '<path d="M10 22h4"/>'
    '<path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8'
    'c0 1 .23 2.23 1.5 3.5.76.76 1.23 1.52 1.41 2.5"/></svg>'
)

DOCUMENT_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/>'
    '<line x1="16" y1="13" x2="8" y2="13"/>'
    '<line x1="16" y1="17" x2="8" y2="17"/>'
    '<polyline points="10 9 9 9 8 9"/></svg>'
)

EDIT_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>'
)

MICROPHONE_ICON: Final[str] = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>'
    '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>'
    '<line x1="12" y1="19" x2="12" y2="23"/>'
    '<line x1="8" y1="23" x2="16" y2="23"/></svg>'
)

# -----------------------------------------------------------------------------
# 图标名称到常量映射字典
# -----------------------------------------------------------------------------

ICON_MAP: Final[dict[str, str]] = {
    "settings": SETTINGS_ICON,
    "cloud": CLOUD_ICON,
    "folder": FOLDER_ICON,
    "play": PLAY_ICON,
    "stop": STOP_ICON,
    "rocket": ROCKET_ICON,
    "save": SAVE_ICON,
    "refresh": REFRESH_ICON,
    "globe": GLOBE_ICON,
    "cut": CUT_ICON,
    "warning": WARNING_ICON,
    "info": INFO_ICON,
    "lightbulb": LIGHTBULB_ICON,
    "document": DOCUMENT_ICON,
    "edit": EDIT_ICON,
    "microphone": MICROPHONE_ICON,
}


def get_svg_icon(
    name: str,
    width: int = 16,
    height: int = 16,
    color: str = "currentColor",
    class_name: str = "",
) -> str:
    """根据图标名称获取调整尺寸与颜色后的纯 SVG 字符串。

    Args:
        name (str): 图标命名标识，如 'settings', 'cloud', 'folder', 'play' 等。
        width (int): 图标渲染宽度（像素），默认 16。
        height (int): 图标渲染高度（像素），默认 16。
        color (str): 图标线条或填充颜色，默认 'currentColor'。
        class_name (str): 可选的 CSS 类名，默认为空字符串。

    Returns:
        str: 格式化后的纯 SVG XML 字符串。若未找到匹配图标则返回空字符串。
    """
    svg = ICON_MAP.get(name.lower().strip())
    if not svg:
        return ""

    # 动态调整 width 与 height
    svg = re.sub(r'width="\d+"', f'width="{width}"', svg)
    svg = re.sub(r'height="\d+"', f'height="{height}"', svg)
    if color != "currentColor":
        svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    if class_name:
        svg = re.sub(r"<svg\s+", f'<svg class="{class_name}" ', svg, count=1)

    return svg


def render_svg_html(
    svg_str: str,
    text: str = "",
    gap: int = 6,
    class_name: str = "",
) -> str:
    """将 SVG 图标与文本包裹在内联 HTML 容器中，适用于 Gradio HTML/Markdown 显示。

    Args:
        svg_str (str): 纯 SVG 字符串。
        text (str): 与图标并排显示的文本内容。
        gap (int): 图标与文本之间的间距（像素），默认 6。
        class_name (str): 可选的容器 CSS 类名，默认为空字符串。

    Returns:
        str: 包含 flexbox 垂直对齐的 HTML 字符串。
    """
    if not text:
        return svg_str

    class_attr = f' class="{class_name}"' if class_name else ""
    return (
        f'<span{class_attr} style="display:inline-flex;align-items:center;gap: {gap}px;'
        f'vertical-align:middle;">{svg_str}<span>{text}</span></span>'
    )
