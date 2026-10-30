"""
Multi-language translation and localization module for Canva Distribution Bot.
Supports Arabic (العربية 🇩🇿), French (Français 🇫🇷), and English (English 🇬🇧).
"""

from typing import Dict, Any

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ---------------------------------------------------------------------------
    # General & Buttons
    # ---------------------------------------------------------------------------
    "btn_pay": {
        "ar": "💳 تفعيل كانفا (500 دج)",
        "fr": "💳 Activer Canva (500 DZD)",
        "en": "💳 Activate Canva (500 DZD)"
    },
    "btn_affiliate": {
        "ar": "🎁 برنامج المكافآت (5 دعوات مدفوعة = هدية)",
        "fr": "🎁 Programme d'Affiliation (5 Payants = Cadeau)",
        "en": "🎁 Affiliate Rewards (5 Paid Invites = Freebie)"
    },
    "btn_status": {
        "ar": "📊 حالة حسابي",
        "fr": "📊 Mon Statut",
        "en": "📊 My Account Status"
    },
    "btn_help": {
        "ar": "❓ مساعدة ودليل الاستخدام",
        "fr": "❓ Aide & Guide",
        "en": "❓ Help & FAQ"
    },
    "btn_lang": {
        "ar": "🌐 تغيير اللغة (Langue)",
        "fr": "🌐 Changer la Langue",
        "en": "🌐 Change Language"
    },
    "btn_back_menu": {
        "ar": "🔙 العودة للقائمة الرئيسية",
        "fr": "🔙 Retour au Menu",
        "en": "🔙 Back to Main Menu"
    },
    "btn_verify_channel": {
        "ar": "🔄 تأكيد الانضمام للقناة",
        "fr": "🔄 Vérifier l'adhésion",
        "en": "🔄 Verify Channel Membership"
    },
    "btn_join_channel": {
        "ar": "📢 الانضمام إلى القناة الرسمية",
        "fr": "📢 Rejoindre le Canal Officiel",
        "en": "📢 Join Official Channel"
    },
    "btn_share_link": {
        "ar": "📤 مشاركة الرابط مع الأصدقاء",
        "fr": "📤 Partager avec des amis",
        "en": "📤 Share Link with Friends"
    },
    "btn_refresh": {
        "ar": "🔄 تحديث البيانات",
        "fr": "🔄 Actualiser",
        "en": "🔄 Refresh Data"
    },
    "btn_enter_email": {
        "ar": "📧 إدخال إيميل كانفا",
        "fr": "📧 Saisir l'e-mail Canva",
        "en": "📧 Enter Canva Email"
    },

    # ---------------------------------------------------------------------------
    # Channel Gate & Start
    # ---------------------------------------------------------------------------
    "channel_gate_title": {
        "ar": (
            "👋 *مرحباً بك {first_name}!* 🇩🇿\n\n"
            "للاستفادة من نظام التوزيع الآلي لـ *Canva (دفعة 500 مقعد)*، "
            "يجب عليك أولاً الانضمام إلى قناتنا الرسمية على تيليجرام:\n\n"
            "👉 *{channel}*\n\n"
            "بعد الانضمام، اضغط على زر *'تأكيد الانضمام للقناة'* بالأسفل للمتابعة مباشرة ⚡"
        ),
        "fr": (
            "👋 *Bienvenue {first_name} !* 🇩🇿\n\n"
            "Pour accéder au système automatisé de distribution *Canva (Lot de 500 Places)*, "
            "vous devez d'abord rejoindre notre canal officiel Telegram :\n\n"
            "👉 *{channel}*\n\n"
            "Après avoir rejoint le canal, cliquez sur *'Vérifier l'adhésion'* ci-dessous pour continuer ⚡"
        ),
        "en": (
            "👋 *Welcome {first_name}!* 🇩🇿\n\n"
            "To access the automated *Canva Distribution System (500 Seats Batch)*, "
            "you must first join our official Telegram channel:\n\n"
            "👉 *{channel}*\n\n"
            "After joining, tap *'Verify Channel Membership'* below to proceed ⚡"
        )
    },
    "channel_gate_alert_not_member": {
        "ar": "❌ لم تنضم للقناة بعد! يرجى الانضمام للقناة أولاً ثم الضغط على تأكيد.",
        "fr": "❌ Vous n'avez pas encore rejoint le canal ! Veuillez rejoindre d'abord.",
        "en": "❌ You haven't joined the channel yet! Please join first."
    },
    "welcome_menu": {
        "ar": (
            "🎨 *منصة توزيع كانفا في الجزائر* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "أهلاً بك *{first_name}* في النظام الآلي الفوري بدون أي تدخل يدوي.\n\n"
            "🪑 *المقاعد المتبقية*: `{remaining}/{max_seats}` مقعداً متاحاً\n"
            "💳 *سعر التفعيل*: `{amount:,.0f} دج` فقط مدى الحياة للدفعة الحالية\n\n"
            "📌 *كيفية الحصول على حسابك*:\n"
            "1. قم بتحويل {amount:,.0f} دج عبر تطبيق *BaridiMob*.\n"
            "2. أرسل وصل الدفع (ملف PDF أو صورة واضحة) هنا مباشرة.\n"
            "3. يتم التحقق من الوصل آلياً في ثوانٍ، ثم تدخل إيميلك لتصلك الدعوة الرسمية!\n\n"
            "🎁 *برنامج المكافآت VIP*:\n"
            "بعد التفعيل، ستحصل على رابط إحالة خاص بك. عند دعوة 5 أصدقاء يقومون بالشراء، "
            "تحصل على *هدية رقمية حصرية (Freebie Gift)*! 🚀\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "اختر من القائمة أدناه للبدء:"
        ),
        "fr": (
            "🎨 *Canva Hub Algérie* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Bonjour *{first_name}*, bienvenue sur le système 100% automatisé.\n\n"
            "🪑 *Places restantes* : `{remaining}/{max_seats}` places disponibles\n"
            "💳 *Frais d'activation* : `{amount:,.0f} DZD` seulement\n\n"
            "📌 *Comment obtenir votre accès Canva* :\n"
            "1. Effectuez un virement de {amount:,.0f} DZD via *BaridiMob*.\n"
            "2. Envoyez le reçu (PDF officiel ou capture d'écran nette) dans ce chat.\n"
            "3. Notre robot vérifie instantanément votre reçu et vous demande votre e-mail !\n\n"
            "🎁 *Programme de Récompenses VIP* :\n"
            "Une fois activé, partagez votre lien. Chaque fois que 5 amis achètent leur accès, "
            "vous gagnez un *Cadeau Digital Exclusif (Freebie)* ! 🚀\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Sélectionnez une option ci-dessous pour démarrer :"
        ),
        "en": (
            "🎨 *Canva Distribution Hub (Algeria)* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Hello *{first_name}*, welcome to our zero-human-delay automated distribution platform.\n\n"
            "🪑 *Remaining Seats*: `{remaining}/{max_seats}` available\n"
            "💳 *Activation Fee*: `{amount:,.0f} DZD`\n\n"
            "📌 *How to get your seat*:\n"
            "1. Transfer {amount:,.0f} DZD using *BaridiMob*.\n"
            "2. Send your receipt (official PDF or sharp screenshot) directly into this chat.\n"
            "3. Our local engine verifies it instantly and assigns your seat!\n\n"
            "🎁 *VIP Affiliate Rewards*:\n"
            "Once activated, invite your friends. For every 5 friends who buy Canva, "
            "you unlock an *Exclusive Freebie Gift*! 🚀\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Choose an option below:"
        )
    },

    # ---------------------------------------------------------------------------
    # Payment Instructions
    # ---------------------------------------------------------------------------
    "payment_instructions": {
        "ar": (
            "💳 *معلومات الدفع عبر بريدي موب (BaridiMob)* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "يرجى إرسال مبلغ *{amount:,.0f} دج* إلى الحساب التالي:\n\n"
            "📌 *رقم الحساب البريدي RIP (20 رقماً)*:\n"
            "`{rip}`\n\n"
            "📌 *رقم الحساب الجاري CCP*:\n"
            "`{ccp}`\n\n"
            "📌 *اسم صاحب الحساب*:\n"
            "*{holder}*\n\n"
            "📌 *المبلغ المطلوب بدقة*:\n"
            "`{amount:,.2f} DZD`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📋 *خطوات التفعيل الآلي (بدون انتظار)*:\n"
            "1. افتح تطبيق BaridiMob وقم بالتحويل.\n"
            "2. اضغط على *'Télécharger le reçu'* لتحميل ملف PDF (الأسرع والأفضل)، أو خذ لقطة شاشة واضحة.\n"
            "3. *أرسل ملف الـ PDF أو الصورة مباشرة إلى هذا الشات*.\n\n"
            "⚡ سيقوم المحرك بفحص رقم المعاملة والتاريخ والحساب في ثوانٍ!"
        ),
        "fr": (
            "💳 *Instructions de Paiement BaridiMob* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Veuillez effectuer le virement de *{amount:,.0f} DZD* vers notre compte officiel :\n\n"
            "📌 *RIP Destinataire (20 chiffres)* :\n"
            "`{rip}`\n\n"
            "📌 *Compte CCP* :\n"
            "`{ccp}`\n\n"
            "📌 *Titulaire du compte* :\n"
            "*{holder}*\n\n"
            "📌 *Montant exact* :\n"
            "`{amount:,.2f} DZD`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📋 *Étapes pour validation 100% instantanée* :\n"
            "1. Effectuez le virement dans BaridiMob.\n"
            "2. Appuyez sur *'Télécharger le reçu'* pour obtenir le PDF officiel, OU prenez une capture d'écran nette.\n"
            "3. *Envoyez le fichier PDF ou la photo directement dans cette conversation*.\n\n"
            "⚡ Notre moteur vérifie la signature, le RIP et l'identifiant en quelques secondes !"
        ),
        "en": (
            "💳 *BaridiMob Payment Instructions* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Please transfer *{amount:,.0f} DZD* to our official postal account:\n\n"
            "📌 *Destination RIP (20 digits)*:\n"
            "`{rip}`\n\n"
            "📌 *CCP Account*:\n"
            "`{ccp}`\n\n"
            "📌 *Account Holder*:\n"
            "*{holder}*\n\n"
            "📌 *Exact Amount*:\n"
            "`{amount:,.2f} DZD`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📋 *Instant Zero-Delay Verification Steps*:\n"
            "1. Open BaridiMob and complete the transfer.\n"
            "2. Tap *'Download Receipt'* (PDF preferred) or take a clear screenshot.\n"
            "3. *Send the PDF or screenshot directly into this chat*.\n\n"
            "⚡ The local verification engine validates your receipt in seconds!"
        )
    },

    # ---------------------------------------------------------------------------
    # Receipt Verification & Errors
    # ---------------------------------------------------------------------------
    "receipt_analyzing": {
        "ar": "🔍 *جاري فحص وصل بريدي موب عبر المحرك الذكي...*",
        "fr": "🔍 *Analyse du reçu BaridiMob avec le moteur local en cours...*",
        "en": "🔍 *Analyzing BaridiMob receipt with local verification engine...*"
    },
    "receipt_verified_success": {
        "ar": (
            "✅ *تم التحقق من الدفع بنجاح آلياً!* ⚡\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *رقم المعاملة (Tx ID)*: `{tx_id}`\n"
            "• *المبلغ المؤكد*: `{amount:,.2f} دج`\n"
            "• *تاريخ التحويل*: `{date}`\n"
            "• *الحساب المطابق*: `{account}`\n"
            "{op_line}"
            "• *حالة التدقيق*: مقبول ومسجل آلياً 🤖\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📧 *الخطوة الأخيرة — إدخال إيميل حسابك في كانفا*:\n"
            "يرجى الرد على هذه الرسالة بكتابة *البريد الإلكتروني* الخاص بحسابك في Canva "
            "(مثال: `yourname@gmail.com`)."
        ),
        "fr": (
            "✅ *PAIEMENT VÉRIFIÉ AVEC SUCCÈS !* ⚡\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *N° de transaction* : `{tx_id}`\n"
            "• *Montant vérifié* : `{amount:,.2f} DZD`\n"
            "• *Date* : `{date}`\n"
            "• *Compte crédité* : `{account}`\n"
            "{op_line}"
            "• *Validation* : Automatique sans délai humain 🤖\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📧 *DERNIÈRE ÉTAPE — VOTRE E-MAIL CANVA* :\n"
            "Veuillez répondre à ce message en écrivant votre *adresse e-mail Canva* "
            "(ex : `votre.email@gmail.com`)."
        ),
        "en": (
            "✅ *PAYMENT VERIFIED AUTOMATICALLY!* ⚡\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *Transaction ID*: `{tx_id}`\n"
            "• *Amount*: `{amount:,.2f} DZD`\n"
            "• *Date*: `{date}`\n"
            "• *Account*: `{account}`\n"
            "{op_line}"
            "• *Verification*: Approved (Zero human delay) 🤖\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📧 *FINAL STEP — ENTER YOUR CANVA EMAIL*:\n"
            "Please reply to this message with your *Canva Account Email Address* "
            "(e.g., `youremail@gmail.com`)."
        )
    },
    "receipt_tip": {
        "ar": "💡 *نصيحة*: الطريقة الأسرع والأضمن هي تنزيل ملف الـ PDF الرسمي مباشرة من تطبيق BaridiMob عبر زر 'Télécharger le reçu' وإرساله كملف.",
        "fr": "💡 *Conseil* : Le moyen le plus fiable est de télécharger le reçu officiel en PDF depuis l'application BaridiMob ('Télécharger le reçu') et de l'envoyer comme document.",
        "en": "💡 *Tip*: The fastest and most reliable way is to download the official PDF receipt inside BaridiMob ('Download receipt') and send that file."
    },

    # ---------------------------------------------------------------------------
    # Email Submission & Seat Confirmation
    # ---------------------------------------------------------------------------
    "email_prompt": {
        "ar": "📧 يرجى كتابة وإرسال *البريد الإلكتروني لحسابك في Canva* (مثال: `name@gmail.com`).",
        "fr": "📧 Veuillez envoyer l'adresse e-mail de votre *compte Canva* (ex : `nom@gmail.com`).",
        "en": "📧 Please send your *Canva Account Email Address* (e.g., `name@gmail.com`)."
    },
    "invalid_email_format": {
        "ar": "❌ *صيغة البريد الإلكتروني غير صحيحة!*\nيرجى إرسال بريد إلكتروني صالح مثل: `example@gmail.com`",
        "fr": "❌ *Format d'e-mail invalide !*\nVeuillez envoyer un e-mail valide (ex : `exemple@gmail.com`).",
        "en": "❌ *Invalid email format!*\nPlease send a valid email address (e.g., `example@gmail.com`)."
    },
    "email_already_registered": {
        "ar": "⚠️ هذا البريد الإلكتروني `{email}` مسجل مسبقاً لمقعد آخر في النظام.\nيرجى كتابة بريد إلكتروني مختلف.",
        "fr": "⚠️ Cet e-mail `{email}` est déjà enregistré pour une autre place.\nVeuillez fournir une adresse différente.",
        "en": "⚠️ The email `{email}` is already registered in our database.\nPlease provide a different email address."
    },
    "all_seats_taken": {
        "ar": "⚠️ *عذراً! تم حجز جميع المقاعد الـ 500 بالكامل.*\nترقبوا الدفعة القادمة عبر قناتنا الرسمية.",
        "fr": "⚠️ *Désolé ! Les 500 places sont toutes réservées.*\nRestez à l'affût sur notre canal pour les prochains lots.",
        "en": "⚠️ *Sorry! All 500 seats have been taken.*\nStay tuned in our channel for future allocations."
    },
    "seat_confirmed_card": {
        "ar": (
            "🎉 *تم تأكيد حجز مقعدك بنجاح!* 🚀\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *إيميل كانفا المسجل*: `{email}`\n"
            "• *طريقة التفعيل*: `مدفوع BaridiMob`\n"
            "• *رقم المقعد*: `#{seat_num} من {max_seats}`\n"
            "• *الحالة*: في قائمة الدعوات الرسمية 📋\n\n"
            "✨ *ماذا يحدث الآن؟*\n"
            "يقوم المشرف باستيراد دفعة الإيميلات المسجلة إلى لوحة تحكم Canva Admin. "
            "ستصلك رسالة دعوة رسمية مباشرة من Canva على بريدك الإلكتروني! "
            "بمجرد فتح الرسالة والضغط على قبول الدعوة، سيتفعل حسابك فوراً.\n\n"
            "🎁 *برنامج الأرباح والمكافآت متاح لك الآن*! اضغط على زر المكافآت بالأسفل للحصول على رابطك الخاص."
        ),
        "fr": (
            "🎉 *RÉSERVATION DE VOTRE PLACE CONFIRMÉE !* 🚀\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *E-mail Canva* : `{email}`\n"
            "• *Méthode* : `Payé BaridiMob`\n"
            "• *Numéro de place* : `#{seat_num} sur {max_seats}`\n"
            "• *Statut* : En attente d'invitation Canva 📋\n\n"
            "✨ *Que se passe-t-il ensuite ?*\n"
            "L'administrateur importe le lot d'e-mails vérifiés dans Canva. "
            "Vous recevrez une invitation officielle directement de Canva dans votre boîte de réception. "
            "Acceptez-la pour profiter de Canva !\n\n"
            "🎁 *Votre programme de parrainage est maintenant actif !* Cliquez sur Récompenses ci-dessous."
        ),
        "en": (
            "🎉 *SEAT RESERVATION CONFIRMED!* 🚀\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *Registered Email*: `{email}`\n"
            "• *Method*: `Paid BaridiMob`\n"
            "• *Seat Position*: `#{seat_num} of {max_seats}`\n"
            "• *Status*: In Canva Invitation Queue 📋\n\n"
            "✨ *Next steps*:\n"
            "The administrator batch-imports all verified emails into Canva. "
            "You will receive an official invitation email directly from Canva. "
            "Accept it in your inbox to access Canva!\n\n"
            "🎁 *Your Affiliate Rewards program is now active!* Click the rewards button below."
        )
    },

    # ---------------------------------------------------------------------------
    # Affiliate / Rewards Screen
    # ---------------------------------------------------------------------------
    "affiliate_locked": {
        "ar": (
            "🔒 *برنامج المكافآت والأرباح (VIP)* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "برنامج المكافآت مخصص للأعضاء النشطين الذين قاموا بتفعيل اشتراكهم في Canva.\n\n"
            "✨ *كيف يعمل البرنامج؟*\n"
            "1. قم بتفعيل مقعدك مقابل 500 دج.\n"
            "2. ستحصل على رابط إحالة مخصص لك.\n"
            "3. مقابل كل *5 أصدقاء يقومون بالشراء من خلال رابطك*، تفوز بـ *هدية رقمية حصرية (Freebie Gift)*! 🎁\n\n"
            "👉 *قم بتفعيل مقعدك أولاً للبدء في جني المكافآت:*"
        ),
        "fr": (
            "🔒 *Programme d'Affiliation VIP* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Ce programme est réservé aux membres actifs ayant activé Canva (500 DZD).\n\n"
            "✨ *Comment ça marche ?*\n"
            "1. Activez votre place pour 500 DZD.\n"
            "2. Obtenez votre lien de parrainage personnalisé.\n"
            "3. Pour chaque tranche de *5 amis qui achètent Canva*, gagnez un *Cadeau Digital Exclusif (Freebie)* ! 🎁\n\n"
            "👉 *Activez votre accès d'abord pour commencer :*"
        ),
        "en": (
            "🔒 *VIP Affiliate Rewards Program* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "The affiliate program is reserved for members who have unlocked Canva (500 DZD).\n\n"
            "✨ *How it works*:\n"
            "1. Activate your Canva seat for 500 DZD.\n"
            "2. Receive your unique referral link.\n"
            "3. For every *5 paying friends you refer*, unlock an *Exclusive Freebie Gift*! 🎁\n\n"
            "👉 *Activate your seat first to start earning rewards:*"
        )
    },
    "affiliate_dashboard": {
        "ar": (
            "🎁 *لوحة تحكم برنامج المكافآت VIP* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "شارك رابط الإحالة الخاص بك مع أصدقائك وزملائك في العمل والدراسة.\n"
            "مقابل كل *{target} أصدقاء يدفعون ويشتركون*، تفوز بـ *هدية مجانية حصرية (Freebie Gift)*! 🎁\n\n"
            "🔗 *رابط الإحالة الخاص بك*:\n"
            "`{link}`\n\n"
            "📊 *إحصائيات أدائك الحالية*:\n"
            "• المشتركون عن طريقك: *{paid_count} أصدقاء دفعوا*\n"
            "• المكافآت التي حصلت عليها: *{claimed} هدية*\n"
            "• المتبقي لهديتك القادمة: *{needed} دعوات مدفوعة فقط*\n\n"
            "💰 *إجمالي المبيعات التي حققتها*: `{revenue:,.0f} دج`"
        ),
        "fr": (
            "🎁 *Tableau de Bord Affiliation VIP* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Partagez votre lien de parrainage avec vos amis et collègues !\n"
            "Pour chaque tranche de *{target} amis qui achètent Canva*, vous gagnez un *Cadeau Digital Exclusif (Freebie)* ! 🎁\n\n"
            "🔗 *Votre Lien de Parrainage* :\n"
            "`{link}`\n\n"
            "📊 *Vos Statistiques* :\n"
            "• Amis parrainés ayant payé : *{paid_count} membres*\n"
            "• Cadeaux déjà reçus : *{claimed}*\n"
            "• Reste pour le prochain cadeau : *{needed} parrainages payants*\n\n"
            "💰 *Chiffre généré grâce à vous* : `{revenue:,.0f} DZD`"
        ),
        "en": (
            "🎁 *VIP Affiliate & Freebie Dashboard* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Share your personal invite link with friends and colleagues!\n"
            "For every *{target} friends who pay for Canva*, unlock an *Exclusive Freebie Gift*! 🎁\n\n"
            "🔗 *Your Referral Link*:\n"
            "`{link}`\n\n"
            "📊 *Your Performance*:\n"
            "• Paid Referrals: *{paid_count} paying friends*\n"
            "• Freebies Claimed: *{claimed}*\n"
            "• Needed for next freebie: *{needed} more paid invites*\n\n"
            "💰 *Total Revenue Generated*: `{revenue:,.0f} DZD`"
        )
    },
    "share_link_text": {
        "ar": "🎨 احصل على حساب كانفا (Canva) بـ 500 دج فقط مع تفعيل آلي فوري! اشترك عبر رابطي:",
        "fr": "🎨 Obtenez Canva pour seulement 500 DZD avec activation instantanée ! Rejoignez via mon lien :",
        "en": "🎨 Get Canva for only 500 DZD with instant automatic activation! Join using my link:"
    },

    # ---------------------------------------------------------------------------
    # Account Status
    # ---------------------------------------------------------------------------
    "account_status_card": {
        "ar": (
            "📊 *بطاقة حالة حسابك* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *معرف الحساب*: `{user_id}`\n"
            "• *الحالة الحالية*: {status_badge}\n"
            "• *البريد المسجل*: `{email}`\n"
            "• *الإحالات المدفوعة*: *{paid_refs} أصدقاء*\n"
            "• *المكافآت المحققة*: *{rewards} هدايا*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "{extra_hint}"
        ),
        "fr": (
            "📊 *État de votre Compte* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *Identifiant* : `{user_id}`\n"
            "• *Statut actuel* : {status_badge}\n"
            "• *E-mail enregistré* : `{email}`\n"
            "• *Amis parrainés payants* : *{paid_refs}*\n"
            "• *Cadeaux obtenus* : *{rewards}*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "{extra_hint}"
        ),
        "en": (
            "📊 *Account Status Card* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• *User ID*: `{user_id}`\n"
            "• *Status*: {status_badge}\n"
            "• *Registered Email*: `{email}`\n"
            "• *Paid Referrals*: *{paid_refs} friends*\n"
            "• *Freebies Earned*: *{rewards}*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "{extra_hint}"
        )
    },
    "status_badge_new": {
        "ar": "🆕 غير مفعل (بانتظار دفع 500 دج)",
        "fr": "🆕 Non activé (En attente du virement 500 DZD)",
        "en": "🆕 Inactive (Pending 500 DZD transfer)"
    },
    "status_badge_awaiting_receipt": {
        "ar": "⏳ بانتظار رفع وصل بريدي موب",
        "fr": "⏳ En attente du reçu BaridiMob",
        "en": "⏳ Awaiting BaridiMob Receipt"
    },
    "status_badge_awaiting_email": {
        "ar": "📧 تم التحقق! بانتظار إيميلك في كانفا",
        "fr": "📧 Paiement validé ! En attente de votre e-mail",
        "en": "📧 Verified! Waiting for your Canva email"
    },
    "status_badge_pending_invite": {
        "ar": "🕒 مسجل في قائمة دعوات كانفا",
        "fr": "🕒 Prêt dans la file d'attente Canva",
        "en": "🕒 Ready in Canva Invite Queue"
    },
    "status_badge_invited": {
        "ar": "🎉 مفعل بالكامل (أنت عضو في فريق Canva)",
        "fr": "🎉 Activé ! (Membre de l'équipe Canva)",
        "en": "🎉 Fully Activated (Member of Canva Team)"
    },

    # ---------------------------------------------------------------------------
    # Help & FAQ
    # ---------------------------------------------------------------------------
    "help_faq": {
        "ar": (
            "❓ *دليل المساعدة والأسئلة الشائعة (FAQ)* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔹 *س: هل هذا اشتراك Canva رسمي؟*\n"
            "ج: نعم، يتم إضافتك رسمياً إلى فريق Canva وتستمتع بجميع المزايا (قوالب مدفوعة، إزالة الخلفية، الذكاء الاصطناعي، خطوط غير محدودة).\n\n"
            "🔹 *س: كم يستغرق استلام الدعوة؟*\n"
            "ج: التحقق من الوصل فوري وآلي 100%. بعد كتابة إيميلك، يرسل المشرف دعوات الدفعة عدة مرات يومياً مباشرة إلى بريدك.\n\n"
            "🔹 *س: ماذا أفعل إذا رُفض الوصل؟*\n"
            "ج: تأكد من أنك قمت بالتحويل إلى رقم الـ RIP الصحيح، وبمبلغ 500 دج، وأن الوصل من تاريخ اليوم أو الأمس. يفضل دائماً إرسال ملف الـ PDF الأصلي.\n\n"
            "🔹 *س: كيف أربح الهدايا المجانية؟*\n"
            "ج: بعد تفعيلك، شارك رابطك مع زملائك. كل 5 أشخاص يدفعون يمنحونك هدية رقمية قيّمة يرسلها المشرف إليك مباشرة.\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "لأي استفسار إضافي، تواصل معنا عبر القناة الرسمية."
        ),
        "fr": (
            "❓ *Aide & Foire Aux Questions (FAQ)* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔹 *Q : Est-ce un accès Canva officiel ?*\n"
            "R : Oui, vous rejoignez une équipe Canva officielle avec tous les avantages (modèles premium, gomme magique IA, suppression d'arrière-plan, polices illimitées).\n\n"
            "🔹 *Q : Combien de temps prend la réception de l'invitation ?*\n"
            "R : La vérification du reçu est instantanée (robot). L'invitation par e-mail est envoyée plusieurs fois par jour par l'administrateur.\n\n"
            "🔹 *Q : Que faire si mon reçu est rejeté ?*\n"
            "R : Vérifiez que le montant est bien de 500 DZD, vers le bon RIP, et date d'aujourd'hui ou d'hier. Privilégiez le fichier PDF officiel BaridiMob.\n\n"
            "🔹 *Q : Comment gagner des cadeaux gratuits ?*\n"
            "R : Partagez votre lien après activation. Chaque tranche de 5 amis qui achètent vous fait débloquer un cadeau exclusif.\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Pour toute assistance, rejoignez notre canal officiel."
        ),
        "en": (
            "❓ *Help & Frequently Asked Questions (FAQ)* 🇩🇿\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔹 *Q: Is this official Canva?*\n"
            "A: Yes, you are invited to an official Canva team with full premium benefits (premium templates, Magic AI tools, background remover, unlimited assets).\n\n"
            "🔹 *Q: How long does it take to receive the invite?*\n"
            "A: Receipt verification is 100% instant and automated. The team email invite is dispatched several times daily.\n\n"
            "🔹 *Q: What if my receipt is rejected?*\n"
            "A: Ensure the transfer is exactly 500 DZD to the configured RIP, and dated today or yesterday. We recommend uploading the official PDF receipt.\n\n"
            "🔹 *Q: How do freebie rewards work?*\n"
            "A: Once activated, invite friends using your link. For every 5 paying friends, you receive an exclusive digital freebie delivered by the admin.\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "For further assistance, visit our official channel."
        )
    },

    # ---------------------------------------------------------------------------
    # Language Selection
    # ---------------------------------------------------------------------------
    "lang_selection_title": {
        "ar": "🌐 *اختر لغة الروبوت المفضلة* / *Choisissez votre langue* :",
        "fr": "🌐 *Choisissez votre langue* / *اختر لغتك المفضلة* :",
        "en": "🌐 *Choose your preferred language*:"
    },
    "lang_switched": {
        "ar": "✅ تم تغيير لغة الروبوت إلى *العربية 🇩🇿* بنجاح!",
        "fr": "✅ Langue changée en *Français 🇫🇷* avec succès !",
        "en": "✅ Language successfully switched to *English 🇬🇧*!"
    }
}


def t(key: str, lang: str = "fr", **kwargs: Any) -> str:
    """
    Retrieves translated string by key and language with fallback.
    Performs safe string formatting using kwargs.
    """
    lang_code = lang.lower() if lang else "fr"
    if lang_code not in ["ar", "fr", "en"]:
        lang_code = "fr"

    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang_code) or entry.get("fr") or entry.get("en") or key

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
