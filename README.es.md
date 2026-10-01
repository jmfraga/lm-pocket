# LM-Pocket — Longitudinal Memory Pocket

**Tu memoria de IA, físicamente tuya.**

[English](README.md)

> Tu modelo puede cambiar. Tu historia no tiene por qué hacerlo.

LM-Pocket es una capa de memoria personal, portable, local-first, independiente del modelo y propiedad del usuario. Vive en una carpeta —en un USB, un SSD externo o tu laptop— y conserva tu contexto, preferencias, decisiones y aprendizajes a través del tiempo, sin importar qué LLM, aplicación, empresa o dispositivo uses.

**No** es un asistente ni un modelo. Es una **capa de continuidad**: almacenamiento, provenance, gobierno y control de acceso de tu memoria de largo plazo, expuesta a cualquier LLM por MCP o por puentes de copiar y pegar.

> **Estado:** etapa de especificación (borrador v0.2). Todavía no hay código. Es el momento ideal para sumarse y discutir el diseño.

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

- [docs/es/ESPECIFICACION.md](docs/es/ESPECIFICACION.md) — especificación del MVP (borrador v0.2)
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
