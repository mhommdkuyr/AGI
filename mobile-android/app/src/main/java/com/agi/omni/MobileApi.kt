package com.agi.omni

import org.json.JSONObject
import java.net.URI
import java.net.HttpURLConnection

class MobileApi(private val baseUrl: String) {
    private fun request(method: String, path: String, body: String? = null): String? {
        val url = URI.create(baseUrl.trimEnd('/') + path).toURL()
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 8000
            readTimeout = 15000
            doInput = true
            setRequestProperty("Accept", "application/json")
        }
        try {
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { stream -> stream.write(body.toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            if (code == 204) return null
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val payload = stream?.bufferedReader(Charsets.UTF_8)?.use { reader -> reader.readText() }.orEmpty()
            if (code !in 200..299) throw IllegalStateException("HTTP $code: $payload")
            return payload
        } finally {
            connection.disconnect()
        }
    }

    fun createSession(deviceName: String): String {
        val response = request("POST", "/v1/mobile/sessions",
            JSONObject().put("device_name", deviceName).toString()) ?: error("No session response")
        return JSONObject(response).getString("id")
    }

    fun submitMobileTask(prompt: String, budget: Double, sessionId: String): String {
        val response = request("POST", "/v1/tasks",
            JSONObject().put("prompt", prompt).put("budget_usd", budget)
                .put("complexity", "normal").put("target", "mobile")
                .put("mobile_session_id", sessionId).toString()) ?: error("No task response")
        return JSONObject(response).getString("id")
    }

    fun postObservation(sessionId: String, observation: JSONObject, screenshotB64: String?): JSONObject {
        val payload = JSONObject().put("observation", observation)
        if (screenshotB64 != null) payload.put("screenshot_b64", screenshotB64)
        return JSONObject(request("POST", "/v1/mobile/sessions/$sessionId/observation", payload.toString())
            ?: error("No observation response"))
    }

    fun pollCommand(sessionId: String): JSONObject? =
        request("GET", "/v1/mobile/sessions/$sessionId/command")?.let(::JSONObject)

    fun fetchScreen(taskId: String): ByteArray? {
        val url = URI.create(baseUrl.trimEnd('/') + "/v1/tasks/" + taskId + "/screen").toURL()
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 4000
            readTimeout = 8000
            doInput = true
        }
        try {
            return when (connection.responseCode) {
                200 -> connection.inputStream.use { stream -> stream.readBytes() }
                404, 409, 204 -> null
                else -> throw IllegalStateException("Screen HTTP " + connection.responseCode)
            }
        } finally {
            connection.disconnect()
        }
    }

    fun postCommandResult(sessionId: String, result: JSONObject, screenshotB64: String?): JSONObject {
        val payload = JSONObject().put("result", result)
        if (screenshotB64 != null) payload.put("screenshot_b64", screenshotB64)
        return JSONObject(request("POST", "/v1/mobile/sessions/$sessionId/command-result", payload.toString())
            ?: error("No command result response"))
    }
}
