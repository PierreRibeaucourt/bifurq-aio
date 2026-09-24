# Notification Windows (toast natif). Un clic ouvre le rapport s'il est donné.
# Usage : powershell -NoProfile -ExecutionPolicy Bypass -File notifier.ps1 -Titre "..." -Texte "..." [-Rapport "C:\...\rapport.html"]
param(
    [Parameter(Mandatory = $true)][string]$Titre,
    [Parameter(Mandatory = $true)][string]$Texte,
    [string]$Rapport = ""
)
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

function Echapper([string]$s) { return [System.Security.SecurityElement]::Escape($s) }

$lancer = ""
if ($Rapport -ne "") {
    $uri = ([System.Uri]$Rapport).AbsoluteUri
    $lancer = " activationType=""protocol"" launch=""$(Echapper $uri)"""
}
$xml = @"
<toast$lancer>
  <visual>
    <binding template="ToastGeneric">
      <text>$(Echapper $Titre)</text>
      <text>$(Echapper $Texte)</text>
    </binding>
  </visual>
</toast>
"@
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
# Identifiant d'application de Windows PowerShell, present sur tout poste Windows 10 et 11 :
# permet d'afficher un toast sans enregistrer d'identite d'application dediee.
$appli = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appli).Show($toast)
