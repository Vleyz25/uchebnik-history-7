@echo off
setlocal

set "JDK=D:\“β¨«¨βλ\AndroidBuildTools\jdk\jdk-17.0.20.1+1"
set "BT=D:\“β¨«¨βλ\AndroidBuildTools\sdk\build-tools\34.0.0"
set "SDKJAR=D:\“β¨«¨βλ\AndroidBuildTools\sdk\platforms\android-34\android.jar"
set "JAVA_HOME=%JDK%"
set "PATH=%JDK%\bin;%PATH%"

set "OUT=build\out"
set "JAR=build\android.jar"
set "ASSETS=android\app\src\main\assets"
set "SRC=android\app\src\main\java\ru\multitool\uchebnik\MainActivity.java"

if not exist "%JAR%" copy /y "%SDKJAR%" "%JAR%" >nul
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%\classes"

echo [1/6] aapt2 link
"%BT%\aapt2.exe" link -o "%OUT%\base.apk" -I "%JAR%" --manifest build\AndroidManifest.xml -A "%ASSETS%" --min-sdk-version 21 --target-sdk-version 34 --version-code 1 --version-name 1.0 || goto :fail

echo [2/6] javac
"%JDK%\bin\javac.exe" -nowarn -source 8 -target 8 -bootclasspath "%JAR%" -d "%OUT%\classes" "%SRC%" || goto :fail

echo [3/6] d8
"%JDK%\bin\java.exe" -cp "%BT%\lib\d8.jar" com.android.tools.r8.D8 --min-api 21 --lib "%JAR%" --output "%OUT%" "%OUT%\classes\ru\multitool\uchebnik\MainActivity.class" || goto :fail

echo [4/6] add classes.dex
"%USERPROFILE%\AppData\Local\Python\bin\python.exe" -X utf8 build\add_dex.py "%OUT%\base.apk" "%OUT%\classes.dex" || goto :fail
move /y "%OUT%\base.apk" "%OUT%\unaligned.apk" >nul

echo [5/6] zipalign
"%BT%\zipalign.exe" -f -p 4 "%OUT%\unaligned.apk" "%OUT%\aligned.apk" || goto :fail

echo [6/6] sign
if not exist build\debug.keystore (
  "%JDK%\bin\keytool.exe" -genkeypair -v -keystore build\debug.keystore -storepass android -keypass android -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US" || goto :fail
)
"%BT%\apksigner.bat" sign --ks build\debug.keystore --ks-pass pass:android --key-pass pass:android --out uchebnik.apk "%OUT%\aligned.apk" || goto :fail

"%BT%\apksigner.bat" verify --print-certs uchebnik.apk || goto :fail
echo BUILD_OK
goto :eof

:fail
echo BUILD_FAILED
exit /b 1
