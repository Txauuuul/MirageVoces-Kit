# Instalador del kit del anfitrion de MirageVoces.
# Se lanza con INSTALAR.bat. Se puede repetir sin miedo: lo que ya esta hecho, lo deja como esta.
#   -Simular : solo mira y dice lo que haria, sin instalar ni cambiar nada.
param([switch]$Simular)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$kit = $PSScriptRoot
$Host.UI.RawUI.WindowTitle = "MirageVoces - kit del anfitrion"

function Paso($t) { Write-Host "`n== $t ==" -ForegroundColor Cyan }
function Bien($t) { Write-Host "   OK  $t" -ForegroundColor Green }
function Ojo($t) { Write-Host "   !!  $t" -ForegroundColor Yellow }
function Mal($t) { Write-Host "   XX  $t" -ForegroundColor Red }
function Pregunta($t, $def) {
    if ($Simular) { Write-Host "   $t -> $def"; return $def }
    $r = Read-Host "   $t$(if ($def) { " [$def]" })"
    if ([string]::IsNullOrWhiteSpace($r)) { return $def } else { return $r.Trim() }
}
function SiNo($t) { return (Pregunta "$t (s/n)" "s") -match '^(s|si|y|yes)$' }
function Refrescar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "MirageVoces - kit del anfitrion" -ForegroundColor Magenta
Write-Host "Esto prepara TU PC para hacer de anfitrion con todas las funciones (Whisper en vivo, respuestas," -ForegroundColor Gray
Write-Host "curar las voces, resumen de la noche...). Los demas jugadores solo necesitan el mod." -ForegroundColor Gray
if ($Simular) { Ojo "MODO SIMULACION: no se instala ni se cambia nada." }

# ------------------------------------------------------------------ Python
Paso "1/6 Python"
function Probar-Python($exe) {
    if (-not $exe -or $exe -match "WindowsApps") { return $null }   # el acceso directo de la Microsoft Store no vale
    try {
        $ver = & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) { return @{ Exe = $exe; Ver = $ver.Trim() } }
    } catch { }
    return $null
}
function Buscar-Python {
    try { $exe = (& py -3 -c "import sys; print(sys.executable)" 2>$null); $r = Probar-Python "$exe".Trim(); if ($r) { return $r } } catch { }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return Probar-Python $cmd.Source }
    return $null
}
$py = Buscar-Python
if (-not $py) {
    Ojo "No encuentro Python."
    if (-not $Simular -and (SiNo "¿Lo instalo ahora con winget (Python 3.12)?")) {
        winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
        Refrescar-Path
        $py = Buscar-Python
    }
    if (-not $py) { Mal "Instala Python 3.10-3.13 desde https://www.python.org (marca 'Add python.exe to PATH') y vuelve a lanzar INSTALAR.bat."; exit 1 }
}
$v = [version]$py.Ver
if ($v -lt [version]"3.10" -or $v -ge [version]"3.14") {
    Mal "Tienes Python $($py.Ver). Whisper necesita Python 3.10 a 3.13. Instala uno de esos y vuelve a lanzar INSTALAR.bat."; exit 1
}
Bien "Python $($py.Ver): $($py.Exe)"
$python = $py.Exe

# ------------------------------------------------------------------ ffmpeg
Paso "2/6 ffmpeg (para convertir los audios)"
Refrescar-Path
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Bien "ffmpeg encontrado"
} else {
    Ojo "No encuentro ffmpeg."
    if (-not $Simular -and (SiNo "¿Lo instalo ahora con winget?")) {
        winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
        Refrescar-Path
    }
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Bien "ffmpeg instalado" }
    elseif (-not $Simular) { Mal "Instala ffmpeg (https://www.gyan.dev/ffmpeg/builds/) y ponlo en el PATH. Luego vuelve a lanzar INSTALAR.bat."; exit 1 }
}

# ------------------------------------------------------------------ Grafica, PyTorch y Whisper
Paso "3/6 Whisper (reconocimiento de voz)"
$gpu = $null; $vram = 0
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $linea = (nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | Select-Object -First 1)
    if ($linea) { $p = $linea.Split(","); $gpu = $p[0].Trim(); $vram = [int]$p[1].Trim() }
}
if ($gpu) { Bien "Grafica: $gpu ($([math]::Round($vram / 1024, 1)) GB)" } else { Ojo "No veo una grafica NVIDIA: Whisper ira con el procesador (mas lento y menos preciso)." }
# Modelo segun la memoria de video (en partida comparte la grafica con el juego).
$modelo = if (-not $gpu) { "base" } elseif ($vram -ge 6000) { "turbo" } elseif ($vram -ge 3500) { "small" } else { "base" }
Bien "Modelo de Whisper elegido: $modelo"

