"""Respuestas cortas: recorta de cualquier grabacion los trozos que sirven para contestar
("Si.", "Estoy aqui!", "Ya voy", "Te oigo"...) y los guarda aparte para que el mod pueda
responder bien a "hay alguien ahi?", "donde estas?", "me oyes?"...

Solo vale un trozo que sea una frase entera (entre signos de puntuacion o al principio/final):
asi "si me escucha alguien" (condicional) no cuenta como "si", pero "Si, si, que me estan viendo" si.
Cada recorte se vuelve a pasar por Whisper y solo se guarda si se entiende lo esperado.

Quedan en Centralizado/Respuestas/<jugador>/<tipo>__<nombre>.wav (puertas y walkies) y .opus (monstruos),
con su lista en Centralizado/Respuestas/indice.json.
"""
import json
import os
import re
import subprocess

# Tipo de respuesta -> frases (normalizadas, sin repeticiones seguidas) que la forman.
TIPOS = {
    "aqui": ["estoy aqui", "aqui estoy", "aqui", "sigo aqui", "estoy aca", "aca", "aca estoy", "estoy por aqui",
             "aqui dentro", "aqui fuera", "aqui arriba", "aqui abajo", "estoy dentro", "estoy fuera", "aqui sigo",
             "estoy aqui dentro", "estoy aqui fuera"],
    "oigo": ["te oigo", "te escucho", "os oigo", "os escucho", "se te oye", "se te escucha", "te oigo bien",
             "te escucho bien", "si te oigo", "si te escucho", "alto y claro"],
    "hola": ["hola", "buenas", "hey", "ey", "que pasa"],
    "bien": ["estoy bien", "todo bien", "bien", "tranquilo", "tranquilos", "tranqui", "estoy vivo", "sigo vivo",
             "si estoy bien"],
    "voy": ["ya voy", "voy", "ahora voy", "ya vamos", "ya estoy", "ya llego", "ya vengo", "voy para alla",
            "espera", "esperame", "un momento", "un segundo", "voy corriendo", "ya va"],
    "si": ["si", "vale", "claro", "ok", "okey", "si claro", "venga", "dale", "por supuesto", "exacto", "correcto",
           "claro que si"],
}
MAX_POR_TIPO = 8
FIN_DE_FRASE = re.compile(r"[,.!?;:…]$")


def colapsar(norm):
    """'si si si' -> 'si'; 'vale vale' -> 'vale' (las repeticiones no cambian lo que significa)."""
    out = []
    for w in norm.split():
        if not out or out[-1] != w:
            out.append(w)
    return " ".join(out)


def tipo_de(norm):
    n = colapsar(norm)
    for tipo, frases in TIPOS.items():
        if n in frases:
            return tipo
    return None


def tipo_texto(crudo, normalizar):
    """Tipo de un texto entero ("Vale, vale, ahora voy." -> voy): cada trozo entre signos tiene que ser
    una respuesta, y como mucho de un tipo ademas de "si"."""
    trozos = [t for t in re.split(r"[,.!;:…]+", crudo) if normalizar(t)]
    tipos = set()
    for t in trozos:
        tipo = tipo_de(normalizar(t))
        if tipo is None or (("?" in t or "¿" in t) and tipo != "hola"):
            return None
        tipos.add(tipo)
    otros = tipos - {"si"}
    if len(otros) > 1:
        return None
    return next(iter(otros)) if otros else ("si" if tipos else None)


def clausulas(palabras, normalizar):
    """Parte las palabras de Whisper en frases por los signos de puntuacion."""
    actual, todas = [], []
    for w in palabras:
        actual.append(w)
        if FIN_DE_FRASE.search(w["word"].strip()):
            todas.append(actual)
            actual = []
    if actual:
        todas.append(actual)
    res = []
    for c in todas:
        crudo = "".join(w["word"] for w in c)
        n = normalizar(crudo)
        # "¿Estoy aqui?" no es una respuesta (un "¿Hola?" si vale: da mas miedo).
        if ("?" in crudo or "¿" in crudo) and tipo_de(n) != "hola":
            n = "?"
        res.append((c, n))
    return res


def candidatos(palabras, normalizar):
    """Trozos que son una respuesta completa. Se juntan las seguidas ("Si, si, estoy aqui")."""
    cl = clausulas(palabras, normalizar)
    res, i = [], 0
    while i < len(cl):
        tipo = tipo_de(cl[i][1])
        if not tipo:
            i += 1
            continue
        trozo, textos, j = list(cl[i][0]), [cl[i][1]], i + 1
        while j < len(cl) and j - i < 3:
            t2 = tipo_de(cl[j][1])
            if not t2 or (t2 != tipo and "si" not in (tipo, t2)):
                break
            if tipo == "si":
                tipo = t2  # "Si, estoy aqui" es mas que un si
            trozo += cl[j][0]
            textos.append(cl[j][1])
            j += 1
        res.append((i, j, tipo, trozo, " ".join(textos)))
        i = j
    return res, cl


