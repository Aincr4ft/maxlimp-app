# MAX LIMP — Informe de correcciones

**Fecha:** 07/11/2026
**Proyecto:** `maxlimp-app` (panel de inventario y pedidos)
**Ruta canónica:** `C:\Users\Romel Toalombo\OneDrive\Imágenes\maxlimp-app`

---

## 1. Resumen

Se revisó el proyecto completo (10 módulos, ~2.700 líneas) y se corrigieron los
errores **reales y verificables**, no los hipotéticos. Los cambios se agrupan en
cuatro frentes:

| Frente | Qué se corrigió |
|---|---|
| Capa de datos | Conexiones que se filtraban, errores silenciados, triggers frágiles, siembra de datos demo que "resucitaba" cuentas |
| Arranque / navegación | Mainloops anidados que rompían la app al cerrar sesión; ventana congelada al iniciar |
| Interfaz | Tablas que no se limpiaban (`_scrollable_frame` inexistente), errores de BD que no se mostraban, carrito que podía corromperse |
| Empaquetado / docs | `.env` no encontrado dentro del `.exe`, logo no incluido, instrucciones incorrectas |

**Estado:** todo compila e importa correctamente. Las pruebas automáticas que no
requieren base de datos pasan. La prueba contra la base real está pendiente
porque **Railway tiene el plan vencido** (ver §7).

---

## 2. Errores corregidos, archivo por archivo

### `base_de_datos/connection.py` — reescrito

| # | Error | Consecuencia real | Corrección |
|---|---|---|---|
| 1 | `load_dotenv()` no encontraba el `.env` al ejecutar el `.exe` | El ejecutable arrancaba sin credenciales y "no conectaba" sin explicación | `_ruta_env()`: en desarrollo busca en la raíz; empaquetado (`sys.frozen`) busca **junto al `.exe`** |
| 2 | Variables faltantes o `DB_PORT` no numérico daban errores crípticos | Difícil de diagnosticar | `_config_bd()` valida y dice exactamente qué falta |
| 3 | `ALTER TABLE usuarios MODIFY password_hash` en **cada arranque** | DDL innecesario y lento contra Railway en cada inicio | Solo ejecuta el `ALTER` si la columna mide menos de 255 (`information_schema`) |
| 4 | Triggers creados con `CREATE TRIGGER` a secas | Si ya existían, fallaba y el stock quedaba **sin validación** | `_asegurar_triggers()` consulta `information_schema` y crea/actualiza solo lo necesario (auto-reparable) |
| 5 | Trigger de validación **sin bloqueo de fila** | Dos pedidos simultáneos (panel + n8n/WhatsApp) podían **sobrevender** | `SELECT ... FOR UPDATE`; si el servidor no lo permite en triggers, cae a la versión sin bloqueo avisando por consola |
| 6 | `INSERT IGNORE` de usuarios demo en cada arranque | Borrabas `admin/admin123` desde el panel y **volvía a aparecer** al reiniciar | `_sembrar_usuarios_demo()` solo si la tabla `usuarios` está **vacía** |
| 7 | Productos demo insertados siempre | Duplicados / datos de prueba mezclados | Solo si `productos` está vacía |
| 8 | Cursor y conexión no se cerraban si algo fallaba | Fugas de conexiones contra el pool | `try/finally` en `inicializar_bd()` |
| 9 | `inicializar_bd()` no informaba resultado | La UI no sabía si la BD quedó lista | Devuelve `bool` |

### `base_de_datos/queries.py` — reescrito

