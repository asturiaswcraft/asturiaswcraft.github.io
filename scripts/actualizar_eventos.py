#!/usr/bin/env python3
"""Actualiza la sección "Últimos eventos" de index.html con los eventos de Saraos.

- Lee la página de la comunidad en saraos.tech y la de cada evento.
- Se queda con los 4 eventos más recientes (los próximos incluidos).
- Descarga los carteles a assets/eventos/ (redimensionados a webp si hay Pillow).
- Reescribe el bloque entre <!-- EVENTOS:INICIO --> y <!-- EVENTOS:FIN -->.

Si algo falla al leer Saraos, termina con error sin tocar ningún fichero.
Solo usa la librería estándar; Pillow es opcional.
"""

from __future__ import annotations

import html
import io
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "https://saraos.tech"
COMUNIDAD = "/@asturias-software-crafters"
LISTADOS = [COMUNIDAD, COMUNIDAD + "/events"]
NUM_EVENTOS = 4
MIN_EVENTOS = 2
ANCHO_CARTEL = 1600
UA = "Mozilla/5.0 (compatible; asc-web-eventos/1.0)"

RAIZ = Path(__file__).resolve().parent.parent
INDEX = RAIZ / "index.html"
DIR_CARTELES = RAIZ / "assets" / "eventos"
INICIO, FIN = "<!-- EVENTOS:INICIO -->", "<!-- EVENTOS:FIN -->"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
# Respaldo por código postal si la dirección no trae la ciudad
CP_CIUDAD = {"330": "Oviedo", "332": "Gijón", "334": "Avilés"}


@dataclass
class Evento:
    url: str
    titulo: str
    fecha: date
    ciudad: str
    cartel_url: str
    cartel_fichero: str = ""


def descargar(url: str, intentos: int = 4) -> tuple[bytes, str]:
    """Descarga con pausa entre peticiones y reintentos si el servidor falla."""
    for n in range(intentos):
        time.sleep(1.5 if n == 0 else 15 * n)  # amables con Saraos
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            codigo = getattr(exc, "code", None)
            if codigo and codigo < 500 and codigo != 429:
                raise
            print(f"Aviso: {url} falló ({exc}); reintento {n + 1}/{intentos - 1}", file=sys.stderr)
    raise RuntimeError(f"No se pudo descargar {url} tras {intentos} intentos")


def texto(url: str) -> str:
    datos, _ = descargar(url)
    return datos.decode("utf-8", "replace")


def lineas_visibles(pagina: str) -> list[str]:
    sin_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", pagina, flags=re.S)
    plano = html.unescape(re.sub(r"<[^>]+>", "\n", sin_scripts))
    return [l.strip() for l in plano.split("\n") if l.strip()]


def meta(pagina: str, prop: str) -> str:
    m = re.search(rf'property="{re.escape(prop)}" content="([^"]*)"', pagina)
    return html.unescape(m.group(1)) if m else ""


def limpiar_titulo(titulo: str) -> str:
    # "{ASC} - noviembre: Título [Charla]" -> "Título"
    if ":" in titulo and re.match(r"^\s*(\{ASC\}|Asturias Software Crafters)", titulo):
        titulo = titulo.split(":", 1)[1]
    anterior = None
    while anterior != titulo:
        anterior = titulo
        titulo = re.sub(r"\s*(\[[^\]]*\]|\([^)]*\))\s*$", "", titulo).strip()
    return re.sub(r"\s+", " ", titulo)


def inferir_fecha(dia: int, mes: int, anio: int | None, hoy: date) -> date:
    if anio:
        return date(anio, mes, dia)
    # Saraos no muestra el año: elegimos el que deja la fecha entre
    # 300 días antes y 120 días después de hoy.
    for a in (hoy.year, hoy.year - 1, hoy.year + 1):
        f = date(a, mes, dia)
        if hoy - timedelta(days=300) <= f <= hoy + timedelta(days=120):
            return f
    return date(hoy.year, mes, dia)


def ciudad_de(direccion: str, lugar: str) -> str:
    for c in ("Gijón", "Oviedo", "Avilés", "Mieres", "Langreo", "Siero"):
        if c.lower() in (direccion + " " + lugar).lower():
            return c
    m = re.search(r"\b(\d{5})\s+([^,]+)", direccion)
    if m:
        return m.group(2).strip()
    m = re.search(r"\b(\d{3})\d{2}\b", direccion)
    if m and m.group(1) in CP_CIUDAD:
        return CP_CIUDAD[m.group(1)]
    return "Asturias"


