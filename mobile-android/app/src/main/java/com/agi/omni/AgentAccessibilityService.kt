package com.agi.omni

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Bitmap
import android.graphics.Path
import android.graphics.Rect
import android.hardware.HardwareBuffer
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.Executors
import kotlin.math.max
import kotlin.math.min

class AgentAccessibilityService : AccessibilityService() {
    private val worker = Executors.newSingleThreadExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val prefs by lazy { getSharedPreferences("agent", MODE_PRIVATE) }
    private var lastFingerprint: String? = null
    private var lastEventClass: String? = null
    private var running = true

    private val observationRunnable = Runnable {
        worker.execute { publishObservation(force = false) }
    }

    private val commandRunnable = object : Runnable {
        override fun run() {
            if (!running) return
            worker.execute { pollAndExecute() }
            handler.postDelayed(this, 500L)
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        running = true
        handler.postDelayed(commandRunnable, 500L)
        handler.post(observationRunnable)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        lastEventClass = event?.className?.toString()
        handler.removeCallbacks(observationRunnable)
        handler.postDelayed(observationRunnable, 300L)
    }

    override fun onInterrupt() {
        running = false
        handler.removeCallbacksAndMessages(null)
        worker.shutdownNow()
    }

    override fun onDestroy() {
        running = false
        handler.removeCallbacksAndMessages(null)
        worker.shutdownNow()
        super.onDestroy()
    }

    private fun baseApi(): MobileApi {
        val url = prefs.getString("server_url", "http://10.0.2.2:8000").orEmpty()
        return MobileApi(url)
    }

    private fun ensureSession(api: MobileApi): String {
        val saved = prefs.getString("session_id", null)
        if (!saved.isNullOrBlank()) return saved
        val id = api.createSession(android.os.Build.MODEL)
        prefs.edit().putString("session_id", id).apply()
        return id
    }

    private fun publishObservation(force: Boolean) {
        val api = try { baseApi() } catch (_: Exception) { return }
        val sessionId = try { ensureSession(api) } catch (_: Exception) { return }
        val observation = buildObservation()
        val fingerprint = observation.toString()
        if (!force && fingerprint == lastFingerprint) return
        val screenshot = takeScreenshotBase64() ?: return
        try {
            api.postObservation(sessionId, observation, screenshot)
            lastFingerprint = fingerprint
        } catch (_: Exception) {
            // The next accessibility event retries delivery.
        }
    }

    private fun pollAndExecute() {
        val api = baseApi()
        val sessionId = try { ensureSession(api) } catch (_: Exception) { return }
        val command = try { api.pollCommand(sessionId) } catch (_: Exception) { return } ?: return
        val commandId = command.optString("id")
        if (commandId.isBlank()) return

        val result = executeCommand(command)
        result.put("command_id", commandId)

        val screenshot = takeScreenshotBase64()
        try {
            val observation = buildObservation()
            api.postObservation(sessionId, observation, screenshot)
            api.postCommandResult(sessionId, result, screenshot)
            lastFingerprint = observation.toString()
        } catch (_: Exception) {
            // Keep the device loop alive; the agent will time out rather than crash the service.
        }
    }

    private fun buildObservation(): JSONObject {
        val root = rootInActiveWindow
        val metrics = resources.displayMetrics
        val nodes = JSONArray()
        if (root != null) {
            appendNode(root, nodes, 0)
        }
        return JSONObject()
            .put("platform", "android")
            .put("package_name", root?.packageName ?: JSONObject.NULL)
            .put("activity_name", lastEventClass ?: JSONObject.NULL)
            .put("screen_width", metrics.widthPixels)
            .put("screen_height", metrics.heightPixels)
            .put("nodes", nodes)
    }

    private fun appendNode(node: AccessibilityNodeInfo, output: JSONArray, depth: Int) {
        if (depth > 20 || output.length() >= 280) return
        val bounds = Rect()
        node.getBoundsInScreen(bounds)

        val password = node.isPassword
        val item = JSONObject()
            .put("class_name", node.className?.toString() ?: JSONObject.NULL)
            .put("package_name", node.packageName?.toString() ?: JSONObject.NULL)
            .put("text", if (password) JSONObject.NULL else node.text?.toString()?.take(500) ?: JSONObject.NULL)
            .put("content_description", if (password) JSONObject.NULL else node.contentDescription?.toString()?.take(500) ?: JSONObject.NULL)
            .put("view_id", try { node.viewIdResourceName } catch (_: Exception) { null } ?: JSONObject.NULL)
            .put("clickable", node.isClickable)
            .put("editable", node.isEditable)
            .put("enabled", node.isEnabled)
            .put("password", password)
            .put("bounds", JSONObject()
                .put("left", bounds.left)
                .put("top", bounds.top)
                .put("right", bounds.right)
                .put("bottom", bounds.bottom)
            )
        output.put(item)

        for (index in 0 until node.childCount) {
            node.getChild(index)?.let { child ->
                appendNode(child, output, depth + 1)
                child.recycle()
            }
        }
    }

    private fun executeCommand(command: JSONObject): JSONObject {
        val type = command.optString("type")
        return try {
            val ok = when (type) {
                "open_app" -> openApp(command.optString("app_name"))
                "click" -> tap(normalizedX(command.optInt("x")), normalizedY(command.optInt("y")))
                "long_press" -> longPress(normalizedX(command.optInt("x")), normalizedY(command.optInt("y")), command.optInt("seconds", 2))
                "drag_and_drop" -> drag(
                    normalizedX(command.optInt("start_x")),
                    normalizedY(command.optInt("start_y")),
                    normalizedX(command.optInt("end_x")),
                    normalizedY(command.optInt("end_y"))
                )
                "wait" -> {
                    Thread.sleep(max(0L, command.optLong("seconds", 1L) * 1000L))
                    true
                }
                "go_back" -> performGlobalAction(GLOBAL_ACTION_BACK)
                "take_screenshot" -> true
                "list_apps" -> true
                "type" -> typeText(command.optString("text"))
                "press_key" -> pressKey(command.optString("key"))
                "scroll" -> scroll(command.optString("direction", "down"))
                else -> false
            }
            if (type == "list_apps") {
                listAppsResult()
            } else {
                JSONObject().put("status", if (ok) "ok" else "failed").put("action", type)
            }
        } catch (error: Exception) {
            JSONObject()
                .put("status", "failed")
                .put("action", type)
                .put("error", error.message ?: "Unknown Android action error")
        }
    }

    private fun normalizedX(value: Int): Int = (value.coerceIn(0, 999) * resources.displayMetrics.widthPixels) / 1000
    private fun normalizedY(value: Int): Int = (value.coerceIn(0, 999) * resources.displayMetrics.heightPixels) / 1000

    private fun tap(x: Int, y: Int): Boolean =
        dispatchGesture(simpleGesture(x, y, 0L, 60L), null, null)

    private fun longPress(x: Int, y: Int, seconds: Int): Boolean =
        dispatchGesture(simpleGesture(x, y, 0L, max(600L, min(3000L, seconds * 1000L))), null, null)

    private fun simpleGesture(x: Int, y: Int, startDelay: Long, duration: Long): GestureDescription {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        return GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, startDelay, duration))
            .build()
    }

    private fun drag(sx: Int, sy: Int, ex: Int, ey: Int): Boolean {
        val path = Path().apply {
            moveTo(sx.toFloat(), sy.toFloat())
            lineTo(ex.toFloat(), ey.toFloat())
        }
        return dispatchGesture(
            GestureDescription.Builder()
                .addStroke(GestureDescription.StrokeDescription(path, 0L, 700L))
                .build(),
            null,
            null
        )
    }

    private fun scroll(direction: String): Boolean {
        val width = resources.displayMetrics.widthPixels
        val height = resources.displayMetrics.heightPixels
        val x = width / 2f
        val fromY = if (direction == "up") height * 0.72f else height * 0.28f
        val toY = if (direction == "up") height * 0.28f else height * 0.72f
        val path = Path().apply {
            moveTo(x, fromY)
            lineTo(x, toY)
        }
        return dispatchGesture(
            GestureDescription.Builder()
                .addStroke(GestureDescription.StrokeDescription(path, 0L, 550L))
                .build(),
            null,
            null
        )
    }

    private fun typeText(value: String): Boolean {
        val root = rootInActiveWindow ?: return false
        var target: AccessibilityNodeInfo? = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        if (target == null || !target.isEditable) {
            target = findEditable(root)
        }
        if (target == null) {
            root.recycle()
            return false
        }
        if (!target.isFocused) target.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        val args = Bundle().apply {
            putCharSequence(
                AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                value
            )
        }
        val ok = target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        if (target !== root) target.recycle()
        root.recycle()
        return ok
    }

    private fun findEditable(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (node.isEditable && node.isVisibleToUser) return AccessibilityNodeInfo.obtain(node)
        for (index in 0 until node.childCount) {
            val child = node.getChild(index) ?: continue
            val found = findEditable(child)
            child.recycle()
            if (found != null) return found
        }
        return null
    }

    private fun pressKey(key: String): Boolean = when (key.uppercase()) {
        "BACK", "ESC" -> performGlobalAction(GLOBAL_ACTION_BACK)
        "HOME" -> performGlobalAction(GLOBAL_ACTION_HOME)
        "RECENTS" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
        else -> false
    }

    private fun openApp(name: String): Boolean {
        val pm = packageManager
        val normalized = name.trim().lowercase()
        val packages = pm.getInstalledApplications(0)
        val match = packages.firstOrNull { info ->
            info.packageName.lowercase() == normalized ||
                info.loadLabel(pm).toString().lowercase().contains(normalized)
        } ?: return false
        val intent = pm.getLaunchIntentForPackage(match.packageName) ?: return false
        intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        return true
    }

    private fun listAppsResult(): JSONObject {
        val pm = packageManager
        val items = JSONArray()
        pm.getInstalledApplications(0)
            .sortedBy { it.loadLabel(pm).toString().lowercase() }
            .take(120)
            .forEach { info ->
                items.put(JSONObject()
                    .put("name", info.loadLabel(pm).toString())
                    .put("package_name", info.packageName)
                )
            }
        return JSONObject().put("status", "ok").put("action", "list_apps").put("apps", items)
    }

    private fun takeScreenshotBase64(): String? {
        if (android.os.Build.VERSION.SDK_INT < 30) return null
        val latch = CountDownLatch(1)
        var encoded: String? = null
        takeScreenshot(
            Display.DEFAULT_DISPLAY,
            mainExecutor,
            object : TakeScreenshotCallback {
                override fun onSuccess(screenshot: ScreenshotResult) {
                    try {
                        val buffer: HardwareBuffer = screenshot.hardwareBuffer
                        val bitmap = Bitmap.wrapHardwareBuffer(buffer, screenshot.colorSpace)
                        if (bitmap != null) {
                            val copy = bitmap.copy(Bitmap.Config.ARGB_8888, false)
                            val output = ByteArrayOutputStream()
                            copy.compress(Bitmap.CompressFormat.PNG, 100, output)
                            encoded = android.util.Base64.encodeToString(output.toByteArray(), android.util.Base64.NO_WRAP)
                            copy.recycle()
                            bitmap.recycle()
                        }
                        buffer.close()
                    } catch (_: Exception) {
                        encoded = null
                    } finally {
                        latch.countDown()
                    }
                }

                override fun onFailure(errorCode: Int) {
                    latch.countDown()
                }
            }
        )
        latch.await(1800L, TimeUnit.MILLISECONDS)
        return encoded
    }
}