| # | Error | Consecuencia real | Corrección |
|---|---|---|---|
| 1 | Cada función abría conexión/cursor sin `finally` | Conexiones filtradas; el pool se agotaba tras varios errores | Context manager `_conexion()` que cierra siempre |
| 2 | Sin BD, las funciones devolvían `[]` / `deque()` | La UI mostraba **"Sin datos"** en vez de "sin conexión": el problema real quedaba oculto | Lanza `ConnectionError("Sin conexión a la base de datos.")` |
| 3 | `_parse_fecha` devolvía `None` con fecha inválida | El filtro de fechas se **ignoraba en silencio** | Lanza `ValueError` con el formato esperado (`dd/mm/aaaa`) |
| 4 | `rowcount == 0` interpretado como "no existe" | Falso error *"No se encontró producto con ID X"* cuando el UPDATE solo dejaba el mismo valor | Se verifica con `_existe()` antes de fallar |
| 5 | Se podía eliminar/degradar **al último admin** | Sistema sin administradores, imposible de recuperar desde la UI | Guardas `_contar_admins()` en `editar_usuario` y `eliminar_usuario` |
| 6 | Upsert de cliente guardaba `NULL` si el vendedor dejaba nombre/dirección en blanco | **Borrado accidental** de los datos del cliente | `COALESCE(NULLIF(%s, ''), nombre)` |
| 7 | `crear_pedido` permitía vender productos dados de baja | Ventas de productos descontinuados | Valida `activo = TRUE` |
| 8 | `crear_pedido` confiaba en el precio que mandaba la UI | Posible manipulación de precio / datos obsoletos | Relee precio y stock de la BD con `FOR UPDATE` |
| 9 | `estadisticas_ventas_7_dias` usaba `INTERVAL 7 DAY` | Mostraba **8 días** (7 + hoy) | `INTERVAL 6 DAY` |
| 10 | Hashes legacy SHA-256 nunca se migraban | Contraseñas con protección débil para siempre | Migración automática a PBKDF2 al iniciar sesión correctamente |

### `login.py` — reescrito

| # | Error | Consecuencia real | Corrección |
|---|---|---|---|
| 1 | La conexión a Railway se hacía **en el hilo de la UI** | Ventana congelada hasta ~30 s (pool + conexión directa con timeout de 15 s) | Inicialización en **hilo secundario**; la ventana aparece al instante |
| 2 | Botón "Ingresar" activo antes de tener BD | Clics que fallaban sin explicación | Deshabilitado hasta que la BD responda |
| 3 | "Contraseña incorrecta" y "sin conexión" mostraban **el mismo mensaje** | Imposible saber qué pasaba | Mensajes diferenciados |
| 4 | La contraseña quedaba escrita tras un fallo | Mala experiencia / riesgo de mirada ajena | Se limpia el campo |
| 5 | `Enter` en la contraseña no enviaba | Obligaba a usar el mouse | `bind("<Return>", ...)` |
| 6 | Abría el panel llamando `VentanaAdmin().mainloop()` desde el callback | **Mainloops anidados** → `TclError: main thread is not in main loop` al cerrar | Solo asigna `siguiente_rol` y llama `quit()`; `main.py` decide |

### `main.py` — reescrito

| # | Error | Consecuencia real | Corrección |
|---|---|---|---|
| 1 | `mainloop()` anidado (login → panel → login dentro del mismo callback) | Cierres de sesión inestables y errores de Tcl | Controlador **secuencial**: `while True`, cada ventana corre su `mainloop` y devuelve el control |
| 2 | Callbacks `after` pendientes al destruir una ventana | Consola llena de `invalid command name "...check_dpi_scaling"` | `_destruir()` cancela los `after` pendientes antes de `destroy()` |

**Flujo nuevo:**

```
LoginApp.mainloop()  →  siguiente_rol?  ── None ──▶  salir
        │                    │
        │                 'admin'  ──▶ VentanaAdmin.mainloop()
        │                 'vendedor' ─▶ VentanaVendedor.mainloop()
        │                                    │
        └──────── cerrar_sesion=True ◀───────┘
```

### `visualizaciones/dashboard.py` — corregido

