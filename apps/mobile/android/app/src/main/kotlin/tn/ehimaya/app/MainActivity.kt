package tn.ehimaya.app

import android.app.KeyguardManager
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONException
import org.json.JSONObject

/**
 * Hosts Flutter, plus the small `tn.ehimaya.app/device` bridge used by the battery saver and the
 * alert delivery check (battery level, Do Not Disturb, battery optimisation, channel settings).
 * No extra plugin is needed for these.
 */
class MainActivity : FlutterActivity() {
    /** The activity is currently allowed over the lock screen (severe alert only). */
    private var shownOverLockScreen = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showOverLockScreenForAlert(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        showOverLockScreenForAlert(intent)
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
                    "openDndAccessSettings" ->
                        result.success(start(Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)))
                    else -> result.notImplemented()
                }
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
}
