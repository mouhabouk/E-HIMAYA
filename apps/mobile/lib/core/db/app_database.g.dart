// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_database.dart';

// ignore_for_file: type=lint
class $PendingReportsTable extends PendingReports
    with TableInfo<$PendingReportsTable, PendingReport> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $PendingReportsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _clientUuidMeta = const VerificationMeta(
    'clientUuid',
  );
  @override
  late final GeneratedColumn<String> clientUuid = GeneratedColumn<String>(
    'client_uuid',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _categoryMeta = const VerificationMeta(
    'category',
  );
  @override
  late final GeneratedColumn<String> category = GeneratedColumn<String>(
    'category',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _payloadMeta = const VerificationMeta(
    'payload',
  );
  @override
  late final GeneratedColumn<String> payload = GeneratedColumn<String>(
    'payload',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _tempCodeMeta = const VerificationMeta(
    'tempCode',
  );
  @override
  late final GeneratedColumn<String> tempCode = GeneratedColumn<String>(
    'temp_code',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _serverIdMeta = const VerificationMeta(
    'serverId',
  );
  @override
  late final GeneratedColumn<String> serverId = GeneratedColumn<String>(
    'server_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _serverTrackingCodeMeta =
      const VerificationMeta('serverTrackingCode');
  @override
  late final GeneratedColumn<String> serverTrackingCode =
      GeneratedColumn<String>(
        'server_tracking_code',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _serverStatusMeta = const VerificationMeta(
    'serverStatus',
  );
  @override
  late final GeneratedColumn<String> serverStatus = GeneratedColumn<String>(
    'server_status',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _serverSnapshotMeta = const VerificationMeta(
    'serverSnapshot',
  );
  @override
  late final GeneratedColumn<String> serverSnapshot = GeneratedColumn<String>(
    'server_snapshot',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _stateMeta = const VerificationMeta('state');
  @override
  late final GeneratedColumn<String> state = GeneratedColumn<String>(
    'state',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('queued'),
  );
  static const VerificationMeta _attemptsMeta = const VerificationMeta(
    'attempts',
  );
  @override
  late final GeneratedColumn<int> attempts = GeneratedColumn<int>(
    'attempts',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _lastErrorMeta = const VerificationMeta(
    'lastError',
  );
  @override
  late final GeneratedColumn<String> lastError = GeneratedColumn<String>(
    'last_error',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _nextAttemptAtMeta = const VerificationMeta(
    'nextAttemptAt',
  );
  @override
  late final GeneratedColumn<DateTime> nextAttemptAt =
      GeneratedColumn<DateTime>(
        'next_attempt_at',
        aliasedName,
        true,
        type: DriftSqlType.dateTime,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<DateTime> createdAt = GeneratedColumn<DateTime>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _updatedAtMeta = const VerificationMeta(
    'updatedAt',
  );
  @override
  late final GeneratedColumn<DateTime> updatedAt = GeneratedColumn<DateTime>(
    'updated_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    clientUuid,
    category,
    payload,
    tempCode,
    serverId,
    serverTrackingCode,
    serverStatus,
    serverSnapshot,
    state,
    attempts,
    lastError,
    nextAttemptAt,
    createdAt,
    updatedAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'pending_reports';
  @override
  VerificationContext validateIntegrity(
    Insertable<PendingReport> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('client_uuid')) {
      context.handle(
        _clientUuidMeta,
        clientUuid.isAcceptableOrUnknown(data['client_uuid']!, _clientUuidMeta),
      );
    } else if (isInserting) {
      context.missing(_clientUuidMeta);
    }
    if (data.containsKey('category')) {
      context.handle(
        _categoryMeta,
        category.isAcceptableOrUnknown(data['category']!, _categoryMeta),
      );
    } else if (isInserting) {
      context.missing(_categoryMeta);
    }
    if (data.containsKey('payload')) {
      context.handle(
        _payloadMeta,
        payload.isAcceptableOrUnknown(data['payload']!, _payloadMeta),
      );
    } else if (isInserting) {
      context.missing(_payloadMeta);
    }
    if (data.containsKey('temp_code')) {
      context.handle(
        _tempCodeMeta,
        tempCode.isAcceptableOrUnknown(data['temp_code']!, _tempCodeMeta),
      );
    } else if (isInserting) {
      context.missing(_tempCodeMeta);
    }
    if (data.containsKey('server_id')) {
      context.handle(
        _serverIdMeta,
        serverId.isAcceptableOrUnknown(data['server_id']!, _serverIdMeta),
      );
    }
    if (data.containsKey('server_tracking_code')) {
      context.handle(
        _serverTrackingCodeMeta,
        serverTrackingCode.isAcceptableOrUnknown(
          data['server_tracking_code']!,
          _serverTrackingCodeMeta,
        ),
      );
    }
    if (data.containsKey('server_status')) {
      context.handle(
        _serverStatusMeta,
        serverStatus.isAcceptableOrUnknown(
          data['server_status']!,
          _serverStatusMeta,
        ),
      );
    }
    if (data.containsKey('server_snapshot')) {
      context.handle(
        _serverSnapshotMeta,
        serverSnapshot.isAcceptableOrUnknown(
          data['server_snapshot']!,
          _serverSnapshotMeta,
        ),
      );
    }
    if (data.containsKey('state')) {
      context.handle(
        _stateMeta,
        state.isAcceptableOrUnknown(data['state']!, _stateMeta),
      );
    }
    if (data.containsKey('attempts')) {
      context.handle(
        _attemptsMeta,
        attempts.isAcceptableOrUnknown(data['attempts']!, _attemptsMeta),
      );
    }
    if (data.containsKey('last_error')) {
      context.handle(
        _lastErrorMeta,
        lastError.isAcceptableOrUnknown(data['last_error']!, _lastErrorMeta),
      );
    }
    if (data.containsKey('next_attempt_at')) {
      context.handle(
        _nextAttemptAtMeta,
        nextAttemptAt.isAcceptableOrUnknown(
          data['next_attempt_at']!,
          _nextAttemptAtMeta,
        ),
      );
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    if (data.containsKey('updated_at')) {
      context.handle(
        _updatedAtMeta,
        updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta),
      );
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {clientUuid};
  @override
  PendingReport map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return PendingReport(
      clientUuid: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}client_uuid'],
      )!,
      category: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}category'],
      )!,
      payload: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}payload'],
      )!,
      tempCode: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}temp_code'],
      )!,
      serverId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}server_id'],
      ),
      serverTrackingCode: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}server_tracking_code'],
      ),
      serverStatus: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}server_status'],
      ),
      serverSnapshot: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}server_snapshot'],
      ),
      state: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}state'],
      )!,
      attempts: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}attempts'],
      )!,
      lastError: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}last_error'],
      ),
      nextAttemptAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}next_attempt_at'],
      ),
      createdAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}created_at'],
      )!,
      updatedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}updated_at'],
      )!,
    );
  }

  @override
  $PendingReportsTable createAlias(String alias) {
    return $PendingReportsTable(attachedDatabase, alias);
  }
}

class PendingReport extends DataClass implements Insertable<PendingReport> {
  final String clientUuid;
  final String category;

  /// JSON body of `POST /api/v1/reports`, frozen at submit time.
  final String payload;
  final String tempCode;
  final String? serverId;
  final String? serverTrackingCode;
  final String? serverStatus;