| # | Error | Consecuencia real | Corrección |
|---|---|---|---|
| 1 | `getattr(frame, "_scrollable_frame", frame)` | **customtkinter 5.2 NO tiene ese atributo**; el código limpiaba el frame equivocado → filas duplicadas y tablas que crecían sin parar | Se limpia `winfo_children()` del propio `CTkScrollableFrame` (4 tablas) |
| 2 | `_cerrar_sesion` destruía y abría el login con mainloop anidado | Error al cerrar sesión | `cerrar_sesion = True` + `quit()` |
| 3 | Sin manejo de errores en clientes / usuarios / gráficos / métricas | Una caída de BD rompía la ventana o dejaba la pantalla en blanco | `try/except` + etiquetas de error visibles |
| 4 | `_cargar_clientes` sin feedback | Parecía que no hacía nada | Etiqueta de estado ("Cargando…", "❌ …") |
| 5 | Aviso de stock decía *"súmale a la cantidad actual"* | Pero `actualizar_stock` **fija** el total, no suma → el usuario corrompía el stock | Texto corregido: *"Escribe el stock final; no se suma al actual"* |
| 6 | `except ValueError` en el popup de edición | `ConnectionError` se escapaba sin mostrarse | `except Exception` |
| 7 | Colores de etiquetas no se restauraban tras un error | Quedaban en rojo para siempre | Se resetean |
| 8 | Código muerto (`_scrollable_frame`, variables sin uso) | Confusión y bugs futuros | Eliminado |

### `visualizaciones/pedidos_panel.py` — corregido

| # | Error | Consecuencia real | Corrección |
|---|---|---|---|
| 1 | Mismo bug de `_scrollable_frame` | Catálogo y carrito no se limpiaban bien | Limpieza correcta del frame |
| 2 | `_renderizar_catalogo` borraba solo las filas **después** del encabezado | Cada búsqueda **duplicaba encabezados** y desalineaba las columnas | Se limpia todo y se repinta el encabezado |
| 3 | `_confirmar_pedido_bg` iteraba `self.carrito` en segundo plano | `RuntimeError: dictionary changed size during iteration` si el vendedor seguía tocando el carrito | Copia `dict(self.carrito)` |
| 4 | Carga de catálogo / búsqueda de cliente / historial sin manejo de errores | Fallos silenciosos | `try/except` con mensaje en pantalla |
| 5 | `_cerrar_sesion` con mainloop anidado | Error al cerrar sesión | `cerrar_sesion = True` + `quit()` |

### `visualizaciones/_widgets.py` — corregido

| # | Error | Consecuencia real | Corrección |
|---|---|---|---|
| 1 | `mostrar_detalle_pedido` sin `try/except` | Cualquier fallo de BD lanzaba excepción en el callback | Diálogo de error controlado |

### `cifrado.py` — corregido

| # | Error | Consecuencia real | Corrección |
|---|---|---|---|
| 1 | PBKDF2 con 100.000 iteraciones | Por debajo de la recomendación OWASP actual | 600.000 iteraciones |

> Los hashes ya guardados conservan su propio número de iteraciones, así que este
> cambio **no invalida ninguna contraseña existente**.

### Archivos nuevos

- **`verificar_conexion.py`** — diagnóstico de solo lectura. Comprueba `.env`,
  servidor MySQL, tablas y triggers **sin crear ni modificar nada**.
  ```
  python verificar_conexion.py
  ```

### `requisitos.txt` y `README.md`

- Añadido `pillow` (se usa `PIL` en `login.py` y en los gráficos).
- Comando de PyInstaller corregido: faltaba `--add-data "assets;assets"` (sin eso
  el `.exe` arranca sin logo) y se documenta copiar el `.env` junto al ejecutable.
- README con comandos de PowerShell (los de Linux fallaban en Windows) y sección
  del diagnóstico.

---

## 3. Verificación realizada

