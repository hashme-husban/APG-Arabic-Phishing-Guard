package com.apg.arabicphishingguard

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var launchPayload: Map<String, String?>? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        ApgNotificationBridge.ensureChannels(this)
        launchPayload = ApgNotificationBridge.launchPayloadFrom(intent)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            ApgNotificationBridge.METHOD_CHANNEL,
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "configureMonitoredPackages" -> {
                    val packages = call.argument<List<String>>("packages").orEmpty()
                    ApgNotificationBridge.configureMonitoredPackages(this, packages)
                    result.success(null)
                }
                "requestPostNotifications" -> {
                    ApgNotificationBridge.requestPostNotifications(this)
                    result.success(null)
                }
                "hasPostNotifications" -> {
                    result.success(ApgNotificationBridge.hasPostNotificationsPermission(this))
                }
                "showDebugTestAlert" -> {
                    val now = System.currentTimeMillis()
                    ApgNotificationBridge.showLocalAlert(
                        context = this,
                        channelId = ApgNotificationBridge.THREAT_ALERT_CHANNEL,
                        riskScore = 99,
                        title = "APG: اختبار الإشعار",
                        body = "إذا ظهر هذا الإشعار فالقناة تعمل.",
                        notificationId = "apg-debug-test-$now",
                        analysisId = null,
                        fingerprint = "debug-test-$now",
                    )
                    result.success(null)
                }
                "requestReadContacts" -> {
                    ApgNotificationBridge.requestReadContacts(this)
                    result.success(null)
                }
                "isKnownContact" -> {
                    val sender = call.argument<String>("sender") ?: ""
                    result.success(ApgNotificationBridge.isKnownContact(this, sender))
                }
                "showLocalAlert" -> {
                    ApgNotificationBridge.showLocalAlert(
                        context = this,
                        channelId = call.argument<String>("channelId")
                            ?: ApgNotificationBridge.THREAT_ALERT_CHANNEL,
                        riskScore = call.argument<Int>("riskScore"),
                        title = call.argument<String>("title") ?: "فحص رسالة APG",
                        body = call.argument<String>("body") ?: "لا توجد مؤشرات خطيرة.",
                        notificationId = call.argument<String>("notificationId"),
                        analysisId = call.argument<String>("analysisId"),
                        fingerprint = call.argument<String>("fingerprint"),
                    )
                    result.success(null)
                }
                "getLaunchPayload" -> result.success(launchPayload ?: emptyMap<String, String?>())
                "clearLaunchPayload" -> {
                    launchPayload = null
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }

    override fun onResume() {
        super.onResume()
        ApgNotificationBridge.setFlutterActive(this, true)
    }

    override fun onPause() {
        ApgNotificationBridge.setFlutterActive(this, false)
        super.onPause()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        launchPayload = ApgNotificationBridge.launchPayloadFrom(intent)
    }
}
