# فهرس المهارات العربية

هذه الاختصارات تربط أسماء عربية بملفات Agent Skills داخل هذا المستودع.

| الاختصار | الوظيفة | الملف |
|---|---|---|
| `@تصفح_عميق` | بحث عميق متعدد المصادر، استخراج منظم، مقارنة الأدلة | [deep-web-research](.agents/skills/deep-web-research/SKILL.md) |
| `@متصفح_مسجل` | تصفح تفاعلي للصفحات المتاحة عبر جلسة مصرح بها | [browser-session-research](.agents/skills/browser-session-research/SKILL.md) |
| `@حصر_المنشآت` | حصر الأنشطة التجارية الجغرافي، التحقق وإزالة التكرار | [google-maps-business-research](.agents/skills/google-maps-business-research/SKILL.md) |
| `@خرائط_جوجل` | تطوير واجهات وميزات Google Maps Platform | [google-maps-platform](.agents/skills/google-maps-platform/SKILL.md) |
| `@تحليل_الفيديو` | تحليل النص والصوت واللقطات والتوقيتات | [video-analysis](.agents/skills/video-analysis/SKILL.md) |

## مصادر المشاريع الأصلية

- [Google Maps Lead Generation Skill](https://github.com/ahmmikun/google-maps-lead-generation-skill)
- [Tencent BrowserSkill](https://github.com/Tencent/BrowserSkill)
- [Google Maps Platform Agent Skills](https://github.com/googlemaps/agent-skills)
- [Firecrawl](https://www.firecrawl.dev/)
- [Claude Video / Watch](https://github.com/bradautomates/claude-video)

## ملاحظات تشغيل مهمة

1. هذه ملفات توجيه قابلة لإعادة الاستخدام في بيئات Agent Skills التي تقرأ `.agents/skills`. لا تعني أن جميع بيئات GitHub أو واجهة ChatGPT ستقوم بتحميلها تلقائيًا.
2. في ChatGPT الحالي، يمكن استخدام البحث والويب وFirecrawl وفق الاتصالات المتاحة. ظهور اسم يبدأ بـ @ هو اصطلاح داخل المحادثة، وليس أمرًا أصليًا مضمونًا من واجهة ChatGPT.
3. للوصول إلى جلسة متصفح شخصية، يجب توصيل أداة متصفح مناسبة والتحقق من حالتها؛ ملفات GitHub وحدها لا تنقل جلسة Chrome أو كلمات المرور.
4. بعض المشاريع الأصلية تحتاج تثبيت CLI/إضافة متصفح أو اعتماديات ومفاتيح API. راجع وثائقها الرسمية قبل استخدامها، ولا تضع الأسرار داخل المستودع.
5. التحقق في CI يختبر تنسيق ملفات المهارات وعناوينها وخرائط الاختصارات، ولا يثبت تلقائيًا تكاملًا خارجيًا أو صحة جميع نتائج البحث.