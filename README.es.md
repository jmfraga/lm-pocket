# LM-Pocket — Longitudinal Memory Pocket

**Tu memoria de IA, físicamente tuya.**

[English](README.md)

> Tu modelo puede cambiar. Tu historia no tiene por qué hacerlo.

LM-Pocket es una capa de memoria personal, portable, local-first, independiente del modelo y propiedad del usuario. Vive en una carpeta —en un USB, un SSD externo o tu laptop— y conserva tu contexto, preferencias, decisiones y aprendizajes a través del tiempo, sin importar qué LLM, aplicación, empresa o dispositivo uses.

**No** es un asistente ni un modelo. Es una **capa de continuidad**: almacenamiento, provenance, gobierno y control de acceso de tu memoria de largo plazo, expuesta a cualquier LLM por MCP o por puentes de copiar y pegar.

> **Estado:** prototipo v0.1. La primera demo funciona de punta a punta sobre un volumen tipo USB real: pocket cifrado, desbloqueo con passphrase, lecturas MCP limitadas por perfil, propuestas aprobadas en la UI local, importación/exportación por prompt y corte del acceso MCP al bloquear o desconectar. **Sin auditoría de seguridad: todavía no para secretos reales.** Especificación congelada en el tag `spec-v0.2-frozen`.

## Inicio rápido

Necesitas [uv](https://docs.astral.sh/uv/). Para máquinas sin internet: [docs/offline.md](docs/offline.md).

```bash
git clone https://github.com/jmfraga/lm-pocket && cd lm-pocket
uv sync
uv run lm-pocket init /Volumes/MiUSB/LM-Pocket --sample   # muestra la clave de recuperación una sola vez
uv run lm-pocket open /Volumes/MiUSB/LM-Pocket            # abre la UI local; desbloquea ahí
```

La página de inicio muestra la configuración MCP exacta de cada perfil. Para Claude Code:

```bash
claude mcp add pocket-work -- "$(uv run which python)" -m lm_pocket mcp --profile work
```

Mira la [primera demo](docs/demo.md) (incluye una sesión real con Claude) o córrela en macOS con una imagen de disco exFAT desechable: `uv run python scripts/demo_usb_macos.py`.

## Por qué

Todos los proveedores de IA están construyendo memoria, y todos la guardan en sus servidores, en su formato y con sus reglas. Cambias de proveedor y empiezas de cero. Pierdes la cuenta y tu historia se va con ella.

LM-Pocket apuesta por lo contrario: **la copia canónica de tu memoria te pertenece**, en un formato abierto, y el modelo es un procesador reemplazable que solo lee lo que tú permites.

## Qué lo hace distinto

Hay piezas de esto en otros lados (motores de memoria, servidores MCP de memoria, formatos de memoria portable). Lo que LM-Pocket combina:

- **Físicamente tuya** — la copia canónica es una carpeta que puedes desconectar.
- **Espacios** — `personal`, `portable_professional`, `work:<id>`… aislados por defecto. El LLM de tu empresa nunca ve tu vida personal ni los secretos de tu empleador anterior.
- **Propuesta → revisión → definitiva** — ningún LLM escribe directo en tu memoria canónica.
- **Provenance en todo** — cada memoria responde *"¿de dónde salió esto?"* y las inferencias se distinguen de lo que tú declaraste.
- **Experiencia portable** — conservas la *lección* ("validar hipótesis pequeñas antes de escalar") sin cargar el *dato propietario* del que salió.
- **Formato de exportación abierto** — nada debe impedir que otro programa lea tu memoria.

## Cómo se conectan los modelos

| Cliente | Vía | Notas |
|---|---|---|
| Claude Desktop / Claude Code / Cursor | MCP local (stdio) | Nativo; solo sale de tu máquina lo que el modelo lee. |
| Gemini CLI | MCP local (stdio) | Soporte MCP nativo. |
| Modelos locales (LM Studio, Open WebUI, clientes sobre Ollama) | MCP local (stdio o HTTP) | Totalmente offline de punta a punta. |
| ChatGPT | **Puente** MCP remoto (Cloudflare Tunnel o similar) o puente por prompt | ChatGPT solo acepta MCP remoto por HTTPS. Opcional, apagado por defecto. Ver [docs/es/puente.md](docs/es/puente.md). |
| App de Gemini y otros chats cerrados | Puente por prompt | Pegas un paquete de contexto; pegas de vuelta la exportación de memoria del modelo. |

El soporte de los clientes cambia rápido — ver [docs/mcp.md](docs/mcp.md) y por favor manda correcciones.

## Documentos

- [docs/es/ESPECIFICACION.md](docs/es/ESPECIFICACION.md) — especificación del MVP (v0.2, congelada para v0.1)
- [docs/demo.md](docs/demo.md) — la primera demo con salida real · [docs/spec-conflicts.md](docs/spec-conflicts.md) — conflictos encontrados al implementar
- [docs/es/modelo-de-amenazas.md](docs/es/modelo-de-amenazas.md) — de qué protege LM-Pocket y de qué no puede
- [docs/es/puente.md](docs/es/puente.md) — puente de solo lectura para ChatGPT y clientes remotos
- [ROADMAP.md](ROADMAP.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [schemas/](schemas/) · [examples/](examples/)

La versión en inglés es la canónica; si hay discrepancia, manda un PR para alinearlas.

## Principios que no deben romperse

1. La memoria pertenece al usuario.
2. El sistema funciona offline.
3. Un LLM nunca escribe directamente la memoria canónica.
4. Los espacios están aislados por defecto.
5. Todo recuerdo tiene provenance.
6. El formato es exportable.
7. MCP es una interfaz, no la memoria.
8. El modelo es reemplazable.
9. El usuario puede desconectar físicamente su memoria.
10. La desaparición del desarrollador no debe destruir la historia del usuario.

## Licencia

- Código: [Apache-2.0](LICENSE)
- Especificación, documentación y esquemas: [CC-BY-4.0](LICENSE-SPEC)

El negocio, si algún día existe, puede vivir en hardware, UX, soporte, administración empresarial, sync opcional o servicios gestionados. **Nunca en cobrar renta por acceder a tu propia memoria.**
