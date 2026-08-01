# Wekelijkse run: ontbrekende weken ophalen, Excel-bestanden herbouwen, mailen.
# Wordt door de Taakplanner op vrijdag gestart, maar je kunt hem ook zelf draaien.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$python = 'C:\Python313\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

& $python -m hitlijsten run
exit $LASTEXITCODE
