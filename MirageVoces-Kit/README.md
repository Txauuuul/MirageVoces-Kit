# MirageVoces – Kit del anfitrión

Kit para **el anfitrión** de la partida que usa el mod [MirageVoces](https://thunderstore.io/c/lethal-company/p/Lloreria/MirageVoces/)
de Lethal Company. Con él, el mod funciona **completo**: entiende lo que decís, los monstruos os contestan con
la voz de vuestros amigos y el Bracken habla con la tuya.

> **Solo lo necesita quien haga de anfitrión.** El resto del grupo solo necesita el mod (y Mirage) desde el mod manager.

*English summary at the bottom.*

---

## ¿Qué añade el kit?

| | Solo el mod | Mod + kit |
|---|:---:|:---:|
| Sin nombres encima de los jugadores, Bracken agresivo | ✅ | ✅ |
| Cadáveres que susurran, walkies falsos, voces tras las puertas | ❌ | ✅ |
| Últimas palabras, voces cuando estás solo, voces por el altavoz de la nave | ❌ | ✅ |
| Los monstruos usan las **mejores** frases de cada uno | ❌ | ✅ |
| **Respuestas**: "¿Hay alguien ahí?" → *"¡Ana! ¿Estás ahí?"* con la voz de un amigo | ❌ | ✅ |
| Invocar monstruos y "prueba de voces" hablando | ❌ | ✅ |
| Bracken con **tu** voz (acecho, persecución, muerte…) | ❌ | ✅ |
| **Resumen de la noche** (página web con muertes, gritos, mejores frases y audios) | ❌ | ✅ |

El kit usa **Whisper** (reconocimiento de voz de OpenAI, funciona en tu PC, sin internet) para entender y
ordenar lo que se dice en la partida.

## Requisitos

- **Windows 10 u 11.**
- **Lethal Company** con un mod manager (Thunderstore Mod Manager, r2modman o Gale) y en tu perfil:
  - [MirageVoces](https://thunderstore.io/c/lethal-company/p/Lloreria/MirageVoces/)
  - [Mirage](https://thunderstore.io/c/lethal-company/p/qwbarch/Mirage/) (o un fork compatible)
- **Recomendado: una gráfica NVIDIA** con 6 GB o más. Con menos, o sin NVIDIA, funciona igual pero entiende peor y más lento.
- Unos **5 GB libres** e internet durante la instalación (Python, PyTorch, Whisper).

## Instalación

1. Instala **MirageVoces** y **Mirage** en tu perfil del mod manager y **abre el juego una vez** desde ese perfil.
2. Descarga este kit: botón verde **Code → Download ZIP**.
3. Descomprímelo en una carpeta fija, por ejemplo `Documentos\MirageVoces-Kit`. No lo dejes en Descargas: si
   luego lo mueves, tendrás que volver a lanzar el instalador.
4. Doble clic en **`INSTALAR.bat`** y sigue lo que dice. Él solo:
   - comprueba **Python** y **ffmpeg** y, si faltan, se ofrece a instalarlos;
   - instala **PyTorch y Whisper** para tu gráfica y elige el modelo según tu memoria de vídeo;
   - encuentra **Lethal Company** y tu **nombre de Steam**;
   - encuentra tu perfil con MirageVoces, copia el **plugin del anfitrión** y configura el mod.
5. (Recomendado) Abre **`apodos.txt`** y pon el nombre de Steam de cada uno y cómo le llamáis.

Se puede volver a lanzar `INSTALAR.bat` las veces que haga falta: lo que ya está, lo deja como está.

## Cómo se usa

**Juega haciendo de anfitrión. Ya está.** Whisper arranca solo con la partida y se cierra solo al salir.
Las primeras partidas el mod va aprendiendo vuestras voces: cuanto más juguéis, mejor.

### Lo que se puede decir (solo el anfitrión, dentro del edificio)
| Frase | Qué pasa |
|---|---|
| **"Activar prueba de voces"** | Suena una frase tuya delante, tras una puerta, por el walkie y desde un monstruo cercano |
| **"Que venga el Bracken"** / **"Que venga el Jester"** | Aparece ese monstruo cerca (una vez por luna) |

Las **preguntas** ("¿Hay alguien ahí?", "¿Dónde estás?", "¿Me oyes?", "¿Ana?"…) las puede hacer cualquiera:
contesta la voz de alguien que no puede contestar de verdad (muerto o lejos).

### Herramientas del kit
| Archivo | Para qué |
|---|---|
| `Ver Whisper en vivo.bat` | Ventana que muestra en directo lo que entiende Whisper y lo que hace el mod |
| `Curar voces.bat` | Procesa las grabaciones a mano (normalmente no hace falta: se hace solo jugando) |
| `Resumen de la ultima noche.bat` | Rehace la página del resumen de la última partida |
| `Recalibrar con el modelo actual.bat` | Vuelve a transcribir todas las frases (si cambias de modelo de Whisper) |
| `apodos.txt` | Nombres de Steam y apodos de tu grupo |
| `diccionario.txt` | Palabras que Whisper debe escribir bien (monstruos, cosas del juego…) |
| `config.json` | Ajustes avanzados (modelo de Whisper, duraciones…) |

### Bracken con tu voz
Graba frases y mételas en `Lethal Company\Mirage\Importar\Bracken\<momento>\`, con un audio por frase o
varias separadas por un segundo de silencio. Los momentos son `acecho`, `pillado`, `persecucion`, `muerte` y
`arrastre`. Tienes ideas en [`docs/GUION_BRACKEN.txt`](docs/GUION_BRACKEN.txt). Se importan solas al empezar la
siguiente partida.

### Frases grabadas a propósito
Audios (WhatsApp, grabadora…) en `Lethal Company\Mirage\Importar\` son tuyos; en
`Lethal Company\Mirage\Importar\<nombre del amigo>\`, de ese amigo. Se importan al empezar la partida.

### Dónde se guarda todo
En la carpeta del juego, `Lethal Company\Mirage\`:
- `Biblioteca\` → frases de cada uno por tipo, y `resumen.txt` con todo lo que se ha entendido.
- `Biblioteca\noches\` → la página del **resumen de cada noche**: ábrela con doble clic.
- `Papelera\` → lo descartado a mano (no se usa nunca).

## Privacidad y consentimiento

- **El anfitrión graba lo que dice cada jugador por el chat de voz**, para que los monstruos lo imiten.
  **Úsalo solo con gente que esté de acuerdo.**
- Todo se queda **en tu PC**. Nada se sube a ningún sitio y Whisper funciona sin internet.
- Durante la partida, los demás jugadores **oyen** los sustos con esas voces, pero no se les guarda nada.
- Si juegas con desconocidos, desactiva la grabación en `BepInEx\config\lloreria.miragevoces.cfg` →
  `Grabar voces de amigos = false`.

## Si algo no va

- **No entiende nada / la ventana de "Whisper en vivo" no se mueve:** mira
  `Lethal Company\Mirage\Centralizado\Vivo\servidor.log`. Si has movido la carpeta del kit, vuelve a lanzar `INSTALAR.bat`.
- **Va lento o da tirones:** en `config.json` cambia `"modelo_whisper": "turbo"` por `"small"`, o por `"base"` si sigue lento.
- **Log del mod:** `BepInEx\LogOutput.log` de tu perfil. Busca las líneas `[respuesta]`, `[bracken]`, `[efecto]`, `[solo]`…
- **El antivirus avisa:** es un mod nuevo sin firma digital. El kit no descarga nada por su cuenta salvo lo que
  instala `INSTALAR.bat`, que te lo pregunta y viene de fuentes oficiales (python.org vía winget, PyTorch y PyPI).

## Desinstalar

Borra la carpeta del kit y la carpeta `BepInEx\plugins\MirageVoces-Anfitrion` de tu perfil. Si quieres borrar
también las voces guardadas, borra `Lethal Company\Mirage\Biblioteca`, `Centralizado` y `Papelera`.

## Créditos

- [Mirage](https://thunderstore.io/c/lethal-company/p/qwbarch/Mirage/) de qwbarch: los monstruos que imitan voces.
- [Whisper](https://github.com/openai/whisper) de OpenAI · [ffmpeg](https://ffmpeg.org) · [PyTorch](https://pytorch.org).
- El código del plugin del anfitrión está en [`plugin/codigo`](plugin/codigo).
- Hecho con ayuda de IA.

---

## English summary

This is the **host kit** for the Lethal Company mod [MirageVoces](https://thunderstore.io/c/lethal-company/p/Lloreria/MirageVoces/).
Only the **host** needs it; other players just need the mod (and Mirage). It adds everything that needs speech
recognition (OpenAI Whisper, running locally): whispering corpses, fake walkie calls, voices behind doors, last
words, monsters **answering** your questions in a friend's voice, spoken summons, a custom-voiced Bracken and a
**night recap** web page.

**Install:** install MirageVoces + Mirage in your mod manager profile and launch the game once → download this
repo (Code → Download ZIP) → unzip to a permanent folder → run **`INSTALAR.bat`** (it checks/installs Python,
ffmpeg, PyTorch + Whisper for your GPU, finds the game and your profile, and configures the mod) → play as host.

Requirements: Windows 10/11, an NVIDIA GPU with 6 GB+ recommended, ~5 GB of disk space. Speech recognition is tuned
for **Spanish** (`"idioma": "es"` in `config.json`; other languages work with Whisper but phrase matching rules are Spanish).

**Consent:** the host records what players say over voice chat. Only use it with people who agree. Everything stays
on the host's PC.
