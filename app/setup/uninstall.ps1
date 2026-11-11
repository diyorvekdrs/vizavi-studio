# Removes Vizavi Studio (the app, its Python environment, downloaded models, shortcuts).
# Projects (videos) stay where they are. Plain ASCII on purpose (Windows PowerShell 5).
$ErrorActionPreference = 'Continue'
$dest = Split-Path -Parent $PSScriptRoot
$projects = $null; $models = $null; $cache = $null
try {
    $cfg = Get-Content -Raw (Join-Path $dest 'settings.json') | ConvertFrom-Json
    $projects = $cfg.projects_dir; $models = $cfg.models_dir; $cache = $cfg.cache_dir
} catch {}
function GB($p) { try { return [math]::Round(((Get-ChildItem $p -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1GB, 1) } catch { return 0 } }

# projects that live INSIDE the app folder would be deleted with it: move them out first
$inside = $false
if ($projects) { try { $inside = ([IO.Path]::GetFullPath($projects).TrimEnd('\') + '\').StartsWith(([IO.Path]::GetFullPath($dest).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase) } catch {} }
if (-not $projects) { $projects = Join-Path $dest 'Projects'; $inside = Test-Path $projects }

Write-Host ""
Write-Host "  Uninstall Vizavi Studio" -ForegroundColor White
Write-Host ""
Write-Host "  This removes the app from $dest"
Write-Host "  (including its Python environment)."
if ($inside) { Write-Host "  Your projects are inside the app folder: they will be MOVED to your Documents folder first." }
elseif ($projects) { Write-Host "  Your projects in $projects are NOT deleted." }
Write-Host ""
$a = Read-Host "  Type Y and press Enter to uninstall"
if ($a -notmatch '^[Yy]') { exit 0 }

Get-Process python, pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$dest\*" } | Stop-Process -Force
try { Get-CimInstance Win32_Process -Filter "Name='msedge.exe' OR Name='chrome.exe'" | Where-Object { $_.CommandLine -like "*$dest*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } } catch {}
Start-Sleep -Seconds 1
if ($inside -and (Test-Path -LiteralPath $projects)) {
    $keep = Join-Path ([Environment]::GetFolderPath('MyDocuments')) ('Vizavi Studio projects ' + (Get-Date -Format 'yyyy-MM-dd'))
    try {
        Move-Item -LiteralPath $projects -Destination $keep -ErrorAction Stop
        Write-Host "  Your projects were moved to $keep" -ForegroundColor Green
    } catch {
        Write-Host "  Could not move your projects out of $projects, so NOTHING was deleted." -ForegroundColor Yellow
        Write-Host "  Copy that folder somewhere safe, then run the uninstaller again."
        Start-Sleep -Seconds 8
        exit 1
    }
}
foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('SendTo'))) {
    Remove-Item -LiteralPath (Join-Path $d 'Vizavi Studio.lnk') -Force -ErrorAction SilentlyContinue
}
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VizaviStudio' -Recurse -Force -ErrorAction SilentlyContinue
Set-Location $env:TEMP
Remove-Item -LiteralPath $dest -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $dest) { Write-Host "  Some files are still in use. Restart the PC and delete $dest by hand." -ForegroundColor Yellow }
else { Write-Host "  Vizavi Studio was removed." -ForegroundColor Green }
# installed in a folder of your choice: its download cache goes too, the speech models only if you say so
if ($cache -and (Test-Path $cache)) { Remove-Item -LiteralPath $cache -Recurse -Force -ErrorAction SilentlyContinue }
if ($models -and (Test-Path $models)) {
    $mgb = GB $models
    $a = Read-Host "  Also delete the downloaded speech models in $models ($mgb GB)? A new install would download them again. [y/N]"
    if ($a -match '^[Yy]') { Remove-Item -LiteralPath $models -Recurse -Force -ErrorAction SilentlyContinue; Write-Host "  Speech models deleted." }
}
Write-Host "  (Chromium for the HTML engine stays in $env:LOCALAPPDATA\ms-playwright - delete it if no other app uses it.)"
Start-Sleep -Seconds 4
