; Inno Setup script for ccCue
; Prefer bundled runtime python when available.

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
Source: "..\installer\cccue.bat"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\AGENTS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CLAUDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\runtime\*"; DestDir: "{app}\runtime"; Flags: recursesubdirs createallsubdirs ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\ccCue Health Check"; Filename: "{app}\installer\cccue.bat"; Parameters: "doctor"; WorkingDir: "{app}"
Name: "{autodesktop}\ccCue Health Check"; Filename: "{app}\installer\cccue.bat"; Parameters: "doctor"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\installer\install.bat"; Parameters: "--no-pause"; Flags: runhidden waituntilterminated; StatusMsg: "Installing ccCue runtime and configuring Claude hooks..."
Filename: "{app}\installer\cccue.bat"; Parameters: "doctor"; Flags: postinstall shellexec skipifsilent; Description: "Run ccCue doctor"

[UninstallRun]
Filename: "{app}\installer\uninstall.bat"; Parameters: "--no-pause"; Flags: runhidden waituntilterminated; RunOnceId: "ccCueUninstallCleanup"
