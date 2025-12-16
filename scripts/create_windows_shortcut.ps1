# Create Windows Shortcut for Perun's BlackBook
# This script creates a desktop shortcut and optionally pins to Start menu

param(
    [string]$AppUrl = "http://localhost:8000",
    [string]$IconPath = "$PSScriptRoot\..\app\static\icons\favicon.ico",
    [switch]$Desktop = $true,
    [switch]$StartMenu = $false
)

$AppName = "Perun's BlackBook"
$ShortcutDescription = "Personal CRM for managing professional relationships"

# Resolve paths
$IconPath = (Resolve-Path $IconPath -ErrorAction SilentlyContinue).Path
if (-not $IconPath) {
    $IconPath = "$PSScriptRoot\..\app\static\icons\favicon.ico"
}

# Create WScript Shell object
$WshShell = New-Object -ComObject WScript.Shell

# Desktop shortcut
if ($Desktop) {
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $DesktopPath "$AppName.lnk"

    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "msedge.exe"  # Use Edge for best PWA experience
    $Shortcut.Arguments = "--app=$AppUrl"
    $Shortcut.Description = $ShortcutDescription
    $Shortcut.WorkingDirectory = $PSScriptRoot

    if (Test-Path $IconPath) {
        $Shortcut.IconLocation = $IconPath
    }

    $Shortcut.Save()
    Write-Host "Desktop shortcut created: $ShortcutPath" -ForegroundColor Green
}

# Start Menu shortcut
if ($StartMenu) {
    $StartMenuPath = [Environment]::GetFolderPath("StartMenu")
    $ProgramsPath = Join-Path $StartMenuPath "Programs"
    $ShortcutPath = Join-Path $ProgramsPath "$AppName.lnk"

    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "msedge.exe"
    $Shortcut.Arguments = "--app=$AppUrl"
    $Shortcut.Description = $ShortcutDescription
    $Shortcut.WorkingDirectory = $PSScriptRoot

    if (Test-Path $IconPath) {
        $Shortcut.IconLocation = $IconPath
    }

    $Shortcut.Save()
    Write-Host "Start Menu shortcut created: $ShortcutPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Shortcut(s) created successfully!" -ForegroundColor Cyan
Write-Host "The app will open in Edge's app mode (no browser chrome)." -ForegroundColor Gray
Write-Host ""
Write-Host "To pin to taskbar: Right-click the shortcut -> Pin to taskbar" -ForegroundColor Yellow