$tieneTorch = $false
try { & $python -c "import torch, whisper" 2>$null; $tieneTorch = ($LASTEXITCODE -eq 0) } catch { }
if ($tieneTorch) {
    $cuda = & $python -c "import torch; print(torch.cuda.is_available())" 2>$null
    Bien "PyTorch y Whisper ya estan instalados (grafica: $cuda)"
} elseif ($Simular) {
    Ojo "Instalaria PyTorch $(if ($gpu) { 'con CUDA' } else { 'para procesador' }) y openai-whisper (unos 3 GB)."
} else {
    Write-Host "   Se va a descargar PyTorch y Whisper (unos 3 GB). Puede tardar un rato." -ForegroundColor Gray
    & $python -m pip install --upgrade pip
    if ($gpu) {
        # Las RTX 50 necesitan CUDA 12.8; el resto, 12.6.
        $idx = if ($gpu -match "RTX 50|RTX PRO|Blackwell") { "cu128" } else { "cu126" }
        & $python -m pip install torch --index-url "https://download.pytorch.org/whl/$idx"
    } else {
        & $python -m pip install torch --index-url "https://download.pytorch.org/whl/cpu"
    }
    if ($LASTEXITCODE -ne 0) { Mal "No se pudo instalar PyTorch."; exit 1 }
    & $python -m pip install -r (Join-Path $kit "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Mal "No se pudo instalar Whisper."; exit 1 }
    Bien "PyTorch y Whisper instalados"
}
if (-not $Simular -and (SiNo "¿Descargo ya el modelo '$modelo' de Whisper? (si no, se descarga solo la primera partida)")) {
    & $python -W ignore -c "import whisper; whisper.load_model('$modelo', device='cpu'); print('   modelo listo')"
}

# ------------------------------------------------------------------ Lethal Company
Paso "4/6 Lethal Company"
function Buscar-Juego {
    $steam = $null
    try { $steam = (Get-ItemProperty "HKCU:\Software\Valve\Steam" -ErrorAction Stop).SteamPath } catch { }
    if (-not $steam) { return $null }
    $libs = @($steam.Replace("/", "\"))
    $vdf = Join-Path $steam "steamapps\libraryfolders.vdf"
    if (Test-Path $vdf) {
        foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) { $libs += $m.Groups[1].Value.Replace("\\", "\") }
    }
    foreach ($lib in $libs | Select-Object -Unique) {
        $c = Join-Path $lib "steamapps\common\Lethal Company"
        if (Test-Path (Join-Path $c "Lethal Company.exe")) { return $c }
    }
    return $null
}
$juego = Buscar-Juego
if ($juego) { Bien "Encontrado: $juego" }
while (-not $juego -or -not (Test-Path (Join-Path $juego "Lethal Company.exe"))) {
    $juego = Pregunta "No lo encuentro. Pega la carpeta de Lethal Company (la que tiene 'Lethal Company.exe')" ""
    if (-not $juego) { Mal "Sin la carpeta del juego no puedo seguir."; exit 1 }
}

# Nombre de Steam: el que se usa en el juego (el de la cuenta con la que entraste la ultima vez)
$sugerido = ""
try {
    $steam = (Get-ItemProperty "HKCU:\Software\Valve\Steam").SteamPath
    $lu = Get-Content (Join-Path $steam "config\loginusers.vdf") -Raw
    $masReciente = -1
    foreach ($b in [regex]::Matches($lu, '"\d{17}"\s*\{([^}]*)\}')) {
        $t = $b.Groups[1].Value
        # La cuenta usada por ultima vez: "MostRecent" en unas versiones de Steam, la "timestamp" mas alta en otras.
        $cuando = if ($t -match '"MostRecent"\s+"1"') { [long]::MaxValue } elseif ($t -match '"timestamp"\s+"(\d+)"') { [long]$Matches[1] } else { 0 }
        if ($cuando -gt $masReciente -and $t -match '"PersonaName"\s+"([^"]+)"') { $sugerido = $Matches[1]; $masReciente = $cuando }
    }
} catch { }
$nombre = Pregunta "Tu nombre de Steam tal cual sale en el juego" $sugerido
Bien "Nombre: $nombre"

# ------------------------------------------------------------------ config.json
Paso "5/6 Configuracion del kit"
if ($Simular) {
    Ojo "Escribiria en config.json: carpeta_juego=$juego, mi_nombre_steam=$nombre, modelo_whisper=$modelo"
} else {
    $env:MV_JUEGO = $juego.Replace("\", "/"); $env:MV_NOMBRE = $nombre; $env:MV_MODELO = $modelo
    & $python -c @"
import json, os, re
p = os.path.join(r'$kit', 'config.json')
s = open(p, encoding='utf-8').read()
for clave, valor in (('carpeta_juego', os.environ['MV_JUEGO']), ('mi_nombre_steam', os.environ['MV_NOMBRE']),
                     ('modelo_whisper', os.environ['MV_MODELO'])):
    s = re.sub(r'("%s":\s*)"[^"]*"' % clave, lambda m: m.group(1) + json.dumps(valor, ensure_ascii=False), s, count=1)
json.loads(s)
open(p, 'w', encoding='utf-8').write(s)
"@
    if ($LASTEXITCODE -ne 0) { Mal "No se pudo escribir config.json"; exit 1 }
    Bien "config.json listo"
}

# ------------------------------------------------------------------ Perfil del mod manager
Paso "6/6 Mod (perfil del mod manager)"
$raices = @(
    @{ App = "Thunderstore Mod Manager"; Dir = Join-Path $env:APPDATA "Thunderstore Mod Manager\DataFolder\LethalCompany\profiles" },
    @{ App = "r2modman"; Dir = Join-Path $env:APPDATA "r2modmanPlus-local\LethalCompany\profiles" },
    @{ App = "Gale"; Dir = Join-Path $env:APPDATA "com.kesomannen.gale\lethal-company\profiles" }
)
$perfiles = @()
foreach ($r in $raices) {
    if (-not (Test-Path $r.Dir)) { continue }
    foreach ($d in Get-ChildItem $r.Dir -Directory) {
        $plugins = Join-Path $d.FullName "BepInEx\plugins"
        if (Test-Path $plugins) {
            $mod = Get-ChildItem $plugins -Recurse -Depth 1 -Filter "MirageVoces.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($mod) { $perfiles += [pscustomobject]@{ Nombre = "$($r.App): $($d.Name)"; Dir = $d.FullName } }
        }
    }
}
if (Test-Path (Join-Path $juego "BepInEx\plugins")) {
    $mod = Get-ChildItem (Join-Path $juego "BepInEx\plugins") -Recurse -Depth 1 -Filter "MirageVoces.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($mod) { $perfiles += [pscustomobject]@{ Nombre = "BepInEx instalado en el juego"; Dir = $juego } }
}
if ($perfiles.Count -eq 0) {
    Mal "No encuentro ningun perfil con MirageVoces instalado."
    Write-Host "   Instala MirageVoces (y Mirage) desde tu mod manager, abre el juego una vez y vuelve a lanzar INSTALAR.bat." -ForegroundColor Gray
    exit 1
}
$elegidos = $perfiles
if ($perfiles.Count -gt 1) {
    Write-Host "   Perfiles con MirageVoces:"
    for ($i = 0; $i -lt $perfiles.Count; $i++) { Write-Host "     $($i + 1)) $($perfiles[$i].Nombre)" }
    $r = Pregunta "¿En cual lo preparo? (numero, o 'todos')" "1"
    if ($r -ne "todos") { $elegidos = @($perfiles[[int]$r - 1]) }
}
$script = Join-Path $kit "mirage_vivo.py"
foreach ($p in $elegidos) {
    $destino = Join-Path $p.Dir "BepInEx\plugins\MirageVoces-Anfitrion"
    $cfg = Join-Path $p.Dir "BepInEx\config\lloreria.miragevoces.cfg"
    if ($Simular) { Ojo "En '$($p.Nombre)': copiaria el plugin a $destino y pondria Script/Python en $cfg"; continue }
    New-Item -ItemType Directory -Force $destino | Out-Null
    Copy-Item (Join-Path $kit "plugin\MirageVoces.Anfitrion.dll") $destino -Force
    # La configuracion del mod: donde esta el script de Whisper en vivo y que Python usar.
    if (Test-Path $cfg) {
        $texto = Get-Content $cfg -Raw -Encoding UTF8
        $texto = [regex]::Replace($texto, '(?m)^Script = .*$', "Script = $script")
        $texto = [regex]::Replace($texto, '(?m)^Python = .*$', "Python = $python")
    } else {
        New-Item -ItemType Directory -Force (Split-Path $cfg) | Out-Null
        $texto = "[Whisper en vivo]`r`n`r`nPython = $python`r`n`r`nScript = $script`r`n"
    }
    [IO.File]::WriteAllText($cfg, $texto, (New-Object System.Text.UTF8Encoding($false)))
    Bien "Listo en '$($p.Nombre)'"
}

Write-Host "`nTODO LISTO" -ForegroundColor Green
Write-Host @"
   Que hacer ahora:
   1. Rellena apodos.txt con los nombres de Steam y apodos de tu grupo (opcional, pero mejora mucho).
   2. Abre Lethal Company desde ese perfil y haz de anfitrion: Whisper arranca solo.
   3. Si quieres ver lo que entiende en directo: 'Ver Whisper en vivo.bat'.
   Avisa a tu grupo: el anfitrion graba lo que se dice por el chat de voz. Hacedlo solo si todos estan de acuerdo.
"@ -ForegroundColor Gray
