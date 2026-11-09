# Vizavi Studio - one-line installer.
#   Open PowerShell and run:
#   irm https://raw.githubusercontent.com/diyorvekdrs/vizavi-studio/main/get.ps1 | iex
# It downloads the newest version from GitHub, checks it is not damaged, unpacks it to a temporary
# folder and runs the normal installer. Nothing else is changed. Plain ASCII (Windows PowerShell 5).
& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
    $base = 'https://github.com/diyorvekdrs/vizavi-studio/releases/latest/download'
    $name = 'Vizavi-Studio-Setup.zip'
    $tmp = Join-Path $env:TEMP ('VizaviStudioSetup_' + [Guid]::NewGuid().ToString('N').Substring(0, 8))

    Write-Host ""
    Write-Host "  Vizavi Studio - quick install" -ForegroundColor White
    Write-Host "  -----------------------------"
    try {
        New-Item -ItemType Directory -Force -Path $tmp | Out-Null
        $zip = Join-Path $tmp $name
        Write-Host "  Downloading the newest version from GitHub..."
        Invoke-WebRequest "$base/$name" -OutFile $zip -UseBasicParsing
        $sums = (Invoke-WebRequest "$base/SHA256SUMS.txt" -UseBasicParsing).Content
        if ($sums -is [byte[]]) { $sums = [Text.Encoding]::ASCII.GetString($sums) }
        $want = $null
        foreach ($line in ($sums -split "`n")) {
            $p = $line.Trim() -split '\s+'
            if ($p.Count -ge 2 -and $p[-1].TrimStart('*') -eq $name) { $want = $p[0].ToLower() }
        }
        $got = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
        if (-not $want -or $want -ne $got) { throw "The download is damaged (checksum mismatch). Please try again." }
        Write-Host "  Download checked. Unpacking..."
        Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
        $installer = Join-Path $tmp 'app\setup\install.ps1'
        if (-not (Test-Path $installer)) { throw "The download does not contain the installer." }
        Get-ChildItem -LiteralPath $tmp -Recurse -File | Unblock-File -ErrorAction SilentlyContinue
        if ($env:VZ_DRYRUN -eq '1') {
            Write-Host "  (test run: would now start $installer)" -ForegroundColor Yellow
        } else {
            Write-Host "  Starting the installer..."
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer -Source (Join-Path $tmp 'app')
        }
    } catch {
        Write-Host ""
        Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  You can also download the zip from https://github.com/diyorvekdrs/vizavi-studio/releases/latest"
        Write-Host ""
        if ($env:VZ_DRYRUN -ne '1') { Read-Host "  Press Enter to close" | Out-Null }
    } finally {
        if ($env:VZ_DRYRUN -ne '1') { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
        else { Write-Host "  (test run: files left in $tmp)" }
    }
}
