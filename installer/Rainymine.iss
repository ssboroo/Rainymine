#define AppVersion "0.6.0"
[Setup]
AppId={{9D7D9D47-CBAB-4076-85B0-4660DF0A9951}
AppName=RAINYMINE
AppVersion={#AppVersion}
AppPublisher=RAINY STUDIO
DefaultDirName={localappdata}\Programs\Rainymine
DefaultGroupName=RAINYMINE
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Rainymine-{#AppVersion}-Setup-x64
SetupIconFile=..\assets\rainymine.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Rainymine.exe
[Files]
Source: "..\dist\Rainymine\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\RAINYMINE"; Filename: "{app}\Rainymine.exe"
Name: "{group}\RAINYMINE - CPU rendering"; Filename: "{app}\Rainymine-Software.bat"
Name: "{autodesktop}\RAINYMINE"; Filename: "{app}\Rainymine.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\Rainymine.exe"; Description: "Launch RAINYMINE"; Flags: nowait postinstall skipifsilent
