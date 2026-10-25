// Labels of the institution codes (phase P2a): the same words as the portal and the dashboard, one switch per
// list so an unknown code from a newer server still shows something.
import '../../l10n/app_localizations.dart';

String orgKindText(AppLocalizations l10n, String wire) => switch (wire) {
  'health' => l10n.orgKindHealth,
  'industrial' => l10n.orgKindIndustrial,
  'energy' => l10n.orgKindEnergy,
  'tourism' => l10n.orgKindTourism,
  'education' => l10n.orgKindEducation,
  'social_care' => l10n.orgKindSocialCare,
  'public_admin' => l10n.orgKindPublicAdmin,
  'culture_sport' => l10n.orgKindCultureSport,
  'commercial' => l10n.orgKindCommercial,
  'transport' => l10n.orgKindTransport,
  'religious' => l10n.orgKindReligious,
  'other' => l10n.orgKindOther,
  _ => l10n.orgKindOther,
};

String kindFieldText(AppLocalizations l10n, String wire) => switch (wire) {
  'reception_phone' => l10n.kindFieldReceptionPhone,
  'beds' => l10n.kindFieldBeds,
  'icu' => l10n.kindFieldIcu,
  'oxygen_hours' => l10n.kindFieldOxygenHours,
  'generator' => l10n.kindFieldGenerator,
  'helipad' => l10n.kindFieldHelipad,
  'non_ambulatory' => l10n.kindFieldNonAmbulatory,
  'workers_per_shift' => l10n.kindFieldWorkersPerShift,
  'self_fire_fighting' => l10n.kindFieldSelfFireFighting,
  'tanks' => l10n.kindFieldTanks,
  'fuel_types' => l10n.kindFieldFuelTypes,
  'storage_m3' => l10n.kindFieldStorageM3,
  'shutoff_valves' => l10n.kindFieldShutoffValves,
  'rooms' => l10n.kindFieldRooms,
  'guest_languages' => l10n.kindFieldGuestLanguages,
  'pool_or_beach' => l10n.kindFieldPoolOrBeach,
  'occupancy_pct' => l10n.kindFieldOccupancyPct,
  'students' => l10n.kindFieldStudents,
  'age_range' => l10n.kindFieldAgeRange,
  'boarding' => l10n.kindFieldBoarding,
  'students_special_needs' => l10n.kindFieldStudentsSpecialNeeds,
  'residents' => l10n.kindFieldResidents,
  'night_watch' => l10n.kindFieldNightWatch,
  'staff' => l10n.kindFieldStaff,
  'archive' => l10n.kindFieldArchive,
  'seated_capacity' => l10n.kindFieldSeatedCapacity,
  'stands' => l10n.kindFieldStands,
  'shops' => l10n.kindFieldShops,
  'underground_parking' => l10n.kindFieldUndergroundParking,
  'daily_passengers' => l10n.kindFieldDailyPassengers,
  'emergency_exits' => l10n.kindFieldEmergencyExits,
  'peak_times' => l10n.kindFieldPeakTimes,
  _ => wire,
};

String visibilityText(AppLocalizations l10n, String wire) => switch (wire) {
  'public' => l10n.orgVisibilityPublic,
  'org_office' => l10n.orgVisibilityOrgOffice,
  'incident' => l10n.orgVisibilityIncident,
  _ => wire,
};

String requirementText(AppLocalizations l10n, String wire) => switch (wire) {
  'safety_file' => l10n.orgReqSafetyFile,
  'safety_plan' => l10n.orgReqSafetyPlan,
  'safety_team' => l10n.orgReqSafetyTeam,
  'training' => l10n.orgReqTraining,
  'hazmat_sds' => l10n.orgReqHazmatSds,
  'equipment' => l10n.orgReqEquipment,
  'evacuation_points' => l10n.orgReqEvacuationPoints,
  _ => wire,
};

String equipmentKindText(AppLocalizations l10n, String wire) => switch (wire) {
  'extinguisher' => l10n.orgEquipExtinguisher,
  'fire_hose_reel' => l10n.orgEquipFireHoseReel,
  'sprinkler' => l10n.orgEquipSprinkler,
  'smoke_detector' => l10n.orgEquipSmokeDetector,
  'alarm_panel' => l10n.orgEquipAlarmPanel,
  'emergency_lighting' => l10n.orgEquipEmergencyLighting,
  'fire_door' => l10n.orgEquipFireDoor,
  'other' => l10n.orgEquipOther,
  _ => l10n.orgEquipOther,
};

