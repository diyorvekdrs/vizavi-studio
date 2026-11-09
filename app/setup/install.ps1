# Vizavi Studio installer (Windows 10 1809+ / 11, 64-bit). Run by "Install Vizavi Studio.cmd".
# Installs Python 3.12 if no suitable Python exists, the Microsoft C++ runtime if missing, copies the app
# to a short ASCII path, creates the app's own Python environment, settings, shortcuts and an
# "Apps & features" entry, then starts the app (whose first start installs the rest for this PC).
# Plain ASCII on purpose: Windows PowerShell 5 reads scripts in the system code page.
param([string]$Source = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
try { $Host.UI.RawUI.WindowTitle = 'Vizavi Studio setup' } catch {}

function Say($t) { Write-Host "  $t" }
function Step($t) { Write-Host ""; Write-Host "  $t" -ForegroundColor Cyan }
function Fail($t) {
    Write-Host ""; Write-Host "  $t" -ForegroundColor Red; Write-Host ""
    Read-Host "  Press Enter to close" | Out-Null; exit 1
}

Write-Host ""
Write-Host "  Vizavi Studio setup" -ForegroundColor White
Write-Host "  -------------------"

# ---------------------------------------------------------------- this PC
if (-not [Environment]::Is64BitOperatingSystem) { Fail "This PC runs 32-bit Windows. Vizavi Studio needs 64-bit Windows 10 or 11." }
$build = [Environment]::OSVersion.Version.Build
if ($build -lt 17763) { Fail "Windows is too old (build $build). Update to Windows 10 version 1809 or newer, or Windows 11." }
if (-not (Test-Path (Join-Path $Source 'Vizavi Studio.pyw'))) { Fail "The app files were not found next to the installer. Extract the whole zip first, then run the installer again." }

# Short path: some Python packages have very long file names. Plain Latin path: some speech libraries
# cannot open models under user names with other letters.
$dest = Join-Path $env:LOCALAPPDATA 'VizaviStudio'
if ($dest -match '[^\x20-\x7E]') { $dest = 'C:\VizaviStudio' }
$same = (Resolve-Path $Source).Path.TrimEnd('\') -eq $dest.TrimEnd('\')

$drive = (Split-Path -Qualifier $dest).TrimEnd(':')
$free = [math]::Round((Get-PSDrive $drive).Free / 1GB, 1)
if ($free -lt 6) { Fail "Only $free GB free on drive ${drive}:. Free at least 15 GB, then run the installer again." }
if ($free -lt 15) { Say "Note: only $free GB free on ${drive}:. 15 GB or more is recommended (speech models and renders)." }

$arch = $env:PROCESSOR_ARCHITECTURE
if ($arch -eq 'ARM64') { Say "Note: this is an ARM PC. The app runs through Windows' x64 emulation and will be slower." }

try { Invoke-WebRequest 'https://pypi.org/simple/pip/' -UseBasicParsing -Method Head -TimeoutSec 15 | Out-Null }
catch { Say "Warning: pypi.org could not be reached. The first start needs internet to download components." }

Get-ChildItem -LiteralPath $Source -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- Python 3.10 - 3.13 (64-bit)
Step "Looking for Python..."
function PyOk($exe) {
    try {
        $v = & $exe -c "import sys,struct;print('%d.%d|%d' % (sys.version_info[0], sys.version_info[1], struct.calcsize('P')*8))" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $v) { return $false }
        $mm, $bits = "$v".Trim().Split('|')
        return ($bits -eq '64') -and (@('3.10', '3.11', '3.12', '3.13') -contains $mm)
    } catch { return $false }
}
$py = $null
foreach ($v in '3.12', '3.13', '3.11', '3.10') {
    $n = $v -replace '\.', ''
    $cands = @("$env:LOCALAPPDATA\Programs\Python\Python$n\python.exe", "$env:ProgramFiles\Python$n\python.exe")
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try { $p = & py "-$v" -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { $cands = @("$p".Trim()) + $cands } } catch {}
    }
    foreach ($c in $cands) { if ($c -and (Test-Path $c) -and (PyOk $c)) { $py = $c; break } }
    if ($py) { break }
}
if ($py) {
    Say "Using $py"
} else {
    Say "Installing Python 3.12 just for this user (about 30 MB, one time)..."
    $target = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try { & winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Null } catch {}
    }
    if (-not (Test-Path $target)) {
        $exe = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
        try {
            Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $exe -UseBasicParsing
            Start-Process $exe -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=0', 'Include_test=0', 'Shortcuts=0', 'AssociateFiles=0' -Wait
        } catch { }
    }
    if ((Test-Path $target) -and (PyOk $target)) { $py = $target; Say "Python installed." }
    else { Fail "Python could not be installed automatically. Install Python 3.12 (64-bit) from python.org, then run this installer again." }
}

