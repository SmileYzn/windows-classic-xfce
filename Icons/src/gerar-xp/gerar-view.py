#!/usr/bin/env python3
# Redesenha, no estilo Windows XP (guia GUI_Xp.pdf), os ícones View Grid e View List *:
# miniaturas azuis, barras de texto cinza, gradiente, contorno escuro, luz no canto superior esquerdo e sombra a 135°.
# Saída: PSD em camadas + PNG 1024. Uso: python3 -I gerar-view.py [Nome ...]   (executar na pasta Icons/xp-icons/NEW)
import importlib.util, os, sys
_e = importlib.util.spec_from_file_location("gl", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gerar-lote.py"))
gl = importlib.util.module_from_spec(_e); _e.loader.exec_module(gl)
retangulo, forma, com_sombra, salvar, R = gl.retangulo, gl.forma, gl.com_sombra, gl.salvar, gl.render_svg
AZ = ("#8cc8ff", "#2a62c0", "#003399"); CZ = ("#ffffff", "#b4b8c4", "#6a6e7c")

DEFS = '''<defs>
<linearGradient id="gAz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8cc8ff"/><stop offset="1" stop-color="#2a62c0"/></linearGradient>
<linearGradient id="gMe" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f2f4fa"/><stop offset="1" stop-color="#8a92a8"/></linearGradient>
<linearGradient id="gEs" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7a8298"/><stop offset="1" stop-color="#2e354a"/></linearGradient>
<radialGradient id="le" cx="0.35" cy="0.3" r="0.9"><stop offset="0" stop-color="#d6ecff"/><stop offset="0.5" stop-color="#3a86e0"/><stop offset="1" stop-color="#0a2f80"/></radialGradient>
<linearGradient id="gVm" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff9e8c"/><stop offset="1" stop-color="#d03020"/></linearGradient>
</defs>'''
def S(corpo): return R(DEFS + corpo)
def F(x0, y0, x1, y1, r, c): return forma(retangulo(x0, y0, x1, y1, r), *c)

ICONES = {}
def icone(nome):
    def d(f): ICONES[nome] = f; return f
    return d

@icone("View Grid")
def _(): return com_sombra([(f"Quadrado {i+1}", F(x, y, x + 400, y + 400, 70, AZ)) for i, (x, y) in enumerate(((90, 90), (534, 90), (90, 534), (534, 534)))])

def linhas(ys, qlado, rq, barras):
    cam = []
    for i, y in enumerate(ys):
        cam.append((f"Miniatura {i+1}", F(90, y, 90 + qlado, y + qlado, rq, AZ)))
        for j, (dy, h, x1) in enumerate(barras[i]):
            cam.append((f"Texto {i+1}.{j+1}", F(90 + qlado + 60, y + dy, x1, y + dy + h, min(36, h // 2), CZ)))
    return com_sombra(cam)

@icone("View List")
def _(): return linhas((110, 410, 710), 200, 40, [[(45, 110, 934)]] * 3)
@icone("View List Compact")
def _(): return linhas((150, 430, 710), 140, 34, [[(35, 70, 934)], [(35, 70, 934)], [(35, 70, 780)]])
@icone("View List Details")
def _(): return linhas((100, 560), 340, 50, [[(40, 110, 934), (200, 90, 720)], [(40, 110, 934), (200, 90, 720)]])
@icone("View List Text")
def _(): return com_sombra([(f"Texto {i+1}", F(90, y, 934, y + 150, 50, CZ)) for i, y in enumerate((140, 440, 740))])

@icone("View List Ordered")
def _():
    def sim(d): return (f'<path d="{d}" fill="none" stroke="#26365a" stroke-width="112" stroke-linecap="round" stroke-linejoin="round"/>'
                        f'<path d="{d}" fill="none" stroke="url(#gAz)" stroke-width="70" stroke-linecap="round" stroke-linejoin="round"/>')
    return com_sombra([("Algarismos", S(sim("M110 260 L180 215 V430") + sim("M110 640 C110 560 260 560 260 640 C260 700 110 760 110 800 H270"))),
                       ("Barra 1", F(380, 200, 934, 350, 50, CZ)), ("Barra 2", F(380, 640, 934, 790, 50, CZ))])

@icone("View List Tree")
def _():
    lig = ('<path d="M240 380 V740 H560 M380 240 H650" fill="none" stroke="#003399" stroke-width="86" stroke-linecap="round" stroke-linejoin="round"/>'
           '<path d="M240 380 V740 H560 M380 240 H650" fill="none" stroke="#4d94f0" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/>')
    return com_sombra([("Ligações", S(lig)), ("Nó 1", F(100, 100, 380, 380, 40, CZ)), ("Nó 2", F(650, 100, 930, 380, 40, CZ)), ("Nó 3", F(560, 600, 930, 930, 40, AZ))])

@icone("View List Images")
def _():
    return com_sombra([("Câmera", S('<rect x="360" y="140" width="300" height="140" rx="40" fill="url(#gEs)" stroke="#1a2038" stroke-width="24"/>'
                                    '<rect x="90" y="230" width="844" height="640" rx="110" fill="url(#gMe)" stroke="#26365a" stroke-width="30"/>'
                                    '<rect x="150" y="290" width="260" height="60" rx="30" fill="#fff" opacity="0.55"/><circle cx="800" cy="360" r="42" fill="url(#gVm)" stroke="#7a1208" stroke-width="16"/>')),
                       ("Lente", S('<circle cx="512" cy="570" r="235" fill="url(#gEs)" stroke="#1a2038" stroke-width="28"/><circle cx="512" cy="570" r="170" fill="url(#le)" stroke="#0a2f80" stroke-width="18"/>'
                                   '<ellipse cx="450" cy="500" rx="70" ry="48" fill="#fff" opacity="0.7" transform="rotate(-30 450 500)"/>'))])

@icone("View List Video")
def _():
    return com_sombra([("Lente", S('<path d="M650 560 L934 340 Q974 316 974 360 V760 Q974 804 934 780 L650 600 Z" fill="url(#gEs)" stroke="#1a2038" stroke-width="28" stroke-linejoin="round"/>')),
                       ("Corpo", S('<rect x="70" y="270" width="640" height="520" rx="100" fill="url(#gAz)" stroke="#003399" stroke-width="30"/>'
                                   '<rect x="130" y="320" width="400" height="70" rx="35" fill="#fff" opacity="0.5"/><circle cx="580" cy="400" r="48" fill="url(#gVm)" stroke="#7a1208" stroke-width="16"/>'))])

if __name__ == "__main__":
    filtro = sys.argv[1:]
    for nome, f in ICONES.items():
        if not filtro or nome in filtro:
            salvar(nome, f())
