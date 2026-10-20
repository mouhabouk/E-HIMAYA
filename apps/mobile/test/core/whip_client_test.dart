import 'package:dio/dio.dart';
import 'package:ehimaya/core/webrtc/whip_client.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';

const offer =
    'v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\n';
const answer =
    'v=0\r\no=- 3 4 IN IP4 10.0.0.1\r\ns=-\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\n';
final whipUrl = Uri.parse('https://media.ehimaya.tn/live/abc/whip');
const token = 'publish-token-43-chars-xxxxxxxxxxxxxxxxxxxxx';

void main() {
  late FakeAdapter adapter;
  late WhipClient client;

  setUp(() {
    adapter = FakeAdapter((_) => const FakeResponse(500));
    client = WhipClient(Dio()..httpClientAdapter = adapter);
  });

  group('publish', () {
    test(
      'POSTs the SDP offer with the publish token and resolves Location',
      () async {
        adapter.handler = (r) => const FakeResponse(
          201,
          text: answer,
          headers: {
            'Location': '/live/abc/whip/session-1',
            'Content-Type': 'application/sdp',
            'ETag': '"e1"',
          },
        );
        final session = await client.publish(
          whipUrl: whipUrl,
          token: token,
          offerSdp: offer,
        );
        final r = adapter.requests.single;
        expect(r.method, 'POST');
        expect(r.uri, whipUrl);
        expect(r.header('Authorization'), 'Bearer $token');
        expect(r.header('Content-Type'), startsWith('application/sdp'));
        expect(r.text, offer);
        // Never the platform identity: no device key towards the media server.
        expect(r.header('X-Device-Key'), isNull);
        expect(
          session.resourceUrl,
          Uri.parse('https://media.ehimaya.tn/live/abc/whip/session-1'),
        );
        expect(session.answerSdp, answer);
        expect(session.etag, '"e1"');
      },
    );

    test('keeps an absolute Location as is', () async {
      adapter.handler = (r) => const FakeResponse(
        201,
        text: answer,
        headers: {'Location': 'https://other.tn/s/9'},
      );
      final session = await client.publish(
        whipUrl: whipUrl,
        token: token,
        offerSdp: offer,
      );
      expect(session.resourceUrl, Uri.parse('https://other.tn/s/9'));
    });

    test('401 and 403 are an unauthorized token', () async {
      for (final status in [401, 403]) {
        adapter.handler = (r) => FakeResponse(status);
        await expectLater(
          client.publish(whipUrl: whipUrl, token: token, offerSdp: offer),
          throwsA(
            isA<WhipException>()
                .having((e) => e.failure, 'failure', WhipFailure.unauthorized)
                .having((e) => e.isTransient, 'transient', false),
          ),
        );
      }
    });

    test('other 4xx are rejected, 5xx are transient server errors', () async {
      adapter.handler = (r) => const FakeResponse(400);
      await expectLater(
        client.publish(whipUrl: whipUrl, token: token, offerSdp: offer),
        throwsA(
          isA<WhipException>().having(
            (e) => e.failure,
            'failure',
            WhipFailure.rejected,
          ),
        ),
      );
      adapter.handler = (r) => const FakeResponse(503);
      await expectLater(
        client.publish(whipUrl: whipUrl, token: token, offerSdp: offer),
        throwsA(
          isA<WhipException>()
              .having((e) => e.failure, 'failure', WhipFailure.server)
              .having((e) => e.isTransient, 'transient', true),
        ),
      );
    });

    test(
      'a 201 without Location or without SDP is not a valid answer',
      () async {
        adapter.handler = (r) => const FakeResponse(201, text: answer);
        await expectLater(
          client.publish(whipUrl: whipUrl, token: token, offerSdp: offer),
          throwsA(isA<WhipException>()),
        );
        adapter.handler = (r) => const FakeResponse(
          201,
          text: 'nope',
          headers: {'Location': '/s/1'},
        );
        await expectLater(
          client.publish(whipUrl: whipUrl, token: token, offerSdp: offer),
          throwsA(isA<WhipException>()),
        );
        // 200 is not the WHIP success code either.
        adapter.handler = (r) => const FakeResponse(
          200,
          text: answer,
          headers: {'Location': '/s/1'},
        );
        await expectLater(
          client.publish(whipUrl: whipUrl, token: token, offerSdp: offer),
          throwsA(isA<WhipException>()),
        );
      },
    );

    test('no network → network failure (transient)', () async {
      adapter.handler = (r) => const FakeResponse.network();
      await expectLater(
        client.publish(whipUrl: whipUrl, token: token, offerSdp: offer),
        throwsA(
          isA<WhipException>()
              .having((e) => e.failure, 'failure', WhipFailure.network)
              .having((e) => e.isTransient, 'transient', true),
        ),
      );
    });
  });

  group('session resource', () {
    final session = WhipSession(
      resourceUrl: Uri.parse('https://media.ehimaya.tn/live/abc/whip/s1'),
      answerSdp: answer,
      etag: '"e1"',
    );

    test('DELETE ends the session with the token', () async {
      adapter.handler = (r) => const FakeResponse(200);
      await client.delete(session: session, token: token);
      final r = adapter.requests.single;
      expect(r.method, 'DELETE');
      expect(r.uri, session.resourceUrl);
      expect(r.header('Authorization'), 'Bearer $token');
    });

    test('DELETE of a session already gone succeeds', () async {
      for (final status in [404, 410]) {
        adapter.handler = (r) => FakeResponse(status);
        await client.delete(session: session, token: token);
      }
    });

    test('DELETE failure surfaces', () async {
      adapter.handler = (r) => const FakeResponse(500);
      await expectLater(
        client.delete(session: session, token: token),
        throwsA(isA<WhipException>()),
      );
    });

    test(
      'PATCH trickles candidates with If-Match; 405 means unsupported',
      () async {
        adapter.handler = (r) => const FakeResponse(204);
        final fragment = trickleFragment(
          iceUfrag: 'uf',
          icePwd: 'pw',
          mid: '0',
          candidates: [
            'candidate:1 1 udp 2122260223 192.168.1.2 50000 typ host',
          ],
        );
        expect(
          await client.patchCandidates(
            session: session,
            token: token,
            sdpFragment: fragment,
          ),
          isTrue,
        );
        final r = adapter.requests.single;
        expect(r.method, 'PATCH');
        expect(r.header('Content-Type'), startsWith(WhipClient.trickleType));
        expect(r.header('If-Match'), '"e1"');
        expect(r.text, contains('a=ice-ufrag:uf\r\n'));
        expect(r.text, contains('a=mid:0\r\n'));
        expect(r.text, contains('a=candidate:1 1 udp'));

        adapter.handler = (r) => const FakeResponse(405);
        expect(
          await client.patchCandidates(
            session: session,
            token: token,
            sdpFragment: fragment,
          ),
          isFalse,
        );
      },
    );
  });
}
