/** The nine simulated cards seeded by migration 0100 (OS2), as `GET /api/v1/staff/call-cards` returns them. [SIM] */
import type { CallCard } from "../lib/callCards";

export const SIM_CALL_CARDS: CallCard[] = [
  {
    "id": "cc-medical",
    "category": "medical",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "إسعاف: شخص مريض أو مصاب",
      "base_band": "normal",
      "base_means": [
        "سيارة إسعاف"
      ],
      "questions": [
        {
          "id": "conscious",
          "text": "هل المريض فاقد للوعي؟",
          "help": "هل يجيب إن ناديته أو هززت كتفه؟",
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "فاقد للوعي",
              "band": "high",
              "flag": "حياة في خطر",
              "means": [],
              "instruction": null,
              "lives": true,
              "injured": false
            }
          }
        },
        {
          "id": "breathing",
          "text": "هل يتنفس تنفسا طبيعيا؟",
          "help": "انظر إلى صدره 10 ثوان",
          "key": true,
          "when": {
            "question": "conscious",
            "answer": "yes"
          },
          "effects": {
            "no": {
              "why": "فاقد للوعي ولا يتنفس طبيعيا",
              "band": "critical",
              "flag": "توقف قلبي محتمل",
              "means": [
                "طلب SMUR عبر 190 (طبيب على متن الإسعاف)"
              ],
              "instruction": "cpr",
              "lives": true,
              "injured": false
            },
            "yes": {
              "why": "يتنفس: وضعية الأمان",
              "band": null,
              "flag": null,
              "means": [],
              "instruction": "recovery",
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "chest",
          "text": "هل يشكو من ألم في الصدر أو ضيق في التنفس؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "ألم صدري أو ضيق تنفس",
              "band": "high",
              "flag": null,
              "means": [
                "طلب SMUR عبر 190 (طبيب على متن الإسعاف)"
              ],
              "instruction": null,
              "lives": true,
              "injured": false
            }
          }
        },
        {
          "id": "bleeding",
          "text": "هل يوجد نزيف قوي لا يتوقف؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "نزيف قوي",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [],
              "instruction": "bleeding",
              "lives": true,
              "injured": true
            }
          }
        },
        {
          "id": "child",
          "text": "هل المريض رضيع أو طفل دون 8 سنوات؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "طفل: تُجهَّز معدات الأطفال",
              "band": null,
              "flag": null,
              "means": [],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "labour",
          "text": "هل هي امرأة حامل في المخاض؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "ولادة جارية",
              "band": "high",
              "flag": null,
              "means": [],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        }
      ],
      "instructions": {
        "cpr": {
          "title": "الإنعاش القلبي بالهاتف",
          "steps": [
            "ضع الهاتف على مكبّر الصوت وابقَ مع المريض.",
            "مدّده على ظهره فوق أرض صلبة.",
            "ضع كفّيك فوق بعض في وسط الصدر.",
            "اضغط بقوة وبسرعة، 5 سم، مع الإيقاع الذي أعدّه لك.",
            "لا تتوقف حتى يصل الفريق أو يأخذ المريض نفَسا طبيعيا."
          ],
          "medical": true,
          "metronome": 110
        },
        "recovery": {
          "title": "وضعية الأمان",
          "steps": [
            "أمِل المريض على جانبه، والرأس مائل قليلا إلى الخلف.",
            "راقب تنفسه، وأخبرني فورا إن توقف.",
            "لا تعطه أكلا ولا شربا."
          ],
          "medical": true,
          "metronome": null
        },
        "bleeding": {
          "title": "إيقاف النزيف",
          "steps": [
            "اضغط مباشرة على الجرح بقطعة قماش نظيفة.",
            "لا ترفع القماش، وأضف فوقه إن تبلّل.",
            "إن كان في الذراع أو الساق، ارفعها إن أمكن."
          ],
          "medical": true,
          "metronome": null
        }
      }
    },
    "sim": true,
    "medical": true,
    "medical_validated_by": "[SIM]",
    "medical_validated_at": "2026-11-10T08:00:00Z",
    "medical_reason": "[SIM] بطاقة تجريبية",
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  },
  {
    "id": "cc-fire",
    "category": "fire",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "حريق",
      "base_band": "high",
      "base_means": [
        "شاحنة إطفاء"
      ],
      "questions": [
        {
          "id": "trapped",
          "text": "هل يوجد أشخاص محاصرون أو لا يستطيعون الخروج؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "أشخاص محاصرون",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [
                "سلّم آلي",
                "سيارة إسعاف"
              ],
              "instruction": "evacuate",
              "lives": true,
              "injured": false
            }
          }
        },
        {
          "id": "high_floor",
          "text": "هل الحريق في الطابق الثالث فما فوق؟",
          "help": null,
          "key": false,
          "when": {
            "question": "trapped",
            "answer": "yes"
          },
          "effects": {
            "yes": {
              "why": "طابق عالٍ: السلّم الآلي ضروري",
              "band": null,
              "flag": null,
              "means": [
                "سلّم آلي"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "gas",
          "text": "هل توجد قوارير غاز أو مواد قابلة للانفجار قرب النار؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "خطر انفجار",
              "band": "critical",
              "flag": "خطر انفجار",
              "means": [
                "إعلام STEG لقطع الغاز",
                "إعلام الحرس أو الشرطة"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "injured",
          "text": "هل يوجد مصابون أو حروق؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "مصابون",
              "band": "critical",
              "flag": null,
              "means": [
                "سيارة إسعاف"
              ],
              "instruction": null,
              "lives": false,
              "injured": true
            }
          }
        },
        {
          "id": "spreading",
          "text": "هل النار تنتشر إلى مبانٍ أو غابة مجاورة؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "انتشار النار",
              "band": "critical",
              "flag": null,
              "means": [
                "إعلام ضابط القاعة"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "public",
          "text": "هل هو مبنى عام (مدرسة، مستشفى، سوق)؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "مبنى عام",
              "band": "critical",
              "flag": null,
              "means": [],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        }
      ],
      "instructions": {
        "evacuate": {
          "title": "الخروج من الحريق",
          "steps": [
            "اخرجوا فورا إن كان الطريق آمنا، ولا تعودوا لأخذ شيء.",
            "إن كان الدخان في الدرج: أغلقوا الباب وسدّوا أسفله بقماش مبلل.",
            "اقتربوا من نافذة وأشيروا للفريق.",
            "لا تستعملوا المصعد."
          ],
          "medical": false,
          "metronome": null
        }
      }
    },
    "sim": true,
    "medical": false,
    "medical_validated_by": null,
    "medical_validated_at": null,
    "medical_reason": null,
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  },
  {
    "id": "cc-traffic_accident",
    "category": "traffic_accident",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "حادث مرور",
      "base_band": "normal",
      "base_means": [
        "سيارة إسعاف",
        "إعلام الحرس أو الشرطة"
      ],
      "questions": [
        {
          "id": "stuck",
          "text": "هل يوجد شخص عالق داخل سيارة؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "عالق داخل سيارة",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [
                "آلية إنقاذ وتخليص"
              ],
              "instruction": "crash",
              "lives": true,
              "injured": false
            }
          }
        },
        {
          "id": "unconscious",
          "text": "هل يوجد مصاب لا يتحرك أو لا يجيب؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "مصاب فاقد للوعي",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [
                "طلب SMUR عبر 190 (طبيب على متن الإسعاف)"
              ],
              "instruction": null,
              "lives": true,
              "injured": true
            }
          }
        },
        {
          "id": "burning",
          "text": "هل تحترق سيارة أو يتسرب منها وقود؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "حريق أو تسرب وقود",
              "band": "critical",
              "flag": null,
              "means": [
                "شاحنة إطفاء"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "heavy",
          "text": "هل في الحادث حافلة أو شاحنة مواد خطرة؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "مركبة ثقيلة أو مواد خطرة",
              "band": "high",
              "flag": null,
              "means": [
                "وحدة المخاطر الكيميائية",
                "إعلام ضابط القاعة"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "many",
          "text": "هل المصابون أكثر من 3؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "إصابات متعددة",
              "band": "high",
              "flag": null,
              "means": [
                "إعلام ضابط القاعة"
              ],
              "instruction": null,
              "lives": false,
              "injured": true
            }
          }
        }
      ],
      "instructions": {
        "crash": {
          "title": "حادث مرور",
          "steps": [
            "أشعل أضواء التنبيه وضع المثلث إن أمكن.",
            "لا تُخرج المصاب من السيارة إلا إن كانت تحترق.",
            "أطفئ محرّك السيارة ولا تدخّن قربها."
          ],
          "medical": false,
          "metronome": null
        }
      }
    },
    "sim": true,
    "medical": false,
    "medical_validated_by": null,
    "medical_validated_at": null,
    "medical_reason": null,
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  },
  {
    "id": "cc-drowning",
    "category": "drowning",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "غرق",
      "base_band": "critical",
      "base_means": [
        "سيارة إسعاف"
      ],
      "questions": [
        {
          "id": "in_water",
          "text": "هل الشخص ما زال في الماء أو اختفى تحته؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "الضحية في الماء",
              "band": null,
              "flag": "حياة في خطر",
              "means": [
                "فرقة الغوص",
                "زورق إنقاذ"
              ],
              "instruction": "drowning",
              "lives": true,
              "injured": false
            },
            "no": {
              "why": "أُخرج من الماء",
              "band": null,
              "flag": null,
              "means": [],
              "instruction": "drowning",
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "breathing",
          "text": "بعد إخراجه: هل يتنفس؟",
          "help": null,
          "key": true,
          "when": {
            "question": "in_water",
            "answer": "no"
          },
          "effects": {
            "no": {
              "why": "لا يتنفس بعد الإخراج",
              "band": null,
              "flag": "توقف قلبي محتمل",
              "means": [
                "طلب SMUR عبر 190 (طبيب على متن الإسعاف)"
              ],
              "instruction": "cpr",
              "lives": true,
              "injured": false
            }
          }
        },
        {
          "id": "guarded",
          "text": "هل الشاطئ محروس؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "يُعلَم مركز الحراسة",
              "band": null,
              "flag": null,
              "means": [],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        }
      ],
      "instructions": {
        "drowning": {
          "title": "الغريق",
          "steps": [
            "لا تنزل إلى الماء إن لم تكن سبّاحا ماهرا؛ ارمِ له شيئا يطفو.",
            "عند إخراجه: إن لم يتنفس، أعطه 5 نفخات ثم ابدأ الضغط على الصدر.",
            "أشِر لأقرب حارس شاطئ."
          ],
          "medical": true,
          "metronome": null
        },
        "cpr": {
          "title": "الإنعاش القلبي بالهاتف",
          "steps": [
            "ضع الهاتف على مكبّر الصوت وابقَ مع المريض.",
            "مدّده على ظهره فوق أرض صلبة.",
            "ضع كفّيك فوق بعض في وسط الصدر.",
            "اضغط بقوة وبسرعة، 5 سم، مع الإيقاع الذي أعدّه لك.",
            "لا تتوقف حتى يصل الفريق أو يأخذ المريض نفَسا طبيعيا."
          ],
          "medical": true,
          "metronome": 110
        }
      }
    },
    "sim": true,
    "medical": true,
    "medical_validated_by": "[SIM]",
    "medical_validated_at": "2026-11-10T08:00:00Z",
    "medical_reason": "[SIM] بطاقة تجريبية",
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  },
  {
    "id": "cc-flood",
    "category": "flood",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "فيضان",
      "base_band": "normal",
      "base_means": [
        "شاحنة إطفاء"
      ],
      "questions": [
        {
          "id": "stranded",
          "text": "هل يوجد أشخاص عالقون في الماء أو فوق سطح؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "أشخاص عالقون",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [
                "زورق إنقاذ",
                "آلية إنقاذ وتخليص"
              ],
              "instruction": "flood",
              "lives": true,
              "injured": false
            }
          }
        },
        {
          "id": "car",
          "text": "هل جرف الماء سيارة؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "سيارة في الماء",
              "band": "critical",
              "flag": null,
              "means": [
                "زورق إنقاذ"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "rising",
          "text": "هل منسوب الماء يرتفع الآن؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "منسوب يرتفع",
              "band": "high",
              "flag": null,
              "means": [
                "إعلام ضابط القاعة"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "vulnerable",
          "text": "هل يوجد مسنّون أو أطفال أو ذوو إعاقة؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "أشخاص هشّون",
              "band": "high",
              "flag": null,
              "means": [],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        }
      ],
      "instructions": {
        "flood": {
          "title": "الفيضان",
          "steps": [
            "اصعدوا إلى أعلى مكان في المبنى.",
            "لا تعبروا الوادي ولا الماء الجاري، ولو بالسيارة.",
            "افصلوا الكهرباء إن كان ذلك آمنا."
          ],
          "medical": false,
          "metronome": null
        }
      }
    },
    "sim": true,
    "medical": false,
    "medical_validated_by": null,
    "medical_validated_at": null,
    "medical_reason": null,
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  },
  {
    "id": "cc-chemical_leak",
    "category": "chemical_leak",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "تسرب غاز أو مادة كيميائية",
      "base_band": "high",
      "base_means": [
        "شاحنة إطفاء",
        "وحدة المخاطر الكيميائية"
      ],
      "questions": [
        {
          "id": "household",
          "text": "هل هو غاز منزلي (قارورة أو قنوات)؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "غاز منزلي",
              "band": null,
              "flag": null,
              "means": [
                "إعلام STEG لقطع الغاز"
              ],
              "instruction": "gas",
              "lives": false,
              "injured": false
            },
            "no": {
              "why": "مادة غير الغاز المنزلي",
              "band": null,
              "flag": null,
              "means": [],
              "instruction": "chemical",
              "lives": false,
              "injured": false
            }
          }
        },
        {
          "id": "symptoms",
          "text": "هل يشكو أحد من دوار أو ضيق تنفس أو إغماء؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "أعراض تسمم",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [
                "سيارة إسعاف",
                "طلب SMUR عبر 190 (طبيب على متن الإسعاف)"
              ],
              "instruction": null,
              "lives": true,
              "injured": true
            }
          }
        },
        {
          "id": "crowd",
          "text": "هل المكان عام أو فيه عدد كبير من الناس؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "عدد كبير معرّض",
              "band": "critical",
              "flag": null,
              "means": [
                "إعلام الحرس أو الشرطة",
                "إعلام ضابط القاعة"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        }
      ],
      "instructions": {
        "gas": {
          "title": "تسرب الغاز",
          "steps": [
            "لا تشعل ولا تطفئ أي ضوء أو جهاز كهربائي.",
            "أغلق صمّام الغاز إن أمكن دون خطر.",
            "افتح النوافذ واخرج من المكان.",
            "اتصل بنا من خارج المبنى."
          ],
          "medical": false,
          "metronome": null
        },
        "chemical": {
          "title": "تسرب كيميائي",
          "steps": [
            "ابتعد عكس اتجاه الريح.",
            "أغلق النوافذ والتكييف إن كنت داخل مبنى.",
            "لا تلمس المادة ولا تقترب لمعرفتها."
          ],
          "medical": false,
          "metronome": null
        }
      }
    },
    "sim": true,
    "medical": false,
    "medical_validated_by": null,
    "medical_validated_at": null,
    "medical_reason": null,
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  },
  {
    "id": "cc-landslide",
    "category": "landslide",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "انزلاق تربة أو انهيار مبنى",
      "base_band": "high",
      "base_means": [
        "آلية إنقاذ وتخليص"
      ],
      "questions": [
        {
          "id": "buried",
          "text": "هل يوجد أشخاص تحت الأنقاض؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "أشخاص تحت الأنقاض",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [
                "سيارة إسعاف",
                "إعلام ضابط القاعة"
              ],
              "instruction": null,
              "lives": true,
              "injured": false
            }
          }
        },
        {
          "id": "road",
          "text": "هل الطريق مقطوع؟",
          "help": null,
          "key": false,
          "when": null,
          "effects": {
            "yes": {
              "why": "طريق مقطوع",
              "band": null,
              "flag": null,
              "means": [
                "إعلام الحرس أو الشرطة"
              ],
              "instruction": null,
              "lives": false,
              "injured": false
            }
          }
        }
      ],
      "instructions": {}
    },
    "sim": true,
    "medical": false,
    "medical_validated_by": null,
    "medical_validated_at": null,
    "medical_reason": null,
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  },
  {
    "id": "cc-sos",
    "category": "sos",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "نجدة عامة",
      "base_band": "high",
      "base_means": [
        "سيارة إسعاف"
      ],
      "questions": [
        {
          "id": "life",
          "text": "هل حياة شخص في خطر الآن؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "حياة في خطر",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [],
              "instruction": null,
              "lives": true,
              "injured": false
            }
          }
        }
      ],
      "instructions": {}
    },
    "sim": true,
    "medical": false,
    "medical_validated_by": null,
    "medical_validated_at": null,
    "medical_reason": null,
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  },
  {
    "id": "cc-other",
    "category": "other",
    "version": 1,
    "status": "approved",
    "content": {
      "title": "أخرى",
      "base_band": "low",
      "base_means": [
        "إعلام ضابط القاعة"
      ],
      "questions": [
        {
          "id": "life",
          "text": "هل حياة شخص في خطر الآن؟",
          "help": null,
          "key": true,
          "when": null,
          "effects": {
            "yes": {
              "why": "حياة في خطر",
              "band": "critical",
              "flag": "حياة في خطر",
              "means": [
                "سيارة إسعاف"
              ],
              "instruction": null,
              "lives": true,
              "injured": false
            }
          }
        }
      ],
      "instructions": {}
    },
    "sim": true,
    "medical": false,
    "medical_validated_by": null,
    "medical_validated_at": null,
    "medical_reason": null,
    "approved_by": "[SIM]",
    "approved_at": "2026-11-10T08:00:00Z",
    "approval_reason": "[SIM] بطاقة تجريبية",
    "created_by_name": "[SIM]",
    "updated_by_name": "[SIM]",
    "updated_at": "2026-11-10T08:00:00Z",
    "used": 0
  }
];
