; Inno Setup script for ccCue
; Requires Python available in PATH (python command)

#define MyAppName "ccCue"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "ccCue"
#define MyAppExeName ""

[Setup]
AppId={{C76E7608-9C23-4D48-B70B-AE7DE892ED66}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\ccCue
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=ccCue-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ChangesEnvironment=no
UninstallDisplayIcon={app}\installer\install.bat

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\hooks\*"; DestDir: "{app}\hooks"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\notifier\*"; DestDir: "{app}\notifier"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\cli\*"; DestDir: "{app}\cli"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\config\*"; DestDir: "{app}\config"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\installer\install.bat"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "..\installer\uninstall.bat"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\AGENTS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CLAUDE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\ccCue Health Check"; Filename: "{cmd}"; Parameters: "/C cd /d ""{app}"" && python -m cli.main doctor"; WorkingDir: "{app}"
Name: "{autodesktop}\ccCue Health Check"; Filename: "{cmd}"; Parameters: "/C cd /d ""{app}"" && python -m cli.main doctor"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{cmd}"; Parameters: "/C cd /d ""{app}"" && python -m cli.main install --project-root ""{app}"""; Flags: runhidden waituntilterminated; StatusMsg: "Configuring Claude hooks..."
Filename: "{cmd}"; Parameters: "/C cd /d ""{app}"" && python -m cli.main doctor"; Flags: postinstall shellexec skipifsilent; Description: "Run ccCue doctor"

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C cd /d ""{app}"" && python -m cli.main uninstall --purge"; Flags: runhidden waituntilterminated; RunOnceId: "ccCueUninstallCleanup"

[Code]
function IsPythonAvailable(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(ExpandConstant('{cmd}'), '/C python --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if Result then
  begin
    Result := (ResultCode = 0);
  end;
end;

function InitializeSetup(): Boolean;
begin
  if not IsPythonAvailable() then
  begin
    MsgBox('Python was not found in PATH. Please install Python 3.10+ and ensure "python" command is available before installing ccCue.', mbError, MB_OK);
    Result := False;
    exit;
  end;

  Result := True;
end;
