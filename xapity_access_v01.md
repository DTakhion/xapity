---
marp: true
theme: default
paginate: true
size: 16:9

style: |
  section {
    font-size: 26px;
    padding: 45px 65px;
  }

  section.compact {
    font-size: 21px;
    padding: 30px 55px;
  }

  section.compact h1 {
    font-size: 36px;
    margin-bottom: 16px;
  }

  section.compact h3 {
    font-size: 24px;
    margin-top: 14px;
    margin-bottom: 8px;
  }

  section.compact table {
    font-size: 18px;
    line-height: 1.15;
  }

  section.compact table th,
  section.compact table td {
    padding: 5px 10px;
  }

  section.diagram {
    font-size: 22px;
    padding: 35px 55px;
  }

  section.diagram h1 {
    font-size: 38px;
  }

  section.architecture {
    font-size: 23px;
    padding: 38px 60px;
  }
---

# Xapity Access
### PoC v0.1 — Registro digital de acceso

**Objetivo:** reemplazar el registro manual en papel por un flujo digital simple, trazable y reutilizable.

---

<!-- _class: diagram -->

# Flujo Xapity Access — PoC v0.1

```text
                 XAPITY ACCESS

     ┌───────────────────────────────┐
     │        1. ONBOARDING          │
     │                               │
     │  Nombre / Apellido            │
     │  RUT                          │
     │  Teléfono                     │
     │  Contacto de emergencia       │
     │  Email + Password             │
     │  Aceptación de condiciones    │
     └──────────────┬────────────────┘
                    │
                    ▼
            VERIFICACIÓN EMAIL
                    │
                    ▼
               CUENTA ACTIVA
                    │
             llegada al recinto
                    │
                    ▼
              2. LOGIN / APP
                    │
                    ▼
             DASHBOARD USUARIO
                    │
                    ▼
                ESCANEAR QR
                    │
                    ▼
             CONFIRMAR INGRESO
                    │
                    ▼
               ACCESS EVENT
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
      USUARIO               RECEPCIÓN
 "Ingreso registrado"    Dashboard en tiempo real
                         Nombre | RUT | Hora
```

**Principio:** el registro del usuario ocurre una vez; el registro de acceso ocurre en cada visita.

---

<!-- _class: compact -->

# PoC v0.1 — Alcance funcional

| Capacidad | v0.1 | Observación |
|---|:---:|---|
| Registro de usuario | ✅ | Datos básicos y contacto |
| Validación matemática RUT | ✅ | Formato + dígito verificador |
| Verificación de email | ✅ | Código enviado al correo |
| Login / autenticación | ✅ | Email + password |
| Aceptación de condiciones | ✅ | Asociada al usuario |
| Dashboard usuario | ✅ | Orientado al ingreso |
| Escaneo QR | ✅ | QR asociado al recinto |
| Confirmación de ingreso | ✅ | Acción explícita del usuario |
| Access Event | ✅ | Usuario + recinto + fecha/hora |
| Dashboard recepción | ✅ | Visualización de ingresos |
| Historial de ingresos | ✅ | Registro básico |
| Identidad física verificada | ❌ | Fuera de la PoC |
| Geolocalización | ❌ | Evolución v0.2 |
| Biometría / documento | ❌ | Evolución posterior |

### La PoC demuestra el proceso completo E2E

**Registro → Verificación → Login → QR → Ingreso → Recepción**

---

<!-- _class: compact -->

# Dos conceptos que NO debemos confundir

<div style="display:flex; gap:50px; margin-top:20px;">

<div style="width:48%; text-align:center;">

## Email verificado ✓

El usuario demostró tener  
**control sobre la cuenta de correo.**

```text
Cuenta
  │
  ▼
Email
  │
  ▼
Código
  │
  ▼
✓ VERIFIED
```

</div>

<div style="width:48%; text-align:center;">

## Identidad verificada ○

Todavía NO demostramos que  
**la persona sea quien declara ser.**

```text
Nombre ─────┐
RUT ────────┤
            ├── ? ── Identidad
Persona ────┘
```

</div>

</div>

> **PoC v0.1:** verificamos la cuenta y registramos accesos.  
> La verificación física de identidad pertenece a una etapa posterior.

---

<!-- _class: compact -->

# Evolución — Xapity Access v0.2

