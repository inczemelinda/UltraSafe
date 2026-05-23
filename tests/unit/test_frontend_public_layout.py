from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_public_pages_source() -> str:
    return (ROOT / "frontend/src/pages/PublicPages.tsx").read_text(
        encoding="utf-8"
    )


def read_grainient_source() -> str:
    return (ROOT / "frontend/src/components/grainient/Grainient.tsx").read_text(
        encoding="utf-8"
    )


def read_ui_source() -> str:
    return (ROOT / "frontend/src/components/ui.tsx").read_text(
        encoding="utf-8"
    )


def read_layouts_source() -> str:
    return (ROOT / "frontend/src/layouts/AppLayouts.tsx").read_text(
        encoding="utf-8"
    )


def component_source(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_public_home_uses_grainient_background_from_shell() -> None:
    source = read_public_pages_source()
    layouts = read_layouts_source()
    home = component_source(
        source,
        "export function HomePage()",
        "export function AboutPage()",
    )

    assert "<PublicBackground>" in layouts
    assert "showGrainient" not in layouts
    assert "bg-transparent text-white" in home
    assert "text-white drop-shadow-sm" in home
    assert "text-white/90 drop-shadow-sm" in home
    assert "<Ballpit" not in home
    assert "bg-gradient-to-r from-white to-sky-100" not in home


def test_public_grainient_is_vibrant_and_flowy() -> None:
    source = read_ui_source()
    public_background = component_source(
        source,
        "export function PublicBackground",
        "export function EmployeeDashboardBackground",
    )

    assert 'color1="#bae6fd"' in public_background
    assert 'color2="#60a5fa"' in public_background
    assert 'color3="#99f6e4"' in public_background
    assert "timeSpeed={1.8}" in public_background
    assert "warpStrength={1.45}" in public_background
    assert "warpAmplitude={28}" in public_background
    assert "warpSpeed={1.15}" in public_background
    assert "saturation={1.5}" in public_background
    assert "bg-white/58" not in public_background
    assert "bg-slate-950/6" in public_background


def test_grainient_does_not_crash_when_webgl_is_unavailable() -> None:
    source = read_grainient_source()

    assert "let renderer: Renderer;" in source
    assert "try {" in source
    assert "new Renderer({" in source
    assert "Grainient disabled because WebGL could not be initialized." in source
    assert "if (!gl)" in source
