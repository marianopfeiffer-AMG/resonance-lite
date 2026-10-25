# Resonance Lite

**Hacé videos largos de sonido funcional para YouTube (lluvia, fogata, piano para dormir, playlists de lofi) con una sola frase en Claude Code.**

Es la herramienta detrás del canal Resonance, armada para que la uses en **tu** canal, con **tus** cuentas y en **tu** computadora.

```
/resonance-lite lluvia sobre una carpa, 2 horas
```
Más o menos una hora después tenés una carpeta con el video terminado, la miniatura y una hoja con título, descripción, capítulos y etiquetas lista para pegar en YouTube Studio.

> 🧪 **Beta privada.** Sos de los primeros en probarlo. Contá todo lo que te confunda, aunque parezca chico (ver [Feedback de la beta](#feedback-de-la-beta)).

> English version: [README.md](README.md)

---

## Qué hace

- 🎧 **Tres tipos de audio.** `ambient` (lluvia, fuego, olas, bosque), `functional` (música lenta de una textura: piano para dormir, pads, binaural) y `playlist` (muchos temas distintos con capítulos).
- 🎞️ **Imagen que no se nota que se repite.** Una foto que "respira" durante horas (cinemagraph), una imagen fija o una imagen o video tuyo.
- 💸 **El costo antes de gastar.** Cada video muestra cuánto va a costar en dólares antes de generar nada, con topes por video y por mes.
- 🔁 **Se puede retomar.** Si se corta internet, se cierra la compu o se acaban los créditos, retomás sin pagar dos veces lo que ya se generó.
- ✅ **Control de calidad.** Sin silencios, sin golpes de volumen y sin costura visible en el loop, verificado automáticamente.
- 🧑‍🎨 **Decidís vos.** Una aprobación por video. Nada se genera en serie ni se publica solo.

Claude es el director creativo: concepto, composición, prompts y SEO. Un programa chico, `rlite`, hace el trabajo que cuesta plata: llama a los servicios, arma el video con ffmpeg y lleva el estado y el presupuesto.

---

## Qué necesitás

- **Claude Code.**
- **macOS** o **Linux** (Windows con WSL2 es experimental).
- Una cuenta de **[ElevenLabs](https://elevenlabs.io)**. Para uso comercial hace falta un plan pago; el gratis exige mencionar a ElevenLabs y no permite monetizar.
- *Opcional:* **[Higgsfield](https://higgsfield.ai)** para imágenes animadas. Sin eso, usás fondos fijos.
- *Opcional:* **Suno vía [Apiframe](https://apiframe.ai)** para playlists. Viene apagado; leé los [riesgos](#riesgos-leelo) antes.
- Unos 10 GB libres mientras se produce un video de 2 horas.

---

## Instalación (beta)

Necesitás acceso a este repo privado y estar logueado en GitHub en tu compu (`gh auth login`), además de [uv](https://docs.astral.sh/uv/).

**1. Instalá el programa** (en tu terminal)
```bash
uv tool install "resonance-lite[stabilize] @ git+https://github.com/marianopfeiffer-AMG/resonance-lite@cli-v0.9.0#subdirectory=cli"
```

**2. Agregá el plugin** (en Claude Code)
```
/plugin marketplace add marianopfeiffer-AMG/resonance-lite
/plugin install resonance-lite@resonance-lite
```

**3. Corré la configuración guiada** (en Claude Code)
```
/resonance-lite setup
```
Claude revisa tu compu y te dice exactamente qué correr para lo que falte. Dos cosas pasan **fuera** del chat, en otra ventana de terminal:
- **Tu clave de ElevenLabs.** Cada usuario usa la suya. Corré `rlite key set elevenlabs` (se escribe oculta), o copiala y corré `rlite key set elevenlabs --from-clipboard`. Queda guardada en el llavero de tu sistema. **Nunca pegues claves en el chat de Claude**: Claude tiene instrucciones de no aceptarlas y `rlite` se niega a leer claves si no lo corrés vos en tu terminal.
- **El login de Higgsfield** (opcional): `higgsfield auth login`.

**4. Hacé un video de prueba** (unos 10 minutos, menos de 1 dólar)
```
/resonance-lite demo
```

> Si `/resonance-lite` choca con otro comando, usá el nombre completo: `/resonance-lite:resonance-lite`.

---

## Uso

```
/resonance-lite fogata para dormir, 90 minutos
/resonance-lite playlist de lofi para estudiar, 2 horas
/resonance-lite resume <job>        # retomar un trabajo cortado
/resonance-lite next                # tomar la próxima idea de tu backlog
```

1. Claude diseña el video y lo controla contra las reglas de composición.
2. Ves **un único punto de aprobación**: concepto, lista de temas, título, la imagen y el costo. Aprobás o pedís cambios.
3. El audio y la imagen se producen en segundo plano. Podés cerrar Claude Code; preguntá "¿cómo va mi video?" cuando quieras.
4. Control de calidad automático.
5. Te queda `~/ResonanceLite/jobs/<id>/final/` con `video.mp4`, `thumbnail.png` y `UPLOAD.md` (título, descripción con capítulos, etiquetas y la lista para YouTube Studio).

**Lo subís vos en YouTube Studio** (5 minutos, todo listo para pegar). Ver [docs/upload-in-studio.md](docs/upload-in-studio.md).

**Los cambios de dirección son gratis.** "Sacá los temas 2 y 6" rearma la playlist sin regenerar nada.

---

## Cuánto cuesta

Le pagás directo a cada servicio. Aproximado, octubre 2026:

| Por video | Con imagen animada | Con imagen fija |
|---|---|---|
| Ambient, 90 min | ~USD 4-6 | ~USD 1-2 |
| Música funcional, 90 min | ~USD 10-11 | ~USD 7 |
| Playlist 2 h (ElevenLabs) | ~USD 23-24 | ~USD 20 |
| Playlist 2 h (Suno, opcional) | ~USD 8 | ~USD 5 |

Lo que pagás aunque hagas pocos videos son las suscripciones, porque varios servicios vencen los créditos a fin de mes:
- 4 videos de sonidos naturales por mes: unos USD 40-45.
- 4 de música: unos USD 115-120 (hace falta ElevenLabs Pro).

Detalle en [docs/costs.md](docs/costs.md).

---

## Riesgos (leelo)

- **Política de "contenido inauténtico" de YouTube.** Desde julio de 2026 YouTube desmonetiza y saca contenido de IA hecho en serie y con poca variación. La herramienta mantiene a una persona en el medio a propósito y varía imágenes y miniaturas, pero **nada garantiza la monetización**.
- **Declarar el contenido sintético.** Si la imagen parece real, hay que marcar "contenido alterado o sintético" en Studio. El `UPLOAD.md` te lo recuerda.
- **Derechos de la música.**
  - Los planes pagos de ElevenLabs incluyen uso comercial.
  - **Suno vía Apiframe es riesgoso para canales que monetizan**: Suno no tiene API oficial, da derechos de uso y no propiedad, y la cuenta que genera no es la tuya. Por eso viene apagado.
- **Monetizar lleva tiempo.** YouTube pide 1.000 suscriptores y 4.000 horas vistas. Los primeros meses son solo gasto.
- No es asesoramiento legal. El software se entrega "tal cual" (licencia MIT).

---

## Privacidad

Sin telemetría. `rlite` solo habla con los servicios que configurás. La única excepción es un chequeo de versión nueva una vez por día, opcional, que no manda datos; se apaga con `RL_NO_UPDATE_CHECK=1`. Tus claves viven en el llavero de tu sistema.

---

## Feedback de la beta

Después de cada video, abrí un issue con la plantilla **Beta feedback**:
- tiempo total;
- dónde te trabaste;
- costo estimado contra el real (mirá los paneles de los servicios);
- calidad del 1 al 5;
- qué cambiarías.

Para algo que te bloquea, escribile a Nano directo. Para reportar un error, pegá la salida de `rlite doctor --report`: nunca incluye claves ni rutas personales.

---

## Créditos

Hecho por **Mariano "Nano" Pfeiffer**. Las reglas de composición y audiencia de `plugin/skills/resonance-lite/knowledge/` se desarrollaron para el canal **Resonance**. Los canales hechos con esta herramienta son independientes y no tienen relación con Resonance.

## Licencia

[MIT](LICENSE) © Mariano Pfeiffer
