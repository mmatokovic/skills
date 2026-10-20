$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$iconPath = (Resolve-Path (Join-Path $scriptDir "..\assets\icon.png") -ErrorAction SilentlyContinue).Path

[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null

function Escape-Xml($text) {
  return [System.Security.SecurityElement]::Escape($text)
}

$title = "Claude Code"
$message = "Finished responding"

$imageXml = if ($iconPath -and (Test-Path $iconPath)) {
  "<image placement=`"appLogoOverride`" src=`"file:///$($iconPath -replace '\\','/')`"/>"
} else { "" }

$toastXml = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>$(Escape-Xml $title)</text>
      <text>$(Escape-Xml $message)</text>
      $imageXml
    </binding>
  </visual>
</toast>
"@

$xml = [Windows.Data.Xml.Dom.XmlDocument]::new()
$xml.LoadXml($toastXml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)