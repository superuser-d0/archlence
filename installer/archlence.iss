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
; Sürüm dışarıdan verilebilir: `ISCC /DMyAppVersion=1.2.3 archlence.iss`.
; #ifndef ŞART: düz bir `#define` komut satırından geleni EZERDİ, yani
; etiketten türeyen sürüm sessizce varsayılana döner ve her release aynı sürüm
; numarasıyla çıkardı. Bu hâliyle CLI kazanır, yerel derlemede güncel sürüm kalır.
#ifndef MyAppVersion
  #define MyAppVersion "0.0.2"
#endif
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
; WorkingDir={app} HER İKİSİNDE DE BİLEREK AÇIK: main.py artık kendi
; başlangıcında doğru dizine chdir ediyor (bkz. utils/app_paths.py::
; resource_dir, main.py'deki FileNotFoundError düzeltmesi) — yani bu satır
; olmadan da çalışması gerekir. Yine de burada belirtmek bedava bir ikinci
; koruma katmanı: WorkingDir belirtilmezse [Icons] kısayolları {app}'ı
; varsayılan alır, ama açıkça yazmak gelecekte main.py'nin kendi
; düzeltmesi yanlışlıkla kaldırılırsa bile aynı çökmenin BURADAN
; tekrarlanmasını engeller.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
; WorkingDir={app} burada [Icons]'dan daha da önemliydi: Inno Setup'ın
; [Run] girdileri için varsayılanı {app} DEĞİL, kurulumun kendi GEÇİCİ
; dizinidir — belirtilmezse kurulum sonunda "Başlat" tıklanınca uygulama
; kurulum tamamlanır tamamlanmaz zaten var olmayacak bir geçici dizinden
; (ya da en azından {app}'tan FARKLI bir dizinden) açılırdı. Bu, main.py
; düzeltmesinden BAĞIMSIZ olarak, kullanıcının bildirdiği çökmenin ikinci,
; ayrı bir olası kaynağıydı.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