def leer_evento(ruta: str, hoy: date) -> Evento:
    url = BASE + ruta
    pagina = texto(url)
    lineas = lineas_visibles(pagina)

    i = lineas.index("¿Cuándo?")
    m = re.search(r"(\d{1,2}) de ([a-záéíóú]+)(?: de (\d{4}))?", lineas[i + 1].lower())
    if not m or m.group(2) not in MESES:
        raise ValueError(f"No entiendo la fecha de {url}: {lineas[i + 1]!r}")
    fecha = inferir_fecha(int(m.group(1)), MESES[m.group(2)], int(m.group(3)) if m.group(3) else None, hoy)

    j = lineas.index("¿Dónde?", i)
    lugar, direccion = lineas[j + 1], lineas[j + 2]

    titulo = limpiar_titulo(meta(pagina, "og:title"))
    if not titulo:
        raise ValueError(f"Evento sin título: {url}")

    cartel = meta(pagina, "og:image")
    if "/featured-image" not in cartel:
        # Sin imagen destacada: probamos con la primera imagen de la descripción
        for src in re.findall(r'<img[^>]+src="([^"]+)"', pagina):
            if "/avatar" not in src and not src.startswith("data:"):
                cartel = html.unescape(src)
                break
    if cartel.startswith("/"):
        cartel = BASE + cartel

    return Evento(url, titulo, fecha, ciudad_de(direccion, lugar), cartel)


def guardar_cartel(ev: Evento) -> None:
    datos, tipo = descargar(ev.cartel_url)
    base = ev.fecha.isoformat()
    try:
        from PIL import Image  # opcional

        img = Image.open(io.BytesIO(datos)).convert("RGB")
        if img.width > ANCHO_CARTEL:
            img = img.resize((ANCHO_CARTEL, round(img.height * ANCHO_CARTEL / img.width)), Image.LANCZOS)
        salida = io.BytesIO()
        img.save(salida, "WEBP", quality=80)
        datos, ext = salida.getvalue(), "webp"
    except ImportError:
        ext = {"image/webp": "webp", "image/png": "png", "image/jpeg": "jpg"}.get(tipo.split(";")[0], "jpg")
    ev.cartel_fichero = f"{base}.{ext}"
    ev._datos = datos  # se escribe al final, solo si todo ha ido bien


def tarjeta(ev: Evento, hoy: date) -> str:
    fecha = f"{ev.fecha.day} {MESES_CORTOS[ev.fecha.month - 1]} {ev.fecha.year}"
    prefijo = "Próximo · " if ev.fecha >= hoy else ""
    e = html.escape
    return (
        f'        <a class="event" href="{e(ev.url)}" target="_blank" rel="noopener">\n'
        f'          <img src="assets/eventos/{e(ev.cartel_fichero)}" alt="Cartel: {e(ev.titulo)}" loading="lazy" width="1600" height="900">\n'
        f'          <div class="event__body">\n'
        f'            <p class="event__meta">{prefijo}{fecha} · 📍 {e(ev.ciudad)}</p>\n'
        f'            <h3>{e(ev.titulo)}</h3>\n'
        f'          </div>\n'
        f'        </a>\n'
    )


def main() -> int:
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()

    rutas: list[str] = []
    for listado in LISTADOS:
        for r in re.findall(rf'href="({re.escape(COMUNIDAD)}/events/[^"/?#]+)"', texto(BASE + listado)):
            if r not in rutas:
                rutas.append(r)
    if not rutas:
        print("No se encontraron eventos en Saraos; no se cambia nada.", file=sys.stderr)
        return 1

    eventos = []
    for r in rutas[: NUM_EVENTOS * 3]:
        try:
            eventos.append(leer_evento(r, hoy))
        except Exception as exc:  # un evento raro no debe tumbar el resto
            print(f"Aviso: se omite {r}: {exc}", file=sys.stderr)
    eventos.sort(key=lambda ev: ev.fecha, reverse=True)
    eventos = eventos[:NUM_EVENTOS]
    if len(eventos) < MIN_EVENTOS:
        print(f"Solo se leyeron {len(eventos)} eventos; no se cambia nada.", file=sys.stderr)
        return 1

    for ev in eventos:
        guardar_cartel(ev)

    index = INDEX.read_text(encoding="utf-8")
    if INICIO not in index or FIN not in index:
        print("Faltan los marcadores EVENTOS en index.html.", file=sys.stderr)
        return 1
    a, resto = index.split(INICIO, 1)
    _, b = resto.split(FIN, 1)
    bloque = INICIO + "\n" + "".join(tarjeta(ev, hoy) for ev in eventos) + "        " + FIN
    nuevo = a + bloque + b

    # Escribimos solo al final, cuando todo ha ido bien
    DIR_CARTELES.mkdir(parents=True, exist_ok=True)
    usados = {ev.cartel_fichero for ev in eventos}
    for ev in eventos:
        destino = DIR_CARTELES / ev.cartel_fichero
        if not destino.exists() or destino.read_bytes() != ev._datos:
            destino.write_bytes(ev._datos)
    for f in DIR_CARTELES.iterdir():
        if f.is_file() and f.name not in usados:
            f.unlink()
    if nuevo != index:
        INDEX.write_text(nuevo, encoding="utf-8")

    for ev in eventos:
        print(f"{ev.fecha} · {ev.ciudad} · {ev.titulo} -> {ev.cartel_fichero}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Error: {exc}. No se ha cambiado nada.", file=sys.stderr)
        sys.exit(1)
