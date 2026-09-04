# Regenerate docs/*.pdf from docs/src/*.html via headless Edge (or Chrome).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$browser = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $browser)) { $browser = "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe" }
if (-not (Test-Path $browser)) { $browser = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" }
if (-not (Test-Path $browser)) { throw "No Edge/Chrome found for headless PDF printing." }

$docs = @(
    @{ src = "architecture.html"; out = "ARCHITECTURE.pdf" },
    @{ src = "instructions.html"; out = "INSTRUCTIONS.pdf" },
    @{ src = "incidents.html";    out = "INCIDENTS.pdf" },
    @{ src = "presentation.html"; out = "PRESENTATION.pdf" }
)
foreach ($d in $docs) {
    $src = Join-Path $here "src\$($d.src)"
    $out = Join-Path $here $d.out
    if (Test-Path $out) { Remove-Item $out -Force }
    # cmd /c so Chromium's benign stderr chatter can't trip PowerShell's error handling
    cmd /c "`"$browser`" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=`"$out`" `"file:///$($src -replace '\\','/')`" 2>nul" | Out-Null
    if (Test-Path $out) { Write-Output ("{0}  ({1:N0} KB)" -f $d.out, ((Get-Item $out).Length/1KB)) }
    else { throw "failed: $($d.out)" }
}
