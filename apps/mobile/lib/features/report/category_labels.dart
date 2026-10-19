import 'package:flutter/material.dart';

import '../../core/http/models.dart';
import '../../l10n/app_localizations.dart';

String categoryLabel(AppLocalizations l10n, ReportCategory c) => switch (c) {
  ReportCategory.sos => l10n.categorySos,
  ReportCategory.fire => l10n.categoryFire,
  ReportCategory.flood => l10n.categoryFlood,
  ReportCategory.trafficAccident => l10n.categoryTrafficAccident,
  ReportCategory.drowning => l10n.categoryDrowning,
  ReportCategory.landslide => l10n.categoryLandslide,
  ReportCategory.chemicalLeak => l10n.categoryChemicalLeak,
  ReportCategory.medical => l10n.categoryMedical,
  ReportCategory.other => l10n.categoryOther,
};

IconData categoryIcon(ReportCategory c) => switch (c) {
  ReportCategory.sos => Icons.sos,
  ReportCategory.fire => Icons.local_fire_department,
  ReportCategory.flood => Icons.flood,
  ReportCategory.trafficAccident => Icons.car_crash,
  ReportCategory.drowning => Icons.pool,
  ReportCategory.landslide => Icons.landslide,
  ReportCategory.chemicalLeak => Icons.science,
  ReportCategory.medical => Icons.medical_services,
  ReportCategory.other => Icons.report,
};
