# Puente remoto (ChatGPT y otros clientes que solo aceptan MCP remoto)

Versión canónica con comandos completos: [bridge.md](../bridge.md).

> **Opcional, apagado por defecto, planeado para v0.2.** Un puente pone tu pocket en internet; rompe "funciona offline" a propósito.

ChatGPT solo se conecta a servidores MCP accesibles por HTTPS público. El puente es el MCP local de LM-Pocket en modo HTTP, publicado con un túnel (Cloudflare Tunnel, Tailscale Funnel o ngrok).

```text
ChatGPT → HTTPS → borde de Cloudflare → cloudflared en tu máquina → lm-pocket bridge (localhost) → pocket
```

## Reglas duras
1. **Un solo perfil, nunca `personal`** ni memorias sensibles o confidenciales.
2. **Solo leer y proponer.**
3. **Con caducidad:** `--ttl` obligatorio (2 h por defecto).
4. **Autenticado:** OAuth 2.1 (lo mejor), token en encabezado si el cliente lo permite, o ruta con token impredecible como último recurso.
5. **Con límite de peticiones y auditoría.**
6. **Interruptor:** bloquear el pocket o cerrar la app apaga el puente al instante.

## Prueba rápida
```bash
lm-pocket bridge --profile work --ttl 2h --port 7421
cloudflared tunnel --url http://localhost:7421
```
Agrega `https://<aleatorio>.trycloudflare.com/mcp` como conector en ChatGPT. Para uso diario, un túnel con nombre en tu propio dominio.

Verifica las opciones de autenticación vigentes de cada cliente antes de confiar en ellas: cambian seguido.
