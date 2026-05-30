package com.apg.arabicphishingguard

import android.Manifest
import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.provider.ContactsContract
import android.service.notification.StatusBarNotification
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlin.math.abs

object ApgNotificationBridge {
    const val METHOD_CHANNEL = "apg/native_notifications"
    const val THREAT_ALERT_CHANNEL = "apg_threat_alerts_v2"
    const val GENERAL_CHANNEL = "apg_general"
    const val SAFE_CHANNEL = "apg_safe_channel"
    const val WARNING_CHANNEL = "apg_warning_channel"
    const val DANGER_CHANNEL = "apg_danger_channel"

    private const val TAG_NOTIFY = "APG_NOTIFY_DEBUG"
    private const val TAG_MONITOR = "APG_MONITOR_DEBUG"
    private const val PREFS = "apg_native_notifications"
    private const val MONITORED_PACKAGES = "monitored_packages"
    private const val FLUTTER_ACTIVE = "flutter_active"
    private const val EXTRA_OPEN = "apg_open"
    private const val EXTRA_NOTIFICATION_ID = "apg_notification_id"
    private const val EXTRA_ANALYSIS_ID = "apg_analysis_id"
    private const val DEDUP_WINDOW_MS = 90_000L
    private const val RECENT_ALERT_PREFIX = "recent_alert_"

    // System notification dedup
    private val shownSeverityBySource = linkedMapOf<String, Int>()
    private val shownAtBySource = linkedMapOf<String, Long>()

    private val defaultPackages = setOf(
        "com.whatsapp",
        "org.telegram.messenger",
        "com.google.android.gm",
        "com.google.android.apps.messaging",
        "com.samsung.android.messaging",
        "com.android.mms",
        "com.facebook.orca",
        "com.instagram.android",
    )

    // ── Channels ────────────────────────────────────────────────────────────

