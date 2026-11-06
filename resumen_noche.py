"""Resumen de la noche: una pagina web (un solo archivo .html, con los audios dentro) con lo que paso en la
partida: premios, muertes con sus ultimas palabras, preguntas que contesto un bicho (pregunta y respuesta), gritos,
sustos, quien hablo mas y las mejores frases.

Lo genera mirage_vivo.py al cerrar el juego en Mirage/Biblioteca/noches/<fecha>.html, a partir de
Centralizado/Vivo/eventos.jsonl (lo escribe el mod) y resultados.jsonl (lo que entendio Whisper).
Se puede abrir con doble clic y pasar por WhatsApp/Discord: no necesita nada mas.

Uso manual:  python resumen_noche.py    (rehace el de la ultima partida)
"""
import base64
import datetime as dt
import html
import json
import os
import random
import re
import subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))

MONSTRUOS = {
    "Flowerman": "Bracken", "Crawler": "Thumper", "Hoarding bug": "Hoarding bug", "Spring": "Coil-head",
    "Jester": "Jester", "Blob": "Hygrodere", "Centipede": "Snare flea", "Bunker Spider": "Araña",
    "MouthDog": "Perro sin ojos", "ForestGiant": "Gigante", "Masked": "Enmascarado", "Nutcracker": "Cascanueces",
    "Butler": "Mayordomo", "Girl": "Niña fantasma", "Puffer": "Spore lizard", "Baboon hawk": "Baboon hawk",
    "Earth Leviathan": "Gusano gigante", "RadMech": "Old Bird", "Clay Surgeon": "Barber", "Maneater": "Maneater",
}
CAUSAS = {
    "Unknown": "algo desconocido", "Bludgeoning": "a golpes", "Gravity": "una caída", "Blast": "una explosión",
    "Strangulation": "estrangulado", "Suffocation": "asfixiado", "Mauling": "despedazado", "Gunshots": "a tiros",
    "Crushing": "aplastado", "Drowning": "ahogado", "Abandoned": "abandonado en la luna",
    "Electrocution": "electrocutado", "Kicking": "a patadas", "Burning": "quemado", "Stabbing": "apuñalado",
    "Fan": "un ventilador", "Inertia": "un choque", "Snipped": "cortado en dos",
}
SUSTOS = [
    ("imita", "Monstruos que imitaron una voz"), ("respuesta", "Preguntas contestadas por algo que no era humano"),
    ("solo", "Susurros a quien estaba solo"), ("ultimas", "Últimas palabras repetidas"),
    ("cadaver", "Cadáveres que susurraron"), ("walkie", "Walkies falsos"), ("puerta", "Voces tras una puerta"),
    ("altavoz", "Muertos por el altavoz de la nave"), ("bracken", "Frases del Bracken"),
    ("bracken_enfado", "Veces que se enfadó el Bracken"),
]


def leer_jsonl(ruta):
    out = []
    try:
        with open(ruta, encoding="utf-8-sig") as f:  # el mod (C#) escribe una marca BOM al principio
            for linea in f:
                try:
                    out.append(json.loads(linea))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def audio_b64(ruta):
    """El audio en opus pequeño, dentro de la pagina (asi se puede compartir sin mas archivos)."""
    if not ruta or not os.path.exists(ruta):
        return None
    r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "fatal", "-i", ruta, "-t", "8", "-ac", "1", "-ar", "48000",
                        "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", "-"], capture_output=True)
    return base64.b64encode(r.stdout).decode() if r.returncode == 0 and r.stdout else None


