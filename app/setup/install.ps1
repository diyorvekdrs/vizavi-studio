# Vizavi Studio installer (Windows 10 1809+ / 11, 64-bit). Run by "Install Vizavi Studio.cmd".
# Installs Python 3.12 if no suitable Python exists, the Microsoft C++ runtime if missing, copies the app
# to a short ASCII path, creates the app's own Python environment, settings, shortcuts and an
# "Apps & features" entry, then starts the app (whose first start installs the rest for this PC).
# Plain ASCII on purpose: Windows PowerShell 5 reads scripts in the system code page.
param([string]$Source = (Split-Path -Parent $PSScriptRoot), [string]$InstallDir = $env:VZ_INSTALL_DIR)

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

# ---------------------------------------------------------------- where to install
# Default: %LOCALAPPDATA%\VizaviStudio (drive C:). Any other folder works too - then EVERYTHING big goes there:
#   <folder>\app       the program + its Python environment (what the uninstaller removes)
#   <folder>\models    speech models (3-8 GB)        <folder>\Projects  your videos
#   <folder>\cache     download caches (pip, Chromium)
# Short plain-Latin paths only: some Python packages have very long file names and some speech libraries can't
# open paths with other letters.
function FreeGB($path) {
    try { $q = (Split-Path -Qualifier $path).TrimEnd(':'); return [math]::Round((Get-PSDrive $q -ErrorAction Stop).Free / 1GB, 1) } catch { return -1 }
}
$defaultDest = Join-Path $env:LOCALAPPDATA 'VizaviStudio'
if ($defaultDest -match '[^\x20-\x7E]') { $defaultDest = 'C:\VizaviStudio' }
$existing = $null
try { $existing = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VizaviStudio' -ErrorAction Stop).InstallLocation } catch {}
if ($existing -and -not (Test-Path (Join-Path $existing 'Vizavi Studio.pyw'))) { $existing = $null }
if (-not $existing -and (Test-Path (Join-Path $defaultDest 'Vizavi Studio.pyw'))) { $existing = $defaultDest }

function ResolveChoice($t) {
    $t = "$t".Trim().Trim('"')
    if (-not $t) { return $null }
    if ($t -match '^[A-Za-z]:?\\?$') { return ($t.Substring(0, 1).ToUpper() + ':\VizaviStudio') }
    try { $t = [IO.Path]::GetFullPath($t) } catch { return '' }
    if ((Test-Path $t) -and (Get-ChildItem -LiteralPath $t -Force -ErrorAction SilentlyContinue | Select-Object -First 1) `
        -and -not (Test-Path (Join-Path $t 'app\Vizavi Studio.pyw'))) { $t = Join-Path $t 'VizaviStudio' }   # an existing folder with other files in it
    return $t.TrimEnd('\')
}
function CheckBase($b) {
    if ($b -match '[^\x20-\x7E]') { return "Use a folder name with plain Latin letters only (no spaces in other alphabets)." }
    if ($b -match 'OneDrive') { return "Don't use a OneDrive folder - renders are big and would be uploaded." }
    if (-not (Test-Path (Split-Path -Qualifier $b))) { return "Drive $(Split-Path -Qualifier $b) does not exist." }
    $f = FreeGB $b
    if ($f -ge 0 -and $f -lt 6) { return "Only $f GB free there. Pick a drive with at least 15 GB free." }
    try { New-Item -ItemType Directory -Force -Path $b -ErrorAction Stop | Out-Null } catch { return "Can't create $b ($($_.Exception.Message))." }
    return $null
}

$base = $null; $dest = $null
if ($InstallDir) {
    $base = ResolveChoice $InstallDir
    $err = CheckBase $base
    if ($err) { Fail $err }
} else {
    $drives = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction SilentlyContinue | Sort-Object DeviceID)
    $here = if ($existing) { $existing } else { $defaultDest }
    $hereFree = FreeGB $here
    $better = $drives | Where-Object { $_.DeviceID -ne (Split-Path -Qualifier $here) -and $_.FreeSpace / 1GB -ge 20 } |
              Sort-Object FreeSpace -Descending | Select-Object -First 1
    Write-Host ""
    Write-Host "  Where should Vizavi Studio go? It needs about 15 GB (program, speech models, renders)." -ForegroundColor White
    if ($existing) { Say "It is installed in $existing now." }
    Say ("  [Enter]  {0}   ({1} GB free)" -f $here, $hereFree)
    $others = ($drives | ForEach-Object { "{0} ({1:N0} GB free)" -f $_.DeviceID.TrimEnd(':'), ($_.FreeSpace / 1GB) }) -join ',  '
    if ($others) { Say "  or type a drive letter:  $others" }
    Say "  or type a folder, e.g. D:\Programs\VizaviStudio"
    if ($better -and $hereFree -lt 20) { Say ("  Recommended: {0} - there is little space on {1}" -f $better.DeviceID.TrimEnd(':'), (Split-Path -Qualifier $here)) }
    for ($try = 0; $try -lt 5; $try++) {
        $ans = Read-Host "  Your choice"
        if (-not "$ans".Trim()) { break }
        $cand = ResolveChoice $ans
        if (-not $cand) { Say "That is not a folder. Try again."; continue }
        $err = CheckBase $cand
        if ($err) { Say $err; continue }
        $base = $cand; break
    }
}
if ($base) {
    if ($existing -and ($existing.TrimEnd('\') -eq $base.TrimEnd('\') -or $existing.TrimEnd('\') -eq (Join-Path $base 'app'))) {
        $dest = $existing; $base = $null                  # same place as now: just update
    } else {
        $dest = Join-Path $base 'app'
    }
} else {
    $dest = if ($existing) { $existing } else { $defaultDest }
}
$custom = [bool]$base
$same = (Resolve-Path $Source).Path.TrimEnd('\') -eq $dest.TrimEnd('\')
$moving = $existing -and ($existing.TrimEnd('\') -ne $dest.TrimEnd('\'))

$drive = (Split-Path -Qualifier $dest).TrimEnd(':')
$free = FreeGB $dest
if ($free -ge 0 -and $free -lt 6) { Fail "Only $free GB free on drive ${drive}:. Free at least 15 GB, or run the installer again and pick another drive." }
if ($free -ge 0 -and $free -lt 15) { Say "Note: only $free GB free on ${drive}:. 15 GB or more is recommended (speech models and renders)." }

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
if ($moving) {
    # moving from another folder: take the installed components along instead of downloading them again
    Get-Process python, pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$existing\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    $oldVenv = Join-Path $existing '.venv'
    if ((Test-Path $oldVenv) -and -not (Test-Path $vpy)) {
        Say "Moving the installed components from $existing (a minute or two)..."
        & robocopy $oldVenv $venv /E /MOVE /NFL /NDL /NJH /NJS /NP /R:2 /W:1 | Out-Null
        $ok = $false
        try { & $vpy -c "import numpy" 2>$null; $ok = ($LASTEXITCODE -eq 0) } catch {}
        if (-not $ok) { Say "They didn't work in the new place - they will be installed again."; Remove-Item -Recurse -Force $venv -ErrorAction SilentlyContinue }
    }
    # (.deps_ok is left behind on purpose: the first start checks the components once in the new place)
    foreach ($m in '.cuda_libs_ok', '.setup_done', '.deps_lock.txt', '.torch_cuda_tried') {
        if (Test-Path (Join-Path $existing $m)) { Copy-Item (Join-Path $existing $m) (Join-Path $dest $m) -Force -ErrorAction SilentlyContinue }
    }
}
if (-not (Test-Path $vpy)) {
    Say "Creating the app's own Python environment..."
    & $py -m venv $venv
    if (-not (Test-Path $vpy)) { Fail "Could not create the Python environment in $venv." }
}
try { & $vpy -m pip install --upgrade --disable-pip-version-check --quiet pip 2>$null | Out-Null } catch {}

# settings: projects outside cloud-synced folders (renders are big). On the default drive the speech models stay in
# the shared cache in the user profile; in a folder of your choice everything goes into that folder.
$sf = Join-Path $dest 'settings.json'
$cfg = $null
if (Test-Path $sf) { try { $cfg = Get-Content -Raw $sf | ConvertFrom-Json } catch {} }
elseif ($moving -and (Test-Path (Join-Path $existing 'settings.json'))) {
    try { $cfg = Get-Content -Raw (Join-Path $existing 'settings.json') | ConvertFrom-Json } catch {}
}
if (-not $cfg) {
    $videos = [Environment]::GetFolderPath('MyVideos')
    if (-not $videos -or $videos -match 'OneDrive') { $videos = $env:USERPROFILE }
    $cfg = [pscustomobject]@{ projects_dir = (Join-Path $videos 'Vizavi Studio') }
    if ($custom) { $cfg.projects_dir = Join-Path $base 'Projects' }
}
if ($custom) {
    foreach ($k in @(@('models_dir', (Join-Path $base 'models')), @('cache_dir', (Join-Path $base 'cache')))) {
        $cfg | Add-Member -NotePropertyName $k[0] -NotePropertyValue $k[1] -Force
        New-Item -ItemType Directory -Force -Path $k[1] | Out-Null
    }
}
# projects (renders are big) on another drive than the chosen folder: offer to move them along
if ($custom -and $cfg.projects_dir -and (Test-Path $cfg.projects_dir) -and
    ((Split-Path -Qualifier $cfg.projects_dir) -ne (Split-Path -Qualifier $base))) {
    $pgb = [math]::Round(((Get-ChildItem $cfg.projects_dir -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1GB, 1)
    if ($pgb -gt 0) {
        $a = Read-Host "  Move your projects ($pgb GB) from $($cfg.projects_dir) to $(Join-Path $base 'Projects') too? [y/N]"
        if ($a -match '^[Yy]') {
            & robocopy $cfg.projects_dir (Join-Path $base 'Projects') /E /MOVE /NFL /NDL /NJH /NJS /NP /R:2 /W:1 | Out-Null
            if ($LASTEXITCODE -lt 8) { $cfg.projects_dir = Join-Path $base 'Projects'; Say "Projects moved." }
            else { Say "Some projects could not be moved (files in use?) - they stay where they were." }
        }
    }
}
[IO.File]::WriteAllText($sf, ($cfg | ConvertTo-Json -Depth 8), (New-Object Text.UTF8Encoding $false))

# speech models already downloaded on C: move along to the new folder (only Vizavi's own models)
if ($custom) {
    $mdir = Join-Path $base 'models'
    $hub = Join-Path $env:USERPROFILE '.cache\huggingface\hub'
    $mine = @()
    if (Test-Path $hub) { $mine += Get-ChildItem $hub -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^models--(Systran--faster-whisper|islomov--rubaistt|MahmoudAshraf--mms-300m)' } }
    foreach ($d in @((Join-Path $env:USERPROFILE '.cache\huggingface\vizavi'), $(if ($existing) { Join-Path $existing 'models' }))) {
        if ($d -and (Test-Path $d)) { $mine += Get-ChildItem $d -Directory -ErrorAction SilentlyContinue }
    }
    $mine = @($mine | Where-Object { $_.FullName.TrimEnd('\') -ne $mdir.TrimEnd('\') -and -not (Test-Path (Join-Path $mdir $_.Name)) })
    if ($mine.Count -gt 0) {
        $gb = [math]::Round((($mine | ForEach-Object { (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }) | Measure-Object -Sum).Sum / 1GB, 1)
        if ((Split-Path -Qualifier $mine[0].FullName) -ne (Split-Path -Qualifier $mdir)) {
            $a = Read-Host "  Move the speech models already on this PC ($gb GB) to $mdir ? [Y/n]"
        } else { $a = 'y' }
        if ($a -notmatch '^[Nn]') {
            foreach ($d in $mine) { & robocopy $d.FullName (Join-Path $mdir $d.Name) /E /MOVE /NFL /NDL /NJH /NJS /NP /R:2 /W:1 | Out-Null }
            Say "Speech models moved ($gb GB)."
        }
    }
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

# ---------------------------------------------------------------- the old copy (when it was moved to another folder)
if ($moving -and (Test-Path $existing)) {
    $oldGB = [math]::Round(((Get-ChildItem $existing -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1GB, 1)
    $a = Read-Host "  Delete the old copy in $existing ($oldGB GB)? Your projects are not in it. [Y/n]"
    if ($a -notmatch '^[Nn]') {
        $oldProj = Join-Path $existing 'Projects'
        if (Test-Path $oldProj) { & robocopy $oldProj (Join-Path (Split-Path -Parent $dest) 'Projects (old install)') /E /MOVE /NFL /NDL /NJH /NJS /NP | Out-Null }
        Remove-Item -LiteralPath $existing -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path $existing) { Say "Some old files are in use - delete $existing by hand after a restart." } else { Say "Old copy deleted ($oldGB GB freed)." }
    }
}

# ---------------------------------------------------------------- start
Step "Starting Vizavi Studio"
Say "The first start checks this PC and installs what it can use (5-30 minutes, needs internet)."
Say "Keep the Vizavi Studio window open until it says Ready. Later starts are instant."
Start-Process -FilePath $vpyw -ArgumentList "`"$pyw`"" -WorkingDirectory $dest
Write-Host ""
Write-Host "  Installed. You can close this window." -ForegroundColor Green
Start-Sleep -Seconds 6
