# ء-حماية / e-Himaya — telephony (Asterisk 22 LTS, GPL-2.0, run as a separate service: docs/telephony.md).
#
# Built from the official release tarball (pinned by SHA-256) with only the modules the platform uses: PJSIP (trunk,
# WebRTC over WSS with DTLS-SRTP), app_queue, MixMonitor, ConfBridge, ARI/Stasis. No sound packages, no AMI, no
# CDR/CEL back-ends. The bundled pjproject is pinned by SHA-256 too (Asterisk also checks its MD5).
# Targets: "runtime" (the telephony service) and "call-sim" (SIMULATION: scripted caller for development).
# Base images pinned by digest (tag kept for readability); Dependabot proposes the updates (.github/dependabot.yml).

FROM ubuntu:26.04@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944 AS build
ARG ASTERISK_VERSION=22.11.0
ARG ASTERISK_SHA256=3bd5ee040509a3d3cd9b1ba9520c18e6ec0a7e7981ca68c457dcd36ba3c54d94
ARG PJPROJECT_VERSION=2.17
ARG PJPROJECT_SHA256=04b2eb1f0f01aa0ad1945b167171843448a51aa6b7c3e806496d434f13a112b7
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl bzip2 patch pkg-config file \
      libedit-dev libjansson-dev libxml2-dev uuid-dev libsqlite3-dev libssl-dev libsrtp2-dev liburiparser-dev \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# Official release assets (the same tarball as downloads.asterisk.org), verified before anything is unpacked.
RUN curl -fsSL -o asterisk.tar.gz \
      "https://github.com/asterisk/asterisk/releases/download/${ASTERISK_VERSION}/asterisk-${ASTERISK_VERSION}.tar.gz" \
 && echo "${ASTERISK_SHA256}  asterisk.tar.gz" | sha256sum -c - \
 && curl -fsSL -o "/tmp/pjproject-${PJPROJECT_VERSION}.tar.bz2" \
      "https://raw.githubusercontent.com/asterisk/third-party/master/pjproject/${PJPROJECT_VERSION}/pjproject-${PJPROJECT_VERSION}.tar.bz2" \
 && echo "${PJPROJECT_SHA256}  /tmp/pjproject-${PJPROJECT_VERSION}.tar.bz2" | sha256sum -c - \
 && tar xzf asterisk.tar.gz --strip-components=1 \
 && rm asterisk.tar.gz