def candidatos_nombre(palabras, normalizar, quien):
    """Trozos que son solo un nombre ("¡Leo!", "Max, Max", "Eh, Ana"): sirven para susurrarle su nombre
    a quien se queda solo. quien(norm) devuelve el jugador nombrado si la frase es solo su nombre."""
    cl = clausulas(palabras, normalizar)
    res, i = [], 0
    while i < len(cl):
        steam = quien(cl[i][1]) if cl[i][1] != "?" else None
        crudo = "".join(w["word"] for w in cl[i][0])
        if steam is None and ("?" in crudo or "¿" in crudo):
            steam = quien(normalizar(crudo))  # "¿Leo?" tambien vale
        if not steam:
            i += 1
            continue
        trozo, textos, j = list(cl[i][0]), [normalizar(crudo)], i + 1
        while j < len(cl) and j - i < 3:
            crudo2 = "".join(w["word"] for w in cl[j][0])
            if quien(normalizar(crudo2)) != steam:
                break
            trozo += cl[j][0]
            textos.append(normalizar(crudo2))
            j += 1
        res.append((i, j, steam, trozo, " ".join(textos)))
        i = j
    return res, cl


def cargar_audio(ruta, sr):
    import numpy as np
    out = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "fatal", "-i", ruta, "-f", "s16le", "-ac", "1",
                          "-ar", str(sr), "-"], capture_output=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768.0


def guardar_wav(ruta, audio, sr):
    import wave
    import numpy as np
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