  /// Server JSON of the report when it differs from the local copy (conflict, server wins).
  final String? serverSnapshot;
  final String state;
  final int attempts;
  final String? lastError;
  final DateTime? nextAttemptAt;
  final DateTime createdAt;
  final DateTime updatedAt;
  const PendingReport({
    required this.clientUuid,
    required this.category,
    required this.payload,
    required this.tempCode,
    this.serverId,
    this.serverTrackingCode,
    this.serverStatus,
    this.serverSnapshot,
    required this.state,
    required this.attempts,
    this.lastError,
    this.nextAttemptAt,
    required this.createdAt,
    required this.updatedAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['client_uuid'] = Variable<String>(clientUuid);
    map['category'] = Variable<String>(category);
    map['payload'] = Variable<String>(payload);
    map['temp_code'] = Variable<String>(tempCode);
    if (!nullToAbsent || serverId != null) {
      map['server_id'] = Variable<String>(serverId);
    }
    if (!nullToAbsent || serverTrackingCode != null) {
      map['server_tracking_code'] = Variable<String>(serverTrackingCode);
    }
    if (!nullToAbsent || serverStatus != null) {
      map['server_status'] = Variable<String>(serverStatus);
    }
    if (!nullToAbsent || serverSnapshot != null) {
      map['server_snapshot'] = Variable<String>(serverSnapshot);
    }
    map['state'] = Variable<String>(state);
    map['attempts'] = Variable<int>(attempts);
    if (!nullToAbsent || lastError != null) {
      map['last_error'] = Variable<String>(lastError);
    }
    if (!nullToAbsent || nextAttemptAt != null) {
      map['next_attempt_at'] = Variable<DateTime>(nextAttemptAt);
    }
    map['created_at'] = Variable<DateTime>(createdAt);
    map['updated_at'] = Variable<DateTime>(updatedAt);
    return map;
  }

  PendingReportsCompanion toCompanion(bool nullToAbsent) {
    return PendingReportsCompanion(
      clientUuid: Value(clientUuid),
      category: Value(category),
      payload: Value(payload),
      tempCode: Value(tempCode),
      serverId: serverId == null && nullToAbsent
          ? const Value.absent()
          : Value(serverId),
      serverTrackingCode: serverTrackingCode == null && nullToAbsent
          ? const Value.absent()
          : Value(serverTrackingCode),
      serverStatus: serverStatus == null && nullToAbsent
          ? const Value.absent()
          : Value(serverStatus),
      serverSnapshot: serverSnapshot == null && nullToAbsent
          ? const Value.absent()
          : Value(serverSnapshot),
      state: Value(state),
      attempts: Value(attempts),
      lastError: lastError == null && nullToAbsent
          ? const Value.absent()
          : Value(lastError),
      nextAttemptAt: nextAttemptAt == null && nullToAbsent
          ? const Value.absent()
          : Value(nextAttemptAt),
      createdAt: Value(createdAt),
      updatedAt: Value(updatedAt),
    );
  }

  factory PendingReport.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return PendingReport(
      clientUuid: serializer.fromJson<String>(json['clientUuid']),
      category: serializer.fromJson<String>(json['category']),
      payload: serializer.fromJson<String>(json['payload']),
      tempCode: serializer.fromJson<String>(json['tempCode']),
      serverId: serializer.fromJson<String?>(json['serverId']),
      serverTrackingCode: serializer.fromJson<String?>(
        json['serverTrackingCode'],
      ),
      serverStatus: serializer.fromJson<String?>(json['serverStatus']),
      serverSnapshot: serializer.fromJson<String?>(json['serverSnapshot']),
      state: serializer.fromJson<String>(json['state']),
      attempts: serializer.fromJson<int>(json['attempts']),
      lastError: serializer.fromJson<String?>(json['lastError']),
      nextAttemptAt: serializer.fromJson<DateTime?>(json['nextAttemptAt']),
      createdAt: serializer.fromJson<DateTime>(json['createdAt']),
      updatedAt: serializer.fromJson<DateTime>(json['updatedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'clientUuid': serializer.toJson<String>(clientUuid),
      'category': serializer.toJson<String>(category),
      'payload': serializer.toJson<String>(payload),
      'tempCode': serializer.toJson<String>(tempCode),
      'serverId': serializer.toJson<String?>(serverId),
      'serverTrackingCode': serializer.toJson<String?>(serverTrackingCode),
      'serverStatus': serializer.toJson<String?>(serverStatus),
      'serverSnapshot': serializer.toJson<String?>(serverSnapshot),
      'state': serializer.toJson<String>(state),
      'attempts': serializer.toJson<int>(attempts),
      'lastError': serializer.toJson<String?>(lastError),
      'nextAttemptAt': serializer.toJson<DateTime?>(nextAttemptAt),
      'createdAt': serializer.toJson<DateTime>(createdAt),
      'updatedAt': serializer.toJson<DateTime>(updatedAt),
    };
  }

  PendingReport copyWith({
    String? clientUuid,
    String? category,
    String? payload,
    String? tempCode,
    Value<String?> serverId = const Value.absent(),
    Value<String?> serverTrackingCode = const Value.absent(),
    Value<String?> serverStatus = const Value.absent(),
    Value<String?> serverSnapshot = const Value.absent(),
    String? state,
    int? attempts,
    Value<String?> lastError = const Value.absent(),
    Value<DateTime?> nextAttemptAt = const Value.absent(),
    DateTime? createdAt,
    DateTime? updatedAt,
  }) => PendingReport(
    clientUuid: clientUuid ?? this.clientUuid,
    category: category ?? this.category,
    payload: payload ?? this.payload,
    tempCode: tempCode ?? this.tempCode,
    serverId: serverId.present ? serverId.value : this.serverId,
    serverTrackingCode: serverTrackingCode.present
        ? serverTrackingCode.value
        : this.serverTrackingCode,
    serverStatus: serverStatus.present ? serverStatus.value : this.serverStatus,
    serverSnapshot: serverSnapshot.present
        ? serverSnapshot.value
        : this.serverSnapshot,
    state: state ?? this.state,
    attempts: attempts ?? this.attempts,
    lastError: lastError.present ? lastError.value : this.lastError,
    nextAttemptAt: nextAttemptAt.present
        ? nextAttemptAt.value
        : this.nextAttemptAt,
    createdAt: createdAt ?? this.createdAt,
    updatedAt: updatedAt ?? this.updatedAt,
  );
  PendingReport copyWithCompanion(PendingReportsCompanion data) {
    return PendingReport(
      clientUuid: data.clientUuid.present
          ? data.clientUuid.value
          : this.clientUuid,
      category: data.category.present ? data.category.value : this.category,
      payload: data.payload.present ? data.payload.value : this.payload,
      tempCode: data.tempCode.present ? data.tempCode.value : this.tempCode,
      serverId: data.serverId.present ? data.serverId.value : this.serverId,
      serverTrackingCode: data.serverTrackingCode.present
          ? data.serverTrackingCode.value
          : this.serverTrackingCode,
      serverStatus: data.serverStatus.present
          ? data.serverStatus.value
          : this.serverStatus,
      serverSnapshot: data.serverSnapshot.present
          ? data.serverSnapshot.value
          : this.serverSnapshot,
      state: data.state.present ? data.state.value : this.state,
      attempts: data.attempts.present ? data.attempts.value : this.attempts,
      lastError: data.lastError.present ? data.lastError.value : this.lastError,
      nextAttemptAt: data.nextAttemptAt.present
          ? data.nextAttemptAt.value
          : this.nextAttemptAt,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('PendingReport(')
          ..write('clientUuid: $clientUuid, ')
          ..write('category: $category, ')
          ..write('payload: $payload, ')
          ..write('tempCode: $tempCode, ')
          ..write('serverId: $serverId, ')
          ..write('serverTrackingCode: $serverTrackingCode, ')
          ..write('serverStatus: $serverStatus, ')
          ..write('serverSnapshot: $serverSnapshot, ')
          ..write('state: $state, ')
          ..write('attempts: $attempts, ')
          ..write('lastError: $lastError, ')
          ..write('nextAttemptAt: $nextAttemptAt, ')
          ..write('createdAt: $createdAt, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    clientUuid,
    category,
    payload,
    tempCode,
    serverId,
    serverTrackingCode,
    serverStatus,
    serverSnapshot,
    state,
    attempts,
    lastError,
    nextAttemptAt,
    createdAt,
    updatedAt,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is PendingReport &&
          other.clientUuid == this.clientUuid &&
          other.category == this.category &&
          other.payload == this.payload &&
          other.tempCode == this.tempCode &&
          other.serverId == this.serverId &&
          other.serverTrackingCode == this.serverTrackingCode &&
          other.serverStatus == this.serverStatus &&
          other.serverSnapshot == this.serverSnapshot &&
          other.state == this.state &&
          other.attempts == this.attempts &&
          other.lastError == this.lastError &&
          other.nextAttemptAt == this.nextAttemptAt &&
          other.createdAt == this.createdAt &&
          other.updatedAt == this.updatedAt);
}

class PendingReportsCompanion extends UpdateCompanion<PendingReport> {
  final Value<String> clientUuid;
  final Value<String> category;
  final Value<String> payload;
  final Value<String> tempCode;
  final Value<String?> serverId;
  final Value<String?> serverTrackingCode;
  final Value<String?> serverStatus;
  final Value<String?> serverSnapshot;
  final Value<String> state;
  final Value<int> attempts;
  final Value<String?> lastError;
  final Value<DateTime?> nextAttemptAt;
  final Value<DateTime> createdAt;
  final Value<DateTime> updatedAt;
  final Value<int> rowid;
  const PendingReportsCompanion({
    this.clientUuid = const Value.absent(),
    this.category = const Value.absent(),
    this.payload = const Value.absent(),
    this.tempCode = const Value.absent(),
    this.serverId = const Value.absent(),
    this.serverTrackingCode = const Value.absent(),
    this.serverStatus = const Value.absent(),
    this.serverSnapshot = const Value.absent(),
    this.state = const Value.absent(),
    this.attempts = const Value.absent(),
    this.lastError = const Value.absent(),
    this.nextAttemptAt = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  PendingReportsCompanion.insert({
    required String clientUuid,
    required String category,
    required String payload,
    required String tempCode,
    this.serverId = const Value.absent(),
    this.serverTrackingCode = const Value.absent(),
    this.serverStatus = const Value.absent(),
    this.serverSnapshot = const Value.absent(),
    this.state = const Value.absent(),
    this.attempts = const Value.absent(),
    this.lastError = const Value.absent(),
    this.nextAttemptAt = const Value.absent(),
    required DateTime createdAt,
    required DateTime updatedAt,
    this.rowid = const Value.absent(),
  }) : clientUuid = Value(clientUuid),
       category = Value(category),
       payload = Value(payload),
       tempCode = Value(tempCode),
       createdAt = Value(createdAt),
       updatedAt = Value(updatedAt);
  static Insertable<PendingReport> custom({
    Expression<String>? clientUuid,
    Expression<String>? category,
    Expression<String>? payload,
    Expression<String>? tempCode,
    Expression<String>? serverId,
    Expression<String>? serverTrackingCode,
    Expression<String>? serverStatus,
    Expression<String>? serverSnapshot,
    Expression<String>? state,
    Expression<int>? attempts,
    Expression<String>? lastError,
    Expression<DateTime>? nextAttemptAt,
    Expression<DateTime>? createdAt,
    Expression<DateTime>? updatedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (clientUuid != null) 'client_uuid': clientUuid,
      if (category != null) 'category': category,
      if (payload != null) 'payload': payload,
      if (tempCode != null) 'temp_code': tempCode,
      if (serverId != null) 'server_id': serverId,
      if (serverTrackingCode != null)
        'server_tracking_code': serverTrackingCode,
      if (serverStatus != null) 'server_status': serverStatus,
      if (serverSnapshot != null) 'server_snapshot': serverSnapshot,
      if (state != null) 'state': state,
      if (attempts != null) 'attempts': attempts,
      if (lastError != null) 'last_error': lastError,
      if (nextAttemptAt != null) 'next_attempt_at': nextAttemptAt,
      if (createdAt != null) 'created_at': createdAt,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  PendingReportsCompanion copyWith({
    Value<String>? clientUuid,
    Value<String>? category,
    Value<String>? payload,
    Value<String>? tempCode,
    Value<String?>? serverId,
    Value<String?>? serverTrackingCode,
    Value<String?>? serverStatus,
    Value<String?>? serverSnapshot,
    Value<String>? state,
    Value<int>? attempts,
    Value<String?>? lastError,
    Value<DateTime?>? nextAttemptAt,
    Value<DateTime>? createdAt,
    Value<DateTime>? updatedAt,
    Value<int>? rowid,
  }) {
    return PendingReportsCompanion(
      clientUuid: clientUuid ?? this.clientUuid,
      category: category ?? this.category,
      payload: payload ?? this.payload,
      tempCode: tempCode ?? this.tempCode,
      serverId: serverId ?? this.serverId,
      serverTrackingCode: serverTrackingCode ?? this.serverTrackingCode,
      serverStatus: serverStatus ?? this.serverStatus,
      serverSnapshot: serverSnapshot ?? this.serverSnapshot,
      state: state ?? this.state,
      attempts: attempts ?? this.attempts,
      lastError: lastError ?? this.lastError,
      nextAttemptAt: nextAttemptAt ?? this.nextAttemptAt,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (clientUuid.present) {
      map['client_uuid'] = Variable<String>(clientUuid.value);
    }
    if (category.present) {
      map['category'] = Variable<String>(category.value);
    }
    if (payload.present) {
      map['payload'] = Variable<String>(payload.value);
    }
    if (tempCode.present) {
      map['temp_code'] = Variable<String>(tempCode.value);
    }
    if (serverId.present) {
      map['server_id'] = Variable<String>(serverId.value);
    }
    if (serverTrackingCode.present) {
      map['server_tracking_code'] = Variable<String>(serverTrackingCode.value);
    }
    if (serverStatus.present) {
      map['server_status'] = Variable<String>(serverStatus.value);
    }
    if (serverSnapshot.present) {
      map['server_snapshot'] = Variable<String>(serverSnapshot.value);
    }
    if (state.present) {
      map['state'] = Variable<String>(state.value);
    }
    if (attempts.present) {
      map['attempts'] = Variable<int>(attempts.value);
    }
    if (lastError.present) {
      map['last_error'] = Variable<String>(lastError.value);
    }
    if (nextAttemptAt.present) {
      map['next_attempt_at'] = Variable<DateTime>(nextAttemptAt.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<DateTime>(createdAt.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<DateTime>(updatedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('PendingReportsCompanion(')
          ..write('clientUuid: $clientUuid, ')
          ..write('category: $category, ')
          ..write('payload: $payload, ')
          ..write('tempCode: $tempCode, ')
          ..write('serverId: $serverId, ')
          ..write('serverTrackingCode: $serverTrackingCode, ')
          ..write('serverStatus: $serverStatus, ')
          ..write('serverSnapshot: $serverSnapshot, ')
          ..write('state: $state, ')
          ..write('attempts: $attempts, ')
          ..write('lastError: $lastError, ')
          ..write('nextAttemptAt: $nextAttemptAt, ')
          ..write('createdAt: $createdAt, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $MediaItemsTable extends MediaItems
    with TableInfo<$MediaItemsTable, MediaItem> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $MediaItemsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _reportUuidMeta = const VerificationMeta(
    'reportUuid',
  );
  @override
  late final GeneratedColumn<String> reportUuid = GeneratedColumn<String>(
    'report_uuid',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES pending_reports (client_uuid)',
    ),
  );
  static const VerificationMeta _pathMeta = const VerificationMeta('path');
  @override
  late final GeneratedColumn<String> path = GeneratedColumn<String>(
    'path',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _kindMeta = const VerificationMeta('kind');
  @override
  late final GeneratedColumn<String> kind = GeneratedColumn<String>(
    'kind',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _mimeMeta = const VerificationMeta('mime');
  @override
  late final GeneratedColumn<String> mime = GeneratedColumn<String>(
    'mime',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sizeMeta = const VerificationMeta('size');
  @override
  late final GeneratedColumn<int> size = GeneratedColumn<int>(
    'size',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sha256Meta = const VerificationMeta('sha256');
  @override
  late final GeneratedColumn<String> sha256 = GeneratedColumn<String>(
    'sha256',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _uploadUrlMeta = const VerificationMeta(
    'uploadUrl',
  );
  @override
  late final GeneratedColumn<String> uploadUrl = GeneratedColumn<String>(
    'upload_url',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _uploadOffsetMeta = const VerificationMeta(
    'uploadOffset',
  );
  @override
  late final GeneratedColumn<int> uploadOffset = GeneratedColumn<int>(
    'upload_offset',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _stateMeta = const VerificationMeta('state');
  @override
  late final GeneratedColumn<String> state = GeneratedColumn<String>(
    'state',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('pending'),
  );
  static const VerificationMeta _attemptsMeta = const VerificationMeta(
    'attempts',
  );
  @override
  late final GeneratedColumn<int> attempts = GeneratedColumn<int>(
    'attempts',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _lastErrorMeta = const VerificationMeta(
    'lastError',
  );
  @override
  late final GeneratedColumn<String> lastError = GeneratedColumn<String>(
    'last_error',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _nextAttemptAtMeta = const VerificationMeta(
    'nextAttemptAt',
  );
  @override
  late final GeneratedColumn<DateTime> nextAttemptAt =
      GeneratedColumn<DateTime>(
        'next_attempt_at',
        aliasedName,
        true,
        type: DriftSqlType.dateTime,
        requiredDuringInsert: false,
      );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    reportUuid,
    path,
    kind,
    mime,
    size,
    sha256,
    uploadUrl,
    uploadOffset,
    state,
    attempts,
    lastError,
    nextAttemptAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'media_items';
  @override
  VerificationContext validateIntegrity(
    Insertable<MediaItem> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('report_uuid')) {
      context.handle(
        _reportUuidMeta,
        reportUuid.isAcceptableOrUnknown(data['report_uuid']!, _reportUuidMeta),
      );
    } else if (isInserting) {
      context.missing(_reportUuidMeta);
    }
    if (data.containsKey('path')) {
      context.handle(
        _pathMeta,
        path.isAcceptableOrUnknown(data['path']!, _pathMeta),
      );
    } else if (isInserting) {
      context.missing(_pathMeta);
    }
    if (data.containsKey('kind')) {
      context.handle(
        _kindMeta,
        kind.isAcceptableOrUnknown(data['kind']!, _kindMeta),
      );
    } else if (isInserting) {
      context.missing(_kindMeta);
    }
    if (data.containsKey('mime')) {
      context.handle(
        _mimeMeta,
        mime.isAcceptableOrUnknown(data['mime']!, _mimeMeta),
      );
    } else if (isInserting) {
      context.missing(_mimeMeta);
    }
    if (data.containsKey('size')) {
      context.handle(
        _sizeMeta,
        size.isAcceptableOrUnknown(data['size']!, _sizeMeta),
      );
    } else if (isInserting) {
      context.missing(_sizeMeta);
    }
    if (data.containsKey('sha256')) {
      context.handle(
        _sha256Meta,
        sha256.isAcceptableOrUnknown(data['sha256']!, _sha256Meta),
      );
    } else if (isInserting) {
      context.missing(_sha256Meta);
    }
    if (data.containsKey('upload_url')) {
      context.handle(
        _uploadUrlMeta,
        uploadUrl.isAcceptableOrUnknown(data['upload_url']!, _uploadUrlMeta),
      );
    }
    if (data.containsKey('upload_offset')) {
      context.handle(
        _uploadOffsetMeta,
        uploadOffset.isAcceptableOrUnknown(
          data['upload_offset']!,
          _uploadOffsetMeta,
        ),
      );
    }
    if (data.containsKey('state')) {
      context.handle(
        _stateMeta,
        state.isAcceptableOrUnknown(data['state']!, _stateMeta),
      );
    }
    if (data.containsKey('attempts')) {
      context.handle(
        _attemptsMeta,
        attempts.isAcceptableOrUnknown(data['attempts']!, _attemptsMeta),
      );
    }
    if (data.containsKey('last_error')) {
      context.handle(
        _lastErrorMeta,
        lastError.isAcceptableOrUnknown(data['last_error']!, _lastErrorMeta),
      );
    }
    if (data.containsKey('next_attempt_at')) {
      context.handle(
        _nextAttemptAtMeta,
        nextAttemptAt.isAcceptableOrUnknown(
          data['next_attempt_at']!,
          _nextAttemptAtMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  MediaItem map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return MediaItem(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      reportUuid: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}report_uuid'],
      )!,
      path: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}path'],
      )!,
      kind: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}kind'],
      )!,
      mime: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}mime'],
      )!,
      size: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}size'],
      )!,
      sha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}sha256'],
      )!,
      uploadUrl: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}upload_url'],
      ),
      uploadOffset: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}upload_offset'],
      )!,
      state: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}state'],
      )!,
      attempts: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}attempts'],
      )!,
      lastError: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}last_error'],
      ),
      nextAttemptAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}next_attempt_at'],
      ),
    );
  }

  @override
  $MediaItemsTable createAlias(String alias) {
    return $MediaItemsTable(attachedDatabase, alias);
  }
}

class MediaItem extends DataClass implements Insertable<MediaItem> {
  final int id;
  final String reportUuid;
  final String path;

