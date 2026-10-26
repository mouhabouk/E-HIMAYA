import 'package:drift/drift.dart' show Value;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/db/app_database.dart';
import '../../core/db/open_database.dart';
import '../../core/platform/device_services.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'safety_models.dart';
import 'safety_providers.dart';
import 'safety_widgets.dart';

/// Addition 5: up to 10 emergency contacts, chosen with the system contact picker (no contacts
/// permission, nothing uploaded) or typed in, sorted into the user's own groups.
class EmergencyContactsScreen extends ConsumerWidget {
  const EmergencyContactsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final contacts = ref.watch(emergencyContactsProvider).value ?? const [];
    final groups = ref.watch(contactGroupsProvider).value ?? const [];
    final linked = linkedContacts(
      contacts,
      ref.watch(safetyLinksProvider).value ?? const [],
    );
    final full = contacts.length >= SafetyRules.maxContacts;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyContactsTitle),
        actions: const [StandardAppBarActions()],
      ),
      floatingActionButton: full
          ? null
          : FloatingActionButton.extended(
              key: const Key('contacts-add'),
              onPressed: () => _add(context, ref),
              icon: const Icon(Icons.person_add),
              label: Text(l10n.safetyContactAdd),
            ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
          children: [
            Text(l10n.safetyContactsIntro),
            const SizedBox(height: 4),
            Text(l10n.safetyContactsPrivacy, style: theme.textTheme.bodySmall),
            if (full) ...[
              const SizedBox(height: 8),
              Text(
                l10n.safetyContactsFull(SafetyRules.maxContacts),
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ],
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: Text(
                    l10n.safetyGroupsTitle,
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                Flexible(
                  child: TextButton.icon(
                    key: const Key('groups-add'),
                    onPressed: () => _addGroup(context, ref),
                    icon: const Icon(Icons.add),
                    label: Text(l10n.safetyGroupAdd),
                  ),
                ),
              ],
            ),
            if (groups.isEmpty)
              Text(l10n.safetyGroupsEmpty, style: theme.textTheme.bodySmall)
            else
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: [
                  for (final g in groups)
                    InputChip(
                      key: Key('group-${g.id}'),
                      label: Text(g.name),
                      onDeleted: () => _deleteGroup(context, ref, g),
                      deleteButtonTooltipMessage: l10n.safetyDelete,
                    ),
                ],
              ),
            const Divider(height: 32),
            if (contacts.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text(
                  l10n.safetyContactsEmpty,
                  textAlign: TextAlign.center,
                ),
              ),
            for (final c in contacts)
              Card(
                child: ListTile(
                  key: Key('contact-${c.id}'),
                  leading: CircleAvatar(
                    child: Text(c.name.characters.first.toUpperCase()),
                  ),
                  title: Text(c.name),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(c.phone, textDirection: TextDirection.ltr),
                      if (linked.containsKey(c.id))
                        Text(
                          l10n.safetyContactLinked,
                          style: TextStyle(color: theme.colorScheme.primary),
                        ),
                      if (groups.any((g) => inGroup(c.groups, g.id)))
                        Text(
                          groups
                              .where((g) => inGroup(c.groups, g.id))
                              .map((g) => g.name)
                              .join(' · '),
                          style: theme.textTheme.bodySmall,
                        ),
                    ],
                  ),
                  isThreeLine: true,
                  trailing: PopupMenuButton<String>(
                    key: Key('contact-menu-${c.id}'),
                    onSelected: (action) => switch (action) {
                      'groups' => _editGroups(context, ref, c, groups),
                      'edit' => _edit(context, ref, c),
                      _ => _delete(context, ref, c),
                    },
                    itemBuilder: (_) => [
                      if (groups.isNotEmpty)
                        PopupMenuItem(
                          value: 'groups',
                          child: Text(l10n.safetyContactGroups),
                        ),
                      PopupMenuItem(
                        value: 'edit',
                        child: Text(l10n.safetyEdit),
                      ),
                      PopupMenuItem(
                        value: 'delete',
                        child: Text(l10n.safetyDelete),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final choice = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              key: const Key('contacts-pick'),
              leading: const Icon(Icons.contact_phone),
              title: Text(l10n.safetyContactPick),
              subtitle: Text(l10n.safetyContactPickHint),
              onTap: () => Navigator.of(context).pop('pick'),
            ),
            ListTile(
              key: const Key('contacts-type'),
              leading: const Icon(Icons.dialpad),
              title: Text(l10n.safetyContactType),
              onTap: () => Navigator.of(context).pop('type'),
            ),
          ],
        ),
      ),
    );
    if (choice == null || !context.mounted) return;
    PickedContact? picked;
    if (choice == 'pick') {
      picked = await ref.read(deviceServicesProvider).pickContact();
      if (picked == null || !context.mounted) return;
    }
    final entered = await _contactDialog(
      context,
      name: picked?.name,
      phone: picked?.phone,
    );
    if (entered == null) return;
    final db = ref.read(databaseProvider);
    final all = await db.allContacts();
    if (all.length >= SafetyRules.maxContacts) return;
    if (all.any((c) => c.phone == entered.phone)) {
      if (context.mounted) showSafetySnack(context, l10n.safetyContactExists);
      return;
    }
    await db.addContact(
      EmergencyContactsCompanion.insert(
        name: entered.name,
        phone: entered.phone,
        position: Value(all.length),
        createdAt: DateTime.now(),
      ),
    );
  }

  Future<void> _edit(
    BuildContext context,
    WidgetRef ref,
    EmergencyContact c,
  ) async {
    final entered = await _contactDialog(context, name: c.name, phone: c.phone);
    if (entered == null) return;
    await ref
        .read(databaseProvider)
        .updateContact(
          c.id,
          EmergencyContactsCompanion(
            name: Value(entered.name),
            phone: Value(entered.phone),
          ),
        );
  }

  Future<void> _delete(
    BuildContext context,
    WidgetRef ref,
    EmergencyContact c,
  ) async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.safetyContactDeleteTitle(c.name)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('contact-delete-confirm'),
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(l10n.safetyDelete),
          ),
        ],
      ),
    );
    if (ok == true) await ref.read(databaseProvider).deleteContact(c.id);
  }

  Future<void> _editGroups(
    BuildContext context,
    WidgetRef ref,
    EmergencyContact c,
    List<ContactGroup> groups,
  ) async {
    final l10n = AppLocalizations.of(context);
    var value = c.groups;
    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: Text(l10n.safetyContactGroups),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final g in groups)
                CheckboxListTile(
                  key: Key('contact-group-${g.id}'),
                  value: inGroup(value, g.id),
                  title: Text(g.name),
                  onChanged: (v) =>
                      setState(() => value = withGroup(value, g.id, v == true)),
                ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(l10n.actionCancel),
            ),
            FilledButton(
              key: const Key('contact-groups-save'),
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(l10n.actionSave),
            ),
          ],
        ),
      ),
    );
    if (saved == true) {
      await ref
          .read(databaseProvider)
          .updateContact(
            c.id,
            EmergencyContactsCompanion(groups: Value(value)),
          );
    }
  }

  Future<void> _addGroup(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final controller = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.safetyGroupAdd),
        content: TextField(
          key: const Key('group-name'),
          controller: controller,
          autofocus: true,
          maxLength: 40,
          decoration: InputDecoration(
            labelText: l10n.safetyGroupName,
            hintText: l10n.safetyGroupNameHint,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('group-save'),
            onPressed: () => Navigator.of(context).pop(controller.text.trim()),
            child: Text(l10n.actionSave),
          ),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    await ref.read(databaseProvider).addGroup(name);
  }

  Future<void> _deleteGroup(
    BuildContext context,
    WidgetRef ref,
    ContactGroup g,
  ) async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.safetyGroupDeleteTitle(g.name)),
        content: Text(l10n.safetyGroupDeleteBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(l10n.safetyDelete),
          ),
        ],
      ),
    );
    if (ok == true) await ref.read(databaseProvider).deleteGroup(g.id);
  }
}

