package tn.ehimaya.app

import android.app.Activity
import android.app.KeyguardManager
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.ContactsContract
import android.provider.Settings
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONException
import org.json.JSONObject

/**
 * Hosts Flutter, plus the small `tn.ehimaya.app/device` bridge used by the battery saver and the
 * alert delivery check (battery level, Do Not Disturb, battery optimisation, channel settings).
 * No extra plugin is needed for these.
 *
 * Phase B2 adds: the system contact picker (one number, no contacts permission), the phone's own
 * lock check before the medical file opens, and the app shortcuts (res/xml/shortcuts.xml).
 */
class MainActivity : FlutterActivity() {
    /** The activity is currently allowed over the lock screen (severe alert only). */
    private var shownOverLockScreen = false

    /** Shortcut chosen on a long press of the icon, until Flutter takes it. */
    private var pendingShortcut: String? = null
    private var pickContactResult: MethodChannel.Result? = null
    private var confirmCredentialResult: MethodChannel.Result? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showOverLockScreenForAlert(intent)
        keepShortcut(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        showOverLockScreenForAlert(intent)
        keepShortcut(intent)
    }

    /**
     * Static shortcuts start this activity with the extra `shortcut`. Only the known names are
     * kept: another app sending this activity an intent can at most open one of these screens.
     */
    private fun keepShortcut(intent: Intent?) {
        val name = intent?.getStringExtra(SHORTCUT_EXTRA) ?: return
        if (name in SHORTCUTS) pendingShortcut = name
    }

    /**
     * The system contact picker: the user chooses one phone number, and only that one reaches
     * the app (temporary read grant of the picked row). No READ_CONTACTS permission.
     */
    private fun pickContact(result: MethodChannel.Result) {
        if (pickContactResult != null) {
            result.success(null)
            return
        }
        val intent = Intent(Intent.ACTION_PICK, ContactsContract.CommonDataKinds.Phone.CONTENT_URI)
        try {
            pickContactResult = result
            @Suppress("DEPRECATION")
            startActivityForResult(intent, PICK_CONTACT)
        } catch (e: Exception) {
            pickContactResult = null
            result.success(null)
        }
    }

    private fun pickedContact(data: Intent?): Map<String, String?>? {
        val uri = data?.data ?: return null
        return try {
            contentResolver.query(
                uri,
                arrayOf(
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER,
                ),
                null,
                null,
                null,
            )?.use { c ->
                if (!c.moveToFirst()) return null
                mapOf("name" to c.getString(0), "phone" to c.getString(1))
            }
        } catch (e: Exception) {
            null
        }
    }

