"""Texts of the messages the platform sends on its own (push and e-mail), in the three app languages.

Every text is here (NFR-08: no user-facing string in the code paths). ``{…}`` placeholders are filled
with ``str.format``; values never include personal data in pushes.
"""

from typing import Literal

Lang = Literal["ar", "fr", "en"]
Localized = dict[str, str]

SIGNATURE: Localized = {
    "ar": "ء-حماية — الديوان الوطني للحماية المدنية",
    "fr": "e-Himaya — Office national de la protection civile",
    "en": "e-Himaya — National Civil Protection Office",
}

# Personal pushes (report status, volunteer call-out, one-user notification) carry no personal text: the
# push services (Google, Apple) only see this generic text; the app fetches the content over the API (A8).
PERSONAL_PUSH_TITLE: Localized = {"ar": "ء-حماية", "fr": "e-Himaya", "en": "e-Himaya"}
PERSONAL_PUSH_BODY: Localized = {
    "ar": "لديك تحديث جديد",
    "fr": "Vous avez une nouvelle mise à jour",
    "en": "You have a new update",
}


# Personal safety (phase B2): an alert from a linked contact rings on the critical channel. Still no name or place in
# the push itself: the app opens the alert over the API.
SAFETY_ALERT_TITLE: Localized = {
    "ar": "تنبيه استغاثة من أحد معارفك",
    "fr": "Alerte de détresse d'un proche",
    "en": "Distress alert from a contact",
}
SAFETY_ALERT_BODY: Localized = {
    "ar": "افتح ء-حماية لرؤية الرسالة والموقع",
    "fr": "Ouvrez e-Himaya pour voir le message et la position",
    "en": "Open e-Himaya to see the message and the location",
}

ALERT_CANCELLED_TITLE: Localized = {"ar": "رُفع التنبيه", "fr": "Alerte levée", "en": "Alert lifted"}

VOLUNTEER_DECISION_SUBJECT: dict[str, Localized] = {
    "approve": {
        "ar": "قبول طلب التطوع — ء-حماية",
        "fr": "Votre candidature de volontaire est acceptée — e-Himaya",
        "en": "Your volunteer application is approved — e-Himaya",
    },
    "reject": {
        "ar": "طلب التطوع — ء-حماية",
        "fr": "Votre candidature de volontaire — e-Himaya",
        "en": "Your volunteer application — e-Himaya",
    },
    "suspend": {
        "ar": "تعليق صفة التطوع — ء-حماية",
        "fr": "Suspension de votre statut de volontaire — e-Himaya",
        "en": "Your volunteer status is suspended — e-Himaya",
    },
    "reinstate": {
        "ar": "إعادة تفعيل صفة التطوع — ء-حماية",
        "fr": "Votre statut de volontaire est rétabli — e-Himaya",
        "en": "Your volunteer status is reinstated — e-Himaya",
    },
}
VOLUNTEER_DECISION_BODY: dict[str, Localized] = {
    "approve": {
        "ar": "مرحبا {name}،\n\nقبلت الحماية المدنية طلب تطوعك وأُدرجت في سجلاتها. يمكنك الآن تفعيل زر «جاهز» في التطبيق لتلقي الاستدعاءات القريبة منك.\n\nشكرا على التزامك.",
        "fr": "Bonjour {name},\n\nLa Protection civile a accepté votre candidature et vous a inscrit(e) dans ses registres. Vous pouvez maintenant activer « Disponible » dans l'application pour recevoir les appels proches de vous.\n\nMerci pour votre engagement.",
        "en": "Hello {name},\n\nThe Civil Protection has approved your application and added you to its registers. You can now switch on “Ready” in the app to receive call-outs near you.\n\nThank you for your commitment.",
    },
    "reject": {
        "ar": "مرحبا {name}،\n\nلم يُقبل طلب تطوعك في الوقت الحالي.\nالسبب: {reason}\n\nيمكنك تحيين طلبك وإعادة تقديمه من التطبيق.",
        "fr": "Bonjour {name},\n\nVotre candidature n'a pas été retenue pour le moment.\nMotif : {reason}\n\nVous pouvez la mettre à jour et la soumettre de nouveau depuis l'application.",
        "en": "Hello {name},\n\nYour application was not accepted for now.\nReason: {reason}\n\nYou can update it and submit it again from the app.",
    },
    "suspend": {
        "ar": "مرحبا {name}،\n\nعُلّقت صفة التطوع الخاصة بك.\nالسبب: {reason}",
        "fr": "Bonjour {name},\n\nVotre statut de volontaire est suspendu.\nMotif : {reason}",
        "en": "Hello {name},\n\nYour volunteer status is suspended.\nReason: {reason}",
    },
    "reinstate": {
        "ar": "مرحبا {name}،\n\nأُعيد تفعيل صفة التطوع الخاصة بك. يمكنك من جديد تلقي الاستدعاءات.",
        "fr": "Bonjour {name},\n\nVotre statut de volontaire est rétabli. Vous pouvez de nouveau recevoir des appels.",
        "en": "Hello {name},\n\nYour volunteer status is reinstated. You can receive call-outs again.",
    },
}

