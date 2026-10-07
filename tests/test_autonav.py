"""Pruebas de la navegación automática (hooks/autonav.py)."""
import os

import pytest

import autonav


def write(root, rel, text="# T\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def flat(nav, out=None):
    out = [] if out is None else out
    for item in nav:
        if isinstance(item, str):
            out.append(item)
        else:
            for v in item.values():
                flat(v, out) if isinstance(v, list) else out.append(v)
    return out


def labels(nav):
    res = []
    for item in nav:
        if isinstance(item, dict):
            for k, v in item.items():
                res.append(k)
                if isinstance(v, list):
                    res.extend(labels(v))
    return res


# --- títulos -------------------------------------------------------------
def test_h1_basico_y_tildes():
    assert autonav.first_h1("texto\n# Instalación de Oracle\n") == "Instalación de Oracle"


def test_h1_dentro_de_bloque_de_codigo_se_ignora():
    assert autonav.first_h1("```bash\n# comentario\n```\n\n# Título real\n") == "Título real"


def test_h1_con_crlf_y_front_matter():
    assert autonav.first_h1("---\ntitle: x\n---\r\n# Con CRLF\r\n") == "Con CRLF"


def test_sin_h1_devuelve_none_y_h2_no_cuenta():
    assert autonav.first_h1("## Solo H2\ntexto") is None


def test_etiqueta_desde_nombre():
    assert autonav.clean_label("03-guia-rapida.md") == "Guia rapida"


def test_primer_parrafo():
    assert autonav.first_paragraph("# T\n\nHola **mundo**.\n\nOtro.\n") == "Hola mundo."
    assert autonav.first_paragraph("# T\n\n- lista\n") is None


# --- estructura del menú -------------------------------------------------
def test_menu_inicio_practica_apartado_documento(tmp_path):
    write(tmp_path, "index.md", "# Inicio\n")
    write(tmp_path, "practicas/01-p/index.md", "# Práctica 1\n")
    write(tmp_path, "practicas/01-p/01-a/index.md", "# Apartado A\n")
    write(tmp_path, "practicas/01-p/01-a/doc.md", "# Mi documento\n")
    nav = autonav.build_nav(tmp_path)
    assert nav == [
        {"Inicio": "index.md"},
        {"Práctica 1": ["practicas/01-p/index.md",
                        {"Apartado A": ["practicas/01-p/01-a/index.md",
                                        {"Mi documento": "practicas/01-p/01-a/doc.md"}]}]},
    ]


def test_ya_no_hay_paginas_de_equipo_ni_organizacion(tmp_path):
    for f in ("index.md", "equipo.md", "organizacion.md", "contribuir.md"):
        write(tmp_path, f, f"# {f}\n")
    assert flat(autonav.build_nav(tmp_path)) == ["index.md"]


def test_documento_nuevo_aparece_sin_editar_nada(tmp_path):
    write(tmp_path, "practicas/01-x/doc.md", "# Doc nuevo\n")
    nav = autonav.build_nav(tmp_path)
    assert "Doc nuevo" in labels(nav) and "X" in labels(nav)


def test_orden_por_prefijo_numerico(tmp_path):
    for n in ("10-diez", "02-dos", "01-uno"):
        write(tmp_path, f"practicas/p/{n}.md", f"# {n}\n")
    assert flat(autonav.build_nav(tmp_path)) == [
        "practicas/p/01-uno.md", "practicas/p/02-dos.md", "practicas/p/10-diez.md"]


def test_carpetas_vacias_recursos_y_ocultos_no_aparecen(tmp_path):
    (tmp_path / "practicas/p/01-vacia").mkdir(parents=True)
    write(tmp_path, "practicas/p/02-ok/doc.md")
    write(tmp_path, "practicas/p/02-ok/capturas/leeme.md")
    write(tmp_path, "practicas/p/_borradores/x.md")
    write(tmp_path, "practicas/p/.oculto.md")
    assert flat(autonav.build_nav(tmp_path)) == ["practicas/p/02-ok/doc.md"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sin soporte de symlinks")
def test_enlaces_simbolicos_no_entran(tmp_path):
    docs = tmp_path / "docs"
    write(tmp_path / "fuera", "secreto.md", "# Secreto\n")
    write(docs, "practicas/p/ok.md", "# OK\n")
    os.symlink(tmp_path / "fuera/secreto.md", docs / "practicas/p/enlace.md")
    os.symlink(tmp_path / "fuera", docs / "practicas/p/carpeta")
    assert flat(autonav.build_nav(docs)) == ["practicas/p/ok.md"]


def test_on_files_elimina_symlinks(tmp_path):
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.files import get_files

    docs = tmp_path / "docs"
    write(tmp_path / "fuera", "secreto.md", "# Secreto\n")
    write(docs, "index.md", "# Inicio\n")
    os.symlink(tmp_path / "fuera/secreto.md", docs / "enlace.md")
    cfg = MkDocsConfig()
    cfg.load_dict({"site_name": "t", "docs_dir": str(docs), "site_dir": str(tmp_path / "site")})
    files = get_files(cfg)
    assert files.get_file_from_path("enlace.md") is not None
    out = autonav.on_files(files, cfg)
    assert out.get_file_from_path("enlace.md") is None
    assert out.get_file_from_path("index.md") is not None


# --- contenido generado --------------------------------------------------
def _ejemplo(tmp_path):
    write(tmp_path, "practicas/01-p/index.md", "# Práctica 1\n\nDescripción de la práctica.\n")
    write(tmp_path, "practicas/01-p/01-a/index.md", "# Apartado A\n")
    write(tmp_path, "practicas/01-p/01-a/uno.md", "# Documento uno\n")
    write(tmp_path, "practicas/01-p/01-a/dos.md", "# Documento dos\n")
    write(tmp_path, "practicas/02-q/solo.md", "# Documento solo\n")


def test_vista_de_practicas(tmp_path):
    _ejemplo(tmp_path)
    text = autonav.render_practicas(tmp_path)
    assert "[Práctica 1](practicas/01-p/index.md)" in text
    assert "Descripción de la práctica." in text
    assert "[Apartado A](practicas/01-p/01-a/index.md) · 2 documentos" in text
    assert "[Q](practicas/02-q/solo.md)" in text  # sin index: lleva a su primer documento


def test_lista_de_todos_los_documentos_con_titulo_interno(tmp_path):
    _ejemplo(tmp_path)
    text = autonav.render_documentos(tmp_path)
    for titulo in ("Documento uno", "Documento dos", "Documento solo"):
        assert f"[{titulo}](" in text
    assert "index.md" not in text
    assert "Práctica 1 › Apartado A" in text


def test_contenido_de_una_portada_usa_rutas_relativas(tmp_path):
    _ejemplo(tmp_path)
    text = autonav.render_contenido(tmp_path, "practicas/01-p/index.md")
    assert "[Apartado A](01-a/index.md)" in text
    assert "    - [Documento uno](01-a/uno.md)" in text
    leaf = autonav.render_contenido(tmp_path, "practicas/01-p/01-a/index.md")
    assert "- [Documento dos](dos.md)" in leaf


def test_determinista(tmp_path):
    _ejemplo(tmp_path)
    assert autonav.build_nav(tmp_path) == autonav.build_nav(tmp_path)
    assert autonav.render_practicas(tmp_path) == autonav.render_practicas(tmp_path)
