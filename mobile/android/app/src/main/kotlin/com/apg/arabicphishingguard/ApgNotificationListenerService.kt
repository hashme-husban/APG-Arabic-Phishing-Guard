package com.apg.arabicphishingguard

import android.service.notification.StatusBarNotification
import notification.listener.service.NotificationListener

class ApgNotificationListenerService : NotificationListener() {
    override fun onNotificationPosted(notification: StatusBarNotification) {
        super.onNotificationPosted(notification)
        ApgNotificationBridge.handleCapturedNotification(applicationContext, notification)
    }
}
