; English Master kurulum paketi (NSIS 3, Unicode).
; Derleme: makensis /DVERSION=0.9.0 /DSOURCE_DIR=..\dist\EnglishMaster /DOUT_FILE=..\dist\EnglishMaster-Setup-0.9.0.exe packaging\installer.nsi
;
; - Yönetici izni gerekmez; kullanıcının kendi klasörüne kurulur (%LOCALAPPDATA%\Programs\English Master).
; - Kişisel veriler (%LOCALAPPDATA%\EnglishMaster) kurulum klasöründen ayrıdır.
; - Kaldırma, kişisel verileri VARSAYILAN OLARAK KORUR; silmek için kullanıcının açıkça işaretlemesi gerekir.
; - Güncelleme (yeni sürümü eskisinin üzerine kurmak) kişisel verilere dokunmaz.

Unicode true
SetCompressor /SOLID lzma
RequestExecutionLevel user
ManifestDPIAware true

!ifndef VERSION
  !error "VERSION tanımlanmalı: /DVERSION=x.y.z"
!endif
!ifndef SOURCE_DIR
  !define SOURCE_DIR "..\dist\EnglishMaster"
!endif
!ifndef ICON_FILE
  !define ICON_FILE "..\build\icon.ico"
!endif
!ifndef OUT_FILE
  !define OUT_FILE "..\dist\EnglishMaster-Setup-${VERSION}.exe"
!endif

!define APP_NAME "English Master"
!define APP_EXE "EnglishMaster.exe"
!define APP_ID "EnglishMaster"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
!define DATA_DIR "$LOCALAPPDATA\EnglishMaster"

Name "${APP_NAME}"
OutFile "${OUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\${APP_NAME}"
InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"
BrandingText "${APP_NAME} ${VERSION}"
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1055 "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=1055 "FileDescription" "${APP_NAME} kurulumu"
VIAddVersionKey /LANG=1055 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1055 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1055 "LegalCopyright" "English Master"

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define MUI_ICON "${ICON_FILE}"
!define MUI_UNICON "${ICON_FILE}"
!define MUI_ABORTWARNING
!define MUI_UNABORTWARNING

!define MUI_WELCOMEPAGE_TEXT "Bu sihirbaz English Master ${VERSION} sürümünü bilgisayarınıza kuracak.$\r$\n$\r$\nProgram ücretsizdir, internet bağlantısı ve hesap gerektirmez. İlerlemeniz yalnızca bu bilgisayarda saklanır.$\r$\n$\r$\nDaha önce kurduysanız yeni sürüm eskisinin üzerine kurulur; ilerlemeniz korunur."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "English Master'ı şimdi başlat"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_COMPONENTS
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Turkish"

; --- Çalışan program kontrolü -------------------------------------------------
!macro CHECK_RUNNING
  check_running:
  nsExec::ExecToStack 'cmd /c tasklist /FI "IMAGENAME eq ${APP_EXE}" /NH | find /I "${APP_EXE}"'
  Pop $0
  Pop $1
  ${If} $0 == 0
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "English Master şu anda açık.$\r$\n$\r$\nLütfen programı kapatın (Ayarlar > Programı kapat ya da sistem tepsisindeki simge > Çıkış) ve Yeniden Dene'ye basın." /SD IDCANCEL IDRETRY check_running
    Abort
  ${EndIf}
!macroend

Function .onInit
  !insertmacro CHECK_RUNNING
FunctionEnd

Function un.onInit
  !insertmacro CHECK_RUNNING
FunctionEnd

; --- Kurulum ------------------------------------------------------------------
Section "English Master (gerekli)" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  ; Önceki sürümün program dosyalarını kaldır (yalnızca kurulum klasöründeki program dosyaları;
  ; kişisel veriler ayrı klasördedir ve hiç dokunulmaz).
  ${If} ${FileExists} "$INSTDIR\${APP_EXE}"
    RMDir /r "$INSTDIR\_internal"
    Delete "$INSTDIR\${APP_EXE}"
  ${EndIf}
  File /r "${SOURCE_DIR}\*.*"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME} kaldır.lnk" "$INSTDIR\Uninstall.exe"

  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "English Master"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" $0
SectionEnd

Section "Masaüstü kısayolu" SecDesktop
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Program dosyaları, eğitim içeriği ve ses kayıtları."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Masaüstüne bir English Master kısayolu ekler."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; --- Kaldırma -----------------------------------------------------------------
Section "un.English Master programı" UnSecMain
  SectionIn RO
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
SectionEnd

; Varsayılan olarak SEÇİLİ DEĞİL (/o). Sessiz kaldırmada (/S) de kişisel veriler korunur.
Section /o "un.Kişisel verilerimi de sil" UnSecData
  MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 "İlerlemeniz, test sonuçlarınız, kelime listeniz, ayarlarınız ve yedekleriniz kalıcı olarak silinecek:$\r$\n${DATA_DIR}$\r$\n$\r$\nEmin misiniz?" /SD IDNO IDYES delete_data
  Goto keep_data
  delete_data:
    RMDir /r "${DATA_DIR}"
  keep_data:
SectionEnd

!insertmacro MUI_UNFUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${UnSecMain} "Program dosyalarını ve kısayolları kaldırır."
  !insertmacro MUI_DESCRIPTION_TEXT ${UnSecData} "İşaretlemezseniz ilerlemeniz korunur ve programı yeniden kurduğunuzda kaldığınız yerden devam edersiniz."
!insertmacro MUI_UNFUNCTION_DESCRIPTION_END
