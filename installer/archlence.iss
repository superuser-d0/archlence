; Archlence — Inno Setup kurulum betiği.
;
; archlence.spec bilerek "onedir" derliyor (Kivy uygulamaları --onefile ile
; sık sorun çıkarıyor, bkz. o dosyadaki not) — yani çıktı tek bir .exe değil,
; .exe + yanında bir DLL/kaynak klasörü. Bu betik o klasörün TAMAMINI TEK bir
; ArchlenceSetup.exe'ye sarmalıyor: son kullanıcı zip açıp klasör bütünlüğünü
; kendi koruma zorunda kalmıyor, Başlat Menüsü kısayolu ve kaldırıcı otomatik
; geliyor.
;
; Kurulum kullanıcı başına (PrivilegesRequired=lowest, %LocalAppData%\Programs
; altına) — Program Files ve yönetici izni GEREKMİYOR. Bu bilinçli bir seçim:
; kullanıcı verisi zaten platformdirs üzerinden kurulum dizininden bağımsız
; bir yerde tutuluyor (docs/ROADMAP.md Faz 1 madde 4), o yüzden Program
; Files'ın salt-okunur olması burada hiç sorun değil — ama UAC yükseltmesi
; istemeden kurulabilmek, imzasız bir .exe'yi test eden bir arkadaş için
; sürtünmeyi azaltıyor.
;
; Derleme (yalnızca Windows'ta, PyInstaller derlemesinden SONRA):
;   iscc installer\archlence.iss
; Çıktı: installer_output\ArchlenceSetup.exe

#define MyAppName "Archlence"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Mehmet Cem Çakırgöz"
#define MyAppExeName "Archlence.exe"

[Setup]
AppId={{A3F2B4C1-8D2E-4F5A-9B7C-1E6D3A8F2C4B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\installer_output
OutputBaseFilename=ArchlenceSetup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; dist\Archlence\ PyInstaller'ın "onedir" çıktısı — .exe'yi çalıştırmak için
; gereken HER ŞEY (DLL'ler, ANGLE/SDL2 ikilileri, Python runtime) burada.
Source: "..\dist\Archlence\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
