package app.alcancia.carpeta

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.activity.result.ActivityResult
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * La copia para el celular que deja el Mac en la nube de la persona (Google Drive, OneDrive, Dropbox…): la persona elige el archivo
 * una vez con el selector del sistema (Storage Access Framework) y Alcancía se queda con un permiso persistente de solo lectura para
 * volver a leerlo al abrir y al volver a primer plano. Alcancía no se conecta a ninguna nube: lee el archivo que el sistema le muestra.
 * El archivo ya viene cifrado (ui/copia.js lo abre en la interfaz); aquí solo se lee el texto.
 * Además: la última copia que se abrió bien (para mirar sin conexión), la llave recordada (solo si la persona lo pidió; cifrada con
 * una llave del Android Keystore que no sale del equipo) y los ajustes del teléfono (idioma, bienvenida, avisos).
 *
 * JS: Carpeta.elegir() → {nombre, texto}     Carpeta.leer() → {nombre, texto}  (SIN_ARCHIVO si nunca eligió; ARCHIVO si no se pudo)
 *     Carpeta.olvidar()   Carpeta.guardarCache({texto})   Carpeta.leerCache() → {texto?}
 *     Carpeta.guardarLlave({valor})   Carpeta.leerLlave() → {valor?}   Carpeta.borrarLlave()
 *     Carpeta.guardarAjustes({texto})   Carpeta.leerAjustes() → {texto?}          Cancelar el selector: error con código CANCELADO.
 */
@CapacitorPlugin(name = "Carpeta")
class CarpetaPlugin : Plugin() {
    private val maximo = 100L * 1024 * 1024 // una copia más grande que esto no es de Alcancía
    private val alias = "alcancia.copia"

    private fun prefs() = context.getSharedPreferences("alcancia.celular", Context.MODE_PRIVATE)
    private fun rutaCache() = File(context.noBackupFilesDir, "copia.alcancia")

    // ───────────── El archivo de la nube ─────────────

