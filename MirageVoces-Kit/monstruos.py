"""Voces propias para un monstruo: el Bracken habla con TU voz segun lo que esta haciendo.

Mete los audios en Mirage/Importar/Bracken/<momento>/ (o sueltos en Importar/Bracken/ con el
momento al principio del nombre, p. ej. "persecucion 1.m4a"). Momentos:
  acecho       te sigue por detras sin que le veas (susurros)
  pillado      le has visto y se esconde
  persecucion  se enfada y va a por ti
  muerte       te mata
  arrastre     se lleva tu cadaver
Un audio corto (hasta 8 s) es una frase; uno largo con varias frases separadas por silencios se parte solo.
Quedan en Centralizado/Monstruos/Bracken/<momento>/*.wav (16 kHz); el mod las usa desde ahi.
"""
import os
import re
import subprocess

MONSTRUOS = {"bracken": "Bracken"}
MOMENTOS = {
    "acecho": ["acecho", "acechar", "seguimiento", "sigilo", "susurro", "susurros"],
    "pillado": ["pillado", "pillar", "visto", "descubierto", "huida"],
    "persecucion": ["persecucion", "perseguir", "enfadado", "enfado", "ataque", "caza"],
    "muerte": ["muerte", "matar", "asesinato", "mata", "kill"],
    "arrastre": ["arrastre", "arrastrar", "cadaver", "llevar"],
}


def momento_de(nombre, normalizar):
    n = normalizar(nombre)
    for momento, palabras in MOMENTOS.items():
        if any(n == p or n.startswith(p + " ") or n.startswith(p) for p in palabras):
            return momento
    return None


def trozos_por_silencio(src, minimo=0.4):
    """Tramos con voz de un audio, separados por silencios de 0,6 s o mas."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", src, "-af", "silencedetect=noise=-35dB:d=0.6", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    total = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)) if dur else None
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    finales = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    tramos, t = [], 0.0
    for a, b in zip(inicios, finales + [None] * (len(inicios) - len(finales))):
        if a - t >= minimo:
            tramos.append((max(0, t - 0.1), a + 0.15))
        t = b if b is not None else (total or a)
    if total and total - t >= minimo:
        tramos.append((max(0, t - 0.1), total))
    return tramos or [(0, total)]


def duracion(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def importar_monstruos(curador, normalizar):
    """Importa Importar/<Monstruo>/... Devuelve {monstruo: {momento: frases nuevas}}."""
    hechos = {}
    for carpeta in sorted(os.listdir(curador.imp)):
        monstruo = MONSTRUOS.get(normalizar(carpeta))
        ruta = os.path.join(curador.imp, carpeta)
        if not monstruo or not os.path.isdir(ruta):
            continue
        archivos = []
        for raiz, _, fs in os.walk(ruta):
            for f in sorted(fs):
                if f.lower().endswith((".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".webm")):
                    sub = os.path.relpath(raiz, ruta)
                    momento = momento_de(sub, normalizar) if sub != "." else None
                    archivos.append((os.path.join(raiz, f), momento or momento_de(os.path.splitext(f)[0], normalizar)))
        for src, momento in archivos:
            rel = os.path.relpath(src, curador.imp)
            if momento is None:
                print(f"¡OJO! {rel}: no sé de qué momento es. Ponlo en una carpeta "
                      f"({', '.join(MOMENTOS)}) dentro de Importar\\{carpeta}.")
                continue
            destino = os.path.join(curador.central, "Monstruos", monstruo, momento)
            os.makedirs(destino, exist_ok=True)
            base = re.sub(r"[^\w-]", "_", os.path.splitext(os.path.basename(src))[0])
            n = 0
            tramos = trozos_por_silencio(src)
            total = duracion(src)
            if total is not None and total <= 8 and tramos and tramos[0][1] is not None:
                # Un audio corto es una sola frase (los susurros tienen pausas): solo se quita el silencio de los bordes.
                tramos = [(max(0, tramos[0][0] - 0.25), min(total, tramos[-1][1] + 0.3))]
            for i, (a, b) in enumerate(tramos):
                if b is not None and b - a > 12:
                    b = a + 12
                dst = os.path.join(destino, f"{base}_{i}.wav")
                cmd = ["ffmpeg", "-y", "-loglevel", "fatal", "-ss", f"{a:.2f}"] + (["-to", f"{b:.2f}"] if b else []) + \
                      ["-i", src, "-af", "loudnorm=I=-16:TP=-1.5", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                       "-f", "wav", dst + ".tmp"]
                if subprocess.run(cmd).returncode == 0:
                    os.replace(dst + ".tmp", dst)
                    n += 1
            print(f"Importado {rel} -> {monstruo} / {momento}: {n} frase(s)")
            if n:
                curador._mover(src, os.path.join(curador.imp, "hechos", rel))
                hechos.setdefault(monstruo, {}).setdefault(momento, 0)
                hechos[monstruo][momento] += n
    return hechos


def resumen_monstruos(curador):
    lineas = []
    raiz = os.path.join(curador.central, "Monstruos")
    if not os.path.isdir(raiz):
        return lineas
    for monstruo in sorted(os.listdir(raiz)):
        lineas.append(f"######## {monstruo} con tu voz ########")
        for momento in MOMENTOS:
            d = os.path.join(raiz, monstruo, momento)
            n = len([f for f in os.listdir(d) if f.endswith(".wav")]) if os.path.isdir(d) else 0
            lineas.append(f"  {momento:<12} {n} frase(s)" + ("  <- falta grabar" if n == 0 else ""))
        lineas.append("")
    return lineas
