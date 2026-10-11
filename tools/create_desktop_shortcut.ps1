$desktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$shortcutPath = Join-Path $desktopPath "Hustler Shorts.lnk"
$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($shortcutPath)
$sc.TargetPath = "c:\Users\Deniz\pushToUp\Hustler\baslat_hustler.bat"
$sc.WorkingDirectory = "c:\Users\Deniz\pushToUp\Hustler"
$sc.Description = "Hustler Shorts Tauri Masaustu Gelistirici Baslatici"
$sc.Save()
Write-Output "Kısayol oluşturuldu: $shortcutPath"