# The bundled pjproject is built first (alone), then Asterisk in parallel.
RUN ./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --libdir=/usr/lib \
      --with-pjproject-bundled --with-download-cache=/tmp --disable-xmldoc \
      --without-dahdi --without-pri --without-ss7 --without-gtk2 --without-x11 --without-sdl --without-postgres \
      --without-unixodbc --without-libcurl --without-ldap --without-lua --without-snmp --without-jack \
      --without-portaudio --without-radius --without-tds --without-neon --without-ical --without-iksemel \
      --without-imap --without-gmime --without-libxslt --without-speex --without-speexdsp --without-ogg \
      --without-vorbis --without-codec2 --without-opus --without-unbound --without-bluetooth \
      > /tmp/configure.log \
 && make -s menuselect.makeopts \
 && for category in ADDONS APPS BRIDGES CDR CEL CHANNELS CODECS FORMATS FUNCS PBX RES TESTS UTILS AGIS \
      CORE_SOUNDS MOH EXTRA_SOUNDS; do \
      menuselect/menuselect --disable-category "MENUSELECT_${category}" menuselect.makeopts; done \
 && menuselect/menuselect --disable BUILD_NATIVE \
      --enable app_dial --enable app_queue --enable app_mixmonitor --enable app_confbridge --enable app_stasis \
      --enable app_playback --enable app_echo --enable app_userevent --enable app_channelredirect \
      --enable app_stack --enable app_verbose --enable app_senddtmf --enable app_exec \
      --enable bridge_simple --enable bridge_native_rtp --enable bridge_softmix --enable bridge_holding \
      --enable bridge_builtin_features --enable bridge_builtin_interval_features \
      --enable chan_pjsip --enable chan_bridge_media \
      --enable codec_ulaw --enable codec_alaw --enable codec_a_mu --enable codec_g722 --enable codec_resample \
      --enable format_wav --enable format_pcm --enable format_sln \
      --enable func_channel --enable func_callerid --enable func_strings --enable func_logic --enable func_env \
      --enable func_global --enable func_cut --enable func_dialplan --enable func_math --enable func_devstate \
      --enable func_pjsip_endpoint --enable func_pjsip_contact --enable func_pjsip_aor --enable func_uri \
      --enable func_hangupcause --enable func_timeout --enable func_db \
      --enable pbx_config \
      --enable res_pjproject --enable res_pjsip --enable res_pjsip_session --enable res_pjsip_sdp_rtp \
      --enable res_pjsip_authenticator_digest --enable res_pjsip_outbound_authenticator_digest \
      --enable res_pjsip_endpoint_identifier_ip --enable res_pjsip_endpoint_identifier_user \
      --enable res_pjsip_registrar --enable res_pjsip_outbound_registration --enable res_pjsip_transport_websocket \
      --enable res_pjsip_caller_id --enable res_pjsip_dtmf_info --enable res_pjsip_nat --enable res_pjsip_rfc3326 \
      --enable res_pjsip_pubsub --enable res_pjsip_refer --enable res_pjsip_header_funcs --enable res_pjsip_path \
      --enable res_pjsip_diversion --enable res_pjsip_acl --enable res_pjsip_logger --enable res_pjsip_dlg_options \
      --enable res_pjsip_empty_info \
      --enable res_rtp_asterisk --enable res_srtp --enable res_http_websocket --enable res_timing_timerfd \
      --enable res_sorcery_config --enable res_sorcery_memory --enable res_sorcery_astdb \
      --enable res_sorcery_memory_cache \
      --enable res_stasis --enable res_stasis_answer --enable res_stasis_device_state --enable res_stasis_playback \
      --enable res_stasis_recording --enable res_stasis_snoop \
      --enable res_ari --enable res_ari_model --enable res_ari_applications --enable res_ari_asterisk \
      --enable res_ari_bridges --enable res_ari_channels --enable res_ari_device_states --enable res_ari_endpoints \
      --enable res_ari_events --enable res_ari_playbacks --enable res_ari_recordings --enable res_ari_sounds \
      --enable res_musiconhold --enable res_clioriginate --enable res_security_log --enable res_format_attr_opus \
      menuselect.makeopts \
 && make -s third-party \
 && make -j"$(nproc)" -s ASTCFLAGS="-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2" \
 && make -s install DESTDIR=/out \
 && rm -rf /out/usr/include /out/var/lib/asterisk/static-http /out/var/lib/asterisk/documentation \
      /out/var/lib/asterisk/rest-api /out/usr/share/man /out/usr/lib/pkgconfig \
 && find /out -type f \( -name '*.so*' -o -perm -u+x \) -exec sh -c 'file "$1" | grep -q ELF && strip --strip-unneeded "$1"' _ {} \; \
 && LD_LIBRARY_PATH=/out/usr/lib /out/usr/sbin/asterisk -V
# /var/run is a symbolic link to /run in the runtime image; sample configuration is never shipped.
RUN rm -rf /out/var/run /out/etc/asterisk

