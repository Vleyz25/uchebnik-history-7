# История Нового времени, 7 класс — Android-приложение

Офлайн-приложение: поиск ответов по тексту учебника (Мединский, Чубарьян, 7 класс).
Интернет не нужен, разрешение на сеть в манифесте не запрашивается.

## Что внутри

```
android/
  settings.gradle, build.gradle, gradle.properties
  app/build.gradle
  app/src/main/AndroidManifest.xml
  app/src/main/java/ru/multitool/uchebnik/MainActivity.java
  app/src/main/assets/index.html   <- само приложение (1 МБ, весь текст книги внутри)
```

Приложение — это один HTML-файл в `assets`. Оболочка открывает его в WebView.
Чтобы поменять содержимое, отредактируйте `index.html` (пересоберите его скриптом
`build_app.py` в корне папки чата) и скопируйте в `app/src/main/assets/index.html`.

## Как собрать APK

Вариант 1 — Android Studio (проще всего, JDK и Gradle идут внутри):

1. Скачать Android Studio с developer.android.com и установить.
2. File → Open → выбрать папку `android` из этой папки чата.
3. Дождаться окончания Gradle Sync (первый раз качает зависимости, нужен интернет).
4. Build → Build Bundle(s) / APK(s) → Build APK(s).
5. Готовый файл: `android/app/build/outputs/apk/debug/app-debug.apk`.

Вариант 2 — командная строка (нужны JDK 17 и Android SDK):

```
cd android
gradle wrapper
gradlew assembleDebug
```

APK появится в `app/build/outputs/apk/debug/app-debug.apk`.
Для release-сборки: `gradlew assembleRelease` — файл будет подписан debug-ключом,
этого достаточно для личной установки на телефон.

## Установка на телефон

1. Перекинуть APK на телефон (кабель, Telegram «избранное», облако).
2. Открыть файл на телефоне, разрешить «Установка из неизвестных источников».
3. Запустить приложение «История 7 класс».

## Ограничения

- Отвечает только тем, что есть в учебнике; на вопрос вне курса честно пишет «нет в учебнике».
- Не пересказывает своими словами: показывает сжатый ответ (1–2 предложения) и дословный текст с номером страницы.
- Иконка — системная заглушка; для своей иконки положите PNG в `app/src/main/res/mipmap-*`
  и укажите `android:icon="@mipmap/ic_launcher"` в манифесте.
