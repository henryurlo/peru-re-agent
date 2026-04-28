# PeruRE — Demo Script para Presentar a un Asesor Inmobiliario

**Duración objetivo:** 10 minutos  
**Rol del presentador:** Tú eres el consultor tecnológico, no el vendedor. Escucha primero, demuestra después.  
**Dispositivo:** Idealmente tu celular (muestra que funciona mobile-first) o laptop con hotspot.

---

## 1. APERTURA — Ganar Contexto (2 min)

> *"Carlos, cuéntame: ¿Cuántas visitas programaste esta semana y cuántas se cayeron?"*

Deja que hable. No interrumpas. Anota mentalmente:
- Número de visitas canceladas / reprogramadas
- Distritos donde más trabaja
- Cómo confirma ahora (WhatsApp manual, llamadas, nada)

**Transición:**
> *"Eso es justo lo que le pasa a todos los asesores con los que hablo. Te voy a mostrar cómo lo resolvemos — y ojo, esto no es una app de delivery, es un sistema construido para inmobiliarias."*

---

## 2. LANDING PAGE — Primer Impacto (1 min)

**URL:** `http://<tu-servidor>:8000/pitch`

**Qué decir:**
> *"Esto es PeruRE. No es un CRM genérico, es un sistema que piensa como asesor en Lima."*

**Scrollea lento** mostrando:
1. Hero: "El Sistema que Tu Agencia Necesita"
2. Problema: tráfico, cancelaciones, leads perdidos
3. Solución: 4 funcionalidades con iconos
4. Botón "Ver Demo" — haz clic para entrar al panel

**Clave:** Que vea que entiendes SU dolor, no que estás vendiendo software genérico.

---

## 3. PANEL DEL ASESOR — El Corazón (4 min)

**URL:** `http://<tu-servidor>:8000/broker`

### A. Catálogo de Propiedades (1 min)

> *"Acá tenemos tus propiedades activas. Mira — departamento en Miraflores, casa colonial en Barranco, penthouse en San Isidro. Todo con precios en soles, metraje, amenities."*

**Toca** una tarjeta de propiedad. Muestra:
- Foto real
- Precio en S/
- Distrito taggeado con colores
- Dormitorios / baños / m2

**Pregunta:**
> *"¿Tienes fotos así de tus propiedades actuales? ¿O usas solo texto en Excel?"*

### B. Pipeline de Clientes (1 min)

> *"Estos son tus clientes activos. María está en 'Nuevo', Carlos está 'En Tour', Lucía está en 'Negociación'. Ves de un vistazo a quién le estás fallando en seguimiento."*

**Enfatiza:**
- Colores por etapa
- Iniciales con avatar
- Sin necesidad de abrir Excel ni el CRM

### C. Ruta de Tours en Mapa (1.5 min)

> *"Y acá viene lo bueno. Hoy tienes dos visitas: Miraflores a las 11, Barranco a las 2. El sistema ya calculó que están a 35 minutos de distancia considerando tráfico real."*

**Muestra el mapa:**
- Miraflores marcado en verde (confirmado)
- Barranco marcado en naranja (tentativo)
- Ruta visible entre ambos

**Luego toca:**
> *"Pero imagina que María cancela a las 10:30. Toca este botón..."*

**Presiona "Simular Cancelación".**

> *"El sistema inmediatamente: 1) busca otra propiedad cercana, 2) propone un nuevo horario, 3) prepara un mensaje de WhatsApp para el cliente. Tú solo apruebas."*

### D. Acciones Rápidas (0.5 min)

Muestra los 4 botones:
- Optimizar Ruta
- WhatsApp Cliente
- Reagendar Cita
- Simular Cancelación

> *"Todo esto es real. No es un mockup. Si conectas tu WhatsApp Business, los mensajes salen de verdad."*

---

## 4. ADMIN / MONITOREO — La Capa Oculta (1 min)

**URL:** `http://<tu-servidor>:8000/admin`

> *"Por detrás, el sistema tiene un tablero de control donde ves que todo está funcionando: servidores de mapas, calendario, WhatsApp, base de datos. Si algo se cae, lo sabes antes de que un cliente se queje."*

Muestra:
- MCP health (4 servicios verdes)
- Request log en tiempo real
- Broker activity

**Mensaje clave:**
> *"Esto no es una app de un solo uso. Es un sistema con backend, base de datos, microservicios — como Netflix o Spotify, pero para tu agencia."*

---

## 5. CIERRE — Próximo Paso (2 min)

**URL:** `http://<tu-servidor>:8000/proposal?agencia=Tu%20Agencia&asesor=Carlos`

> *"Carlos, esto no es un PowerPoint. Es una propuesta viva. Si te interesa, los próximos pasos son:"*

1. **Demo personalizada** — 30 min con TUS propiedades, TUS zonas
2. **Configuración** — subimos tu catálogo, tus horarios, tu zona de trabajo
3. **Prueba gratuita** — 7 días sin costo

**Muestra la propuesta impresa:**
> *"Mira, acá tienes la inversión: S/ 290 al mes. Sin contratos de permanencia. Y si entras en beta, el primer mes es S/ 149."*

**Cierra con pregunta abierta:**
> *"¿Qué te parece si agendamos la demo personalizada esta semana? ¿Martes o miércoles te funciona?"*

---

## OBJECIONES COMUNES — Respuestas

### "Yo ya uso Excel / Trello / un CRM"
> *"Perfecto, ¿sabes cuánto tiempo pierdes pasando datos entre Excel y WhatsApp? PeruRE conecta todo: mapas, clientes, mensajes, agenda. No reemplaza tu CRM, lo hace inteligente."*

### "Suena caro"
> *"Hagamos la cuenta: si te ayuda a cerrar UNA venta más al mes, ya pagó el año entero. Y si no te ahorra tiempo en 7 días de prueba, no pagas nada."*

### "No soy muy tecnológico"
> *"Justo por eso lo construimos así: tú solo tocas 'Aprobar' o 'Rechazar'. El sistema piensa, tú decides. Es como tener un asistente, no una computadora."*

### "Necesito hablarlo con mi socio"
> *"Claro. Te mando la propuesta por PDF y agendamos una demo de 15 minutos con ambos. Así él también ve cómo funciona."*

---

## CHECKLIST PRE-DEMO

- [ ] Servidor corriendo en `http://localhost:8000` (o tu IP pública)
- [ ] Datos demo cargados (`POST /api/v1/demo/seed` ya hecho si `DEMO_MODE=true`)
- [ ] Mapbox token funcional (mapa muestra marcadores)
- [ ] Abrir `/pitch`, `/broker`, `/admin`, `/proposal` en pestañas separadas
- [ ] Celular cargado o laptop con batería
- [ ] Conexión estable (mejor usar tu celular como hotspot que WiFi de café)

---

## NOTAS PARA EL PRESENTADOR

- **No digas "IA" o "inteligencia artificial" en los primeros 3 minutos.** Dile "sistema automatizado" o "asistente inteligente". La palabra "IA" asusta a algunos clientes.
- **Deja que toque la pantalla.** Si estás en tu celular, dáselo. El tacto genera propiedad.
- **Si el mapa no carga, no te estanques.** Dile *"En producción esto carga con tu token de Mapbox, ahora estamos en demo."* y sigue con el pipeline de clientes.
- **El objetivo no es que entienda cómo funciona.** Es que vea que SU problema ya está resuelto.

---

*¡Buena suerte con la demo! Si cierras al primer asesor, ya pagó todo el desarrollo.*
