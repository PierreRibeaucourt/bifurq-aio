# Installe (ou retire) la tache planifiee Windows de Bifurq AIO (veille des adresses inventees).
# Appele par veille_ia.scheduler_windows, jamais directement par l'utilisateur final.
#
# Installer :
#   powershell -File planifier.ps1 -NomTache "..." -CheminPythonw "...\pythonw.exe" `
#       -CheminScript "...\lancer_veille.pyw" [-AuDemarrage] [-HeureFixe] [-Heure "09:15"]
# Retirer :
#   powershell -File planifier.ps1 -NomTache "..." -Desinstaller
param(
    [Parameter(Mandatory = $true)][string]$NomTache,
    [string]$CheminPythonw,
    [string]$CheminScript,
    [string]$DossierTravail,
    [switch]$AuDemarrage,
    [switch]$HeureFixe,
    [string]$Heure = "09:15",
    [switch]$Desinstaller
)

if ($Desinstaller) {
    if (Get-ScheduledTask -TaskName $NomTache -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $NomTache -Confirm:$false
        "tache retiree : $NomTache"
    } else {
        "aucune tache a retirer : $NomTache"
    }
    exit 0
}

if (-not $CheminPythonw -or -not $CheminScript) { throw "CheminPythonw et CheminScript sont requis pour installer" }
if (-not $AuDemarrage -and -not $HeureFixe) { throw "au moins -AuDemarrage ou -HeureFixe doit etre indique" }
if (-not $DossierTravail) { $DossierTravail = Split-Path -Parent $CheminScript }

$compte = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$action = New-ScheduledTaskAction -Execute $CheminPythonw -Argument ('"' + $CheminScript + '"') -WorkingDirectory $DossierTravail
# LogonType Interactive + RunLevel Limited : necessaire pour que les toasts Windows
# s'affichent (une tache SYSTEM ne peut pas notifier la session ouverte).
$reglages = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew

$triggers = @()
if ($AuDemarrage) {
    $t = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $t.Delay = "PT2M"          # laisse le reseau et Python le temps d'etre prets
    $triggers += $t
}
if ($HeureFixe) {
    $triggers += New-ScheduledTaskTrigger -Daily -At $Heure
}

Register-ScheduledTask -TaskName $NomTache -Action $action -Trigger $triggers -Settings $reglages `
    -Principal $compte -Force -Description "Bifurq AIO : veille des adresses inventees par l'IA de Google. Script : $CheminScript" | Out-Null

$i = Get-ScheduledTask -TaskName $NomTache | Get-ScheduledTaskInfo
"{0} installee | prochaine execution {1}" -f $NomTache, $i.NextRunTime