| Prueba | Resultado |
|---|---|
| `py_compile` de los 13 módulos | ✅ OK |
| Importación de todos los módulos | ✅ OK |
| `_parse_fecha` (válida / vacía / inválida) | ✅ OK |
| `cifrar_contrasena` / `verificar_contrasena` / hash legacy | ✅ OK |
| Flujo de login con BD simulada (`db_listo`, `db_ok`, `siguiente_rol`, sesión) | ✅ OK |
| Construcción de `VentanaAdmin` y `VentanaVendedor` + cierre de sesión | ✅ OK |
| `verificar_conexion.py` contra la BD real | ⚠️ Falla correctamente con mensaje claro (Railway caído) |
| Prueba contra la BD real (crear/editar/borrar) | ⏸ Bloqueada (§7) |

---

## 4. Sobre las otras copias del proyecto

En el equipo hay **tres** carpetas con el nombre `maxlimp-app`. Solo una sirve:

| Ruta | Estado |
|---|---|
| `OneDrive\Imágenes\maxlimp-app` | ✅ **Canónica**. Estructura completa, `.env`, repo git |
| `Pictures\maxlimp-app` | ❌ Copia plana rota: le faltan `base_de_datos/`, `visualizaciones/`, `assets/` y `.env`. Falla con `ModuleNotFoundError: No module named 'base_de_datos'` |
| `OneDrive\Desktop\MaxLimp_App` | ⚠️ Copia antigua (17/09) con su propio `venv`. No se tocó |

**Recomendación:** usar siempre la ruta de OneDrive y borrar o renombrar las otras
dos para no ejecutar la equivocada.

---

## 5. Cómo ejecutar

```powershell
cd "C:\Users\Romel Toalombo\OneDrive\Imágenes\maxlimp-app"
.\venv\Scripts\Activate.ps1
python verificar_conexion.py   # primero: ¿hay base de datos?
python main.py
```

---

## 6. Pendiente (no corregido, documentado)

Estos puntos **no son errores** que rompan la app, sino mejoras conocidas:

1. **Paginación** — las tablas cargan todos los registros. Con miles de pedidos se
   volverá lento.
2. **Normalización de teléfonos** — no se unifican formatos (`+593…`, `09…`) antes
   de buscar/crear cliente, así que el mismo cliente puede quedar duplicado. Es
   importante antes de conectar el flujo de WhatsApp/n8n.
3. **Tests automatizados de `queries.py`** — solo se probó con mocks; falta una BD
   de pruebas real.
4. **KPI "Ingresos"** incluye pedidos `pendiente` (no solo `confirmado`/`entregado`).
   Es una decisión de negocio: hoy suma todo lo no cancelado.
5. **IDs escritos a mano** en algunos popups del panel admin; sería mejor un
   selector.
6. **Credenciales demo visibles en el login** (`admin / admin123`). Se dejaron
   porque sirven para la demostración académica; conviene quitarlas en producción.

---

## 7. Nota sobre Railway

La base de datos **no está caída por un bug del código**: el plan de Railway está
vencido (`Lost connection ... reading initial communication packet`, error 2013).
No se modificó ni se creó nada en la base mientras estuvo inaccesible.

Cuando se renueve el plan:

1. Ejecutar `python verificar_conexion.py` y confirmar que aparecen las 5 tablas.
2. Ejecutar `python main.py` una vez: crea/actualiza triggers y siembra datos demo
   **solo si las tablas están vacías**.
3. Probar: login admin → crear producto → crear pedido → verificar que el stock
   bajó → cancelar pedido → verificar que el stock volvió.

---

## 8. Estado de los cambios

Los cambios están **en el árbol de trabajo, sin commit**. `git` no está instalado
en este equipo, así que no se pudo hacer commit ni push. Cuando lo instales:

```powershell
cd "C:\Users\Romel Toalombo\OneDrive\Imágenes\maxlimp-app"
git status
git add -A
git commit -m "Corrige fugas de conexion, mainloops anidados, triggers de stock y errores de UI"
git push
```

> ⚠️ El repositorio es **público**. Antes de hacer `git add -A` confirma que el
> `.env` sigue en `.gitignore` (hoy nunca se ha subido, pero verifícalo).
