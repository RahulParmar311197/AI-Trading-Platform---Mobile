plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android { namespace="com.aitrading.platform"; compileSdk=35
    defaultConfig { applicationId="com.aitrading.platform"; minSdk=26; targetSdk=35; versionCode=1; versionName="1.0.0" }
    buildFeatures { compose=true }
}

dependencies {
    val composeBom=platform("androidx.compose:compose-bom:2025.01.00")
    implementation(composeBom); androidTestImplementation(composeBom)
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.navigation:navigation-compose:2.8.5")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.1")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.0")
}