  /// `image` | `video` | `audio`.
  final String kind;
  final String mime;
  final int size;

  /// Lowercase hex SHA-256 of the whole file, computed by streaming.
  final String sha256;
  final String? uploadUrl;
  final int uploadOffset;
  final String state;
  final int attempts;
  final String? lastError;
  final DateTime? nextAttemptAt;
  const MediaItem({
    required this.id,
    required this.reportUuid,
    required this.path,
    required this.kind,
    required this.mime,
    required this.size,
    required this.sha256,
    this.uploadUrl,
    required this.uploadOffset,
    required this.state,
    required this.attempts,
    this.lastError,
    this.nextAttemptAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['report_uuid'] = Variable<String>(reportUuid);
    map['path'] = Variable<String>(path);
    map['kind'] = Variable<String>(kind);
    map['mime'] = Variable<String>(mime);
    map['size'] = Variable<int>(size);
    map['sha256'] = Variable<String>(sha256);
    if (!nullToAbsent || uploadUrl != null) {
      map['upload_url'] = Variable<String>(uploadUrl);
    }
    map['upload_offset'] = Variable<int>(uploadOffset);
    map['state'] = Variable<String>(state);
    map['attempts'] = Variable<int>(attempts);
    if (!nullToAbsent || lastError != null) {
      map['last_error'] = Variable<String>(lastError);
    }
    if (!nullToAbsent || nextAttemptAt != null) {
      map['next_attempt_at'] = Variable<DateTime>(nextAttemptAt);
    }
    return map;
  }

  MediaItemsCompanion toCompanion(bool nullToAbsent) {
    return MediaItemsCompanion(
      id: Value(id),
      reportUuid: Value(reportUuid),
      path: Value(path),
      kind: Value(kind),
      mime: Value(mime),
      size: Value(size),
      sha256: Value(sha256),
      uploadUrl: uploadUrl == null && nullToAbsent
          ? const Value.absent()
          : Value(uploadUrl),
      uploadOffset: Value(uploadOffset),
      state: Value(state),
      attempts: Value(attempts),
      lastError: lastError == null && nullToAbsent
          ? const Value.absent()
          : Value(lastError),
      nextAttemptAt: nextAttemptAt == null && nullToAbsent
          ? const Value.absent()
          : Value(nextAttemptAt),
    );
  }

  factory MediaItem.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return MediaItem(
      id: serializer.fromJson<int>(json['id']),
      reportUuid: serializer.fromJson<String>(json['reportUuid']),
      path: serializer.fromJson<String>(json['path']),
      kind: serializer.fromJson<String>(json['kind']),
      mime: serializer.fromJson<String>(json['mime']),
      size: serializer.fromJson<int>(json['size']),
      sha256: serializer.fromJson<String>(json['sha256']),
      uploadUrl: serializer.fromJson<String?>(json['uploadUrl']),
      uploadOffset: serializer.fromJson<int>(json['uploadOffset']),
      state: serializer.fromJson<String>(json['state']),
      attempts: serializer.fromJson<int>(json['attempts']),
      lastError: serializer.fromJson<String?>(json['lastError']),
      nextAttemptAt: serializer.fromJson<DateTime?>(json['nextAttemptAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'reportUuid': serializer.toJson<String>(reportUuid),
      'path': serializer.toJson<String>(path),
      'kind': serializer.toJson<String>(kind),
      'mime': serializer.toJson<String>(mime),
      'size': serializer.toJson<int>(size),
      'sha256': serializer.toJson<String>(sha256),
      'uploadUrl': serializer.toJson<String?>(uploadUrl),
      'uploadOffset': serializer.toJson<int>(uploadOffset),
      'state': serializer.toJson<String>(state),
      'attempts': serializer.toJson<int>(attempts),
      'lastError': serializer.toJson<String?>(lastError),
      'nextAttemptAt': serializer.toJson<DateTime?>(nextAttemptAt),
    };
  }

  MediaItem copyWith({
    int? id,
    String? reportUuid,
    String? path,
    String? kind,
    String? mime,
    int? size,
    String? sha256,
    Value<String?> uploadUrl = const Value.absent(),
    int? uploadOffset,
    String? state,
    int? attempts,
    Value<String?> lastError = const Value.absent(),
    Value<DateTime?> nextAttemptAt = const Value.absent(),
  }) => MediaItem(
    id: id ?? this.id,
    reportUuid: reportUuid ?? this.reportUuid,
    path: path ?? this.path,
    kind: kind ?? this.kind,
    mime: mime ?? this.mime,
    size: size ?? this.size,
    sha256: sha256 ?? this.sha256,
    uploadUrl: uploadUrl.present ? uploadUrl.value : this.uploadUrl,
    uploadOffset: uploadOffset ?? this.uploadOffset,
    state: state ?? this.state,
    attempts: attempts ?? this.attempts,
    lastError: lastError.present ? lastError.value : this.lastError,
    nextAttemptAt: nextAttemptAt.present
        ? nextAttemptAt.value
        : this.nextAttemptAt,
  );
  MediaItem copyWithCompanion(MediaItemsCompanion data) {
    return MediaItem(
      id: data.id.present ? data.id.value : this.id,
      reportUuid: data.reportUuid.present
          ? data.reportUuid.value
          : this.reportUuid,
      path: data.path.present ? data.path.value : this.path,
      kind: data.kind.present ? data.kind.value : this.kind,
      mime: data.mime.present ? data.mime.value : this.mime,
      size: data.size.present ? data.size.value : this.size,
      sha256: data.sha256.present ? data.sha256.value : this.sha256,
      uploadUrl: data.uploadUrl.present ? data.uploadUrl.value : this.uploadUrl,
      uploadOffset: data.uploadOffset.present
          ? data.uploadOffset.value
          : this.uploadOffset,
      state: data.state.present ? data.state.value : this.state,
      attempts: data.attempts.present ? data.attempts.value : this.attempts,
      lastError: data.lastError.present ? data.lastError.value : this.lastError,
      nextAttemptAt: data.nextAttemptAt.present
          ? data.nextAttemptAt.value
          : this.nextAttemptAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('MediaItem(')
          ..write('id: $id, ')
          ..write('reportUuid: $reportUuid, ')
          ..write('path: $path, ')
          ..write('kind: $kind, ')
          ..write('mime: $mime, ')
          ..write('size: $size, ')
          ..write('sha256: $sha256, ')
          ..write('uploadUrl: $uploadUrl, ')
          ..write('uploadOffset: $uploadOffset, ')
          ..write('state: $state, ')
          ..write('attempts: $attempts, ')
          ..write('lastError: $lastError, ')
          ..write('nextAttemptAt: $nextAttemptAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    reportUuid,
    path,
    kind,
    mime,
    size,
    sha256,
    uploadUrl,
    uploadOffset,
    state,
    attempts,
    lastError,
    nextAttemptAt,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is MediaItem &&
          other.id == this.id &&
          other.reportUuid == this.reportUuid &&
          other.path == this.path &&
          other.kind == this.kind &&
          other.mime == this.mime &&
          other.size == this.size &&
          other.sha256 == this.sha256 &&
          other.uploadUrl == this.uploadUrl &&
          other.uploadOffset == this.uploadOffset &&
          other.state == this.state &&
          other.attempts == this.attempts &&
          other.lastError == this.lastError &&
          other.nextAttemptAt == this.nextAttemptAt);
}

class MediaItemsCompanion extends UpdateCompanion<MediaItem> {
  final Value<int> id;
  final Value<String> reportUuid;
  final Value<String> path;
  final Value<String> kind;
  final Value<String> mime;
  final Value<int> size;
  final Value<String> sha256;
  final Value<String?> uploadUrl;
  final Value<int> uploadOffset;
  final Value<String> state;
  final Value<int> attempts;
  final Value<String?> lastError;
  final Value<DateTime?> nextAttemptAt;
  const MediaItemsCompanion({
    this.id = const Value.absent(),
    this.reportUuid = const Value.absent(),
    this.path = const Value.absent(),
    this.kind = const Value.absent(),
    this.mime = const Value.absent(),
    this.size = const Value.absent(),
    this.sha256 = const Value.absent(),
    this.uploadUrl = const Value.absent(),
    this.uploadOffset = const Value.absent(),
    this.state = const Value.absent(),
    this.attempts = const Value.absent(),
    this.lastError = const Value.absent(),
    this.nextAttemptAt = const Value.absent(),
  });
  MediaItemsCompanion.insert({
    this.id = const Value.absent(),
    required String reportUuid,
    required String path,
    required String kind,
    required String mime,
    required int size,
    required String sha256,
    this.uploadUrl = const Value.absent(),
    this.uploadOffset = const Value.absent(),
    this.state = const Value.absent(),
    this.attempts = const Value.absent(),
    this.lastError = const Value.absent(),
    this.nextAttemptAt = const Value.absent(),
  }) : reportUuid = Value(reportUuid),
       path = Value(path),
       kind = Value(kind),
       mime = Value(mime),
       size = Value(size),
       sha256 = Value(sha256);
  static Insertable<MediaItem> custom({
    Expression<int>? id,
    Expression<String>? reportUuid,
    Expression<String>? path,
    Expression<String>? kind,
    Expression<String>? mime,
    Expression<int>? size,
    Expression<String>? sha256,
    Expression<String>? uploadUrl,
    Expression<int>? uploadOffset,
    Expression<String>? state,
    Expression<int>? attempts,
    Expression<String>? lastError,
    Expression<DateTime>? nextAttemptAt,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (reportUuid != null) 'report_uuid': reportUuid,
      if (path != null) 'path': path,
      if (kind != null) 'kind': kind,
      if (mime != null) 'mime': mime,
      if (size != null) 'size': size,
      if (sha256 != null) 'sha256': sha256,
      if (uploadUrl != null) 'upload_url': uploadUrl,
      if (uploadOffset != null) 'upload_offset': uploadOffset,
      if (state != null) 'state': state,
      if (attempts != null) 'attempts': attempts,
      if (lastError != null) 'last_error': lastError,
      if (nextAttemptAt != null) 'next_attempt_at': nextAttemptAt,
    });
  }

  MediaItemsCompanion copyWith({
    Value<int>? id,
    Value<String>? reportUuid,
    Value<String>? path,
    Value<String>? kind,
    Value<String>? mime,
    Value<int>? size,
    Value<String>? sha256,
    Value<String?>? uploadUrl,
    Value<int>? uploadOffset,
    Value<String>? state,
    Value<int>? attempts,
    Value<String?>? lastError,
    Value<DateTime?>? nextAttemptAt,
  }) {
    return MediaItemsCompanion(
      id: id ?? this.id,
      reportUuid: reportUuid ?? this.reportUuid,
      path: path ?? this.path,
      kind: kind ?? this.kind,
      mime: mime ?? this.mime,
      size: size ?? this.size,
      sha256: sha256 ?? this.sha256,
      uploadUrl: uploadUrl ?? this.uploadUrl,
      uploadOffset: uploadOffset ?? this.uploadOffset,
      state: state ?? this.state,
      attempts: attempts ?? this.attempts,
      lastError: lastError ?? this.lastError,
      nextAttemptAt: nextAttemptAt ?? this.nextAttemptAt,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (reportUuid.present) {
      map['report_uuid'] = Variable<String>(reportUuid.value);
    }
    if (path.present) {
      map['path'] = Variable<String>(path.value);
    }
    if (kind.present) {
      map['kind'] = Variable<String>(kind.value);
    }
    if (mime.present) {
      map['mime'] = Variable<String>(mime.value);
    }
    if (size.present) {
      map['size'] = Variable<int>(size.value);
    }
    if (sha256.present) {
      map['sha256'] = Variable<String>(sha256.value);
    }
    if (uploadUrl.present) {
      map['upload_url'] = Variable<String>(uploadUrl.value);
    }
    if (uploadOffset.present) {
      map['upload_offset'] = Variable<int>(uploadOffset.value);
    }
    if (state.present) {
      map['state'] = Variable<String>(state.value);
    }
    if (attempts.present) {
      map['attempts'] = Variable<int>(attempts.value);
    }
    if (lastError.present) {
      map['last_error'] = Variable<String>(lastError.value);
    }
    if (nextAttemptAt.present) {
      map['next_attempt_at'] = Variable<DateTime>(nextAttemptAt.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('MediaItemsCompanion(')
          ..write('id: $id, ')
          ..write('reportUuid: $reportUuid, ')
          ..write('path: $path, ')
          ..write('kind: $kind, ')
          ..write('mime: $mime, ')
          ..write('size: $size, ')
          ..write('sha256: $sha256, ')
          ..write('uploadUrl: $uploadUrl, ')
          ..write('uploadOffset: $uploadOffset, ')
          ..write('state: $state, ')
          ..write('attempts: $attempts, ')
          ..write('lastError: $lastError, ')
          ..write('nextAttemptAt: $nextAttemptAt')
          ..write(')'))
        .toString();
  }
}

class $EmergencyContactsTable extends EmergencyContacts
    with TableInfo<$EmergencyContactsTable, EmergencyContact> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $EmergencyContactsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _nameMeta = const VerificationMeta('name');
  @override
  late final GeneratedColumn<String> name = GeneratedColumn<String>(
    'name',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _phoneMeta = const VerificationMeta('phone');
  @override
  late final GeneratedColumn<String> phone = GeneratedColumn<String>(
    'phone',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _groupsMeta = const VerificationMeta('groups');
  @override
  late final GeneratedColumn<String> groups = GeneratedColumn<String>(
    'groups',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant(','),
  );
  static const VerificationMeta _linkIdMeta = const VerificationMeta('linkId');
  @override
  late final GeneratedColumn<String> linkId = GeneratedColumn<String>(
    'link_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _positionMeta = const VerificationMeta(
    'position',
  );
  @override
  late final GeneratedColumn<int> position = GeneratedColumn<int>(
    'position',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<DateTime> createdAt = GeneratedColumn<DateTime>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    name,
    phone,
    groups,
    linkId,
    position,
    createdAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'emergency_contacts';
  @override
  VerificationContext validateIntegrity(
    Insertable<EmergencyContact> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('name')) {
      context.handle(
        _nameMeta,
        name.isAcceptableOrUnknown(data['name']!, _nameMeta),
      );
    } else if (isInserting) {
      context.missing(_nameMeta);
    }
    if (data.containsKey('phone')) {
      context.handle(
        _phoneMeta,
        phone.isAcceptableOrUnknown(data['phone']!, _phoneMeta),
      );
    } else if (isInserting) {
      context.missing(_phoneMeta);
    }
    if (data.containsKey('groups')) {
      context.handle(
        _groupsMeta,
        groups.isAcceptableOrUnknown(data['groups']!, _groupsMeta),
      );
    }
    if (data.containsKey('link_id')) {
      context.handle(
        _linkIdMeta,
        linkId.isAcceptableOrUnknown(data['link_id']!, _linkIdMeta),
      );
    }
    if (data.containsKey('position')) {
      context.handle(
        _positionMeta,
        position.isAcceptableOrUnknown(data['position']!, _positionMeta),
      );
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  EmergencyContact map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return EmergencyContact(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      name: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}name'],
      )!,
      phone: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}phone'],
      )!,
      groups: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}groups'],
      )!,
      linkId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}link_id'],
      ),
      position: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}position'],
      )!,
      createdAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}created_at'],
      )!,
    );
  }

  @override
  $EmergencyContactsTable createAlias(String alias) {
    return $EmergencyContactsTable(attachedDatabase, alias);
  }
}

