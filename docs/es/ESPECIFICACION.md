# LM-Pocket — Especificación del MVP

**Versión:** 0.2 (borrador) · **Estado:** abierta a discusión.
**Canónica:** [SPEC.md](../../SPEC.md) en inglés. Esta versión resume cada sección; si hay discrepancia, manda la inglesa.

**Objetivo:** una memoria longitudinal personal, portable, local-first, independiente del modelo y propiedad del usuario, que vive en una carpeta (USB/SSD/laptop) y se consulta por MCP o por puentes de prompt.

## 1. Principio
> **Tu memoria de IA debe pertenecerte a ti, no al proveedor del modelo.**

LM-Pocket no es asistente ni modelo: es una **capa de continuidad** que conserva contexto, memoria, preferencias, aprendizajes y provenance, sin importar el LLM, la app, la empresa o el dispositivo.

## 2. Arquitectura
Carpeta de datos (cifrada por la app) → **LM-Pocket Local** (UI en localhost, servidor MCP, importar/exportar) → tres caminos:
- **MCP local** (stdio o HTTP en localhost): Claude, Cursor, Gemini CLI, modelos locales.
- **Puente remoto opcional** (túnel HTTPS): ChatGPT y clientes que solo aceptan MCP remoto.
- **Puente por prompt** (copiar/pegar): app de Gemini y cualquier chat cerrado.

## 3. Alcance v0.1
Incluye: carpeta cifrada, desbloqueo con passphrase, SQLite + FTS5, espacios, provenance, flujo propuesta → revisión → definitiva (con revisión por lotes y reglas simples), MCP local, UI en localhost, puente por prompt, exportación completa, auditoría, perfiles de permisos.
Fuera: vectores, grafos, sync en la nube, fine-tuning, modelos integrados, multiusuario, app móvil, hardware propio, instaladores firmados, puente remoto (v0.2).

## 4. Almacenamiento y cifrado
**Decisión:** el cifrado lo hace **la app**, no el volumen. APFS, BitLocker, LUKS y VeraCrypt no son portables entre sistemas sin drivers. El USB es una carpeta exFAT y abre igual en macOS, Windows y Linux.

```text
passphrase → Argon2id → KEK → desenvuelve DEK → base SQLCipher
```
La passphrase nunca es la clave; cambiarla solo re-envuelve la DEK. Una **clave de recuperación** se genera una vez al crear el pocket. Solo librerías maduras.

## 5. Distribución
v0.1: `uvx lm-pocket --data /Volumes/MiUSB/LM-Pocket`. Binarios firmados, después.

## 6. Flujo
Conectar USB → abrir LM-Pocket Local → passphrase → elegir perfil → MCP disponible → conectar LLM. Bloquear o desconectar → las claves se borran de memoria y el MCP responde "pocket bloqueado".

## 7. Modelo de memoria
Campos: `id` (UUIDv7), `content`, `type` (fact, preference, event, interpretation, skill, decision, relationship, goal), `status` (candidate, durable, archived, rejected), `space`, `sensitivity`, `portable`, `source_type` (user, llm, imported, derived), `provenance` (provider, model, client, method, conversation_ref, recorded_at), `confidence`, fechas, `derived_from`, `supersedes`, `tags`.
Se eliminó `visibility`: se traslapaba con `space` + `portable`. Un solo mecanismo de acceso.

## 8. Propuestas
Ningún LLM escribe directo a la memoria canónica. Para que revisar no se vuelva un trámite: revisión por lotes, detección de duplicados, reglas automáticas opcionales (apagadas por defecto, registradas y reversibles) y caducidad de candidatas sin revisar.

## 9. Espacios
`personal`, `portable_professional`, `work:<id>`, `shared`, `public`. **Ningún espacio lee otro sin autorización explícita.**

## 10. Experiencia portable
Guardar la *lección* sin el *dato propietario*. La memoria derivada enlaza a su origen, pero **exportarla nunca exporta el origen**.

