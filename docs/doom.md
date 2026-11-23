# Módulo 9 · Doom jugado por IA (Databricks Apps)

Proyecto original: <https://github.com/ivancalvo-dbxs/doom-databricks> (Chocolate Doom GPL-2.0+, datos Freedoom).
No se copia a este repo: se despliega directo desde el original.

**Qué se muestra:** una aplicación web (Node.js) corriendo *dentro* de Databricks, con su propia
identidad (service principal) y autenticación SSO. El juego no se controla con teclado: en cada
paso el servidor manda el estado del juego a la API `ai_decide`, y un modelo elige la acción
(avanzar, girar, disparar…). Los estudiantes solo miran.

## Despliegue

```bash
git clone https://github.com/ivancalvo-dbxs/doom-databricks.git
cd doom-databricks
databricks bundle deploy -t dev --profile ulatina-demo --var app_name=doom-ulatina
databricks bundle run doom  -t dev --profile ulatina-demo --var app_name=doom-ulatina
```

URL: `https://doom-ulatina-<workspace-id>.aws.databricksapps.com`

## Requisitos y costos

- Requiere la preview **AI Decide** habilitada en el workspace. Si no está, el juego carga, pero
  el personaje no se mueve y la API responde `PERMISSION_DENIED` o un error 500.
- Cada decisión consume presupuesto. Las sesiones duran 15 minutos como máximo, se cortan tras 60 s sin actividad
  y caben 12 partidas simultáneas.
- Después de la clase: `databricks apps stop doom-ulatina` o
  `databricks bundle destroy -t dev --auto-approve --var app_name=doom-ulatina`.

## Plan B (si `ai_decide` no responde)

Mostrar la app igual (la UI, el log de decisiones, la identidad de la app en *Compute → Apps*) y
explicar la arquitectura. El patrón es el mismo de cualquier app que consulta un modelo servido
en Databricks.