    /**
     * The phone's own lock (PIN, pattern, fingerprint) before the medical file is shown. Null when
     * the phone has no secure lock: the app then explains that the lock cannot protect the file.
     */
    private fun confirmCredential(title: String?, description: String?, result: MethodChannel.Result) {
        val keyguard = getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        if (!keyguard.isDeviceSecure || confirmCredentialResult != null) {
            result.success(null)
            return
        }
        @Suppress("DEPRECATION")
        val intent = keyguard.createConfirmDeviceCredentialIntent(title, description)
        if (intent == null) {
            result.success(null)
            return
        }
        try {
            confirmCredentialResult = result
            @Suppress("DEPRECATION")
            startActivityForResult(intent, CONFIRM_CREDENTIAL)
        } catch (e: Exception) {
            confirmCredentialResult = null
            result.success(null)
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        when (requestCode) {
            PICK_CONTACT -> {
                val result = pickContactResult
                pickContactResult = null
                result?.success(if (resultCode == Activity.RESULT_OK) pickedContact(data) else null)
            }
            CONFIRM_CREDENTIAL -> {
                val result = confirmCredentialResult
                confirmCredentialResult = null
                result?.success(resultCode == Activity.RESULT_OK)
            }
            else -> super.onActivityResult(requestCode, resultCode, data)
        }
    }

    override fun onStop() {
        super.onStop()
        // Only the alert that woke the phone is shown over the lock screen, never the app later.
        setLockScreenFlags(false)
    }

    /**
     * The full-screen intent of a most severe official alert (flutter_local_notifications action
     * SELECT_NOTIFICATION, payload of an alert with severity "high") opens the app over the lock
     * screen and turns the screen on. Set at run time, and only for that public content, so any
     * other notification (personal ones included) and the rest of the app still need an unlock.
     */
    private fun showOverLockScreenForAlert(intent: Intent?) {
        if (intent?.action != "SELECT_NOTIFICATION") return
        val severe = try {
            val payload = JSONObject(intent.getStringExtra("payload") ?: "{}")
            payload.optString("type") == "alert" && payload.optString("severity") == "high"
        } catch (e: JSONException) {
            false
        }
        if (severe) setLockScreenFlags(true)
    }

    private fun setLockScreenFlags(on: Boolean) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(on)
            setTurnScreenOn(on)
            shownOverLockScreen = on
        }
    }

    /**
     * True while the app is displayed over a locked keyguard: Flutter then shows only the
     * public alert view and asks for an unlock before anything else.
     */
    private fun lockedAlertMode(): Boolean {
        val keyguard = getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        return shownOverLockScreen && keyguard.isKeyguardLocked
    }

    /** Asks the user to unlock (PIN, biometrics). On success the lock-screen flags are cleared. */
    private fun requestUnlock(result: MethodChannel.Result) {
        val keyguard = getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        if (!keyguard.isKeyguardLocked) {
            setLockScreenFlags(false)
            result.success(true)
            return
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            result.success(false)
            return
        }
        keyguard.requestDismissKeyguard(
            this,
            object : KeyguardManager.KeyguardDismissCallback() {
                override fun onDismissSucceeded() {
                    setLockScreenFlags(false)
                    result.success(true)
                }

                override fun onDismissCancelled() {
                    result.success(false)
                }

                override fun onDismissError() {
                    result.success(false)
                }
            },
        )
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "tn.ehimaya.app/device")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "battery" -> result.success(battery())
                    "lockedAlertMode" -> result.success(lockedAlertMode())
                    "requestUnlock" -> requestUnlock(result)
                    "alertHealth" -> result.success(alertHealth())
                    "openChannelSettings" ->
                        result.success(openChannelSettings(call.argument<String>("channelId")))
                    "openAppNotificationSettings" -> result.success(openChannelSettings(null))
                    "requestIgnoreBatteryOptimizations" ->
                        result.success(requestIgnoreBatteryOptimizations())
                    "openFullScreenIntentSettings" -> result.success(openFullScreenIntentSettings())
                    "keepScreenOn" -> {
                        keepScreenOn(call.argument<Boolean>("on") == true)
                        result.success(true)
                    }
                    "openAppSettings" -> result.success(start(appDetails()))
                    "openDndAccessSettings" ->
                        result.success(start(Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)))
                    "pickContact" -> pickContact(result)
                    "confirmCredential" -> confirmCredential(
                        call.argument<String>("title"),
                        call.argument<String>("description"),
                        result,
                    )
                    "deviceSecure" -> result.success(
                        (getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager).isDeviceSecure,
                    )
                    "takeShortcut" -> {
                        result.success(pendingShortcut)
                        pendingShortcut = null
                    }
                    else -> result.notImplemented()
                }
            }
    }

    /** Live streaming (phase 6): the screen stays on while the camera is published. */
    private fun keepScreenOn(on: Boolean) {
        if (on) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    private fun battery(): Map<String, Any?> {
        val manager = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val power = getSystemService(Context.POWER_SERVICE) as PowerManager
        val level = manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val charging = manager.isCharging
        return mapOf(
            "level" to if (level in 0..100) level else null,
            "charging" to charging,
            "powerSave" to power.isPowerSaveMode,
        )
    }

    private fun alertHealth(): Map<String, Any?> {
        val notifications = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val power = getSystemService(Context.POWER_SERVICE) as PowerManager
        val channels = mutableMapOf<String, Int>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            for (channel in notifications.notificationChannels) {
                channels[channel.id] = channel.importance
            }
        }
        return mapOf(
            "notificationsEnabled" to notifications.areNotificationsEnabled(),
            "channels" to channels,
            "doNotDisturb" to
                (notifications.currentInterruptionFilter > NotificationManager.INTERRUPTION_FILTER_ALL),
            "policyAccess" to notifications.isNotificationPolicyAccessGranted,
            "ignoringBatteryOptimizations" to power.isIgnoringBatteryOptimizations(packageName),
            "fullScreenIntentAllowed" to
                if (Build.VERSION.SDK_INT >= 34) notifications.canUseFullScreenIntent() else null,
        )
    }

    private fun openChannelSettings(channelId: String?): Boolean {
        val intent = if (channelId != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
                .putExtra(Settings.EXTRA_CHANNEL_ID, channelId)
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
        } else {
            appDetails()
        }
        return start(intent) || start(appDetails())
    }

    /**
     * Shown only to a volunteer on call, after an explanation in the app. Falls back to the
     * list of optimised apps when the direct dialog is unavailable.
     */
    private fun requestIgnoreBatteryOptimizations(): Boolean {
        val power = getSystemService(Context.POWER_SERVICE) as PowerManager
        if (power.isIgnoringBatteryOptimizations(packageName)) return true
        return start(
            Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                .setData(Uri.parse("package:$packageName")),
        ) || start(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
    }

    private fun openFullScreenIntentSettings(): Boolean {
        if (Build.VERSION.SDK_INT < 34) return false
        return start(
            Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT)
                .setData(Uri.parse("package:$packageName")),
        ) || openChannelSettings(null)
    }

    private fun appDetails() =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).setData(Uri.parse("package:$packageName"))

    private fun start(intent: Intent): Boolean = try {
        startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    } catch (e: Exception) {
        false
    }

    private companion object {
        const val PICK_CONTACT = 4201
        const val CONFIRM_CREDENTIAL = 4202
        const val SHORTCUT_EXTRA = "shortcut"
        val SHORTCUTS = setOf("sos_message", "report")
    }
}
