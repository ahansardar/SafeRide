#define MyAppName "SafeRide"
#ifndef MyAppVersion
  #error MyAppVersion must be passed by tools\build-installer.ps1
#endif
#define MyAppPublisher "SafeRide Project"
#define MyAppExeName "SafeRide.exe"
#define ProjectRoot SourcePath + "\.."

[Setup]
AppId={{69A9DBFC-1F26-4B8B-9E72-42B354735B72}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SafeRide
DefaultGroupName=SafeRide
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#ProjectRoot}\release
OutputBaseFilename=SafeRide-Setup-x64
SetupIconFile={#ProjectRoot}\assets\saferide.ico
UninstallDisplayIcon={app}\SafeRide.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoDescription=SafeRide offline installer
VersionInfoCompany={#MyAppPublisher}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#ProjectRoot}\dist\SafeRide\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ProjectRoot}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\USB_DRIVER_HELP.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SafeRide"; Filename: "{app}\SafeRide.exe"; WorkingDir: "{app}"
Name: "{group}\SafeRide documentation"; Filename: "{app}\README.md"
Name: "{group}\SafeRide connection help"; Filename: "{app}\USB_DRIVER_HELP.txt"
Name: "{autodesktop}\SafeRide"; Filename: "{app}\SafeRide.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\SafeRide.exe"; Description: "Launch SafeRide"; Flags: nowait postinstall skipifsilent
Filename: "{app}\SafeRide.exe"; Flags: nowait skipifnotsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsWin64 then
  begin
    MsgBox('SafeRide requires 64-bit Windows 10 or Windows 11.', mbError, MB_OK);
    Result := False;
  end;
end;

