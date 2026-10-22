#define AppVersion "0.9.0"
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
CloseApplications=yes
RestartApplications=no
MinVersion=10.0
[Files]
Source: "..\dist\Rainymine\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\RAINYMINE"; Filename: "{app}\Rainymine.exe"
Name: "{group}\RAINYMINE - CPU дүрслэл"; Filename: "{app}\Rainymine-Software.bat"
Name: "{autodesktop}\RAINYMINE"; Filename: "{app}\Rainymine.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Ширээний товчлол үүсгэх"; Flags: unchecked
[Run]
Filename: "{app}\Rainymine.exe"; Description: "RAINYMINE-ийг нээх"; Flags: nowait postinstall skipifsilent