# ---------------------------------------------------------------- Microsoft C++ runtime (PyTorch, CuPy need it)
$vc = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue
if (-not $vc -or -not $vc.Installed -or [int]$vc.Major -lt 14 -or ([int]$vc.Major -eq 14 -and [int]$vc.Minor -lt 40)) {
    Step "Installing the Microsoft Visual C++ runtime (speech models need it)..."
    Say "Windows will ask for permission - click Yes."
    $vcexe = Join-Path $env:TEMP 'vc_redist.x64.exe'
    try {
        Invoke-WebRequest 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile $vcexe -UseBasicParsing
        Start-Process $vcexe -ArgumentList '/install', '/quiet', '/norestart' -Verb RunAs -Wait
        Say "Done."
    } catch {
        Say "Skipped ($($_.Exception.Message)). If speech models fail later, install 'Microsoft Visual C++ Redistributable x64' from microsoft.com."
    }
}

# ---------------------------------------------------------------- app files
Step "Installing the app to $dest ..."
Get-Process python, pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$dest\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $dest | Out-Null
if (-not $same) {
    & robocopy $Source $dest /E /NFL /NDL /NJH /NJS /NP /R:2 /W:1 /XD Projects .venv models .ui_profile .incoming .update __pycache__ /XF settings.json .deps_ok .setup_done .cuda_libs_ok .chromium_ok .torch_cuda_tried .deps_lock.txt .session_token .last_alive | Out-Null
    if ($LASTEXITCODE -ge 8) { Fail "Copying the app failed (robocopy code $LASTEXITCODE). Close Vizavi Studio if it is open and try again." }
    if (Test-Path (Join-Path $Source 'Projects')) {
        Say "Note: the Projects folder inside $Source was NOT copied. To keep those projects, move that folder's contents to the projects folder the app uses (Settings > Projects folder)."
    }
}

# the app's own Python environment: the friend's other Python things can't break it, and it can't break them
$venv = Join-Path $dest '.venv'
$vpy = Join-Path $venv 'Scripts\python.exe'
$vpyw = Join-Path $venv 'Scripts\pythonw.exe'
if (-not (Test-Path $vpy)) {
    Say "Creating the app's own Python environment..."
    & $py -m venv $venv
    if (-not (Test-Path $vpy)) { Fail "Could not create the Python environment in $venv." }
}
try { & $vpy -m pip install --upgrade --disable-pip-version-check --quiet pip 2>$null | Out-Null } catch {}

# settings: projects outside cloud-synced folders (renders are big), models next to the app
$sf = Join-Path $dest 'settings.json'
if (-not (Test-Path $sf)) {
    $videos = [Environment]::GetFolderPath('MyVideos')
    if (-not $videos -or $videos -match 'OneDrive') { $videos = $env:USERPROFILE }
    $cfg = [ordered]@{ projects_dir = (Join-Path $videos 'Vizavi Studio'); models_dir = (Join-Path $dest 'models') }
    [IO.File]::WriteAllText($sf, ($cfg | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
}

# ---------------------------------------------------------------- shortcuts + Apps & features entry
Step "Creating shortcuts..."
$ico = Join-Path $dest 'studio\vizavi.ico'
$pyw = Join-Path $dest 'Vizavi Studio.pyw'
$w = New-Object -ComObject WScript.Shell
foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('SendTo'))) {
    try {
        $s = $w.CreateShortcut((Join-Path $d 'Vizavi Studio.lnk'))
        $s.TargetPath = $vpyw; $s.Arguments = "`"$pyw`""; $s.WorkingDirectory = $dest
        if (Test-Path $ico) { $s.IconLocation = $ico }
        $s.Save()
    } catch { Say "Shortcut in $d skipped." }
}
Set-Content -LiteralPath (Join-Path $dest '.setup_done') -Value 'ok' -Encoding Ascii

$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VizaviStudio'
New-Item -Path $key -Force | Out-Null
$un = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$dest\setup\uninstall.ps1`""
$ver = '2'
try { $ver = ((Get-Content -Raw (Join-Path $dest 'studio\version.py')) | Select-String 'VERSION = "([^"]+)"').Matches[0].Groups[1].Value } catch {}
$props = @{ DisplayName = 'Vizavi Studio'; DisplayVersion = $ver; Publisher = 'Vizavi'; InstallLocation = $dest;
            UninstallString = $un; DisplayIcon = $ico }
foreach ($k in $props.Keys) { New-ItemProperty -Path $key -Name $k -Value $props[$k] -PropertyType String -Force | Out-Null }
foreach ($k in 'NoModify', 'NoRepair') { New-ItemProperty -Path $key -Name $k -Value 1 -PropertyType DWord -Force | Out-Null }

# ---------------------------------------------------------------- start
Step "Starting Vizavi Studio"
Say "The first start checks this PC and installs what it can use (5-30 minutes, needs internet)."
Say "Keep the Vizavi Studio window open until it says Ready. Later starts are instant."
Start-Process -FilePath $vpyw -ArgumentList "`"$pyw`"" -WorkingDirectory $dest
Write-Host ""
Write-Host "  Installed. You can close this window." -ForegroundColor Green
Start-Sleep -Seconds 6