def tramo_seguido(frases, desde, hasta):
    """Un solo audio de 'desde' a 'hasta' (en segundos de reloj) con las frases de una persona colocadas en su
    momento exacto y silencio entre medias: se oye tal cual paso, de seguido. Devuelve el base64 o None."""
    import numpy as np
    from respuestas import cargar_audio
    sr = 24000
    pista = np.zeros(int((hasta - desde) * sr), dtype=np.float32)
    puesto = False
    for inicio, ruta in frases:
        audio = cargar_audio(ruta, sr)
        a = int((inicio - desde) * sr)
        b0 = max(0, -a)                         # si empezo antes de la ventana, se corta el principio
        a = max(0, a)
        n = min(len(audio) - b0, len(pista) - a)
        if n > 0:
            pista[a:a + n] += audio[b0:b0 + n]
            puesto = True
    if not puesto:
        return None
    pista = np.clip(pista, -1, 1)
    r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "fatal", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                        "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", "-"], input=pista.tobytes(), capture_output=True)
    return base64.b64encode(r.stdout).decode() if r.returncode == 0 and r.stdout else None


def reproductor(ruta):
    b = audio_b64(ruta)
    return f'<audio controls preload="none" src="data:audio/ogg;base64,{b}"></audio>' if b else ""


def esc(t):
    return html.escape(str(t or ""))


