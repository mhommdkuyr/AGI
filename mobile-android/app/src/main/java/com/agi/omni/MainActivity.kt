package com.agi.omni

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.*
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private val prefs by lazy { getSharedPreferences("agent", MODE_PRIVATE) }
    private lateinit var status: TextView
    private lateinit var prompt: EditText
    private lateinit var budget: EditText
    private lateinit var serverUrl: EditText

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun text(value: String, size: Float, color: Int = Color.WHITE) =
        TextView(this).apply {
            text = value
            textSize = size
            setTextColor(color)
            textDirection = View.TEXT_DIRECTION_ANY
        }

    private fun card() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(16), dp(16), dp(16), dp(16))
        setBackgroundColor(Color.rgb(19, 24, 32))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.TOP
            setPadding(dp(16), dp(8), dp(16), dp(28))
            setBackgroundColor(Color.rgb(7, 9, 13))
            layoutDirection = View.LAYOUT_DIRECTION_RTL
        }
        setContentView(ScrollView(this).apply { addView(root) })

        val header = LinearLayout(this).apply {
            gravity = Gravity.CENTER_VERTICAL
            layoutDirection = View.LAYOUT_DIRECTION_RTL
        }
        header.addView(text("وكيل", 22f, Color.rgb(247, 248, 250)),
            LinearLayout.LayoutParams(0, dp(56), 1f))
        header.addView(Button(this).apply {
            text = "☰"
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.rgb(21, 26, 34))
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        }, LinearLayout.LayoutParams(dp(48), dp(48)))
        root.addView(header)

        root.addView(text("ماذا تريد أن أنفّذ؟", 32f, Color.rgb(247, 248, 250)).apply {
            setPadding(dp(2), dp(24), 0, dp(8))
        })
        root.addView(text(
            "اكتب المهمة كما تقولها لشخص يعمل أمام الهاتف. أخطط، أتصفح، أنفّذ، ثم أتحقق من النتيجة.",
            16f, Color.rgb(154, 164, 178)
        ))

        val taskCard = card()
        taskCard.addView(text("المهمة", 13f, Color.rgb(203, 211, 223)))
        prompt = EditText(this).apply {
            hint = "مثال: افتح تطبيق الساعة واضبط منبهاً على 07:00"
            hintTextColor = Color.rgb(117, 117, 117)
            setTextColor(Color.WHITE)
            setPadding(dp(14), dp(14), dp(14), dp(14))
            minLines = 5
            gravity = Gravity.TOP or Gravity.RIGHT
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(Color.rgb(10, 13, 18))
                setStroke(dp(1), Color.rgb(42, 49, 61))
                cornerRadius = dp(17).toFloat()
            }
        }
        taskCard.addView(prompt, LinearLayout.LayoutParams(-1, dp(130)).apply { topMargin = dp(10) })

        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            layoutDirection = View.LAYOUT_DIRECTION_RTL
        }
        budget = EditText(this).apply {
            setText("0.75")
            inputType = android.text.InputType.TYPE_CLASS_NUMBER or android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL
            setTextColor(Color.WHITE)
            hintTextColor = Color.GRAY
            gravity = Gravity.CENTER
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(Color.rgb(10, 13, 18))
                setStroke(dp(1), Color.rgb(42, 49, 61))
                cornerRadius = dp(14).toFloat()
            }
        }
        row.addView(budget, LinearLayout.LayoutParams(0, dp(56), 1f))
        row.addView(Button(this).apply {
            text = "بدء التنفيذ ↗"
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.rgb(22, 119, 255))
            setOnClickListener { submitTask() }
        }, LinearLayout.LayoutParams(0, dp(56), 1f).apply { marginStart = dp(10) })
        taskCard.addView(row, LinearLayout.LayoutParams(-1, dp(66)).apply { topMargin = dp(10) })
        root.addView(taskCard, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(18) })

        val controlCard = card()
        controlCard.addView(text("التحكم على الهاتف", 13f, Color.rgb(203, 211, 223)))
        controlCard.addView(Button(this).apply {
            text = "تفعيل خدمة التحكم"
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.rgb(38, 57, 77))
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        }, LinearLayout.LayoutParams(-1, dp(54)).apply { topMargin = dp(10) })

        serverUrl = EditText(this).apply {
            setText(prefs.getString("server_url", "http://10.0.2.2:8000"))
            hint = "عنوان خادم الوكيل"
            setTextColor(Color.WHITE)
            hintTextColor = Color.GRAY
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(Color.rgb(10, 13, 18))
                setStroke(dp(1), Color.rgb(42, 49, 61))
                cornerRadius = dp(14).toFloat()
            }
        }
        controlCard.addView(serverUrl, LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(10) })
        root.addView(controlCard, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })

        status = text("جاهز — أنشئ الجلسة ثم فعّل الخدمة من إعدادات Android.", 13f, Color.rgb(154, 164, 178))
        status.setPadding(0, dp(12), 0, 0)
        root.addView(status)

        root.addView(text(
            "تنبيه الخصوصية: خدمة Accessibility تقرأ عناصر الواجهة وتنفّذ أوامر المستخدم على الجهاز، وترسل بيانات الواجهة ولقطات الشاشة اللازمة إلى خادم الوكيل. هذه النسخة مخصصة للـPoC والاختبار الداخلي؛ لا تُدرج في Google Play كأداة وصول عامة دون استيفاء سياسة AccessibilityService.",
            12f, Color.rgb(154, 164, 178)
        ).apply { setPadding(0, dp(16), 0, 0) })
    }

    private fun submitTask() {
        val taskText = prompt.text?.toString()?.trim().orEmpty()
        if (taskText.length < 3) {
            status.text = "اكتب مهمة صالحة أولاً."
            return
        }
        val budgetValue = budget.text?.toString()?.toDoubleOrNull() ?: 0.75
        val url = serverUrl.text?.toString()?.trim().orEmpty().ifBlank { "http://10.0.2.2:8000" }
        prefs.edit().putString("server_url", url).apply()
        status.text = "جارٍ إنشاء جلسة الهاتف…"
        executor.execute {
            try {
                val api = MobileApi(url)
                val sessionId = prefs.getString("session_id", null)
                    ?: api.createSession(android.os.Build.MODEL).also {
                        prefs.edit().putString("session_id", it).apply()
                    }
                val taskId = api.submitMobileTask(taskText, budgetValue, sessionId)
                runOnUiThread {
                    status.text = "تم إرسال المهمة: " + taskId
                    Toast.makeText(this, "تبدأ الآن حلقة التنفيذ على الجهاز.", Toast.LENGTH_LONG).show()
                }
            } catch (error: Exception) {
                runOnUiThread { status.text = "فشل الاتصال: " + (error.message ?: "خطأ غير معروف") }
            }
        }
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
