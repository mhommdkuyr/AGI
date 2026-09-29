# Omni Mobile Agent — Android PoC

هذا المجلد هو عميل Android أصلي لمسار الهاتف في AGI.

## البناء

المشروع يستهدف Android 16 (API 36)، ويستخدم Android Gradle Plugin 9.4.0 وGradle 9.6.0 وJDK 17.

شغّل: cd mobile-android && gradle :app:assembleDebug

## التشغيل

1. شغّل خادم AGI.
2. افتح التطبيق وأدخل عنوان الخادم. للمحاكي Android استخدم عادة http://10.0.2.2:8000.
3. فعّل خدمة «وكيل — التحكم على الهاتف» من إعدادات Accessibility.
4. أرسل المهمة من واجهة التطبيق.
5. ترسل الخدمة UI Tree عند تغيّر الحالة، ولقطة PNG عند الحاجة وبعد تنفيذ الأوامر، ثم تنفذ أوامر Gemini على الجهاز.

## حدود الـPoC

الخدمة تستخدم AccessibilityService للتحكم في الجهاز. هذه البنية مناسبة للاختبار الداخلي/التجريبي، لكنها ليست إعلاناً بأن التطبيق مؤهل للنشر العام في Google Play؛ سياسة Google Play تفرض قيوداً خاصة على الأتمتة الذاتية باستخدام AccessibilityService.
