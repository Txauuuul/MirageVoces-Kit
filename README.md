# MirageVoces – Kit del anfitrión / Host Kit

**🆕 [What's new](#-whats-new--novedades) · 🇬🇧 [English](#-english) · 🇪🇸 [Español](#-español)**

Host kit for the Lethal Company mod **[MirageVoces](https://thunderstore.io/c/lethal-company/p/Lloreria/MirageVoces/)**.
Without it, the mod does very little.

*Kit para quien hace de **anfitrión** con el mod de Lethal Company
**[MirageVoces](https://thunderstore.io/c/lethal-company/p/Lloreria/MirageVoces/)**. Sin este kit, el mod casi no hace nada.*

---

## 🆕 What's new · Novedades

### Host Kit
**1.1** · 2026-11-06 · *Live Whisper keeps up with big lobbies · Whisper en vivo aguanta partidas con mucha gente*
- Only listens to players **alive on a moon**: ship talk and dead players are skipped, so it no longer falls behind with 8-10 people. · *Solo escucha a los **vivos en una luna**: lo que se dice en la nave o estando muerto se ignora, y ya no se retrasa con 8-10 personas.*
- One line at a time, newest first, with a faster mode when lines pile up. · *De una en una, lo más nuevo primero, y modo rápido cuando hay cola.*
- Monsters never answer something said more than 20 s ago. · *Los monstruos nunca contestan algo dicho hace más de 20 s.*
- If it still falls behind, it keeps only each player's most important line (screams, short questions). · *Si aun así se retrasa, de cada uno escucha solo lo más importante (gritos, preguntas cortas).*
- Stops a few seconds after you close the game. · *Se cierra a los pocos segundos de cerrar el juego.*

**1.0** · 2026-11-05 · *First public release · Primera versión pública*
- One-click installer (`INSTALAR.bat`), Whisper **turbo** with your nicknames and game words, smart answers, conversations, Bracken voice and the night recap page. · *Instalador de un clic, Whisper **turbo** con vuestros apodos y palabras del juego, respuestas con cabeza, conversaciones, voz del Bracken y resumen de la noche.*

### Mod ([Thunderstore](https://thunderstore.io/c/lethal-company/p/Lloreria/MirageVoces/))
| Version | What's new · Novedades |
|---|---|
| **0.8.2** | Host Kit made public. · *Kit del anfitrión público.* |
| **0.8.1** | **Conversations**: the voice that answered you keeps answering, from the same place. · ***Conversaciones**: la voz que te contestó sigue contestándote desde el mismo sitio.* |
| **0.8.0** | **Smart answers**: understands what was said and picks the best line from your library, even saying your name. · ***Respuestas con cabeza**: entiende lo que se dice y elige la mejor frase, incluso con tu nombre.* |
| **0.7.0** | Records every player at all times, however far away. · *Graba a todos en todo momento, estén donde estén.* |
| **0.6.x** | Night log for the recap, death screams kept, real voices only (never pitch-shifted), rarer "alone" voices. · *Diario de la noche, se guarda el grito al morir, voces sin modular, susurros "solo" más raros.* |
| **0.5.x** | No name tags, last words, alone in the dark, ship speaker. The mod no longer runs any program. · *Sin nombres, últimas palabras, solo en la oscuridad, altavoz de la nave. El mod ya no ejecuta programas.* |
| **0.4.x** | Bracken with the host's voice and aggressive Bracken; summons need *"que venga el…"*. · *Bracken con tu voz y Bracken agresivo; para invocar hay que decir "que venga el…".* |
| **0.3.x** | Live Whisper: monsters answer questions, spoken summons, voice test. · *Whisper en vivo: los monstruos contestan, invocaciones por voz, prueba de voces.* |
| **0.1-0.2** | Friends' voices recorded by the host; whispering corpses, fake walkies, voices behind doors. · *Grabación de voces de los amigos; cadáveres que susurran, walkies falsos, voces tras las puertas.* |

---

## 🇬🇧 English

### What is it?
MirageVoces is a horror mod for Lethal Company that works alongside
[Mirage](https://thunderstore.io/c/lethal-company/p/qwbarch/Mirage/): monsters speak with **your friends'
voices**, corpses whisper, voices come from behind doors… and if you ask *"Is anyone there?"*, something that
isn't human may answer.

To do that, the **host's** PC has to understand what is being said during the game. That's what this kit is for.
It uses **Whisper** (OpenAI's speech recognition) and runs **locally, offline**.

> **Only the host installs it.** Everyone else just needs the mod and Mirage from their mod manager.

### What does it add?
| | Mod only | Mod + kit |
|---|:---:|:---:|
| Hidden name tags · aggressive Bracken | ✅ | ✅ |
| Whispering corpses · fake walkie calls · voices behind doors | ❌ | ✅ |
| Last words · voices when you're alone · ship speaker | ❌ | ✅ |
| Monsters use each player's **best** lines | ❌ | ✅ |
| **Answers**: *"Is anyone there?"* → *"Ana! Are you there?"* in a friend's voice | ❌ | ✅ |
| **Conversations**: the same voice keeps answering you from the same place | ❌ | ✅ |
| Spoken monster summons and voice test | ❌ | ✅ |
| Bracken with **your** voice (stalking, chase, kill, drag) | ❌ | ✅ |
| **Night recap**: web page with deaths, screams and best lines, with audio | ❌ | ✅ |

### Requirements
- **Windows 10 or 11.**
- **Lethal Company** with a mod manager (Thunderstore Mod Manager, r2modman or Gale) and, in your profile:
  [MirageVoces](https://thunderstore.io/c/lethal-company/p/Lloreria/MirageVoces/) and
  [Mirage](https://thunderstore.io/c/lethal-company/p/qwbarch/Mirage/) (or a compatible fork).
- **Recommended:** an **NVIDIA GPU with 6 GB or more**. It works without one, but recognition is slower and less accurate.
- About **5 GB of free space** and an internet connection during installation.

### Installation (5 minutes + downloads)
1. Install **MirageVoces** and **Mirage** in your mod manager profile and **launch the game once** from that profile.
2. Download this kit: green button **`Code` → `Download ZIP`**.
3. Unzip it to a **permanent** folder, e.g. `Documents\MirageVoces-Kit`. If you move it later, run the installer again.
4. Open the unzipped folder and double-click **`INSTALAR.bat`**. The installer, by itself:
   - checks **Python** and **ffmpeg** and offers to install them if missing;
   - installs **PyTorch and Whisper** for your GPU and picks the model that fits its memory;
   - finds **Lethal Company** and your **Steam name**;
   - finds your profile with MirageVoces, copies the **host plugin** and configures the mod.
5. *(Recommended)* Open **`apodos.txt`** and write each player's Steam name and what you call them.

You can run `INSTALAR.bat` as many times as you want: whatever is already done is left as is.

### Usage
**Just play as the host.** Whisper starts with the game and closes when you quit.
In the first games the mod collects your voices: **the more you play, the better it gets**.

> The installer and the tools are in Spanish, and speech recognition is tuned for **Spanish** speakers
> (`"idioma": "es"` in `config.json`). Whisper understands other languages, but the phrase rules
> (questions, answers, summons) are written for Spanish.

**Special phrases** (host only, inside the facility):
| Say… | What happens |
|---|---|
| **"Activar prueba de voces"** | One of your lines plays in front of you, behind a door, over the walkie and from a nearby monster |
| **"Que venga el Bracken"** / **"Que venga el Jester"** | That monster spawns nearby (once per moon) |

**Questions** ("¿Hay alguien ahí?", "¿Dónde estás?", "¿Me oyes?"…): anyone can ask. The voice of someone who
**can't really answer** (dead or far away) replies, from a monster, a door, the walkie or a dark corner.

**Tools** (in the kit folder):
| File | What for |
|---|---|
| `Ver Whisper en vivo.bat` | Live window with what Whisper understands and what the mod does |
| `Resumen de la ultima noche.bat` | Rebuilds the recap page of the last game |
| `Curar voces.bat` | Processes recordings manually (usually not needed) |
| `Recalibrar con el modelo actual.bat` | Re-transcribes every saved line (if you change the Whisper model) |
| `apodos.txt` | Steam names and nicknames of your group |
| `diccionario.txt` | Words Whisper should spell right (monsters, game terms, expressions) |
| `config.json` | Advanced settings (Whisper model, durations…) |

**Bracken with your voice:** record lines and put them in `Lethal Company\Mirage\Importar\Bracken\<moment>\`,
where `<moment>` is `acecho` (stalking), `pillado` (spotted), `persecucion` (chase), `muerte` (kill) or `arrastre` (drag).
Ideas in [`docs/GUION_BRACKEN.txt`](docs/GUION_BRACKEN.txt).

**Lines recorded on purpose** (voice notes, recorder…): files in `Lethal Company\Mirage\Importar\` are yours; in
`Importar\<friend's name>\`, that friend's. They are imported when the next game starts.

**Where everything is saved** (`Lethal Company\Mirage\`):
- `Biblioteca\`: each player's lines sorted by type, and `resumen.txt` with everything understood.
- `Biblioteca\noches\`: the **recap page of each night**. Open it with a double click.

### Privacy and consent
- The host **records what each player says over voice chat** so monsters can imitate it.
  **Only use it with people who agree.**
- Everything stays **on the host's PC**. Nothing is uploaded and Whisper works offline.
- During the game, other players **hear** the scares with those voices, but nothing is stored on their PCs.
- If you play with strangers, turn recording off in `BepInEx\config\lloreria.miragevoces.cfg` →
  `Grabar voces de amigos = false`.

### Troubleshooting
- **It doesn't understand anything / the live window doesn't move:** check
  `Lethal Company\Mirage\Centralizado\Vivo\servidor.log`. If you moved the kit folder, run `INSTALAR.bat` again.
- **Slow or stuttering:** in `config.json`, change `"modelo_whisper": "turbo"` to `"small"` (or `"base"`).
- **Mod log:** `BepInEx\LogOutput.log` in your profile. Look for `[respuesta]`, `[bracken]`, `[efecto]`, `[solo]`…
- **Antivirus warning:** it's a new, unsigned project. The kit only downloads what `INSTALAR.bat` installs, after
  asking you, from official sources (winget, PyTorch, PyPI). All the code is in this repository.

### Uninstall
Delete the kit folder and `BepInEx\plugins\MirageVoces-Anfitrion` from your profile. To also delete the saved
voices: `Lethal Company\Mirage\Biblioteca`, `Centralizado` and `Papelera`.

---

## 🇪🇸 Español

### ¿Qué es?
MirageVoces es un mod de terror para Lethal Company que funciona junto a
[Mirage](https://thunderstore.io/c/lethal-company/p/qwbarch/Mirage/): los monstruos hablan con **la voz de tus
amigos**, los cadáveres susurran, se oyen voces tras las puertas… y si preguntas *"¿Hay alguien ahí?"*, puede
contestarte algo que no es humano.

Para conseguirlo, el PC del **anfitrión** tiene que entender lo que se dice en la partida. Para eso está este kit,
que usa **Whisper**, el reconocimiento de voz de OpenAI. Funciona **en tu PC, sin internet**.

> **Solo lo instala quien hace de anfitrión.** El resto del grupo solo necesita el mod y Mirage desde el mod manager.

### ¿Qué añade?
| | Solo el mod | Mod + kit |
|---|:---:|:---:|
| Sin nombres encima de los jugadores · Bracken agresivo | ✅ | ✅ |
| Cadáveres que susurran · walkies falsos · voces tras las puertas | ❌ | ✅ |
| Últimas palabras · voces cuando estás solo · altavoz de la nave | ❌ | ✅ |
| Los monstruos usan las **mejores** frases de cada uno | ❌ | ✅ |
| **Respuestas**: *"¿Hay alguien ahí?"* → *"¡Ana! ¿Estás ahí?"* con la voz de un amigo | ❌ | ✅ |
| **Conversaciones**: la misma voz te sigue contestando desde el mismo sitio | ❌ | ✅ |
| Invocar monstruos y "prueba de voces" hablando | ❌ | ✅ |
| Bracken con **tu** voz (acecho, persecución, muerte, arrastre) | ❌ | ✅ |
| **Resumen de la noche**: página web con muertes, gritos y mejores frases, con audio | ❌ | ✅ |

### Requisitos
- **Windows 10 u 11.**
- **Lethal Company** con un mod manager (Thunderstore Mod Manager, r2modman o Gale) y, en tu perfil:
  [MirageVoces](https://thunderstore.io/c/lethal-company/p/Lloreria/MirageVoces/) y
  [Mirage](https://thunderstore.io/c/lethal-company/p/qwbarch/Mirage/) (o un fork compatible).
- **Recomendado:** una gráfica **NVIDIA con 6 GB o más**. Sin ella también funciona, pero entiende peor y más despacio.
- Unos **5 GB libres** y conexión a internet durante la instalación.

### Instalación (5 minutos + descargas)
1. Instala **MirageVoces** y **Mirage** en tu perfil del mod manager y **abre el juego una vez** desde ese perfil.
2. Descarga este kit: botón verde **`Code` → `Download ZIP`**.
3. Descomprímelo en una carpeta **fija**, por ejemplo `Documentos\MirageVoces-Kit`. Si luego la mueves, vuelve a
   lanzar el instalador.
4. Entra en la carpeta descomprimida y haz doble clic en **`INSTALAR.bat`**. El instalador, solo:
   - comprueba **Python** y **ffmpeg**, y si faltan se ofrece a instalarlos;
   - instala **PyTorch y Whisper** para tu gráfica y elige el modelo según su memoria;
   - encuentra **Lethal Company** y tu **nombre de Steam**;
   - encuentra tu perfil con MirageVoces, copia el **plugin del anfitrión** y configura el mod.
5. *(Recomendado)* Abre **`apodos.txt`** y escribe el nombre de Steam de cada uno y cómo le llamáis.

Puedes repetir `INSTALAR.bat` las veces que quieras: lo que ya está hecho, lo deja como está.

### Uso
**Juega haciendo de anfitrión. Ya está.** Whisper arranca solo al empezar la partida y se cierra solo al salir.
Las primeras partidas el mod va guardando vuestras voces: **cuanto más juguéis, mejor funciona**.

**Frases especiales** (solo el anfitrión, dentro del edificio):
| Di… | Y pasa… |
|---|---|
| **"Activar prueba de voces"** | Suena una frase tuya delante, tras una puerta, por el walkie y desde un monstruo cercano |
| **"Que venga el Bracken"** / **"Que venga el Jester"** | Aparece ese monstruo cerca (una vez por luna) |

**Preguntas** ("¿Hay alguien ahí?", "¿Dónde estás?", "¿Me oyes?", "¿Ana?"…): las puede hacer cualquiera.
Contesta la voz de alguien que **no puede contestar de verdad** (muerto o lejos), desde un monstruo, una puerta,
el walkie o un rincón oscuro.

**Herramientas** (en la carpeta del kit):
| Archivo | Para qué |
|---|---|
| `Ver Whisper en vivo.bat` | Ventana que muestra en directo lo que entiende Whisper y lo que hace el mod |
| `Resumen de la ultima noche.bat` | Vuelve a crear la página del resumen de la última partida |
| `Curar voces.bat` | Procesa las grabaciones a mano (normalmente no hace falta) |
| `Recalibrar con el modelo actual.bat` | Vuelve a transcribir todas las frases (si cambias de modelo) |
| `apodos.txt` | Nombres de Steam y apodos de tu grupo |
| `diccionario.txt` | Palabras que Whisper debe escribir bien (monstruos, cosas del juego, expresiones) |
| `config.json` | Ajustes avanzados (modelo de Whisper, duraciones…) |

**Bracken con tu voz:** graba frases y ponlas en `Lethal Company\Mirage\Importar\Bracken\<momento>\`, donde
`<momento>` es `acecho`, `pillado`, `persecucion`, `muerte` o `arrastre`. Ideas en
[`docs/GUION_BRACKEN.txt`](docs/GUION_BRACKEN.txt).

**Frases grabadas a propósito** (WhatsApp, grabadora…): en `Lethal Company\Mirage\Importar\` son tuyas; en
`Importar\<nombre del amigo>\`, de ese amigo. Se importan al empezar la siguiente partida.

**Dónde se guarda todo** (`Lethal Company\Mirage\`):
- `Biblioteca\`: las frases de cada uno, ordenadas por tipo, y `resumen.txt` con todo lo que se ha entendido.
- `Biblioteca\noches\`: el **resumen de cada noche**. Ábrelo con doble clic.

### Privacidad y consentimiento
- El anfitrión **graba lo que dice cada jugador por el chat de voz** para que los monstruos lo imiten.
  **Úsalo solo con gente que esté de acuerdo.**
- Todo se queda **en el PC del anfitrión**. No se sube nada a ningún sitio y Whisper funciona sin internet.
- Durante la partida, los demás **oyen** los sustos con esas voces, pero no se les guarda nada.
- Si juegas con desconocidos, desactiva la grabación en `BepInEx\config\lloreria.miragevoces.cfg` →
  `Grabar voces de amigos = false`.

### Problemas
- **No entiende nada / "Whisper en vivo" no se mueve:** mira `Lethal Company\Mirage\Centralizado\Vivo\servidor.log`.
  Si has movido la carpeta del kit, vuelve a lanzar `INSTALAR.bat`.
- **Va lento o da tirones:** en `config.json`, cambia `"modelo_whisper": "turbo"` por `"small"` (o `"base"`).
- **Log del mod:** `BepInEx\LogOutput.log` de tu perfil. Busca `[respuesta]`, `[bracken]`, `[efecto]`, `[solo]`…
- **El antivirus avisa:** es un proyecto nuevo y sin firma digital. El kit solo descarga lo que instala
  `INSTALAR.bat`, que antes te lo pregunta, y desde fuentes oficiales (winget, PyTorch, PyPI). El código está
  a la vista en este repositorio.

### Desinstalar
Borra la carpeta del kit y `BepInEx\plugins\MirageVoces-Anfitrion` de tu perfil. Para borrar también las voces
guardadas: `Lethal Company\Mirage\Biblioteca`, `Centralizado` y `Papelera`.

---

### Credits / Créditos
- [Mirage](https://thunderstore.io/c/lethal-company/p/qwbarch/Mirage/) by qwbarch: the monsters that imitate voices.
- [Whisper](https://github.com/openai/whisper) by OpenAI · [ffmpeg](https://ffmpeg.org) · [PyTorch](https://pytorch.org).
- Host plugin source code: [`plugin/codigo`](plugin/codigo).
- Made with the help of AI. / Hecho con ayuda de IA.
