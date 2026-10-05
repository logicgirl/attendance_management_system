; Inno Setup script for the AttendEase desktop client.
; 1. Build the program:   .venv\Scripts\pyinstaller --noconfirm attendease_client.spec
; 2. Copy config.json.example to config.json and set your server's address
; 3. Compile this file with Inno Setup 6 (https://jrsoftware.org/isinfo.php)
; The installer is written to installer_output\.

#define AppName "AttendEase"
#define AppVersion "1.0.0"

[Setup]
AppId={{6F1C2B7E-3D4A-4E8B-9A51-0C2D7E3F4B19}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=AttendEase
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\AttendEase.exe
OutputDir=installer_output
OutputBaseFilename=AttendEase-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Installs for the current user, so no administrator rights are needed
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\AttendEase.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\AttendEase.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\AttendEase.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AttendEase.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
