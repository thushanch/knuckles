# Wraps the artifact body-fragments into standalone HTML documents and
# rewrites the hosted cross-links to local relative paths.
# Run:  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"

$scratch = "C:\Users\thush\AppData\Local\Temp\claude\C--Users-thush-OneDrive-Desktop-Knuckles\bcca4a23-1cf5-46b0-9081-ff2dd074dd49\scratchpad"
$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$APP_URL = "https://claude.ai/code/artifact/b1588c5a-e9ec-4026-8cbe-4c12d27d8037"

$pages = @(
  @{ src = "cadence.html";     out = "index.html"; desc = "Cadence - sex education for adults, from the anatomy up." },
  @{ src = "cadence-app.html"; out = "app.html";   desc = "Cadence Atlas - interactive clitoral anatomy, notation library, and overlap tool." }
)

foreach ($p in $pages) {
  $srcPath = Join-Path $scratch $p.src
  if (-not (Test-Path $srcPath)) { Write-Warning "missing $srcPath - skipped"; continue }

  $t = Get-Content $srcPath -Raw

  # hosted artifact links -> local file
  $t = $t.Replace($APP_URL, "app.html")

  $title = [regex]::Match($t, '(?s)<title>.*?</title>').Value
  $style = [regex]::Match($t, '(?s)<style>.*?</style>').Value
  $rest  = $t -replace '(?s)<title>.*?</title>', '' -replace '(?s)<style>.*?</style>', ''

  $head = @"
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="$($p.desc)">
$title
$style
</head>
<body>
"@

  $outPath = Join-Path $here $p.out
  Set-Content -Path $outPath -Value ($head + $rest.TrimStart() + "`n</body>`n</html>`n") -Encoding utf8
  "{0,-12} <- {1}  ({2:N0} bytes)" -f $p.out, $p.src, (Get-Item $outPath).Length
}