    fun ensureChannels(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            Log.d(TAG_NOTIFY, "ensureChannels skipped: sdk=${Build.VERSION.SDK_INT}")
            return
        }
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(THREAT_ALERT_CHANNEL, "APG Threat Alerts", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Heads-up alerts for suspicious or dangerous APG results"
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 140)
                setSound(
                    android.provider.Settings.System.DEFAULT_NOTIFICATION_URI,
                    android.media.AudioAttributes.Builder()
                        .setUsage(android.media.AudioAttributes.USAGE_NOTIFICATION)
                        .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build(),
                )
            },
        )
        val threatChannel = manager.getNotificationChannel(THREAT_ALERT_CHANNEL)
        Log.d(
            TAG_NOTIFY,
            "channel_created id=$THREAT_ALERT_CHANNEL importance=${threatChannel?.importance} canBypassDnd=${threatChannel?.canBypassDnd()}",
        )
        manager.createNotificationChannel(
            NotificationChannel(GENERAL_CHANNEL, "APG General", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "General APG notifications"
            },
        )
        val generalChannel = manager.getNotificationChannel(GENERAL_CHANNEL)
        Log.d(
            TAG_NOTIFY,
            "channel_created id=$GENERAL_CHANNEL importance=${generalChannel?.importance}",
        )
    }

    // ── Package / lifecycle config ───────────────────────────────────────────

    fun configureMonitoredPackages(context: Context, packages: List<String>) {
        prefs(context).edit()
            .putStringSet(
                MONITORED_PACKAGES,
                packages.map { it.trim() }.filter { it.isNotEmpty() }.toSet(),
            )
            .apply()
    }

    fun setFlutterActive(context: Context, active: Boolean) {
        prefs(context).edit().putBoolean(FLUTTER_ACTIVE, active).apply()
    }

    fun isFlutterActive(context: Context): Boolean =
        prefs(context).getBoolean(FLUTTER_ACTIVE, false)

    // ── Permission helpers ───────────────────────────────────────────────────

    fun requestPostNotifications(activity: Activity) {
        Log.d(TAG_NOTIFY, "requestPostNotifications current=${canPostNotifications(activity)} sdk=${Build.VERSION.SDK_INT}")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 7301)
        }
    }

    fun hasPostNotificationsPermission(context: Context): Boolean {
        val granted = canPostNotifications(context)
        Log.d(TAG_NOTIFY, "hasPostNotificationsPermission granted=$granted sdk=${Build.VERSION.SDK_INT}")
        return granted
    }

    fun requestReadContacts(activity: Activity) {
        if (activity.checkSelfPermission(Manifest.permission.READ_CONTACTS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            activity.requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), 7302)
        }
    }

    // ── Contacts lookup ──────────────────────────────────────────────────────

    fun isKnownContact(context: Context, sender: String): Boolean? {
        val value = sender.trim()
        if (value.isBlank() || value == "غير معروف" || looksLikePackageName(value)) return null
        if (context.checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) return null
        return try {
            val normalizedPhone = value.filter { it.isDigit() || it == '+' }
            if (normalizedPhone.length >= 6) {
                val uri = ContactsContract.PhoneLookup.CONTENT_FILTER_URI.buildUpon()
                    .appendPath(normalizedPhone)
                    .build()
                context.contentResolver.query(
                    uri,
                    arrayOf(ContactsContract.PhoneLookup._ID),
                    null, null, null,
                )?.use { cursor -> cursor.moveToFirst() } ?: false
            } else {
                val args = arrayOf(value, value)
                context.contentResolver.query(
                    ContactsContract.Contacts.CONTENT_URI,
                    arrayOf(ContactsContract.Contacts._ID),
                    "${ContactsContract.Contacts.DISPLAY_NAME_PRIMARY} = ? OR ${ContactsContract.Contacts.DISPLAY_NAME} = ?",
                    args, null,
                )?.use { cursor -> cursor.moveToFirst() } ?: false
            }
        } catch (error: Exception) {
            if (isDebuggable(context)) Log.d(TAG_MONITOR, "contact_lookup_failed ${error.message}")
            null
        }
    }

    // ── Notification listener handler ────────────────────────────────────────

    fun handleCapturedNotification(context: Context, sbn: StatusBarNotification) {
        val packageName = sbn.packageName ?: return
        if (packageName == context.packageName) {
            Log.d(TAG_MONITOR, "native_skip self_package=$packageName")
            return
        }
        if (!monitoredPackages(context).contains(packageName)) {
            Log.d(TAG_MONITOR, "native_skip unmonitored package=$packageName")
            return
        }
        if (prefs(context).getBoolean(FLUTTER_ACTIVE, false)) {
            Log.d(TAG_MONITOR, "native_observed_flutter_active package=$packageName id=${sbn.id}")
            return
        }
        if (!canPostNotifications(context)) {
            Log.d(TAG_NOTIFY, "native_skip_post_permission_denied package=$packageName id=${sbn.id}")
            return
        }

        val extras = sbn.notification?.extras ?: Bundle.EMPTY
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extractNotificationText(extras)
        if (title.isBlank() && text.isBlank()) {
            Log.d(TAG_MONITOR, "native_skip empty_text package=$packageName id=${sbn.id}")
            return
        }

        Log.d(TAG_MONITOR, "native_captured package=$packageName id=${sbn.id} titleLen=${title.length} textLen=${text.length}")
        // Threat alerts are posted only after Flutter receives a canonical
        // AnalysisResult from the APG API. No native heuristic notification is
        // shown here, so scores always match result details/history.
    }

    // ── System notification ──────────────────────────────────────────────────

    fun showLocalAlert(
        context: Context,
        channelId: String,
        riskScore: Int?,
        title: String,
        body: String,
        notificationId: String?,
        analysisId: String?,
        fingerprint: String? = null,
    ) {
        ensureChannels(context)
        val permissionGranted = canPostNotifications(context)
        Log.d(
            TAG_NOTIFY,
            "showLocalAlert requested channel=$channelId permission=$permissionGranted risk=${riskScore ?: "none"} fingerprint=${fingerprint?.hashCode()}",
        )
        if (!permissionGranted) {
            Log.d(TAG_NOTIFY, "showLocalAlert skipped reason=post_notifications_denied")
            return
        }

        val safeChannel = when (channelId) {
            THREAT_ALERT_CHANNEL, WARNING_CHANNEL, DANGER_CHANNEL -> THREAT_ALERT_CHANNEL
            GENERAL_CHANNEL, SAFE_CHANNEL -> GENERAL_CHANNEL
            else -> THREAT_ALERT_CHANNEL
        }
        val sourceKey = notificationId?.takeIf { it.isNotBlank() }
            ?: analysisId?.takeIf { it.isNotBlank() }
            ?: riskScore?.toString()
            ?: System.currentTimeMillis().toString()
        val now = System.currentTimeMillis()
        pruneRecentEntries(now)
        val severity = severityForChannel(safeChannel)
        val alertEventKey = fingerprint?.takeIf { it.isNotBlank() }
            ?: alertEventKey(sourceKey, analysisId, riskScore, severity, now)
        val previousSeverity = shownSeverityBySource[alertEventKey]
        val previousAt = shownAtBySource[alertEventKey]
        val persistedAt = recentAlertShownAt(context, alertEventKey)
        if (previousSeverity != null &&
            previousAt != null &&
            now - previousAt < DEDUP_WINDOW_MS &&
            previousSeverity >= severity
        ) {
            val remaining = DEDUP_WINDOW_MS - (now - previousAt)
            Log.d(TAG_NOTIFY, "notify_skipped_duplicate fingerprint=${alertEventKey.hashCode()} remainingMs=$remaining previous=$previousSeverity next=$severity")
            return
        }
        if (persistedAt != null && now - persistedAt < DEDUP_WINDOW_MS) {
            val remaining = DEDUP_WINDOW_MS - (now - persistedAt)
            Log.d(TAG_NOTIFY, "notify_skipped_persisted_duplicate fingerprint=${alertEventKey.hashCode()} remainingMs=$remaining")
            return
        }
        shownSeverityBySource[alertEventKey] = severity
        shownAtBySource[alertEventKey] = now
        rememberAlertShown(context, alertEventKey, now)
        if (shownSeverityBySource.size > 160) {
            val firstKey = shownSeverityBySource.keys.firstOrNull()
            if (firstKey != null) {
                shownSeverityBySource.remove(firstKey)
                shownAtBySource.remove(firstKey)
            }
        }

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val activeChannel = manager.getNotificationChannel(safeChannel)
            Log.d(TAG_NOTIFY, "notify_channel id=$safeChannel importance=${activeChannel?.importance}")
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            (analysisId ?: notificationId ?: System.currentTimeMillis().toString()).hashCode(),
            Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra(EXTRA_OPEN, true)
                putExtra(EXTRA_NOTIFICATION_ID, notificationId)
                putExtra(EXTRA_ANALYSIS_ID, analysisId)
            },
            PendingIntent.FLAG_UPDATE_CURRENT or immutableFlag(),
        )

        val smallIcon = R.drawable.ic_apg_notification
        Log.d(TAG_NOTIFY, "notify_builder smallIcon=$smallIcon notificationId=$notificationId analysisId=$analysisId fingerprint=${alertEventKey.hashCode()}")

        val builder = NotificationCompat.Builder(context, safeChannel)
            .setSmallIcon(smallIcon)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setShowWhen(true)
            .setOnlyAlertOnce(false)
            .setColor(colorForChannel(safeChannel))
            .setCategory(Notification.CATEGORY_STATUS)
            .setDefaults(NotificationCompat.DEFAULT_SOUND)
            .setPriority(
                when (safeChannel) {
                    THREAT_ALERT_CHANNEL -> NotificationCompat.PRIORITY_HIGH
                    else -> NotificationCompat.PRIORITY_DEFAULT
                },
            )

        if (safeChannel == THREAT_ALERT_CHANNEL) {
            builder.setVibrate(longArrayOf(0, 140))
        }

        val systemNotificationId = 900000 + abs(
            (notificationId ?: analysisId ?: riskScore ?: System.currentTimeMillis()).hashCode(),
        ) % 99999
        manager.notify(systemNotificationId, builder.build())
        Log.d(TAG_NOTIFY, "notify_called id=$systemNotificationId channel=$safeChannel risk=${riskScore ?: "pending"} fingerprint=${alertEventKey.hashCode()}")
    }

    // ── Launch payload ───────────────────────────────────────────────────────

    fun launchPayloadFrom(intent: Intent?): Map<String, String?>? {
        if (intent?.getBooleanExtra(EXTRA_OPEN, false) != true) return null
        return mapOf(
            "notificationId" to intent.getStringExtra(EXTRA_NOTIFICATION_ID),
            "analysisId" to intent.getStringExtra(EXTRA_ANALYSIS_ID),
        )
    }

    // ── Private helpers ──────────────────────────────────────────────────────

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun monitoredPackages(context: Context): Set<String> =
        prefs(context).getStringSet(MONITORED_PACKAGES, defaultPackages) ?: defaultPackages

    private fun canPostNotifications(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    private fun isDebuggable(context: Context): Boolean =
        (context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0

    private fun immutableFlag(): Int =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0

    private fun knownAppName(packageName: String): String =
        when (packageName) {
            "com.whatsapp" -> "WhatsApp"
            "org.telegram.messenger" -> "Telegram"
            "com.google.android.gm" -> "Gmail"
            "com.google.android.apps.messaging" -> "Google Messages"
            "com.samsung.android.messaging" -> "Samsung Messages"
            "com.android.mms" -> "SMS"
            else -> "تطبيق"
        }

    private fun looksLikePackageName(value: String): Boolean =
        Regex("^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$").matches(value.trim())

    private data class QuickRisk(
        val level: String,
        val score: Int,
        val channelId: String,
        val title: String,
        val body: String,
    )

    private fun quickRiskFor(rawText: String): QuickRisk {
        val text = normalizeArabic(rawText)
        val hasUrl = Regex("""(?i)(https?://|www\.|bit\.ly|tinyurl|t\.co|rb\.gy|cutt\.ly)""").containsMatchIn(text)
        val hasOtp = Regex("""(?i)\b(otp|2fa|verification code|auth code)\b|رمز ?التحقق|كود ?التحقق|رمز ?الدخول|كود ?الدخول|رمز ?التفعيل""").containsMatchIn(text)
        val bankOrAccount = Regex("""(?i)\b(bank|account|login|verify|update)\b|بنك|مصرف|حساب|تحديث|تعليق|ايقاف|إيقاف|تسجيل ?الدخول""").containsMatchIn(text)
        val urgent = Regex("""(?i)urgent|immediately|blocked|suspended|closed|عاجل|فورا|فورًا|اخر ?فرصه|آخر ?فرصة|تعليق|ايقاف|إيقاف|حظر|خلال 24""").containsMatchIn(text)
        val linkAccountUpdate = (hasUrl || Regex("""رابط|الرابط|اضغط|افتح|click|link""").containsMatchIn(text)) &&
            bankOrAccount &&
            Regex("""حدث ?بيانات|تحديث ?بيانات|تفعيل ?الحساب|تأكيد ?الحساب|تاكيد ?الحساب|تحديث ?معلومات""").containsMatchIn(text)
        val sensitiveRequest = hasUnnegatedSensitiveRequest(text)
        val safeContext = isBenignLocalContext(text, hasOtp)

        val dangerous = !safeContext && (
            sensitiveRequest ||
                linkAccountUpdate ||
                (urgent && hasUrl && bankOrAccount)
            )
        val suspicious = !safeContext && (
            dangerous ||
                (hasUrl && bankOrAccount) ||
                (urgent && bankOrAccount) ||
                (hasUrl && !hasOtp) ||
                (bankOrAccount && !Regex("""تم ?خصم|تم ?ايداع|تمت ?عمليه|عملية ?شراء|الرصيد|حواله|حوالة""").containsMatchIn(text)) ||
                (hasOtp && !sensitiveRequest && !isOtpInformational(text))
            )

        return when {
            dangerous -> QuickRisk(
                level = "dangerous",
                score = 90,
                channelId = DANGER_CHANNEL,
                title = "APG: تحذير أمني",
                body = "لا تفتح الرابط ولا تشارك رموز OTP أو بيانات حساسة.",
            )
            suspicious -> QuickRisk(
                level = "suspicious",
                score = 55,
                channelId = WARNING_CHANNEL,
                title = "APG: رسالة تحتاج تحققًا",
                body = "تحقق من الرسالة قبل فتح الرابط أو مشاركة بيانات.",
            )
            else -> QuickRisk(
                level = "safe",
                score = 10,
                channelId = SAFE_CHANNEL,
                title = "فحص رسالة APG",
                body = "لا توجد مؤشرات خطيرة.",
            )
        }
    }

    private fun hasUnnegatedSensitiveRequest(text: String): Boolean {
        val sensitive = Regex("""(?i)\b(otp|2fa|verification code|auth code|cvv|cvc|pin|password|passcode|iban)\b|رمز ?التحقق|كود ?التحقق|رمز ?الدخول|كود ?الدخول|رمز ?التفعيل|كلمه ?المرور|كلمة ?المرور|الرقم ?السري|رقم ?البطاقه|رقم ?البطاقة|بيانات ?البطاقه|بيانات ?البطاقة|بطاقتك|البطاقه|البطاقة""")
        val action = Regex("""(?i)\b(send|share|enter|provide|submit)\b|ارسل|شارك|ادخل|تدخل|اكتب|زودنا|اعطني|اعطيني|ابعت|ابعث|هات|قدم|صورلي|يرجى ?ادخال|يرجى ?ارسال""")
        val questionForCode = Regex("""شو ?رمز|ما ?هو ?رمز|كم ?رمز|الرمز ?اللي ?وصلك|رمز ?واتساب ?اللي ?وصلك""")
        if (questionForCode.containsMatchIn(text) && Regex("""رمز|كود|otp|واتساب""", RegexOption.IGNORE_CASE).containsMatchIn(text)) {
            return true
        }
        for (actionMatch in action.findAll(text)) {
            if (hasLocalNegation(text, actionMatch.range.first)) continue
            val start = (actionMatch.range.first - 45).coerceAtLeast(0)
            val end = (actionMatch.range.last + 46).coerceAtMost(text.length)
            if (sensitive.containsMatchIn(text.substring(start, end))) return true
        }
        return false
    }

    private fun hasLocalNegation(text: String, index: Int): Boolean {
        val start = (index - 18).coerceAtLeast(0)
        val prefix = text.substring(start, index)
        return Regex("""(?i)(لا|لن|لا ?تقم|do not|don't|never)\s*$""").containsMatchIn(prefix) ||
            Regex("""(?i)(لا|لن|do not|don't|never)""").containsMatchIn(prefix.split(Regex("\\s+")).takeLast(4).joinToString(" "))
    }

    private fun isBenignLocalContext(text: String, hasOtp: Boolean): Boolean =
        isWhatsAppVerificationStatus(text) ||
            isBenignBankNotice(text) ||
            isAwarenessMessage(text) ||
            (hasOtp && isOtpInformational(text))

    private fun isOtpInformational(text: String): Boolean =
        Regex("""(?i)your verification code|your otp|do not share|رمز ?التحقق ?الخاص ?بك|كود ?التحقق ?الخاص ?بك|رمز ?الدخول ?لمره ?واحده|رمزك ?هو|لا ?تشاركه|لا ?تشارك|لا ?تفصح|لا ?ترسله|لا ?تعطه""").containsMatchIn(text)

    private fun isAwarenessMessage(text: String): Boolean =
        Regex("""(?i)do not share|never share|رساله ?توعويه|رسالة ?توعوية|نصيحه ?امنيه|نصيحة ?امنية|احذر|لا ?تشارك|لا ?تفصح|لا ?تعط|لا ?ترسل|لا ?تدخل|لا ?تضغط|لن ?يطلب|لا ?يطلب""").containsMatchIn(text)

    private fun isBenignBankNotice(text: String): Boolean =
        Regex("""تم ?خصم|خصم ?مبلغ|تم ?ايداع|تمت ?عمليه|تمت ?عملية|عملية ?شراء|عمليه ?شراء|تم ?الدفع|تم ?السحب|تم ?تنفيذ ?حواله|تم ?تنفيذ ?حوالة|الرصيد|الرصيد ?المتاح|عملية ?ناجحة|عمليه ?ناجحه""").containsMatchIn(text)

    private fun isWhatsAppVerificationStatus(text: String): Boolean =
        Regex("""(?i)whatsapp verification in progress|whatsapp verification|جاري ?التحقق ?من ?واتساب|تم ?التحقق ?من ?واتساب|واتساب:? ?جاري ?التحقق|واتساب ?يتحقق""").containsMatchIn(text)

    private fun extractNotificationText(extras: Bundle): String {
        val parts = mutableListOf<String>()
        listOf(
            Notification.EXTRA_TEXT,
            Notification.EXTRA_BIG_TEXT,
            Notification.EXTRA_SUB_TEXT,
            Notification.EXTRA_SUMMARY_TEXT,
            Notification.EXTRA_CONVERSATION_TITLE,
        ).forEach { key ->
            extras.getCharSequence(key)?.toString()?.takeIf { it.isNotBlank() }?.let { parts.add(it) }
        }
        val lines = extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)
        lines?.forEach { line ->
            line?.toString()?.takeIf { it.isNotBlank() }?.let { parts.add(it) }
        }
        return parts.distinct().joinToString(" ")
    }

    private fun normalizeArabic(value: String): String =
        value.lowercase()
            .replace(Regex("[ؐ-ًؚ-ٰٟۖ-ۭ]"), "")
            .replace('أ', 'ا')
            .replace('إ', 'ا')
            .replace('آ', 'ا')
            .replace('ى', 'ي')
            .replace('ة', 'ه')

    private fun colorForChannel(channelId: String): Int =
        when (channelId) {
            THREAT_ALERT_CHANNEL -> Color.rgb(198, 40, 40)
            DANGER_CHANNEL -> Color.rgb(198, 40, 40)
            WARNING_CHANNEL -> Color.rgb(245, 124, 0)
            else -> Color.rgb(46, 125, 50)
        }

    private fun severityForChannel(channelId: String): Int =
        when (channelId) {
            THREAT_ALERT_CHANNEL -> 3
            DANGER_CHANNEL -> 3
            WARNING_CHANNEL -> 2
            else -> 1
        }

    private fun recentAlertShownAt(context: Context, key: String): Long? {
        val value = prefs(context).getLong("$RECENT_ALERT_PREFIX$key", -1L)
        return if (value > 0) value else null
    }

    private fun rememberAlertShown(context: Context, key: String, now: Long) {
        val preferences = prefs(context)
        val editor = preferences.edit().putLong("$RECENT_ALERT_PREFIX$key", now)
        preferences.all
            .filterKeys { it.startsWith(RECENT_ALERT_PREFIX) }
            .forEach { (storedKey, storedValue) ->
                val shownAt = storedValue as? Long ?: 0L
                if (now - shownAt > DEDUP_WINDOW_MS) editor.remove(storedKey)
            }
        editor.apply()
    }

    private fun pruneRecentEntries(now: Long) {
        shownAtBySource
            .filterValues { now - it > DEDUP_WINDOW_MS }
            .keys.toList()
            .forEach {
                shownAtBySource.remove(it)
                shownSeverityBySource.remove(it)
            }
    }

    private fun eventBucket(now: Long): Long = now / DEDUP_WINDOW_MS

    private fun alertEventKey(
        sourceKey: String,
        analysisId: String?,
        riskScore: Int?,
        severity: Int,
        now: Long,
    ): String {
        val identity = analysisId?.takeIf { it.isNotBlank() } ?: "bucket-${eventBucket(now)}"
        return "$sourceKey|$identity|${riskScore ?: "pending"}|$severity"
    }
}