String featureKindText(AppLocalizations l10n, String wire) => switch (wire) {
  'evacuation_point' => l10n.orgFeatureEvacuationPoint,
  'water_point' => l10n.orgFeatureWaterPoint,
  'alarm' => l10n.orgFeatureAlarm,
  _ => wire,
};

String orgRoleText(AppLocalizations l10n, String wire) => switch (wire) {
  'admin' => l10n.orgRoleAdmin,
  'editor' => l10n.orgRoleEditor,
  'member' => l10n.orgRoleMember,
  _ => wire,
};

String certificateStatusText(AppLocalizations l10n, String wire) =>
    switch (wire) {
      'draft' => l10n.orgCertDraft,
      'submitted' => l10n.orgCertSubmitted,
      'approved' => l10n.orgCertApproved,
      'rejected' => l10n.orgCertRejected,
      'revoked' => l10n.orgCertRevoked,
      _ => wire,
    };

String orgAlertText(AppLocalizations l10n, String wire) => switch (wire) {
  'training_expired' => l10n.orgAlertTrainingExpired,
  'training_expiring' => l10n.orgAlertTrainingExpiring,
  'maintenance_overdue' => l10n.orgAlertMaintenanceOverdue,
  'maintenance_due_soon' => l10n.orgAlertMaintenanceDueSoon,
  'certificate_expiring' => l10n.orgAlertCertificateExpiring,
  'certificate_expired' => l10n.orgAlertCertificateExpired,
  'certificate_needs_update' => l10n.orgAlertCertificateNeedsUpdate,
  'visit_scheduled' => l10n.orgAlertVisitScheduled,
  'reservation_due_soon' => l10n.orgAlertReservationDueSoon,
  'reservation_overdue' => l10n.orgAlertReservationOverdue,
  'prevention_expiring' => l10n.orgAlertPreventionExpiring,
  'prevention_expired' => l10n.orgAlertPreventionExpired,
  _ => wire,
};

/// A section of the comparison with the approved certificate (phase P3a §3.4).
String certificateSectionText(AppLocalizations l10n, String wire) =>
    switch (wire) {
      'identity' => l10n.orgCertSectionIdentity,
      'building' => l10n.orgCertSectionBuilding,
      'classification' => l10n.orgCertSectionClassification,
      'hazmat' => l10n.orgCertSectionHazmat,
      'documents' => l10n.orgCertSectionDocuments,
      'safety_team' => l10n.orgCertSectionSafetyTeam,
      'evacuation' => l10n.orgCertSectionEvacuation,
      _ => wire,
    };

// ---- Phase P3b: prevention visits ----

String visitOriginText(AppLocalizations l10n, String wire) =>
    wire == 'office' ? l10n.orgVisitOriginOffice : l10n.orgVisitOriginRequest;

String visitStatusText(AppLocalizations l10n, String wire) => switch (wire) {
  'requested' => l10n.orgVisitStatusRequested,
  'scheduled' => l10n.orgVisitStatusScheduled,
  'inspected' => l10n.orgVisitStatusInspected,
  'decided' => l10n.orgVisitStatusDecided,
  'cancelled' => l10n.orgVisitStatusCancelled,
  _ => wire,
};

String visitDecisionText(AppLocalizations l10n, String wire) => switch (wire) {
  'approved' => l10n.orgVisitDecisionApproved,
  'approved_with_reservations' => l10n.orgVisitDecisionReservations,
  'refused' => l10n.orgVisitDecisionRefused,
  _ => wire,
};

String reservationStateText(AppLocalizations l10n, String wire) =>
    switch (wire) {
      'open' => l10n.orgReservationOpen,
      'responded' => l10n.orgReservationResponded,
      'overdue' => l10n.orgReservationOverdue,
      'lifted' => l10n.orgReservationLifted,
      _ => wire,
    };

String certificateKindText(AppLocalizations l10n, String wire) =>
    wire == 'prevention' ? l10n.orgCertKindPrevention : l10n.orgCertKindSafety;