# Voice prompts generated with text-to-speech (espeak-ng GPL-3.0 and sox GPL-2.0 run only in this build stage; only
# the generated audio is copied, no binary). 8 kHz mono 16-bit WAV, the format Asterisk plays without transcoding.
# - notice-ar.wav / notice-fr.wav: the recorded-call notice every caller hears before recording and queueing (legal
#   point L04). Replace them with professional recordings (same names and format) in production (docs/telephony.md).
# - prompt.wav: ┏━━ SIMULATION ━━ what the simulated caller says (call-sim target only).
#               ┃ PRODUCTION: the runtime image never contains it.
#               ┗━━━━━━━━━━━━━━━━
FROM ubuntu:26.04@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944 AS prompts
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends espeak-ng sox \
 && rm -rf /var/lib/apt/lists/*
RUN mkdir /prompts \
 && espeak-ng -v ar -s 140 -w /tmp/notice-ar.wav \
      "مرحبا بكم في منظومة الحماية. هذه المكالمة مسجلة لأغراض الطوارئ. ابقوا على الخط، سيرد عليكم عون في أقرب وقت." \
 && espeak-ng -v fr -s 150 -w /tmp/notice-fr.wav \
      "Bienvenue sur e-Himaya. Cet appel est enregistré pour le traitement de l'urgence. Restez en ligne, un opérateur va vous répondre." \
 && sox /tmp/notice-ar.wav -r 8000 -c 1 -b 16 /prompts/notice-ar.wav \
 && sox /tmp/notice-fr.wav -r 8000 -c 1 -b 16 /prompts/notice-fr.wav \
 && espeak-ng -v ar -s 130 -w /tmp/ar.wav "هذه مكالمة تجريبية من محاكي منظومة الحماية. يوجد حريق قرب الطريق." \
 && espeak-ng -v fr -s 130 -w /tmp/fr.wav "Ceci est un appel simulé. Un incendie est signalé près de la route." \
 && sox /tmp/ar.wav /tmp/fr.wav -r 8000 -c 1 -b 16 /prompts/prompt.wav

FROM ubuntu:26.04@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944 AS runtime
ENV DEBIAN_FRONTEND=noninteractive
# Shared libraries of the modules built above only (ca-certificates: TLS to a SIP trunk). User ehimaya has the same
# uid as the API image (10001): the API worker reads and deletes the recordings on the shared volume.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates libedit2 libjansson4 libxml2-16 libsqlite3-0 libssl3t64 libsrtp2-1 liburiparser1 libuuid1 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --home /var/lib/asterisk --shell /usr/sbin/nologin ehimaya
COPY --from=build /out/ /
COPY config/ /etc/ehimaya-asterisk/templates/
COPY --from=prompts /prompts/notice-ar.wav /prompts/notice-fr.wav /var/lib/asterisk/sounds/ehimaya/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
 && rm -rf /etc/asterisk \
 && mkdir -p /run/asterisk /var/lib/asterisk/sounds/ehimaya /var/spool/asterisk/ehimaya /var/log/asterisk \
 && chown -R ehimaya:ehimaya /run/asterisk /var/lib/asterisk /var/spool/asterisk /var/log/asterisk \
 && asterisk -V
USER ehimaya
# SIP (trunk, UDP/TCP), SIP over TLS (trunk), HTTP (ARI + WebSocket SIP, internal), RTP (range set in the env).
EXPOSE 5060/udp 5060/tcp 5061/tcp 8088/tcp
HEALTHCHECK --interval=10s --timeout=5s --retries=12 \
  CMD asterisk -C /run/asterisk/etc/asterisk.conf -rx "core show uptime" | grep -q "System uptime"
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["asterisk", "-f", "-C", "/run/asterisk/etc/asterisk.conf"]

# ┏━━ SIMULATION ━━ call-sim: an Asterisk that places scripted calls to 8000 (compose profile "sim") and plays the
# ┃   generated prompt, so the queue, the dashboard softphone, recording and linking run end to end.
# ┃ PRODUCTION: never deployed; real callers arrive through the SIP trunk (docs/telephony.md).
# ┗━━━━━━━━━━━━━━━━
FROM runtime AS call-sim
USER root
RUN rm -rf /etc/ehimaya-asterisk/templates \
 && mkdir -p /var/lib/asterisk/sounds/ehimaya-sim
COPY sim/config/ /etc/ehimaya-asterisk/templates/
COPY sim/call-sim.sh /usr/local/bin/call-sim.sh
COPY --from=prompts /prompts/prompt.wav /var/lib/asterisk/sounds/ehimaya-sim/prompt.wav
RUN chmod 0755 /usr/local/bin/call-sim.sh && chown -R ehimaya:ehimaya /var/lib/asterisk/sounds
USER ehimaya
HEALTHCHECK --interval=10s --timeout=5s --retries=12 \
  CMD asterisk -C /run/asterisk/etc/asterisk.conf -rx "core show uptime" | grep -q "System uptime"
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["/usr/local/bin/call-sim.sh"]