    @PluginMethod
    fun elegir(call: PluginCall) {
        val intento = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }
        startActivityForResult(call, intento, "alElegir")
    }

    @ActivityCallback
    private fun alElegir(call: PluginCall?, resultado: ActivityResult) {
        if (call == null) return
        val uri = resultado.data?.data
        if (resultado.resultCode != Activity.RESULT_OK || uri == null) {
            call.reject("cancelado", "CANCELADO")
            return
        }
        // Permiso persistente de solo lectura: así se vuelve a leer sin preguntar. Si el proveedor no lo da, igual se lee esta vez.
        try {
            context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (e: SecurityException) {
            // sigue sin permiso persistente
        }
        val anterior = prefs().getString("uri", null)
        if (anterior != null && anterior != uri.toString()) soltar(Uri.parse(anterior))
        prefs().edit().putString("uri", uri.toString()).apply()
        Thread { responder(call, uri) }.start()
    }

    @PluginMethod
    fun leer(call: PluginCall) {
        val guardada = prefs().getString("uri", null)
        if (guardada == null) {
            call.reject("Todavía no eliges el archivo.", "SIN_ARCHIVO")
            return
        }
        Thread { responder(call, Uri.parse(guardada)) }.start()
    }

    private fun responder(call: PluginCall, uri: Uri) {
        try {
            var nombre = "Alcancia-celular.alcancia"
            var tamano = 0L
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                if (c.moveToFirst()) {
                    if (!c.isNull(0)) nombre = c.getString(0)
                    if (!c.isNull(1)) tamano = c.getLong(1)
                }
            }
            if (tamano > maximo) throw IllegalStateException("muy grande")
            // El tamaño que dice el proveedor puede faltar o mentir: se lee con tope igual (sin quedarse sin memoria).
            val texto = context.contentResolver.openInputStream(uri)?.use { leerConTope(it).toString(Charsets.UTF_8) }
                ?: throw IllegalStateException("sin entrada")
            val r = JSObject()
            r.put("nombre", nombre)
            r.put("texto", texto)
            call.resolve(r)
        } catch (e: Exception) {
            call.reject("No pude leer el archivo.", "ARCHIVO")
        }
    }

    /** Lee todo el archivo, pero nunca más de `maximo` bytes (si hay más, no es una copia de Alcancía). */
    private fun leerConTope(entrada: InputStream): ByteArray {
        val salida = ByteArrayOutputStream()
        val trozo = ByteArray(64 * 1024)
        var total = 0L
        while (true) {
            val n = entrada.read(trozo)
            if (n < 0) break
            total += n
            if (total > maximo) throw IllegalStateException("muy grande")
            salida.write(trozo, 0, n)
        }
        return salida.toByteArray()
    }

    private fun soltar(uri: Uri) {
        try {
            context.contentResolver.releasePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (e: Exception) {
            // ya no estaba
        }
    }

    /** Desconectar este teléfono: sin permiso para leer el archivo, sin la última copia y sin la llave (los ajustes quedan). */
    @PluginMethod
    fun olvidar(call: PluginCall) {
        prefs().getString("uri", null)?.let { soltar(Uri.parse(it)) }
        prefs().edit().remove("uri").remove("llave").apply()
        rutaCache().delete()
        call.resolve()
    }

    // ───────────── La última copia que se abrió bien (sigue cifrada) ─────────────

    @PluginMethod
    fun guardarCache(call: PluginCall) {
        val texto = call.getString("texto")
        if (texto == null || texto.length > maximo) {
            call.reject("Falta la copia.", "COPIA")
            return
        }
        try {
            val tmp = File(context.noBackupFilesDir, "copia.alcancia.tmp")
            tmp.writeText(texto, Charsets.UTF_8)
            if (!tmp.renameTo(rutaCache())) throw IllegalStateException("no se pudo renombrar")
            call.resolve()
        } catch (e: Exception) {
            call.reject("No pude guardar la copia.", "COPIA")
        }
    }

    @PluginMethod
    fun leerCache(call: PluginCall) {
        val r = JSObject()
        try {
            val f = rutaCache()
            if (f.exists() && f.length() <= maximo) r.put("texto", f.readText(Charsets.UTF_8))
        } catch (e: Exception) {
            // sin copia guardada
        }
        call.resolve(r)
    }

    // ───────────── La llave recordada (cifrada con una llave del Android Keystore, que no sale del equipo) ─────────────

    private fun llaveDelEquipo(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return gen.generateKey()
    }

    @PluginMethod
    fun guardarLlave(call: PluginCall) {
        val valor = call.getString("valor")
        if (valor.isNullOrEmpty() || valor.length > 4096) {
            call.reject("Falta la llave.", "LLAVE")
            return
        }
        try {
            val cifra = Cipher.getInstance("AES/GCM/NoPadding")
            cifra.init(Cipher.ENCRYPT_MODE, llaveDelEquipo())
            val datos = cifra.doFinal(valor.toByteArray(Charsets.UTF_8))
            val guardado = Base64.encodeToString(cifra.iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(datos, Base64.NO_WRAP)
            prefs().edit().putString("llave", guardado).apply()
            call.resolve()
        } catch (e: Exception) {
            call.reject("No pude guardar la llave.", "LLAVE")
        }
    }

    @PluginMethod
    fun leerLlave(call: PluginCall) {
        val r = JSObject()
        val guardado = prefs().getString("llave", null)
        if (guardado != null) {
            try {
                val partes = guardado.split(":")
                val cifra = Cipher.getInstance("AES/GCM/NoPadding")
                cifra.init(Cipher.DECRYPT_MODE, llaveDelEquipo(), GCMParameterSpec(128, Base64.decode(partes[0], Base64.NO_WRAP)))
                r.put("valor", String(cifra.doFinal(Base64.decode(partes[1], Base64.NO_WRAP)), Charsets.UTF_8))
            } catch (e: Exception) {
                prefs().edit().remove("llave").apply() // ya no se puede abrir (p. ej. se restauró en otro equipo): se pide la frase
            }
        }
        call.resolve(r)
    }

    @PluginMethod
    fun borrarLlave(call: PluginCall) {
        prefs().edit().remove("llave").apply()
        call.resolve()
    }

    // ───────────── Ajustes del teléfono (idioma, bienvenida, avisos: nada secreto) ─────────────

    @PluginMethod
    fun guardarAjustes(call: PluginCall) {
        val texto = call.getString("texto")
        if (texto == null || texto.length > 16384) {
            call.reject("Faltan los ajustes.", "AJUSTES")
            return
        }
        prefs().edit().putString("ajustes", texto).apply()
        call.resolve()
    }

    @PluginMethod
    fun leerAjustes(call: PluginCall) {
        val r = JSObject()
        prefs().getString("ajustes", null)?.let { r.put("texto", it) }
        call.resolve(r)
    }
}
