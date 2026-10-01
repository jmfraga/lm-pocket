# Modelo de amenazas

Versión canónica: [threat-model.md](../threat-model.md).

LM-Pocket protege tu memoria **en reposo y en la frontera entre espacios**. No puede proteger lo que ya salió del pocket. Decirlo claro es parte del producto.

## De qué protege
- **USB perdido o robado:** SQLCipher en reposo, KEK derivada con Argon2id, ninguna copia en texto plano.
- **Un LLM de trabajo leyendo lo personal:** espacios aislados por defecto; el servidor aplica el perfil en cada llamada.
- **Un LLM escribiendo recuerdos falsos:** las propuestas siempre entran como candidatas.
- **Alteración silenciosa o exportaciones incompletas:** auditoría y manifiesto con conteos y SHA-256.
- **Que el proyecto desaparezca:** formato abierto y documentado; Apache-2.0 y CC-BY.
- **Passphrase olvidada:** clave de recuperación.

## De qué NO puede proteger
- **Lo que ya le mandaste a un modelo.** Lo que un LLM en la nube leyó queda del lado del proveedor. Desconectar el pocket detiene lecturas *futuras*, no pasadas.
- **Un equipo comprometido.** Si la computadora donde desbloqueas tiene malware, puede leer la RAM y la pantalla.
- **Que el modelo ignore "no guardes esto".** El pocket no puede obligarlo.
- **Que apruebes propuestas malas.** La compuerta vale lo que vale la revisión.
- **El puente remoto, si lo activas.** Suma al túnel, tu manejo de tokens y el cliente remoto a la frontera de confianza.