```text
                         v0.1
                          │
                          ▼
                ┌───────────────────┐
                │   ACCESS EVENT    │
                │                   │
                │ usuario           │
                │ recinto           │
                │ fecha / hora      │
                │ QR                │
                └─────────┬─────────┘
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
       UBICACIÓN       IDENTIDAD       SEGURIDAD
            │             │             │
     Geolocalización   Foto cédula   Doble ingreso
     proximidad        Nombre/RUT    patrones anómalos
     al recinto        fotografía    accesos imposibles
            │             │             │
            └─────────────┼─────────────┘
                          ▼
                  MAYOR CONFIANZA
                   EN EL INGRESO
```

### Mejoras candidatas v0.2

- 📍 **Geolocalización:** comprobar proximidad física al recinto.
- 🪪 **Documento de identidad:** carga de cédula con datos no necesarios ocultos.
- 🚨 **Detección de anomalías:** doble ingreso o accesos temporalmente incompatibles.
- 🔄 **QR dinámico:** reducir reutilización o envío remoto del código.
- 👤 **Estado de identidad:** `UNVERIFIED → PENDING → VERIFIED`.

---

<!-- _class: compact -->

# Roadmap conceptual

```text
       PoC v0.1                    v0.2                     Futuro
────────────────────      ────────────────────      ───────────────────

Registro                  Geolocalización           Biometría facial
Email verificado          QR dinámico               Prueba de vida
Login                     Foto documento            Validación identidad
Aceptación                Risk / Alert Engine       Firma avanzada
QR                        Mayor evidencia           Fidelización
Access Event                                        Membresías
Dashboard recepción                                 Turnos / Agenda

        │                         │                         │
        ▼                         ▼                         ▼

  DIGITALIZAR               VERIFICAR                 EXPANDIR
  EL PROCESO                EL ACCESO                 LA PLATAFORMA
```

### Estrategia

**Primero reemplazamos el papel.**  
Luego aumentamos la confianza del acceso.  
Finalmente construimos servicios sobre una identidad y un historial digital.

---

<!-- _class: architecture -->

# Arquitectura de experiencia

<div style="font-size:20px;">

```text
                         XAPITY ACCESS
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
     EXPERIENCIA USUARIO             EXPERIENCIA RECEPCIÓN
          Mobile-first                   Desktop-first
              │                               │
              ▼                               ▼
        📱 Teléfono                     💻 PC / Tablet
              │                               │
        Login / Registro                 Usuarios
        Dashboard                       Ingresos
        Escanear QR                     Historial
        Confirmar acceso                Monitoreo
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ XAPITY ACCESS API │
                    └─────────┬─────────┘
                              │
                              ▼
                     Datos / Access Events
```

</div>

### Una plataforma, dos experiencias

**Usuario:** interfaz optimizada para teléfono y una acción principal: **ingresar**.

**Recepción:** interfaz optimizada para desktop/tablet y una acción principal: **supervisar**.

---

# Decisión tecnológica — v0.1

## Web App **mobile-first**

Xapity Access v0.1 será una **Web App mobile-first**, potencialmente **PWA**, con interfaz de usuario optimizada para teléfono e interfaz administrativa optimizada para desktop/tablet.

```text
               xapity-access.app
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
     📱 USUARIO                 💻 RECEPCIÓN
    Mobile-first               Desktop-first
          │                         │
          └────────────┬────────────┘
                       ▼
                XAPITY ACCESS API
```

### ¿Por qué comenzar así?

**Sin instalación obligatoria · Acceso inmediato · Cámara/QR · Geolocalización futura · Un solo backend**

> Una aplicación móvil nativa puede incorporarse posteriormente sin reemplazar la arquitectura base.

---

# Xapity Access — PoC

> **De una hoja que termina archivada y desechada...**
>
> **a un registro digital, trazable y reutilizable.**

### v0.1

**Usuario → Cuenta → QR → Access Event → Recepción**

La PoC no busca resolver todos los problemas de identidad y seguridad.

**Busca demostrar que el proceso actual puede ser reemplazado de punta a punta.**

---

# Xapity Access

### PoC v0.1

**Web App mobile-first · Registro digital · Acceso por QR · Trazabilidad**

```text
REGISTRAR              INGRESAR              SUPERVISAR
    │                      │                      │
    ▼                      ▼                      ▼
 Usuario  ───────────► Access Event ─────────► Recepción
```

**Primero digitalizamos el acceso.  
Después aumentamos la confianza.  
Finalmente expandimos la plataforma.**
