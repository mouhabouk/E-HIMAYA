import Flutter
import UIKit
import UserNotifications

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
    if let registrar = engineBridge.pluginRegistry.registrar(forPlugin: "EHimayaDevice") {
      DeviceChannel.register(messenger: registrar.messenger())
    }
  }
}

/// `tn.ehimaya.app/device`: battery level for the in-app battery saver and the notification
/// settings for the alert delivery check (same contract as MainActivity.kt; Android-only
/// methods answer false/null).
enum DeviceChannel {
  static func register(messenger: FlutterBinaryMessenger) {
    let channel = FlutterMethodChannel(name: "tn.ehimaya.app/device", binaryMessenger: messenger)
    channel.setMethodCallHandler { call, result in
      switch call.method {
      case "battery":
        let device = UIDevice.current
        // Read on demand only; monitoring is turned off again right away.
        device.isBatteryMonitoringEnabled = true
        let level = device.batteryLevel
        let state = device.batteryState
        device.isBatteryMonitoringEnabled = false
        result([
          "level": level < 0 ? NSNull() : Int((level * 100).rounded()),
          "charging": state == .charging || state == .full,
          "powerSave": ProcessInfo.processInfo.isLowPowerModeEnabled,
        ] as [String: Any])
      case "alertHealth":
        UNUserNotificationCenter.current().getNotificationSettings { settings in
          let enabled = settings.authorizationStatus == .authorized
            || settings.authorizationStatus == .provisional
            || settings.authorizationStatus == .ephemeral
          DispatchQueue.main.async {
            result(["notificationsEnabled": enabled] as [String: Any])
          }
        }
      case "openChannelSettings", "openAppNotificationSettings":
        let target: String
        if #available(iOS 16.0, *) {
          target = UIApplication.openNotificationSettingsURLString
        } else {
          target = UIApplication.openSettingsURLString
        }
        guard let url = URL(string: target) else {
          result(false)
          return
        }
        UIApplication.shared.open(url) { opened in result(opened) }
      case "lockedAlertMode":
        // iOS never shows an app over the lock screen.
        result(false)
      case "requestUnlock":
        result(true)
      case "keepScreenOn":
        // Live streaming (phase 6): no auto-lock while the camera is published.
        let on = (call.arguments as? [String: Any])?["on"] as? Bool ?? false
        UIApplication.shared.isIdleTimerDisabled = on
        result(true)
      case "openAppSettings":
        guard let url = URL(string: UIApplication.openSettingsURLString) else {
          result(false)
          return
        }
        UIApplication.shared.open(url) { opened in result(opened) }
      case "requestIgnoreBatteryOptimizations", "openFullScreenIntentSettings",
        "openDndAccessSettings":
        result(false)
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }
}
