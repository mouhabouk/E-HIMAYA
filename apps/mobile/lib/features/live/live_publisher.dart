import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';

import '../../core/logging/log.dart';
import 'live_policies.dart';

final _log = logger('live.publisher');

/// Connection of the media path, as far as the controller cares.
enum PublisherConnection { connecting, connected, disconnected, failed, closed }

/// Camera or microphone refused by the user (or by a policy).
class MediaPermissionDenied implements Exception {
  const MediaPermissionDenied();
}

/// No camera, or the camera is busy (another app, a call).
class MediaUnavailable implements Exception {
  const MediaUnavailable();
}

/// The local side of a WHIP publish: camera + microphone, one send-only peer connection.
/// The controller drives it; tests replace it with a fake.
abstract class LivePublisher {
  /// Opens the camera (back camera first) and the microphone. Throws [MediaPermissionDenied]
  /// or [MediaUnavailable].
  Future<void> openMedia({required bool frontCamera});

  /// Creates a fresh peer connection on the opened media and returns the SDP offer with the
  /// candidates gathered within [gatherFor] (non-trickle WHIP works with MediaMTX).
  Future<String> createOffer({
    required LiveQuality quality,
    Duration gatherFor = const Duration(seconds: 3),
  });

  /// Applies the WHIP answer.
  Future<void> applyAnswer(String sdp);

  /// Candidates found after the offer was sent (a=candidate lines), for a trickle PATCH.
  Stream<String> get lateCandidates;

  Stream<PublisherConnection> get connection;

  Future<void> setQuality(LiveQuality quality);

  /// Outgoing network statistics, null when not available yet.
  Future<LiveNetworkSample?> sample();

  /// Switches between the back and front cameras; returns true when the front one is now used.
  Future<bool> switchCamera();

  Future<void> setMuted(bool muted);

  /// Closes the peer connection only (the camera stays open for a reconnect).
  Future<void> closeConnection();

  /// Closes everything, camera and microphone included.
  Future<void> dispose();

  /// Local camera preview.
  Widget preview(BuildContext context);
}

/// [LivePublisher] on flutter_webrtc (libwebrtc on Android and iOS).
class WebRtcLivePublisher implements LivePublisher {
  WebRtcLivePublisher({this.iceServers = const []});

  /// Optional STUN/TURN URLs (`--dart-define=WEBRTC_ICE_SERVERS=stun:…,turn:…`). MediaMTX on a
  /// public address works without any: it learns the phone's address from its checks.
  final List<String> iceServers;

  MediaStream? _stream;
  RTCPeerConnection? _pc;
  RTCRtpSender? _videoSender;
  RTCVideoRenderer? _renderer;
  final _renderReady = ValueNotifier<bool>(false);
  bool _front = false;
  bool _offerSent = false;
  final _late = StreamController<String>.broadcast();
  final _connection = StreamController<PublisherConnection>.broadcast();

  @override
  Stream<String> get lateCandidates => _late.stream;

  @override
  Stream<PublisherConnection> get connection => _connection.stream;

  @override
  Future<void> openMedia({required bool frontCamera}) async {
    if (_stream != null) return;
    _front = frontCamera;
    final constraints = <String, Object?>{
      'audio': {
        'echoCancellation': true,
        'noiseSuppression': true,
        'autoGainControl': true,
      },
      'video': {
        'facingMode': frontCamera ? 'user' : 'environment',
        'width': {'ideal': LiveQuality.captureWidth},
        'height': {'ideal': LiveQuality.captureHeight},
        'frameRate': {'ideal': LiveQuality.captureFramerate},
      },
    };
    try {
      _stream = await navigator.mediaDevices.getUserMedia(constraints);
    } on Object catch (e) {
      final text = '$e'.toLowerCase();
      _log.info('getUserMedia failed: ${e.runtimeType}');
      if (text.contains('permission') ||
          text.contains('notallowed') ||
          text.contains('denied')) {
        throw const MediaPermissionDenied();
      }
      throw const MediaUnavailable();
    }
    final renderer = RTCVideoRenderer();
    await renderer.initialize();
    renderer.srcObject = _stream;
    _renderer = renderer;
    _renderReady.value = true;
  }

  Map<String, Object?> get _configuration => {
    'iceServers': [
      for (final url in iceServers) {'urls': url},
    ],
    'sdpSemantics': 'unified-plan',
    'bundlePolicy': 'max-bundle',
    'rtcpMuxPolicy': 'require',
  };

  @override
  Future<String> createOffer({
    required LiveQuality quality,
    Duration gatherFor = const Duration(seconds: 3),
  }) async {
    final stream = _stream;
    if (stream == null) throw const MediaUnavailable();
    await closeConnection();
    _offerSent = false;
    final pc = await createPeerConnection(_configuration);
    _pc = pc;
    final gathered = Completer<void>();
    pc.onIceGatheringState = (state) {
      if (state == RTCIceGatheringState.RTCIceGatheringStateComplete &&
          !gathered.isCompleted) {
        gathered.complete();
      }
    };
    pc.onIceCandidate = (candidate) {
      final line = candidate.candidate;
      if (_offerSent && line != null && line.isNotEmpty) _late.add(line);
    };
    pc.onConnectionState = (state) {
      final mapped = switch (state) {
        RTCPeerConnectionState.RTCPeerConnectionStateConnected =>
          PublisherConnection.connected,
        RTCPeerConnectionState.RTCPeerConnectionStateDisconnected =>
          PublisherConnection.disconnected,
        RTCPeerConnectionState.RTCPeerConnectionStateFailed =>
          PublisherConnection.failed,
        RTCPeerConnectionState.RTCPeerConnectionStateClosed =>
          PublisherConnection.closed,
        _ => PublisherConnection.connecting,
      };
      if (!_connection.isClosed) _connection.add(mapped);
    };

    for (final track in stream.getAudioTracks()) {
      await pc.addTransceiver(
        track: track,
        kind: RTCRtpMediaType.RTCRtpMediaTypeAudio,
        init: RTCRtpTransceiverInit(
          direction: TransceiverDirection.SendOnly,
          streams: [stream],
          sendEncodings: [
            RTCRtpEncoding(maxBitrate: LiveQuality.audioMaxBitrate),
          ],
        ),
      );
    }
    for (final track in stream.getVideoTracks()) {
      final transceiver = await pc.addTransceiver(
        track: track,
        kind: RTCRtpMediaType.RTCRtpMediaTypeVideo,
        init: RTCRtpTransceiverInit(
          direction: TransceiverDirection.SendOnly,
          streams: [stream],
          sendEncodings: [_encoding(quality)],
        ),
      );
      _videoSender = transceiver.sender;
    }

    final offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await gathered.future.timeout(gatherFor, onTimeout: () {});
    final local = await pc.getLocalDescription();
    _offerSent = true;
    return local?.sdp ?? offer.sdp ?? '';
  }