DOCTOR_DECISION_SUBJECT: dict[str, Localized] = {
    "approve": {
        "ar": "توثيق صفة الطبيب — ء-حماية",
        "fr": "Votre statut de médecin est vérifié — e-Himaya",
        "en": "Your doctor status is verified — e-Himaya",
    },
    "reject": {
        "ar": "طلب صفة الطبيب — ء-حماية",
        "fr": "Votre demande de statut de médecin — e-Himaya",
        "en": "Your doctor application — e-Himaya",
    },
    "suspend": {
        "ar": "تعليق صفة الطبيب — ء-حماية",
        "fr": "Suspension de votre statut de médecin — e-Himaya",
        "en": "Your doctor status is suspended — e-Himaya",
    },
    "reinstate": {
        "ar": "إعادة تفعيل صفة الطبيب — ء-حماية",
        "fr": "Votre statut de médecin est rétabli — e-Himaya",
        "en": "Your doctor status is reinstated — e-Himaya",
    },
}
DOCTOR_DECISION_BODY: dict[str, Localized] = {
    "approve": {
        "ar": "مرحبا {name}،\n\nتحققت الحماية المدنية من صفتك كطبيب وأُدرجت في مجموعة أطباء ولايتك. سيصلك إشعار في التطبيق عند تفعيل استقبال الملفات الطبية.\n\nشكرا على التزامك.",
        "fr": "Bonjour {name},\n\nLa Protection civile a vérifié votre statut de médecin et vous a inscrit(e) dans le groupe des médecins de votre gouvernorat. L'application vous préviendra quand la réception des dossiers médicaux sera ouverte.\n\nMerci pour votre engagement.",
        "en": "Hello {name},\n\nThe Civil Protection has verified your doctor status and added you to the doctors' group of your gouvernorat. The app will let you know when receiving medical files opens.\n\nThank you for your commitment.",
    },
    "reject": {
        "ar": "مرحبا {name}،\n\nلم يُقبل طلب صفة الطبيب في الوقت الحالي.\nالسبب: {reason}\n\nيمكنك تحيين طلبك وإعادة تقديمه من التطبيق.",
        "fr": "Bonjour {name},\n\nVotre demande de statut de médecin n'a pas été retenue pour le moment.\nMotif : {reason}\n\nVous pouvez la mettre à jour et la soumettre de nouveau depuis l'application.",
        "en": "Hello {name},\n\nYour doctor application was not accepted for now.\nReason: {reason}\n\nYou can update it and submit it again from the app.",
    },
    "suspend": {
        "ar": "مرحبا {name}،\n\nعُلّقت صفة الطبيب الخاصة بك، فلن تصلك ملفات طبية.\nالسبب: {reason}",
        "fr": "Bonjour {name},\n\nVotre statut de médecin est suspendu : vous ne recevrez plus de dossiers médicaux.\nMotif : {reason}",
        "en": "Hello {name},\n\nYour doctor status is suspended: you will not receive medical files.\nReason: {reason}",
    },
    "reinstate": {
        "ar": "مرحبا {name}،\n\nأُعيد تفعيل صفة الطبيب الخاصة بك.",
        "fr": "Bonjour {name},\n\nVotre statut de médecin est rétabli.",
        "en": "Hello {name},\n\nYour doctor status is reinstated.",
    },
}

