"""
One-shot helper: adds healthcare + education_university batch-1 entities
to jo_entities.json.  Run once from backend/:
    python scripts/_add_entities_batch1.py
"""
from __future__ import annotations
import json
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REGISTRY = BACKEND_DIR / "app" / "data" / "entities" / "jo_entities.json"

NEW_ENTITIES = [
    # ── Healthcare ─────────────────────────────────────────────────────────────
    {
        "id": "royal_medical_services_jo",
        "name": "Royal Medical Services Jordan",
        "primary_arabic_name": "الخدمات الطبية الملكية",
        "aliases": [
            "الخدمات الطبية الملكية",
            "الخدمات الطبيه الملكيه",
            "الطبية الملكية",
            "Royal Medical Services",
            "RMS Jordan",
            "RMS"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["rms.gov.jo"],
        "official_sender_names": ["RMS", "Royal Medical Services"],
        "allowed_message_types": [
            "appointment_notice", "lab_result_notice", "payment_receipt",
            "service_notice", "security_awareness", "advertisement"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "Royal Medical Services operates under the Jordan Armed Forces.",
            "Official domain rms.gov.jo verified from official .gov.jo registry.",
            "RMS is a 3-char alias; short — may collide; exact gateway sender unconfirmed.",
            "Should never request passwords, OTP codes, card numbers, or recovery codes via SMS."
        ]
    },
    {
        "id": "king_hussein_cancer_center",
        "name": "King Hussein Cancer Center",
        "primary_arabic_name": "مركز الحسين للسرطان",
        "aliases": [
            "مركز الحسين للسرطان",
            "مركز الحسين",
            "King Hussein Cancer Center",
            "KHCC"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["khcc.jo"],
        "official_sender_names": ["KHCC", "King Hussein Cancer Center"],
        "allowed_message_types": [
            "appointment_notice", "lab_result_notice", "payment_receipt",
            "service_notice", "security_awareness", "advertisement"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "King Hussein Cancer Center is a JCI-accredited oncology center in Amman.",
            "Official domain khcc.jo verified from official entity website.",
            "Appointment reminder impersonation is a known healthcare phishing vector.",
            "Should never request passwords, OTP codes, or card data via SMS."
        ]
    },
    {
        "id": "jordan_university_hospital",
        "name": "Jordan University Hospital",
        "primary_arabic_name": "مستشفى الجامعة الأردنية",
        "aliases": [
            "مستشفى الجامعة الأردنية",
            "مستشفى الجامعه الأردنيه",
            "Jordan University Hospital",
            "JUH"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["juh.jo"],
        "official_sender_names": ["JUH", "Jordan University Hospital"],
        "allowed_message_types": [
            "appointment_notice", "lab_result_notice", "payment_receipt",
            "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "Jordan University Hospital is affiliated with the University of Jordan; major teaching hospital.",
            "Official domain juh.jo verified from entity official website.",
            "Alias does not include الجامعة الأردنية alone — that alias belongs to university_of_jordan entity.",
            "Should never request sensitive credentials via SMS."
        ]
    },
    {
        "id": "specialty_hospital_jo",
        "name": "Specialty Hospital Amman",
        "primary_arabic_name": "مستشفى التخصصي",
        "aliases": [
            "مستشفى التخصصي",
            "مستشفى التخصصي عمان",
            "Specialty Hospital",
            "Specialty Hospital Amman"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["specialty-hospital.com"],
        "official_sender_names": ["Specialty Hospital"],
        "allowed_message_types": [
            "appointment_notice", "lab_result_notice", "payment_receipt",
            "service_notice", "security_awareness", "advertisement"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "Specialty Hospital Amman is a major private tertiary care hospital in Jordan.",
            "Official domain specialty-hospital.com verified from official entity website.",
            "SMS sender names are unconfirmed; conservative values used.",
            "Should never request sensitive credentials or card data via SMS."
        ]
    },
    {
        "id": "istishari_hospital_jo",
        "name": "Istishari Hospital",
        "primary_arabic_name": "مستشفى الاستشاري",
        "aliases": [
            "مستشفى الاستشاري",
            "الاستشاري",
            "Istishari Hospital",
            "Arab Istishari Hospital"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["istishari.com"],
        "official_sender_names": ["Istishari Hospital", "Istishari"],
        "allowed_message_types": [
            "appointment_notice", "lab_result_notice", "payment_receipt",
            "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "Istishari Hospital (Arab Istishari Hospital) is a private hospital in Amman, Jordan.",
            "Official domain istishari.com used; SMS sender names are unconfirmed.",
            "Should never request sensitive credentials or card data via SMS."
        ]
    },
    {
        "id": "abdali_hospital_jo",
        "name": "Abdali Hospital",
        "primary_arabic_name": "مستشفى عبدالي",
        "aliases": [
            "مستشفى عبدالي",
            "عبدالي مستشفى",
            "Abdali Hospital"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["abdali-hospital.com"],
        "official_sender_names": ["Abdali Hospital"],
        "allowed_message_types": [
            "appointment_notice", "lab_result_notice", "payment_receipt",
            "service_notice", "security_awareness", "advertisement"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "Abdali Hospital is a private hospital in Amman's Abdali development area.",
            "Official domain abdali-hospital.com used; SMS sender names are unconfirmed.",
            "Should never request sensitive credentials or card data via SMS."
        ]
    },
    {
        "id": "al_khalidi_hospital_jo",
        "name": "Al Khalidi Hospital",
        "primary_arabic_name": "مستشفى الخالدي",
        "aliases": [
            "مستشفى الخالدي",
            "الخالدي",
            "Al Khalidi Hospital",
            "Khalidi Hospital"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["khalidihospital.com"],
        "official_sender_names": ["Al Khalidi Hospital", "Khalidi Hospital"],
        "allowed_message_types": [
            "appointment_notice", "lab_result_notice", "payment_receipt",
            "service_notice", "security_awareness", "advertisement"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "Al Khalidi Hospital is a well-established private hospital in Amman, Jordan.",
            "Official domain khalidihospital.com used; SMS sender names are unconfirmed.",
            "Should never request sensitive credentials or card data via SMS."
        ]
    },
    {
        "id": "arab_medical_center_jo",
        "name": "Arab Medical Center",
        "primary_arabic_name": "المركز الطبي العربي",
        "aliases": [
            "المركز الطبي العربي",
            "المركز الطبي",
            "Arab Medical Center",
            "AMC Jordan"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["arabmedicalcenter.jo"],
        "official_sender_names": ["Arab Medical Center", "AMC"],
        "allowed_message_types": [
            "appointment_notice", "lab_result_notice", "payment_receipt",
            "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "Arab Medical Center is a private hospital in Amman, Jordan.",
            "Official domain arabmedicalcenter.jo used; SMS sender names are unconfirmed.",
            "Alias المركز الطبي العربي is the full official name; المركز الطبي alone may be too generic.",
            "Should never request sensitive credentials or card data via SMS."
        ]
    },
    {
        "id": "biolab_jordan",
        "name": "Biolab Jordan",
        "primary_arabic_name": "بايولاب الأردن",
        "aliases": [
            "بايولاب",
            "بايولاب الأردن",
            "Biolab",
            "Biolab Jordan"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["biolab.com.jo"],
        "official_sender_names": ["Biolab", "Biolab Jordan"],
        "allowed_message_types": [
            "lab_result_notice", "appointment_notice", "payment_receipt",
            "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "Biolab is one of Jordan's largest clinical laboratory chains.",
            "Official domain biolab.com.jo verified from official entity website.",
            "Lab result phishing is a known attack vector.",
            "Should never request sensitive credentials or card data via SMS."
        ]
    },
    {
        "id": "medlabs_jordan",
        "name": "MedLabs Jordan",
        "primary_arabic_name": "ميدلابس",
        "aliases": [
            "ميدلابس",
            "MedLabs",
            "MedLabs Jordan",
            "Medlabs"
        ],
        "entity_type": "healthcare",
        "country": "JO",
        "official_domains": ["medlabs.com"],
        "official_sender_names": ["MedLabs", "Medlabs"],
        "allowed_message_types": [
            "lab_result_notice", "appointment_notice", "payment_receipt",
            "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "card_number", "cvv", "card_pin", "recovery_code"
        ],
        "risk_notes": [
            "MedLabs is a regional clinical laboratory chain with major operations in Jordan.",
            "Official domain medlabs.com verified from official entity website.",
            "Fraudulent SMS claiming to share lab results via external links is a known risk.",
            "Should never request sensitive credentials or card data via SMS."
        ]
    },
    # ── Education / University ─────────────────────────────────────────────────
    {
        "id": "university_of_jordan",
        "name": "University of Jordan",
        "primary_arabic_name": "الجامعة الأردنية",
        "aliases": [
            "الجامعة الأردنية",
            "الجامعه الأردنيه",
            "الجامعة الاردنية",
            "University of Jordan",
            "UJ"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["ju.edu.jo"],
        "official_sender_names": ["University of Jordan", "UJ"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "University of Jordan is Jordan's oldest and largest public university, founded 1962.",
            "Official domain ju.edu.jo under Jordan's official .edu.jo registry.",
            "University credential phishing — fake portals stealing student logins — is a known attack.",
            "UJ is a 2-char alias; marked high-risk; exact registered sender unconfirmed.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "just_jordan",
        "name": "Jordan University of Science and Technology",
        "primary_arabic_name": "جامعة العلوم والتكنولوجيا الأردنية",
        "aliases": [
            "جامعة العلوم والتكنولوجيا الأردنية",
            "جامعة العلوم والتكنولوجيا",
            "Jordan University of Science and Technology",
            "JUST"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["just.edu.jo"],
        "official_sender_names": ["JUST", "Jordan University of Science and Technology"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "Jordan University of Science and Technology (JUST) is a major public university in Irbid.",
            "Official domain just.edu.jo under Jordan's official .edu.jo registry.",
            "University credential phishing is a known attack vector.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "yarmouk_university",
        "name": "Yarmouk University",
        "primary_arabic_name": "جامعة اليرموك",
        "aliases": [
            "جامعة اليرموك",
            "جامعه اليرموك",
            "Yarmouk University"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["yu.edu.jo"],
        "official_sender_names": ["Yarmouk University", "Yarmouk"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "Yarmouk University is a public university located in Irbid, Jordan.",
            "Official domain yu.edu.jo under Jordan's official .edu.jo registry.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "balqa_applied_university",
        "name": "Al-Balqa Applied University",
        "primary_arabic_name": "جامعة البلقاء التطبيقية",
        "aliases": [
            "جامعة البلقاء التطبيقية",
            "جامعة البلقاء",
            "جامعه البلقاء",
            "Al-Balqa Applied University",
            "Balqa University",
            "BAU"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["bau.edu.jo"],
        "official_sender_names": ["BAU", "Balqa University"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "Al-Balqa Applied University is a public applied university in Jordan with many campuses.",
            "Official domain bau.edu.jo under Jordan's official .edu.jo registry.",
            "BAU is a 3-char abbreviation; well-established for this institution.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "hashemite_university",
        "name": "The Hashemite University",
        "primary_arabic_name": "الجامعة الهاشمية",
        "aliases": [
            "الجامعة الهاشمية",
            "الجامعه الهاشميه",
            "The Hashemite University",
            "Hashemite University"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["hu.edu.jo"],
        "official_sender_names": ["Hashemite University", "HU Jordan"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "The Hashemite University is a public university located in Zarqa, Jordan.",
            "Official domain hu.edu.jo under Jordan's official .edu.jo registry.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "mutah_university",
        "name": "Mutah University",
        "primary_arabic_name": "جامعة مؤتة",
        "aliases": [
            "جامعة مؤتة",
            "جامعه مؤتة",
            "Mutah University",
            "Mu'tah University"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["mutah.edu.jo"],
        "official_sender_names": ["Mutah University", "Mutah"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "Mutah University is a public university in Al-Karak, Jordan.",
            "Official domain mutah.edu.jo under Jordan's official .edu.jo registry.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "german_jordanian_university",
        "name": "German Jordanian University",
        "primary_arabic_name": "الجامعة الألمانية الأردنية",
        "aliases": [
            "الجامعة الألمانية الأردنية",
            "الجامعه الألمانيه الأردنيه",
            "German Jordanian University",
            "GJU"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["gju.edu.jo"],
        "official_sender_names": ["GJU", "German Jordanian University"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "German Jordanian University is a private university in Amman, established in partnership with Germany.",
            "Official domain gju.edu.jo under Jordan's official .edu.jo registry.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "princess_sumaya_university",
        "name": "Princess Sumaya University for Technology",
        "primary_arabic_name": "جامعة الأميرة سمية للتكنولوجيا",
        "aliases": [
            "جامعة الأميرة سمية للتكنولوجيا",
            "جامعة الأميرة سمية",
            "Princess Sumaya University for Technology",
            "Princess Sumaya University",
            "PSUT"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["psut.edu.jo"],
        "official_sender_names": ["PSUT", "Princess Sumaya University"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "Princess Sumaya University for Technology (PSUT) is a private technology-focused university in Amman.",
            "Official domain psut.edu.jo under Jordan's official .edu.jo registry.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "applied_science_university_jo",
        "name": "Applied Science Private University",
        "primary_arabic_name": "جامعة العلوم التطبيقية الخاصة",
        "aliases": [
            "جامعة العلوم التطبيقية الخاصة",
            "جامعة العلوم التطبيقية",
            "Applied Science Private University",
            "Applied Science University",
            "ASU Jordan"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["asu.edu.jo"],
        "official_sender_names": ["ASU Jordan", "Applied Science University"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "Applied Science Private University (ASU) is a private university in Amman, Jordan.",
            "Official domain asu.edu.jo under Jordan's official .edu.jo registry.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
    {
        "id": "philadelphia_university_jo",
        "name": "Philadelphia University Jordan",
        "primary_arabic_name": "جامعة فيلادلفيا",
        "aliases": [
            "جامعة فيلادلفيا",
            "جامعه فيلادلفيا",
            "Philadelphia University Jordan",
            "Philadelphia University",
            "PUA Jordan"
        ],
        "entity_type": "education_university",
        "country": "JO",
        "official_domains": ["philadelphia.edu.jo"],
        "official_sender_names": ["Philadelphia University", "PUA Jordan"],
        "allowed_message_types": [
            "admission_notice", "registration_notice", "tuition_notice",
            "exam_notice", "service_notice", "security_awareness"
        ],
        "forbidden_requests": [
            "password", "otp_code", "recovery_code", "card_number", "cvv"
        ],
        "risk_notes": [
            "Philadelphia University is a private university in Jerash Governorate, Jordan.",
            "Official domain philadelphia.edu.jo under Jordan's official .edu.jo registry.",
            "Should never request student passwords, recovery codes, or card data via SMS."
        ]
    },
]


def main() -> None:
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entities: list[dict] = raw["entities"]

    existing_ids = {e["id"] for e in entities}
    added = []
    for ent in NEW_ENTITIES:
        if ent["id"] in existing_ids:
            print(f"  SKIP (already exists): {ent['id']}")
        else:
            entities.append(ent)
            added.append(ent["id"])
            print(f"  ADDED: {ent['id']}")

    raw["entities"] = entities
    REGISTRY.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nDone. Added {len(added)} entities. Registry now has {len(entities)} total.")


if __name__ == "__main__":
    main()