class Respuestas:
    def __init__(self, curador):
        self.c = curador
        self.raiz = os.path.join(curador.central, "Respuestas")
        self.ruta_indice = os.path.join(self.raiz, "indice.json")
        try:
            with open(self.ruta_indice, encoding="utf-8") as f:
                self.indice = json.load(f)
        except (OSError, ValueError):
            self.indice = {}

    def guardar(self):
        if self.c.simular:
            return
        os.makedirs(self.raiz, exist_ok=True)
        tmp = self.ruta_indice + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.indice, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.ruta_indice)
        # Para el mod (que no lee diccionarios JSON): "jugador/archivo|NombreDeSteam" de cada nombre suelto.
        with open(os.path.join(self.raiz, "nombres.txt"), "w", encoding="utf-8") as f:
            for clave, items in self.indice.items():
                for archivo, e in items.items():
                    if e["tipo"] == "nombre" and e.get("a"):
                        f.write(f"{clave}/{archivo}|{e['a']}\n")

    def extraer(self, clave, ruta, t, base, solo_nombres=False):
        """Recorta las respuestas de una grabacion ya transcrita (t["palabras"]). Devuelve cuantas guarda."""
        palabras = t.get("palabras") or []
        if not palabras or self.c.simular:
            return 0
        from mirage_voces import normalizar
        trozos, cl = candidatos(palabras, normalizar)
        trozos = [] if solo_nombres else trozos
        nombres, _ = candidatos_nombre(palabras, normalizar, self.c.nombre_solo)
        trozos = [(i, j, t, ws, x, None, f"{base}_{n}") for n, (i, j, t, ws, x) in enumerate(trozos)]
        trozos += [(i, j, "nombre", ws, x, steam, f"{base}_n{n}") for n, (i, j, steam, ws, x) in enumerate(nombres)]
        audio = None
        guardadas = 0
        for i, j, tipo, ws, texto, steam, nombre in trozos:
            prob = sum(w.get("probability", 0) for w in ws) / len(ws)
            if prob < 0.5:
                continue
            # Un poco de margen, sin comerse la palabra de antes ni la de despues.
            ini, fin = ws[0]["start"] - 0.12, ws[-1]["end"] + 0.22
            if i > 0:
                ini = max(ini, cl[i - 1][0][-1]["end"] + 0.02)
            if j < len(cl):
                fin = min(fin, cl[j][0][0]["start"] - 0.02)
            if fin - ini < 0.25 or fin - ini > 3.0:
                continue
            if audio is None:
                audio = cargar_audio(ruta, 48000)
                if len(audio) == 0:
                    return 0
            if self._guardar_trozo(clave, tipo, texto, prob, audio, ini, fin, nombre, steam):
                guardadas += 1
        if guardadas:
            self._limitar(clave)
            self.guardar()
        return guardadas

    def _guardar_trozo(self, clave, tipo, texto, prob, audio, ini, fin, nombre, steam=None):
        import numpy as np
        from mirage_voces import FFMPEG_OPUS, normalizar
        sr = 48000
        a, b = max(0, int(ini * sr)), min(len(audio), int(fin * sr))
        trozo = audio[a:b].copy()
        if len(trozo) < sr * 0.2:
            return False
        # Fundidos cortos (sin chasquidos) y volumen parecido al resto de frases.
        f_in, f_out = min(len(trozo) // 4, int(0.015 * sr)), min(len(trozo) // 4, int(0.04 * sr))
        trozo[:f_in] *= np.linspace(0, 1, f_in)
        trozo[-f_out:] *= np.linspace(1, 0, f_out)
        rms = float(np.sqrt(np.mean(trozo ** 2))) or 1e-6
        trozo *= min(0.12 / rms, 0.95 / (float(np.abs(trozo).max()) or 1e-6))

        carpeta = os.path.join(self.raiz, clave)
        os.makedirs(carpeta, exist_ok=True)
        archivo = f"{tipo}__{nombre}"
        tmp48 = os.path.join(carpeta, archivo + ".tmp48.wav")
        wav16, opus = os.path.join(carpeta, archivo + ".wav"), os.path.join(carpeta, archivo + ".opus")
        guardar_wav(tmp48, trozo, sr)
        try:
            # Comprobacion: Whisper tiene que entender en el recorte una respuesta del mismo tipo.
            r = self.c._whisper().transcribe(tmp48, language=self.c.cfg["idioma"], temperature=0,
                                             fp16=self.c.dispositivo == "cuda", condition_on_previous_text=False)
            oido = r["text"].strip()
            if tipo == "nombre":
                ok_texto = self.c.nombre_solo(normalizar(oido)) == steam
            else:
                t2 = tipo_texto(oido, normalizar)
                ok_texto = t2 is not None and (t2 == tipo or "si" in (t2, tipo))
            if not ok_texto:
                print(f"    recorte \"{texto}\" no se entiende bien (\"{oido}\"): fuera")
                return False
            ok = subprocess.run(["ffmpeg", "-y", "-loglevel", "fatal", "-i", tmp48] + FFMPEG_OPUS +
                                ["-f", "ogg", opus]).returncode == 0
            ok = ok and subprocess.run(["ffmpeg", "-y", "-loglevel", "fatal", "-i", tmp48, "-ac", "1", "-ar", "16000",
                                        "-c:a", "pcm_s16le", "-f", "wav", wav16]).returncode == 0
            if not ok:
                return False
        finally:
            if os.path.exists(tmp48):
                os.remove(tmp48)
        entrada = {"tipo": tipo, "texto": oido, "prob": round(prob, 3)}
        if steam:
            entrada["a"] = steam
        self.indice.setdefault(clave, {})[archivo] = entrada
        print(f"    + {'nombre de ' + steam if steam else 'respuesta ' + repr(tipo)}: \"{oido}\"")
        return True

    def _limitar(self, clave):
        """Como mucho MAX_POR_TIPO por tipo y jugador: se quedan las que mejor se entienden."""
        por_tipo = {}
        for archivo, e in self.indice.get(clave, {}).items():
            # Los nombres cuentan aparte para cada persona nombrada.
            por_tipo.setdefault((e["tipo"], e.get("a")), []).append((e["prob"], archivo))
        for lista in por_tipo.values():
            for _, archivo in sorted(lista, reverse=True)[MAX_POR_TIPO:]:
                for ext in (".wav", ".opus"):
                    p = os.path.join(self.raiz, clave, archivo + ext)
                    if os.path.exists(p):
                        os.remove(p)
                del self.indice[clave][archivo]

    def resumen(self, nombre_de):
        """Lineas para resumen.txt: que respuestas tiene cada uno y cuales le faltan."""
        lineas = []
        for clave in sorted(self.indice, key=nombre_de):
            items = self.indice[clave]
            if not items:
                continue
            lineas.append(f"######## Respuestas cortas de {nombre_de(clave)} ({len(items)}) ########")
            por_tipo = {}
            for e in items.values():
                if e["tipo"] == "nombre":
                    por_tipo.setdefault("nombres", []).append(f"{e['texto']} ({e.get('a')})")
                else:
                    por_tipo.setdefault(e["tipo"], []).append(e["texto"])
            for tipo in list(TIPOS) + ["nombres"]:
                if tipo in por_tipo:
                    lineas.append(f"  {tipo}: " + " | ".join(f"\"{t}\"" for t in por_tipo[tipo]))
            faltan = [t for t in TIPOS if t not in por_tipo]
            if faltan:
                lineas.append(f"  (le faltan: {', '.join(faltan)})")
            lineas.append("")
        return lineas
