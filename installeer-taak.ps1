# Zet de wekelijkse taak in de Windows Taakplanner.
# Eenmalig draaien, als beheerder:   .\installeer-taak.ps1
# Verwijderen:                       .\installeer-taak.ps1 -Verwijder

param(
    [switch]$Verwijder,
    [string]$Tijd = '09:00',
    [string]$TaakNaam = 'Hitlijsten verzamelen'
)

$ErrorActionPreference = 'Stop'
$map = $PSScriptRoot

if ($Verwijder) {
    Unregister-ScheduledTask -TaskName $TaakNaam -Confirm:$false
    Write-Host "Taak '$TaakNaam' verwijderd."
    return
}

$python = 'C:\Python313\pythonw.exe'   # pythonw: geen console-venster
if (-not (Test-Path $python)) { $python = 'C:\Python313\python.exe' }

$actie = New-ScheduledTaskAction -Execute $python `
                                 -Argument '-m hitlijsten run' `
                                 -WorkingDirectory $map

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At $Tijd

# StartWhenAvailable: stond de pc vrijdag uit, dan draait de taak alsnog zodra
# hij weer aan gaat -- hij wacht niet tot de volgende vrijdag. De run haalt
# vervolgens ELKE ontbrekende week op, niet alleen de nieuwste, dus een paar
# gemiste weken halen zichzelf in. Ook een gemiste jaarwisseling: de run vult
# de afgekapte staart van de vorige jaargang aan.
#
# Grens: dit werkt zolang de bronsites die weken nog in hun archief hebben (dat
# gaat decennia terug). Heeft de pc echt lang stilgestaan, gebruik dan
# 'python -m hitlijsten historie --vanaf <jaar>'; die is gebouwd om hele
# jaargangen op te halen met de pauzes die daarbij horen.
$instellingen = New-ScheduledTaskSettingsSet -StartWhenAvailable `
                                             -DontStopIfGoingOnBatteries `
                                             -AllowStartIfOnBatteries `
                                             -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaakNaam `
                       -Action $actie `
                       -Trigger $trigger `
                       -Settings $instellingen `
                       -Description 'Haalt de vier hitlijsten op, bouwt de Excel-bestanden en mailt de nieuwe binnenkomers.' `
                       -Force | Out-Null

Write-Host "Taak '$TaakNaam' aangemaakt: elke vrijdag om $Tijd."
Write-Host "Handmatig testen:  Start-ScheduledTask -TaskName '$TaakNaam'"