## 11. Perfiles de permisos
Un MCP local por stdio no puede verificar qué cliente lo lanzó. Por eso cada entrada MCP del cliente lleva un **perfil con nombre** (`--profile work`), y el servidor aplica sus reglas en cada llamada. Por MCP nunca se escriben memorias definitivas, se borran ni se cambian políticas: eso solo pasa en la UI local.

## 12. MCP
Herramientas: `pocket.search_memories`, `get_memory`, `get_context`, `get_recent_context`, `get_profile`, `list_spaces`, `propose_memory`, `get_policies`. **Nunca enviar todo el corpus al LLM**: el compilador de contexto respeta un presupuesto de tokens y devuelve provenance con cada elemento.

## 13. Niveles de conexión
1. MCP local — Claude Desktop/Code, Cursor, Gemini CLI, LM Studio, Open WebUI.
2. Puente MCP remoto (opcional) — ChatGPT. Ver [puente.md](puente.md).
3. Adaptador de API (después) — endpoints compatibles con OpenAI, modelos locales sin interfaz de chat.
4. Puente por prompt — app de Gemini, cualquier chat cerrado.

## 14. Puente por prompt
**Importar:** LM-Pocket genera un prompt; el modelo devuelve lo que sabe del usuario en JSON lines; se pega en `localhost/import`, se previsualiza, se edita y entra **como candidatas** con provenance. El parser tolera prosa y bloques de código alrededor del JSON.
**Paquete de contexto:** bloque por propósito y espacio, con la instrucción "no guardes esto en tu propia memoria". Nunca "todo".

## 15–18. Seguridad, equipos ajenos, provenance y auditoría
Local-first, cifrado en reposo, mínimo privilegio, cero confianza entre espacios, bloqueo rápido, exportación explícita, el usuario conserva las claves. Lo que **no** se puede proteger está en el [modelo de amenazas](modelo-de-amenazas.md). Toda memoria responde "¿de dónde salió?"; las inferencias se distinguen de lo que el usuario declaró. La auditoría registra eventos, no contenido sensible.

## 19. Formato de exportación
`manifest.json` (con conteo de registros y SHA-256 por archivo), `memories.jsonl`, `spaces.json`, `policies.json`, `audit.jsonl`. El provenance vive dentro de cada memoria. Un importador debe **verificar conteos y checksums antes de leer el contenido**. Exportaciones cifradas por defecto. Ver [memory-format.md](../memory-format.md).

## 20–21. Requisitos
FR-01 a FR-16 como en la versión inglesa, incluido **FR-16: bloquear o desconectar hace que toda llamada MCP responda "bloqueado"**. No funcionales: un comando para arrancar; la misma carpeta abre en los tres sistemas; cambiar de SQLite a otro motor no cambia el contrato MCP ni el formato; búsqueda en inglés y español sin depender de acentos.

## 22. Stack sugerido
Python + FastAPI, SQLCipher + FTS5, Jinja/HTMX, SDK oficial de MCP, `argon2-cffi` + `cryptography`, `uv`.

## 23. Primera demo
USB → `uvx lm-pocket` → passphrase → 10 memorias ficticias → conectar Claude (u otro) con perfil `work` → pregunta que depende de memoria, con provenance → mostrar que `personal` **no** es alcanzable desde `work` → el modelo propone una memoria → aprobarla en localhost → desconectar el USB → repetir la pregunta: "pocket bloqueado".

## 24. Cambios respecto a v0.1
Cifrado en la app y no en el volumen · perfiles en lugar de "MCP valida identidad" · ChatGPT por puente remoto o prompt · Gemini y modelos locales cubiertos · `uvx` en lugar de instaladores firmados · revisión por lotes y reglas · se quita `visibility` · provenance dentro de cada memoria y manifiesto con checksums · modelo de amenazas explícito.

## 25. Hipótesis
> Una memoria longitudinal personal puede residir físicamente bajo control del usuario y dar continuidad útil entre distintos LLMs sin depender de un proveedor ni de una suscripción permanente.

**Soberanía + continuidad + interoperabilidad + provenance + control de contexto.** Nada más, hasta que funcione de punta a punta.