/// Name and number of a contact; the number must be one the SMS and WhatsApp apps accept.
Future<({String name, String phone})?> _contactDialog(
  BuildContext context, {
  String? name,
  String? phone,
}) async {
  final l10n = AppLocalizations.of(context);
  final nameField = TextEditingController(text: name);
  final phoneField = TextEditingController(text: phone);
  final form = GlobalKey<FormState>();
  final result = await showDialog<({String name, String phone})>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(l10n.safetyContactTitle),
      content: Form(
        key: form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              key: const Key('contact-name'),
              controller: nameField,
              maxLength: 60,
              decoration: InputDecoration(labelText: l10n.safetyContactName),
              validator: (v) => (v ?? '').trim().isEmpty
                  ? l10n.safetyContactNameRequired
                  : null,
            ),
            TextFormField(
              key: const Key('contact-phone'),
              controller: phoneField,
              keyboardType: TextInputType.phone,
              textDirection: TextDirection.ltr,
              decoration: InputDecoration(
                labelText: l10n.safetyContactPhone,
                hintText: '+216 …',
              ),
              validator: (v) => normalizeContactPhone(v ?? '') == null
                  ? l10n.validationPhone
                  : null,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l10n.actionCancel),
        ),
        FilledButton(
          key: const Key('contact-save'),
          onPressed: () {
            if (!form.currentState!.validate()) return;
            Navigator.of(context).pop((
              name: nameField.text.trim(),
              phone: normalizeContactPhone(phoneField.text)!,
            ));
          },
          child: Text(l10n.actionSave),
        ),
      ],
    ),
  );
  return result;
}
