# MAX LIMP — Panel de Inventario y Pedidos

Adaptación del proyecto académico **Auratec** (Python + CustomTkinter + MySQL en
Railway) para el uso real de **Max Limp**, empresa de venta de productos de
limpieza. Este panel es la pieza "Panel administrativo" del proyecto completo
descrito en el documento de contexto (base de datos + panel + automatización
de WhatsApp vía n8n).

## Qué cambió respecto a Auratec

- **Esquema de base de datos**: se reemplazó `usuarios (cliente) / ventas / ordenes /
  detalle_orden` por el esquema oficial del proyecto: `productos`, `clientes`,
  `pedidos`, `detalle_pedido` — **el mismo que usará el workflow de n8n** para
  registrar los pedidos que lleguen por WhatsApp. Un pedido hecho desde este
  panel y uno hecho desde WhatsApp quedan guardados exactamente igual.
- **Trigger `descontar_stock`**: se crea automáticamente al iniciar la app
  (`base_de_datos/connection.py`). Descuenta el stock en cada `INSERT` sobre
  `detalle_pedido`, sin importar si lo insertó este panel o el nodo MySQL de n8n.
- **Tabla `usuarios`** se mantiene, pero ahora es *solo* para el personal que
  usa el panel (roles `admin` / `vendedor`) — no tiene relación con los
  clientes finales de Max Limp, que ahora viven en la tabla `clientes`
  (identificados por `telefono`, igual que en WhatsApp).
- **Rol "usuario" → rol "vendedor"**: la pantalla que en Auratec era una
  tienda para que un cliente comprara con su propia cuenta, aquí se convirtió
  en `visualizaciones/pedidos_panel.py`: una pantalla para que el personal de
  Max Limp registre pedidos manuales (venta en el local, pedido telefónico,
  o cualquier pedido de WhatsApp que aún no pase por la automatización de n8n
  durante la fase de pruebas).
- **Panel admin** (`visualizaciones/dashboard.py`) ahora tiene 5 pestañas:
  Resumen (gráficos), Productos, Pedidos, Clientes, Usuarios.
- **Baja lógica de productos**: "Eliminar" ahora marca `activo = FALSE` en vez
  de borrar la fila, porque un producto ya vendido tiene historial en
  `detalle_pedido` y borrarlo rompería esos pedidos. El futuro catálogo de
  WhatsApp debe listar solo `activo = TRUE`.
- **Paleta de colores**: verde (línea de limpieza) en vez de azul.
- Se quitó `ofertas.py` (código de una tabla `ofertas` en SQLite que no
  llegó a integrarse en Auratec y no corresponde al esquema de Max Limp).
  Si más adelante quieres ofertas/descuentos, se puede añadir como tabla
  nueva sin tocar lo demás.

## Cómo correrlo

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requisitos.txt

cp .env.example .env
# edita .env con tus credenciales de Railway (ver instrucciones dentro del archivo)

python main.py
```

Usuarios de demo (se crean solos la primera vez que corres la app):

| Usuario  | Contraseña   | Rol      |
|----------|-------------|----------|
| admin    | admin123    | admin    |
| vendedor | vendedor123 | vendedor |

**Cambia estas contraseñas antes de usar la app con datos reales del
negocio** (Panel Admin → pestaña Usuarios → Editar).

## Dónde encaja esto en el proyecto completo

```
WhatsApp (cliente) ──► Meta Cloud API ──► Webhook n8n
                                              │
                                              ▼
                                    Nodo MySQL (n8n) ──► MISMA base de datos
                                              │           (productos, clientes,
                                              │            pedidos, detalle_pedido)
                                              ▼                    ▲
                                    Confirma por WhatsApp          │
                                                                   │
Este panel (main.py) ─────────────────────────────────────────────┘
  - Admin: gestiona catálogo, ve todos los pedidos, gestiona clientes/staff
  - Vendedor: registra pedidos manuales, consulta historial
```

Como n8n y este panel comparten exactamente las mismas tablas y el mismo
trigger de stock, no hace falta sincronizar nada entre ambos: el inventario
que ve el admin en el panel ya refleja los pedidos hechos por WhatsApp en
cuanto n8n los inserta.

## Pendiente (ver documento de contexto del proyecto)

- RUC de Max Limp para verificación de negocio en Meta.
- Número de WhatsApp Business dedicado (no el personal del tío).
- Reemplazar el catálogo de demo por la lista real de productos con fotos.
- Construir el workflow de n8n que consuma este mismo esquema (fuera del
  alcance de este panel — este panel ya está listo para que n8n apunte a
  la misma base de datos).
- Catálogo visual nativo de Meta y notificaciones de stock bajo quedan
  fuera del MVP, igual que en el documento de contexto original.