  static RTCRtpEncoding _encoding(LiveQuality q) => RTCRtpEncoding(
    maxBitrate: q.maxBitrate,
    maxFramerate: q.maxFramerate,
    scaleResolutionDownBy: q.scaleDown,
    priority: RTCPriorityType.high,
  );

  @override
  Future<void> applyAnswer(String sdp) async {
    await _pc?.setRemoteDescription(RTCSessionDescription(sdp, 'answer'));
  }

  @override
  Future<void> setQuality(LiveQuality quality) async {
    final sender = _videoSender;
    if (sender == null) return;
    try {
      final params = sender.parameters;
      final encodings = params.encodings;
      if (encodings == null || encodings.isEmpty) {
        params.encodings = [_encoding(quality)];
      } else {
        for (final e in encodings) {
          e
            ..maxBitrate = quality.maxBitrate
            ..maxFramerate = quality.maxFramerate
            ..scaleResolutionDownBy = quality.scaleDown;
        }
      }
      params.degradationPreference = RTCDegradationPreference.BALANCED;
      await sender.setParameters(params);
    } on Object catch (e) {
      _log.info('setParameters failed: ${e.runtimeType}');
    }
  }

  @override
  Future<LiveNetworkSample?> sample() async {
    final pc = _pc;
    if (pc == null) return null;
    try {
      double? bw;
      double? loss;
      Duration? rtt;
      for (final r in await pc.getStats()) {
        final v = r.values;
        if (r.type == 'candidate-pair' &&
            (v['nominated'] == true || v['selected'] == true)) {
          final a = v['availableOutgoingBitrate'];
          if (a is num) bw = a.toDouble();
          final t = v['currentRoundTripTime'];
          if (t is num) rtt = Duration(milliseconds: (t * 1000).round());
        } else if (r.type == 'remote-inbound-rtp' && v['kind'] == 'video') {
          final f = v['fractionLost'];
          if (f is num) loss = f.toDouble();
        }
      }
      return LiveNetworkSample(
        availableOutgoingBitrate: bw,
        fractionLost: loss,
        roundTripTime: rtt,
      );
    } on Object {
      return null;
    }
  }

  @override
  Future<bool> switchCamera() async {
    final track = _stream?.getVideoTracks().firstOrNull;
    if (track == null) return _front;
    try {
      await Helper.switchCamera(track);
      _front = !_front;
    } on Object catch (e) {
      _log.info('switchCamera failed: ${e.runtimeType}');
    }
    return _front;
  }

  @override
  Future<void> setMuted(bool muted) async {
    for (final t in _stream?.getAudioTracks() ?? const <MediaStreamTrack>[]) {
      t.enabled = !muted;
    }
  }

  @override
  Future<void> closeConnection() async {
    final pc = _pc;
    _pc = null;
    _videoSender = null;
    if (pc == null) return;
    pc
      ..onConnectionState = null
      ..onIceCandidate = null
      ..onIceGatheringState = null;
    try {
      await pc.close();
      await pc.dispose();
    } on Object {
      // Already closed by the native side.
    }
  }

  @override
  Future<void> dispose() async {
    await closeConnection();
    final stream = _stream;
    _stream = null;
    if (stream != null) {
      for (final t in stream.getTracks()) {
        try {
          await t.stop();
        } on Object {
          // Track already ended.
        }
      }
      await stream.dispose();
    }
    _renderReady.value = false;
    final renderer = _renderer;
    _renderer = null;
    if (renderer != null) {
      renderer.srcObject = null;
      await renderer.dispose();
    }
    await _late.close();
    await _connection.close();
  }

  @override
  Widget preview(BuildContext context) => ValueListenableBuilder<bool>(
    valueListenable: _renderReady,
    builder: (context, ready, _) {
      final renderer = _renderer;
      if (!ready || renderer == null) {
        return const ColoredBox(color: Colors.black);
      }
      return RTCVideoView(
        renderer,
        objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
        mirror: _front,
      );
    },
  );
}

/// STUN/TURN servers given at build time (comma separated), none by default.
const _iceServersDefine = String.fromEnvironment('WEBRTC_ICE_SERVERS');

List<String> configuredIceServers([String raw = _iceServersDefine]) => [
  for (final s in raw.split(','))
    if (s.trim().isNotEmpty) s.trim(),
];

/// A new publisher for each live session (it owns the camera).
final livePublisherFactoryProvider = Provider<LivePublisher Function()>(
  (ref) =>
      () => WebRtcLivePublisher(iceServers: configuredIceServers()),
);