class EmergencyContact extends DataClass
    implements Insertable<EmergencyContact> {
  final int id;
  final String name;

  /// `+216XXXXXXXX`, or an international number with `+`.
  final String phone;

  /// Comma-separated ids of [ContactGroups] (`,3,7,`), so a contact can sit in several groups.
  final String groups;
  final String? linkId;
  final int position;
  final DateTime createdAt;
  const EmergencyContact({
    required this.id,
    required this.name,
    required this.phone,
    required this.groups,
    this.linkId,
    required this.position,
    required this.createdAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['name'] = Variable<String>(name);
    map['phone'] = Variable<String>(phone);
    map['groups'] = Variable<String>(groups);
    if (!nullToAbsent || linkId != null) {
      map['link_id'] = Variable<String>(linkId);
    }
    map['position'] = Variable<int>(position);
    map['created_at'] = Variable<DateTime>(createdAt);
    return map;
  }

  EmergencyContactsCompanion toCompanion(bool nullToAbsent) {
    return EmergencyContactsCompanion(
      id: Value(id),
      name: Value(name),
      phone: Value(phone),
      groups: Value(groups),
      linkId: linkId == null && nullToAbsent
          ? const Value.absent()
          : Value(linkId),
      position: Value(position),
      createdAt: Value(createdAt),
    );
  }

  factory EmergencyContact.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return EmergencyContact(
      id: serializer.fromJson<int>(json['id']),
      name: serializer.fromJson<String>(json['name']),
      phone: serializer.fromJson<String>(json['phone']),
      groups: serializer.fromJson<String>(json['groups']),
      linkId: serializer.fromJson<String?>(json['linkId']),
      position: serializer.fromJson<int>(json['position']),
      createdAt: serializer.fromJson<DateTime>(json['createdAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'name': serializer.toJson<String>(name),
      'phone': serializer.toJson<String>(phone),
      'groups': serializer.toJson<String>(groups),
      'linkId': serializer.toJson<String?>(linkId),
      'position': serializer.toJson<int>(position),
      'createdAt': serializer.toJson<DateTime>(createdAt),
    };
  }

  EmergencyContact copyWith({
    int? id,
    String? name,
    String? phone,
    String? groups,
    Value<String?> linkId = const Value.absent(),
    int? position,
    DateTime? createdAt,
  }) => EmergencyContact(
    id: id ?? this.id,
    name: name ?? this.name,
    phone: phone ?? this.phone,
    groups: groups ?? this.groups,
    linkId: linkId.present ? linkId.value : this.linkId,
    position: position ?? this.position,
    createdAt: createdAt ?? this.createdAt,
  );
  EmergencyContact copyWithCompanion(EmergencyContactsCompanion data) {
    return EmergencyContact(
      id: data.id.present ? data.id.value : this.id,
      name: data.name.present ? data.name.value : this.name,
      phone: data.phone.present ? data.phone.value : this.phone,
      groups: data.groups.present ? data.groups.value : this.groups,
      linkId: data.linkId.present ? data.linkId.value : this.linkId,
      position: data.position.present ? data.position.value : this.position,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('EmergencyContact(')
          ..write('id: $id, ')
          ..write('name: $name, ')
          ..write('phone: $phone, ')
          ..write('groups: $groups, ')
          ..write('linkId: $linkId, ')
          ..write('position: $position, ')
          ..write('createdAt: $createdAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(id, name, phone, groups, linkId, position, createdAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is EmergencyContact &&
          other.id == this.id &&
          other.name == this.name &&
          other.phone == this.phone &&
          other.groups == this.groups &&
          other.linkId == this.linkId &&
          other.position == this.position &&
          other.createdAt == this.createdAt);
}

class EmergencyContactsCompanion extends UpdateCompanion<EmergencyContact> {
  final Value<int> id;
  final Value<String> name;
  final Value<String> phone;
  final Value<String> groups;
  final Value<String?> linkId;
  final Value<int> position;
  final Value<DateTime> createdAt;
  const EmergencyContactsCompanion({
    this.id = const Value.absent(),
    this.name = const Value.absent(),
    this.phone = const Value.absent(),
    this.groups = const Value.absent(),
    this.linkId = const Value.absent(),
    this.position = const Value.absent(),
    this.createdAt = const Value.absent(),
  });
  EmergencyContactsCompanion.insert({
    this.id = const Value.absent(),
    required String name,
    required String phone,
    this.groups = const Value.absent(),
    this.linkId = const Value.absent(),
    this.position = const Value.absent(),
    required DateTime createdAt,
  }) : name = Value(name),
       phone = Value(phone),
       createdAt = Value(createdAt);
  static Insertable<EmergencyContact> custom({
    Expression<int>? id,
    Expression<String>? name,
    Expression<String>? phone,
    Expression<String>? groups,
    Expression<String>? linkId,
    Expression<int>? position,
    Expression<DateTime>? createdAt,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (name != null) 'name': name,
      if (phone != null) 'phone': phone,
      if (groups != null) 'groups': groups,
      if (linkId != null) 'link_id': linkId,
      if (position != null) 'position': position,
      if (createdAt != null) 'created_at': createdAt,
    });
  }

  EmergencyContactsCompanion copyWith({
    Value<int>? id,
    Value<String>? name,
    Value<String>? phone,
    Value<String>? groups,
    Value<String?>? linkId,
    Value<int>? position,
    Value<DateTime>? createdAt,
  }) {
    return EmergencyContactsCompanion(
      id: id ?? this.id,
      name: name ?? this.name,
      phone: phone ?? this.phone,
      groups: groups ?? this.groups,
      linkId: linkId ?? this.linkId,
      position: position ?? this.position,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (name.present) {
      map['name'] = Variable<String>(name.value);
    }
    if (phone.present) {
      map['phone'] = Variable<String>(phone.value);
    }
    if (groups.present) {
      map['groups'] = Variable<String>(groups.value);
    }
    if (linkId.present) {
      map['link_id'] = Variable<String>(linkId.value);
    }
    if (position.present) {
      map['position'] = Variable<int>(position.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<DateTime>(createdAt.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('EmergencyContactsCompanion(')
          ..write('id: $id, ')
          ..write('name: $name, ')
          ..write('phone: $phone, ')
          ..write('groups: $groups, ')
          ..write('linkId: $linkId, ')
          ..write('position: $position, ')
          ..write('createdAt: $createdAt')
          ..write(')'))
        .toString();
  }
}

class $ContactGroupsTable extends ContactGroups
    with TableInfo<$ContactGroupsTable, ContactGroup> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ContactGroupsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _nameMeta = const VerificationMeta('name');
  @override
  late final GeneratedColumn<String> name = GeneratedColumn<String>(
    'name',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _positionMeta = const VerificationMeta(
    'position',
  );
  @override
  late final GeneratedColumn<int> position = GeneratedColumn<int>(
    'position',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  @override
  List<GeneratedColumn> get $columns => [id, name, position];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'contact_groups';
  @override
  VerificationContext validateIntegrity(
    Insertable<ContactGroup> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('name')) {
      context.handle(
        _nameMeta,
        name.isAcceptableOrUnknown(data['name']!, _nameMeta),
      );
    } else if (isInserting) {
      context.missing(_nameMeta);
    }
    if (data.containsKey('position')) {
      context.handle(
        _positionMeta,
        position.isAcceptableOrUnknown(data['position']!, _positionMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  ContactGroup map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return ContactGroup(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      name: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}name'],
      )!,
      position: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}position'],
      )!,
    );
  }

  @override
  $ContactGroupsTable createAlias(String alias) {
    return $ContactGroupsTable(attachedDatabase, alias);
  }
}

class ContactGroup extends DataClass implements Insertable<ContactGroup> {
  final int id;
  final String name;
  final int position;
  const ContactGroup({
    required this.id,
    required this.name,
    required this.position,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['name'] = Variable<String>(name);
    map['position'] = Variable<int>(position);
    return map;
  }

  ContactGroupsCompanion toCompanion(bool nullToAbsent) {
    return ContactGroupsCompanion(
      id: Value(id),
      name: Value(name),
      position: Value(position),
    );
  }

  factory ContactGroup.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return ContactGroup(
      id: serializer.fromJson<int>(json['id']),
      name: serializer.fromJson<String>(json['name']),
      position: serializer.fromJson<int>(json['position']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'name': serializer.toJson<String>(name),
      'position': serializer.toJson<int>(position),
    };
  }

  ContactGroup copyWith({int? id, String? name, int? position}) => ContactGroup(
    id: id ?? this.id,
    name: name ?? this.name,
    position: position ?? this.position,
  );
  ContactGroup copyWithCompanion(ContactGroupsCompanion data) {
    return ContactGroup(
      id: data.id.present ? data.id.value : this.id,
      name: data.name.present ? data.name.value : this.name,
      position: data.position.present ? data.position.value : this.position,
    );
  }

  @override
  String toString() {
    return (StringBuffer('ContactGroup(')
          ..write('id: $id, ')
          ..write('name: $name, ')
          ..write('position: $position')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(id, name, position);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ContactGroup &&
          other.id == this.id &&
          other.name == this.name &&
          other.position == this.position);
}

class ContactGroupsCompanion extends UpdateCompanion<ContactGroup> {
  final Value<int> id;
  final Value<String> name;
  final Value<int> position;
  const ContactGroupsCompanion({
    this.id = const Value.absent(),
    this.name = const Value.absent(),
    this.position = const Value.absent(),
  });
  ContactGroupsCompanion.insert({
    this.id = const Value.absent(),
    required String name,
    this.position = const Value.absent(),
  }) : name = Value(name);
  static Insertable<ContactGroup> custom({
    Expression<int>? id,
    Expression<String>? name,
    Expression<int>? position,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (name != null) 'name': name,
      if (position != null) 'position': position,
    });
  }

  ContactGroupsCompanion copyWith({
    Value<int>? id,
    Value<String>? name,
    Value<int>? position,
  }) {
    return ContactGroupsCompanion(
      id: id ?? this.id,
      name: name ?? this.name,
      position: position ?? this.position,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (name.present) {
      map['name'] = Variable<String>(name.value);
    }
    if (position.present) {
      map['position'] = Variable<int>(position.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ContactGroupsCompanion(')
          ..write('id: $id, ')
          ..write('name: $name, ')
          ..write('position: $position')
          ..write(')'))
        .toString();
  }
}

class $SafetyAlertHistoryTable extends SafetyAlertHistory
    with TableInfo<$SafetyAlertHistoryTable, SafetyAlertEntry> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SafetyAlertHistoryTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _kindMeta = const VerificationMeta('kind');
  @override
  late final GeneratedColumn<String> kind = GeneratedColumn<String>(
    'kind',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _atMeta = const VerificationMeta('at');
  @override
  late final GeneratedColumn<DateTime> at = GeneratedColumn<DateTime>(
    'at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _channelsMeta = const VerificationMeta(
    'channels',
  );
  @override
  late final GeneratedColumn<String> channels = GeneratedColumn<String>(
    'channels',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant(''),
  );
  static const VerificationMeta _recipientsMeta = const VerificationMeta(
    'recipients',
  );
  @override
  late final GeneratedColumn<int> recipients = GeneratedColumn<int>(
    'recipients',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _serverIdMeta = const VerificationMeta(
    'serverId',
  );
  @override
  late final GeneratedColumn<String> serverId = GeneratedColumn<String>(
    'server_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _statusMeta = const VerificationMeta('status');
  @override
  late final GeneratedColumn<String> status = GeneratedColumn<String>(
    'status',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    kind,
    at,
    channels,
    recipients,
    serverId,
    status,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'safety_alert_history';
  @override
  VerificationContext validateIntegrity(
    Insertable<SafetyAlertEntry> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('kind')) {
      context.handle(
        _kindMeta,
        kind.isAcceptableOrUnknown(data['kind']!, _kindMeta),
      );
    } else if (isInserting) {
      context.missing(_kindMeta);
    }
    if (data.containsKey('at')) {
      context.handle(_atMeta, at.isAcceptableOrUnknown(data['at']!, _atMeta));
    } else if (isInserting) {
      context.missing(_atMeta);
    }
    if (data.containsKey('channels')) {
      context.handle(
        _channelsMeta,
        channels.isAcceptableOrUnknown(data['channels']!, _channelsMeta),
      );
    }
    if (data.containsKey('recipients')) {
      context.handle(
        _recipientsMeta,
        recipients.isAcceptableOrUnknown(data['recipients']!, _recipientsMeta),
      );
    }
    if (data.containsKey('server_id')) {
      context.handle(
        _serverIdMeta,
        serverId.isAcceptableOrUnknown(data['server_id']!, _serverIdMeta),
      );
    }
    if (data.containsKey('status')) {
      context.handle(
        _statusMeta,
        status.isAcceptableOrUnknown(data['status']!, _statusMeta),
      );
    } else if (isInserting) {
      context.missing(_statusMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  SafetyAlertEntry map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SafetyAlertEntry(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      kind: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}kind'],
      )!,
      at: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}at'],
      )!,
      channels: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}channels'],
      )!,
      recipients: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}recipients'],
      )!,
      serverId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}server_id'],
      ),
      status: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}status'],
      )!,
    );
  }

  @override
  $SafetyAlertHistoryTable createAlias(String alias) {
    return $SafetyAlertHistoryTable(attachedDatabase, alias);
  }
}

class SafetyAlertEntry extends DataClass
    implements Insertable<SafetyAlertEntry> {
  final int id;

  /// `sos_message` | `safety_check` | `live_share`.
  final String kind;
  final DateTime at;

  /// Comma-separated: `app`, `sms`, `whatsapp`.
  final String channels;
  final int recipients;
  final String? serverId;

  /// `sent` | `cancelled` | `failed` | `ok` (a safety check answered).
  final String status;
  const SafetyAlertEntry({
    required this.id,
    required this.kind,
    required this.at,
    required this.channels,
    required this.recipients,
    this.serverId,
    required this.status,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['kind'] = Variable<String>(kind);
    map['at'] = Variable<DateTime>(at);
    map['channels'] = Variable<String>(channels);
    map['recipients'] = Variable<int>(recipients);
    if (!nullToAbsent || serverId != null) {
      map['server_id'] = Variable<String>(serverId);
    }
    map['status'] = Variable<String>(status);
    return map;
  }

  SafetyAlertHistoryCompanion toCompanion(bool nullToAbsent) {
    return SafetyAlertHistoryCompanion(
      id: Value(id),
      kind: Value(kind),
      at: Value(at),
      channels: Value(channels),
      recipients: Value(recipients),
      serverId: serverId == null && nullToAbsent
          ? const Value.absent()
          : Value(serverId),
      status: Value(status),
    );
  }

  factory SafetyAlertEntry.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SafetyAlertEntry(
      id: serializer.fromJson<int>(json['id']),
      kind: serializer.fromJson<String>(json['kind']),
      at: serializer.fromJson<DateTime>(json['at']),
      channels: serializer.fromJson<String>(json['channels']),
      recipients: serializer.fromJson<int>(json['recipients']),
      serverId: serializer.fromJson<String?>(json['serverId']),
      status: serializer.fromJson<String>(json['status']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'kind': serializer.toJson<String>(kind),
      'at': serializer.toJson<DateTime>(at),
      'channels': serializer.toJson<String>(channels),
      'recipients': serializer.toJson<int>(recipients),
      'serverId': serializer.toJson<String?>(serverId),
      'status': serializer.toJson<String>(status),
    };
  }

  SafetyAlertEntry copyWith({
    int? id,
    String? kind,
    DateTime? at,
    String? channels,
    int? recipients,
    Value<String?> serverId = const Value.absent(),
    String? status,
  }) => SafetyAlertEntry(
    id: id ?? this.id,
    kind: kind ?? this.kind,
    at: at ?? this.at,
    channels: channels ?? this.channels,
    recipients: recipients ?? this.recipients,
    serverId: serverId.present ? serverId.value : this.serverId,
    status: status ?? this.status,
  );
  SafetyAlertEntry copyWithCompanion(SafetyAlertHistoryCompanion data) {
    return SafetyAlertEntry(
      id: data.id.present ? data.id.value : this.id,
      kind: data.kind.present ? data.kind.value : this.kind,
      at: data.at.present ? data.at.value : this.at,
      channels: data.channels.present ? data.channels.value : this.channels,
      recipients: data.recipients.present
          ? data.recipients.value
          : this.recipients,
      serverId: data.serverId.present ? data.serverId.value : this.serverId,
      status: data.status.present ? data.status.value : this.status,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SafetyAlertEntry(')
          ..write('id: $id, ')
          ..write('kind: $kind, ')
          ..write('at: $at, ')
          ..write('channels: $channels, ')
          ..write('recipients: $recipients, ')
          ..write('serverId: $serverId, ')
          ..write('status: $status')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(id, kind, at, channels, recipients, serverId, status);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SafetyAlertEntry &&
          other.id == this.id &&
          other.kind == this.kind &&
          other.at == this.at &&
          other.channels == this.channels &&
          other.recipients == this.recipients &&
          other.serverId == this.serverId &&
          other.status == this.status);
}

class SafetyAlertHistoryCompanion extends UpdateCompanion<SafetyAlertEntry> {
  final Value<int> id;
  final Value<String> kind;
  final Value<DateTime> at;
  final Value<String> channels;
  final Value<int> recipients;
  final Value<String?> serverId;
  final Value<String> status;
  const SafetyAlertHistoryCompanion({
    this.id = const Value.absent(),
    this.kind = const Value.absent(),
    this.at = const Value.absent(),
    this.channels = const Value.absent(),
    this.recipients = const Value.absent(),
    this.serverId = const Value.absent(),
    this.status = const Value.absent(),
  });
  SafetyAlertHistoryCompanion.insert({
    this.id = const Value.absent(),
    required String kind,
    required DateTime at,
    this.channels = const Value.absent(),
    this.recipients = const Value.absent(),
    this.serverId = const Value.absent(),
    required String status,
  }) : kind = Value(kind),
       at = Value(at),
       status = Value(status);
  static Insertable<SafetyAlertEntry> custom({
    Expression<int>? id,
    Expression<String>? kind,
    Expression<DateTime>? at,
    Expression<String>? channels,
    Expression<int>? recipients,
    Expression<String>? serverId,
    Expression<String>? status,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (kind != null) 'kind': kind,
      if (at != null) 'at': at,
      if (channels != null) 'channels': channels,
      if (recipients != null) 'recipients': recipients,
      if (serverId != null) 'server_id': serverId,
      if (status != null) 'status': status,
    });
  }

  SafetyAlertHistoryCompanion copyWith({
    Value<int>? id,
    Value<String>? kind,
    Value<DateTime>? at,
    Value<String>? channels,
    Value<int>? recipients,
    Value<String?>? serverId,
    Value<String>? status,
  }) {
    return SafetyAlertHistoryCompanion(
      id: id ?? this.id,
      kind: kind ?? this.kind,
      at: at ?? this.at,
      channels: channels ?? this.channels,
      recipients: recipients ?? this.recipients,
      serverId: serverId ?? this.serverId,
      status: status ?? this.status,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (kind.present) {
      map['kind'] = Variable<String>(kind.value);
    }
    if (at.present) {
      map['at'] = Variable<DateTime>(at.value);
    }
    if (channels.present) {
      map['channels'] = Variable<String>(channels.value);
    }
    if (recipients.present) {
      map['recipients'] = Variable<int>(recipients.value);
    }
    if (serverId.present) {
      map['server_id'] = Variable<String>(serverId.value);
    }
    if (status.present) {
      map['status'] = Variable<String>(status.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SafetyAlertHistoryCompanion(')
          ..write('id: $id, ')
          ..write('kind: $kind, ')
          ..write('at: $at, ')
          ..write('channels: $channels, ')
          ..write('recipients: $recipients, ')
          ..write('serverId: $serverId, ')
          ..write('status: $status')
          ..write(')'))
        .toString();
  }
}

class $MedicalProfilesTable extends MedicalProfiles
    with TableInfo<$MedicalProfilesTable, MedicalProfileRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $MedicalProfilesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _dataMeta = const VerificationMeta('data');
  @override
  late final GeneratedColumn<String> data = GeneratedColumn<String>(
    'data',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _consentVersionMeta = const VerificationMeta(
    'consentVersion',
  );
  @override
  late final GeneratedColumn<String> consentVersion = GeneratedColumn<String>(
    'consent_version',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _consentAtMeta = const VerificationMeta(
    'consentAt',
  );
  @override
  late final GeneratedColumn<DateTime> consentAt = GeneratedColumn<DateTime>(
    'consent_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _lockedMeta = const VerificationMeta('locked');
  @override
  late final GeneratedColumn<bool> locked = GeneratedColumn<bool>(
    'locked',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("locked" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _updatedAtMeta = const VerificationMeta(
    'updatedAt',
  );
  @override
  late final GeneratedColumn<DateTime> updatedAt = GeneratedColumn<DateTime>(
    'updated_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    data,
    consentVersion,
    consentAt,
    locked,
    updatedAt,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'medical_profiles';
  @override
  VerificationContext validateIntegrity(
    Insertable<MedicalProfileRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('data')) {
      context.handle(
        _dataMeta,
        this.data.isAcceptableOrUnknown(data['data']!, _dataMeta),
      );
    } else if (isInserting) {
      context.missing(_dataMeta);
    }
    if (data.containsKey('consent_version')) {
      context.handle(
        _consentVersionMeta,
        consentVersion.isAcceptableOrUnknown(
          data['consent_version']!,
          _consentVersionMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_consentVersionMeta);
    }
    if (data.containsKey('consent_at')) {
      context.handle(
        _consentAtMeta,
        consentAt.isAcceptableOrUnknown(data['consent_at']!, _consentAtMeta),
      );
    } else if (isInserting) {
      context.missing(_consentAtMeta);
    }
    if (data.containsKey('locked')) {
      context.handle(
        _lockedMeta,
        locked.isAcceptableOrUnknown(data['locked']!, _lockedMeta),
      );
    }
    if (data.containsKey('updated_at')) {
      context.handle(
        _updatedAtMeta,
        updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta),
      );
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  MedicalProfileRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return MedicalProfileRow(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      data: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}data'],
      )!,
      consentVersion: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}consent_version'],
      )!,
      consentAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}consent_at'],
      )!,
      locked: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}locked'],
      )!,
      updatedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}updated_at'],
      )!,
    );
  }

  @override
  $MedicalProfilesTable createAlias(String alias) {
    return $MedicalProfilesTable(attachedDatabase, alias);
  }
}

class MedicalProfileRow extends DataClass
    implements Insertable<MedicalProfileRow> {
  final int id;
  final String data;
  final String consentVersion;
  final DateTime consentAt;
  final bool locked;
  final DateTime updatedAt;
  const MedicalProfileRow({
    required this.id,
    required this.data,
    required this.consentVersion,
    required this.consentAt,
    required this.locked,
    required this.updatedAt,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['data'] = Variable<String>(data);
    map['consent_version'] = Variable<String>(consentVersion);
    map['consent_at'] = Variable<DateTime>(consentAt);
    map['locked'] = Variable<bool>(locked);
    map['updated_at'] = Variable<DateTime>(updatedAt);
    return map;
  }

  MedicalProfilesCompanion toCompanion(bool nullToAbsent) {
    return MedicalProfilesCompanion(
      id: Value(id),
      data: Value(data),
      consentVersion: Value(consentVersion),
      consentAt: Value(consentAt),
      locked: Value(locked),
      updatedAt: Value(updatedAt),
    );
  }

  factory MedicalProfileRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return MedicalProfileRow(
      id: serializer.fromJson<int>(json['id']),
      data: serializer.fromJson<String>(json['data']),
      consentVersion: serializer.fromJson<String>(json['consentVersion']),
      consentAt: serializer.fromJson<DateTime>(json['consentAt']),
      locked: serializer.fromJson<bool>(json['locked']),
      updatedAt: serializer.fromJson<DateTime>(json['updatedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'data': serializer.toJson<String>(data),
      'consentVersion': serializer.toJson<String>(consentVersion),
      'consentAt': serializer.toJson<DateTime>(consentAt),
      'locked': serializer.toJson<bool>(locked),
      'updatedAt': serializer.toJson<DateTime>(updatedAt),
    };
  }

  MedicalProfileRow copyWith({
    int? id,
    String? data,
    String? consentVersion,
    DateTime? consentAt,
    bool? locked,
    DateTime? updatedAt,
  }) => MedicalProfileRow(
    id: id ?? this.id,
    data: data ?? this.data,
    consentVersion: consentVersion ?? this.consentVersion,
    consentAt: consentAt ?? this.consentAt,
    locked: locked ?? this.locked,
    updatedAt: updatedAt ?? this.updatedAt,
  );
  MedicalProfileRow copyWithCompanion(MedicalProfilesCompanion data) {
    return MedicalProfileRow(
      id: data.id.present ? data.id.value : this.id,
      data: data.data.present ? data.data.value : this.data,
      consentVersion: data.consentVersion.present
          ? data.consentVersion.value
          : this.consentVersion,
      consentAt: data.consentAt.present ? data.consentAt.value : this.consentAt,
      locked: data.locked.present ? data.locked.value : this.locked,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('MedicalProfileRow(')
          ..write('id: $id, ')
          ..write('data: $data, ')
          ..write('consentVersion: $consentVersion, ')
          ..write('consentAt: $consentAt, ')
          ..write('locked: $locked, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(id, data, consentVersion, consentAt, locked, updatedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is MedicalProfileRow &&
          other.id == this.id &&
          other.data == this.data &&
          other.consentVersion == this.consentVersion &&
          other.consentAt == this.consentAt &&
          other.locked == this.locked &&
          other.updatedAt == this.updatedAt);
}

class MedicalProfilesCompanion extends UpdateCompanion<MedicalProfileRow> {
  final Value<int> id;
  final Value<String> data;
  final Value<String> consentVersion;
  final Value<DateTime> consentAt;
  final Value<bool> locked;
  final Value<DateTime> updatedAt;
  const MedicalProfilesCompanion({
    this.id = const Value.absent(),
    this.data = const Value.absent(),
    this.consentVersion = const Value.absent(),
    this.consentAt = const Value.absent(),
    this.locked = const Value.absent(),
    this.updatedAt = const Value.absent(),
  });
  MedicalProfilesCompanion.insert({
    this.id = const Value.absent(),
    required String data,
    required String consentVersion,
    required DateTime consentAt,
    this.locked = const Value.absent(),
    required DateTime updatedAt,
  }) : data = Value(data),
       consentVersion = Value(consentVersion),
       consentAt = Value(consentAt),
       updatedAt = Value(updatedAt);
  static Insertable<MedicalProfileRow> custom({
    Expression<int>? id,
    Expression<String>? data,
    Expression<String>? consentVersion,
    Expression<DateTime>? consentAt,
    Expression<bool>? locked,
    Expression<DateTime>? updatedAt,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (data != null) 'data': data,
      if (consentVersion != null) 'consent_version': consentVersion,
      if (consentAt != null) 'consent_at': consentAt,
      if (locked != null) 'locked': locked,
      if (updatedAt != null) 'updated_at': updatedAt,
    });
  }

  MedicalProfilesCompanion copyWith({
    Value<int>? id,
    Value<String>? data,
    Value<String>? consentVersion,
    Value<DateTime>? consentAt,
    Value<bool>? locked,
    Value<DateTime>? updatedAt,
  }) {
    return MedicalProfilesCompanion(
      id: id ?? this.id,
      data: data ?? this.data,
      consentVersion: consentVersion ?? this.consentVersion,
      consentAt: consentAt ?? this.consentAt,
      locked: locked ?? this.locked,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (data.present) {
      map['data'] = Variable<String>(data.value);
    }
    if (consentVersion.present) {
      map['consent_version'] = Variable<String>(consentVersion.value);
    }
    if (consentAt.present) {
      map['consent_at'] = Variable<DateTime>(consentAt.value);
    }
    if (locked.present) {
      map['locked'] = Variable<bool>(locked.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<DateTime>(updatedAt.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('MedicalProfilesCompanion(')
          ..write('id: $id, ')
          ..write('data: $data, ')
          ..write('consentVersion: $consentVersion, ')
          ..write('consentAt: $consentAt, ')
          ..write('locked: $locked, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $PendingReportsTable pendingReports = $PendingReportsTable(this);
  late final $MediaItemsTable mediaItems = $MediaItemsTable(this);
  late final $EmergencyContactsTable emergencyContacts =
      $EmergencyContactsTable(this);
  late final $ContactGroupsTable contactGroups = $ContactGroupsTable(this);
  late final $SafetyAlertHistoryTable safetyAlertHistory =
      $SafetyAlertHistoryTable(this);
  late final $MedicalProfilesTable medicalProfiles = $MedicalProfilesTable(
    this,
  );
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    pendingReports,
    mediaItems,
    emergencyContacts,
    contactGroups,
    safetyAlertHistory,
    medicalProfiles,
  ];
  @override
  DriftDatabaseOptions get options =>
      const DriftDatabaseOptions(storeDateTimeAsText: true);
}

typedef $$PendingReportsTableCreateCompanionBuilder =
    PendingReportsCompanion Function({
      required String clientUuid,
      required String category,
      required String payload,
      required String tempCode,
      Value<String?> serverId,
      Value<String?> serverTrackingCode,
      Value<String?> serverStatus,
      Value<String?> serverSnapshot,
      Value<String> state,
      Value<int> attempts,
      Value<String?> lastError,
      Value<DateTime?> nextAttemptAt,
      required DateTime createdAt,
      required DateTime updatedAt,
      Value<int> rowid,
    });
typedef $$PendingReportsTableUpdateCompanionBuilder =
    PendingReportsCompanion Function({
      Value<String> clientUuid,
      Value<String> category,
      Value<String> payload,
      Value<String> tempCode,
      Value<String?> serverId,
      Value<String?> serverTrackingCode,
      Value<String?> serverStatus,
      Value<String?> serverSnapshot,
      Value<String> state,
      Value<int> attempts,
      Value<String?> lastError,
      Value<DateTime?> nextAttemptAt,
      Value<DateTime> createdAt,
      Value<DateTime> updatedAt,
      Value<int> rowid,
    });

final class $$PendingReportsTableReferences
    extends BaseReferences<_$AppDatabase, $PendingReportsTable, PendingReport> {
  $$PendingReportsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static MultiTypedResultKey<$MediaItemsTable, List<MediaItem>>
  _mediaItemsRefsTable(_$AppDatabase db) => MultiTypedResultKey.fromTable(
    db.mediaItems,
    aliasName: 'pending_reports__client_uuid__media_items__report_uuid',
  );

  $$MediaItemsTableProcessedTableManager get mediaItemsRefs {
    final manager = $$MediaItemsTableTableManager($_db, $_db.mediaItems).filter(
      (f) => f.reportUuid.clientUuid.sqlEquals(
        $_itemColumn<String>('client_uuid')!,
      ),
    );

    final cache = $_typedResult.readTableOrNull(_mediaItemsRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$PendingReportsTableFilterComposer
    extends Composer<_$AppDatabase, $PendingReportsTable> {
  $$PendingReportsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get category => $composableBuilder(
    column: $table.category,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get payload => $composableBuilder(
    column: $table.payload,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get tempCode => $composableBuilder(
    column: $table.tempCode,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get serverId => $composableBuilder(
    column: $table.serverId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get serverTrackingCode => $composableBuilder(
    column: $table.serverTrackingCode,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get serverStatus => $composableBuilder(
    column: $table.serverStatus,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get serverSnapshot => $composableBuilder(
    column: $table.serverSnapshot,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get attempts => $composableBuilder(
    column: $table.attempts,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get lastError => $composableBuilder(
    column: $table.lastError,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get nextAttemptAt => $composableBuilder(
    column: $table.nextAttemptAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnFilters(column),
  );

  Expression<bool> mediaItemsRefs(
    Expression<bool> Function($$MediaItemsTableFilterComposer f) f,
  ) {
    final $$MediaItemsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.clientUuid,
      referencedTable: $db.mediaItems,
      getReferencedColumn: (t) => t.reportUuid,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MediaItemsTableFilterComposer(
            $db: $db,
            $table: $db.mediaItems,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$PendingReportsTableOrderingComposer
    extends Composer<_$AppDatabase, $PendingReportsTable> {
  $$PendingReportsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get category => $composableBuilder(
    column: $table.category,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get payload => $composableBuilder(
    column: $table.payload,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get tempCode => $composableBuilder(
    column: $table.tempCode,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get serverId => $composableBuilder(
    column: $table.serverId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get serverTrackingCode => $composableBuilder(
    column: $table.serverTrackingCode,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get serverStatus => $composableBuilder(
    column: $table.serverStatus,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get serverSnapshot => $composableBuilder(
    column: $table.serverSnapshot,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get attempts => $composableBuilder(
    column: $table.attempts,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get lastError => $composableBuilder(
    column: $table.lastError,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get nextAttemptAt => $composableBuilder(
    column: $table.nextAttemptAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$PendingReportsTableAnnotationComposer
    extends Composer<_$AppDatabase, $PendingReportsTable> {
  $$PendingReportsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get clientUuid => $composableBuilder(
    column: $table.clientUuid,
    builder: (column) => column,
  );

  GeneratedColumn<String> get category =>
      $composableBuilder(column: $table.category, builder: (column) => column);

  GeneratedColumn<String> get payload =>
      $composableBuilder(column: $table.payload, builder: (column) => column);

  GeneratedColumn<String> get tempCode =>
      $composableBuilder(column: $table.tempCode, builder: (column) => column);

  GeneratedColumn<String> get serverId =>
      $composableBuilder(column: $table.serverId, builder: (column) => column);

  GeneratedColumn<String> get serverTrackingCode => $composableBuilder(
    column: $table.serverTrackingCode,
    builder: (column) => column,
  );

  GeneratedColumn<String> get serverStatus => $composableBuilder(
    column: $table.serverStatus,
    builder: (column) => column,
  );

  GeneratedColumn<String> get serverSnapshot => $composableBuilder(
    column: $table.serverSnapshot,
    builder: (column) => column,
  );

  GeneratedColumn<String> get state =>
      $composableBuilder(column: $table.state, builder: (column) => column);

  GeneratedColumn<int> get attempts =>
      $composableBuilder(column: $table.attempts, builder: (column) => column);

  GeneratedColumn<String> get lastError =>
      $composableBuilder(column: $table.lastError, builder: (column) => column);

  GeneratedColumn<DateTime> get nextAttemptAt => $composableBuilder(
    column: $table.nextAttemptAt,
    builder: (column) => column,
  );

  GeneratedColumn<DateTime> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<DateTime> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);

  Expression<T> mediaItemsRefs<T extends Object>(
    Expression<T> Function($$MediaItemsTableAnnotationComposer a) f,
  ) {
    final $$MediaItemsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.clientUuid,
      referencedTable: $db.mediaItems,
      getReferencedColumn: (t) => t.reportUuid,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$MediaItemsTableAnnotationComposer(
            $db: $db,
            $table: $db.mediaItems,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$PendingReportsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $PendingReportsTable,
          PendingReport,
          $$PendingReportsTableFilterComposer,
          $$PendingReportsTableOrderingComposer,
          $$PendingReportsTableAnnotationComposer,
          $$PendingReportsTableCreateCompanionBuilder,
          $$PendingReportsTableUpdateCompanionBuilder,
          (PendingReport, $$PendingReportsTableReferences),
          PendingReport,
          PrefetchHooks Function({bool mediaItemsRefs})
        > {
  $$PendingReportsTableTableManager(
    _$AppDatabase db,
    $PendingReportsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$PendingReportsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$PendingReportsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$PendingReportsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> clientUuid = const Value.absent(),
                Value<String> category = const Value.absent(),
                Value<String> payload = const Value.absent(),
                Value<String> tempCode = const Value.absent(),
                Value<String?> serverId = const Value.absent(),
                Value<String?> serverTrackingCode = const Value.absent(),
                Value<String?> serverStatus = const Value.absent(),
                Value<String?> serverSnapshot = const Value.absent(),
                Value<String> state = const Value.absent(),
                Value<int> attempts = const Value.absent(),
                Value<String?> lastError = const Value.absent(),
                Value<DateTime?> nextAttemptAt = const Value.absent(),
                Value<DateTime> createdAt = const Value.absent(),
                Value<DateTime> updatedAt = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => PendingReportsCompanion(
                clientUuid: clientUuid,
                category: category,
                payload: payload,
                tempCode: tempCode,
                serverId: serverId,
                serverTrackingCode: serverTrackingCode,
                serverStatus: serverStatus,
                serverSnapshot: serverSnapshot,
                state: state,
                attempts: attempts,
                lastError: lastError,
                nextAttemptAt: nextAttemptAt,
                createdAt: createdAt,
                updatedAt: updatedAt,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String clientUuid,
                required String category,
                required String payload,
                required String tempCode,
                Value<String?> serverId = const Value.absent(),
                Value<String?> serverTrackingCode = const Value.absent(),
                Value<String?> serverStatus = const Value.absent(),
                Value<String?> serverSnapshot = const Value.absent(),
                Value<String> state = const Value.absent(),
                Value<int> attempts = const Value.absent(),
                Value<String?> lastError = const Value.absent(),
                Value<DateTime?> nextAttemptAt = const Value.absent(),
                required DateTime createdAt,
                required DateTime updatedAt,
                Value<int> rowid = const Value.absent(),
              }) => PendingReportsCompanion.insert(
                clientUuid: clientUuid,
                category: category,
                payload: payload,
                tempCode: tempCode,
                serverId: serverId,
                serverTrackingCode: serverTrackingCode,
                serverStatus: serverStatus,
                serverSnapshot: serverSnapshot,
                state: state,
                attempts: attempts,
                lastError: lastError,
                nextAttemptAt: nextAttemptAt,
                createdAt: createdAt,
                updatedAt: updatedAt,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$PendingReportsTable, PendingReport>(table),
                  $$PendingReportsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({mediaItemsRefs = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [if (mediaItemsRefs) db.mediaItems],
              addJoins: null,
              getPrefetchedDataCallback: (items) async {
                return [
                  if (mediaItemsRefs)
                    await $_getPrefetchedData<
                      PendingReport,
                      $PendingReportsTable,
                      MediaItem
                    >(
                      currentTable: table,
                      referencedTable: $$PendingReportsTableReferences
                          ._mediaItemsRefsTable(db),
                      managerFromTypedResult: (p0) =>
                          $$PendingReportsTableReferences(
                            db,
                            table,
                            p0,
                          ).mediaItemsRefs,
                      referencedItemsForCurrentItem: (item, referencedItems) =>
                          referencedItems.where(
                            (e) => e.reportUuid == item.clientUuid,
                          ),
                      typedResults: items,
                    ),
                ];
              },
            );
          },
        ),
      );
}

typedef $$PendingReportsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $PendingReportsTable,
      PendingReport,
      $$PendingReportsTableFilterComposer,
      $$PendingReportsTableOrderingComposer,
      $$PendingReportsTableAnnotationComposer,
      $$PendingReportsTableCreateCompanionBuilder,
      $$PendingReportsTableUpdateCompanionBuilder,
      (PendingReport, $$PendingReportsTableReferences),
      PendingReport,
      PrefetchHooks Function({bool mediaItemsRefs})
    >;
typedef $$MediaItemsTableCreateCompanionBuilder = MediaItemsCompanion Function({
  Value<int> id,
  required String reportUuid,
  required String path,
  required String kind,
  required String mime,
  required int size,
  required String sha256,
  Value<String?> uploadUrl,
  Value<int> uploadOffset,
  Value<String> state,
  Value<int> attempts,
  Value<String?> lastError,
  Value<DateTime?> nextAttemptAt,
});
typedef $$MediaItemsTableUpdateCompanionBuilder = MediaItemsCompanion Function({
  Value<int> id,
  Value<String> reportUuid,
  Value<String> path,
  Value<String> kind,
  Value<String> mime,
  Value<int> size,
  Value<String> sha256,
  Value<String?> uploadUrl,
  Value<int> uploadOffset,
  Value<String> state,
  Value<int> attempts,
  Value<String?> lastError,
  Value<DateTime?> nextAttemptAt,
});

final class $$MediaItemsTableReferences
    extends BaseReferences<_$AppDatabase, $MediaItemsTable, MediaItem> {
  $$MediaItemsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $PendingReportsTable _reportUuidTable(_$AppDatabase db) => db
      .pendingReports
      .createAlias('media_items__report_uuid__pending_reports__client_uuid');

  $$PendingReportsTableProcessedTableManager get reportUuid {
    final $_column = $_itemColumn<String>('report_uuid')!;

    final manager = $$PendingReportsTableTableManager(
      $_db,
      $_db.pendingReports,
    ).filter((f) => f.clientUuid.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_reportUuidTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$MediaItemsTableFilterComposer
    extends Composer<_$AppDatabase, $MediaItemsTable> {
  $$MediaItemsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get path => $composableBuilder(
    column: $table.path,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get mime => $composableBuilder(
    column: $table.mime,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get size => $composableBuilder(
    column: $table.size,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get sha256 => $composableBuilder(
    column: $table.sha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get uploadUrl => $composableBuilder(
    column: $table.uploadUrl,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get uploadOffset => $composableBuilder(
    column: $table.uploadOffset,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get attempts => $composableBuilder(
    column: $table.attempts,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get lastError => $composableBuilder(
    column: $table.lastError,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get nextAttemptAt => $composableBuilder(
    column: $table.nextAttemptAt,
    builder: (column) => ColumnFilters(column),
  );

  $$PendingReportsTableFilterComposer get reportUuid {
    final $$PendingReportsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.reportUuid,
      referencedTable: $db.pendingReports,
      getReferencedColumn: (t) => t.clientUuid,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$PendingReportsTableFilterComposer(
            $db: $db,
            $table: $db.pendingReports,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$MediaItemsTableOrderingComposer
    extends Composer<_$AppDatabase, $MediaItemsTable> {
  $$MediaItemsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get path => $composableBuilder(
    column: $table.path,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get mime => $composableBuilder(
    column: $table.mime,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get size => $composableBuilder(
    column: $table.size,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get sha256 => $composableBuilder(
    column: $table.sha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get uploadUrl => $composableBuilder(
    column: $table.uploadUrl,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get uploadOffset => $composableBuilder(
    column: $table.uploadOffset,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get attempts => $composableBuilder(
    column: $table.attempts,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get lastError => $composableBuilder(
    column: $table.lastError,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get nextAttemptAt => $composableBuilder(
    column: $table.nextAttemptAt,
    builder: (column) => ColumnOrderings(column),
  );

  $$PendingReportsTableOrderingComposer get reportUuid {
    final $$PendingReportsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.reportUuid,
      referencedTable: $db.pendingReports,
      getReferencedColumn: (t) => t.clientUuid,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$PendingReportsTableOrderingComposer(
            $db: $db,
            $table: $db.pendingReports,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$MediaItemsTableAnnotationComposer
    extends Composer<_$AppDatabase, $MediaItemsTable> {
  $$MediaItemsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get path =>
      $composableBuilder(column: $table.path, builder: (column) => column);

  GeneratedColumn<String> get kind =>
      $composableBuilder(column: $table.kind, builder: (column) => column);

  GeneratedColumn<String> get mime =>
      $composableBuilder(column: $table.mime, builder: (column) => column);

  GeneratedColumn<int> get size =>
      $composableBuilder(column: $table.size, builder: (column) => column);

  GeneratedColumn<String> get sha256 =>
      $composableBuilder(column: $table.sha256, builder: (column) => column);

  GeneratedColumn<String> get uploadUrl =>
      $composableBuilder(column: $table.uploadUrl, builder: (column) => column);

  GeneratedColumn<int> get uploadOffset => $composableBuilder(
    column: $table.uploadOffset,
    builder: (column) => column,
  );

  GeneratedColumn<String> get state =>
      $composableBuilder(column: $table.state, builder: (column) => column);

  GeneratedColumn<int> get attempts =>
      $composableBuilder(column: $table.attempts, builder: (column) => column);

  GeneratedColumn<String> get lastError =>
      $composableBuilder(column: $table.lastError, builder: (column) => column);

  GeneratedColumn<DateTime> get nextAttemptAt => $composableBuilder(
    column: $table.nextAttemptAt,
    builder: (column) => column,
  );

  $$PendingReportsTableAnnotationComposer get reportUuid {
    final $$PendingReportsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.reportUuid,
      referencedTable: $db.pendingReports,
      getReferencedColumn: (t) => t.clientUuid,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$PendingReportsTableAnnotationComposer(
            $db: $db,
            $table: $db.pendingReports,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$MediaItemsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $MediaItemsTable,
          MediaItem,
          $$MediaItemsTableFilterComposer,
          $$MediaItemsTableOrderingComposer,
          $$MediaItemsTableAnnotationComposer,
          $$MediaItemsTableCreateCompanionBuilder,
          $$MediaItemsTableUpdateCompanionBuilder,
          (MediaItem, $$MediaItemsTableReferences),
          MediaItem,
          PrefetchHooks Function({bool reportUuid})
        > {
  $$MediaItemsTableTableManager(_$AppDatabase db, $MediaItemsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$MediaItemsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$MediaItemsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$MediaItemsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> reportUuid = const Value.absent(),
                Value<String> path = const Value.absent(),
                Value<String> kind = const Value.absent(),
                Value<String> mime = const Value.absent(),
                Value<int> size = const Value.absent(),
                Value<String> sha256 = const Value.absent(),
                Value<String?> uploadUrl = const Value.absent(),
                Value<int> uploadOffset = const Value.absent(),
                Value<String> state = const Value.absent(),
                Value<int> attempts = const Value.absent(),
                Value<String?> lastError = const Value.absent(),
                Value<DateTime?> nextAttemptAt = const Value.absent(),
              }) => MediaItemsCompanion(
                id: id,
                reportUuid: reportUuid,
                path: path,
                kind: kind,
                mime: mime,
                size: size,
                sha256: sha256,
                uploadUrl: uploadUrl,
                uploadOffset: uploadOffset,
                state: state,
                attempts: attempts,
                lastError: lastError,
                nextAttemptAt: nextAttemptAt,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String reportUuid,
                required String path,
                required String kind,
                required String mime,
                required int size,
                required String sha256,
                Value<String?> uploadUrl = const Value.absent(),
                Value<int> uploadOffset = const Value.absent(),
                Value<String> state = const Value.absent(),
                Value<int> attempts = const Value.absent(),
                Value<String?> lastError = const Value.absent(),
                Value<DateTime?> nextAttemptAt = const Value.absent(),
              }) => MediaItemsCompanion.insert(
                id: id,
                reportUuid: reportUuid,
                path: path,
                kind: kind,
                mime: mime,
                size: size,
                sha256: sha256,
                uploadUrl: uploadUrl,
                uploadOffset: uploadOffset,
                state: state,
                attempts: attempts,
                lastError: lastError,
                nextAttemptAt: nextAttemptAt,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$MediaItemsTable, MediaItem>(table),
                  $$MediaItemsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({reportUuid = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (reportUuid) {
                      state = state.withJoin(
                        currentTable: table,
                        currentColumn: table.reportUuid,
                        referencedTable: $$MediaItemsTableReferences
                            ._reportUuidTable(db),
                        referencedColumn: $$MediaItemsTableReferences
                            ._reportUuidTable(db)
                            .clientUuid,
                      ) as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$MediaItemsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $MediaItemsTable,
      MediaItem,
      $$MediaItemsTableFilterComposer,
      $$MediaItemsTableOrderingComposer,
      $$MediaItemsTableAnnotationComposer,
      $$MediaItemsTableCreateCompanionBuilder,
      $$MediaItemsTableUpdateCompanionBuilder,
      (MediaItem, $$MediaItemsTableReferences),
      MediaItem,
      PrefetchHooks Function({bool reportUuid})
    >;
typedef $$EmergencyContactsTableCreateCompanionBuilder =
    EmergencyContactsCompanion Function({
      Value<int> id,
      required String name,
      required String phone,
      Value<String> groups,
      Value<String?> linkId,
      Value<int> position,
      required DateTime createdAt,
    });
typedef $$EmergencyContactsTableUpdateCompanionBuilder =
    EmergencyContactsCompanion Function({
      Value<int> id,
      Value<String> name,
      Value<String> phone,
      Value<String> groups,
      Value<String?> linkId,
      Value<int> position,
      Value<DateTime> createdAt,
    });

class $$EmergencyContactsTableFilterComposer
    extends Composer<_$AppDatabase, $EmergencyContactsTable> {
  $$EmergencyContactsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get phone => $composableBuilder(
    column: $table.phone,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get groups => $composableBuilder(
    column: $table.groups,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get linkId => $composableBuilder(
    column: $table.linkId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get position => $composableBuilder(
    column: $table.position,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );
}

class $$EmergencyContactsTableOrderingComposer
    extends Composer<_$AppDatabase, $EmergencyContactsTable> {
  $$EmergencyContactsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get phone => $composableBuilder(
    column: $table.phone,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get groups => $composableBuilder(
    column: $table.groups,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get linkId => $composableBuilder(
    column: $table.linkId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get position => $composableBuilder(
    column: $table.position,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$EmergencyContactsTableAnnotationComposer
    extends Composer<_$AppDatabase, $EmergencyContactsTable> {
  $$EmergencyContactsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get name =>
      $composableBuilder(column: $table.name, builder: (column) => column);

  GeneratedColumn<String> get phone =>
      $composableBuilder(column: $table.phone, builder: (column) => column);

  GeneratedColumn<String> get groups =>
      $composableBuilder(column: $table.groups, builder: (column) => column);

  GeneratedColumn<String> get linkId =>
      $composableBuilder(column: $table.linkId, builder: (column) => column);

  GeneratedColumn<int> get position =>
      $composableBuilder(column: $table.position, builder: (column) => column);

  GeneratedColumn<DateTime> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);
}

class $$EmergencyContactsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $EmergencyContactsTable,
          EmergencyContact,
          $$EmergencyContactsTableFilterComposer,
          $$EmergencyContactsTableOrderingComposer,
          $$EmergencyContactsTableAnnotationComposer,
          $$EmergencyContactsTableCreateCompanionBuilder,
          $$EmergencyContactsTableUpdateCompanionBuilder,
          (
            EmergencyContact,
            BaseReferences<
              _$AppDatabase,
              $EmergencyContactsTable,
              EmergencyContact
            >,
          ),
          EmergencyContact,
          PrefetchHooks Function()
        > {
  $$EmergencyContactsTableTableManager(
    _$AppDatabase db,
    $EmergencyContactsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$EmergencyContactsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$EmergencyContactsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$EmergencyContactsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> name = const Value.absent(),
                Value<String> phone = const Value.absent(),
                Value<String> groups = const Value.absent(),
                Value<String?> linkId = const Value.absent(),
                Value<int> position = const Value.absent(),
                Value<DateTime> createdAt = const Value.absent(),
              }) => EmergencyContactsCompanion(
                id: id,
                name: name,
                phone: phone,
                groups: groups,
                linkId: linkId,
                position: position,
                createdAt: createdAt,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String name,
                required String phone,
                Value<String> groups = const Value.absent(),
                Value<String?> linkId = const Value.absent(),
                Value<int> position = const Value.absent(),
                required DateTime createdAt,
              }) => EmergencyContactsCompanion.insert(
                id: id,
                name: name,
                phone: phone,
                groups: groups,
                linkId: linkId,
                position: position,
                createdAt: createdAt,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$EmergencyContactsTable, EmergencyContact>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $EmergencyContactsTable,
                    EmergencyContact
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$EmergencyContactsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $EmergencyContactsTable,
      EmergencyContact,
      $$EmergencyContactsTableFilterComposer,
      $$EmergencyContactsTableOrderingComposer,
      $$EmergencyContactsTableAnnotationComposer,
      $$EmergencyContactsTableCreateCompanionBuilder,
      $$EmergencyContactsTableUpdateCompanionBuilder,
      (
        EmergencyContact,
        BaseReferences<
          _$AppDatabase,
          $EmergencyContactsTable,
          EmergencyContact
        >,
      ),
      EmergencyContact,
      PrefetchHooks Function()
    >;
typedef $$ContactGroupsTableCreateCompanionBuilder =
    ContactGroupsCompanion Function({
      Value<int> id,
      required String name,
      Value<int> position,
    });
typedef $$ContactGroupsTableUpdateCompanionBuilder =
    ContactGroupsCompanion Function({
      Value<int> id,
      Value<String> name,
      Value<int> position,
    });

class $$ContactGroupsTableFilterComposer
    extends Composer<_$AppDatabase, $ContactGroupsTable> {
  $$ContactGroupsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get position => $composableBuilder(
    column: $table.position,
    builder: (column) => ColumnFilters(column),
  );
}

class $$ContactGroupsTableOrderingComposer
    extends Composer<_$AppDatabase, $ContactGroupsTable> {
  $$ContactGroupsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get position => $composableBuilder(
    column: $table.position,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$ContactGroupsTableAnnotationComposer
    extends Composer<_$AppDatabase, $ContactGroupsTable> {
  $$ContactGroupsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get name =>
      $composableBuilder(column: $table.name, builder: (column) => column);

  GeneratedColumn<int> get position =>
      $composableBuilder(column: $table.position, builder: (column) => column);
}

class $$ContactGroupsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $ContactGroupsTable,
          ContactGroup,
          $$ContactGroupsTableFilterComposer,
          $$ContactGroupsTableOrderingComposer,
          $$ContactGroupsTableAnnotationComposer,
          $$ContactGroupsTableCreateCompanionBuilder,
          $$ContactGroupsTableUpdateCompanionBuilder,
          (
            ContactGroup,
            BaseReferences<_$AppDatabase, $ContactGroupsTable, ContactGroup>,
          ),
          ContactGroup,
          PrefetchHooks Function()
        > {
  $$ContactGroupsTableTableManager(_$AppDatabase db, $ContactGroupsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ContactGroupsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ContactGroupsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ContactGroupsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<int> id = const Value.absent(),
            Value<String> name = const Value.absent(),
            Value<int> position = const Value.absent(),
          }) => ContactGroupsCompanion(id: id, name: name, position: position),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String name,
                Value<int> position = const Value.absent(),
              }) => ContactGroupsCompanion.insert(
                id: id,
                name: name,
                position: position,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$ContactGroupsTable, ContactGroup>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $ContactGroupsTable,
                    ContactGroup
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$ContactGroupsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $ContactGroupsTable,
      ContactGroup,
      $$ContactGroupsTableFilterComposer,
      $$ContactGroupsTableOrderingComposer,
      $$ContactGroupsTableAnnotationComposer,
      $$ContactGroupsTableCreateCompanionBuilder,
      $$ContactGroupsTableUpdateCompanionBuilder,
      (
        ContactGroup,
        BaseReferences<_$AppDatabase, $ContactGroupsTable, ContactGroup>,
      ),
      ContactGroup,
      PrefetchHooks Function()
    >;
typedef $$SafetyAlertHistoryTableCreateCompanionBuilder =
    SafetyAlertHistoryCompanion Function({
      Value<int> id,
      required String kind,
      required DateTime at,
      Value<String> channels,
      Value<int> recipients,
      Value<String?> serverId,
      required String status,
    });
typedef $$SafetyAlertHistoryTableUpdateCompanionBuilder =
    SafetyAlertHistoryCompanion Function({
      Value<int> id,
      Value<String> kind,
      Value<DateTime> at,
      Value<String> channels,
      Value<int> recipients,
      Value<String?> serverId,
      Value<String> status,
    });

class $$SafetyAlertHistoryTableFilterComposer
    extends Composer<_$AppDatabase, $SafetyAlertHistoryTable> {
  $$SafetyAlertHistoryTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get at => $composableBuilder(
    column: $table.at,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get channels => $composableBuilder(
    column: $table.channels,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get recipients => $composableBuilder(
    column: $table.recipients,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get serverId => $composableBuilder(
    column: $table.serverId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnFilters(column),
  );
}

class $$SafetyAlertHistoryTableOrderingComposer
    extends Composer<_$AppDatabase, $SafetyAlertHistoryTable> {
  $$SafetyAlertHistoryTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get at => $composableBuilder(
    column: $table.at,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get channels => $composableBuilder(
    column: $table.channels,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get recipients => $composableBuilder(
    column: $table.recipients,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get serverId => $composableBuilder(
    column: $table.serverId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$SafetyAlertHistoryTableAnnotationComposer
    extends Composer<_$AppDatabase, $SafetyAlertHistoryTable> {
  $$SafetyAlertHistoryTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get kind =>
      $composableBuilder(column: $table.kind, builder: (column) => column);

  GeneratedColumn<DateTime> get at =>
      $composableBuilder(column: $table.at, builder: (column) => column);

  GeneratedColumn<String> get channels =>
      $composableBuilder(column: $table.channels, builder: (column) => column);

  GeneratedColumn<int> get recipients => $composableBuilder(
    column: $table.recipients,
    builder: (column) => column,
  );

  GeneratedColumn<String> get serverId =>
      $composableBuilder(column: $table.serverId, builder: (column) => column);

  GeneratedColumn<String> get status =>
      $composableBuilder(column: $table.status, builder: (column) => column);
}

class $$SafetyAlertHistoryTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $SafetyAlertHistoryTable,
          SafetyAlertEntry,
          $$SafetyAlertHistoryTableFilterComposer,
          $$SafetyAlertHistoryTableOrderingComposer,
          $$SafetyAlertHistoryTableAnnotationComposer,
          $$SafetyAlertHistoryTableCreateCompanionBuilder,
          $$SafetyAlertHistoryTableUpdateCompanionBuilder,
          (
            SafetyAlertEntry,
            BaseReferences<
              _$AppDatabase,
              $SafetyAlertHistoryTable,
              SafetyAlertEntry
            >,
          ),
          SafetyAlertEntry,
          PrefetchHooks Function()
        > {
  $$SafetyAlertHistoryTableTableManager(
    _$AppDatabase db,
    $SafetyAlertHistoryTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SafetyAlertHistoryTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SafetyAlertHistoryTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SafetyAlertHistoryTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> kind = const Value.absent(),
                Value<DateTime> at = const Value.absent(),
                Value<String> channels = const Value.absent(),
                Value<int> recipients = const Value.absent(),
                Value<String?> serverId = const Value.absent(),
                Value<String> status = const Value.absent(),
              }) => SafetyAlertHistoryCompanion(
                id: id,
                kind: kind,
                at: at,
                channels: channels,
                recipients: recipients,
                serverId: serverId,
                status: status,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String kind,
                required DateTime at,
                Value<String> channels = const Value.absent(),
                Value<int> recipients = const Value.absent(),
                Value<String?> serverId = const Value.absent(),
                required String status,
              }) => SafetyAlertHistoryCompanion.insert(
                id: id,
                kind: kind,
                at: at,
                channels: channels,
                recipients: recipients,
                serverId: serverId,
                status: status,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$SafetyAlertHistoryTable, SafetyAlertEntry>(
                    table,
                  ),
                  BaseReferences<
                    _$AppDatabase,
                    $SafetyAlertHistoryTable,
                    SafetyAlertEntry
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$SafetyAlertHistoryTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $SafetyAlertHistoryTable,
      SafetyAlertEntry,
      $$SafetyAlertHistoryTableFilterComposer,
      $$SafetyAlertHistoryTableOrderingComposer,
      $$SafetyAlertHistoryTableAnnotationComposer,
      $$SafetyAlertHistoryTableCreateCompanionBuilder,
      $$SafetyAlertHistoryTableUpdateCompanionBuilder,
      (
        SafetyAlertEntry,
        BaseReferences<
          _$AppDatabase,
          $SafetyAlertHistoryTable,
          SafetyAlertEntry
        >,
      ),
      SafetyAlertEntry,
      PrefetchHooks Function()
    >;
typedef $$MedicalProfilesTableCreateCompanionBuilder =
    MedicalProfilesCompanion Function({
      Value<int> id,
      required String data,
      required String consentVersion,
      required DateTime consentAt,
      Value<bool> locked,
      required DateTime updatedAt,
    });
typedef $$MedicalProfilesTableUpdateCompanionBuilder =
    MedicalProfilesCompanion Function({
      Value<int> id,
      Value<String> data,
      Value<String> consentVersion,
      Value<DateTime> consentAt,
      Value<bool> locked,
      Value<DateTime> updatedAt,
    });

class $$MedicalProfilesTableFilterComposer
    extends Composer<_$AppDatabase, $MedicalProfilesTable> {
  $$MedicalProfilesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get data => $composableBuilder(
    column: $table.data,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get consentVersion => $composableBuilder(
    column: $table.consentVersion,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get consentAt => $composableBuilder(
    column: $table.consentAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get locked => $composableBuilder(
    column: $table.locked,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnFilters(column),
  );
}

class $$MedicalProfilesTableOrderingComposer
    extends Composer<_$AppDatabase, $MedicalProfilesTable> {
  $$MedicalProfilesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get data => $composableBuilder(
    column: $table.data,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get consentVersion => $composableBuilder(
    column: $table.consentVersion,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get consentAt => $composableBuilder(
    column: $table.consentAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get locked => $composableBuilder(
    column: $table.locked,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$MedicalProfilesTableAnnotationComposer
    extends Composer<_$AppDatabase, $MedicalProfilesTable> {
  $$MedicalProfilesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get data =>
      $composableBuilder(column: $table.data, builder: (column) => column);

  GeneratedColumn<String> get consentVersion => $composableBuilder(
    column: $table.consentVersion,
    builder: (column) => column,
  );

  GeneratedColumn<DateTime> get consentAt =>
      $composableBuilder(column: $table.consentAt, builder: (column) => column);

  GeneratedColumn<bool> get locked =>
      $composableBuilder(column: $table.locked, builder: (column) => column);

  GeneratedColumn<DateTime> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);
}

class $$MedicalProfilesTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $MedicalProfilesTable,
          MedicalProfileRow,
          $$MedicalProfilesTableFilterComposer,
          $$MedicalProfilesTableOrderingComposer,
          $$MedicalProfilesTableAnnotationComposer,
          $$MedicalProfilesTableCreateCompanionBuilder,
          $$MedicalProfilesTableUpdateCompanionBuilder,
          (
            MedicalProfileRow,
            BaseReferences<
              _$AppDatabase,
              $MedicalProfilesTable,
              MedicalProfileRow
            >,
          ),
          MedicalProfileRow,
          PrefetchHooks Function()
        > {
  $$MedicalProfilesTableTableManager(
    _$AppDatabase db,
    $MedicalProfilesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$MedicalProfilesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$MedicalProfilesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$MedicalProfilesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> data = const Value.absent(),
                Value<String> consentVersion = const Value.absent(),
                Value<DateTime> consentAt = const Value.absent(),
                Value<bool> locked = const Value.absent(),
                Value<DateTime> updatedAt = const Value.absent(),
              }) => MedicalProfilesCompanion(
                id: id,
                data: data,
                consentVersion: consentVersion,
                consentAt: consentAt,
                locked: locked,
                updatedAt: updatedAt,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String data,
                required String consentVersion,
                required DateTime consentAt,
                Value<bool> locked = const Value.absent(),
                required DateTime updatedAt,
              }) => MedicalProfilesCompanion.insert(
                id: id,
                data: data,
                consentVersion: consentVersion,
                consentAt: consentAt,
                locked: locked,
                updatedAt: updatedAt,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$MedicalProfilesTable, MedicalProfileRow>(table),
                  BaseReferences<
                    _$AppDatabase,
                    $MedicalProfilesTable,
                    MedicalProfileRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$MedicalProfilesTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $MedicalProfilesTable,
      MedicalProfileRow,
      $$MedicalProfilesTableFilterComposer,
      $$MedicalProfilesTableOrderingComposer,
      $$MedicalProfilesTableAnnotationComposer,
      $$MedicalProfilesTableCreateCompanionBuilder,
      $$MedicalProfilesTableUpdateCompanionBuilder,
      (
        MedicalProfileRow,
        BaseReferences<_$AppDatabase, $MedicalProfilesTable, MedicalProfileRow>,
      ),
      MedicalProfileRow,
      PrefetchHooks Function()
    >;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$PendingReportsTableTableManager get pendingReports =>
      $$PendingReportsTableTableManager(_db, _db.pendingReports);
  $$MediaItemsTableTableManager get mediaItems =>
      $$MediaItemsTableTableManager(_db, _db.mediaItems);
  $$EmergencyContactsTableTableManager get emergencyContacts =>
      $$EmergencyContactsTableTableManager(_db, _db.emergencyContacts);
  $$ContactGroupsTableTableManager get contactGroups =>
      $$ContactGroupsTableTableManager(_db, _db.contactGroups);
  $$SafetyAlertHistoryTableTableManager get safetyAlertHistory =>
      $$SafetyAlertHistoryTableTableManager(_db, _db.safetyAlertHistory);
  $$MedicalProfilesTableTableManager get medicalProfiles =>
      $$MedicalProfilesTableTableManager(_db, _db.medicalProfiles);
}
