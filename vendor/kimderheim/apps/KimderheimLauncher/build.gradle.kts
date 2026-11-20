plugins {
    id("com.android.application") version "8.7.3"
}

// Манифест общий со сборкой системы (Android.bp). Gradle не принимает в нём
// атрибут package, поэтому для Gradle делаем копию без него.
val gradleManifest = layout.buildDirectory.file("gradle-manifest/AndroidManifest.xml").get().asFile
gradleManifest.parentFile.mkdirs()
gradleManifest.writeText(
    file("AndroidManifest.xml").readText().replace(Regex("""\s+package="[^"]*""""), "")
)

android {
    namespace = "os.kimderheim.launcher"
    compileSdk = 35

    defaultConfig {
        applicationId = "os.kimderheim.launcher"
        minSdk = 33
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    sourceSets["main"].apply {
        manifest.srcFile(gradleManifest)
        java.srcDirs("src")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
