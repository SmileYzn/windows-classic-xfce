#!/usr/bin/env python3
# Funções comuns dos geradores de ícones no estilo Windows XP (guia GUI_Xp.pdf): formas com gradiente e contorno,
# sombra projetada a 135°, atalhos para colar ícones da galeria (Icons/xp-icons/1024x1024) e gravar PSD em camadas + PNG 1024.
# Os geradores (gerar-*.py) importam este arquivo da própria pasta.
import io, subprocess
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

GAL = "../1024x1024/"      # galeria XP, relativa à pasta NEW (onde os geradores são executados)
T = (1024, 1024)

def ref(nome):
    return Image.open(GAL + nome + ".png").convert("RGBA")

def salvar(nome, camadas):
    psd = PSDImage.new("RGB", T); comp = Image.new("RGBA", T, (0, 0, 0, 0))
    for n, im in camadas:
        psd.append(PixelLayer.frompil(im, psd, n)); comp = Image.alpha_composite(comp, im)
    psd.save(nome + ".psd"); comp.save(nome + ".png"); print(nome)

def colar(img, x, y, w, h=None):
    """Reduz img (recortada no conteúdo) para caber em w x h e posiciona em (x, y)."""
    img = img.crop(img.getbbox()); h = h or w
    k = min(w / img.width, h / img.height)
    img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
    out = Image.new("RGBA", T, (0, 0, 0, 0))
    out.paste(img, (x + (w - img.width) // 2, y + (h - img.height) // 2), img)
    return out

def render_svg(corpo):
    s = '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">%s</svg>' % corpo
    png = subprocess.run(["rsvg-convert", "-w", "1024", "-h", "1024"], input=s.encode(), capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(png)).convert("RGBA")

def sombra(img, dx=26, dy=26, desfoque=14, op=0.55):
    a = img.getchannel("A").point(lambda v: int(v * op)).filter(ImageFilter.GaussianBlur(desfoque))
    d = Image.new("L", T, 0); d.paste(a, (dx, dy)); a = d      # desloca sem dar a volta nas bordas
    s = Image.new("RGBA", T, (0, 0, 0, 0)); s.putalpha(a); return s

def com_sombra(camadas):
    comp = Image.new("RGBA", T, (0, 0, 0, 0))
    for _, im in camadas:
        comp = Image.alpha_composite(comp, im)
    return [("Sombra", sombra(comp))] + camadas

def mascara(desenhar):
    m = Image.new("L", (2048, 2048), 0); d = ImageDraw.Draw(m); desenhar(d, 2)
    return m.resize(T, Image.LANCZOS)

def retangulo(x0, y0, x1, y1, r):
    return mascara(lambda d, k: d.rounded_rectangle([x0*k, y0*k, x1*k, y1*k], radius=r*k, fill=255))

def circulo(cx, cy, r):
    return mascara(lambda d, k: d.ellipse([(cx-r)*k, (cy-r)*k, (cx+r)*k, (cy+r)*k], fill=255))

def hex2rgb(h):
    return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))

def forma(m, topo, base, contorno, brilho=True, esp=16):
    """Preenche a máscara com degradê vertical, faixa de luz no topo e contorno."""
    y0, y1 = m.getbbox()[1], m.getbbox()[3]
    t = np.clip((np.arange(1024)[:, None, None] - y0) / max(1, y1 - y0), 0, 1)
    c0, c1 = np.array(hex2rgb(topo)), np.array(hex2rgb(base))
    cor = (c0 * (1 - t) + c1 * t) * np.ones((1, 1024, 1))
    fill = Image.fromarray(cor.astype("uint8"), "RGB").convert("RGBA"); fill.putalpha(m)
    if brilho:
        gl = Image.new("L", T, 0); d = ImageDraw.Draw(gl)
        for i in range(60):
            yy = y0 + i * (y1 - y0) * 0.5 / 60
            d.line([(0, yy), (1024, yy)], fill=int(95 * (1 - i / 60)))
        luz = Image.new("RGBA", T, (255, 255, 255, 0)); luz.putalpha(ImageChops.multiply(gl, m))
        fill = Image.alpha_composite(fill, luz)
    anel = ImageChops.subtract(m.filter(ImageFilter.MaxFilter(esp * 2 + 1)), m)
    borda = Image.new("RGBA", T, hex2rgb(contorno) + (0,)); borda.putalpha(anel)
    return Image.alpha_composite(borda, fill)
