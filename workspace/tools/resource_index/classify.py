"""Classification helpers for local VFX resources."""

from pathlib import Path


_EXTENSION_TYPES = {
    **{ext: "texture" for ext in (".png", ".jpg", ".jpeg", ".tga", ".dds", ".psd", ".tif", ".tiff", ".exr", ".bmp")},
    **{ext: "model" for ext in (".fbx", ".obj", ".blend", ".dae", ".gltf", ".glb")},
    **{ext: "material" for ext in (".mat",)},
    **{ext: "shader" for ext in (".shader", ".hlsl", ".cginc", ".compute", ".shadergraph")},
    **{ext: "package" for ext in (".unitypackage",)},
    **{ext: "document" for ext in (".pdf", ".txt", ".md", ".doc", ".docx", ".rtf")},
    **{ext: "archive" for ext in (".zip", ".rar", ".7z", ".tar", ".gz")},
}

_TAGS = (
    ("slash", ("刀光", "daoguang", "slash", "blade")),
    ("fire", ("火", "fire", "huo", "flame")),
    ("ice", ("冰", "ice", "frost")),
    ("magic-circle", ("法阵", "法陣", "magic-circle", "magic_circle", "magiccircle")),
    ("mask", ("mask", "遮罩")),
    ("noise", ("noise", "噪声", "噪音", "niuqu")),
    ("distortion", ("distortion", "扰动", "扭曲")),
    ("flipbook", ("序列", "序列帧", "sequence", "flipbook")),
    ("trail", ("trail", "拖尾", "轨迹")),
    ("water", ("water", "水", "水系")),
    ("smoke", ("smoke", "烟雾", "烟")),
    ("lightning", ("lightning", "闪电", "雷电", "雷")),
    ("shield", ("shield", "护盾")),
    ("portal", ("portal", "传送门", "传送")),
    ("ground", ("ground", "地面")),
    ("UI", ("ui", "UI", "界面")),
    ("model", ("model", "模型")),
)

_LICENSE_HINTS = (
    ("免责声明", ("免责声明", "disclaimer")),
    ("商店页面", ("商店页面", "store", "assetstore", "商店")),
    ("来源", ("来源", "source", "出处")),
    ("具体游戏名", ("游戏", "game", "unity")),
    ("素材包", ("素材包", "assetpack", "pack")),
)


def _matches(component: str, terms: tuple[str, ...]) -> bool:
    value = component.casefold()
    return any(term.casefold() in value for term in terms)


def classify_asset(path: Path) -> str:
    """Return the stable asset category for a path based on its extension."""
    return _EXTENSION_TYPES.get(path.suffix.casefold(), "other")


def derive_tags(relative_path: Path) -> list[str]:
    """Normalize recognized vocabulary in first-seen path order."""
    components = tuple(relative_path.parts)
    tags: list[str] = []
    for component in components:
        for tag, terms in _TAGS:
            if tag not in tags and _matches(component, terms):
                tags.append(tag)
    if classify_asset(relative_path) == "model" and "model" not in tags:
        tags.append("model")
    return tags


def infer_license(relative_path: Path) -> tuple[str, list[str]]:
    """Collect licensing evidence without changing the conservative status."""
    components = tuple(relative_path.parts)
    hints = [hint for hint, terms in _LICENSE_HINTS if any(_matches(component, terms) for component in components)]
    return "unknown", hints