def generar(mirage_dir, nombres=None, salida=None):
    """Crea la pagina y devuelve su ruta (o None si no hubo partida)."""
    vivo = os.path.join(mirage_dir, "Centralizado", "Vivo")
    eventos = [e for e in leer_jsonl(os.path.join(vivo, "eventos.jsonl")) if e.get("tipo") != "invocacion"]
    # tarde.jsonl: lo que se entendio cuando ya era tarde para reaccionar (partidas con mucha gente)
    todas = leer_jsonl(os.path.join(vivo, "resultados.jsonl")) + leer_jsonl(os.path.join(vivo, "tarde.jsonl"))
    todas.sort(key=lambda f: f.get("inicio") or f.get("t", 0))
    frases = [f for f in todas if f.get("texto")]
    if not eventos and not todas:
        return None
    nombre = (lambda j: (nombres or {}).get(j, j))
    tiempos = [e["t"] for e in eventos] + [f["t"] for f in todas]
    ini, fin = dt.datetime.fromtimestamp(min(tiempos)), dt.datetime.fromtimestamp(max(tiempos))
    lunas = [e.get("detalle") for e in eventos if e["tipo"] == "luna"]
    # partidas anteriores a la 0.6.0 no apuntaban muertes ni lunas
    con_diario = any(e["tipo"] in ("luna", "muerte", "despegue") for e in eventos)
    jugadores = sorted({nombre(f["jugador"]) for f in frases} | {nombre(e["jugador"]) for e in eventos if e.get("jugador")})

    def audio_de(f):
        """El audio de una frase: la copia de la sesion (todo lo dicho) o, si no, la frase guardada."""
        for ruta in (f.get("audio"), os.path.join(mirage_dir, f["activa"]) if f.get("activa") else None):
            if ruta and os.path.exists(ruta):
                return ruta
        return None

    def hora(f):
        """Cuando se dijo (no cuando Whisper termino de escribirlo)."""
        return f.get("inicio") or f["t"]

    def basura(f):
        """Whisper no sabe escribir un grito: lo deja vacio, pone "¡¡¡¡¡", "¡Suscribete!" o letras en bucle."""
        t = (f.get("texto") or "").strip()
        letras = re.sub(r"[^a-zñáéíóú]", "", t.lower())
        return (not letras or "suscr" in letras or "subtitul" in letras
                or len(set(letras)) <= 3 and len(letras) > 6)

    def mostrar(f):
        return "(grito)" if basura(f) else f["texto"]

    def de(f, quien):
        return nombre(f["jugador"]) == nombre(quien)

    def limpia(f):
        """Fuera lo que Whisper se inventa: 'jajajaja' de 300 letras o la misma palabra en bucle."""
        w = f["texto"].split()
        return w and max(len(x) for x in w) <= 20 and len(set(x.lower() for x in w)) > len(w) / 2

    # ---- muertes: las ultimas 3 cosas que dijo, la ultima con audio ----
    muertes = []
    for e in (e for e in eventos if e["tipo"] == "muerte"):
        quien = e.get("jugador")
        antes = [f for f in frases if de(f, quien) and e["t"] - 90 <= hora(f) <= e["t"] + 5 and limpia(f)][-1:]
        # Lo que dijo el que muere de 10 s antes a 5 s despues (si una frase empezo antes, entra su final).
        charla = sorted((f for f in todas if de(f, quien) and audio_de(f)
                         and hora(f) + (f.get("dur") or 0) >= e["t"] - 10 and hora(f) <= e["t"] + 5), key=hora)
        luna = next((l.get("detalle") for l in reversed(eventos) if l["tipo"] == "luna" and l["t"] <= e["t"]), "")
        killer = MONSTRUOS.get(e.get("otro"), e.get("otro"))
        causa = CAUSAS.get(e.get("detalle"), e.get("detalle") or "")
        muertes.append((quien, luna, killer, causa, antes, e["t"], charla))

    # ---- quien hablo mas ----
    habla = {}
    for f in frases:
        habla[nombre(f["jugador"])] = habla.get(nombre(f["jugador"]), 0) + 1
    maximo = max(habla.values(), default=1)

    # ---- sustos ----
    cuenta = {t: sum(1 for e in eventos if e["tipo"] == t) for t, _ in SUSTOS}

    # ---- respuestas: la pregunta (con su audio) y lo que contesto el bicho ----
    respuestas = []
    for e in (e for e in eventos if e["tipo"] == "respuesta"):
        texto_pregunta, _, como = (e.get("detalle") or "").partition(" -> ")
        preg = [f for f in frases if de(f, e.get("otro")) and e["t"] - 40 <= f["t"] <= e["t"] + 2]
        exacta = [f for f in preg if f["texto"].strip() == texto_pregunta.strip()]
        pregunta = (exacta or preg[-1:] or [None])[-1]
        respuestas.append((e, texto_pregunta, como, pregunta))
    respuestas = respuestas[:8]
    susurros = [e for e in eventos if e["tipo"] == "solo"][:4]

    # ---- gritos: casi siempre es que algo ha asustado a alguien ----
    def es_grito(f):
        """Un grito de verdad: corto, con "¡...!" o un "aaah", no una frase que dice "no ayuda" de pasada."""
        texto = f["texto"]
        n = texto.lower()
        palabras = n.split()
        if not palabras or len(palabras) > 8:
            return False
        if re.search(r"\b(a{3,}h*|ah{2,}|a+y{2,}|ay ay|socorro|madre m[ií]a|mami|qu[eé] miedo|qu[eé] susto)\b", n):
            return True
        exclama = "!" in texto
        if exclama and re.search(r"\b(ayuda|ay[uú]dame|ayudadme|corre+|corred|huye|huid|s[aá]came|cuidado)\b", n):
            return True
        return exclama and len(palabras) <= 4 and re.search(r"\b(joder|hostia|hoscias|ostia|dios|mierda|no no|oh|uh|uy|ay)\b", n) is not None

    def contexto(f):
        """Que paso cerca de ese grito (20 s antes o despues)."""
        cerca = [e for e in eventos if abs(e["t"] - hora(f)) <= 20]
        for e in cerca:
            if e["tipo"] == "muerte" and de(f, e.get("jugador")):
                return "justo antes de morir" if e["t"] >= hora(f) else "al morir"
        textos = {
            "muerte": lambda e: f"cuando murió {nombre(e.get('jugador'))}",
            "respuesta": lambda e: f"después de que le contestara algo con la voz de {nombre(e.get('jugador'))}",
            "solo": lambda e: "solo, oyendo una voz",
            "imita": lambda e: f"con un {MONSTRUOS.get(e.get('detalle'), e.get('detalle'))} imitando a {nombre(e.get('jugador'))} cerca",
            "puerta": lambda e: "con una voz detrás de la puerta",
            "walkie": lambda e: "con una voz por el walkie",
            "cadaver": lambda e: "con un cadáver susurrando",
            "bracken": lambda e: "con el Bracken encima",
            "bracken_enfado": lambda e: "con el Bracken persiguiéndole",
        }
        for e in sorted(cerca, key=lambda e: abs(e["t"] - hora(f))):
            if e["tipo"] in textos:
                return textos[e["tipo"]](e)
        return ""

    def pico(f):
        return f.get("vol_pico", f.get("vol_media"))

    volumenes = {}
    for f in todas:
        if pico(f) is not None:
            volumenes.setdefault(nombre(f["jugador"]), []).append(pico(f))
    normal = {j: sorted(v)[len(v) // 2] for j, v in volumenes.items() if len(v) >= 5}

    def fuerte(f):
        """Su medio segundo mas fuerte supera en 6 dB a lo normal en esa persona (cada micro es distinto)."""
        base = normal.get(nombre(f["jugador"]))
        if base is None or pico(f) is None or pico(f) < base + 6 or (f.get("dur") or 0) > 10:
            return False
        # Fuerte no basta: "¡HOLA!" o "prueba de voces" a voces no son sustos.
        texto = (f.get("texto") or "").lower()
        if re.search(r"\b(hola|voces|prueba|vale|venga|vamos|adi[oó]s)\b", texto):
            return False
        return basura(f) or "!" in texto or len(texto.split()) <= 2

    gritos = [f for f in todas if audio_de(f) and ((f.get("texto") and es_grito(f) and limpia(f)) or fuerte(f))]
    por_gritos = {}
    for f in gritos:
        por_gritos[nombre(f["jugador"])] = por_gritos.get(nombre(f["jugador"]), 0) + 1
    # primero los que pasaron con algo alrededor
    gritos = sorted(gritos, key=lambda f: (contexto(f) == "", -(pico(f) or -99)))[:15]
    gritos.sort(key=hora)

    # ---- frases de la noche ----
    rnd = random.Random(int(min(tiempos)))
    candidatas = [f for f in frases if f.get("guardada") and 3 <= len(f["texto"].split()) <= 18 and limpia(f)
                  and audio_de(f) and f not in gritos]
    destacadas = [f for f in candidatas if set(f.get("categorias") or []) & {"risa", "ayuda", "nombre"}]
    resto = [f for f in candidatas if f not in destacadas]
    rnd.shuffle(destacadas)
    rnd.shuffle(resto)
    mejores = (destacadas + resto)[:6]

    # ---- premios ----
    premios = []
    if habla:
        j, n = max(habla.items(), key=lambda x: x[1])
        premios.append(("🗣️", "El más hablador", j, f"{n} frase" + ("s" if n != 1 else "")))
    if por_gritos:
        j, n = max(por_gritos.items(), key=lambda x: x[1])
        premios.append(("😱", "El más asustadizo", j, f"{n} grito" + ("s" if n != 1 else "")))
    if muertes:
        primero = min(muertes, key=lambda m: m[5])
        premios.append(("⚰️", "Primero en caer", nombre(primero[0]), primero[2] or primero[3]))
        veces = {}
        for m in muertes:
            veces[nombre(m[0])] = veces.get(nombre(m[0]), 0) + 1
        j, n = max(veces.items(), key=lambda x: x[1])
        if n > 1:
            premios.append(("💀", "Más veces muerto", j, f"{n} veces"))
    if con_diario:
        vivos = [j for j in jugadores if j not in {nombre(m[0]) for m in muertes}]
        if vivos:
            premios.append(("🛡️", "Superviviente", ", ".join(vivos), "no murió en toda la noche"))

    # ---------------- HTML ----------------
    h = []
    h.append(f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Noche del {ini:%d/%m}</title>
<style>
:root{{--bg:#0b0d0c;--card:#141816;--line:#232a26;--txt:#e7ece9;--dim:#8d9a93;--acc:#c8ff5a;--red:#ff5a5a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font:16px/1.5 system-ui,Segoe UI,sans-serif}}
main{{max-width:860px;margin:0 auto;padding:28px 16px 60px}}
h1{{font-size:30px;margin:0 0 4px;letter-spacing:.5px}}.sub{{color:var(--dim);margin:0 0 24px}}
h2{{font-size:15px;text-transform:uppercase;letter-spacing:2px;color:var(--acc);margin:32px 0 12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}}
.row{{display:flex;gap:12px;align-items:center;flex-wrap:wrap}}.dim{{color:var(--dim)}}.red{{color:var(--red)}}
.chips span{{display:inline-block;background:#1c2420;border:1px solid var(--line);border-radius:99px;padding:2px 10px;margin:2px 4px 2px 0;font-size:14px}}
.bar{{height:10px;background:var(--acc);border-radius:99px;opacity:.85}}.barbox{{flex:1;min-width:120px;background:#1c2420;border-radius:99px}}
.who{{width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}}
.num{{font-size:28px;font-weight:700;color:var(--acc)}}q{{font-style:italic}}audio{{height:32px;max-width:100%}}
.dialog{{display:grid;grid-template-columns:auto 1fr;gap:6px 12px;align-items:center;margin-top:8px}}
.tag{{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--dim)}}.bicho{{color:var(--red)}}
.premio .ico{{font-size:26px}}.premio b{{display:block}}
footer{{color:var(--dim);font-size:13px;margin-top:40px;text-align:center}}
.muerte-audio{{margin-top:10px;display:grid;gap:4px;max-width:420px}}.muerte-audio audio{{width:100%}}
.linea{{position:relative;height:6px;background:#1c2420;border-radius:99px}}
.linea span{{position:absolute;top:-3px;width:3px;height:12px;background:var(--red);border-radius:2px}}
button.seguido{{margin:8px 0;background:var(--acc);color:#0b0d0c;border:0;border-radius:99px;padding:4px 14px;font-weight:600;cursor:pointer}}
</style>
<script>
function seguido(btn){{
  const audios=[...btn.parentElement.querySelectorAll('audio')];
  audios.forEach(a=>{{a.pause();a.currentTime=0;a.onended=null}});
  audios.forEach((a,i)=>{{a.onended=()=>audios[i+1]&&audios[i+1].play()}});
  audios[0]&&audios[0].play();
}}
</script></head><body><main>
<h1>🌙 Noche del {ini:%d/%m/%Y}</h1>
<p class="sub">{len(jugadores)} jugadores{f" · {len(lunas)} lunas" if lunas else ""} · {ini:%H:%M}–{fin:%H:%M} ({int((fin - ini).total_seconds() // 60)} min)</p>
<div class="chips">{''.join(f'<span>{esc(j)}</span>' for j in jugadores)}</div>""")
    if lunas:
        h.append(f'<div class="chips" style="margin-top:6px">{"".join(f"<span>🪐 {esc(l)}</span>" for l in lunas)}</div>')

    if premios:
        h.append("<h2>🏆 Premios de la noche</h2><div class='grid'>")
        for ico, titulo, quien, extra in premios:
            h.append(f'<div class="card premio"><span class="ico">{ico}</span><b>{esc(titulo)}</b>{esc(quien)} '
                     f'<span class="dim">· {esc(extra)}</span></div>')
        h.append("</div>")

    h.append("<h2>💀 Muertes</h2>")
    if not con_diario:
        h.append('<div class="card dim">Esta partida es de antes de que el mod apuntara las muertes: '
                 'a partir de ahora saldrán aquí, con sus últimas palabras.</div>')
    elif not muertes:
        h.append('<div class="card dim">Nadie murió. Sospechoso.</div>')
    for quien, luna, killer, causa, antes, t_muerte, charla in muertes:
        como = esc(killer) if killer else esc(causa)
        h.append(f'<div class="card"><div class="row"><b class="red">{esc(nombre(quien))}</b>'
                 f'<span class="dim">{esc(luna)} · {como}</span></div>')
        if antes:
            h.append(f'<div class="dialog"><span class="tag">últimas palabras</span><div class="row">'
                     f'<q>{esc(antes[0]["texto"])}</q></div></div>')
        tramo = tramo_seguido([(hora(f), audio_de(f)) for f in charla], t_muerte - 10, t_muerte + 5) if charla else None
        if tramo:
            h.append(f'<div class="muerte-audio"><span class="tag">🎧 10 s antes · muere · 5 s después</span>'
                     f'<audio controls preload="none" src="data:audio/ogg;base64,{tramo}"></audio>'
                     f'<div class="linea"><span style="left:66.7%"></span></div></div>')
        h.append("</div>")

    if respuestas or susurros:
        h.append("<h2>👂 Le contestó algo que no era humano</h2>")
        for e, texto_pregunta, como, pregunta in respuestas:
            voz = nombre(e.get("jugador"))
            h.append(f'<div class="card"><div class="dialog">'
                     f'<span class="tag">{esc(nombre(e.get("otro")))}</span><div class="row"><q>{esc(texto_pregunta)}</q>'
                     f'{reproductor(audio_de(pregunta)) if pregunta else ""}</div>'
                     f'<span class="tag bicho">«{esc(voz)}»</span><div class="row">{reproductor(e.get("archivo"))}'
                     f'<span class="dim">{esc(como)}… pero no era {esc(voz)}</span></div></div></div>')
        for e in susurros:
            h.append(f'<div class="card"><b>{esc(nombre(e.get("jugador")))}</b> se quedó solo y oyó una voz: la de '
                     f'<b>{esc(nombre(e.get("otro")))}</b>.<div style="margin-top:6px">{reproductor(e.get("archivo"))}</div></div>')

    if gritos:
        h.append("<h2>😱 Gritos de la noche</h2>")
        for f in gritos:
            ctx = contexto(f)
            h.append(f'<div class="card"><div class="row"><b>{esc(nombre(f["jugador"]))}</b><q>{esc(mostrar(f))}</q></div>'
                     f'{f"<div class=dim>{esc(ctx)}</div>" if ctx else ""}'
                     f'<div style="margin-top:6px">{reproductor(audio_de(f))}</div></div>')

    activos = [(t, txt) for t, txt in SUSTOS if cuenta[t]]
    if activos:
        h.append("<h2>🎃 Sustos que saltaron</h2>")
        h.append('<div class="grid">' + "".join(f'<div class="card"><div class="num">{cuenta[t]}</div>{esc(txt)}</div>'
                                                for t, txt in activos) + "</div>")

    h.append("<h2>🗣️ Quién habló más</h2><div class='card'>")
    for j, n in sorted(habla.items(), key=lambda x: -x[1]):
        h.append(f'<div class="row" style="margin:6px 0"><span class="who">{esc(j)}</span><div class="barbox">'
                 f'<div class="bar" style="width:{100 * n / maximo:.0f}%"></div></div><span class="dim">{n}</span></div>')
    h.append("</div>")

    if mejores:
        h.append("<h2>💬 Frases de la noche</h2>")
        for f in mejores:
            h.append(f'<div class="card"><div class="row"><b>{esc(nombre(f["jugador"]))}</b><q>{esc(f["texto"])}</q></div>'
                     f'<div style="margin-top:6px">{reproductor(audio_de(f))}</div></div>')

    h.append(f'<footer>MirageVoces · generado el {dt.datetime.now():%d/%m/%Y %H:%M}</footer></main></body></html>')

    carpeta = os.path.join(mirage_dir, "Biblioteca", "noches")
    os.makedirs(carpeta, exist_ok=True)
    salida = salida or os.path.join(carpeta, f"{ini:%Y-%m-%d_%H%M}.html")
    with open(salida, "w", encoding="utf-8") as fh:
        fh.write("\n".join(h))
    return salida


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with open(os.path.join(AQUI, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    mirage = os.path.join(cfg["carpeta_juego"], "Mirage")
    try:
        with open(os.path.join(mirage, "Centralizado", "jugadores.json"), encoding="utf-8") as f:
            nombres = json.load(f)
    except (OSError, ValueError):
        nombres = {}
    nombres["Tu"] = cfg.get("mi_nombre_steam", "Tu")
    print(generar(mirage, nombres) or "No hay datos de ninguna partida.")
