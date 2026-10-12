# Frontend

`solicitudes.service.ts` y `analizar-solicitud.component.ts` son archivos sueltos, sin proyecto de Angular alrededor. Se comprobó que compilan en un proyecto nuevo de Angular 22; no se probaron en el navegador.

## Token de Microsoft Entra ID en cada petición

1. Registrar el frontend en Entra ID como **SPA** (cliente público): usa Authorization Code con **PKCE** y no tiene secreto de cliente.
2. Registrar la API como otra aplicación que expone un alcance, por ejemplo `api://<id-de-la-api>/Solicitudes.Analizar`.
3. Usar `@azure/msal-angular`: `MsalGuard` exige iniciar sesión y `MsalInterceptor` se registra como interceptor HTTP.
4. En `protectedResourceMap` se asocia la URL de la API con ese alcance. El interceptor obtiene el token de acceso (en silencio, renovándolo si venció) y agrega `Authorization: Bearer <token>` solo a esas peticiones.
5. El servicio y el componente no cambian: no conocen el token.
6. En el navegador solo quedan el `clientId` y el `tenantId`, que son identificadores y no secretos. La caché de tokens va en `sessionStorage`, no en `localStorage`.
7. La API valida el token en cada petición: firma, emisor, audiencia y alcance. Hoy no lo hace; está listado como pendiente en el README principal.