INVITATION_SUBJECT: Localized = {
    "ar": "دعوة للانضمام إلى {org} على ء-حماية",
    "fr": "Invitation à rejoindre {org} sur e-Himaya",
    "en": "Invitation to join {org} on e-Himaya",
}
INVITATION_BODY: Localized = {
    "ar": "مرحبا،\n\nدعاك {inviter} للانضمام إلى فضاء المؤسسة «{org}» على بوابة ء-حماية.\nلقبول الدعوة افتح الرابط التالي قبل {expires}:\n{link}",
    "fr": "Bonjour,\n\n{inviter} vous invite à rejoindre l'espace de l'établissement « {org} » sur le portail e-Himaya.\nPour accepter, ouvrez ce lien avant le {expires} :\n{link}",
    "en": "Hello,\n\n{inviter} invites you to join the space of “{org}” on the e-Himaya portal.\nTo accept, open this link before {expires}:\n{link}",
}

DIGEST_SUBJECT: Localized = {
    "ar": "تنبيهات السلامة لمؤسستكم {org}",
    "fr": "Alertes de sécurité de votre établissement {org}",
    "en": "Safety alerts for your institution {org}",
}
DIGEST_BODY: Localized = {
    "ar": "مرحبا،\n\nتحتاج المعطيات التالية في ملف السلامة لمؤسستكم «{org}» إلى تحيين:\n\n{items}\n\nيمكنكم تحيينها من البوابة: {link}",
    "fr": "Bonjour,\n\nLes éléments suivants du dossier de sécurité de votre établissement « {org} » sont à mettre à jour :\n\n{items}\n\nMise à jour depuis le portail : {link}",
    "en": "Hello,\n\nThe following items of the safety file of “{org}” need updating:\n\n{items}\n\nUpdate them from the portal: {link}",
}
DIGEST_ITEM: dict[str, Localized] = {
    "training_expired": {
        "ar": "انتهت صلاحية تكوين عضو فريق السلامة: {name}",
        "fr": "Formation expirée du membre de l'équipe de sécurité : {name}",
        "en": "Expired safety training of team member: {name}",
    },
    "training_expiring": {
        "ar": "تقترب نهاية صلاحية تكوين عضو فريق السلامة: {name}",
        "fr": "Formation bientôt expirée du membre de l'équipe de sécurité : {name}",
        "en": "Safety training about to expire for team member: {name}",
    },
    "maintenance_overdue": {
        "ar": "صيانة متأخرة لأداة السلامة: {name}",
        "fr": "Maintenance en retard de l'équipement : {name}",
        "en": "Overdue maintenance of equipment: {name}",
    },
    "maintenance_due_soon": {
        "ar": "تقترب الصيانة الدورية لأداة السلامة: {name}",
        "fr": "Maintenance bientôt due de l'équipement : {name}",
        "en": "Maintenance due soon for equipment: {name}",
    },
}


def pick(text: Localized, lang: str) -> str:
    return text.get(lang) or text["ar"]


def fill(text: Localized, **values: object) -> Localized:
    return {lang: value.format(**values) for lang, value in text.items()}


def multilingual(text: Localized) -> str:
    """One e-mail body in the three languages, for recipients whose language is unknown."""
    return "\n\n— — —\n\n".join(text[lang] for lang in ("ar", "fr", "en") if text.get(lang))
